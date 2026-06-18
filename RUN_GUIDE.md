# Huong Dan Chay Project

Tai lieu nay huong dan cai dat moi truong, train model va chay giao dien web cua project Movie Recommender.

## 1. Yeu Cau

Project duoc viet bang Python va da duoc kiem tra voi Python 3.11.

Cac thu vien chinh:

- `pandas`: doc va xu ly du lieu CSV.
- `numpy`: tinh toan nen.
- `scipy`: dependency cho `scikit-surprise`.
- `scikit-surprise`: train model recommendation bang SVD.

## 2. Cau Truc Project

```text
app/
  server.py              # Web server va API
  services/
    data_loader.py       # Doc va validate data
    trainer.py           # Train model SVD va luu model
    recommender.py       # Goi y phim cho user
  static/
    index.html           # Giao dien web
    styles.css           # CSS
    app.js               # Goi API va render ket qua
data/
  movies.csv             # Danh sach phim
  ratings.csv            # Diem danh gia cua user
model/
  svd_model.pkl          # Model da train
notebooks/
  experiment.ipynb       # Notebook thu nghiem
requirements.txt         # Dependency toi thieu
README.md
```

## 3. Tao Moi Truong Ao

Neu chua co virtual environment:

```bash
python3.11 -m venv venv311
```

Kich hoat moi truong:

```bash
source venv311/bin/activate
```

Kiem tra Python dang dung:

```bash
python --version
```

## 4. Cai Dependency

```bash
pip install -r requirements.txt
```

Neu may gap loi khi cai `scikit-surprise`, hay dam bao Python dang la ban 3.11 va cac thu vien build co san tren may.

Neu dung PostgreSQL/Neon, tao file `.env` tu file mau:

```bash
cp .env.example .env
```

Sau do dien `DATABASE_URL` cua Neon vao `.env`.

## 5. Train Lai Model

Chay lenh:

```bash
source venv311/bin/activate
python -m app.services.trainer
```

Ket qua mong doi:

```text
Saved model to: /.../model/svd_model.pkl
RMSE: ...
MAE: ...
```

File model se duoc luu tai:

```text
model/svd_model.pkl
```

Neu file nay da ton tai, lenh train se ghi de bang model moi.

## 6. Chay Giao Dien Web

Chay server:

```bash
source venv311/bin/activate
python -m app.server
```

Mac dinh server chay tai:

```text
http://127.0.0.1:8000
```

Mo URL nay tren trinh duyet. Giao dien cho phep:

- Nhap `User ID`.
- Chon so luong phim muon goi y.
- Bam `Recommend` de xem danh sach phim phu hop.
- Cham diem phim tu `0.5` den `5.0`.
- Sau khi user co rating, he thong uu tien goi y phim co the loai tuong tu voi cac phim user cham diem cao.

Rating moi se duoc luu cuc bo tai:

```text
data/user_ratings.json
```

Neu `.env` co `DATABASE_URL` cua Neon va dependency database da cai day du, app se co gang ghi them rating vao bang `user_ratings`.

Neu chua kich hoat virtual environment, chay truc tiep bang Python trong `venv311`:

```bash
./venv311/bin/python -m app.server
```

Tren macOS, lenh `python` co the khong ton tai neu chua activate venv. Khi do hay dung `python3`, `python3.11`, hoac `./venv311/bin/python`.

## 7. Chay Bang Port Khac

Neu port `8000` dang ban:

```bash
source venv311/bin/activate
python -m app.server --port 8080
```

Sau do mo:

```text
http://127.0.0.1:8080
```

## 8. Test Nhanh API

Lay thong tin tong quan:

```bash
curl http://127.0.0.1:8000/api/summary
```

Lay goi y cho user 1:

```bash
curl 'http://127.0.0.1:8000/api/recommendations?user_id=1&top_n=10'
```

Neu `user_id` khong ton tai trong data, he thong se tra ve danh sach phim pho bien nhat thay vi loi.

## 9. Loi Thuong Gap

### Khong tim thay model

Neu API tra ve loi model khong ton tai, chay lai:

```bash
python -m app.services.trainer
```

### Sai dependency

Neu import `surprise` bi loi, cai lai dependency:

```bash
pip install -r requirements.txt
```

### Sai thu muc khi chay lenh

Hay chay cac lenh tu thu muc goc project:

```text
/Users/pham.quang.nam/Documents/AI
```
