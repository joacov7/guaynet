"""
Telegram linking for security clients (titular and property members).

The operator or the client generates a one-time link https://t.me/<bot>?start=<code>;
opening it in Telegram sends "/start <code>" to the bot, which binds that chat.
Who receives what:
  - titular (SecuritySubscription.client_telegram_id): alerts, "¿Estás bien?", commands.
  - members (PropertyMember.telegram_chat_id): alerts if notify_on_alarm, entry notices
    if notify_on_entry, and the client bot commands for their property.
"""
import hashlib
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.security.member import PropertyMember
from app.models.security.property import Property
from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus
from app.models.security.telegram_link import SecurityTelegramLink

logger = logging.getLogger(__name__)

LINK_TTL = timedelta(hours=48)
_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_bot_username_cache: dict = {}


class LinkError(Exception):
    """User-facing reason why a link code could not be used."""


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def bot_username() -> str:
    from app.services.runtime_config import telegram_token
    token = await telegram_token()
    if not token:
        raise HTTPException(
            status_code=422,
            detail="Telegram todavía no está configurado (Seguridad → Configuración).",
        )
    if token not in _bot_username_cache:
        from telegram import Bot
        from telegram.error import TelegramError
        try:
            async with Bot(token) as bot:
                _bot_username_cache.clear()
                _bot_username_cache[token] = (await bot.get_me()).username
        except TelegramError as exc:
            raise HTTPException(status_code=502, detail=f"No se pudo consultar el bot de Telegram: {exc}")
    return _bot_username_cache[token]


async def create_link(db: AsyncSession, subscription_id: int, member_id: Optional[int] = None) -> dict:
    sub = await db.get(SecuritySubscription, subscription_id)
    if sub is None or sub.status == SecuritySubscriptionStatus.cancelled:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    if member_id is not None:
        member = await db.get(PropertyMember, member_id)
        if member is None or member.property_id != sub.property_id or member.status != "active":
            raise HTTPException(status_code=404, detail="Miembro no encontrado")

    username = await bot_username()

    # A new link replaces any unused one for the same person
    await db.execute(
        delete(SecurityTelegramLink).where(
            SecurityTelegramLink.subscription_id == subscription_id,
            SecurityTelegramLink.member_id.is_(None) if member_id is None else SecurityTelegramLink.member_id == member_id,
            SecurityTelegramLink.used_at.is_(None),
        )
    )
    code = secrets.token_urlsafe(24)
    expires = datetime.now(timezone.utc) + LINK_TTL
    db.add(SecurityTelegramLink(
        code_hash=_hash(code), subscription_id=subscription_id, member_id=member_id, expires_at=expires,
    ))
    await db.commit()
    return {"url": f"https://t.me/{username}?start={code}", "expires_at": expires.isoformat()}


async def consume_link(db: AsyncSession, code: str, chat_id: int) -> str:
    """Bind chat_id using a link code. Returns the property name; raises LinkError."""
    invalid = LinkError("El enlace no es válido o ya venció. Pedí uno nuevo.")
    if not _CODE_RE.match(code or ""):
        raise invalid
    link = (await db.execute(
        select(SecurityTelegramLink)
        .where(SecurityTelegramLink.code_hash == _hash(code))
        .with_for_update()
    )).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if link is None or link.used_at is not None or _aware(link.expires_at) <= now:
        raise invalid

    sub = await db.get(SecuritySubscription, link.subscription_id)
    if sub is None or sub.status == SecuritySubscriptionStatus.cancelled:
        raise invalid
    if link.member_id is not None:
        member = await db.get(PropertyMember, link.member_id)
        if member is None or member.status != "active":
            raise invalid
        member.telegram_chat_id = str(chat_id)
        member.telegram_linked_at = now
    else:
        sub.client_telegram_id = str(chat_id)

    link.used_at = now
    link.used_by_chat_id = str(chat_id)
    prop = await db.get(Property, sub.property_id)
    await db.commit()
    return prop.name if prop else f"Suscripción #{sub.id}"


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class ChatLink:
    sub: SecuritySubscription
    property_name: str
    is_owner: bool                      # titular, or a member with role "owner"
    member: Optional[PropertyMember]    # None when linked as titular


async def chat_links(db: AsyncSession, chat_id: int) -> List[ChatLink]:
    """Active subscriptions this chat may use, titular links first."""
    chat = str(chat_id)
    out: dict[int, ChatLink] = {}

    owned = (await db.execute(
        select(SecuritySubscription)
        .options(selectinload(SecuritySubscription.features), selectinload(SecuritySubscription.plan))
        .where(
            SecuritySubscription.client_telegram_id == chat,
            SecuritySubscription.status == SecuritySubscriptionStatus.active,
        )
    )).scalars().all()
    for sub in owned:
        out[sub.id] = ChatLink(sub, "", True, None)

    members = (await db.execute(
        select(PropertyMember).where(
            PropertyMember.telegram_chat_id == chat,
            PropertyMember.status == "active",
        )
    )).scalars().all()
    for m in members:
        subs = (await db.execute(
            select(SecuritySubscription)
            .options(selectinload(SecuritySubscription.features), selectinload(SecuritySubscription.plan))
            .where(
                SecuritySubscription.property_id == m.property_id,
                SecuritySubscription.status == SecuritySubscriptionStatus.active,
            )
        )).scalars().all()
        for sub in subs:
            out.setdefault(sub.id, ChatLink(sub, "", m.role.value == "owner", m))

    for link in out.values():
        prop = await db.get(Property, link.sub.property_id)
        link.property_name = prop.name if prop else f"Suscripción #{link.sub.id}"
    return sorted(out.values(), key=lambda l: (not l.is_owner, l.property_name))


async def family_chat_ids(db: AsyncSession, sub: SecuritySubscription, kind: str = "alarm") -> List[str]:
    """
    Linked member chats that want this kind of notice ("alarm" or "entry"),
    excluding the titular's chat (it is notified on its own channel).
    """
    flag = PropertyMember.notify_on_alarm if kind == "alarm" else PropertyMember.notify_on_entry
    rows = (await db.execute(
        select(PropertyMember.telegram_chat_id).where(
            PropertyMember.property_id == sub.property_id,
            PropertyMember.status == "active",
            PropertyMember.telegram_chat_id.is_not(None),
            flag.is_(True),
        )
    )).scalars().all()
    owner = (sub.client_telegram_id or "").strip()
    return [c for c in dict.fromkeys(rows) if c and c != owner]


async def unlink_chat(db: AsyncSession, chat_id: int) -> int:
    """Remove every link of this chat (titular and member). Returns how many."""
    chat = str(chat_id)
    r1 = await db.execute(
        update(SecuritySubscription)
        .where(SecuritySubscription.client_telegram_id == chat)
        .values(client_telegram_id=None)
    )
    r2 = await db.execute(
        update(PropertyMember)
        .where(PropertyMember.telegram_chat_id == chat)
        .values(telegram_chat_id=None, telegram_linked_at=None)
    )
    await db.commit()
    return (r1.rowcount or 0) + (r2.rowcount or 0)


async def unlink_member(db: AsyncSession, member_id: int) -> PropertyMember:
    member = await db.get(PropertyMember, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    member.telegram_chat_id = None
    member.telegram_linked_at = None
    await db.commit()
    await db.refresh(member)
    return member
