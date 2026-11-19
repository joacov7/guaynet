from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.core.deps import get_current_user, get_db
from app.services.security.certificate import get_or_create_certificate, verify_certificate

router = APIRouter()
public_router = APIRouter()


@router.post("/{subscription_id}/certificate")
async def generate_certificate(
    subscription_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    """Generate (or regenerate) the protection certificate PDF for a subscription."""
    cert = await get_or_create_certificate(db, subscription_id)
    return {
        "id": cert.id,
        "issued_at": cert.issued_at.isoformat(),
        "valid_until": cert.valid_until.isoformat(),
        "verification_token": cert.verification_token,
        "download_url": f"/api/v1/security/subscriptions/{subscription_id}/certificate/download",
    }


@router.get("/{subscription_id}/certificate/download")
async def download_certificate(
    subscription_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    """Download the current protection certificate PDF."""
    from sqlalchemy import select
    from app.models.security.report import SecurityCertificate
    from fastapi import HTTPException

    result = await db.execute(
        select(SecurityCertificate).where(
            SecurityCertificate.subscription_id == subscription_id
        )
    )
    cert = result.scalar_one_or_none()
    if cert is None or not cert.file_path:
        raise HTTPException(
            status_code=404,
            detail="Certificado no generado. Usá POST /certificate primero.",
        )

    return FileResponse(
        path=cert.file_path,
        media_type="application/pdf",
        filename=f"certificado_proteccion_{subscription_id}.pdf",
    )


@public_router.get("/verify/{token}")
async def verify_cert(token: str, db=Depends(get_db)):
    """
    Public endpoint — no auth required.
    Insurers scan the QR and call this to confirm the certificate is genuine.
    """
    return await verify_certificate(db, token)
