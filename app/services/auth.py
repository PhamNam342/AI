from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
AUTH_USERS_PATH = BASE_DIR / "data" / "app_users.json"
AUTH_SESSIONS_PATH = BASE_DIR / "data" / "user_sessions.json"
SESSION_DAYS = 14


def register_user(username: str, password: str, display_name: str | None = None) -> dict[str, Any]:
    username = normalize_username(username)
    validate_password(password)

    data = _load_json(AUTH_USERS_PATH, {"next_user_id": 10000, "users": {}})
    if username in data["users"]:
        raise ValueError("Username already exists.")

    user_id = int(data["next_user_id"])
    data["next_user_id"] = user_id + 1
    data["users"][username] = {
        "user_id": user_id,
        "username": username,
        "display_name": display_name or username,
        "password_hash": hash_password(password),
        "created_at": utc_now(),
    }
    _save_json(AUTH_USERS_PATH, data)
    return public_user(data["users"][username])


def authenticate_user(username: str, password: str) -> dict[str, Any]:
    username = normalize_username(username)
    data = _load_json(AUTH_USERS_PATH, {"next_user_id": 10000, "users": {}})
    user = data["users"].get(username)
    if not user or not verify_password(password, user["password_hash"]):
        raise ValueError("Invalid username or password.")
    return public_user(user)


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    sessions = _load_json(AUTH_SESSIONS_PATH, {"sessions": []})
    sessions["sessions"].append(
        {
            "token_hash": hash_token(token),
            "user_id": int(user_id),
            "expires_at": (datetime.utcnow() + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds") + "Z",
            "created_at": utc_now(),
        },
    )
    _save_json(AUTH_SESSIONS_PATH, sessions)
    return token


def get_user_by_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None

    token_hash = hash_token(token)
    sessions = _load_json(AUTH_SESSIONS_PATH, {"sessions": []})
    active_session = None
    for session in sessions["sessions"]:
        if session["token_hash"] == token_hash and session["expires_at"] > utc_now():
            active_session = session
            break

    if not active_session:
        return None

    users = _load_json(AUTH_USERS_PATH, {"next_user_id": 10000, "users": {}})["users"]
    for user in users.values():
        if int(user["user_id"]) == int(active_session["user_id"]):
            return public_user(user)
    return None


def revoke_session(token: str | None) -> None:
    if not token or not AUTH_SESSIONS_PATH.exists():
        return

    token_hash = hash_token(token)
    sessions = _load_json(AUTH_SESSIONS_PATH, {"sessions": []})
    sessions["sessions"] = [
        session for session in sessions["sessions"] if session["token_hash"] != token_hash
    ]
    _save_json(AUTH_SESSIONS_PATH, sessions)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    algorithm, salt, digest = password_hash.split("$", 2)
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260_000)
    return hmac.compare_digest(candidate.hex(), digest)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if len(normalized) < 3:
        raise ValueError("Username must be at least 3 characters.")
    return normalized


def validate_password(password: str) -> None:
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": int(user["user_id"]),
        "username": user["username"],
        "display_name": user.get("display_name") or user["username"],
    }


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"
