"""User seeder for creating test accounts."""

from sqlalchemy.orm import Session
from ..models import User
from ..utils.auth import hash_password

def seed(db: Session):
    """Seed users table with test accounts."""
    # Check if we already have users
    if db.query(User).count() > 0:
        return
    
    users = [
        {
            "username": "admin",
            "password": "admin123",
            "full_name": "Administrator",
            "role": "admin",
            "group_name": "Admin Group"
        },
        {
            "username": "teacher1",
            "password": "teacher123",
            "full_name": "Teacher One",
            "role": "teacher",
            "group_name": "Teachers"
        },
        {
            "username": "student1",
            "password": "student123",
            "full_name": "Student One",
            "role": "user",
            "group_name": "Group 1"
        },
        {
            "username": "student2",
            "password": "student123",
            "full_name": "Student Two",
            "role": "user",
            "group_name": "Group 2"
        },
        {
            "username": "student3",
            "password": "student123",
            "full_name": "Student Three",
            "role": "user",
            "group_name": "Group 1"
        }
    ]
    
    for user_data in users:
        user = User(
            username=user_data["username"],
            password_hash=hash_password(user_data["password"]),
            full_name=user_data["full_name"],
            role=user_data["role"],
            group_name=user_data["group_name"]
        )
        db.add(user)
    
    db.commit()