# Movie Recommender

A small movie recommendation app built with MovieLens data and an SVD collaborative-filtering model from `scikit-surprise`.

## Project Structure

```text
app/
  server.py              # Web UI and JSON API
  services/
    data_loader.py       # CSV loading and validation
    trainer.py           # SVD training and model persistence
    recommender.py       # Recommendation logic
  static/
    index.html
    styles.css
    app.js
data/
  movies.csv
  ratings.csv
model/
  svd_model.pkl
notebooks/
  experiment.ipynb
  experiment1.ipynb
```

## Setup

```bash
python3.11 -m venv venv311
source venv311/bin/activate
pip install -r requirements.txt
```

## Train The Model

```bash
source venv311/bin/activate
python -m app.services.trainer
```

The trained artifact is saved at `model/svd_model.pkl`.

## Run The Web App

```bash
source venv311/bin/activate
python -m app.server
```

Open `http://127.0.0.1:8000` in your browser.

If you do not activate the virtual environment, use:

```bash
./venv311/bin/python -m app.server
```

The UI supports rating movies from `0.5` to `5.0`. After a user rates movies, future recommendations for that user prioritize movies with similar genres and stronger rating signals. Local ratings are saved in `data/user_ratings.json` and can also be mirrored to PostgreSQL/Neon when `DATABASE_URL` is configured.

## Database

PostgreSQL/Neon schema and import notes are available in:

- `database/migrations/001_init.sql`
- `database/migrations/002_movielens_staging.sql`
- `database/migrations/003_apply_movielens_import.sql`
- `database/README.md`

## Use From Python

```python
from app.services.recommender import recommend_for_user

recommendations = recommend_for_user(user_id=1, top_n=10)
for movie in recommendations:
    print(movie["title"], movie["predicted_rating"])
```
