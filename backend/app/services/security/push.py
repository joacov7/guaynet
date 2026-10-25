"""
Mobile push notifications (Android app).

PushProvider is the interface; two adapters:
- FcmPushProvider: Firebase Cloud Messaging HTTP v1 API, authenticated with a
  service account (OAuth2 JWT-bearer flow). Used when FCM_SERVICE_ACCOUNT_FILE is set.
- MockPushProvider: SIMULATED adapter. Only logs what would be sent. Used when
  Firebase is not configured, so the rest of the system works without it.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ALARM_CHANNEL = "alarmas"  # must match the channel created by the Android app


@dataclass
class PushMessage:
    title: str
    body: str
    data: Dict[str, str] = field(default_factory=dict)
    urgent: bool = False


class PushInvalidToken(Exception):
    """The device token is no longer valid (app uninstalled / token rotated)."""


class PushProvider(Protocol):
    name: str

    async def send(self, token: str, message: PushMessage) -> None: ...


class MockPushProvider:
    """SIMULATED push adapter — nothing leaves the server."""
    name = "mock"

    async def send(self, token: str, message: PushMessage) -> None:
        logger.info(
            "[PUSH SIMULADO] token=%s… title=%r urgent=%s data=%s",
            token[:12], message.title, message.urgent, message.data,
        )


class FcmPushProvider:
    name = "fcm"
    _SCOPE = "https://www.googleapis.com/auth/firebase.messaging"

    def __init__(self, service_account_file: str):
        with open(service_account_file, encoding="utf-8") as f:
            sa = json.load(f)
        self._client_email: str = sa["client_email"]
        self._private_key: str = sa["private_key"]
        self._token_uri: str = sa.get("token_uri", "https://oauth2.googleapis.com/token")
        self._project_id: str = sa["project_id"]
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token
        from jose import jwt

        now = int(time.time())
        assertion = jwt.encode(
            {
                "iss": self._client_email,
                "scope": self._SCOPE,
                "aud": self._token_uri,
                "iat": now,
                "exp": now + 3600,
            },
            self._private_key,
            algorithm="RS256",
        )
        r = await client.post(
            self._token_uri,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        )
        r.raise_for_status()
        payload = r.json()
        self._access_token = payload["access_token"]
        self._expires_at = time.time() + int(payload.get("expires_in", 3600))
        return self._access_token

    async def send(self, token: str, message: PushMessage) -> None:
        body = {
            "message": {
                "token": token,
                "notification": {"title": message.title, "body": message.body},
                "data": message.data,
                "android": {
                    "priority": "HIGH" if message.urgent else "NORMAL",
                    "notification": {
                        "channel_id": ALARM_CHANNEL if message.urgent else "general",
                    },
                },
            }
        }
        async with httpx.AsyncClient(timeout=10) as client:
            access = await self._get_access_token(client)
            r = await client.post(
                f"https://fcm.googleapis.com/v1/projects/{self._project_id}/messages:send",
                json=body,
                headers={"Authorization": f"Bearer {access}"},
            )
        if r.status_code in (400, 404):
            text = r.text
            if "UNREGISTERED" in text or "registration token is not a valid" in text.lower():
                raise PushInvalidToken(text[:200])
        r.raise_for_status()


_provider: Optional[PushProvider] = None


def get_push_provider() -> PushProvider:
    global _provider
    if _provider is None:
        path = settings.FCM_SERVICE_ACCOUNT_FILE
        if path:
            try:
                _provider = FcmPushProvider(path)
            except Exception as exc:
                logger.error("FCM misconfigured (%s); falling back to SIMULATED push", exc)
                _provider = MockPushProvider()
        else:
            _provider = MockPushProvider()
    return _provider
