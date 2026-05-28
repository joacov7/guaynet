import asyncio
import logging
from typing import List

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from app.models.client import Client, ClientStatus
from app.models.plan import Plan
from app.models.router import MikrotikRouter
from app.services.mikrotik import MikrotikError, build_service_from_router

logger = logging.getLogger(__name__)


def _emoji(status: str) -> str:
    return {"active": "✅", "suspended": "⛔", "cancelled": "❌"}.get(status, "❓")


async def _push_mikrotik(client: Client, db):
    plan = await db.get(Plan, client.plan_id)
    router = await db.get(MikrotikRouter, client.router_id)
    if not plan or not router:
        return
    disabled = client.status == ClientStatus.suspended

    def _sync():
        svc = build_service_from_router(router)
        with svc:
            existing = svc.get_queue_by_name(client.mikrotik_queue_name)
            params = dict(
                name=client.mikrotik_queue_name,
                target=client.mikrotik_target,
                max_limit=plan.mikrotik_max_limit,
                burst_limit=plan.mikrotik_burst_limit,
                burst_threshold=plan.mikrotik_burst_threshold,
                burst_time=plan.mikrotik_burst_time if plan.mikrotik_burst_limit else None,
                comment=f"guaynet:{client.id}|{client.full_name}",
                disabled=disabled,
            )
            if existing:
                svc.update_simple_queue(existing["id"], **{
                    k: v for k, v in params.items()
                    if k not in ("name", "target") and v is not None
                })
            else:
                svc.add_simple_queue(**params)

    await asyncio.to_thread(_sync)


