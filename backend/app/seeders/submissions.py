"""Submission seeder for creating sample submissions."""

import os
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from ..models import Submission, Dataset, User, Metric
from sklearn.metrics import roc_auc_score, f1_score

def create_sample_submission(groundtruth_path: str, quality: str = 'good') -> tuple:
    """Create a sample submission with controlled quality."""
    gt_df = pd.read_csv(groundtruth_path)
    
    # Base predictions on groundtruth with controlled noise
    if quality == 'good':
        noise = np.random.normal(0, 0.2, len(gt_df))
    elif quality == 'medium':
        noise = np.random.normal(0, 0.4, len(gt_df))
    else:  # poor
        noise = np.random.normal(0, 0.8, len(gt_df))
    
    # Generate probabilities
    probs = np.clip(gt_df['label'].values + noise, 0, 1)
    
    # Create submission dataframe
    sub_df = pd.DataFrame({
        'id': gt_df['id'],
        'probability': probs
    })
    
    # Calculate metrics
    predictions = (probs > 0.5).astype(int)
    metrics = {
        'auc': float(roc_auc_score(gt_df['label'], probs)),
        'f1': float(f1_score(gt_df['label'], predictions))
    }
    
    return sub_df, metrics

def seed(db: Session):
    """Seed submissions table with sample data."""
    # Check if we already have submissions
    if db.query(Submission).count() > 0:
        return
    
    # Get datasets and users
    datasets = db.query(Dataset).all()
    users = db.query(User).filter(User.role == 'user').all()
    
    if not datasets or not users:
        return
    
    # Ensure submissions directory exists
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                             "uploads", "submissions")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Create some submissions for each user on each dataset
    for user in users:
        for dataset in datasets:
            # Skip if dataset is not official and user is not the uploader
            if not dataset.is_official and dataset.uploader_id != user.id:
                continue
                
            qualities = ['good', 'medium', 'poor']
            for quality in qualities:
                # Create submission file
                sub_df, metrics = create_sample_submission(dataset.groundtruth_path, quality)
                
                # Save submission file
                sub_name = f"submission_{user.username}_{dataset.id}_{quality}.csv"
                sub_path = os.path.join(upload_dir, sub_name)
                sub_df.to_csv(sub_path, index=False)
                
                # Create submission record
                submission = Submission(
                    dataset_id=dataset.id,
                    user_id=user.id,
                    file_path=sub_path,
                    evaluated=True,
                    score_json=metrics
                )
                db.add(submission)
                
                # Add individual metrics
                db.flush()  # Get submission ID
                for metric_name, value in metrics.items():
                    metric = Metric(
                        submission_id=submission.id,
                        metric_name=metric_name,
                        metric_value=value
                    )
                    db.add(metric)
    
    db.commit()