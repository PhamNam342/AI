from __future__ import annotations

import json
import pickle
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from surprise import Dataset
from surprise import Reader
from surprise import SVD
from surprise import accuracy
from surprise.model_selection import train_test_split

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from app.services.data_loader import load_movie_data_with_metadata
else:
    from app.services.data_loader import load_movie_data_with_metadata


BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "model"
MODEL_PATH = MODEL_DIR / "svd_model.pkl"
TRAINING_RUNS_PATH = BASE_DIR / "data" / "training_runs.json"


def train_svd_model(
    test_size: float = 0.2,
    random_state: int = 42,
    min_ratings_per_user: int = 20,
    max_rmse: float = 1.2,
) -> dict:
    _, ratings, metadata = load_movie_data_with_metadata(
        min_ratings_per_user=min_ratings_per_user,
    )

    reader = Reader(rating_scale=(0.5, 5.0)) # MovieLens ratings are typically between 0.5 and 5.0
    data = Dataset.load_from_df(ratings[["userId", "movieId", "rating"]], reader)
    trainset, testset = train_test_split(
        data,
        test_size=test_size,
        random_state=random_state,
    )
    model = SVD(random_state=random_state)
    model.fit(trainset)
    predictions = model.test(testset)
    rmse = accuracy.rmse(predictions, verbose=False)
    mae = accuracy.mae(predictions, verbose=False)
    if rmse > max_rmse:
        raise ValueError(f"RMSE {rmse:.4f} is above quality gate {max_rmse:.4f}")

    return {
        "model": model,
        "metrics": {
            "rmse": rmse,
            "mae": mae,
        },
        "config": {
            "test_size": test_size,
            "random_state": random_state,
            "min_ratings_per_user": min_ratings_per_user,
            "max_rmse": max_rmse,
            "data_source": metadata["source"],
            "data_warning": metadata.get("warning"),
            "saved_rating_count": int(metadata.get("saved_rating_count", 0)),
            "training_rating_count": int(len(ratings)),
        },
    }


def save_model(artifact: dict, model_path: Path | None = None) -> Path:
    path = model_path or MODEL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with temp_path.open("wb") as file_obj:
        pickle.dump(artifact, file_obj)
    temp_path.replace(path)

    return path


def train_and_save_model(
    model_path: Path | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
    min_ratings_per_user: int = 20,
    max_rmse: float = 1.2,
) -> tuple[dict, Path]:
    run_id = str(uuid4())
    started_at = _utc_now()

    try:
        artifact = train_svd_model(
            test_size=test_size,
            random_state=random_state,
            min_ratings_per_user=min_ratings_per_user,
            max_rmse=max_rmse,
        )
        saved_path = save_model(artifact, model_path=model_path)
    except Exception as exc:
        record_training_run(
            {
                "id": run_id,
                "status": "failed",
                "started_at": started_at,
                "finished_at": _utc_now(),
                "error_message": str(exc),
                "model_path": str(model_path or MODEL_PATH),
            },
        )
        raise

    record_training_run(
        {
            "id": run_id,
            "status": "succeeded",
            "started_at": started_at,
            "finished_at": _utc_now(),
            "metrics": artifact["metrics"],
            "config": artifact["config"],
            "model_path": str(saved_path),
        },
    )
    return artifact, saved_path


def record_training_run(run: dict) -> None:
    TRAINING_RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TRAINING_RUNS_PATH.exists():
        runs = json.loads(TRAINING_RUNS_PATH.read_text(encoding="utf-8"))
    else:
        runs = []

    runs.append(run)
    TRAINING_RUNS_PATH.write_text(
        json.dumps(runs[-50:], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_training_runs(limit: int = 10) -> list[dict]:
    if not TRAINING_RUNS_PATH.exists():
        return []

    runs = json.loads(TRAINING_RUNS_PATH.read_text(encoding="utf-8"))
    return list(reversed(runs[-limit:]))


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


if __name__ == "__main__":
    artifact, saved_path = train_and_save_model()
    metrics = artifact["metrics"]

    print(f"Saved model to: {saved_path}")
    print(f"RMSE: {metrics['rmse']:.4f}")
    print(f"MAE: {metrics['mae']:.4f}")
