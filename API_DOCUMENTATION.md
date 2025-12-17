# API Documentation for LUNA 2025

## New Endpoints

### 1. Lesion Prediction API

#### POST /api/apitest/v1/predict/lesion

Endpoint for predicting lung lesion malignancy from CT scan images.

**Content-Type:** `multipart/form-data`

**Authentication:** Required - Bearer token in Authorization header

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file | File | YES | CT scan image file (.mha or .mhd format) |
| seriesInstanceUID | String | YES | Unique identifier for the image series (e.g., "1.2.840.113654...") |
| lesionID | Integer | YES | Lesion identifier (1, 2, 3, ...) |
| coordX | Float | YES | World coordinate X in mm (e.g., 61.14) |
| coordY | Float | YES | World coordinate Y in mm (e.g., -163.28) |
| coordZ | Float | YES | World coordinate Z in mm (e.g., -177.75) |
| patientID | String/Int | NO | Patient identifier (e.g., "100570") |
| studyDate | String/Int | NO | Study date in YYYYMMDD format (e.g., "19990102") |
| ageAtStudyDate | Integer | NO | Patient age at study date (e.g., 63) |
| gender | String | NO | Patient gender: "Male" or "Female" (case-sensitive) |

**Success Response (200 OK):**

```json
{
  "status": "success",
  "data": {
    "seriesInstanceUID": "1.2.840.113654.2.55.323804676332963457174235140303454945005",
    "lesionID": 1,
    "probability": 0.985,
    "predictionLabel": 1,
    "processingTimeMs": 150
  }
}
```

**Response Fields:**

- `lesionID`: The same lesion ID from the request
- `probability`: Malignancy probability (0.0 - 1.0)
- `predictionLabel`: 1 (Malignant) or 0 (Benign)
- `processingTimeMs`: Processing time in milliseconds

**Error Responses:**

| HTTP Code | Error Code | Description |
|-----------|------------|-------------|
| 400 | INVALID_FILE_FORMAT | Invalid file format (not .mha/.mhd) or missing required field |
| 401 | UNAUTHORIZED | Missing or invalid Authorization header |
| 403 | FORBIDDEN | Account locked or API limit exceeded |
| 404 | NOT_FOUND | Endpoint not found or service offline |
| 422 | PROCESSING_ERROR | Model internal error (e.g., GPU memory overflow) |
| 500 | INTERNAL_SERVER_ERROR | Unspecified server error |
| 504 | GATEWAY_TIMEOUT | Processing exceeded 600 seconds |

**Example Error Response:**

```json
{
  "error_code": "INVALID_FILE_FORMAT",
  "message": "File must be .mha or .mhd format"
}
```

**Example Usage (cURL):**

```bash
curl -X POST "http://localhost:8000/api/apitest/v1/predict/lesion" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@scan.mha" \
  -F "seriesInstanceUID=1.2.840.113654.2.55.323804676332963457174235140303454945005" \
  -F "lesionID=1" \
  -F "coordX=61.14" \
  -F "coordY=-163.28" \
  -F "coordZ=-177.75" \
  -F "patientID=100570" \
  -F "studyDate=19990102" \
  -F "ageAtStudyDate=63" \
  -F "gender=Male"
```

**Example Usage (Python):**

```python
import requests

url = "http://localhost:8000/api/apitest/v1/predict/lesion"
headers = {"Authorization": "Bearer YOUR_JWT_TOKEN"}

files = {'file': open('scan.mha', 'rb')}
data = {
    'seriesInstanceUID': '1.2.840.113654.2.55.323804676332963457174235140303454945005',
    'lesionID': 1,
    'coordX': 61.14,
    'coordY': -163.28,
    'coordZ': -177.75,
    'patientID': '100570',
    'studyDate': '19990102',
    'ageAtStudyDate': 63,
    'gender': 'Male'
}

response = requests.post(url, files=files, data=data, headers=headers)
print(response.json())
```

