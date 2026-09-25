from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User
from app.security import hash_password


async def seed_admin(db: AsyncSession) -> None:
    existing = (await db.execute(select(User).where(User.username == settings.default_admin_username.lower()))).scalar_one_or_none()
    if existing:
        return
    db.add(
        User(
            username=settings.default_admin_username.lower(),
            name="Administrator",
            email="admin@pingwatch.local",
            phone="",
            password_hash=hash_password(settings.default_admin_password),
            role="admin",
            status="active",
            must_change_password=1,
        )
    )
    await db.commit()
