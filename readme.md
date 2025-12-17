#LUNA2025-uet

### 1: run frontend:
```bash
nvm use 20
cd frontend
npm i -f
npm run dev
```

### 2: run backend
```bash
cd backend
pip install --no-cache-dir -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file .env
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug --env-file .env
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/luna"
uvicorn app.main:app --reload
```

### 3: New Features

#### Docker Image Submission
- **POST /submissions/docker**: Upload Docker images containing LUNA models
- Automatic evaluation with dataset
- Background task processing
- Results stored in MinIO
- Leaderboard automatically updated

#### Lesion Prediction API
- **POST /apitest/v1/predict/lesion**: Standard API for lesion prediction (mock implementation)
- Accepts .mha/.mhd CT scan files
- Returns malignancy probability and classification
- Full error handling per specification
- Detailed API documentation in [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)

#### Testing
```bash
# Test the lesion prediction API
cd backend
python3 test_lesion_api.py
```

### features 3:
#### Frontend
**FE-01**: Auth pages (login), layout (sidebar/header), guard route theo role.
**FE-02**: Datasets page (list, upload admin, analyze button, stats chart).
**FE-03**: Submissions page (upload CSV, list, detail hiển thị metrics + ROC/PR).
**FE-04**: Leaderboard page (filter dataset, bảng xếp hạng, sparkline AUC theo thời gian).
**FE-05**: API Test page (form URL, chọn ảnh mẫu, hiển thị JSON/latency).
**FE-06**: Notebook page (iframe /lite?token&dataset_id), hướng dẫn ngắn.

#### Backend
**BE-01**: Models + CRUD cơ bản (users/datasets/submissions/metrics/api_logs).
**BE-02**: Auth JWT (login, /users/me), middleware lấy current_user + role.
**BE-03**: Datasets API (upload, list, detail, analyze → stats_json, mark_official).
**BE-04**: Submissions API (upload CSV, evaluate → sklearn, lưu score_json).
**BE-05**: Leaderboard API (best-per-group, sort theo AUC, tie-break theo F1).
**BE-06**: API Test API (/apitest/call với 1–2 ảnh mẫu, timeout, log latency).
**BE-07**: Groundtruth download (protected), pagination, filters, error codes.
**BE-08**: Unit/integration tests (pytest) cho evaluate & merge CSV.
**BE-09**: Docker submission API (upload Docker images, auto-evaluate, update leaderboard).
**BE-10**: Lesion prediction API (POST /api/v1/predict/lesion, .mha/.mhd support).