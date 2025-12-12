"""Database seeders for initializing test data."""

from sqlalchemy.orm import Session
from . import users, datasets, submissions
from ..utils.auth import hash_password

def seed_all(db: Session):
    """Run all seeders in the correct order."""
    users.seed(db)
    # NOTE: dataset seeding disabled to avoid recreating sample datasets
    # during deployments. Remove this comment and uncomment the next line
    # to re-enable dataset seeding in non-production environments.
    # datasets.seed(db)
    submissions.seed(db)