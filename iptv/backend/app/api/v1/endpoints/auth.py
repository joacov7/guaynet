from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_token, verify_password
from app.models.user import User

router = APIRouter()
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class AccessCodeRequest(BaseModel):
    code: str


async def get_current_user(token: str = Depends(oauth2), db: AsyncSession = Depends(get_db)):
    from app.core.security import decode_token
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "Token inválido")
    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(401, "Usuario inactivo")
    return user


async def require_admin(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Se requieren permisos de administrador")
    return user


@router.post("/login")
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Credenciales incorrectas")
    if not user.is_active:
        raise HTTPException(403, "Usuario inactivo")
    return {"access_token": create_token(str(user.id), user.role), "token_type": "bearer", "role": user.role}


@router.post("/code")
async def login_with_code(body: AccessCodeRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.access_code == body.code.strip().upper()))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(401, "Código inválido")
    return {"access_token": create_token(str(user.id), user.role), "token_type": "bearer", "role": user.role}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "role": user.role}
