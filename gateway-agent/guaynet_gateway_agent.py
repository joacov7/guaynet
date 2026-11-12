"""Guaynet Smart local Home Assistant gateway agent.

The agent only makes outbound connections: Home Assistant on the local network
and the configured Guaynet HTTPS API. It never exposes a local HTTP listener.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import uuid
from datetime import datetime, timezone
from typing import Any

import aiohttp

LOG = logging.getLogger("guaynet_gateway")
HA_TIMEOUT = aiohttp.ClientTimeout(total=20)
API_TIMEOUT = aiohttp.ClientTimeout(total=30)


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Falta la variable obligatoria {name}")
    return value


def iso_datetime(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def safe_attributes(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    # HA attributes can contain nested structures; JSON round-trip also
    # guarantees the payload is serializable before sending it to the API.
    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
        decoded = json.loads(encoded)
        return decoded if isinstance(decoded, dict) else {}
    except (TypeError, ValueError):
        return {}


class HomeAssistantClient:
    def __init__(self, url: str, token: str, session: aiohttp.ClientSession):
        self.base = url.rstrip("/")
        self.token = token
        self.session = session

    async def rest(self, path: str) -> Any:
        async with self.session.get(
            f"{self.base}/api/{path.lstrip('/')}",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=HA_TIMEOUT,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def websocket_command(self, ws: aiohttp.ClientWebSocketResponse, command_id: int,
                                command_type: str) -> Any:
        await ws.send_json({"id": command_id, "type": command_type})
        while True:
            message = await ws.receive_json(timeout=HA_TIMEOUT.total)
            if message.get("id") != command_id:
                continue
            if not message.get("success"):
                raise RuntimeError(f"Home Assistant rechazó {command_type}")
            return message.get("result")

    async def registries(self) -> tuple[list[dict], list[dict]]:
        ws_url = self.base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
        async with self.session.ws_connect(
            f"{ws_url}/api/websocket", heartbeat=30, timeout=HA_TIMEOUT
        ) as ws:
            hello = await ws.receive_json(timeout=HA_TIMEOUT.total)
            if hello.get("type") != "auth_required":
                raise RuntimeError("Respuesta WebSocket inesperada de Home Assistant")
            await ws.send_json({"type": "auth", "access_token": self.token})
            auth = await ws.receive_json(timeout=HA_TIMEOUT.total)
            if auth.get("type") != "auth_ok":
                raise RuntimeError("Autenticación WebSocket de Home Assistant fallida")
            devices = await self.websocket_command(ws, 1, "config/device_registry/list")
            entities = await self.websocket_command(ws, 2, "config/entity_registry/list")
            areas = await self.websocket_command(ws, 3, "config/area_registry/list")
            return devices or [], entities or [], areas or []

    async def inventory(self) -> tuple[list[dict], list[dict]]:
        states = await self.rest("states")
        devices, entity_registry, areas = await self.registries()
        area_names = {item.get("area_id"): item.get("name") for item in areas or []}
        device_map: dict[str, dict] = {}
        for item in devices:
            external_id = str(item.get("id", "")).strip()
            if not external_id:
                continue
            device_map[external_id] = {
                "external_device_id": external_id,
                "name": (item.get("name_by_user") or item.get("name") or external_id)[:160],
                "manufacturer": item.get("manufacturer"),
                "model": item.get("model"),
                "software_version": item.get("sw_version"),
                "area_name": area_names.get(item.get("area_id")),
                "device_class": item.get("entry_type"),
                "availability": "unknown",
                "attributes": {
                    "identifiers": item.get("identifiers", []),
                    "connections": item.get("connections", []),
                    "configuration_url": item.get("configuration_url"),
                },
            }

        registry_by_entity = {
            item.get("entity_id"): item
            for item in entity_registry
            if item.get("entity_id")
        }
        entities: list[dict] = []
        for state in states:
            entity_id = state.get("entity_id")
            if not isinstance(entity_id, str) or "." not in entity_id:
                continue
            domain = entity_id.split(".", 1)[0]
            attributes = safe_attributes(state.get("attributes"))
            registry = registry_by_entity.get(entity_id, {})
            external_device_id = registry.get("device_id")
            if external_device_id and external_device_id not in device_map:
                external_device_id = None
            raw_state = state.get("state")
            availability = "unavailable" if raw_state == "unavailable" else (
                "unknown" if raw_state in (None, "unknown") else "available"
            )
            entities.append({
                "external_entity_id": entity_id,
                "external_device_id": external_device_id,
                "domain": domain[:60],
                "entity_type": attributes.get("device_class"),
                "name": (registry.get("name") or registry.get("original_name")
                         or attributes.get("friendly_name") or entity_id)[:160],
                "state": str(raw_state)[:500] if raw_state is not None else None,
                "availability": availability,
                "attributes": attributes,
                "last_changed_at": iso_datetime(state.get("last_changed")),
                "last_reported_at": iso_datetime(state.get("last_reported")
                                                   or state.get("last_updated")),
            })

        if len(device_map) > 500 or len(entities) > 2000:
            raise RuntimeError(
                "El inventario supera los límites actuales de Guaynet "
                "(500 dispositivos / 2000 entidades); no se enviaron datos."
            )
        # Devices not currently reporting an entity remain in the registry.
        return list(device_map.values()), entities


class GuaynetClient:
    def __init__(self, base_url: str, token: str, session: aiohttp.ClientSession):
        self.base = base_url.rstrip("/")
        self.token = token
        self.session = session
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def post(self, path: str, payload: dict) -> dict:
        async with self.session.post(
            f"{self.base}/smart/gateway/{path}",
            json=payload,
            headers=self.headers,
            timeout=API_TIMEOUT,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def heartbeat(self, external_id: str, version: str) -> None:
        await self.post("heartbeat", {
            "external_gateway_id": external_id,
            "software_version": version,
            "capabilities": {
                "inventory_sync": True,
                "home_assistant_rest": True,
                "home_assistant_websocket_registry": True,
            },
        })

    async def sync_inventory(self, devices: list[dict], entities: list[dict]) -> dict:
        return await self.put_inventory({"devices": devices, "entities": entities})

    async def put_inventory(self, payload: dict) -> dict:
        async with self.session.put(
            f"{self.base}/smart/gateway/inventory",
            json=payload,
            headers=self.headers,
            timeout=API_TIMEOUT,
        ) as response:
            response.raise_for_status()
            return await response.json()


async def run() -> None:
    ha_url = required_env("HA_URL")
    ha_token = required_env("HA_TOKEN")
    api_url = required_env("GUAYNET_API_BASE_URL")
    api_token = required_env("GUAYNET_GATEWAY_TOKEN")
    external_id = os.getenv("GATEWAY_EXTERNAL_ID", "").strip() or str(uuid.uuid4())
    interval = max(30, int(os.getenv("SYNC_INTERVAL_SECONDS", "300")))
    version = "0.1.0"

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        ha = HomeAssistantClient(ha_url, ha_token, session)
        guaynet = GuaynetClient(api_url, api_token, session)
        wake = asyncio.Event()

        async def sync_once() -> None:
            await guaynet.heartbeat(external_id, version)
            devices, entities = await ha.inventory()
            result = await guaynet.sync_inventory(devices, entities)
            LOG.info(
                "Inventario sincronizado: %s dispositivos, %s entidades",
                result.get("devices_received", len(devices)),
                result.get("entities_received", len(entities)),
            )

        async def periodic_sync() -> None:
            while not stop.is_set():
                try:
                    await sync_once()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    # Never log request headers, tokens, or response bodies.
                    LOG.warning("Sincronización fallida (%s)", type(exc).__name__)
                try:
                    await asyncio.wait_for(wake.wait(), timeout=interval)
                    wake.clear()
                    # Coalesce bursts of state_changed events into one inventory snapshot.
                    await asyncio.sleep(3)
                    wake.clear()
                except asyncio.TimeoutError:
                    pass

        async def watch_ha_events() -> None:
            ws_url = ha.base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
            while not stop.is_set():
                try:
                    async with session.ws_connect(
                        f"{ws_url}/api/websocket", heartbeat=30, timeout=HA_TIMEOUT
                    ) as ws:
                        hello = await ws.receive_json(timeout=HA_TIMEOUT.total)
                        if hello.get("type") != "auth_required":
                            raise RuntimeError("WebSocket HA inesperado")
                        await ws.send_json({"type": "auth", "access_token": ha.token})
                        auth = await ws.receive_json(timeout=HA_TIMEOUT.total)
                        if auth.get("type") != "auth_ok":
                            raise RuntimeError("Autenticación HA fallida")
                        await ws.send_json({
                            "id": 10, "type": "subscribe_events", "event_type": "state_changed"
                        })
                        ack = await ws.receive_json(timeout=HA_TIMEOUT.total)
                        if not ack.get("success"):
                            raise RuntimeError("No se pudo suscribir a state_changed")
                        LOG.info("Conectado a eventos locales de Home Assistant")
                        async for message in ws:
                            if message.type == aiohttp.WSMsgType.TEXT:
                                data = message.json()
                                if data.get("type") == "event":
                                    wake.set()
                            elif message.type in (aiohttp.WSMsgType.CLOSED,
                                                  aiohttp.WSMsgType.ERROR):
                                break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    LOG.warning("WebSocket HA desconectado (%s)", type(exc).__name__)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=10)
                except asyncio.TimeoutError:
                    pass

        tasks = [
            asyncio.create_task(periodic_sync(), name="periodic-sync"),
            asyncio.create_task(watch_ha_events(), name="ha-events"),
        ]
        await stop.wait()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
