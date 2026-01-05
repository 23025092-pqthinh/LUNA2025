import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import io

# Mock database before importing app
import sys
mock_db = Mock()
mock_db.Base = type('Base', (), {'metadata': Mock()})
mock_db.engine = Mock()
mock_db.SessionLocal = Mock()
mock_db.get_db = Mock()
sys.modules['app.database'] = mock_db

from app.main import app

client = TestClient(app)


def test_predict_lesion_endpoint_without_auth():
    """Test that endpoint requires authorization"""
    response = client.post("/api/apitest/v1/predict/lesion")
    assert response.status_code == 401
    assert "UNAUTHORIZED" in str(response.json())


def test_predict_lesion_endpoint_invalid_file_format():
    """Test that endpoint validates file format"""
    # Create a mock file with wrong extension
    files = {"file": ("test.txt", io.BytesIO(b"test data"), "text/plain")}
    data = {
        "seriesInstanceUID": "1.2.840.113654.2.55.323804676332963457174235140303454945005",
        "lesionID": 1,
        "coordX": 61.14,
        "coordY": -163.28,
        "coordZ": -177.75,
    }
    
    response = client.post(
        "/api/apitest/v1/predict/lesion",
        files=files,
        data=data,
        headers={"Authorization": "Bearer test_token"}
    )
    
    assert response.status_code == 400
    assert "INVALID_FILE_FORMAT" in str(response.json())


def test_predict_lesion_endpoint_success():
    """Test successful prediction"""
    # Create a mock .mha file
    files = {"file": ("test.mha", io.BytesIO(b"mock mha data"), "application/octet-stream")}
    data = {
        "seriesInstanceUID": "1.2.840.113654.2.55.323804676332963457174235140303454945005",
        "lesionID": 1,
        "coordX": 61.14,
        "coordY": -163.28,
        "coordZ": -177.75,
        "patientID": "100570",
        "studyDate": "19990102",
        "ageAtStudyDate": 63,
        "gender": "Male"
    }
    
    response = client.post(
        "/api/apitest/v1/predict/lesion",
        files=files,
        data=data,
        headers={"Authorization": "Bearer test_token"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    assert "data" in result
    assert result["data"]["seriesInstanceUID"] == data["seriesInstanceUID"]
    assert result["data"]["lesionID"] == data["lesionID"]
    assert "probability" in result["data"]
    assert "predictionLabel" in result["data"]
    assert "processingTimeMs" in result["data"]
    assert 0 <= result["data"]["probability"] <= 1
    assert result["data"]["predictionLabel"] in [0, 1]


def test_predict_lesion_endpoint_invalid_gender():
    """Test that endpoint validates gender field"""
    files = {"file": ("test.mha", io.BytesIO(b"mock mha data"), "application/octet-stream")}
    data = {
        "seriesInstanceUID": "1.2.840.113654.2.55.323804676332963457174235140303454945005",
        "lesionID": 1,
        "coordX": 61.14,
        "coordY": -163.28,
        "coordZ": -177.75,
        "gender": "invalid"  # Invalid gender
    }
    
    response = client.post(
        "/api/apitest/v1/predict/lesion",
        files=files,
        data=data,
        headers={"Authorization": "Bearer test_token"}
    )
    
    assert response.status_code == 400
    assert "VALIDATION_ERROR" in str(response.json())


def test_predict_lesion_endpoint_empty_file():
    """Test that endpoint rejects empty files"""
    files = {"file": ("test.mha", io.BytesIO(b""), "application/octet-stream")}
    data = {
        "seriesInstanceUID": "1.2.840.113654.2.55.323804676332963457174235140303454945005",
        "lesionID": 1,
        "coordX": 61.14,
        "coordY": -163.28,
        "coordZ": -177.75,
    }
    
    response = client.post(
        "/api/apitest/v1/predict/lesion",
        files=files,
        data=data,
        headers={"Authorization": "Bearer test_token"}
    )
    
    assert response.status_code == 400
    assert "Empty file" in str(response.json())
