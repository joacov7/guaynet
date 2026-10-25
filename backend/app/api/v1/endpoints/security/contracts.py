from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.security.contract import SecurityContract
from app.services.security import contracts as svc

router = APIRouter()


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    title: str
    body: str
    body_hash: str
    is_active: bool
    created_at: datetime


class AcceptanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    version: str
    accepted_at: str
    signer_name: Optional[str] = None
    signer_dni: Optional[str] = None
    acceptance_ip: Optional[str] = None
    document_hash: Optional[str] = None
    method: Optional[str] = None
    has_pdf: bool = False

    @classmethod
    def from_model(cls, c: SecurityContract) -> "AcceptanceResponse":
        r = cls.model_validate(c)
        r.has_pdf = bool(c.pdf_path)
        return r


@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(_=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await svc.list_templates(db)


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    body: svc.TemplateCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await svc.create_template(db, body, current_user.id)


@router.post("/templates/{template_id}/activate", response_model=TemplateResponse)
async def activate_template(
    template_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await svc.activate_template(db, template_id)


@router.get("/acceptances", response_model=List[AcceptanceResponse])
async def list_acceptances(
    subscription_id: Optional[int] = Query(default=None),
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return [AcceptanceResponse.from_model(c) for c in await svc.list_acceptances(db, subscription_id)]


@router.get("/acceptances/{acceptance_id}/pdf")
async def download_acceptance_pdf(
    acceptance_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c = await db.get(SecurityContract, acceptance_id)
    if c is None or not c.pdf_path or not Path(c.pdf_path).is_file():
        raise HTTPException(status_code=404, detail="PDF no disponible")
    return FileResponse(
        c.pdf_path,
        media_type="application/pdf",
        filename=f"contrato_sub{c.subscription_id}_v{c.version}.pdf",
    )
