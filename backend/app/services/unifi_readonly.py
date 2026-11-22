"""Read-only client for UniFi Network Application's legacy controller API.

Only GET requests are exposed. No configuration or mutation methods are implemented.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx


class UniFiControllerError(Exception):
    pass


def _validate_controller_url(base_url: str) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    if parsed.scheme != "https":
        raise UniFiControllerError("El controlador UniFi debe utilizar HTTPS")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UniFiControllerError("URL del controlador inválida")
    if parsed.port not in (None, 443, 8443):
        raise UniFiControllerError("Puerto del controlador no permitido")
    return base_url.rstrip("/")


async def _ensure_safe_destination(base_url: str) -> None:
    """Restrict controller connections to private network addresses (anti-SSRF)."""
    parsed = urlparse(base_url)
    host = parsed.hostname
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            records = await asyncio.get_running_loop().getaddrinfo(
                host, parsed.port or 443, type=socket.SOCK_STREAM
            )
        except OSError as exc:
            raise UniFiControllerError("No se pudo resolver el host del controlador") from exc
        addresses = list({ipaddress.ip_address(record[4][0]) for record in records})

    if not addresses or any(
        not (address.is_private and not address.is_loopback and not address.is_link_local
             and not address.is_multicast and not address.is_reserved)
        for address in addresses
    ):
        raise UniFiControllerError(
            "Por seguridad, el controlador debe resolver a una dirección IP privada de la red"
        )


class UniFiReadOnlyClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_tls: bool = True,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = _validate_controller_url(base_url)
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.timeout = timeout

    async def _request(self, client: httpx.AsyncClient, method: str, path: str) -> Any:
        response = await client.request(method, f"{self.base_url}{path}")
        if response.status_code in (401, 403):
            raise UniFiControllerError("Autenticación rechazada por el controlador UniFi")
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise UniFiControllerError("El controlador devolvió una respuesta no válida") from exc
        if isinstance(payload, dict) and payload.get("meta", {}).get("rc") == "error":
            raise UniFiControllerError("El controlador UniFi informó un error en la consulta")
        return payload

    async def _session(self) -> httpx.AsyncClient:
        await _ensure_safe_destination(self.base_url)
        client = httpx.AsyncClient(
            verify=self.verify_tls,
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=False,
        )
        try:
            response = await client.post(
                f"{self.base_url}/api/login",
                json={"username": self.username, "password": self.password},
            )
            if response.status_code in (401, 403):
                raise UniFiControllerError("Usuario o contraseña rechazados por UniFi")
            response.raise_for_status()
            return client
        except (httpx.HTTPError, UniFiControllerError) as exc:
            await client.aclose()
            if isinstance(exc, UniFiControllerError):
                raise
            raise UniFiControllerError("No se pudo establecer sesión con el controlador UniFi") from exc

    async def get_sites(self) -> list[dict[str, Any]]:
        client = await self._session()
        try:
            payload = await self._request(client, "GET", "/api/self/sites")
            data = payload.get("data", []) if isinstance(payload, dict) else []
            return data if isinstance(data, list) else []
        except httpx.HTTPError as exc:
            raise UniFiControllerError("No se pudieron consultar los sitios UniFi") from exc
        finally:
            await client.aclose()

    async def get_devices(self, site_name: str = "default") -> list[dict[str, Any]]:
        if not site_name or "/" in site_name or ".." in site_name:
            raise UniFiControllerError("Nombre de sitio inválido")
        client = await self._session()
        try:
            payload = await self._request(
                client, "GET", f"/api/s/{site_name}/stat/device"
            )
            data = payload.get("data", []) if isinstance(payload, dict) else []
            return data if isinstance(data, list) else []
        except httpx.HTTPError as exc:
            raise UniFiControllerError("No se pudieron consultar los dispositivos UniFi") from exc
        finally:
            await client.aclose()
