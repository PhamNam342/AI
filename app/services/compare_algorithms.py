from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from surprise import Dataset
from surprise import KNNWithMeans
from surprise import Reader
from surprise import SVD
from surprise import accuracy
from surprise.model_selection import train_test_split

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from app.services.data_loader import load_movie_data
else:
    from app.services.data_loader import load_movie_data


@dataclass
class AlgorithmResult:
    name: str
    rmse: float
    mae: float
    fit_seconds: float
    test_seconds: float


def compare_svd_and_knn(
    test_size: float = 0.2,
    random_state: int = 42,
    min_ratings_per_user: int = 20,
    knn_k: int = 40,
    knn_min_k: int = 1,
) -> list[AlgorithmResult]:
    _, ratings = load_movie_data(min_ratings_per_user=min_ratings_per_user)
    reader = Reader(rating_scale=(0.5, 5.0))
    data = Dataset.load_from_df(ratings[["userId", "movieId", "rating"]], reader)
    trainset, testset = train_test_split(
        data,
        test_size=test_size,
        random_state=random_state,
    )

    algorithms = [
        (
            "SVD matrix factorization",
            SVD(random_state=random_state),
        ),
        (
            "Item-based KNNWithMeans",
            KNNWithMeans(
                k=knn_k,
                min_k=knn_min_k,
                sim_options={
                    "name": "cosine",
                    "user_based": False,
                },
                verbose=False,
            ),
        ),
    ]

    results = []
    for name, algorithm in algorithms:
        fit_started_at = time.perf_counter()
        algorithm.fit(trainset)
        fit_seconds = time.perf_counter() - fit_started_at

        test_started_at = time.perf_counter()
        predictions = algorithm.test(testset)
        test_seconds = time.perf_counter() - test_started_at

        results.append(
            AlgorithmResult(
                name=name,
                rmse=accuracy.rmse(predictions, verbose=False),
                mae=accuracy.mae(predictions, verbose=False),
                fit_seconds=fit_seconds,
                test_seconds=test_seconds,
            ),
        )

    return results


def print_comparison_table(results: list[AlgorithmResult]) -> None:
    print("Algorithm comparison on the same train/test split")
    print()
    print(f"{'Algorithm':<28} {'RMSE':>8} {'MAE':>8} {'Fit(s)':>8} {'Test(s)':>8}")
    print("-" * 64)
    for result in results:
        print(
            f"{result.name:<28} "
            f"{result.rmse:>8.4f} "
            f"{result.mae:>8.4f} "
            f"{result.fit_seconds:>8.2f} "
            f"{result.test_seconds:>8.2f}"
        )

    best = min(results, key=lambda result: result.rmse)
    print()
    print(f"Best RMSE: {best.name} ({best.rmse:.4f})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare SVD and KNN collaborative-filtering algorithms.",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--min-ratings-per-user", type=int, default=20)
    parser.add_argument("--knn-k", type=int, default=40)
    parser.add_argument("--knn-min-k", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = compare_svd_and_knn(
        test_size=args.test_size,
        random_state=args.random_state,
        min_ratings_per_user=args.min_ratings_per_user,
        knn_k=args.knn_k,
        knn_min_k=args.knn_min_k,
    )
    print_comparison_table(results)


if __name__ == "__main__":
    main()
