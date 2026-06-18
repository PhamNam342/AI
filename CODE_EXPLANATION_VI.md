# Giai thich code Movie Recommender

Tai lieu nay giai thich project theo cach de doc code: bat dau tu luong chay tong the, sau do di qua tung file quan trong, va cuoi cung mo tung buoc cua thuat toan goi y phim.

Luu y: thu muc `venv311/`, `__pycache__/`, file `.pkl`, file `.csv`, va notebook khong duoc giai thich tung dong o day vi chung la moi truong phu thuoc, file sinh ra, hoac du lieu. Code chinh nam trong `app/`, `database/`, va cac file huong dan.

## 1. Luong hoat dong tong the

```text
Trinh duyet
  |
  | mo /
  v
app/server.py
  |
  | tra ve app/static/index.html, styles.css, app.js
  v
Giao dien web
  |
  | goi API: /api/auth/*, /api/summary, /api/recommendations, /api/ratings, /api/train
  v
server.py
  |
  +--> auth.py: dang ky, dang nhap, session cookie
  +--> data_loader.py: doc movies.csv/ratings.csv hoac PostgreSQL
  +--> recommender.py: tao danh sach phim goi y
  +--> trainer.py: train lai SVD va luu model
  +--> user_ratings.py: luu diem nguoi dung danh gia
```

Khi nguoi dung bam "Recommend":

```text
app.js
  -> fetch("/api/recommendations?top_n=...")
  -> server.py::_handle_recommendations()
  -> recommender.py::recommend_for_user_with_context()
  -> tra JSON ve app.js
  -> app.js::renderRecommendations()
  -> hien thi danh sach phim
```

Khi nguoi dung bam "Retrain model":

```text
app.js::retrainModel()
  -> POST /api/train
  -> server.py::_handle_train()
  -> trainer.py::train_and_save_model()
  -> trainer.py::train_svd_model()
  -> surprise.SVD.fit(trainset)
  -> danh gia RMSE/MAE
  -> luu model/svd_model.pkl
```

## 2. Giai thich file `app/server.py`

Day la web server tu viet bang `http.server`, khong dung Flask. File nay nhan request HTTP, goi service phu hop, roi tra HTML/CSS/JS hoac JSON.

### Import va hang so

- `from __future__ import annotations`: cho phep type hint hien dai, tranh mot so loi tham chieu kieu khi runtime.
- `argparse`: doc tham so command line `--host`, `--port`.
- `json`: parse request JSON va encode response JSON.
- `mimetypes`: doan `Content-Type` khi tra file tinh.
- `SimpleCookie`: doc cookie `movie_session`.
- `HTTPStatus`: dung ten trang thai HTTP ro rang nhu `HTTPStatus.OK`.
- `BaseHTTPRequestHandler`, `ThreadingHTTPServer`: tao HTTP server nhieu thread.
- `Path`: xu ly duong dan file an toan.
- `parse_qs`, `urlparse`: tach path va query string.
- Cac import tu `app.services.*`: ket noi server voi cac tang logic nhu auth, train, recommend.
- `APP_DIR`, `BASE_DIR`, `STATIC_DIR`, `INDEX_PATH`: dinh nghia vi tri thu muc app, static, va file HTML chinh.
- `load_local_env()`: nap bien moi truong tu `.env`, dac biet la `DATABASE_URL`.

### Class `RecommendationHandler`

- `server_version`: ten server hien trong header/log.

#### `do_HEAD`

- Parse URL hien tai.
- Neu path la `/`, `/api/summary`, `/api/recommendations`, hoac `/static/...` thi tra `200 OK` nhung khong tra body.
- Neu khong khop route nao thi tra `404`.

#### `do_GET`

- Route `/`: goi `_send_file(INDEX_PATH)` de tra giao dien HTML.
- Route `/static/...`: lay ten file sau `/static/`, roi tra file trong `app/static`.
- Route `/api/summary`: tra thong tin tong quan dataset/model.
- Route `/api/recommendations`: goi handler de lay phim goi y.
- Route `/api/user-ratings`: tra rating da luu cua user.
- Route `/api/auth/me`: tra user hien tai dua tren cookie.
- Cac path khac: tra JSON loi `Not found`.

#### `do_POST`

