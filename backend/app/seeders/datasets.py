"""Dataset seeder for creating sample datasets."""

import os
import shutil
from sqlalchemy.orm import Session
from ..models import Dataset, User
import pandas as pd
import numpy as np

def create_sample_groundtruth(path: str, size: int = 1000):
    """Create a sample groundtruth CSV file."""
    ids = list(range(1, size + 1))
    # Generate random binary labels with slight imbalance
    labels = np.random.choice([0, 1], size=size, p=[0.7, 0.3])
    
    df = pd.DataFrame({
        'id': ids,
        'label': labels
    })
    df.to_csv(path, index=False)
    return {
        'total_samples': size,
        'positive_samples': int(labels.sum()),
        'negative_samples': int(size - labels.sum()),
        'class_distribution': {
            '0': float(np.mean(labels == 0)),
            '1': float(np.mean(labels == 1))
        }
    }

def seed(db: Session):
    """Seed datasets table with sample data."""
    # Check if we already have datasets
    if db.query(Dataset).count() > 0:
        return
    
    # Get admin user for uploader_id
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        return
    
    # Ensure uploads directory exists
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "datasets")
    os.makedirs(upload_dir, exist_ok=True)
    
    datasets = [
        {
            "name": "Training Dataset 2025",
            "description": "Official training dataset for LUNA 2025",
            "is_official": True,
            "size": 1000
        },
        {
            "name": "Validation Dataset",
            "description": "Validation dataset for model testing",
            "is_official": True,
            "size": 500
        },
        {
            "name": "Test Dataset Small",
            "description": "Small test dataset for quick iterations",
            "is_official": False,
            "size": 200
        }
    ]
    
    for ds_data in datasets:
        # Create groundtruth file
        gt_name = f"{ds_data['name'].lower().replace(' ', '_')}_groundtruth.csv"
        gt_path = os.path.join(upload_dir, gt_name)
        
        stats = create_sample_groundtruth(gt_path, ds_data["size"])
        
        ds = Dataset(
            name=ds_data["name"],
            description=ds_data["description"],
            groundtruth_path=gt_path,
            uploader_id=admin.id,
            is_official=ds_data["is_official"],
            stats_json=stats
        )
        db.add(ds)
    
    db.commit()