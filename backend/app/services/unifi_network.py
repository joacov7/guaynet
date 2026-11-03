"""Read-only UniFi Network controller adapter.

Supports UniFi OS and legacy self-hosted Network Application login flows.
Only performs authentication and GET requests; it never changes controller state.
"""
import ipaddress
from urllib.parse import urlparse

import httpx


class UniFiError(Exception):
    """Safe, user-facing UniFi integration error."""


def _validated_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        raise UniFiError("Por seguridad, la conexión UniFi requiere HTTPS.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UniFiError("La URL del controlador no es válida.")
    # Controllers are expected on the private management LAN. Avoid arbitrary
    # public destinations and DNS-based SSRF in this first implementation.
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        raise UniFiError("En esta versión inicial, usá la IP privada del controlador, no un nombre DNS.")
    if address.version != 4 or not address.is_private or address.is_loopback or address.is_link_local:
        raise UniFiError("El controlador debe tener una dirección IPv4 privada de la red de administración.")
    return base_url.rstrip("/")


class UniFiNetworkService:
    def __init__(self, base_url: str, username: str, password: str, verify_tls: bool = True, timeout: float = 10.0):
        self.base_url = _validated_base_url(base_url)
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.timeout = timeout

    def test_connection(self) -> dict:
        """Authenticate and read the site list. No configuration writes."""
        with httpx.Client(
            base_url=self.base_url,
            verify=self.verify_tls,
            timeout=self.timeout,
            follow_redirects=False,
            headers={"Accept": "application/json"},
        ) as client:
            authenticated = False
            # UniFi OS and legacy Network Application use different login paths.
            for path in ("/api/auth/login", "/api/login"):
                try:
                    response = client.post(
                        path,
                        json={"username": self.username, "password": self.password, "rememberMe": True},
                    )
                except httpx.RequestError:
                    raise UniFiError("No se pudo establecer conexión HTTPS con el controlador.")
                if response.status_code in (200, 201) and response.headers.get("content-type", "").startswith("application/json"):
                    payload = response.json()
                    if payload.get("meta", {}).get("rc") == "ok" or payload.get("code") == "AUTHENTICATION_SUCCESS":
                        authenticated = True
                        break
                    # Some versions return a successful HTTP status with a token/cookie.
                    if client.cookies:
                        authenticated = True
                        break
                if response.status_code == 404:
                    continue
                if response.status_code in (401, 403):
                    continue
            if not authenticated:
                raise UniFiError("El controlador rechazó el inicio de sesión o no reconoce la API compatible.")

            site_paths = (
                "/proxy/network/api/self/sites",
                "/api/self/sites",
            )
            sites = None
            for path in site_paths:
                try:
                    response = client.get(path)
                except httpx.RequestError:
                    raise UniFiError("Se autenticó, pero no se pudo consultar la lista de sitios.")
                if response.status_code == 404:
                    continue
                if response.status_code in (401, 403):
                    raise UniFiError("La sesión se autenticó, pero no tiene permiso para consultar sitios.")
                if response.is_success:
                    try:
                        payload = response.json()
                    except ValueError:
                        raise UniFiError("El controlador devolvió una respuesta no válida al consultar sitios.")
                    sites = payload.get("data", []) if isinstance(payload, dict) else []
                    break
            if sites is None:
                raise UniFiError("No se encontró un endpoint de sitios compatible en este controlador.")
            return {
                "connected": True,
                "sites_count": len(sites),
                "sites": [
                    {"name": item.get("name") or item.get("desc") or item.get("siteName") or "sin_nombre",
                     "site_id": item.get("_id") or item.get("id")}
                    for item in sites if isinstance(item, dict)
                ],
            }
