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

    # ── Connection ────────────────────────────────────────────────────────────

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

    # ── System info ───────────────────────────────────────────────────────────

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

    # ── Simple Queues ─────────────────────────────────────────────────────────

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

    # ── DHCP ──────────────────────────────────────────────────────────────────

    def get_dhcp_leases(self) -> List[Dict]:
        return self._call("/ip/dhcp-server/lease/print")

    def add_dhcp_static_lease(self, ip: str, mac: str, comment: str = "") -> None:
        params = {"address": ip, "mac-address": mac, "server": "all"}
        if comment:
            params["comment"] = comment
        self._call("/ip/dhcp-server/lease/add", **params)

    # ── ARP ───────────────────────────────────────────────────────────────────

    def get_arp_table(self) -> List[Dict]:
        return self._call("/ip/arp/print")

    # ── Interfaces ────────────────────────────────────────────────────────────

    def get_interfaces(self) -> List[Dict]:
        return self._call("/interface/print")

    # ── Firewall Filter ───────────────────────────────────────────────────────

    def get_firewall_filter_rules(self) -> List[Dict]:
        raw = self._call("/ip/firewall/filter/print")
        rules = []
        for r in raw:
            rules.append({
                "id": r.get(".id", ""),
                "chain": r.get("chain", ""),
                "action": r.get("action", ""),
                "src_address": r.get("src-address", "") or None,
                "dst_address": r.get("dst-address", "") or None,
                "protocol": r.get("protocol", "") or None,
                "src_port": r.get("src-port", "") or None,
                "dst_port": r.get("dst-port", "") or None,
                "in_interface": r.get("in-interface", "") or None,
                "out_interface": r.get("out-interface", "") or None,
                "comment": r.get("comment", "") or None,
                "disabled": r.get("disabled", "false") in ("true", "yes"),
                "bytes": r.get("bytes", "") or None,
                "packets": r.get("packets", "") or None,
            })
        return rules

    def remove_firewall_filter_rule(self, rule_id: str) -> None:
        self._call("/ip/firewall/filter/remove", **{".id": rule_id})

    def disable_firewall_filter_rule(self, rule_id: str) -> None:
        self._call("/ip/firewall/filter/set", **{".id": rule_id, "disabled": "yes"})

    def enable_firewall_filter_rule(self, rule_id: str) -> None:
        self._call("/ip/firewall/filter/set", **{".id": rule_id, "disabled": "no"})

    # ── Mangle ────────────────────────────────────────────────────────────────

    def get_mangle_rules(self) -> List[Dict]:
        raw = self._call("/ip/firewall/mangle/print")
        rules = []
        for r in raw:
            rules.append({
                "id": r.get(".id", ""),
                "chain": r.get("chain", ""),
                "action": r.get("action", ""),
                "new_packet_mark": r.get("new-packet-mark", "") or None,
                "new_connection_mark": r.get("new-connection-mark", "") or None,
                "src_address": r.get("src-address", "") or None,
                "dst_address": r.get("dst-address", "") or None,
                "protocol": r.get("protocol", "") or None,
                "dst_port": r.get("dst-port", "") or None,
                "comment": r.get("comment", "") or None,
                "disabled": r.get("disabled", "false") in ("true", "yes"),
                "passthrough": r.get("passthrough", "true") in ("true", "yes"),
            })
        return rules

    def remove_mangle_rule(self, rule_id: str) -> None:
        self._call("/ip/firewall/mangle/remove", **{".id": rule_id})

    # ── PCQ / Queue Types ─────────────────────────────────────────────────────

    def get_pcq_queues(self) -> List[Dict]:
        raw = self._call("/queue/type/print")
        return [
            {
                "id": r.get(".id", ""),
                "name": r.get("name", ""),
                "kind": r.get("kind", ""),
                "pcq_rate": r.get("pcq-rate", "") or None,
                "pcq_limit": r.get("pcq-limit", "") or None,
                "pcq_classifier": r.get("pcq-classifier", "") or None,
            }
            for r in raw
            if r.get("kind", "") == "pcq"
        ]

    def setup_pcq(self) -> int:
        existing = {r["name"] for r in self.get_pcq_queues()}
        added = 0
        if "pcq-download" not in existing:
            self._call(
                "/queue/type/add",
                name="pcq-download",
                kind="pcq",
                **{"pcq-classifier": "dst-address", "pcq-rate": "0", "pcq-limit": "50", "pcq-total-limit": "2000"},
            )
            added += 1
        if "pcq-upload" not in existing:
            self._call(
                "/queue/type/add",
                name="pcq-upload",
                kind="pcq",
                **{"pcq-classifier": "src-address", "pcq-rate": "0", "pcq-limit": "50", "pcq-total-limit": "2000"},
            )
            added += 1
        return added

    # ── Security / QoS Templates ──────────────────────────────────────────────

    def apply_template(self, template: str) -> int:
        if template == "basic_security":
            return self._apply_basic_security()
        if template == "icmp_limit":
            return self._apply_icmp_limit()
        if template == "qos_prioritization":
            return self._apply_qos_prioritization()
        if template == "drop_invalid":
            return self._apply_drop_invalid()
        raise MikrotikError(f"Template desconocido: {template}")

    def _apply_basic_security(self) -> int:
        rules = [
            {"chain": "input", "action": "accept", "connection-state": "established,related", "comment": "guaynet: accept established"},
            {"chain": "input", "action": "drop", "connection-state": "invalid", "comment": "guaynet: drop invalid input"},
            {"chain": "input", "action": "accept", "protocol": "icmp", "comment": "guaynet: accept icmp"},
            {"chain": "input", "action": "accept", "dst-port": "8728,8729,22", "protocol": "tcp", "src-address": "192.168.0.0/16", "comment": "guaynet: allow mgmt LAN"},
            {"chain": "input", "action": "drop", "in-interface": "ether1", "comment": "guaynet: drop all from WAN"},
            {"chain": "forward", "action": "accept", "connection-state": "established,related", "comment": "guaynet: forward established"},
            {"chain": "forward", "action": "drop", "connection-state": "invalid", "comment": "guaynet: drop invalid forward"},
        ]
        for r in rules:
            self._call("/ip/firewall/filter/add", **r)
        return len(rules)

    def _apply_icmp_limit(self) -> int:
        rules = [
            {"chain": "input", "action": "accept", "protocol": "icmp", "limit": "10,20:packet", "comment": "guaynet: icmp rate accept"},
            {"chain": "input", "action": "drop", "protocol": "icmp", "comment": "guaynet: icmp rate drop excess"},
        ]
        for r in rules:
            self._call("/ip/firewall/filter/add", **r)
        return len(rules)

    def _apply_drop_invalid(self) -> int:
        rules = [
            {"chain": "input", "action": "drop", "connection-state": "invalid", "comment": "guaynet: drop invalid conn"},
            {"chain": "forward", "action": "drop", "connection-state": "invalid", "comment": "guaynet: drop invalid fwd"},
        ]
        for r in rules:
            self._call("/ip/firewall/filter/add", **r)
        return len(rules)

    def _apply_qos_prioritization(self) -> int:
        self.setup_pcq()
        rules = [
            {"chain": "prerouting", "action": "mark-packet", "protocol": "udp", "dst-port": "5060,5061,10000-20000", "new-packet-mark": "voip", "passthrough": "yes", "comment": "guaynet: mark VoIP"},
            {"chain": "prerouting", "action": "mark-packet", "protocol": "udp", "dst-port": "53", "new-packet-mark": "dns", "passthrough": "yes", "comment": "guaynet: mark DNS"},
            {"chain": "prerouting", "action": "mark-packet", "protocol": "tcp", "dst-port": "443", "new-packet-mark": "https", "passthrough": "yes", "comment": "guaynet: mark HTTPS"},
            {"chain": "prerouting", "action": "mark-packet", "protocol": "tcp", "dst-port": "80", "new-packet-mark": "http", "passthrough": "yes", "comment": "guaynet: mark HTTP"},
        ]
        for r in rules:
            self._call("/ip/firewall/mangle/add", **r)
        return len(rules)


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
