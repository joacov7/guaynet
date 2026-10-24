"""
Security notification dispatcher.

Routing logic:
  - plan.includes_monitoring=True  → alert dispatched to operator Telegram group
  - subscription.client_telegram_id set → alert dispatched directly to client

Both paths can fire for the same alert (e.g. a monitoring plan that also
notifies the client). Fire-and-forget: errors are logged, never raised.
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


def _alert_type_str(alert: "SecurityAlert") -> str:
    return alert.alert_type.value if hasattr(alert.alert_type, "value") else str(alert.alert_type)


def _build_message(alert: "SecurityAlert", property_name: str, for_client: bool) -> str:
    atype = _alert_type_str(alert)
    emoji = _ALERT_EMOJI.get(atype, "🔔")
    label = _ALERT_LABELS.get(atype, atype)

    header = f"{emoji} *{'Alerta en tu propiedad' if for_client else 'ALERTA DE SEGURIDAD'}*"
    lines = [header, f"*Tipo:* {label}"]
    if property_name:
        lines.append(f"*Propiedad:* {property_name}")
    lines.append(f"*Suscripción:* #{alert.subscription_id}")
    if not for_client:
        lines.append(f"*Estado:* nuevo")
    return "\n".join(lines)


async def dispatch_alert_operator(alert: "SecurityAlert", property_name: str = "") -> None:
    """Send alert to the configured operator Telegram group."""
    try:
        from app.services.telegram import send_telegram
        await send_telegram(_build_message(alert, property_name, for_client=False))
    except Exception as exc:
        logger.warning("Operator Telegram dispatch failed for alert %s: %s", getattr(alert, "id", "?"), exc)


async def dispatch_alert_client(
    alert: "SecurityAlert",
    client_telegram_id: str,
    property_name: str = "",
) -> None:
    """Send alert directly to the client's Telegram chat."""
    try:
        from app.services.telegram import send_telegram_to
        await send_telegram_to(client_telegram_id, _build_message(alert, property_name, for_client=True))
    except Exception as exc:
        logger.warning("Client Telegram dispatch failed for alert %s: %s", getattr(alert, "id", "?"), exc)


async def dispatch_alert(alert: "SecurityAlert", db=None) -> None:
    """
    Route a new alert through the correct notification channels.

    Loads the subscription's plan from DB to determine routing:
      - includes_monitoring=True  → operator group
      - client_telegram_id set    → client direct message
    Both can fire simultaneously.
    """
    property_name = ""
    client_telegram_id = None
    includes_monitoring = True  # safe default: always notify operators if we can't load the plan

    if db is not None:
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            from app.models.security.subscription import SecuritySubscription
            from app.models.security.property import Property

            result = await db.execute(
                select(SecuritySubscription)
                .options(selectinload(SecuritySubscription.plan))
                .where(SecuritySubscription.id == alert.subscription_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                client_telegram_id = sub.client_telegram_id
                if sub.plan:
                    includes_monitoring = sub.plan.includes_monitoring

                # Resolve property name
                prop_result = await db.execute(
                    select(Property.name).where(Property.id == sub.property_id)
                )
                row = prop_result.first()
                if row:
                    property_name = row[0]
        except Exception as exc:
            logger.warning("Could not load subscription for alert %s: %s", getattr(alert, "id", "?"), exc)

    dispatched = False

    if includes_monitoring:
        await dispatch_alert_operator(alert, property_name)
        dispatched = True

    if client_telegram_id:
        await dispatch_alert_client(alert, client_telegram_id, property_name)
        dispatched = True

    if not dispatched:
        logger.warning(
            "Alert %s (subscription #%s) has no notification channel configured "
            "(includes_monitoring=False and no client_telegram_id).",
            getattr(alert, "id", "?"), alert.subscription_id,
        )
