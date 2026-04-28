from datetime import datetime, timedelta
from typing import Optional, Union

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: Union[str, int], expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (
        expires_delta if expires_delta else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode({"exp": expire, "sub": str(subject)}, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None


def encrypt_value(value: str) -> str:
    if not settings.ENCRYPTION_KEY:
        return value
    from cryptography.fernet import Fernet
    return Fernet(settings.ENCRYPTION_KEY.encode()).encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    if not settings.ENCRYPTION_KEY:
        return encrypted
    try:
        from cryptography.fernet import Fernet
        return Fernet(settings.ENCRYPTION_KEY.encode()).decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted
