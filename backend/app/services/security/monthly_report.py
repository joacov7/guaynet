"""
Monthly activity report PDF generator.

Generates a one-page PDF summary of security activity for the previous month
and optionally delivers it via Telegram to the client.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import settings

_MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

_EVENT_LABELS = {
    "armed":              "Armado",
    "disarmed":           "Desarmado",
    "intrusion":          "Intrusión",
    "battery_low":        "Batería baja",
    "power_failure":      "Falla de energía",
    "power_restored":     "Energía restaurada",
    "communication_lost": "Pérdida de señal",
    "tamper":             "Manipulación",
    "zone_open":          "Zona abierta",
    "test":               "Prueba",
    "panic":              "Pánico",
    "duress":             "Coacción",
    "other":              "Otro",
}

_ALERT_LABELS = {
    "PANIC":              "Botón de pánico",
    "ENTRY_TIMEOUT":      "Entrada expirada",
    "DURESS":             "PIN de coacción",
    "INTRUSION":          "Intrusión",
    "CHECKIN_MISSED":     "Check-in perdido",
    "INACTIVITY":         "Inactividad",
    "SYSTEM_FAULT":       "Falla de sistema",
    "CONNECTION_LOST":    "Pérdida de señal",
    "SCHEDULE_VIOLATION": "Violación horaria",
}

_ALERT_STATUS_LABELS = {
    "new":         "Nuevo",
    "acknowledged": "Reconocido",
    "resolved":    "Resuelto",
    "false_alarm": "Falsa alarma",
}


def _uploads_path() -> Path:
    p = Path(settings.UPLOADS_DIR) / "security" / "monthly_reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def render_pdf(
    output_path: Path,
    subscription_id: int,
    period: str,           # YYYY-MM
    property_name: str,
    property_address: str,
    plan_name: str,
    event_count: int,
    armed_count: int,
    disarmed_count: int,
    alert_count: int,
    test_count: int,
    event_breakdown: list[tuple[str, int]],   # [(label, count), ...]
    alerts_detail: list[dict],                 # [{type, triggered_at, status}, ...]
    generated_at: datetime,
) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )

    year_str, month_str = period.split("-")
    month_label = _MONTH_NAMES[int(month_str) - 1]
    period_label = f"{month_label} {year_str}"

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    styles = getSampleStyleSheet()
    DARK   = colors.HexColor("#1a2a4a")
    ACCENT = colors.HexColor("#2563eb")
    LIGHT  = colors.HexColor("#f0f4ff")
    GREY   = colors.HexColor("#6b7280")
    GREEN  = colors.HexColor("#16a34a")
    RED    = colors.HexColor("#dc2626")

    title_style = ParagraphStyle("T", parent=styles["Heading1"], fontSize=17, textColor=DARK, spaceAfter=2, alignment=1)
    sub_style   = ParagraphStyle("S", parent=styles["Normal"],   fontSize=11, textColor=ACCENT, spaceAfter=2, alignment=1)
    label_style = ParagraphStyle("L", parent=styles["Normal"],   fontSize=8,  textColor=GREY,  spaceAfter=1)
    value_style = ParagraphStyle("V", parent=styles["Normal"],   fontSize=11, textColor=DARK,  spaceAfter=6)
    section_style = ParagraphStyle("Sec", parent=styles["Heading2"], fontSize=10, textColor=DARK, spaceBefore=10, spaceAfter=4)
    footer_style  = ParagraphStyle("F", parent=styles["Normal"], fontSize=7, textColor=GREY, alignment=1)

    def fmt_dt(iso: str) -> str:
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.strftime("%d/%m %H:%M")
        except Exception:
            return iso

    story = [
        Paragraph("GUAYNET SEGURIDAD", title_style),
        Paragraph(f"Reporte Mensual de Actividad — {period_label}", sub_style),
        Spacer(1, 0.2 * cm),
        HRFlowable(width="100%", thickness=2, color=ACCENT),
        Spacer(1, 0.4 * cm),

        # Property / subscription info
        Paragraph("PROPIEDAD", label_style),
        Paragraph(property_name or "—", value_style),
        Paragraph("DIRECCIÓN", label_style),
        Paragraph(property_address or "—", value_style),
        Paragraph("PLAN  ·  SUSCRIPCIÓN", label_style),
        Paragraph(f"{plan_name or '—'}  ·  #{subscription_id}", value_style),

        Spacer(1, 0.2 * cm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")),

        # Summary stats
        Paragraph("RESUMEN DEL PERÍODO", section_style),
    ]

    summary_data = [
        ["Métrica", "Total"],
        ["Eventos registrados", str(event_count)],
        ["Armes / Desarmes", f"{armed_count} / {disarmed_count}"],
        ["Alertas generadas", str(alert_count)],
        ["Eventos de prueba", str(test_count)],
    ]
    summary_table = Table(summary_data, colWidths=[12 * cm, 4 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTSIZE",   (0, 0), (-1, 0), 9),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("FONTSIZE",   (0, 1), (-1, -1), 9),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("ALIGN",  (1, 0), (1, -1), "CENTER"),
    ]))
    story.append(summary_table)

    # Event breakdown (top types)
    if event_breakdown:
        story.append(Paragraph("ACTIVIDAD POR TIPO DE EVENTO", section_style))
        breakdown_data = [["Tipo de evento", "Cantidad"]] + [
            [label, str(cnt)] for label, cnt in event_breakdown[:10]
        ]
        breakdown_table = Table(breakdown_data, colWidths=[12 * cm, 4 * cm])
        breakdown_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTSIZE",   (0, 0), (-1, 0), 9),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID",  (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",   (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
            ("ALIGN",  (1, 0), (1, -1), "CENTER"),
        ]))
        story.append(breakdown_table)

    # Alerts detail
    if alerts_detail:
        story.append(Paragraph("DETALLE DE ALERTAS", section_style))
        alert_table_data = [["Tipo", "Fecha/Hora", "Estado"]] + [
            [
                _ALERT_LABELS.get(a["type"], a["type"]),
                fmt_dt(a["triggered_at"]),
                _ALERT_STATUS_LABELS.get(a["status"], a["status"]),
            ]
            for a in alerts_detail[:20]
        ]
        alert_table = Table(alert_table_data, colWidths=[6 * cm, 4 * cm, 6 * cm])
        alert_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), RED),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTSIZE",   (0, 0), (-1, 0), 9),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff1f2")]),
            ("GRID",  (0, 0), (-1, -1), 0.5, colors.HexColor("#fecaca")),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",   (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ]))
        story.append(alert_table)

    story += [
        Spacer(1, 0.5 * cm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")),
        Spacer(1, 0.2 * cm),
        Paragraph(
            f"Generado el {generated_at.strftime('%d/%m/%Y %H:%M')} UTC · "
            f"Suscripción #{subscription_id} · Período {period_label} · Guaynet Seguridad",
            footer_style,
        ),
    ]

    doc.build(story)


async def generate_and_deliver(
    db,
    sub,
    period: str,
    report_year: int,
    report_month: int,
) -> dict:
    """
    Generate the PDF for one subscription and send it via Telegram.
    Returns a dict with status and counters for the task.
    """
    from datetime import timedelta
    from sqlalchemy import select, func, extract
    from app.models.security.event import SecurityEvent, SecurityEventType
    from app.models.security.alert import SecurityAlert
    from app.models.security.report import SecurityMonthlyReport, SecurityMonthlyReportStatus
    from app.models.security.property import Property
    from app.models.security.subscription import SecuritySubscription, SecurityFeatureName

    # Fetch property info
    prop_result = await db.execute(select(Property).where(Property.id == sub.property_id))
    prop = prop_result.scalar_one_or_none()
    property_name    = prop.name    if prop else f"Propiedad #{sub.property_id}"
    property_address = prop.address if prop else ""
    plan_name = sub.plan.name if sub.plan else "Plan de seguridad"

    # --- Counts ---
    def _period_filter(model, col):
        return [
            model.subscription_id == sub.id,
            extract("year",  col) == report_year,
            extract("month", col) == report_month,
        ]

    async def _count(model, col, *extra):
        r = await db.execute(
            select(func.count()).select_from(model).where(*_period_filter(model, col), *extra)
        )
        return r.scalar() or 0

    event_count  = await _count(SecurityEvent, SecurityEvent.occurred_at)
    armed_count  = await _count(SecurityEvent, SecurityEvent.occurred_at, SecurityEvent.event_type == SecurityEventType.armed.value)
    disarmed_count = await _count(SecurityEvent, SecurityEvent.occurred_at, SecurityEvent.event_type == SecurityEventType.disarmed.value)
    test_count   = await _count(SecurityEvent, SecurityEvent.occurred_at, SecurityEvent.event_type == SecurityEventType.test.value)
    alert_count  = await _count(SecurityAlert, SecurityAlert.triggered_at)

    # --- Event breakdown by type ---
    from sqlalchemy import case
    breakdown_result = await db.execute(
        select(SecurityEvent.event_type, func.count().label("cnt"))
        .where(*_period_filter(SecurityEvent, SecurityEvent.occurred_at))
        .group_by(SecurityEvent.event_type)
        .order_by(func.count().desc())
    )
    event_breakdown = [
        (_EVENT_LABELS.get(row.event_type, row.event_type), row.cnt)
        for row in breakdown_result
    ]

    # --- Alerts detail (max 20) ---
    alerts_result = await db.execute(
        select(SecurityAlert.alert_type, SecurityAlert.triggered_at, SecurityAlert.status)
        .where(*_period_filter(SecurityAlert, SecurityAlert.triggered_at))
        .order_by(SecurityAlert.triggered_at.desc())
        .limit(20)
    )
    alerts_detail = [
        {
            "type": row.alert_type.value if hasattr(row.alert_type, "value") else str(row.alert_type),
            "triggered_at": row.triggered_at.isoformat() if row.triggered_at else "",
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        }
        for row in alerts_result
    ]

    # --- Generate PDF ---
    now = datetime.now(timezone.utc)
    output_path = _uploads_path() / f"monthly_{sub.id}_{period}.pdf"
    render_pdf(
        output_path=output_path,
        subscription_id=sub.id,
        period=period,
        property_name=property_name,
        property_address=property_address,
        plan_name=plan_name,
        event_count=event_count,
        armed_count=armed_count,
        disarmed_count=disarmed_count,
        alert_count=alert_count,
        test_count=test_count,
        event_breakdown=event_breakdown,
        alerts_detail=alerts_detail,
        generated_at=now,
    )

    # --- Upsert report record ---
    existing = await db.execute(
        select(SecurityMonthlyReport).where(
            SecurityMonthlyReport.subscription_id == sub.id,
            SecurityMonthlyReport.period == period,
        )
    )
    report = existing.scalar_one_or_none()
    if report is None:
        report = SecurityMonthlyReport(subscription_id=sub.id, period=period)
        db.add(report)

    report.generated_at = now
    report.status = SecurityMonthlyReportStatus.ready
    report.event_count = event_count
    report.alert_count = alert_count
    report.test_count = test_count
    report.visit_count = 0
    report.file_path = str(output_path)
    await db.flush()

    # --- Telegram delivery ---
    if sub.client_telegram_id:
        year_str, month_str = period.split("-")
        month_label = _MONTH_NAMES[int(month_str) - 1]
        caption = (
            f"📊 *Reporte Mensual — {month_label} {year_str}*\n"
            f"*Propiedad:* {property_name}\n"
            f"*Suscripción:* #{sub.id}\n\n"
            f"• Eventos registrados: {event_count}\n"
            f"• Armes / Desarmes: {armed_count} / {disarmed_count}\n"
            f"• Alertas generadas: {alert_count}\n"
            f"• Eventos de prueba: {test_count}"
        )
        from app.services.telegram import send_telegram_document
        await send_telegram_document(sub.client_telegram_id, str(output_path), caption)

    return {
        "subscription_id": sub.id,
        "period": period,
        "event_count": event_count,
        "alert_count": alert_count,
    }
