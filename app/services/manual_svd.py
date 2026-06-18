from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable


Rating = tuple[int, int, float]
@dataclass
class PredictionError:
    rmse: float
    mae: float


class ManualSVD:
    """Small educational matrix-factorization recommender.

    The production app uses surprise.SVD in trainer.py. This class is a compact
    from-scratch version so the algorithm is easier to inspect.
    """

    def __init__(
        self,
        factors: int = 20,
        learning_rate: float = 0.005,
        regularization: float = 0.02,
        epochs: int = 20,
        random_state: int = 42,
        rating_min: float = 0.5,
        rating_max: float = 5.0,
    ) -> None:
        self.factors = factors
        self.learning_rate = learning_rate
        self.regularization = regularization
        self.epochs = epochs
        self.random_state = random_state
        self.rating_min = rating_min
        self.rating_max = rating_max

        self.global_mean = 0.0
        self.user_biases: dict[int, float] = {}
        self.movie_biases: dict[int, float] = {}
        self.user_factors: dict[int, list[float]] = {}
        self.movie_factors: dict[int, list[float]] = {}

    def fit(self, ratings: Iterable[Rating]) -> None:
        training_data = list(ratings)
        if not training_data:
            raise ValueError("ratings must not be empty")

        random_generator = random.Random(self.random_state)
        self.global_mean = sum(rating for _, _, rating in training_data) / len(training_data)

        for user_id, movie_id, _ in training_data:
            self._init_user(user_id, random_generator)
            self._init_movie(movie_id, random_generator)

        for _ in range(self.epochs):
            random_generator.shuffle(training_data)
            for user_id, movie_id, actual_rating in training_data:
                predicted_rating = self.predict(user_id, movie_id)
                error = actual_rating - predicted_rating
                self._learn_from_error(user_id, movie_id, error)

    def predict(self, user_id: int, movie_id: int) -> float:
        user_vector = self.user_factors.get(user_id)
        movie_vector = self.movie_factors.get(movie_id)
        if user_vector is None or movie_vector is None:
            return self._clip(self.global_mean)

        dot_product = sum(
            user_value * movie_value
            for user_value, movie_value in zip(user_vector, movie_vector)
        )
        prediction = (
            self.global_mean
            + self.user_biases.get(user_id, 0.0)
            + self.movie_biases.get(movie_id, 0.0)
            + dot_product
        )
        return self._clip(prediction)

    def evaluate(self, ratings: Iterable[Rating]) -> PredictionError:
        test_data = list(ratings)
        if not test_data:
            raise ValueError("ratings must not be empty")

        absolute_error_sum = 0.0
        squared_error_sum = 0.0
        for user_id, movie_id, actual_rating in test_data:
            error = actual_rating - self.predict(user_id, movie_id)
            absolute_error_sum += abs(error)
            squared_error_sum += error * error

        return PredictionError(
            rmse=math.sqrt(squared_error_sum / len(test_data)),
            mae=absolute_error_sum / len(test_data),
        )

    def _learn_from_error(self, user_id: int, movie_id: int, error: float) -> None:
        user_bias = self.user_biases[user_id]
        movie_bias = self.movie_biases[movie_id]

        self.user_biases[user_id] += self.learning_rate * (
            error - self.regularization * user_bias
        )
        self.movie_biases[movie_id] += self.learning_rate * (
            error - self.regularization * movie_bias
        )

        user_vector = self.user_factors[user_id]
        movie_vector = self.movie_factors[movie_id]
        old_user_vector = user_vector.copy()

        for index in range(self.factors):
            user_value = old_user_vector[index]
            movie_value = movie_vector[index]

            user_vector[index] += self.learning_rate * (
                error * movie_value - self.regularization * user_value
            )
            movie_vector[index] += self.learning_rate * (
                error * user_value - self.regularization * movie_value
            )

    def _init_user(self, user_id: int, random_generator: random.Random) -> None:
        if user_id in self.user_factors:
            return
        self.user_biases[user_id] = 0.0
        self.user_factors[user_id] = self._random_vector(random_generator)

    def _init_movie(self, movie_id: int, random_generator: random.Random) -> None:
        if movie_id in self.movie_factors:
            return
        self.movie_biases[movie_id] = 0.0
        self.movie_factors[movie_id] = self._random_vector(random_generator)

    def _random_vector(self, random_generator: random.Random) -> list[float]:
        return [
            random_generator.normalvariate(0.0, 0.1)
            for _ in range(self.factors)
        ]

    def _clip(self, rating: float) -> float:
        return min(self.rating_max, max(self.rating_min, rating))


def train_test_split(
    ratings: Iterable[Rating],
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[list[Rating], list[Rating]]:
    data = list(ratings)
    random_generator = random.Random(random_state)
    random_generator.shuffle(data)
    split_index = int(len(data) * (1 - test_size))
    return data[:split_index], data[split_index:]
