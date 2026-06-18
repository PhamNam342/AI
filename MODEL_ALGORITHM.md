# Thuat Toan, Train Data Va Danh Gia Model

Project nay xay dung he thong goi y phim dua tren collaborative filtering. Model chinh duoc dung la `SVD` tu thu vien `scikit-surprise`.

## 1. Bai Toan

Input cua he thong:

- `userId`: ma nguoi dung.
- `movieId`: ma phim.
- `rating`: diem user da cham cho phim, tu `0.5` den `5.0`.

Muc tieu:

- Hoc tu lich su cham diem cua nhieu user.
- Du doan user co the cham bao nhieu diem cho cac phim chua xem.
- Sap xep cac phim theo diem du doan cao nhat de tao danh sach goi y.

## 2. Data Su Dung

Data nam trong thu muc `data/`:

```text
data/movies.csv
data/ratings.csv
```

`movies.csv` gom cac cot bat buoc:

- `movieId`
- `title`
- `genres`

`ratings.csv` gom cac cot bat buoc:

- `userId`
- `movieId`
- `rating`

Cot `timestamp` co trong file ratings nhung hien tai project khong dung khi train model.

## 3. Tien Xu Ly Data

File xu ly data:

```text
app/services/data_loader.py
```

Cac buoc:

1. Doc `movies.csv` bang `pandas.read_csv`.
2. Kiem tra cac cot bat buoc cua movies.
3. Doc `ratings.csv`.
4. Kiem tra cac cot bat buoc cua ratings.
5. Loc user co it nhat `20` ratings.

Tham so loc:

```python
min_ratings_per_user = 20
```

Ly do loc:

- User co qua it rating tao tin hieu yeu.
- Collaborative filtering can du lich su hanh vi de hoc preference.
- Loc user it rating giup tap train on dinh hon.

## 4. Thuat Toan SVD

Model duoc train trong:

```text
app/services/trainer.py
```

Project dung:

```python
from surprise import SVD
```

SVD trong recommendation la matrix factorization. Y tuong:

- Xem ratings nhu mot ma tran `User x Movie`.
- Moi o trong ma tran la diem rating cua user cho movie.
- Ma tran nay rat thua vi moi user chi xem mot phan nho so phim.
- SVD hoc vector an cho user va vector an cho movie.
- Diem du doan duoc tinh tu muc do phu hop giua vector user va vector movie.

Noi truc giac:

- User co mot vector the hien gu phim.
- Movie co mot vector the hien dac trung an cua phim.
- Neu hai vector gan nhau, model du doan user se thich phim do.

## 5. Pipeline Train Model

Ham chinh:

```python
train_svd_model(
    test_size=0.2,
    random_state=42,
    min_ratings_per_user=20,
)
```

Cac buoc train:

1. Load data da tien xu ly:

```python
_, ratings = load_movie_data(min_ratings_per_user=20)
```

2. Khai bao thang diem:

```python
reader = Reader(rating_scale=(0.5, 5.0))
```

3. Chuyen DataFrame thanh format cua `surprise`:

```python
data = Dataset.load_from_df(
    ratings[["userId", "movieId", "rating"]],
    reader,
)
```

4. Chia train/test:

```python
trainset, testset = train_test_split(
    data,
    test_size=0.2,
    random_state=42,
)
```

Nghia la:

- 80% ratings dung de train.
- 20% ratings dung de test.
- `random_state=42` giup ket qua co the lap lai.

5. Train model:

```python
model = SVD(random_state=42)
model.fit(trainset)
```

6. Du doan tren test set:

```python
predictions = model.test(testset)
```

7. Tinh metrics:

```python
rmse = accuracy.rmse(predictions, verbose=False)
mae = accuracy.mae(predictions, verbose=False)
```

8. Luu artifact:

```text
model/svd_model.pkl
```

Artifact gom:

- `model`: model SVD da train.
- `metrics`: RMSE va MAE.
- `config`: cau hinh train.

## 6. Cach He Thong Goi Y Phim

File xu ly goi y:

```text
app/services/recommender.py
```

Ham chinh:

```python
recommend_for_user(user_id, top_n=10)
```

Voi user da co trong data:

1. Load model tu `model/svd_model.pkl`.
2. Load movies va ratings voi cung `min_ratings_per_user` da dung khi train.
3. Lay danh sach phim user da rating.
4. Loai cac phim user da rating khoi tap ung vien.
5. Dung model du doan rating cho tung phim con lai.
6. Sap xep theo `predicted_rating` giam dan.
7. Tra ve top N phim.

Voi user khong co trong data:

- He thong dung fallback `get_popular_movies`.
- Fallback tinh rating trung binh moi phim.
- Chi lay phim co it nhat `20` ratings.
- Sap xep theo rating trung binh va so luong rating.

Voi user da cham diem phim tren giao dien:

- Rating moi duoc doc tu `data/user_ratings.json`.
- He thong lay genres cua cac phim user da cham diem.
- Moi genre duoc gan trong so dua tren muc diem user da cham.
- Phim co rating cao hon `2.5` tao tin hieu tich cuc, rating thap hon hoac bang `2.5` khong duoc dung de tang preference.
- Cac phim user da cham diem hoac da co trong lich su rating se bi loai khoi tap ung vien.
- Cac phim con lai duoc cham diem theo do trung the loai, rating trung binh va so luong rating.
- He thong chi lay phim co it nhat `20` ratings de tranh goi y phim qua it tin hieu.

