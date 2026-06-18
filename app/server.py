from __future__ import annotations

import argparse
import json
import mimetypes
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import urlparse

from app.services.auth import authenticate_user
from app.services.auth import create_session
from app.services.auth import get_user_by_session
from app.services.auth import register_user
from app.services.auth import revoke_session
from app.services.data_loader import load_movie_data
from app.services.data_loader import load_movie_data_with_metadata
from app.services.env import load_local_env
from app.services.recommender import MODEL_PATH
from app.services.recommender import recommend_for_user_with_context
from app.services.trainer import load_training_runs
from app.services.trainer import train_and_save_model
from app.services.user_ratings import get_saved_user_ratings
from app.services.user_ratings import save_user_rating


APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
STATIC_DIR = APP_DIR / "static"
INDEX_PATH = STATIC_DIR / "index.html"

load_local_env()


class RecommendationHandler(BaseHTTPRequestHandler):
    server_version = "MovieRecommender/1.0"

    def do_HEAD(self) -> None:
        parsed_url = urlparse(self.path)
        if parsed_url.path in {"/", "/api/summary", "/api/recommendations"} or parsed_url.path.startswith("/static/"):
            self.send_response(HTTPStatus.OK)
            self.end_headers()
            return

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/":
            self._send_file(INDEX_PATH)
            return

        if parsed_url.path.startswith("/static/"):
            safe_path = parsed_url.path.removeprefix("/static/").strip("/")
            self._send_file(STATIC_DIR / safe_path)
            return

        if parsed_url.path == "/api/summary":
            self._send_json(build_summary())
            return

        if parsed_url.path == "/api/recommendations":
            self._handle_recommendations(parsed_url.query)
            return

        if parsed_url.path == "/api/user-ratings":
            self._handle_user_ratings(parsed_url.query)
            return

        if parsed_url.path == "/api/auth/me":
            self._handle_auth_me()
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/api/ratings":
            self._handle_rating()
            return

        if parsed_url.path == "/api/train":
            self._handle_train()
            return

        if parsed_url.path == "/api/auth/register":
            self._handle_auth_register()
            return

        if parsed_url.path == "/api/auth/login":
            self._handle_auth_login()
            return

        if parsed_url.path == "/api/auth/logout":
            self._handle_auth_logout()
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def _handle_recommendations(self, query: str) -> None:
        params = parse_qs(query)

        try:
            user_id = self._resolve_user_id(params)
            top_n = int(params.get("top_n", ["10"])[0])
        except (ValueError, PermissionError):
            self._send_json(
                {"error": "Login or provide numeric user_id."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        top_n = max(1, min(top_n, 30))

        try:
            recommendation_payload = recommend_for_user_with_context(
                user_id=user_id,
                top_n=top_n,
            )
            self._send_json(
                {
                    "user_id": user_id,
                    "top_n": top_n,
                    "user_ratings": get_saved_user_ratings(user_id),
                    **recommendation_payload,
                },
            )
        except FileNotFoundError:
            self._send_json(
                {
                    "error": "Model file was not found.",
                    "detail": "Run: python -m app.services.trainer",
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )

    def _handle_user_ratings(self, query: str) -> None:
        params = parse_qs(query)

        try:
            user_id = self._resolve_user_id(params)
        except (ValueError, PermissionError):
            self._send_json(
                {"error": "Login or provide numeric user_id."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        self._send_json({"user_id": user_id, "user_ratings": get_saved_user_ratings(user_id)})

    def _handle_rating(self) -> None:
        try:
            payload = self._read_json_body()
            user_id = int(payload.get("user_id") or self._current_user()["user_id"])
            movie_id = int(payload["movie_id"])
            rating = float(payload["rating"])
        except (KeyError, TypeError, ValueError, PermissionError, json.JSONDecodeError):
            self._send_json(
                {"error": "Expected login, movie_id and rating."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            result = save_user_rating(
                user_id=user_id,
                movie_id=movie_id,
                rating=rating,
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        self._send_json(result, status=HTTPStatus.CREATED)

    def _handle_auth_register(self) -> None:
        try:
            payload = self._read_json_body()
            user = register_user(
                username=str(payload["username"]),
                password=str(payload["password"]),
                display_name=str(payload.get("display_name") or payload["username"]),
            )
            token = create_session(user["user_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"user": user}, status=HTTPStatus.CREATED, session_token=token)

    def _handle_auth_login(self) -> None:
        try:
            payload = self._read_json_body()
            user = authenticate_user(
                username=str(payload["username"]),
                password=str(payload["password"]),
            )
            token = create_session(user["user_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"user": user}, session_token=token)

    def _handle_auth_logout(self) -> None:
        revoke_session(self._session_token())
        self._send_json({"status": "logged_out"}, clear_session=True)

    def _handle_auth_me(self) -> None:
        self._send_json({"user": self._current_user(required=False)})

    def _handle_train(self) -> None:
        try:
            artifact, saved_path = train_and_save_model()
        except Exception as exc:
            self._send_json(
                {
                    "error": "Training failed. Existing model was kept.",
                    "detail": str(exc),
                    "training_runs": load_training_runs(),
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        self._send_json(
            {
                "status": "succeeded",
                "model_path": str(saved_path),
                "metrics": artifact["metrics"],
                "config": artifact["config"],
                "training_runs": load_training_runs(),
            },
            status=HTTPStatus.CREATED,
        )

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        return json.loads(raw_body.decode("utf-8"))

    def _send_file(self, path: Path) -> None:
        try:
            resolved_path = path.resolve()
            static_root = STATIC_DIR.resolve()
            if resolved_path != static_root and static_root not in resolved_path.parents:
                raise FileNotFoundError

            content = resolved_path.read_bytes()
        except FileNotFoundError:
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(resolved_path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(
        self,
        payload: dict,
        status: HTTPStatus = HTTPStatus.OK,
        session_token: str | None = None,
        clear_session: bool = False,
    ) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        if session_token:
            self.send_header(
                "Set-Cookie",
                f"movie_session={session_token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=1209600",
            )
        if clear_session:
            self.send_header(
                "Set-Cookie",
                "movie_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
            )
        self.end_headers()
        self.wfile.write(content)

    def _resolve_user_id(self, params: dict) -> int:
        raw_user_id = params.get("user_id", [""])[0]
        if raw_user_id:
            return int(raw_user_id)

        user = self._current_user()
        return int(user["user_id"])

    def _current_user(self, required: bool = True) -> dict | None:
        user = get_user_by_session(self._session_token())
        if required and not user:
            raise PermissionError("Login required.")
        return user

    def _session_token(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie"))
        morsel = cookie.get("movie_session")
        return morsel.value if morsel else None

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def build_summary() -> dict:
    movies, ratings, metadata = load_movie_data_with_metadata()

    summary = {
        "movie_count": int(len(movies)),
        "rating_count": int(len(ratings)),
        "user_count": int(ratings["userId"].nunique()),
        "user_min": int(ratings["userId"].min()),
        "user_max": int(ratings["userId"].max()),
        "model_exists": MODEL_PATH.exists(),
        "model_path": str(MODEL_PATH),
        "data_source": metadata["source"],
        "data_warning": metadata.get("warning"),
        "algorithm": "SVD",
        "saved_rating_count": int(metadata.get("saved_rating_count", 0)),
        "training_runs": load_training_runs(),
    }

    if MODEL_PATH.exists():
        try:
            import pickle

            with MODEL_PATH.open("rb") as file_obj:
                artifact = pickle.load(file_obj)
            summary["metrics"] = artifact.get("metrics", {})
            summary["config"] = artifact.get("config", {})
        except Exception as exc:  # pragma: no cover - defensive UI metadata.
            summary["model_warning"] = str(exc)

    return summary


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), RecommendationHandler)
    print(f"Movie recommender is running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the movie recommendation web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
