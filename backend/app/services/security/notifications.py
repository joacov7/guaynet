"""
Security notification dispatcher.

Routing logic per alert:

  1. Alert type is DURESS → always goes to operators silently (never ask client).
  2. alert_confirmation feature enabled + client_telegram_id set
       → Send "¿Estás bien?" keyboard to client.
       → Set confirmation_sent_at / confirmation_expires_at on the alert.
       → Do NOT dispatch to operators yet.
       → If client responds "Estoy bien" → false_alarm (handled by bot callback).
       → If client responds "Necesito ayuda" → escalate to operators (handled by bot callback).
       → If window expires without response → check_confirmation_timeouts task escalates.
  3. includes_monitoring=True (and condition 2 does not apply)
       → Dispatch to operator group immediately.
  4. client_telegram_id set (and condition 2 does not apply)
       → Plain message to client.
  5. Neither channel → log warning.

Fire-and-forget: errors are logged, never raised.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.security.alert import SecurityAlert

logger = logging.getLogger(__name__)

# Alert types that bypass the client confirmation flow (safety-critical).
_NO_CONFIRMATION_TYPES = {"DURESS"}

# Window for the client to respond before operators are called.
CONFIRMATION_WINDOW_SECONDS = 180  # 3 minutes

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
    if for_client:
        lines.append("\n_¿Podés confirmarnos que estás bien?_")
    else:
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
    """Send a plain alert message directly to the client's Telegram chat."""
    try:
        from app.services.telegram import send_telegram_to
        await send_telegram_to(client_telegram_id, _build_message(alert, property_name, for_client=True))
    except Exception as exc:
        logger.warning("Client Telegram dispatch failed for alert %s: %s", getattr(alert, "id", "?"), exc)


async def dispatch_alert(alert: "SecurityAlert", db=None) -> None:
    """
    Route a new alert through the correct notification channels.
    See module docstring for the full routing logic.
    """
    property_name = ""
    client_telegram_id: Optional[str] = None
    includes_monitoring = True  # safe default
    confirmation_enabled = False

    if db is not None:
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            from app.models.security.subscription import SecuritySubscription, SecurityFeatureName
            from app.models.security.property import Property

            result = await db.execute(
                select(SecuritySubscription)
                .options(
                    selectinload(SecuritySubscription.plan),
                    selectinload(SecuritySubscription.features),
                )
                .where(SecuritySubscription.id == alert.subscription_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                client_telegram_id = sub.client_telegram_id
                if sub.plan:
                    includes_monitoring = sub.plan.includes_monitoring
                confirmation_enabled = sub.has_feature(SecurityFeatureName.alert_confirmation)

                prop_result = await db.execute(
                    select(Property.name).where(Property.id == sub.property_id)
                )
                row = prop_result.first()
                if row:
                    property_name = row[0]
        except Exception as exc:
            logger.warning("Could not load subscription for alert %s: %s", getattr(alert, "id", "?"), exc)

    atype = _alert_type_str(alert)
    use_confirmation = (
        confirmation_enabled
        and client_telegram_id
        and atype not in _NO_CONFIRMATION_TYPES
    )

    if use_confirmation:
        await _dispatch_with_confirmation(alert, client_telegram_id, property_name, db)
        return

    dispatched = False

    if atype in _NO_CONFIRMATION_TYPES or includes_monitoring:
        await dispatch_alert_operator(alert, property_name)
        dispatched = True

    if client_telegram_id:
        await dispatch_alert_client(alert, client_telegram_id, property_name)
        dispatched = True

    if not dispatched:
        logger.warning(
            "Alert %s (subscription #%s) has no notification channel configured.",
            getattr(alert, "id", "?"), alert.subscription_id,
        )


async def _dispatch_with_confirmation(
    alert: "SecurityAlert",
    client_telegram_id: str,
    property_name: str,
    db,
) -> None:
    """
    Send the "¿Estás bien?" keyboard message to the client and record the
    confirmation window on the alert row.  Operator dispatch is deferred until
    the client responds or the window expires (handled by check_confirmation_timeouts).
    """
    try:
        from app.services.telegram import send_telegram_confirmation
        alert_id = getattr(alert, "id", None)
        if alert_id is None:
            logger.warning("Cannot send confirmation: alert has no id yet")
            return

        msg_id = await send_telegram_confirmation(
            client_telegram_id,
            _build_message(alert, property_name, for_client=True),
            alert_id,
        )

        now = datetime.now(timezone.utc)
        alert.confirmation_sent_at = now
        alert.confirmation_expires_at = now + timedelta(seconds=CONFIRMATION_WINDOW_SECONDS)
        if msg_id:
            alert.confirmation_telegram_msg_id = msg_id

        if db is not None:
            db.add(alert)
            await db.flush()

        logger.info(
            "Confirmation sent for alert %s, window expires at %s",
            alert_id, alert.confirmation_expires_at,
        )
    except Exception as exc:
        logger.error("Failed to send confirmation for alert %s: %s", getattr(alert, "id", "?"), exc)
        # Fall back to operator dispatch so the alert is never silently dropped
        await dispatch_alert_operator(alert, property_name)
