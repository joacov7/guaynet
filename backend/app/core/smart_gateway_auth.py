"""Authentication dependency for outbound Smart gateway connections."""
import hashlib
import hmac

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.smart_foundation import SmartGateway


async def get_authenticated_smart_gateway(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> SmartGateway:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Credencial de gateway requerida")
    token = authorization[7:].strip()
    if len(token) < 32:
        raise HTTPException(status_code=401, detail="Credencial de gateway inválida")

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    result = await db.execute(
        select(SmartGateway).where(SmartGateway.credential_hash == token_hash)
    )
    gateway = result.scalar_one_or_none()
    if gateway is None or gateway.status == "revoked":
        raise HTTPException(status_code=401, detail="Credencial de gateway inválida")

    # Constant-time comparison after indexed lookup; never log or return the token.
    if not hmac.compare_digest(gateway.credential_hash or "", token_hash):
        raise HTTPException(status_code=401, detail="Credencial de gateway inválida")
    return gateway