- `/api/ratings`: luu rating nguoi dung vua chon.
- `/api/train`: train lai model.
- `/api/auth/register`: dang ky tai khoan.
- `/api/auth/login`: dang nhap.
- `/api/auth/logout`: dang xuat.
- Path khac: tra `404`.

#### `_handle_recommendations`

- `parse_qs(query)`: bien `top_n=10` thanh dict.
- `_resolve_user_id(params)`: uu tien query `user_id`; neu khong co thi lay user dang dang nhap tu cookie.
- `top_n`: ep ve so nguyen, sau do gioi han trong khoang 1 den 30.
- `recommend_for_user_with_context(...)`: goi logic goi y that su.
- Tra ve JSON gom `user_id`, `top_n`, rating da luu, strategy, va danh sach phim.
- Neu chua co `model/svd_model.pkl` thi tra `503` va huong dan chay trainer.

#### `_handle_user_ratings`

- Lay user id bang `_resolve_user_id`.
- Tra `get_saved_user_ratings(user_id)`.

#### `_handle_rating`

- Doc JSON body.
- Lay `user_id`: neu payload co thi dung payload, khong co thi lay user dang dang nhap.
- Lay `movie_id` va `rating`.
- Goi `save_user_rating`.
- Neu rating sai dinh dang/khoang gia tri thi tra `400`.
- Neu thanh cong thi tra `201 Created`.

#### Auth handlers

- `_handle_auth_register`: doc username/password, tao user moi, tao session token, set cookie.
- `_handle_auth_login`: xac thuc username/password, tao session token, set cookie.
- `_handle_auth_logout`: xoa session va clear cookie.
- `_handle_auth_me`: tra user hien tai hoac `null`.

#### `_handle_train`

- Goi `train_and_save_model()`.
- Neu train loi thi tra `500`, kem lich su training.
- Neu thanh cong thi tra path model, metrics, config, training runs.

#### Helper methods

- `_read_json_body`: doc so byte theo `Content-Length`, decode UTF-8, parse JSON.
- `_send_file`: resolve path, chan truy cap ra ngoai `STATIC_DIR`, doc byte va tra file.
- `_send_json`: encode JSON, set `Content-Type`, `Content-Length`, cookie neu can.
- `_resolve_user_id`: lay `user_id` tu query hoac cookie.
- `_current_user`: tra user tu session, neu bat buoc ma khong co thi raise `PermissionError`.
- `_session_token`: parse header `Cookie` va lay `movie_session`.
- `log_message`: tuy bien log request ra terminal.

### Ham ngoai class

- `build_summary()`: doc dataset, dem movie/rating/user, kiem tra model co ton tai, doc metrics trong pickle neu co.
- `run(host, port)`: tao `ThreadingHTTPServer` va chay den khi Ctrl+C.
- `main()`: doc tham so command line roi goi `run`.
- `if __name__ == "__main__"`: cho phep chay bang `python -m app.server`.

## 3. Giai thich file `app/services/data_loader.py`

File nay phu trach nap du lieu phim/rating. No uu tien PostgreSQL neu co `DATABASE_URL`; neu khong thi doc CSV trong `data/`.

- `BASE_DIR`, `DATA_DIR`, `MOVIES_PATH`, `RATINGS_PATH`, `USER_RATINGS_PATH`: cac duong dan co dinh.
- `load_local_env()`: nap `.env`.

### `load_movies`

- Nhan optional `movies_path`.
- `pd.read_csv(path)`: doc file phim.
- Kiem tra bat buoc co cot `movieId`, `title`, `genres`.
- Neu thieu cot thi raise `ValueError`.
- Tra DataFrame phim.

### `load_ratings`

- Doc `ratings.csv`.
- Kiem tra cot `userId`, `movieId`, `rating`.
- Neu `min_ratings_per_user > 0`, dem so rating moi user, chi giu user co du rating toi thieu. Viec nay giup model hoc on dinh hon.
- Neu `include_saved_ratings=True`, gop rating nguoi dung tu `data/user_ratings.json`.
- Tra DataFrame rating.

### `load_movie_data`

- Goi `load_movie_data_with_metadata`.
- Bo metadata, chi tra `(movies, ratings)`.

### `load_movie_data_with_metadata`

