from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _seed()
    yield


async def _seed():
    async with AsyncSessionLocal() as db:
        from app.models.user import User
        try:
            existing = (await db.execute(
                select(User).where(User.username == settings.FIRST_ADMIN)
            )).scalar_one_or_none()
            if not existing:
                db.add(User(
                    username=settings.FIRST_ADMIN,
                    hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                    role="admin",
                    is_active=True,
                ))
                await db.commit()
        except Exception:
            await db.rollback()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
