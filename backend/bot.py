import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# httpx logs every request URL at INFO, and Telegram URLs contain the bot token
logging.getLogger("httpx").setLevel(logging.WARNING)

from app.core.config import settings  # noqa: E402
from app.services import runtime_config  # noqa: E402
from app.services.telegram_bot import build_application  # noqa: E402

CHECK_SECONDS = 30
log = logging.getLogger("guaynet.bot")


async def _current():
    runtime_config.invalidate_cache()
    return await runtime_config.telegram_token(), await runtime_config.operator_chat_ids()


async def main() -> None:
    """
    Run the bot with the token/chats configured in Seguridad → Configuración
    (or .env). Waits while there is no token, and restarts by itself when the
    token or the authorized chats change, so no container restart is needed.
    """
    warned = False
    while True:
        token, chat_ids = await _current()
        if not token:
            if not warned:
                log.warning("Sin token de Telegram: esperando que se configure en Seguridad → Configuración.")
                warned = True
            await asyncio.sleep(CHECK_SECONDS)
            continue
        warned = False
        if not chat_ids:
            log.warning("Sin chats autorizados: el bot no aceptará comandos de nadie.")

        app = build_application(token=token, database_url=settings.DATABASE_URL, allowed_ids=chat_ids)
        try:
            async with app:
                await app.start()
                await app.updater.start_polling(drop_pending_updates=True)
                log.info("Guaynet Bot iniciado.")
                while True:
                    await asyncio.sleep(CHECK_SECONDS)
                    if await _current() != (token, chat_ids):
                        log.info("Cambió la configuración de Telegram: reiniciando el bot.")
                        break
                await app.updater.stop()
                await app.stop()
        except Exception as exc:
            # Invalid token, network down, etc.: retry later instead of crash-looping
            # The library's InvalidToken message includes the token itself
            log.error("El bot se detuvo: %s. Reintento en %ss.", str(exc).replace(token, "***"), CHECK_SECONDS)
            await asyncio.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