- Dem rating local da luu.
- Neu co `DATABASE_URL`: thu doc du lieu tu PostgreSQL.
- Neu DB co du lieu hop le: gop rating local va tra source `database`.
- Neu DB loi hoac rong: luu warning va fallback CSV.
- Neu khong co `DATABASE_URL`: dung CSV va them warning.

### `load_movie_data_from_database`

- Import `psycopg`; neu chua cai thi raise loi.
- Query bang `movies` de lay `movieId`, `title`, `genres`.
- Query `user_ratings` join `app_users`, `movies` de lay rating MovieLens-compatible.
- Loc user co toi thieu `min_ratings_per_user` rating.
- Tra `(movies, ratings)`.

### `load_saved_user_ratings`

- Neu file JSON chua ton tai thi tra DataFrame rong dung schema.
- Doc JSON local dang `{user_id: {movie_id: rating}}`.
- Chuyen tung cap user/movie/rating thanh row DataFrame.

### `merge_saved_user_ratings`

- Doc rating local.
- Neu rong thi tra rating goc.
- Neu co thi `concat` rating goc + rating local.
- `drop_duplicates(... keep="last")`: neu user danh gia lai cung phim, lay ban moi nhat.

### `count_saved_user_ratings`

- Dem so dong trong DataFrame rating local.

## 4. Giai thich file `app/services/trainer.py`

File nay train model SVD production bang thu vien `scikit-surprise`.

### Hang so

- `MODEL_DIR`: thu muc `model/`.
- `MODEL_PATH`: file pickle `model/svd_model.pkl`.
- `TRAINING_RUNS_PATH`: file JSON luu lich su lan train.

### `train_svd_model`

Tham so:

- `test_size=0.2`: 20% rating dung de test.
- `random_state=42`: seed de ket qua lap lai duoc.
- `min_ratings_per_user=20`: chi train user co it nhat 20 rating.
- `max_rmse=1.2`: quality gate; RMSE cao hon thi coi la train fail.

Tung buoc:

1. Goi `load_movie_data_with_metadata` de lay ratings.
2. `Reader(rating_scale=(0.5, 5.0))`: bao cho Surprise biet diem rating nam tu 0.5 den 5.0.
3. `Dataset.load_from_df(...)`: chuyen DataFrame thanh dataset cua Surprise.
4. `train_test_split(...)`: chia train/test cung random seed.
5. `SVD(random_state=random_state)`: tao model SVD.
6. `model.fit(trainset)`: hoc latent factors tu trainset.
7. `model.test(testset)`: du doan tren testset.
8. Tinh `rmse` va `mae`.
9. Neu RMSE qua nguong thi raise loi.
10. Tra artifact gom model, metrics, config.

### `save_model`

- Chon path mac dinh neu khong truyen.
- Tao thu muc cha neu chua co.
- Ghi pickle vao file tam `.tmp`.
- `temp_path.replace(path)`: thay the file cu bang file moi mot cach an toan hon.
- Tra path da luu.

### `train_and_save_model`

- Tao `run_id` bang UUID.
- Ghi thoi gian bat dau.
- Thu train va save model.
- Neu loi: ghi training run status `failed`, roi raise lai loi.
- Neu thanh cong: ghi training run status `succeeded`.
- Tra `(artifact, saved_path)`.

### `record_training_run`

- Doc file lich su neu co.
- Append run moi.
- Chi giu 50 run gan nhat.

### `load_training_runs`

- Neu chua co file thi tra list rong.
- Doc JSON, lay `limit` run cuoi, dao nguoc de run moi nhat nam dau.

### `_utc_now`

- Tra chuoi thoi gian UTC dang ISO, co hau to `Z`.

## 5. Giai thich thuat toan trong `app/services/manual_svd.py`

File nay la ban SVD tu code tay de hoc, de nhin ro cong thuc. Production dung `surprise.SVD`, nhung y tuong cot loi giong nhau.

### Du lieu dau vao

```python
Rating = tuple[int, int, float]
```

Moi rating co dang:

```text
(user_id, movie_id, rating)
```

Vi du:

```text
(1, 318, 5.0)
```

nghia la user 1 cham phim 318 diem 5.0.

### Cong thuc du doan

Trong `predict`, model tinh:

```text
predicted_rating =
    global_mean
  + user_bias[user_id]
  + movie_bias[movie_id]
  + dot(user_factors[user_id], movie_factors[movie_id])
```

