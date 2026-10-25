"""Seguridad → Configuración: Telegram, operating parameters, integration status."""
import os
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_admin
from app.models.config import SystemConfig
from app.services import runtime_config as rc

router = APIRouter()


class SettingsUpdate(BaseModel):
    # None = leave unchanged; "" = remove the panel value (falls back to .env)
    telegram_token: Optional[str] = Field(default=None, max_length=200)
    operator_chat_ids: Optional[List[int]] = None
    params: Optional[Dict[str, int]] = None

    @field_validator("params")
    @classmethod
    def _known_params(cls, v):
        if v is None:
            return v
        for key, value in v.items():
            if key not in rc.INT_PARAMS:
                raise ValueError(f"Parámetro desconocido: {key}")
            _, lo, hi = rc.INT_PARAMS[key]
            if not lo <= value <= hi:
                raise ValueError(f"{key} debe estar entre {lo} y {hi}")
        return v


def _hint(token: str) -> Optional[str]:
    return f"…{token[-4:]}" if token else None


async def _telegram_get_me(token: str) -> str:
    from telegram import Bot
    from telegram.error import InvalidToken, TelegramError
    try:
        async with Bot(token) as bot:
            me = await bot.get_me()
            return me.username
    except InvalidToken:
        raise HTTPException(status_code=422, detail="Telegram rechazó el token. Revisá que esté completo.")
    except TelegramError as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo validar el token con Telegram: {exc}")


async def _set(db: AsyncSession, key: str, value: Optional[str]) -> None:
    row = await db.get(SystemConfig, key)
    if value in (None, ""):
        if row:
            await db.delete(row)
    elif row:
        row.value = value
    else:
        db.add(SystemConfig(key=key, value=value))


async def _payload() -> dict:
    rc.invalidate_cache()
    token = await rc.telegram_token()
    push_file = settings.FCM_SERVICE_ACCOUNT_FILE
    return {
        "telegram": {
            "configured": bool(token),
            "token_hint": _hint(token),
            "token_source": await rc.telegram_token_source(),
            "operator_chat_ids": await rc.operator_chat_ids(),
            "operator_chat_ids_source": await rc.operator_chat_ids_source(),
        },
        "params": {key: await rc.int_param(key) for key in rc.INT_PARAMS},
        "param_limits": {key: {"default": d, "min": lo, "max": hi} for key, (d, lo, hi) in rc.INT_PARAMS.items()},
        "integrations": {
            "beat_adapter": os.getenv("BEAT_ADAPTER", "mock").lower(),
            "beat_mock_polling": os.getenv("BEAT_MOCK_POLLING") == "1",
            "push": "fcm" if push_file and os.path.isfile(push_file) else "simulado",
            "public_url": settings.PUBLIC_URL,
        },
    }


@router.get("/")
async def get_settings(_=Depends(get_current_user)):
    return await _payload()


@router.put("/")
async def update_settings(
    body: SettingsUpdate,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.core.security import encrypt_value

    rc.invalidate_cache()
    new_token = body.telegram_token.strip() if body.telegram_token is not None else None
    final_token = (new_token if new_token else settings.TELEGRAM_BOT_TOKEN) if new_token is not None else await rc.telegram_token()
    final_ids = body.operator_chat_ids if body.operator_chat_ids is not None else await rc.operator_chat_ids()

    # The bot accepts commands (e.g. suspending clients) only from these chats:
    # never allow a token without at least one authorized chat.
    if final_token and not final_ids:
        raise HTTPException(
            status_code=422,
            detail="Agregá al menos un ID de Telegram que reciba las alertas antes de guardar el token.",
        )

    if new_token:
        await _telegram_get_me(new_token)
    if new_token is not None:
        await _set(db, rc.TELEGRAM_TOKEN_KEY, encrypt_value(new_token) if new_token else None)
    if body.operator_chat_ids is not None:
        await _set(db, rc.TELEGRAM_CHAT_IDS_KEY, ",".join(str(i) for i in dict.fromkeys(body.operator_chat_ids)))
    for key, value in (body.params or {}).items():
        await _set(db, key, str(value))
    await db.commit()
    return await _payload()


@router.post("/telegram-test")
async def telegram_test(_=Depends(require_admin)):
    from telegram import Bot
    from telegram.error import TelegramError

    rc.invalidate_cache()
    token, chat_ids = await rc.telegram_token(), await rc.operator_chat_ids()
    if not token:
        raise HTTPException(status_code=422, detail="Todavía no hay un token de Telegram configurado.")
    if not chat_ids:
        raise HTTPException(status_code=422, detail="No hay IDs de Telegram que reciban las alertas.")

    username = await _telegram_get_me(token)
    results = []
    async with Bot(token) as bot:
        for chat_id in chat_ids:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="✅ Prueba de Guaynet Seguridad: este chat va a recibir las alertas de la central.",
                )
                results.append({"chat_id": chat_id, "ok": True})
            except TelegramError as exc:
                hint = " (¿le mandaste /start al bot?)" if "chat not found" in str(exc).lower() else ""
                results.append({"chat_id": chat_id, "ok": False, "error": f"{exc}{hint}"})
    return {"bot_username": username, "results": results}