---

### 2. Docker Image Submission API

#### POST /submissions/docker

Upload a Docker image containing a LUNA model for automatic evaluation.

**Content-Type:** `multipart/form-data`

**Authentication:** Required - JWT token

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file | File | YES | Docker image file (.tar, .tar.gz, or .tgz) |
| dataset_id | String | YES | Dataset ID to evaluate against |
| model_endpoint | String | NO | API endpoint for model testing (optional) |

**Success Response (201 Created):**

```json
{
  "id": 42,
  "submission_type": "docker",
  "docker_image_name": "model.tar",
  "docker_image_path": "minio://submissions/user_1/dataset_2/docker_abc123.tar",
  "dataset_id": 2,
  "evaluation_status": "pending",
  "message": "Docker image uploaded successfully. Evaluation will start shortly."
}
```

**Process:**

1. Docker image is uploaded to MinIO storage
2. System loads the Docker image
3. Container is started with the model
4. Model is tested with the dataset
5. Predictions are evaluated and metrics computed
6. Leaderboard is updated with results

**Evaluation Status Values:**

- `pending`: Waiting to start evaluation
- `running`: Currently evaluating the model
- `completed`: Evaluation finished successfully
- `failed`: Evaluation failed (check evaluation_error field)

**Error Responses:**

| HTTP Code | Description |
|-----------|-------------|
| 400 | Invalid request (missing dataset_id, wrong file format) |
| 503 | Storage unavailable (MinIO not ready) |
| 500 | Internal server error |

**Example Usage (cURL):**

```bash
curl -X POST "http://localhost:8000/submissions/docker" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@my_model.tar" \
  -F "dataset_id=2" \
  -F "model_endpoint=/predict"
```

**Example Usage (Python):**

```python
import requests

url = "http://localhost:8000/submissions/docker"
headers = {"Authorization": "Bearer YOUR_JWT_TOKEN"}

files = {'file': open('my_model.tar', 'rb')}
data = {
    'dataset_id': '2',
    'model_endpoint': '/predict'
}

response = requests.post(url, files=files, data=data, headers=headers)
print(response.json())
```

---

## Changes Summary

### Models Updated

**Submission Model** - New fields added:
- `submission_type`: 'csv' or 'docker'
- `docker_image_path`: MinIO path to Docker image
- `docker_image_name`: Docker image filename
- `model_endpoint`: API endpoint for model testing
- `evaluation_status`: Status of evaluation (pending/running/completed/failed)
- `evaluation_error`: Error message if evaluation fails

### MinIO Configuration

MinIO endpoints now properly handle `http://` and `https://` prefixes.

Configuration is read from environment variables:
- `MINIO_ENDPOINT`: MinIO server endpoint (e.g., "localhost:9000")
- `MINIO_ACCESS_KEY`: Access key (default: "minioadmin")
- `MINIO_SECRET_KEY`: Secret key (default: "minioadmin")
- `MINIO_SECURE`: Use HTTPS (default: "false")
- `MINIO_SUBMISSIONS_BUCKET`: Bucket for submissions (default: "submissions")

### Background Evaluation

Docker submissions are automatically evaluated in the background:
1. Image is downloaded from MinIO
2. Docker image is loaded
3. Container is started
4. Model API is tested with dataset samples
5. Predictions are collected and evaluated
6. Metrics are computed and stored
7. Leaderboard is updated

---

## Testing

Run the manual test script:

```bash
cd backend
python3 test_lesion_api.py
```

This will test:
- Successful prediction request
- Missing authorization
- Invalid file format
- Invalid gender value
- Empty file

---

## Notes

- The lesion prediction endpoint currently returns mock predictions for testing
- In production, this endpoint should be connected to the actual LUNA model
- Docker evaluation uses background tasks to avoid blocking the API
- All files are stored in MinIO for scalability
- The system automatically cleans up temporary files after evaluation
