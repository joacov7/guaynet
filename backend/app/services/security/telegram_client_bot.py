"""
Client commands of the Telegram bot: titular and linked members of a security
subscription (see services/security/telegram_link.py for how a chat gets linked).

Every action re-checks that the chat is linked to the subscription it acts on,
including the ones that arrive as button presses (callback data can be forged).
Messages use HTML parse mode with escaped values.
"""
import html
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.services.security.notifications import _md
from app.services.security.telegram_link import ChatLink, LinkError, chat_links, consume_link, family_chat_ids, unlink_chat

logger = logging.getLogger(__name__)

AR_TZ = timezone(timedelta(hours=-3))  # Argentina, no DST (same rule as schedule.py)
HISTORY_LIMIT = 10

_EVENT_LABELS = {
    "armed": "🔒 Armado",
    "disarmed": "🔓 Desarmado",
    "intrusion": "🚨 Intrusión",
    "battery_low": "🔋 Batería baja",
    "battery_restored": "🔋 Batería normal",
    "power_failure": "⚡ Corte de luz",
    "power_restored": "⚡ Volvió la luz",
    "communication_lost": "📡 Sin comunicación",
    "communication_restored": "📡 Comunicación restablecida",
    "tamper": "⚠️ Manipulación del equipo",
    "tamper_restored": "⚠️ Manipulación normalizada",
    "zone_open": "🚪 Zona abierta",
    "zone_restore": "🚪 Zona cerrada",
    "test": "🧪 Prueba",
    "panic": "🆘 Pánico",
    "duress": "🆘 Coacción",
    "other": "• Otro evento",
}

HELP = (
    "🛡 <b>Guaynet Seguridad</b>\n\n"
    "/estado — Cómo está tu alarma\n"
    "/historial — Últimos eventos\n"
    "/entrada <code>[minutos]</code> — Iniciar entrada segura\n"
    "/llegue <code>PIN</code> — Avisar que llegaste bien\n"
    "/vacaciones <code>[DD/MM]</code> — Modo vacaciones hasta esa fecha\n"
    "/panico — Enviar alerta de pánico\n"
    "/desvincular — Dejar de recibir avisos en este chat"
)

NOT_LINKED = (
    "Este chat no está vinculado a ninguna alarma.\n"
    "Pedí el enlace de vinculación a Guaynet o generalo desde el portal de clientes."
)

_CB_RE = re.compile(r"^cli:(estado|historial|entrada|vac|panic|panic_ok|unlink_ok):(\d+|-)(?::(\d{0,8}))?$")

Reply = Callable[..., Awaitable]


def _e(text) -> str:
    return html.escape(str(text))


def _local(dt: Optional[datetime], with_date: bool = True) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(AR_TZ).strftime("%d/%m %H:%M" if with_date else "%H:%M")


def _today() -> date:
    return datetime.now(AR_TZ).date()


def _who(link: ChatLink) -> str:
    return link.member.name if link.member else "El titular"


