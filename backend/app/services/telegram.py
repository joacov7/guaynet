"""
Shared Telegram alert utility.
Called from any endpoint or task; silently ignores missing config.
"""
from app.core.config import settings


async def send_telegram(text: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.telegram_allowed_ids_list:
        return
    try:
        from telegram import Bot
        async with Bot(settings.TELEGRAM_BOT_TOKEN) as bot:
            for chat_id in settings.telegram_allowed_ids_list:
                try:
                    await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                except Exception:
                    pass
    except Exception:
        pass


async def send_telegram_to(chat_id: str, text: str) -> None:
    """Send a message to a specific Telegram chat ID (e.g. a client's personal chat)."""
    if not settings.TELEGRAM_BOT_TOKEN or not chat_id:
        return
    try:
        from telegram import Bot
        async with Bot(settings.TELEGRAM_BOT_TOKEN) as bot:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception:
        pass