Y nghia:

- `global_mean`: diem trung binh toan bo dataset.
- `user_bias`: user nay de tinh hay kho tinh hon trung binh bao nhieu.
- `movie_bias`: phim nay thuong duoc cham cao/thap hon trung binh bao nhieu.
- `user_factors`: vector an cua user, vi du co the ngam hieu so thich hanh dong, hai, drama.
- `movie_factors`: vector an cua phim.
- `dot_product`: do hop nhau giua user va phim.
- `_clip`: ep ket qua nam trong khoang 0.5 den 5.0.

### `PredictionError`

- `@dataclass`: tu tao constructor va repr.
- `rmse`: can bac hai trung binh binh phuong loi.
- `mae`: trung binh tri tuyet doi loi.

### `ManualSVD.__init__`

- `factors`: so chieu vector an. Cang lon cang bieu dien phuc tap hon nhung de overfit hon.
- `learning_rate`: buoc hoc moi lan cap nhat.
- `regularization`: phat vector/bias qua lon de giam overfit.
- `epochs`: so lan quet qua toan bo training data.
- `random_state`: seed khoi tao random.
- `rating_min`, `rating_max`: gioi han diem.
- `global_mean`: ban dau 0, sau fit moi co gia tri.
- `user_biases`, `movie_biases`: dict id -> bias.
- `user_factors`, `movie_factors`: dict id -> vector latent.

### `fit`

Tung buoc:

1. Chuyen `ratings` thanh list vi can shuffle nhieu lan.
2. Neu khong co data thi bao loi.
3. Tao random generator rieng de ket qua on dinh.
4. Tinh `global_mean`.
5. Duyet moi rating de khoi tao user/movie neu chua co.
6. Lap `epochs` lan:
   - Shuffle training data.
   - Voi tung rating that `actual_rating`:
     - Goi `predict` de lay `predicted_rating`.
     - `error = actual_rating - predicted_rating`.
     - Goi `_learn_from_error` de cap nhat bias va vector.

### `_learn_from_error`

Day la trai tim cua thuat toan. No dung stochastic gradient descent.

Cap nhat bias:

```text
user_bias += learning_rate * (error - regularization * user_bias)
movie_bias += learning_rate * (error - regularization * movie_bias)
```

Neu model du doan thap hon rating that (`error > 0`), bias co xu huong tang. Neu bias qua lon, thanh phan `regularization * bias` keo no nho lai.

Cap nhat vector:

```text
user_factor[k] += learning_rate * (error * movie_factor[k] - regularization * user_factor[k])
movie_factor[k] += learning_rate * (error * old_user_factor[k] - regularization * movie_factor[k])
```

Y nghia:

- Neu user va movie can gan nhau hon de tang prediction, cac chieu latent se duoc day theo huong do.
- Neu vector qua lon, regularization keo ve gan 0.
- `old_user_vector = user_vector.copy()` rat quan trong: khi cap nhat movie vector, code dung gia tri user vector cu, tranh viec vua update user xong lai dung ngay gia tri moi lam cong thuc lech.

### `predict`

- Lay vector user/movie.
- Neu user hoac movie chua tung thay trong training, tra `global_mean`.
- Tinh dot product bang `sum(user_value * movie_value ...)`.
- Cong mean + bias + dot product.
- Clip rating ve khoang hop le.

### `evaluate`

- Chuyen test ratings thanh list.
- Neu rong thi bao loi.
- Voi moi rating:
  - Tinh loi `actual - predict`.
  - Cong `abs(error)` vao MAE.
  - Cong `error * error` vao RMSE.
- Tra `PredictionError(rmse, mae)`.

### `_init_user`, `_init_movie`

- Neu id da co vector thi bo qua.
- Neu chua co:
  - bias = 0.
  - vector random normal mean 0, std 0.1.

### `_random_vector`

- Tao list co `self.factors` so ngau nhien.
- Moi so lay tu phan phoi normal quanh 0.

### `_clip`

- `max(self.rating_min, rating)`: dam bao khong nho hon 0.5.
- `min(self.rating_max, ...)`: dam bao khong lon hon 5.0.

### `train_test_split`

- Chuyen ratings thanh list.
- Shuffle bang seed.
- Tinh index cat theo `test_size`.
- Tra `(train, test)`.