Diem goi y theo rating moi hien tai la hybrid don gian:

```text
score = genre_score * 0.7
      + normalized_average_rating * 0.25
      + normalized_rating_count * 0.05
```

Day la buoc content-based nhe ben canh SVD. No giup user moi co the nhan goi y ngay sau khi cham diem vai phim, ngay ca khi chua co lich su rating du de train model rieng.

## 7. Danh Gia Do Dung Cua Model

Project dang danh gia bang hai metric:

```text
RMSE
MAE
```

### RMSE

RMSE la Root Mean Squared Error.

Y nghia:

- Do sai lech trung binh giua rating du doan va rating that.
- Phat nang cac loi lon do binh phuong sai so.
- RMSE cang thap thi model cang tot.

Cong thuc truc giac:

```text
sqrt(mean((rating_that - rating_du_doan)^2))
```

### MAE

MAE la Mean Absolute Error.

Y nghia:

- Trung binh do lech tuyet doi giua rating du doan va rating that.
- De dien giai hon RMSE.
- MAE cang thap thi model cang tot.

Cong thuc truc giac:

```text
mean(abs(rating_that - rating_du_doan))
```

## 8. Ket Qua Hien Tai

Model hien tai trong `model/svd_model.pkl` co metrics:

```text
RMSE: 0.8807
MAE: 0.6766
```

Dien giai:

- Thang rating la `0.5` den `5.0`.
- MAE khoang `0.6766` nghia la trung binh model du doan lech khoang `0.68` diem rating.
- RMSE khoang `0.8807` cho thay van co mot so du doan sai lon hon muc trung binh.

Voi bai toan recommendation co data sparse, muc sai so nay la chap nhan duoc cho project demo/learning. Tuy nhien de ket luan model tot trong san pham that, can them danh gia ranking nhu Precision@K, Recall@K hoac NDCG@K.

## 9. Cach Kiem Tra Tinh Dung Dan Cua Model

Trong project nay, tinh dung dan nen duoc hieu theo cac tang:

### Tang 1: Data dung format

Kiem tra:

- `movies.csv` co `movieId`, `title`, `genres`.
- `ratings.csv` co `userId`, `movieId`, `rating`.
- Rating nam trong thang `0.5` den `5.0`.

Code da validate cot bat buoc trong `data_loader.py`.

### Tang 2: Train/test tach biet

Project chia data thanh:

- Train set: 80%.
- Test set: 20%.

Model chi hoc tren train set, sau do du doan tren test set. Cach nay giup danh gia kha nang du doan rating chua thay trong qua trinh train.

### Tang 3: Metric hop ly

Sau khi train, xem:

```text
RMSE
MAE
```

Neu train lai nhieu lan voi cung `random_state=42`, metrics nen gan nhu giong nhau. Neu metrics tang bat thuong, co the data hoac dependency da thay doi.

### Tang 4: Goi y khong tra phim user da rating

Trong `recommend_for_user`, project loai cac phim user da cham diem:

```python
candidate_movies = movies[~movies["movieId"].isin(rated_movie_ids)].copy()
```

Day la logic dung cho recommendation, vi he thong nen goi y phim user chua xem/chua rating.

### Tang 5: Fallback cho user moi

Neu user khong ton tai trong ratings, model khong co lich su hanh vi de ca nhan hoa. Khi do fallback sang phim pho bien la hop ly:

```python
if user_id not in ratings["userId"].values:
    return get_popular_movies(...)
```

## 10. Han Che Hien Tai

Model hien tai co mot so han che:

- Chua dung thong tin `genres` khi train.
- Chua dung `timestamp`, nen khong bat duoc thay doi gu phim theo thoi gian.
- Chua co cross-validation nhieu fold.
- Chua co metric ranking nhu Precision@K, Recall@K, NDCG@K.
- Chua co API train lai model tu giao dien.
- Chua co xu ly cold-start theo genre/user profile.

## 11. Huong Cai Tien

Co the cai tien project theo cac huong:

- Them cross-validation de danh gia on dinh hon.
- Them Precision@K va Recall@K cho dung ban chat recommendation.
- Them content-based filtering dua tren `genres`.
- Ket hop collaborative filtering va content-based filtering thanh hybrid recommender.
- Luu metadata train nhu ngay train, so rating, so user, so movie.
- Them test tu dong cho data loader, trainer va recommender.

## 12. So Sanh SVD Voi KNN

Project co script so sanh SVD voi KNN collaborative filtering:

```bash
python -m app.services.compare_algorithms
```

Script nay dung cung mot tap data, cung cach chia train/test va cung metric
`RMSE`, `MAE` de ket qua so sanh cong bang hon.

Ket qua hien tai:

```text
Algorithm                        RMSE      MAE
------------------------------------------------
SVD matrix factorization       0.8754   0.6744
Item-based KNNWithMeans        0.9073   0.6919
```

Nhan xet:

- SVD co RMSE va MAE thap hon KNN trong lan chay nay.
- KNN de giai thich hon vi dua tren cac phim tuong tu.
- SVD phu hop hon voi MovieLens trong project nay vi du lieu rating thua va
  SVD hoc duoc cac dac trung an cua user/movie.
