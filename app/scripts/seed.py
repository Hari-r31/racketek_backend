"""
User Seed Script - Inserts default users only

Run:
    cd E:\Work\racketek\backend
    .venv\Scripts\python -m app.scripts.seed
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Register all models
import app.db.base  # noqa: F401

from app.db.session import SessionLocal
from app.models.user import User
from app.enums import UserRole
from app.models.cart import Cart
from app.core.security import get_password_hash


DEFAULT_USERS = [
    ("Super Admin", "admin@racketek.com", "9000000001", "Admin@123", UserRole.super_admin),
    ("Admin User", "admin2@racketek.com", "9000000002", "Admin@123", UserRole.admin),
    ("Staff Member", "staff@racketek.com", "9000000003", "Staff@123", UserRole.staff),
    ("Test Customer", "customer@racketek.com", "9000000004", "Customer@123", UserRole.customer),
]


def seed_users():
    db = SessionLocal()
    try:
        for full_name, email, phone, password, role in DEFAULT_USERS:
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                print(f"⏭ Already exists: {email}")
                continue

            user = User(
                full_name=full_name,
                email=email,
                phone=phone,
                hashed_password=get_password_hash(password),
                role=role,
                is_active=True,
                is_email_verified=True,
            )

            db.add(user)
            db.flush()  # get user.id

            db.add(Cart(user_id=user.id))

            print(f"✅ Created {role.value}: {email}")

        db.commit()
        print("\n🎉 User seed completed successfully.")

    except Exception as e:
        db.rollback()
        print("❌ Seed failed:", str(e))
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_users()