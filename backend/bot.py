import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from app.core.config import settings  # noqa: E402
from app.services.telegram_bot import build_application  # noqa: E402

if not settings.TELEGRAM_BOT_TOKEN:
    logging.error("TELEGRAM_BOT_TOKEN no configurado. Saliendo.")
    sys.exit(0)

app = build_application(
    token=settings.TELEGRAM_BOT_TOKEN,
    database_url=settings.DATABASE_URL,
    allowed_ids=settings.telegram_allowed_ids_list,
)

if __name__ == "__main__":
    logging.info("Iniciando Guaynet Bot...")
    app.run_polling(drop_pending_updates=True)
