"""User seeder for creating test accounts."""

from sqlalchemy.orm import Session
from ..models import User
from ..utils.auth import hash_password


def seed(db: Session):
    """Seed users table with test accounts.

    This seeder will ensure core accounts exist. It will not bail out
    when the users table is non-empty; instead it will create missing
    accounts (useful when running seed repeatedly).
    """

    desired = [
        {
            "username": "admin",
            "password": "admin123",
            "full_name": "Administrator",
            "role": "admin",
            "group_name": "Admin Group",
        },
        {
            "username": "teacher1",
            "password": "teacher123",
            "full_name": "Teacher One",
            "role": "teacher",
            "group_name": "Teachers",
        },
    ]

    # Create students student1..student20 each mapped to Group 1..Group 20
    # Add nhom1..nhom24 accounts (keep existing accounts unchanged)
    for i in range(1, 25):
        desired.append({
            "username": f"nhom{i}",
            "password": "P4ssw0rd!",
            "full_name": f"Nhom {i}",
            "role": "student",
            "group_name": f"Group {i}",
        })

    for user_data in desired:
        existing = db.query(User).filter(User.username == user_data["username"]).first()
        if existing:
            # ensure role and group are set for seeded accounts (do not change password)
            changed = False
            desired_role = user_data.get("role", "user")
            if getattr(existing, "role", None) != desired_role:
                existing.role = desired_role
                changed = True
            desired_group = user_data.get("group_name")
            if desired_group and getattr(existing, "group_name", None) != desired_group:
                existing.group_name = desired_group
                changed = True
            if changed:
                db.add(existing)
            continue

        user = User(
            username=user_data["username"],
            password_hash=hash_password(user_data["password"]),
            full_name=user_data.get("full_name"),
            role=user_data.get("role", "user"),
            group_name=user_data.get("group_name"),
        )
        db.add(user)

    db.commit()