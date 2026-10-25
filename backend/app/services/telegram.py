"""
Shared Telegram alert utility.
Called from any endpoint or task; silently ignores missing config.
Token and operator chats come from the admin panel (runtime_config), with the
environment as fallback.
"""
import logging

from app.services.runtime_config import operator_chat_ids, telegram_token

# httpx logs request URLs (DEBUG/INFO), and Telegram URLs contain the bot token
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def send_telegram(text: str) -> None:
    token, chat_ids = await telegram_token(), await operator_chat_ids()
    if not token or not chat_ids:
        return
    try:
        from telegram import Bot
        async with Bot(token) as bot:
            for chat_id in chat_ids:
                try:
                    await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                except Exception:
                    pass
    except Exception:
        pass


async def send_telegram_to(chat_id: str, text: str) -> None:
    """Send a message to a specific Telegram chat ID (e.g. a client's personal chat)."""
    token = await telegram_token()
    if not token or not chat_id:
        return
    try:
        from telegram import Bot
        async with Bot(token) as bot:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception:
        pass


async def send_telegram_document(
    chat_id: str,
    file_path: str,
    caption: str = "",
) -> None:
    """Send a local file as a Telegram document to a specific chat."""
    token = await telegram_token()
    if not token or not chat_id:
        return
    try:
        from telegram import Bot
        async with Bot(token) as bot:
            with open(file_path, "rb") as f:
                await bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    caption=caption,
                    parse_mode="Markdown",
                )
    except Exception:
        pass


async def send_telegram_confirmation(
    chat_id: str,
    text: str,
    alert_id: int,
) -> int | None:
    """
    Send a message with ¿Estás bien? inline keyboard to a specific chat.
    Returns the Telegram message_id so it can be edited later, or None on failure.
    Callback data format: sec_safe:{alert_id} / sec_help:{alert_id}
    """
    token = await telegram_token()
    if not token or not chat_id:
        return None
    try:
        from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Estoy bien", callback_data=f"sec_safe:{alert_id}"),
            InlineKeyboardButton("🆘 Necesito ayuda", callback_data=f"sec_help:{alert_id}"),
        ]])
        async with Bot(token) as bot:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=kb,
            )
            return msg.message_id
    except Exception:
        return None
