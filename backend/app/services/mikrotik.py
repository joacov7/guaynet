"""
Mikrotik RouterOS API service.
Wraps librouteros for Simple Queue management across RouterOS 6 and 7.
All methods are synchronous — call via asyncio.to_thread() from async endpoints.
"""
import socket
from typing import Any, Dict, List, Optional

import librouteros
from librouteros.exceptions import ConnectionClosed, FatalError


class MikrotikError(Exception):
    pass


class MikrotikService:
    def __init__(self, host: str, port: int, username: str, password: str, timeout: int = 10):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self._api = None

    def connect(self) -> "MikrotikService":
        try:
            self._api = librouteros.connect(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
            )
        except FatalError as e:
            raise MikrotikError(f"Autenticación fallida en {self.host}: {e}")
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            raise MikrotikError(f"No se pudo conectar a {self.host}:{self.port} — {e}")
        return self

    def disconnect(self) -> None:
        if self._api:
            try:
                self._api.close()
            except Exception:
                pass
            self._api = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.disconnect()

    def _call(self, cmd: str, **params) -> List[Dict]:
        if not self._api:
            raise MikrotikError("No hay conexión activa")
        try:
            return list(self._api(cmd, **params))
        except ConnectionClosed as e:
            raise MikrotikError(f"Conexión cerrada: {e}")
        except FatalError as e:
            raise MikrotikError(f"Error de API: {e}")

    def get_system_info(self) -> Dict[str, Any]:
        identity = self._call("/system/identity/print")
        resource = self._call("/system/resource/print")
        r = resource[0] if resource else {}
        return {
            "identity": identity[0].get("name", "") if identity else "",
            "version": r.get("version", ""),
            "uptime": r.get("uptime", ""),
            "cpu_load": r.get("cpu-load", "0"),
            "free_memory": r.get("free-memory", "0"),
            "total_memory": r.get("total-memory", "0"),
            "board_name": r.get("board-name", ""),
        }

    def get_simple_queues(self) -> List[Dict]:
        raw = self._call("/queue/simple/print")
        queues = []
        for q in raw:
            queues.append({
                "id": q.get(".id", ""),
                "name": q.get("name", ""),
                "target": q.get("target", ""),
                "max_limit": q.get("max-limit", ""),
                "burst_limit": q.get("burst-limit", ""),
                "burst_threshold": q.get("burst-threshold", ""),
                "burst_time": q.get("burst-time", ""),
                "disabled": q.get("disabled", "false") in ("true", "yes"),
                "comment": q.get("comment", ""),
                "bytes": q.get("bytes", ""),
                "packets": q.get("packets", ""),
            })
        return queues

    def get_queue_by_name(self, name: str) -> Optional[Dict]:
        queues = self.get_simple_queues()
        return next((q for q in queues if q["name"] == name), None)

    def add_simple_queue(
        self,
        name: str,
        target: str,
        max_limit: str,
        burst_limit: Optional[str] = None,
        burst_threshold: Optional[str] = None,
        burst_time: Optional[str] = None,
        comment: str = "",
        disabled: bool = False,
    ) -> None:
        params: Dict[str, str] = {
            "name": name,
            "target": target,
            "max-limit": max_limit,
            "disabled": "yes" if disabled else "no",
        }
        if burst_limit:
            params["burst-limit"] = burst_limit
        if burst_threshold:
            params["burst-threshold"] = burst_threshold
        if burst_time:
            params["burst-time"] = burst_time
        if comment:
            params["comment"] = comment
        self._call("/queue/simple/add", **params)

    def update_simple_queue(
        self,
        queue_id: str,
        max_limit: Optional[str] = None,
        burst_limit: Optional[str] = None,
        burst_threshold: Optional[str] = None,
        burst_time: Optional[str] = None,
        disabled: Optional[bool] = None,
        comment: Optional[str] = None,
    ) -> None:
        params: Dict[str, str] = {".id": queue_id}
        if max_limit is not None:
            params["max-limit"] = max_limit
        if burst_limit is not None:
            params["burst-limit"] = burst_limit
        if burst_threshold is not None:
            params["burst-threshold"] = burst_threshold
        if burst_time is not None:
            params["burst-time"] = burst_time
        if disabled is not None:
            params["disabled"] = "yes" if disabled else "no"
        if comment is not None:
            params["comment"] = comment
        self._call("/queue/simple/set", **params)

    def disable_queue(self, queue_id: str) -> None:
        self._call("/queue/simple/set", **{".id": queue_id, "disabled": "yes"})

    def enable_queue(self, queue_id: str) -> None:
        self._call("/queue/simple/set", **{".id": queue_id, "disabled": "no"})

    def remove_queue(self, queue_id: str) -> None:
        self._call("/queue/simple/remove", **{".id": queue_id})

    def get_dhcp_leases(self) -> List[Dict]:
        return self._call("/ip/dhcp-server/lease/print")

    def add_dhcp_static_lease(self, ip: str, mac: str, comment: str = "") -> None:
        params = {"address": ip, "mac-address": mac, "server": "all"}
        if comment:
            params["comment"] = comment
        self._call("/ip/dhcp-server/lease/add", **params)

    def get_arp_table(self) -> List[Dict]:
        return self._call("/ip/arp/print")

    def get_interfaces(self) -> List[Dict]:
        return self._call("/interface/print")


def build_service_from_router(router) -> MikrotikService:
    """Build a MikrotikService from a MikrotikRouter ORM model."""
    from app.core.security import decrypt_value

    password = decrypt_value(router.password_encrypted)
    return MikrotikService(
        host=router.host,
        port=router.port,
        username=router.username,
        password=password,
    )