def build_client_handlers(maker):
    """Return the handler callables the main bot wires in."""

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _links(chat_id: int):
        async with maker() as db:
            return await chat_links(db, chat_id)

    async def _pick(update: Update, action: str, extra: str = "") -> Optional[ChatLink]:
        """The only linked subscription, or None after asking which one."""
        links = await _links(update.effective_chat.id)
        if not links:
            await update.message.reply_text(NOT_LINKED)
            return None
        if len(links) == 1:
            return links[0]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(l.property_name[:40], callback_data=f"cli:{action}:{l.sub.id}:{extra}")]
            for l in links[:8]
        ])
        await update.message.reply_text("¿De qué propiedad?", reply_markup=kb)
        return None

    async def _link_for(chat_id: int, sub_id: int) -> Optional[ChatLink]:
        return next((l for l in await _links(chat_id) if l.sub.id == sub_id), None)

    async def _notify_family(link: ChatLink, text: str, kind: str, skip_chat: int) -> None:
        """text is sent with Markdown: build it with _md() around names."""
        from app.services.telegram import send_telegram_to
        async with maker() as db:
            chats = await family_chat_ids(db, link.sub, kind)
        owner = (link.sub.client_telegram_id or "").strip()
        if kind == "entry" and owner and link.member is not None:
            chats = [owner, *chats]  # the titular always hears about entries of others
        for chat in chats:
            if chat != str(skip_chat):
                await send_telegram_to(chat, text)

    # ── actions (shared by commands and buttons) ─────────────────────────────

    async def act_estado(link: ChatLink, reply: Reply) -> None:
        from app.models.security.alert import SecurityAlert
        from app.models.security.contract import VacationMode
        from app.models.security.entry_session import EntrySession, EntrySessionStatus
        from app.models.security.event import SecurityEvent

        sid = link.sub.id

        async with maker() as db:
            async def last(types):
                q = select(SecurityEvent).where(SecurityEvent.subscription_id == sid)
                if types:
                    q = q.where(SecurityEvent.event_type.in_(types))
                return (await db.execute(q.order_by(SecurityEvent.occurred_at.desc()).limit(1))).scalar_one_or_none()

            arm = await last(["armed", "disarmed"])
            any_evt = await last(None)
            power = await last(["power_failure", "power_restored"])
            battery = await last(["battery_low", "battery_restored"])
            open_alerts = (await db.execute(
                select(func.count()).select_from(SecurityAlert).where(
                    SecurityAlert.subscription_id == sid,
                    SecurityAlert.status.in_(["new", "acknowledged"]),
                )
            )).scalar() or 0
            entry = (await db.execute(
                select(EntrySession).where(
                    EntrySession.subscription_id == sid, EntrySession.status == EntrySessionStatus.active,
                )
            )).scalars().first()
            vacation = (await db.execute(
                select(VacationMode).where(
                    VacationMode.subscription_id == sid,
                    VacationMode.active.is_(True),
                    VacationMode.end_date >= _today(),
                )
            )).scalars().first()

        def etype(e):
            return e.event_type.value if hasattr(e.event_type, "value") else e.event_type

        monitored = bool(link.sub.plan and link.sub.plan.includes_monitoring)
        lines = [
            f"🏠 <b>{_e(link.property_name)}</b>",
            f"Plan: {_e(link.sub.plan.name) if link.sub.plan else '—'}"
            f" ({'con central de monitoreo' if monitored else 'sin central de monitoreo'})",
            "",
        ]
        if arm is None:
            lines.append("❔ Armado: todavía sin datos")
        elif etype(arm) == "armed":
            lines.append(f"🔒 <b>Armada</b> desde {_local(arm.occurred_at)}")
        else:
            lines.append(f"🔓 <b>Desarmada</b> desde {_local(arm.occurred_at)}")
        lines.append(f"📡 Última comunicación: {_local(any_evt.received_at) if any_evt else 'sin datos'}")
        if power is not None and etype(power) == "power_failure":
            lines.append(f"⚡ <b>Sin luz</b> desde {_local(power.occurred_at)} (funciona con batería)")
        else:
            lines.append("⚡ Energía: normal" if power or any_evt else "⚡ Energía: sin datos")
        if battery is not None and etype(battery) == "battery_low":
            lines.append(f"🔋 <b>Batería baja</b> desde {_local(battery.occurred_at)}")
        if open_alerts:
            lines.append(f"🚨 Alertas abiertas: {open_alerts}")
        if entry is not None:
            lines.append(f"⏱ Entrada segura activa hasta las {_local(entry.expires_at, with_date=False)}")
        if vacation is not None:
            lines.append(f"🌴 Modo vacaciones hasta el {vacation.end_date.strftime('%d/%m')}")
        if any_evt is not None and any_evt.source == "mock":
            lines.append("\n<i>⚠️ Datos de prueba: la conexión con la central todavía es simulada.</i>")
        await reply("\n".join(lines), parse_mode="HTML")

    async def act_historial(link: ChatLink, reply: Reply) -> None:
        from app.models.security.event import SecurityEvent
        from app.models.security.subscription import SecurityFeatureName

        if not link.sub.has_feature(SecurityFeatureName.event_history):
            await reply("El historial de eventos no está incluido en tu plan.")
            return
        async with maker() as db:
            events = (await db.execute(
                select(SecurityEvent)
                .where(SecurityEvent.subscription_id == link.sub.id)
                .order_by(SecurityEvent.occurred_at.desc())
                .limit(HISTORY_LIMIT)
            )).scalars().all()
        if not events:
            await reply("Todavía no hay eventos registrados.")
            return
        lines = [f"📋 <b>Últimos eventos — {_e(link.property_name)}</b>", ""]
        for e in events:
            t = e.event_type.value if hasattr(e.event_type, "value") else e.event_type
            zone = f" (zona {e.zone_number})" if e.zone_number else ""
            lines.append(f"{_local(e.occurred_at)} · {_EVENT_LABELS.get(t, t)}{zone}")
        if any(e.source == "mock" for e in events):
            lines.append("\n<i>⚠️ Datos de prueba: la conexión con la central todavía es simulada.</i>")
        await reply("\n".join(lines), parse_mode="HTML")

    async def act_entrada(link: ChatLink, reply: Reply, minutes_arg: str, chat_id: int) -> None:
        from app.models.security.subscription import SecurityFeatureName
        from app.schemas.security.entry_session import EntrySessionCreate
        from app.services.runtime_config import int_param
        from app.services.security.entry_sessions import start_entry_session

        if not link.sub.has_feature(SecurityFeatureName.entry_secure):
            await reply("La entrada segura no está incluida en tu plan.")
            return
        minutes = int(minutes_arg) if minutes_arg.isdigit() else await int_param("sec_entry_default_minutes")
        minutes = max(1, min(minutes, 30))
        async with maker() as db:
            try:
                session = await start_entry_session(
                    db, EntrySessionCreate(subscription_id=link.sub.id, duration_minutes=minutes), None,
                )
            except HTTPException as exc:
                await reply(f"No se pudo iniciar: {exc.detail}")
                return
        monitored = bool(link.sub.plan and link.sub.plan.includes_monitoring)
        await reply(
            f"⏱ <b>Entrada segura iniciada</b> en {_e(link.property_name)}.\n"
            f"Tenés {minutes} minutos (hasta las {_local(session.expires_at, with_date=False)}).\n\n"
            "Cuando llegues bien mandá <code>/llegue TU_PIN</code>.\n"
            f"Si no, avisamos {'a la central de monitoreo' if monitored else 'a las personas vinculadas a la alarma'}.",
            parse_mode="HTML",
        )
        await _notify_family(
            link,
            f"⏱ {_md(_who(link))} inició una entrada segura en {_md(link.property_name)} "
            f"hasta las {_local(session.expires_at, with_date=False)}.",
            "entry", chat_id,
        )

    async def act_vacaciones(link: ChatLink, reply: Reply, until: str) -> None:
        from app.models.security.contract import VacationMode
        from app.models.security.subscription import SecurityFeatureName
        from app.services.security.vacation import VacationModeCreate, create_vacation_mode

        if not link.sub.has_feature(SecurityFeatureName.vacation_mode):
            await reply("El modo vacaciones no está incluido en tu plan.")
            return
        if not until:
            async with maker() as db:
                vm = (await db.execute(
                    select(VacationMode).where(
                        VacationMode.subscription_id == link.sub.id,
                        VacationMode.active.is_(True),
                        VacationMode.end_date >= _today(),
                    )
                )).scalars().first()
            if vm:
                await reply(
                    f"🌴 Modo vacaciones activo hasta el {vm.end_date.strftime('%d/%m/%Y')}.\n"
                    "Para desactivarlo antes usá el portal o la app (te pide el PIN)."
                )
            else:
                await reply("No hay modo vacaciones activo.\nPara activarlo: /vacaciones DD/MM (hasta qué día).")
            return
        if not link.is_owner:
            await reply("Solo el titular puede activar el modo vacaciones.")
            return
        end = date(int(until[4:]), int(until[2:4]), int(until[:2]))
        async with maker() as db:
            try:
                vm = await create_vacation_mode(
                    db,
                    VacationModeCreate(subscription_id=link.sub.id, start_date=_today(), end_date=end,
                                       notes="Activado por Telegram"),
                    created_by_user_id=None,
                )
            except HTTPException as exc:
                await reply(f"No se pudo activar: {exc.detail}")
                return
        await reply(
            f"🌴 Modo vacaciones activado hasta el {vm.end_date.strftime('%d/%m/%Y')}.\n"
            "Cualquier movimiento en la propiedad se va a tratar como alerta."
        )

    async def act_panic_ask(link: ChatLink, reply: Reply) -> None:
        from app.models.security.subscription import SecurityFeatureName

        if not link.sub.has_feature(SecurityFeatureName.panic_button):
            await reply("El botón de pánico no está incluido en tu plan.")
            return
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🚨 Sí, enviar alerta", callback_data=f"cli:panic_ok:{link.sub.id}:"),
            InlineKeyboardButton("Cancelar", callback_data="cancelar"),
        ]])
        await reply(f"¿Enviar una <b>alerta de pánico</b> para {_e(link.property_name)}?",
                    parse_mode="HTML", reply_markup=kb)

    async def act_panic_send(link: ChatLink, reply: Reply, chat_id: int, message_id: int) -> None:
        from app.models.security.subscription import SecurityFeatureName
        from app.services.security.alert_factory import create_panic_alert

        if not link.sub.has_feature(SecurityFeatureName.panic_button):
            await reply("El botón de pánico no está incluido en tu plan.")
            return
        async with maker() as db:
            await create_panic_alert(
                db, link.sub.id,
                idempotency_key=f"panic:tg:{chat_id}:{message_id}",
                notes=f"Pánico enviado por Telegram ({_who(link)})",
            )
        monitored = bool(link.sub.plan and link.sub.plan.includes_monitoring)
        await reply(
            "🚨 <b>Alerta de pánico enviada.</b>\n"
            + ("Avisamos a la central de monitoreo y a las personas vinculadas a la alarma."
               if monitored else "Avisamos a las personas vinculadas a la alarma.")
            + "\n<i>Si estás en peligro, llamá al 911.</i>",
            parse_mode="HTML",
        )

    # ── command handlers ─────────────────────────────────────────────────────

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """/start <code> from the deep link, or plain /start /ayuda."""
        if ctx.args:
            if update.effective_chat.type != "private":
                await update.message.reply_text("Abrí el enlace en un chat privado con el bot.")
                return
            async with maker() as db:
                try:
                    name = await consume_link(db, ctx.args[0], update.effective_chat.id)
                except LinkError as exc:
                    await update.message.reply_text(str(exc))
                    return
            await update.message.reply_text(
                f"✅ Listo: vas a recibir los avisos de <b>{_e(name)}</b> en este chat.\n\n{HELP}",
                parse_mode="HTML",
            )
            return
        links = await _links(update.effective_chat.id)
        if not links:
            await update.message.reply_text(NOT_LINKED)
            return
        props = "\n".join(f"• {_e(l.property_name)}" for l in links)
        await update.message.reply_text(f"{HELP}\n\nAlarmas vinculadas:\n{props}", parse_mode="HTML")

    async def estado(update: Update, _ctx) -> None:
        link = await _pick(update, "estado")
        if link:
            await act_estado(link, update.message.reply_text)

    async def historial(update: Update, _ctx) -> None:
        link = await _pick(update, "historial")
        if link:
            await act_historial(link, update.message.reply_text)

    async def entrada(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        arg = ctx.args[0] if ctx.args else ""
        if arg and (not arg.isdigit() or not 1 <= int(arg) <= 30):
            await update.message.reply_text("Uso: /entrada [minutos], entre 1 y 30.")
            return
        link = await _pick(update, "entrada", arg)
        if link:
            await act_entrada(link, update.message.reply_text, arg, update.effective_chat.id)

    async def llegue(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        from app.models.security.entry_session import EntrySession, EntrySessionStatus
        from app.services.security.entry_sessions import cancel_entry_session

        chat = update.effective_chat
        if chat.type != "private":
            await update.message.reply_text("Por seguridad, el PIN solo se acepta en el chat privado con el bot.")
            return
        # The message carries the PIN: remove it from the chat right away
        try:
            await update.message.delete()
        except Exception:
            pass
        if not ctx.args or not ctx.args[0].isdigit():
            await chat.send_message("Uso: /llegue TU_PIN")
            return
        links = await _links(chat.id)
        if not links:
            await chat.send_message(NOT_LINKED)
            return
        by_sub = {l.sub.id: l for l in links}
        async with maker() as db:
            session = (await db.execute(
                select(EntrySession)
                .where(
                    EntrySession.subscription_id.in_(list(by_sub)),
                    EntrySession.status == EntrySessionStatus.active,
                )
                .order_by(EntrySession.created_at.desc())
            )).scalars().first()
            if session is None:
                await chat.send_message("No hay ninguna entrada segura activa.")
                return
            try:
                closed = await cancel_entry_session(db, session.id, ctx.args[0])
            except HTTPException as exc:
                await chat.send_message(f"❌ {exc.detail}")
                return
        link = by_sub[closed.subscription_id]
        # Same answer for the duress PIN: whoever is watching must not notice
        await chat.send_message(f"✅ Entrada segura cerrada en {link.property_name}. ¡Bienvenido!")
        if closed.cancel_reason != "pin_duress":
            await _notify_family(link, f"✅ {_md(_who(link))} llegó bien a {_md(link.property_name)}.", "entry", chat.id)

    async def vacaciones(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        until = ""
        if ctx.args:
            m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?", ctx.args[0])
            try:
                if not m:
                    raise ValueError
                today = _today()
                year = int(m.group(3)) if m.group(3) else today.year
                year = year + 2000 if year < 100 else year
                end = date(year, int(m.group(2)), int(m.group(1)))
                if not m.group(3) and end <= today:
                    end = end.replace(year=today.year + 1)
            except ValueError:
                await update.message.reply_text("Uso: /vacaciones DD/MM (hasta qué día). Ej: /vacaciones 15/01")
                return
            if end <= _today() or end > _today() + timedelta(days=365):
                await update.message.reply_text("La fecha tiene que ser posterior a hoy y dentro del próximo año.")
                return
            until = end.strftime("%d%m%Y")
        link = await _pick(update, "vac", until)
        if link:
            await act_vacaciones(link, update.message.reply_text, until)

    async def panico(update: Update, _ctx) -> None:
        link = await _pick(update, "panic")
        if link:
            await act_panic_ask(link, update.message.reply_text)

    async def desvincular(update: Update, _ctx) -> None:
        if not await _links(update.effective_chat.id):
            await update.message.reply_text(NOT_LINKED)
            return
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Sí, desvincular", callback_data="cli:unlink_ok:-:"),
            InlineKeyboardButton("Cancelar", callback_data="cancelar"),
        ]])
        await update.message.reply_text(
            "¿Dejar de recibir los avisos de la alarma en este chat?", reply_markup=kb,
        )

    async def callback(update: Update, _ctx) -> None:
        """Buttons with data cli:<action>:<sub_id>:<extra>."""
        q = update.callback_query
        m = _CB_RE.match(q.data or "")
        chat_id = q.message.chat.id if q.message else None
        if not m or chat_id is None:
            await q.edit_message_text("❌ Opción inválida.")
            return
        action, sub_s, extra = m.group(1), m.group(2), m.group(3) or ""

        if action == "unlink_ok":
            async with maker() as db:
                n = await unlink_chat(db, chat_id)
            await q.edit_message_text(
                "Listo, este chat ya no recibe avisos de la alarma." if n else NOT_LINKED
            )
            return

        link = await _link_for(chat_id, int(sub_s)) if sub_s.isdigit() else None
        if link is None:
            logger.warning("Client callback %s for unlinked subscription from chat %s", action, chat_id)
            await q.edit_message_text("❌ Este chat no está vinculado a esa alarma.")
            return

        reply = q.edit_message_text
        if action == "estado":
            await act_estado(link, reply)
        elif action == "historial":
            await act_historial(link, reply)
        elif action == "entrada":
            await act_entrada(link, reply, extra, chat_id)
        elif action == "vac":
            if extra and len(extra) != 8:
                await reply("❌ Opción inválida.")
                return
            await act_vacaciones(link, reply, extra)
        elif action == "panic":
            await act_panic_ask(link, reply)
        elif action == "panic_ok":
            await act_panic_send(link, reply, chat_id, q.message.message_id)

    return {
        "start": start,
        "estado": estado,
        "historial": historial,
        "entrada": entrada,
        "llegue": llegue,
        "vacaciones": vacaciones,
        "panico": panico,
        "desvincular": desvincular,
        "callback": callback,
    }
