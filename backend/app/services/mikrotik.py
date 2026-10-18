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
        # Pre-check: fast TCP reachability test before librouteros handshake
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(self.timeout)
        try:
            result = probe.connect_ex((self.host, self.port))
            if result != 0:
                raise MikrotikError(f"Puerto {self.port} inaccesible en {self.host} (errno {result})")
        except socket.timeout:
            raise MikrotikError(f"Timeout al conectar con {self.host}:{self.port} ({self.timeout}s)")
        except OSError as e:
            raise MikrotikError(f"No se pudo conectar a {self.host}:{self.port} — {e}")
        finally:
            probe.close()

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
        except Exception as e:
            raise MikrotikError(f"Error al conectar con {self.host}: {e}")
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
        except Exception as e:
            raise MikrotikError(f"Error inesperado en RouterOS: {e}")

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
                "parent": q.get("parent", "none"),
            })
        return queues

    def ensure_parent_queue(self, name: str, max_limit: str) -> None:
        """Create or update the uplink parent queue."""
        existing = self.get_queue_by_name(name)
        if existing:
            if existing.get("max_limit") != max_limit:
                self.update_simple_queue(existing["id"], max_limit=max_limit)
        else:
            self._call(
                "/queue/simple/add",
                name=name,
                target="0.0.0.0/0",
                **{"max-limit": max_limit},
            )

    def get_queue_by_name(self, name: str) -> Optional[Dict]:
        # Use RouterOS-side filtering to avoid fetching all queues
        try:
            raw = self._call("/queue/simple/print", **{"?name": name})
        except MikrotikError:
            # Fall back to full scan if filtered query fails
            raw = self._call("/queue/simple/print")
        q = next((r for r in raw if r.get("name") == name), None)
        if not q:
            return None
        return {
            "id": q.get(".id", ""),
            "name": q.get("name", ""),
            "target": q.get("target", ""),
            "max_limit": q.get("max-limit", ""),
            "disabled": q.get("disabled", "false") in ("true", "yes"),
            "comment": q.get("comment", ""),
            "parent": q.get("parent", "none"),
        }

    def get_queues_with_bytes(self) -> List[Dict]:
        """Return queues with parsed upload/download byte counters."""
        result = []
        for q in self.get_simple_queues():
            raw_bytes = q.get("bytes", "0/0")
            parts = raw_bytes.split("/") if "/" in str(raw_bytes) else ["0", "0"]
            try:
                upload = int(parts[0])
                download = int(parts[1]) if len(parts) > 1 else 0
            except (ValueError, IndexError):
                upload = download = 0
            result.append({
                "name": q["name"],
                "target": q["target"],
                "upload_bytes": upload,
                "download_bytes": download,
            })
        return result

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
        parent: Optional[str] = None,
        queue_type: Optional[str] = None,
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
        if parent:
            params["parent"] = parent
        if queue_type:
            params["queue"] = f"{queue_type}/{queue_type}"
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
        parent: Optional[str] = None,
        queue_type: Optional[str] = None,
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
        if parent is not None:
            params["parent"] = parent
        if queue_type is not None:
            params["queue"] = f"{queue_type}/{queue_type}"
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

    def get_interface_stats(self) -> List[Dict]:
        """Interface list with byte/rate counters for utilization monitoring."""
        raw = self._call("/interface/print")
        result = []
        for r in raw:
            result.append({
                "name": r.get("name", ""),
                "type": r.get("type", ""),
                "running": r.get("running", "false") in ("true", "yes"),
                "rx_byte": int(r.get("rx-byte", 0) or 0),
                "tx_byte": int(r.get("tx-byte", 0) or 0),
                "rx_rate": int(r.get("rx-rate", 0) or 0),
                "tx_rate": int(r.get("tx-rate", 0) or 0),
            })
        return result

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
                "src_port": str(v) if (v := r.get("src-port")) else None,
                "dst_port": str(v) if (v := r.get("dst-port")) else None,
                "in_interface": r.get("in-interface", "") or None,
                "out_interface": r.get("out-interface", "") or None,
                "comment": r.get("comment", "") or None,
                "disabled": r.get("disabled", "false") in ("true", "yes"),
                "bytes": str(v) if (v := r.get("bytes")) is not None else None,
                "packets": str(v) if (v := r.get("packets")) is not None else None,
            })
        return rules

    def remove_firewall_filter_rule(self, rule_id: str) -> None:
        self._call("/ip/firewall/filter/remove", **{".id": rule_id})

    def disable_firewall_filter_rule(self, rule_id: str) -> None:
        self._call("/ip/firewall/filter/set", **{".id": rule_id, "disabled": "yes"})

    def enable_firewall_filter_rule(self, rule_id: str) -> None:
        self._call("/ip/firewall/filter/set", **{".id": rule_id, "disabled": "no"})

    def _ensure_filter_rule(self, rule: dict) -> str:
        """Add a filter rule only if none with the same comment exists.
        Re-enables it if it was disabled. Returns 'added'|'enabled'|'exists'."""
        comment = rule.get("comment", "")
        for r in self.get_firewall_filter_rules():
            if r.get("comment") == comment:
                if r.get("disabled"):
                    self.enable_firewall_filter_rule(r["id"])
                    return "enabled"
                return "exists"
        self._call("/ip/firewall/filter/add", **rule)
        return "added"

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
                "dst_port": str(v) if (v := r.get("dst-port")) else None,
                "comment": r.get("comment", "") or None,
                "disabled": r.get("disabled", "false") in ("true", "yes"),
                "passthrough": r.get("passthrough", "true") in ("true", "yes"),
            })
        return rules

    def remove_mangle_rule(self, rule_id: str) -> None:
        self._call("/ip/firewall/mangle/remove", **{".id": rule_id})

    def enable_mangle_rule(self, rule_id: str) -> None:
        self._call("/ip/firewall/mangle/set", **{".id": rule_id, "disabled": "no"})

    def disable_mangle_rule(self, rule_id: str) -> None:
        self._call("/ip/firewall/mangle/set", **{".id": rule_id, "disabled": "yes"})

    def _ensure_mangle_rule(self, rule: dict) -> str:
        """Add a mangle rule only if none with the same comment exists.
        Re-enables it if it was disabled. Returns 'added'|'enabled'|'exists'."""
        comment = rule.get("comment", "")
        for r in self.get_mangle_rules():
            if r.get("comment") == comment:
                if r.get("disabled"):
                    self.enable_mangle_rule(r["id"])
                    return "enabled"
                return "exists"
        self._call("/ip/firewall/mangle/add", **rule)
        return "added"

    # ── PCQ / Queue Types ─────────────────────────────────────────────────────

    def get_pcq_queues(self) -> List[Dict]:
        raw = self._call("/queue/type/print")
        return [
            {
                "id": r.get(".id", ""),
                "name": r.get("name", ""),
                "kind": r.get("kind", ""),
                "pcq_rate": str(v) if (v := r.get("pcq-rate")) else None,
                "pcq_limit": str(v) if (v := r.get("pcq-limit")) is not None else None,
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

    def has_queue_type(self, name: str) -> bool:
        try:
            types = self._call("/queue/type/print", **{"?name": name})
        except MikrotikError:
            types = self._call("/queue/type/print")
        return any(r.get("name") == name for r in types)

    def setup_sfq(self) -> int:
        """Create guaynet-sfq (Stochastic Fair Queuing) queue type if absent. Returns 1 if created."""
        if self.has_queue_type("guaynet-sfq"):
            return 0
        self._call("/queue/type/add", name="guaynet-sfq", kind="sfq", **{"sfq-perturb": "10"})
        return 1

    # ── Queue Tree ────────────────────────────────────────────────────────────

    def get_queue_trees(self) -> List[Dict]:
        raw = self._call("/queue/tree/print")
        result = []
        for r in raw:
            result.append({
                "id": r.get(".id", ""),
                "name": r.get("name", ""),
                "parent": r.get("parent", ""),
                "packet_mark": r.get("packet-mark", "") or None,
                "priority": r.get("priority", "8"),
                "max_limit": r.get("max-limit", ""),
                "disabled": r.get("disabled", "false") in ("true", "yes"),
            })
        return result

    def setup_queue_tree(
        self,
        wan_interface: str,
        lan_interface: Optional[str],
        upload_mbps: Optional[int],
        download_mbps: Optional[int],
    ) -> Dict[str, int]:
        """Create/update Queue Tree for priority QoS on WAN (upload) and LAN (download).

        Upload tree  (parent=<wan_interface>, max-limit=upload_mbps):
          guaynet-qos-up → voip p1, dns p2, https p4, http p6

        Download tree (parent=<lan_interface>, max-limit=download_mbps) — only when lan_interface set:
          guaynet-qos-down → voip p1, dns p2, https p4, http p6

        Both trees reuse the same packet marks from mangle rules.
        """
        CHILDREN = [
            ("voip",  "voip",  "1"),
            ("dns",   "dns",   "2"),
            ("https", "https", "4"),
            ("http",  "http",  "6"),
        ]

        existing = {t["name"]: t for t in self.get_queue_trees()}
        added = 0
        updated = 0

        def _ensure_tree(root_name: str, parent: str, max_limit: str) -> None:
            nonlocal added, updated
            root = existing.get(root_name)
            if root:
                if root["parent"] != parent or root["max_limit"] != max_limit:
                    self._call("/queue/tree/set", **{".id": root["id"], "parent": parent, "max-limit": max_limit})
                    updated += 1
            else:
                self._call("/queue/tree/add", name=root_name, parent=parent, **{"max-limit": max_limit, "priority": "8"})
                added += 1

            for suffix, mark, priority in CHILDREN:
                name = f"{root_name}-{suffix}"
                entry = existing.get(name)
                if entry:
                    if entry["parent"] != root_name or entry.get("packet_mark") != mark:
                        self._call("/queue/tree/set", **{".id": entry["id"], "parent": root_name, "packet-mark": mark, "priority": priority})
                        updated += 1
                else:
                    self._call("/queue/tree/add", name=name, parent=root_name, **{"packet-mark": mark, "priority": priority})
                    added += 1

        ul_limit = f"{upload_mbps}M" if upload_mbps else "0"
        _ensure_tree("guaynet-qos-up", wan_interface, ul_limit)

        if lan_interface:
            dl_limit = f"{download_mbps}M" if download_mbps else "0"
            _ensure_tree("guaynet-qos-down", lan_interface, dl_limit)

        return {"added": added, "updated": updated}

    # ── Security / QoS Templates ──────────────────────────────────────────────

    def apply_template(self, template: str) -> Dict[str, int]:
        """Apply a rule template idempotently. Returns {added, enabled, skipped}."""
        if template == "basic_security":
            return self._apply_basic_security()
        if template == "icmp_limit":
            return self._apply_icmp_limit()
        if template == "qos_prioritization":
            return self._apply_qos_prioritization()
        if template == "drop_invalid":
            return self._apply_drop_invalid()
        raise MikrotikError(f"Template desconocido: {template}")

    def _count_results(self, results: List[str]) -> Dict[str, int]:
        return {
            "added": results.count("added"),
            "enabled": results.count("enabled"),
            "skipped": results.count("exists"),
        }

    def _apply_basic_security(self) -> Dict[str, int]:
        rules = [
            {"chain": "input", "action": "accept", "connection-state": "established,related", "comment": "guaynet: accept established"},
            {"chain": "input", "action": "drop", "connection-state": "invalid", "comment": "guaynet: drop invalid input"},
            {"chain": "input", "action": "accept", "protocol": "icmp", "comment": "guaynet: accept icmp"},
            {"chain": "input", "action": "accept", "dst-port": "8728,8729,22", "protocol": "tcp", "src-address": "192.168.0.0/16", "comment": "guaynet: allow mgmt LAN"},
            {"chain": "input", "action": "drop", "in-interface": "ether1", "comment": "guaynet: drop all from WAN"},
            {"chain": "forward", "action": "accept", "connection-state": "established,related", "comment": "guaynet: forward established"},
            {"chain": "forward", "action": "drop", "connection-state": "invalid", "comment": "guaynet: drop invalid forward"},
        ]
        return self._count_results([self._ensure_filter_rule(r) for r in rules])

    def _apply_icmp_limit(self) -> Dict[str, int]:
        rules = [
            {"chain": "input", "action": "accept", "protocol": "icmp", "limit": "10,20:packet", "comment": "guaynet: icmp rate accept"},
            {"chain": "input", "action": "drop", "protocol": "icmp", "comment": "guaynet: icmp rate drop excess"},
        ]
        return self._count_results([self._ensure_filter_rule(r) for r in rules])

    def _apply_drop_invalid(self) -> Dict[str, int]:
        rules = [
            {"chain": "input", "action": "drop", "connection-state": "invalid", "comment": "guaynet: drop invalid conn"},
            {"chain": "forward", "action": "drop", "connection-state": "invalid", "comment": "guaynet: drop invalid fwd"},
        ]
        return self._count_results([self._ensure_filter_rule(r) for r in rules])

    def _apply_qos_prioritization(self) -> Dict[str, int]:
        self.setup_pcq()
        rules = [
            {"chain": "prerouting", "action": "mark-packet", "protocol": "udp", "dst-port": "5060,5061,10000-20000", "new-packet-mark": "voip", "passthrough": "yes", "comment": "guaynet: mark VoIP"},
            {"chain": "prerouting", "action": "mark-packet", "protocol": "udp", "dst-port": "53", "new-packet-mark": "dns", "passthrough": "yes", "comment": "guaynet: mark DNS"},
            {"chain": "prerouting", "action": "mark-packet", "protocol": "tcp", "dst-port": "443", "new-packet-mark": "https", "passthrough": "yes", "comment": "guaynet: mark HTTPS"},
            {"chain": "prerouting", "action": "mark-packet", "protocol": "tcp", "dst-port": "80", "new-packet-mark": "http", "passthrough": "yes", "comment": "guaynet: mark HTTP"},
        ]
        return self._count_results([self._ensure_mangle_rule(r) for r in rules])


    # ── PPPoE Secrets ─────────────────────────────────────────────────────────

    def get_pppoe_secrets(self) -> list:
        try:
            return [dict(s) for s in self._call("/ppp/secret/print")]
        except Exception as e:
            print(f"[mikrotik] get_pppoe_secrets error: {e}", flush=True)
            return []

    def add_pppoe_secret(self, username: str, password: str, ip_address: str, profile: str = "default", comment: str = "") -> bool:
        try:
            self._call("/ppp/secret/add", **{
                "name": username,
                "password": password,
                "service": "pppoe",
                "remote-address": ip_address,
                "profile": profile,
                "comment": comment,
                "disabled": "no",
            })
            return True
        except Exception as e:
            print(f"[mikrotik] add_pppoe_secret error: {e}", flush=True)
            return False

    def update_pppoe_secret(self, username: str, password: Optional[str] = None, ip_address: Optional[str] = None, disabled: Optional[bool] = None) -> bool:
        try:
            secrets = self._call("/ppp/secret/print", **{"?name": username})
            if not secrets:
                return False
            secret_id = secrets[0].get(".id") or secrets[0].get("id")
            params: Dict[str, str] = {".id": secret_id}
            if password is not None:
                params["password"] = password
            if ip_address is not None:
                params["remote-address"] = ip_address
            if disabled is not None:
                params["disabled"] = "yes" if disabled else "no"
            self._call("/ppp/secret/set", **params)
            return True
        except Exception as e:
            print(f"[mikrotik] update_pppoe_secret error: {e}", flush=True)
            return False

    def remove_pppoe_secret(self, username: str) -> bool:
        try:
            secrets = self._call("/ppp/secret/print", **{"?name": username})
            if not secrets:
                return True
            secret_id = secrets[0].get(".id") or secrets[0].get("id")
            self._call("/ppp/secret/remove", **{".id": secret_id})
            return True
        except Exception as e:
            print(f"[mikrotik] remove_pppoe_secret error: {e}", flush=True)
            return False


def build_service_from_router(router) -> MikrotikService:
    """Build a MikrotikService from a MikrotikRouter ORM model."""
    from app.core.security import decrypt_value

    password = decrypt_value(router.password_encrypted)
    return MikrotikService(
        host=router.host,
        port=router.port,
        username=router.username,
        password=password,
        timeout=20,
    )
