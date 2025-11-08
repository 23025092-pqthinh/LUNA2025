from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..deps import get_current_user, require_admin
from ..evaluate import analyze_groundtruth
from ..utils.pagination import Paginator
import os, shutil, uuid
from typing import Optional, List

router = APIRouter(prefix="/datasets", tags=["datasets"])

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "datasets")
os.makedirs(DATA_DIR, exist_ok=True)

@router.get("/", response_model=schemas.Page[schemas.DatasetOut])
def list_datasets(
    params: schemas.DatasetFilterParams = Depends(),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """List datasets with pagination and filters. Regular users see only official
    datasets and their own uploads. Admins see all datasets."""
    q = db.query(models.Dataset)
    
    # Apply filters
    if params.is_official is not None:
        q = q.filter(models.Dataset.is_official == params.is_official)
    if params.uploader_id is not None:
        q = q.filter(models.Dataset.uploader_id == params.uploader_id)
    elif user.role != "admin":
        # Regular users see official datasets + their own
        q = q.filter((models.Dataset.is_official == True) | 
                    (models.Dataset.uploader_id == user.id))
    
    return Paginator(
        query=q.order_by(models.Dataset.created_at.desc()),
        page=params.page,
        page_size=params.page_size
    ).execute()

@router.post("/", response_model=schemas.DatasetOut, dependencies=[Depends(require_admin)],
           status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    name: str = Form(...),
    description: str = Form(""),
    data_file: Optional[UploadFile] = File(None),
    groundtruth_csv: UploadFile = File(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Upload a new dataset. Only admins can create datasets.
    - data_file: Optional dataset file (e.g. images archive)
    - groundtruth_csv: Required CSV with ground truth labels (must have id,label columns)
    """
    # Save files with unique names to avoid collisions
    data_path = None
    if data_file is not None:
        ext = os.path.splitext(data_file.filename)[1]
        unique_name = f"{uuid.uuid4()}{ext}"
        data_path = os.path.join(DATA_DIR, unique_name)
        with open(data_path, "wb") as f:
            shutil.copyfileobj(data_file.file, f)

    gt_ext = os.path.splitext(groundtruth_csv.filename)[1]
    if gt_ext.lower() != '.csv':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ground truth file must be a CSV"
        )
    
    gt_name = f"{uuid.uuid4()}.csv"
    gt_path = os.path.join(DATA_DIR, gt_name)
    with open(gt_path, "wb") as f:
        shutil.copyfileobj(groundtruth_csv.file, f)

    try:
        ds = models.Dataset(
            name=name, description=description,
            data_file_path=data_path, groundtruth_path=gt_path,
            uploader_id=user.id
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)
        return ds
    except Exception as e:
        # Clean up files if DB operation fails
        if data_path and os.path.exists(data_path):
            os.unlink(data_path)
        if os.path.exists(gt_path):
            os.unlink(gt_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create dataset"
        )

@router.post("/{id}/mark_official", dependencies=[Depends(require_admin)],
           response_model=schemas.DatasetOut)
def mark_official(id: int, db: Session = Depends(get_db)):
    """Mark a dataset as official (only one can be official at a time). Admin only."""
    ds = db.query(models.Dataset).get(id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Clear official flag from all datasets and set this one
    db.query(models.Dataset).update({"is_official": False})
    ds.is_official = True
    db.commit()
    db.refresh(ds)
    return ds

@router.get("/{id}", response_model=schemas.DatasetOut)
def get_dataset(
    id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Get dataset details. Users can only see official datasets or their own uploads."""
    ds = db.query(models.Dataset).get(id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    if user.role != "admin" and not ds.is_official and ds.uploader_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    return ds

@router.get("/{id}/groundtruth")
def download_groundtruth(
    id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Download dataset ground truth CSV. Protected - users can only access official
    datasets or their own uploads."""
    ds = db.query(models.Dataset).get(id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    if user.role != "admin" and not ds.is_official and ds.uploader_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if not ds.groundtruth_path or not os.path.exists(ds.groundtruth_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ground truth file not found"
        )
    
    # Use a sensible filename: dataset_name_groundtruth.csv
    safe_name = "".join(c for c in ds.name if c.isalnum() or c in "-_").lower()
    filename = f"{safe_name}_groundtruth.csv"
    return FileResponse(
        ds.groundtruth_path,
        media_type="text/csv",
        filename=filename
    )

@router.post("/{id}/analyze",
            response_model=schemas.DatasetOut,
            dependencies=[Depends(require_admin)])
def analyze_dataset(id: int, db: Session = Depends(get_db)):
    """Analyze dataset ground truth to compute statistics. Admin only."""
    ds = db.query(models.Dataset).get(id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    if not ds.groundtruth_path or not os.path.exists(ds.groundtruth_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ground truth file not found"
        )
    
    try:
        stats = analyze_groundtruth(ds.groundtruth_path)
        ds.stats_json = stats
        db.commit()
        db.refresh(ds)
        return ds
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to analyze dataset: {str(e)}"
        )
