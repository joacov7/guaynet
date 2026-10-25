"""
Security protection certificate generator.

Generates a PDF certificate that subscribers can present to their home
insurance company to obtain a premium discount.

Uses ReportLab for PDF generation and its built-in QR barcode for the
verification code. The QR links to the public verify endpoint so insurers
can scan and confirm authenticity online.
"""
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.security.report import SecurityCertificate
from app.models.security.subscription import SecuritySubscription


def _uploads_path() -> Path:
    p = Path(settings.UPLOADS_DIR) / "security" / "certificates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _verify_url(token: str) -> str:
    return f"{settings.PUBLIC_URL}/api/v1/security/certificates/verify/{token}"


def _render_pdf(
    output_path: Path,
    token: str,
    subscription_id: int,
    property_name: str,
    property_address: str,
    plan_name: str,
    contract_start: str,
    issued_at: datetime,
    valid_until: datetime,
) -> None:
    """Render certificate PDF using ReportLab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics import renderPDF

    W, H = A4
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    styles = getSampleStyleSheet()
    DARK = colors.HexColor("#1a2a4a")
    ACCENT = colors.HexColor("#2563eb")
    LIGHT = colors.HexColor("#f0f4ff")

    title_style = ParagraphStyle(
        "CertTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=DARK,
        spaceAfter=4,
        alignment=1,  # center
    )
    sub_style = ParagraphStyle(
        "CertSub",
        parent=styles["Normal"],
        fontSize=11,
        textColor=ACCENT,
        spaceAfter=2,
        alignment=1,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#6b7280"),
        spaceAfter=1,
    )
    value_style = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontSize=11,
        textColor=DARK,
        spaceAfter=8,
    )
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=7,
        textColor=colors.HexColor("#9ca3af"),
        alignment=1,
    )

    def fmt_date(dt: datetime) -> str:
        months = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ]
        return f"{dt.day} de {months[dt.month - 1]} de {dt.year}"

    cert_number = token[:8].upper()
    verify_url = _verify_url(token)

    # Build QR widget
    qr = QrCodeWidget(verify_url)
    qr_size = 3.5 * cm
    qr.barWidth = qr_size
    qr.barHeight = qr_size
    d = Drawing(qr_size, qr_size)
    d.add(qr)

    story = [
        # Header band
        Paragraph("GUAYNET SEGURIDAD", title_style),
        Paragraph("Certificado de Protección Domiciliaria", sub_style),
        Spacer(1, 0.3 * cm),
        HRFlowable(width="100%", thickness=2, color=ACCENT),
        Spacer(1, 0.5 * cm),

        # Certificate number
        Paragraph("NÚMERO DE CERTIFICADO", label_style),
        Paragraph(f"<b>{cert_number}</b>", value_style),

        # Property info
        Paragraph("PROPIEDAD PROTEGIDA", label_style),
        Paragraph(property_name or "—", value_style),

        Paragraph("DIRECCIÓN", label_style),
        Paragraph(property_address or "—", value_style),

        # Subscription info
        Paragraph("PLAN DE PROTECCIÓN", label_style),
        Paragraph(plan_name or "—", value_style),

        Paragraph("NÚMERO DE SUSCRIPCIÓN", label_style),
        Paragraph(f"#{subscription_id}", value_style),

        Paragraph("INICIO DE CONTRATO", label_style),
        Paragraph(contract_start or "—", value_style),

        Spacer(1, 0.3 * cm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")),
        Spacer(1, 0.4 * cm),

        # Validity
        Paragraph("PERÍODO DE VALIDEZ", label_style),
        Paragraph(
            f"<b>{fmt_date(issued_at)}</b> al <b>{fmt_date(valid_until)}</b>",
            value_style,
        ),

        Spacer(1, 0.5 * cm),

        # QR + verification text side by side
        Table(
            [[d, Paragraph(
                f"<b>Verificación digital</b><br/>"
                f"Este certificado puede ser verificado por la aseguradora "
                f"escaneando el código QR o ingresando a:<br/>"
                f"<font color='#2563eb'>{verify_url}</font>",
                ParagraphStyle(
                    "QrText",
                    parent=styles["Normal"],
                    fontSize=8,
                    textColor=DARK,
                    leading=12,
                ),
            )]],
            colWidths=[4 * cm, 12 * cm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("ROWPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#dbeafe")),
            ]),
        ),

        Spacer(1, 0.8 * cm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")),
        Spacer(1, 0.3 * cm),

        Paragraph(
            f"Emitido el {fmt_date(issued_at)}. "
            "Este documento acredita que la propiedad indicada cuenta con servicio activo de "
            "monitoreo y/o alarma domiciliaria provisto por Guaynet Seguridad. "
            "Válido para presentar ante compañías de seguros del hogar.",
            footer_style,
        ),
    ]

    doc.build(story)


async def get_or_create_certificate(
    db: AsyncSession,
    subscription_id: int,
) -> SecurityCertificate:
    """
    Generate (or regenerate) the protection certificate for a subscription.
    Returns the updated SecurityCertificate record.
    """
    from app.models.security.property import Property
    from app.models.security.subscription import SecurityPlan

    # Load subscription with plan and property
    result = await db.execute(
        select(SecuritySubscription)
        .options(
            selectinload(SecuritySubscription.plan),
            selectinload(SecuritySubscription.features),
        )
        .where(SecuritySubscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    prop_result = await db.execute(
        select(Property).where(Property.id == sub.property_id)
    )
    prop = prop_result.scalar_one_or_none()

    plan_name = sub.plan.name if sub.plan else "Plan de seguridad"
    property_name = prop.name if prop else f"Propiedad #{sub.property_id}"
    property_address = prop.address if prop else ""
    contract_start = sub.contract_start or ""

    now = datetime.now(timezone.utc)
    valid_until = now + timedelta(days=365)
    token = uuid.uuid4().hex  # 32-char hex

    # Fetch or create the certificate record
    cert_result = await db.execute(
        select(SecurityCertificate).where(
            SecurityCertificate.subscription_id == subscription_id
        )
    )
    cert = cert_result.scalar_one_or_none()

    if cert is None:
        cert = SecurityCertificate(
            subscription_id=subscription_id,
            issued_at=now,
            valid_until=valid_until,
            verification_token=token,
        )
        db.add(cert)
    else:
        # Regenerate: new token + new dates
        cert.issued_at = now
        cert.valid_until = valid_until
        cert.verification_token = token

    await db.flush()  # get cert.id if new

    output_path = _uploads_path() / f"cert_{subscription_id}_{token[:8]}.pdf"
    _render_pdf(
        output_path=output_path,
        token=token,
        subscription_id=subscription_id,
        property_name=property_name,
        property_address=property_address,
        plan_name=plan_name,
        contract_start=str(contract_start),
        issued_at=now,
        valid_until=valid_until,
    )

    cert.file_path = str(output_path)
    await db.commit()
    await db.refresh(cert)
    return cert


async def verify_certificate(db: AsyncSession, token: str) -> dict:
    """Public verification endpoint payload."""
    result = await db.execute(
        select(SecurityCertificate).where(
            SecurityCertificate.verification_token == token
        )
    )
    cert = result.scalar_one_or_none()
    if cert is None:
        raise HTTPException(status_code=404, detail="Certificado no encontrado")

    now = datetime.now(timezone.utc)
    valid = cert.valid_until >= now

    return {
        "valid": valid,
        "subscription_id": cert.subscription_id,
        "issued_at": cert.issued_at.isoformat(),
        "valid_until": cert.valid_until.isoformat(),
        "expired": not valid,
    }
