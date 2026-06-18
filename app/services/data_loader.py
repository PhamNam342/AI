from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from app.services.env import load_local_env

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
MOVIES_PATH = DATA_DIR / "movies.csv"
RATINGS_PATH = DATA_DIR / "ratings.csv"
USER_RATINGS_PATH = DATA_DIR / "user_ratings.json"

load_local_env()


def load_movies(movies_path: Path | None = None) -> pd.DataFrame:
    path = movies_path or MOVIES_PATH
    movies = pd.read_csv(path)
    required_columns = {"movieId", "title", "genres"}

    missing_columns = required_columns.difference(movies.columns)
    if missing_columns:
        raise ValueError(f"movies.csv is missing columns: {sorted(missing_columns)}")

    return movies


def load_ratings(
    ratings_path: Path | None = None,
    min_ratings_per_user: int = 20,
    include_saved_ratings: bool = True,
) -> pd.DataFrame:
    path = ratings_path or RATINGS_PATH
    ratings = pd.read_csv(path)
    required_columns = {"userId", "movieId", "rating"}

    missing_columns = required_columns.difference(ratings.columns)
    if missing_columns:
        raise ValueError(f"ratings.csv is missing columns: {sorted(missing_columns)}")

    if min_ratings_per_user > 0:
        user_counts = ratings["userId"].value_counts()
        active_users = user_counts[user_counts >= min_ratings_per_user].index
        ratings = ratings[ratings["userId"].isin(active_users)].copy()

    if include_saved_ratings:
        ratings = merge_saved_user_ratings(ratings)

    return ratings


def load_movie_data(min_ratings_per_user: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    movies, ratings, _ = load_movie_data_with_metadata(min_ratings_per_user=min_ratings_per_user)
    return movies, ratings


def load_movie_data_with_metadata(
    min_ratings_per_user: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    saved_rating_count = count_saved_user_ratings()
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            movies, ratings = load_movie_data_from_database(
                database_url=database_url,
                min_ratings_per_user=min_ratings_per_user,
            )
            if not movies.empty and not ratings.empty:
                ratings = merge_saved_user_ratings(ratings)
                return movies, ratings, {
                    "source": "database",
                    "saved_rating_count": str(saved_rating_count),
                }
            warning = "Database returned no MovieLens-compatible movies or ratings."
        except Exception as exc:
            warning = f"Database unavailable, using CSV files instead: {exc}"
    else:
        warning = "DATABASE_URL is not configured; using CSV files."

    movies = load_movies()
    ratings = load_ratings(min_ratings_per_user=min_ratings_per_user)
    return movies, ratings, {
        "source": "csv",
        "warning": warning,
        "saved_rating_count": str(saved_rating_count),
    }


def load_movie_data_from_database(
    database_url: str,
    min_ratings_per_user: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is not installed") from exc

    with psycopg.connect(database_url, connect_timeout=3) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    movielens_movie_id,
                    title,
                    array_to_string(genres, '|')
                from movies
                where movielens_movie_id is not null
                order by movielens_movie_id
                """,
            )
            movies = pd.DataFrame(
                cur.fetchall(),
                columns=["movieId", "title", "genres"],
            )

            cur.execute(
                """
                select
                    u.external_user_id::integer,
                    m.movielens_movie_id,
                    r.rating::float
                from user_ratings r
                join app_users u on u.id = r.user_id
                join movies m on m.id = r.movie_id
                where u.external_user_id ~ '^[0-9]+$'
                  and m.movielens_movie_id is not null
                """,
            )
            ratings = pd.DataFrame(
                cur.fetchall(),
                columns=["userId", "movieId", "rating"],
            )

    if min_ratings_per_user > 0 and not ratings.empty:
        user_counts = ratings["userId"].value_counts()
        active_users = user_counts[user_counts >= min_ratings_per_user].index
        ratings = ratings[ratings["userId"].isin(active_users)].copy()

    return movies, ratings


def load_saved_user_ratings(path: Path | None = None) -> pd.DataFrame:
    ratings_path = path or USER_RATINGS_PATH
    if not ratings_path.exists():
        return pd.DataFrame(columns=["userId", "movieId", "rating"])

    payload = json.loads(ratings_path.read_text(encoding="utf-8"))
    rows = []
    for user_id, movie_ratings in payload.items():
        for movie_id, rating in movie_ratings.items():
            rows.append(
                {
                    "userId": int(user_id),
                    "movieId": int(movie_id),
                    "rating": float(rating),
                },
            )

    return pd.DataFrame(rows, columns=["userId", "movieId", "rating"])


def merge_saved_user_ratings(ratings: pd.DataFrame) -> pd.DataFrame:
    saved_ratings = load_saved_user_ratings()
    if saved_ratings.empty:
        return ratings

    merged = pd.concat([ratings, saved_ratings], ignore_index=True)
    return merged.drop_duplicates(
        subset=["userId", "movieId"],
        keep="last",
    )


def count_saved_user_ratings() -> int:
    return int(len(load_saved_user_ratings()))