## 6. Giai thich file `app/services/recommender.py`

File nay quyet dinh chien luoc goi y nao se duoc dung.

### `load_trained_model`

- Mo file pickle `model/svd_model.pkl`.
- `pickle.load` tra artifact gom model, metrics, config.

### `get_popular_movies`

Dung khi khong co user hop le hoac khong du tin hieu ca nhan.

Tung buoc:

1. Group ratings theo `movieId`.
2. Tinh `mean` va `count`.
3. Doi ten cot thanh `predicted_rating` va `rating_count`.
4. Chi giu phim co it nhat `min_rating_count`.
5. Merge voi bang movies de co title/genres.
6. Sap xep theo diem trung binh cao, neu bang nhau thi phim nhieu rating hon len truoc.
7. Lay `top_n`.
8. Tra list dict de server encode JSON.

### `recommend_for_user`

- Wrapper don gian: goi `recommend_for_user_with_context` roi chi lay list `recommendations`.

### `recommend_for_user_with_context`

Day la ham chinh.

1. Load artifact da train.
2. Lay model va config `min_ratings_per_user`.
3. Load movies/ratings theo config luc train.
4. Lay rating local cua user.
5. Neu user co rating local:
   - Goi `recommend_from_saved_ratings`.
   - Strategy la `personal_genre`.
6. Neu user khong nam trong ratings train:
   - Tra popular fallback.
7. Neu user co trong dataset:
   - Lay cac phim user da rating.
   - Tao candidate la phim chua rating.
   - Goi `model.predict(user_id, movie_id).est` cho tung phim.
   - Sap xep diem du doan giam dan.
   - Tra top N.

### `recommend_from_saved_ratings`

Ham nay tao goi y nhanh dua tren the loai nguoi dung da thich.

1. Lay danh sach phim user da rating local.
2. `_build_genre_weights`: tinh trong so the loai.
3. Neu khong co genre weight thi fallback popular.
4. Tao tap phim can loai tru: phim user da rating local va phim user da rating trong dataset goc.
5. Tinh `average_rating` va `rating_count` moi phim.
6. Tao candidates la phim chua xem/chua rating.
7. Fill null rating bang 0.
8. Chi giu phim co `rating_count >= 20` de tranh phim qua it rating.
9. `genre_score`: tong weight cua cac genre trung voi so thich user.
10. Loai phim co genre_score <= 0.
11. Neu het candidate thi fallback popular.
12. Tinh `predicted_rating` theo cong thuc:

```text
predicted_rating =
  (
    genre_score * 0.70
  + average_rating/5.0 * 0.25
  + min(rating_count, 200)/200 * 0.05
  ) * 5.0
```

Y nghia:

- 70% dua vao the loai user thich.
- 25% dua vao diem trung binh cong dong.
- 5% dua vao do pho bien, clip toi da 200 rating.

13. `reason`: liet ke genre nao khop voi so thich.
14. Sap xep theo predicted_rating, average_rating, rating_count.
15. Tra top N.

### `_build_genre_weights`

- Duyet cac phim user da rating.
- `preference = rating - 2.5`: rating tren 2.5 duoc xem la thich; duoi hoac bang thi bo qua.
- Moi genre cua phim duoc cong `preference`.
- Tinh tong weight.
- Chia moi weight cho tong de normalize, tong weight sau cung bang 1.

Vi du:

```text
User cham:
- Action 5.0 => preference 2.5
- Comedy 4.0 => preference 1.5

Tong = 4.0
Action weight = 2.5 / 4.0 = 0.625
Comedy weight = 1.5 / 4.0 = 0.375
```

### `_split_genres`

- Neu genres rong hoac `(no genres listed)` thi tra list rong.
- Tach chuoi `Action|Comedy` thanh `["Action", "Comedy"]`.

## 7. Giai thich file `app/services/compare_algorithms.py`

File nay dung de so sanh SVD voi KNN.

- `AlgorithmResult`: dataclass luu ten thuat toan, RMSE, MAE, thoi gian train, thoi gian test.
- `compare_svd_and_knn`: load rating, chia train/test, tao 2 algorithm:
  - `SVD matrix factorization`.
  - `Item-based KNNWithMeans`.
