from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.services.data_loader import load_movie_data
from app.services.manual_svd import ManualSVD
from app.services.manual_svd import train_test_split

def main() -> None:
    _, ratings = load_movie_data(min_ratings_per_user=20)
    sample = ratings[["userId", "movieId", "rating"]].head(5000)
    rating_rows = [
        (int(row.userId), int(row.movieId), float(row.rating))
        for row in sample.itertuples(index=False)
    ]
    train_data, test_data = train_test_split(rating_rows, test_size=0.2)

    model = ManualSVD(factors=12, epochs=12, learning_rate=0.007, regularization=0.03)
    model.fit(train_data)
    metrics = model.evaluate(test_data)

    print("Manual SVD demo trained on 5,000 ratings")
    print(f"RMSE: {metrics.rmse:.4f}")
    print(f"MAE: {metrics.mae:.4f}")
    print(f"Prediction user=1 movie=318: {model.predict(1, 318):.2f}")


if __name__ == "__main__":
    main()
