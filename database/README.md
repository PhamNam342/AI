# PostgreSQL/Neon Database

Thu muc nay chua schema database cho ban app co dang nhap, luu rating va luu hanh vi nguoi dung.

## 1. Muc Tieu Schema

Schema nay ho tro:

- Dang ky/dang nhap user that cua app.
- Import user/movie/rating tu MovieLens.
- Luu rating moi cua nguoi dung.
- Luu hanh vi nhu xem phim, thich, khong thich, favorite, watchlist.
- Luu lich su train model va ket qua recommendation neu can cache.

## 2. Cac Bang Chinh

### `app_users`

Luu thong tin user.

- User that cua app co `source = 'app'`.
- User import tu MovieLens co `source = 'movielens'`.
- `password_hash` chi luu hash, khong bao gio luu plain password.

### `movies`

Luu phim.

- `movielens_movie_id` giu id goc tu `movies.csv`.
- `genres` la mang text PostgreSQL.
- `release_year` duoc tach tu title neu co.

### `user_ratings`

Luu rating cua user cho movie.

- Moi user chi co mot rating moi movie.
- Rating nam trong khoang `0.5` den `5.0`.
- Day la bang quan trong nhat de train collaborative filtering.

### `user_movie_interactions`

Luu hanh vi ngoai rating.

Gia tri `interaction` co the la:

- `view`
- `like`
- `dislike`
- `favorite`
- `watchlist`
- `skip`

Bang nay dung de lam recommendation nang cao hon, vi khong phai user nao cung cham diem phim.

### `recommendation_runs`

Luu moi lan train model:

- Ten algorithm.
- Config train.
- Metrics nhu RMSE, MAE.
- Duong dan artifact model.
- Trang thai train.

### `recommendation_results`

Luu ket qua goi y da tinh san cho user neu muon cache.

### `user_sessions`

Luu session token dang nhap. Bang nay chi nen luu hash cua token.

## 3. Tao Database Tren Neon

1. Tao project Neon moi.
2. Mo `SQL Editor`.
3. Copy noi dung file:

```text
database/migrations/001_init.sql
```

4. Chay script.

Sau khi chay thanh cong, database se co schema day du.

## 4. Import Data MovieLens Bang `psql`

Do Neon SQL Editor khong doc truc tiep file CSV tren may cua ban, cach gon nhat la dung `psql`.

Lay connection string tu Neon, co dang gan nhu:

```text
postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require
```

Gan vao bien moi truong:

```bash
export DATABASE_URL='postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require'
```

Tao staging tables:

```bash
psql "$DATABASE_URL" -f database/migrations/002_movielens_staging.sql
```

Sau do import CSV:

```bash
psql "$DATABASE_URL" \
  -c "\copy stg_movielens_movies(movie_id, title, genres) from 'data/movies.csv' with (format csv, header true)"

psql "$DATABASE_URL" \
  -c "\copy stg_movielens_ratings(user_id, movie_id, rating, rating_timestamp) from 'data/ratings.csv' with (format csv, header true)"
```

Chay migration apply de dua data vao bang chinh:

```bash
psql "$DATABASE_URL" -f database/migrations/003_apply_movielens_import.sql
```

## 5. Kiem Tra Data Sau Khi Import

```sql
select count(*) from movies;
select count(*) from app_users where source = 'movielens';
select count(*) from user_ratings;
```

Voi data hien tai, ket qua gan dung se la:

```text
movies: 9742
movielens users: 610
user_ratings: 100836
```

## 6. Query Goi Y Pho Bien

Lay phim co rating trung binh cao va co it nhat 20 ratings:

```sql
select
    title,
    genres,
    rating_count,
    average_rating
from movie_rating_stats
where rating_count >= 20
order by average_rating desc, rating_count desc
limit 10;
```

## 7. Query Lich Su User

Lay phim user da rating:

```sql
select
    m.title,
    r.rating,
    r.rated_at
from user_ratings r
join movies m on m.id = r.movie_id
join app_users u on u.id = r.user_id
where u.source = 'movielens'
  and u.external_user_id = '1'
order by r.rated_at desc
limit 20;
```

## 8. Luu Rating Cho User That

Vi du user that da ton tai trong `app_users`, movie da ton tai trong `movies`:

```sql
insert into user_ratings (user_id, movie_id, rating, source)
values (
    'USER_UUID',
    'MOVIE_UUID',
    4.5,
    'app'
)
on conflict (user_id, movie_id) do update
set
    rating = excluded.rating,
    rated_at = now(),
    source = excluded.source;
```

## 9. Luu Tuong Tac Like/View

```sql
insert into user_movie_interactions (user_id, movie_id, interaction, weight)
values ('USER_UUID', 'MOVIE_UUID', 'like', 1.0);
```

## 10. Ket Noi App Python Sau Nay

Khi app chuyen sang dung database, nen them bien moi truong:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require
```

Dependency Python nen dung:

```text
psycopg[binary]
python-dotenv
passlib[bcrypt]
```

- `psycopg[binary]`: ket noi PostgreSQL.
- `python-dotenv`: doc file `.env` khi dev local.
- `passlib[bcrypt]`: hash password an toan.

## 11. Goi Y Kien Truc App Tiep Theo

Sau khi co database, nen tach them cac module:

```text
app/
  db.py                  # Tao connection pool
  services/
    auth.py              # Dang ky, dang nhap, hash password
    user_store.py        # CRUD user/session
    movie_store.py       # Query movie/rating/interaction
    recommender.py       # Goi y tu model hoac database
```

Flow thuc te:

1. User dang ky/dang nhap.
2. App tao session.
3. User rating/like/view phim.
4. Rating duoc luu vao `user_ratings`.
5. Interaction duoc luu vao `user_movie_interactions`.
6. Job train doc data tu database.
7. Model moi duoc luu va metrics duoc ghi vao `recommendation_runs`.
