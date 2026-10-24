"""
Security notification dispatcher.

Sends alerts via available channels when a SecurityAlert is created.
Currently supports Telegram (existing infrastructure).
SMS/WhatsApp will be added when credentials are available.

All functions are fire-and-forget: errors are logged, never raised.
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.security.alert import SecurityAlert

logger = logging.getLogger(__name__)

_ALERT_EMOJI = {
    "PANIC":              "🚨",
    "ENTRY_TIMEOUT":      "⏰",
    "DURESS":             "🆘",
    "INTRUSION":          "🔓",
    "CHECKIN_MISSED":     "❓",
    "INACTIVITY":         "😴",
    "SYSTEM_FAULT":       "⚠️",
    "CONNECTION_LOST":    "📡",
    "SCHEDULE_VIOLATION": "🕐",
}

_ALERT_LABELS = {
    "PANIC":              "Botón de pánico",
    "ENTRY_TIMEOUT":      "Entrada segura expirada",
    "DURESS":             "PIN de coacción",
    "INTRUSION":          "Intrusión detectada",
    "CHECKIN_MISSED":     "Check-in no realizado",
    "INACTIVITY":         "Inactividad detectada",
    "SYSTEM_FAULT":       "Falla del sistema",
    "CONNECTION_LOST":    "Pérdida de comunicación",
    "SCHEDULE_VIOLATION": "Violación de horario",
}


async def dispatch_alert_telegram(alert: "SecurityAlert", property_name: str = "") -> None:
    """Send a Telegram message to configured operator chat IDs."""
    try:
        from app.services.telegram import send_telegram

        emoji = _ALERT_EMOJI.get(alert.alert_type.value if hasattr(alert.alert_type, "value") else str(alert.alert_type), "🔔")
        label = _ALERT_LABELS.get(alert.alert_type.value if hasattr(alert.alert_type, "value") else str(alert.alert_type), str(alert.alert_type))

        lines = [
            f"{emoji} *ALERTA DE SEGURIDAD*",
            f"*Tipo:* {label}",
        ]
        if property_name:
            lines.append(f"*Propiedad:* {property_name}")
        lines.append(f"*Suscripción:* #{alert.subscription_id}")
        lines.append(f"*Estado:* nuevo")

        await send_telegram("\n".join(lines))
    except Exception as exc:
        logger.warning("Telegram dispatch failed for alert %s: %s", getattr(alert, "id", "?"), exc)


async def dispatch_alert(alert: "SecurityAlert", db=None) -> None:
    """
    Entry point: dispatch a new alert through all configured channels.
    Resolves property name from DB when db is provided.
    """
    property_name = ""
    if db is not None:
        try:
            from sqlalchemy import select
            from app.models.security.subscription import SecuritySubscription
            from app.models.security.property import Property
            result = await db.execute(
                select(Property.name)
                .join(SecuritySubscription, SecuritySubscription.property_id == Property.id)
                .where(SecuritySubscription.id == alert.subscription_id)
            )
            row = result.first()
            if row:
                property_name = row[0]
        except Exception:
            pass

    await dispatch_alert_telegram(alert, property_name)
