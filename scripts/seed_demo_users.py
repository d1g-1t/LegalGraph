from __future__ import annotations

import asyncio
from uuid import uuid4


DEMO_USERS = [
    {
        "email": "admin@legalops.ru",
        "password": "Admin123!@#",
        "role": "ADMIN",
    },
    {
        "email": "lawyer@legalops.ru",
        "password": "Lawyer123!@#",
        "role": "LAWYER",
    },
    {
        "email": "reviewer@legalops.ru",
        "password": "Reviewer123!@#",
        "role": "REVIEWER",
    },
    {
        "email": "analyst@legalops.ru",
        "password": "Analyst123!@#",
        "role": "ANALYST",
    },
    {
        "email": "viewer@legalops.ru",
        "password": "Viewer123!@#",
        "role": "VIEWER",
    },
]


async def main() -> None:
    from src.core.config import get_settings
    from src.core.security import hash_password
    from src.infrastructure.database import build_session_factory
    from src.infrastructure.database.models import ApiUserModel

    from sqlalchemy import select

    session_factory = build_session_factory()
    async with session_factory() as session:
        for u in DEMO_USERS:
            exists = await session.scalar(
                select(ApiUserModel.id).where(ApiUserModel.email == u["email"])
            )
            if exists:
                print(f"  [skip] {u['email']} already exists")
                continue

            user = ApiUserModel(
                id=uuid4(),
                email=u["email"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
                is_active=True,
            )
            session.add(user)
            print(f"  [+] {u['email']} ({u['role']})")

        await session.commit()

    print("\n✅ Demo users seeded successfully!")


if __name__ == "__main__":
    asyncio.run(main())
