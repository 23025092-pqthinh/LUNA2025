from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..deps import get_current_user, require_admin
from .. import models
import os, time, httpx, random
from datetime import datetime

router = APIRouter(prefix="/apitest", tags=["apitest"])

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "samples")
os.makedirs(SAMPLE_DIR, exist_ok=True)

# Put two tiny placeholder sample files
for i in range(1,3):
    p = os.path.join(SAMPLE_DIR, f"sample_{i}.txt")
    if not os.path.exists(p):
        with open(p, "w") as f: f.write(f"sample-{i}")

@router.get("/samples")
def list_samples():
    files = [f for f in os.listdir(SAMPLE_DIR) if os.path.isfile(os.path.join(SAMPLE_DIR,f))]
    return [{"name": fn, "path": f"/apitest/sample/{fn}"} for fn in files]

@router.get("/sample/{name}")
def download_sample(name: str):
    path = os.path.join(SAMPLE_DIR, name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Sample not found")
    return {"name": name, "size": os.path.getsize(path)}

@router.post("/call", dependencies=[Depends(require_admin)])
def call_model(url: str = Form(...), sample_name: str = Form(...), db: Session = Depends(get_db), user = Depends(get_current_user)):
    file_path = os.path.join(SAMPLE_DIR, sample_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Sample not found")

    timeout = float(os.getenv("API_TEST_TIMEOUT", "10"))
    start = time.perf_counter()
    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
            with httpx.Client(timeout=timeout) as client:
                r = client.post(url, files=files)
        elapsed = (time.perf_counter() - start) * 1000.0
        preview = r.text[:500]
        status = r.status_code
    except Exception as ex:
        elapsed = (time.perf_counter() - start) * 1000.0
        status = 0
        preview = f"ERROR: {ex}"

    log = models.ApiLog(
        request_url=url,
        status_code=int(status),
        response_time=float(elapsed),
        result_preview=preview
    )
    db.add(log); db.commit()
    return {"status_code": status, "latency_ms": elapsed, "preview": preview}


@router.post("/v1/predict/lesion")
async def predict_lesion(
    file: UploadFile = File(...),
    seriesInstanceUID: str = Form(...),
    lesionID: int = Form(...),
    coordX: float = Form(...),
    coordY: float = Form(...),
    coordZ: float = Form(...),
    patientID: Optional[str] = Form(None),
    studyDate: Optional[str] = Form(None),
    ageAtStudyDate: Optional[int] = Form(None),
    gender: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/predict/lesion - Endpoint for lesion prediction
    
    Accepts .mha/.mhd file and metadata, returns prediction for lung nodule.
    This is a test endpoint that validates the API contract.
    """
    # Validate authorization
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={"error_code": "UNAUTHORIZED", "message": "Authorization header required"}
        )
    
    # Validate file format
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_FILE_FORMAT", "message": "No file provided"}
        )
    
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ['.mha', '.mhd']:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_FILE_FORMAT", "message": "File must be .mha or .mhd format"}
        )
    
    # Validate gender if provided
    if gender and gender not in ['Male', 'Female']:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "VALIDATION_ERROR", "message": "Gender must be 'Male' or 'Female'"}
        )
    
    # Process the request (mock implementation)
    start_time = time.perf_counter()
    
    try:
        # Read file content (in real implementation, this would be processed by the model)
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "INVALID_FILE_FORMAT", "message": "Empty file"}
            )
        
        # Mock prediction (in production, this would call the actual model)
        # For now, return a mock response that demonstrates the API format
        probability = random.uniform(0.1, 0.99)
        prediction_label = 1 if probability >= 0.5 else 0
        
        processing_time = int((time.perf_counter() - start_time) * 1000)
        
        # Log the API call
        log = models.ApiLog(
            request_url=f"/api/v1/predict/lesion",
            status_code=200,
            response_time=float(processing_time),
            result_preview=f"Lesion {lesionID}: {probability:.3f}"
        )
        db.add(log)
        db.commit()
        
        return {
            "status": "success",
            "data": {
                "seriesInstanceUID": seriesInstanceUID,
                "lesionID": lesionID,
                "probability": round(probability, 3),
                "predictionLabel": prediction_label,
                "processingTimeMs": processing_time
            }
        }
        
    except HTTPException:
        raise
    except Exception as ex:
        # Log error with sanitized message
        processing_time = int((time.perf_counter() - start_time) * 1000)
        error_msg = "Processing error occurred"  # Sanitized message
        log = models.ApiLog(
            request_url=f"/api/v1/predict/lesion",
            status_code=422,
            response_time=float(processing_time),
            result_preview=error_msg
        )
        db.add(log)
        db.commit()
        
        raise HTTPException(
            status_code=422,
            detail={"error_code": "PROCESSING_ERROR", "message": "Internal processing error"}
        )