- Voi moi algorithm:
  - Do thoi gian `fit`.
  - Do thoi gian `test`.
  - Tinh RMSE/MAE.
  - Append vao results.
- `print_comparison_table`: in bang can cot va chon algorithm co RMSE thap nhat.
- `parse_args`: doc tham so command line.
- `main`: noi parse args -> compare -> print.

### Co che KNN trong file nay

`KNNWithMeans` item-based tim cac phim giong nhau bang cosine similarity. Khi du doan user se cham phim A bao nhieu, no nhin cac phim tuong tu A ma user da cham, sau do tinh trung binh co trong so. Khac voi SVD, KNN khong hoc vector latent an; no dua truc tiep vao do tuong dong item-item.

## 8. Giai thich file `app/services/auth.py`

File nay la auth local bang JSON, phu hop demo/project nho.

- `AUTH_USERS_PATH`: file luu user.
- `AUTH_SESSIONS_PATH`: file luu session.
- `SESSION_DAYS = 14`: session song 14 ngay.

### `register_user`

- Chuan hoa username.
- Kiem tra password toi thieu 6 ky tu.
- Load JSON user hoac default.
- Neu username da ton tai thi bao loi.
- Lay `next_user_id`, sau do tang len 1.
- Luu user moi voi password hash va created_at.
- Tra `public_user`, khong tra password hash.

### `authenticate_user`

- Chuan hoa username.
- Load users.
- Tim user.
- Neu khong co hoac password sai thi raise.
- Neu dung thi tra public user.

### `create_session`

- Tao token random bang `secrets.token_urlsafe`.
- Chi luu hash cua token, khong luu token raw.
- Luu `expires_at` sau 14 ngay.
- Tra token raw de server set cookie.

### `get_user_by_session`

- Neu khong co token thi tra `None`.
- Hash token trong cookie.
- Tim session co hash trung va chua het han.
- Tim user ung voi session.
- Tra public user.

### `revoke_session`

- Hash token.
- Loc bo session co token_hash trung.
- Ghi lai file.

### Password/token helpers

- `hash_password`: tao salt, dung PBKDF2-HMAC-SHA256 voi 260000 vong.
- `verify_password`: hash password nhap vao cung salt, so sanh bang `hmac.compare_digest`.
- `hash_token`: SHA256 token session.
- `normalize_username`: trim, lower, yeu cau toi thieu 3 ky tu.
- `validate_password`: yeu cau password toi thieu 6 ky tu.
- `public_user`: bo thong tin nhay cam, chi tra id/username/display_name.
- `_load_json`, `_save_json`: doc/ghi JSON.
- `utc_now`: thoi gian UTC ISO.

## 9. Giai thich file `app/services/user_ratings.py`

File nay luu rating moi cua nguoi dung.

### `get_saved_user_ratings`

- Load toan bo rating tu JSON.
- Lay rating cua user theo key string.
- Chuyen movie_id ve int va rating ve float.

### `save_user_rating`

- Kiem tra rating trong khoang 0.5 den 5.0.
- Lam tron ve buoc 0.5: `round(rating * 2) / 2`.
- Load JSON hien co.
- Tao dict cho user neu chua co.
- Luu rating theo movie_id.
- Ghi file JSON.
- Thu luu them vao PostgreSQL neu co `DATABASE_URL`.
- Tra object gom user_id, movie_id, rating, storage, va toan bo ratings cua user.

### `_try_save_to_postgres`

- Neu khong co `DATABASE_URL` thi tra `False`.
- Neu chua cai `psycopg` thi tra `False`.
- Insert/update rating vao DB.
- Neu loi bat ky thi tra `False`, app van chay voi local JSON.

## 10. Giai thich file `app/services/env.py`

- `load_local_env`: nap file `.env`.
- Neu co `python-dotenv`, dung `load_dotenv(path)`.
- Neu khong co, code tu parse `.env`:
  - Bo qua dong rong/comment.
  - Ho tro dong bat dau bang `export `.
  - Tach `KEY=VALUE`.
  - `os.environ.setdefault`: chi set neu bien moi truong chua co.

## 11. Giai thich file `app/services/manual_svd_demo.py`

File demo cach chay `ManualSVD`.