def build_application(token: str, database_url: str, allowed_ids: List[int]) -> Application:
    engine = create_async_engine(database_url)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    def ok(update: Update) -> bool:
        return not allowed_ids or update.effective_chat.id in allowed_ids

    # ── /start /help ──────────────────────────────────────────────────────────

    async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
        if not ok(update):
            return
        await update.message.reply_text(
            "🛰 *Guaynet Bot*\n\n"
            "Comandos disponibles:\n"
            "/buscar `<nombre o IP>` — Buscar clientes\n"
            "/estado `<id>` — Ver estado del cliente\n"
            "/planes — Listar planes activos\n"
            "/cortar `<id>` — Suspender servicio\n"
            "/activar `<id>` — Activar servicio\n"
            "/plan `<id_cliente> <id_plan>` — Cambiar plan",
            parse_mode="Markdown",
        )

    # ── /buscar ───────────────────────────────────────────────────────────────

    async def cmd_buscar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not ok(update):
            return
        if not ctx.args:
            await update.message.reply_text("Uso: /buscar <nombre o IP>")
            return
        term = f"%{' '.join(ctx.args)}%"
        async with maker() as db:
            rows = (await db.execute(
                select(Client).where(
                    or_(
                        (Client.first_name + " " + Client.last_name).ilike(term),
                        Client.ip_address.like(term),
                        Client.phone.like(term),
                    )
                ).limit(10)
            )).scalars().all()
        if not rows:
            await update.message.reply_text("No se encontraron clientes.")
            return
        lines = [f"{_emoji(c.status)} `{c.id}` — {c.full_name} ({c.ip_address})" for c in rows]
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    # ── /estado ───────────────────────────────────────────────────────────────

    async def cmd_estado(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not ok(update):
            return
        if not ctx.args or not ctx.args[0].isdigit():
            await update.message.reply_text("Uso: /estado <id>")
            return
        async with maker() as db:
            client = (await db.execute(
                select(Client)
                .options(selectinload(Client.plan), selectinload(Client.router))
                .where(Client.id == int(ctx.args[0]))
            )).scalar_one_or_none()
        if not client:
            await update.message.reply_text("Cliente no encontrado.")
            return
        await update.message.reply_text(
            f"{_emoji(client.status)} *{client.full_name}*\n"
            f"ID: `{client.id}` | Estado: {client.status}\n"
            f"IP: `{client.ip_address}`\n"
            f"Plan: {client.plan.name if client.plan else '—'}\n"
            f"Router: {client.router.name if client.router else '—'}\n"
            f"Tel: {client.phone or '—'}",
            parse_mode="Markdown",
        )

    # ── /planes ───────────────────────────────────────────────────────────────

    async def cmd_planes(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
        if not ok(update):
            return
        async with maker() as db:
            plans = (await db.execute(
                select(Plan).where(Plan.is_active == True).order_by(Plan.price)
            )).scalars().all()
        if not plans:
            await update.message.reply_text("No hay planes activos.")
            return
        lines = [
            f"`{p.id}` — {p.name}  {p.download_mbps}/{p.upload_mbps} Mbps  ${p.price}"
            for p in plans
        ]
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    # ── /cortar ───────────────────────────────────────────────────────────────

    async def cmd_cortar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not ok(update):
            return
        if not ctx.args or not ctx.args[0].isdigit():
            await update.message.reply_text("Uso: /cortar <id>")
            return
        cid = int(ctx.args[0])
        async with maker() as db:
            client = await db.get(Client, cid)
        if not client:
            await update.message.reply_text("Cliente no encontrado.")
            return
        if client.status == ClientStatus.suspended:
            await update.message.reply_text(f"⛔ {client.full_name} ya está suspendido.")
            return
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirmar corte", callback_data=f"cortar:{cid}"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancelar"),
        ]])
        await update.message.reply_text(
            f"¿Suspender el servicio de *{client.full_name}* ({client.ip_address})?",
            reply_markup=kb, parse_mode="Markdown",
        )

    # ── /activar ──────────────────────────────────────────────────────────────

    async def cmd_activar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not ok(update):
            return
        if not ctx.args or not ctx.args[0].isdigit():
            await update.message.reply_text("Uso: /activar <id>")
            return
        cid = int(ctx.args[0])
        async with maker() as db:
            client = await db.get(Client, cid)
        if not client:
            await update.message.reply_text("Cliente no encontrado.")
            return
        if client.status == ClientStatus.active:
            await update.message.reply_text(f"✅ {client.full_name} ya está activo.")
            return
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirmar activación", callback_data=f"activar:{cid}"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancelar"),
        ]])
        await update.message.reply_text(
            f"¿Activar el servicio de *{client.full_name}* ({client.ip_address})?",
            reply_markup=kb, parse_mode="Markdown",
        )

    # ── /plan ─────────────────────────────────────────────────────────────────

    async def cmd_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not ok(update):
            return
        if len(ctx.args) < 2 or not ctx.args[0].isdigit() or not ctx.args[1].isdigit():
            await update.message.reply_text("Uso: /plan <id_cliente> <id_plan>")
            return
        cid, pid = int(ctx.args[0]), int(ctx.args[1])
        async with maker() as db:
            client = await db.get(Client, cid)
            plan = await db.get(Plan, pid)
        if not client:
            await update.message.reply_text("Cliente no encontrado.")
            return
        if not plan or not plan.is_active:
            await update.message.reply_text("Plan no encontrado o inactivo. Usá /planes para ver los disponibles.")
            return
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirmar cambio", callback_data=f"plan:{cid}:{pid}"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancelar"),
        ]])
        await update.message.reply_text(
            f"¿Cambiar *{client.full_name}* al plan *{plan.name}* "
            f"({plan.download_mbps}/{plan.upload_mbps} Mbps)?",
            reply_markup=kb, parse_mode="Markdown",
        )

    # ── Callbacks (botones inline) ────────────────────────────────────────────

    async def on_callback(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        data = q.data

        if data == "cancelar":
            await q.edit_message_text("❌ Operación cancelada.")
            return

        if data.startswith("cortar:"):
            cid = int(data.split(":")[1])
            async with maker() as db:
                result = await db.execute(
                    select(Client)
                    .options(selectinload(Client.plan), selectinload(Client.router))
                    .where(Client.id == cid)
                )
                client = result.scalar_one_or_none()
                if not client:
                    await q.edit_message_text("Cliente no encontrado.")
                    return
                client.status = ClientStatus.suspended
                db.add(client)
                await db.commit()
                await db.refresh(client)
                try:
                    await _push_mikrotik(client, db)
                except MikrotikError as e:
                    await q.edit_message_text(
                        f"⚠️ Suspendido en DB pero error Mikrotik: {e}"
                    )
                    return
            await q.edit_message_text(
                f"⛔ Servicio de *{client.full_name}* suspendido.", parse_mode="Markdown"
            )

        elif data.startswith("activar:"):
            cid = int(data.split(":")[1])
            async with maker() as db:
                result = await db.execute(
                    select(Client)
                    .options(selectinload(Client.plan), selectinload(Client.router))
                    .where(Client.id == cid)
                )
                client = result.scalar_one_or_none()
                if not client:
                    await q.edit_message_text("Cliente no encontrado.")
                    return
                client.status = ClientStatus.active
                db.add(client)
                await db.commit()
                await db.refresh(client)
                try:
                    await _push_mikrotik(client, db)
                except MikrotikError as e:
                    await q.edit_message_text(
                        f"⚠️ Activado en DB pero error Mikrotik: {e}"
                    )
                    return
            await q.edit_message_text(
                f"✅ Servicio de *{client.full_name}* activado.", parse_mode="Markdown"
            )

        elif data.startswith("plan:"):
            _, cid_s, pid_s = data.split(":")
            cid, pid = int(cid_s), int(pid_s)
            async with maker() as db:
                result = await db.execute(
                    select(Client)
                    .options(selectinload(Client.plan), selectinload(Client.router))
                    .where(Client.id == cid)
                )
                client = result.scalar_one_or_none()
                plan = await db.get(Plan, pid)
                if not client or not plan:
                    await q.edit_message_text("Cliente o plan no encontrado.")
                    return
                client.plan_id = pid
                db.add(client)
                await db.commit()
                await db.refresh(client)
                try:
                    await _push_mikrotik(client, db)
                except MikrotikError as e:
                    await q.edit_message_text(
                        f"⚠️ Plan cambiado en DB pero error Mikrotik: {e}"
                    )
                    return
            await q.edit_message_text(
                f"✅ *{client.full_name}* cambiado al plan *{plan.name}*.",
                parse_mode="Markdown",
            )

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("buscar", cmd_buscar))
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("planes", cmd_planes))
    app.add_handler(CommandHandler("cortar", cmd_cortar))
    app.add_handler(CommandHandler("activar", cmd_activar))
    app.add_handler(CommandHandler("plan", cmd_plan))
    app.add_handler(CallbackQueryHandler(on_callback))
    return app
