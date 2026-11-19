"""
SMTP email alert service.
Settings are read from system_config table at send time.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional


async def send_email_alert(subject: str, body: str, db) -> bool:
    """Send an email alert using SMTP settings from system_config. Returns True on success."""
    from app.models.config import SystemConfig

    async def _get(key: str, default: str = "") -> str:
        row = await db.get(SystemConfig, key)
        return row.value if row else default

    smtp_host = await _get("smtp_host")
    smtp_port_s = await _get("smtp_port", "587")
    smtp_user = await _get("smtp_user")
    smtp_password = await _get("smtp_password")
    smtp_from = await _get("smtp_from") or smtp_user
    alert_email = await _get("alert_email")

    if not smtp_host or not alert_email:
        return False

    try:
        smtp_port = int(smtp_port_s)
    except ValueError:
        smtp_port = 587

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Guaynet WISP] {subject}"
    msg["From"] = smtp_from
    msg["To"] = alert_email
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if smtp_port != 465:
                server.starttls()
                server.ehlo()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True
    except Exception:
        return False


async def test_email_config(db) -> dict:
    ok = await send_email_alert(
        "Prueba de configuración",
        "Este es un mensaje de prueba desde Guaynet WISP.\n\nSi recibís este email, la configuración SMTP es correcta.",
        db,
    )
    if ok:
        return {"ok": True, "message": "Email enviado correctamente"}
    return {"ok": False, "message": "No se pudo enviar. Verificá host, puerto, usuario y contraseña SMTP."}