- Them root project vao `sys.path` neu chay file truc tiep.
- Load movie/rating.
- Lay 5000 rating dau de demo nhanh.
- Chuyen DataFrame thanh list tuple `(userId, movieId, rating)`.
- Chia train/test.
- Tao `ManualSVD(factors=12, epochs=12, learning_rate=0.007, regularization=0.03)`.
- Fit model.
- Evaluate RMSE/MAE.
- In du doan thu cho user 1 va movie 318.

## 12. Giai thich frontend `app/static/index.html`

HTML chia lam 2 view:

- `auth-view`: man hinh dang nhap/dang ky.
- `app-view`: man hinh app sau khi dang nhap.

Cac `id` trong HTML la diem moc de `app.js` tim va cap nhat:

- `auth-form`, `login-tab`, `register-tab`: dieu khien auth.
- `auth-rmse`, `auth-source`: hien metric o man hinh auth.
- `account-name`, `logout-button`: thong tin user.
- `recommendation-form`, `top-n`, `train-button`: dieu khien goi y/train.
- `movie-count`, `user-count`, `rating-count`, `rmse`, `data-source`: thong ke dataset/model.
- `recommendations`: noi render danh sach movie cards.
- Cuoi file load `/static/app.js`.

## 13. Giai thich frontend `app/static/app.js`

File nay la logic browser.

### Lay DOM node

Cac dong `document.querySelector("#...")` lay element theo id tu HTML. Vi du:

- `authView`: section login/register.
- `appView`: section app chinh.
- `recommendationsNode`: container de render cards phim.
- `statusNode`: vung hien trang thai Ready/Loading/Training.

### Bien trang thai

- `formatNumber`: format so theo `en-US`.
- `currentUser`: user dang dang nhap.
- `authMode`: `"login"` hoac `"register"`.
- `summaryLoaded`: tranh load summary lap lai nhieu lan.

### Cac ham chinh

- `setStatus(text, tone)`: cap nhat text va data-tone cho status.
- `setAuthMode(mode)`: doi tab login/register, doi title/button/autocomplete.
- `showAuth()`: hien auth view, an app view, xoa recommendations.
- `showApp(user)`: luu user, hien app, load summary neu can, load recommendations.
- `loadCurrentUser()`: goi `/api/auth/me`; neu co user thi vao app, khong thi hien auth.
- `submitAuth(event)`: chan submit mac dinh, goi `/api/auth/login` hoac `/api/auth/register`.
- `logout()`: POST logout, quay ve auth.
- `renderRecommendations(payload)`: bien JSON recommendations thanh HTML cards.
- `renderRatingOptions(currentRating)`: tao option 0.5 den 5.0.
- `saveRating(movieId, rating)`: POST rating moi len server.
- `loadSummaryForAuth()`: load metric nho cho man hinh auth.
- `loadSummary()`: load thong ke dataset/model cho app.
- `renderTrainingRun(run)`: hien lan train gan nhat.
- `loadRecommendations()`: fetch `/api/recommendations`.
- `retrainModel()`: POST `/api/train`, cap nhat RMSE va reload recommendations.
- `formatRating(value)`: format diem 2 chu so thap phan.
- `escapeHtml(value)`: chong chen HTML/XSS khi render title/genres/reason.

### Event listeners

- Slider `topNInput`: cap nhat output so top N.
- Click login/register tab: doi mode.
- Submit auth form: dang nhap/dang ky.
- Click logout: dang xuat.
- Submit recommendation form: reload recommendations.
- Click train button: train model.
- Change select rating trong movie card: luu rating, roi load recommendations moi.
- Cuoi file: `loadCurrentUser()` de khoi dong app.

## 14. Giai thich CSS `app/static/styles.css`

CSS khong chua thuat toan, chi dieu khien giao dien:

- `:root`: khai bao bien mau, shadow, radius.
- `*`, `body`, `button`, `input`, `select`: reset va style chung.
- `.auth-view`, `.auth-shell`, `.auth-copy`, `.auth-card`: layout man hinh auth.
- `.auth-tabs`, `.auth-tab`, `.auth-form`: tab va form dang nhap.
- `.app-view`, `.topbar`, `.workspace`: layout app chinh.
- `.panel`, `.controls`, `.stats`: sidebar dieu khien va thong ke.
- `.results`, `.recommendation-grid`, `.movie-card`: khu vuc danh sach phim.
- `.rating`, `.rating-picker`, `.status`, `.notice`: style diem, select rating, trang thai, canh bao.
- Media queries `@media`: dieu chinh layout cho man hinh nho.

