"""
Electronic contract acceptance (firma electrónica, Ley 25.506 art. 5 — not
"firma digital", which requires a licensed certifier).

Evidence recorded per acceptance: signer name + DNI typed by the client,
identity confirmed with the alarm PIN, UTC timestamp, IP, user-agent, and the
SHA-256 of the exact text accepted. A PDF with the text and that evidence is
generated and sent to the client.
"""
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.security.contract import SecurityContract, SecurityContractTemplate

logger = logging.getLogger(__name__)


def body_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class TemplateCreate(BaseModel):
    version: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=20)


class AcceptRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=150)
    dni: str
    pin: str = Field(min_length=1, max_length=12)
    document_hash: str = Field(min_length=64, max_length=64)
    token: Optional[str] = None

    @field_validator("dni")
    @classmethod
    def _dni(cls, v: str) -> str:
        digits = "".join(ch for ch in v if ch.isdigit())
        if not 7 <= len(digits) <= 8:
            raise ValueError("DNI inválido")
        return digits

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return " ".join(v.split())


# ── Templates ─────────────────────────────────────────────────────────────────

async def list_templates(db: AsyncSession) -> List[SecurityContractTemplate]:
    result = await db.execute(
        select(SecurityContractTemplate).order_by(SecurityContractTemplate.id.desc())
    )
    return result.scalars().all()


async def create_template(
    db: AsyncSession, body: TemplateCreate, user_id: Optional[int]
) -> SecurityContractTemplate:
    tpl = SecurityContractTemplate(
        version=body.version.strip(),
        title=body.title.strip(),
        body=body.body,
        body_hash=body_hash(body.body),
        is_active=False,
        created_by_user_id=user_id,
    )
    db.add(tpl)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Ya existe la versión {body.version}")
    await db.refresh(tpl)
    return tpl


async def activate_template(db: AsyncSession, template_id: int) -> SecurityContractTemplate:
    tpl = await db.get(SecurityContractTemplate, template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Versión de contrato no encontrada")
    await db.execute(
        update(SecurityContractTemplate)
        .where(SecurityContractTemplate.id != template_id)
        .values(is_active=False)
    )
    await db.flush()
    tpl.is_active = True
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def get_active_template(db: AsyncSession) -> Optional[SecurityContractTemplate]:
    result = await db.execute(
        select(SecurityContractTemplate).where(SecurityContractTemplate.is_active == True)
    )
    return result.scalar_one_or_none()


# ── Acceptances ───────────────────────────────────────────────────────────────

async def list_acceptances(
    db: AsyncSession, subscription_id: Optional[int] = None
) -> List[SecurityContract]:
    q = select(SecurityContract).order_by(SecurityContract.id.desc())
    if subscription_id is not None:
        q = q.where(SecurityContract.subscription_id == subscription_id)
    result = await db.execute(q)
    return result.scalars().all()


async def get_acceptance(
    db: AsyncSession, subscription_id: int, version: str
) -> Optional[SecurityContract]:
    result = await db.execute(
        select(SecurityContract).where(
            SecurityContract.subscription_id == subscription_id,
            SecurityContract.version == version,
        )
    )
    return result.scalar_one_or_none()


def _uploads_path() -> Path:
    p = Path(settings.UPLOADS_DIR) / "security" / "contracts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _render_pdf(
    output_path: Path,
    tpl: SecurityContractTemplate,
    acceptance: SecurityContract,
    property_name: str,
    property_address: str,
) -> None:
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.grey)
    mono = ParagraphStyle("mono", parent=styles["Normal"], fontName="Courier", fontSize=7.5, leading=10)

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        title=f"{tpl.title} — v{tpl.version}",
    )
    story = [
        Paragraph(escape(tpl.title), styles["Title"]),
        Paragraph(f"Versión {escape(tpl.version)} · Suscripción #{acceptance.subscription_id}", small),
        Spacer(1, 0.4 * cm),
    ]
    for para in tpl.body.split("\n\n"):
        story.append(Paragraph(escape(para).replace("\n", "<br/>"), body_style))
        story.append(Spacer(1, 0.2 * cm))

    story += [
        Spacer(1, 0.4 * cm),
        HRFlowable(width="100%", color=colors.grey),
        Spacer(1, 0.2 * cm),
        Paragraph("Constancia de aceptación electrónica", styles["Heading3"]),
    ]
    rows = [
        ["Firmante", acceptance.signer_name or "—"],
        ["DNI", acceptance.signer_dni or "—"],
        ["Propiedad", f"{property_name} — {property_address}"],
        ["Fecha y hora (UTC)", acceptance.accepted_at],
        ["Dirección IP", acceptance.acceptance_ip or "—"],
        ["Verificación de identidad", "PIN de la alarma del titular" if acceptance.method == "portal_pin" else (acceptance.method or "—")],
        ["Huella del texto (SHA-256)", acceptance.document_hash or "—"],
    ]
    t = Table(
        [
            [Paragraph(f"<b>{escape(k)}</b>", body_style),
             Paragraph(escape(v), mono if k.startswith("Huella") else body_style)]
            for k, v in rows
        ],
        colWidths=[5 * cm, 12 * cm],
    )
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
    ]))
    story += [
        t,
        Spacer(1, 0.3 * cm),
        Paragraph(
            "La huella SHA-256 permite comprobar que el texto de este documento es idéntico "
            "al aceptado: cualquier modificación del texto produce una huella distinta.",
            small,
        ),
    ]
    doc.build(story)


async def accept_contract(
    db: AsyncSession,
    subscription_id: int,
    req: AcceptRequest,
    ip: Optional[str],
    user_agent: Optional[str],
) -> SecurityContract:
    """Record an acceptance of the active template. PIN must already be verified."""
    from app.models.security.property import Property
    from app.models.security.subscription import SecuritySubscription

    tpl = await get_active_template(db)
    if tpl is None:
        raise HTTPException(status_code=404, detail="No hay un contrato vigente para firmar")
    if req.document_hash != tpl.body_hash:
        # The text shown to the client is not the current version anymore
        raise HTTPException(
            status_code=409,
            detail="El contrato fue actualizado. Recargá la página para leer la versión vigente.",
        )
    if await get_acceptance(db, subscription_id, tpl.version):
        raise HTTPException(status_code=409, detail="Este contrato ya fue firmado")

    acceptance = SecurityContract(
        subscription_id=subscription_id,
        accepted_by_user_id=None,
        template_id=tpl.id,
        version=tpl.version,
        accepted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        acceptance_ip=ip,
        acceptance_user_agent=(user_agent or "")[:500] or None,
        document_hash=tpl.body_hash,
        signer_name=req.full_name,
        signer_dni=req.dni,
        method="portal_pin",
    )
    db.add(acceptance)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Este contrato ya fue firmado")

    sub = await db.get(SecuritySubscription, subscription_id)
    prop = await db.get(Property, sub.property_id) if sub else None
    output = _uploads_path() / f"contract_{subscription_id}_v{tpl.version}_{acceptance.id}.pdf"
    _render_pdf(output, tpl, acceptance, prop.name if prop else "—", prop.address if prop else "—")
    acceptance.pdf_path = str(output)
    await db.commit()
    await db.refresh(acceptance)

    if sub and sub.client_telegram_id:
        try:
            from app.services.telegram import send_telegram_document
            await send_telegram_document(
                sub.client_telegram_id,
                str(output),
                caption=f"📄 Copia de tu contrato firmado ({tpl.title}, versión {tpl.version}).",
            )
        except Exception as exc:
            logger.warning("Could not send signed contract to client: %s", exc)

    return acceptance
