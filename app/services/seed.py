from datetime import datetime, timezone

from app.core.config import settings
from app.core.security import hash_password
from app.db.mongodb import get_users_collection


async def seed_default_users() -> None:
    await seed_user(
        email=settings.seed_admin_email,
        password=settings.seed_admin_password,
        name=settings.seed_admin_name,
        role="admin",
    )
    await seed_user(
        email=settings.seed_customer_email,
        password=settings.seed_customer_password,
        name=settings.seed_customer_name,
        role="customer",
    )


async def seed_user(email: str, password: str, name: str, role: str) -> None:
    users = get_users_collection()
    normalized_email = email.lower()
    existing = await users.find_one({"email": normalized_email})
    if existing:
        return

    now = datetime.now(timezone.utc)
    await users.insert_one(
        {
            "name": name,
            "email": normalized_email,
            "phone": None,
            "role": role,
            "password_hash": hash_password(password),
            "is_active": True,
            "is_verified": True,
            "created_at": now,
            "updated_at": now,
        }
    )
