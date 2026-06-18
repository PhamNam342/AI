from __future__ import annotations

import pickle
import sys
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2])) # This allows running the script directly for testing purposes
    from app.services.data_loader import load_movie_data
    from app.services.user_ratings import get_saved_user_ratings
else:
    from app.services.data_loader import load_movie_data
    from app.services.user_ratings import get_saved_user_ratings

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = BASE_DIR / "model" / "svd_model.pkl"


def load_trained_model(model_path: Path | None = None) -> dict:
    path = model_path or MODEL_PATH
    with path.open("rb") as file_obj:
        return pickle.load(file_obj)


def get_popular_movies(
    movies: pd.DataFrame,
    ratings: pd.DataFrame,
    top_n: int = 10,
    min_rating_count: int = 20,
) -> list[dict]:
    movie_stats = (
        ratings.groupby("movieId")["rating"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "predicted_rating", "count": "rating_count"})
        .reset_index()
    )
    movie_stats = movie_stats[movie_stats["rating_count"] >= min_rating_count]

    recommendations = (
        movie_stats.merge(movies, on="movieId", how="left")
        .sort_values(["predicted_rating", "rating_count"], ascending=[False, False])
        .head(top_n)
    )

    return recommendations[
        ["movieId", "title", "genres", "predicted_rating", "rating_count"]
    ].to_dict(orient="records")


def recommend_for_user(
    user_id: int,
    top_n: int = 10,
    model_path: Path | None = None,
) -> list[dict]:
    return recommend_for_user_with_context(
        user_id=user_id,
        top_n=top_n,
        model_path=model_path,
    )["recommendations"]


def recommend_for_user_with_context(
    user_id: int,
    top_n: int = 10,
    model_path: Path | None = None,
) -> dict:
    artifact = load_trained_model(model_path=model_path)
    model = artifact["model"]
    min_ratings_per_user = artifact["config"]["min_ratings_per_user"]
    movies, ratings = load_movie_data(min_ratings_per_user=min_ratings_per_user)
    saved_ratings = get_saved_user_ratings(user_id)

    if saved_ratings:
        recommendations = recommend_from_saved_ratings(
            movies=movies,
            ratings=ratings,
            user_id=user_id,
            saved_ratings=saved_ratings,
            top_n=top_n,
        )
        return {
            "strategy": "personal_genre",
            "strategy_label": "Personalized from your ratings",
            "recommendations": recommendations,
        }

    if user_id not in ratings["userId"].values:
        return {
            "strategy": "popular",
            "strategy_label": "Popular movies fallback",
            "recommendations": get_popular_movies(movies, ratings, top_n=top_n),
        }

    rated_movie_ids = set(ratings.loc[ratings["userId"] == user_id, "movieId"])
    candidate_movies = movies[~movies["movieId"].isin(rated_movie_ids)].copy()

    candidate_movies["predicted_rating"] = candidate_movies["movieId"].apply(
        lambda movie_id: model.predict(user_id, movie_id).est
    )

    recommendations = candidate_movies.sort_values(
        "predicted_rating",
        ascending=False,
    ).head(top_n)

    return {
        "strategy": "svd",
        "strategy_label": "SVD collaborative filtering",
        "recommendations": recommendations[
            ["movieId", "title", "genres", "predicted_rating"]
        ].to_dict(orient="records"),
    }


def recommend_from_saved_ratings(
    movies: pd.DataFrame,
    ratings: pd.DataFrame,
    user_id: int,
    saved_ratings: dict[int, float],
    top_n: int = 10,
) -> list[dict]:
    user_rated_movie_ids = set(saved_ratings)
    rated_movies = movies[movies["movieId"].isin(user_rated_movie_ids)]
    genre_weights = _build_genre_weights(rated_movies, saved_ratings)

    if not genre_weights:
        return get_popular_movies(movies, ratings, top_n=top_n)

    excluded_movie_ids = set(user_rated_movie_ids)
    if user_id in ratings["userId"].values:
        excluded_movie_ids.update(ratings.loc[ratings["userId"] == user_id, "movieId"])

    movie_stats = (
        ratings.groupby("movieId")["rating"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "average_rating", "count": "rating_count"})
        .reset_index()
    )

    candidates = (
        movies[~movies["movieId"].isin(excluded_movie_ids)]
        .merge(movie_stats, on="movieId", how="left")
        .fillna({"average_rating": 0, "rating_count": 0})
    )
    candidates = candidates[candidates["rating_count"] >= 20].copy()

    candidates["genre_score"] = candidates["genres"].apply(
        lambda genres: sum(genre_weights.get(genre, 0) for genre in _split_genres(genres))
    )
    candidates = candidates[candidates["genre_score"] > 0].copy()

    if candidates.empty:
        return get_popular_movies(movies, ratings, top_n=top_n)

    candidates["predicted_rating"] = (
        candidates["genre_score"] * 0.7
        + (candidates["average_rating"] / 5.0) * 0.25
        + (candidates["rating_count"].clip(upper=200) / 200.0) * 0.05
    ) * 5.0
    candidates["reason"] = candidates["genres"].apply(
        lambda genres: ", ".join(
            genre for genre in _split_genres(genres) if genre in genre_weights
        )
    )

    recommendations = candidates.sort_values(
        ["predicted_rating", "average_rating", "rating_count"],
        ascending=[False, False, False],
    ).head(top_n)

    return recommendations[
        ["movieId", "title", "genres", "predicted_rating", "rating_count", "reason"]
    ].to_dict(orient="records")


def _build_genre_weights(rated_movies: pd.DataFrame, saved_ratings: dict[int, float]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for movie in rated_movies.to_dict(orient="records"):
        preference = saved_ratings.get(int(movie["movieId"]), 0) - 2.5
        if preference <= 0:
            continue

        genres = movie["genres"]
        for genre in _split_genres(genres):
            weights[genre] = weights.get(genre, 0.0) + preference

    total = sum(weights.values())
    if total <= 0:
        return {}

    return {genre: weight / total for genre, weight in weights.items()}


def _split_genres(genres: str) -> list[str]:
    if not genres or genres == "(no genres listed)":
        return []
    return [genre for genre in str(genres).split("|") if genre]


if __name__ == "__main__":
    user_id = 1
    recommendations = recommend_for_user(user_id=user_id, top_n=10)

    print(f"Top recommendations for user {user_id}:")
    for item in recommendations:
        print(f"{item['title']} ({item['predicted_rating']:.2f})")