Khi doc CSS, ban nen doc theo component thay vi tung dong rieng le: selector nao trung voi class trong HTML thi selector do style cho phan tu tuong ung.

## 15. Giai thich database migrations

### `database/migrations/001_init.sql`

- Tao extension `pgcrypto` de dung `gen_random_uuid()`.
- Tao extension `citext` de email/username khong phan biet hoa thuong.
- Tao enum:
  - `user_source`: user tu app, MovieLens, admin.
  - `interaction_type`: view/like/dislike/favorite/watchlist/skip.
  - `training_status`: queued/running/succeeded/failed.
- Tao bang `app_users`: user trong app va user import tu MovieLens.
- Tao bang `movies`: phim, MovieLens id, title, release year, genres.
- Tao bang `user_ratings`: rating cua user cho movie, unique theo `(user_id, movie_id)`.
- Tao bang `user_movie_interactions`: hanh vi khac ngoai rating.
- Tao bang `recommendation_runs`: lich su train/recommend job.
- Tao bang `recommendation_results`: ket qua recommend theo run/user/rank.
- Tao bang `user_sessions`: session dang nhap.
- Tao function/trigger `set_updated_at`: tu cap nhat `updated_at` khi row thay doi.
- Tao view `movie_rating_stats`: thong ke rating moi phim.
- Tao view `active_user_stats`: thong ke rating moi user active.

### `database/migrations/002_movielens_staging.sql`

- Tao bang tam `stg_movielens_movies` de import `movies.csv`.
- Tao bang tam `stg_movielens_ratings` de import `ratings.csv`.

### `database/migrations/003_apply_movielens_import.sql`

- Insert phim tu staging vao bang `movies`.
- Tach nam phat hanh tu title bang regex.
- Tach genres bang `string_to_array(genres, '|')`.
- Insert user MovieLens vao `app_users`.
- Insert rating vao `user_ratings`, join user/movie theo id MovieLens.
- Dung `on conflict ... do update` de import lai khong bi trung.

## 16. Cac file markdown va config

- `README.md`: huong dan setup, train, run app, cau truc project.
- `RUN_GUIDE.md`: huong dan chay chi tiet hon.
- `MODEL_ALGORITHM.md`: mo ta model va thuat toan o muc bao cao.
- `requirements.txt`: danh sach dependency Python:
  - `pandas`: xu ly CSV/DataFrame.
  - `scikit-surprise`: SVD/KNN recommender.
  - `numpy`, `scikit-learn`, `jupyter`: tinh toan/thu nghiem.
  - `psycopg`, `python-dotenv`: PostgreSQL va `.env`.

## 17. Nen doc file nao truoc?

Thu tu de hieu nhanh:

1. `README.md`: project lam gi.
2. `app/static/app.js`: nguoi dung bam gi, browser goi API nao.
3. `app/server.py`: API nao goi service nao.
4. `app/services/recommender.py`: logic goi y luc runtime.
5. `app/services/trainer.py`: train SVD production.
6. `app/services/manual_svd.py`: hieu thuat toan bang code tu viet.
7. `app/services/data_loader.py`: du lieu vao tu dau.
8. `app/services/auth.py` va `user_ratings.py`: user/rating local.
9. `database/migrations/*.sql`: neu can hieu DB.

## 18. Tom tat thuat toan bang ngon ngu don gian

SVD collaborative filtering gia dinh rang:

- Moi user co mot vector so thich an.
- Moi phim co mot vector dac trung an.
- Neu hai vector hop nhau, user co kha nang cham phim cao.

Model hoc cac vector nay tu rating lich su. Moi lan thay mot rating that, model:

1. Du doan rating.
2. Tinh sai so.
3. Dieu chinh bias va vector de lan sau du doan gan rating that hon.
4. Lap lai qua nhieu epoch.

App nay co 3 chien luoc recommend:

1. `svd`: user da co trong dataset train, dung model SVD.
2. `personal_genre`: user moi vua cham phim trong app, dung the loai da thich de goi y nhanh.
3. `popular`: khong co du thong tin, tra phim pho bien co rating cao.

