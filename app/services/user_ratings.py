from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.env import load_local_env


BASE_DIR = Path(__file__).resolve().parents[2]
USER_RATINGS_PATH = BASE_DIR / "data" / "user_ratings.json"

load_local_env()


def get_saved_user_ratings(user_id: int) -> dict[int, float]:
    all_ratings = _load_ratings()
    user_ratings = all_ratings.get(str(user_id), {})
    return {int(movie_id): float(rating) for movie_id, rating in user_ratings.items()}


def save_user_rating(user_id: int, movie_id: int, rating: float) -> dict[str, Any]:
    if rating < 0.5 or rating > 5.0:
        raise ValueError("rating must be between 0.5 and 5.0")

    normalized_rating = round(rating * 2) / 2
    all_ratings = _load_ratings()
    user_key = str(user_id)
    user_ratings = all_ratings.setdefault(user_key, {})
    user_ratings[str(movie_id)] = normalized_rating

    _save_ratings(all_ratings)

    storage = "local"
    if _try_save_to_postgres(user_id=user_id, movie_id=movie_id, rating=normalized_rating):
        storage = "local+postgres"

    return {
        "user_id": user_id,
        "movie_id": movie_id,
        "rating": normalized_rating,
        "storage": storage,
        "ratings": get_saved_user_ratings(user_id),
    }


def _load_ratings() -> dict[str, Any]:
    if not USER_RATINGS_PATH.exists():
        return {}

    with USER_RATINGS_PATH.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def _save_ratings(ratings: dict[str, Any]) -> None:
    USER_RATINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "users": ratings,
    }
    with USER_RATINGS_PATH.open("w", encoding="utf-8") as file_obj:
        json.dump(payload["users"], file_obj, indent=2, sort_keys=True)


def _try_save_to_postgres(user_id: int, movie_id: int, rating: float) -> bool:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return False

    try:
        import psycopg
    except ImportError:
        return False

    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into user_ratings (user_id, movie_id, rating, source)
                    select u.id, m.id, %s, 'movielens'::user_source
                    from app_users u
                    join movies m on m.movielens_movie_id = %s
                    where u.source = 'movielens'
                      and u.external_user_id = %s
                    on conflict (user_id, movie_id) do update
                    set
                        rating = excluded.rating,
                        rated_at = now(),
                        source = excluded.source
                    """,
                    (rating, movie_id, str(user_id)),
                )
            conn.commit()
        return True
    except Exception:
        return False
