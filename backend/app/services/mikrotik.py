"""
Mikrotik RouterOS API service.
Wraps librouteros for Simple Queue management across RouterOS 6 and 7.
All methods are synchronous — call via asyncio.to_thread() from async endpoints.
"""
import logging
import socket
import unicodedata
from typing import Any, Dict, List, Optional

import librouteros

logger = logging.getLogger(__name__)
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
            probe.connect((self.host, self.port))
        except socket.timeout:
            raise MikrotikError(f"Timeout al conectar con {self.host}:{self.port} ({self.timeout}s)")
        except ConnectionRefusedError:
            raise MikrotikError(f"Puerto {self.port} inaccesible en {self.host}")
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

    @staticmethod
    def _ascii_safe(s: str) -> str:
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

    def _call(self, cmd: str, **params) -> List[Dict]:
        if not self._api:
            raise MikrotikError("No hay conexión activa")
        safe_params = {
            k: self._ascii_safe(v) if isinstance(v, str) else v
            for k, v in params.items()
        }
        try:
            return list(self._api(cmd, **safe_params))
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

    def update_queue_target(self, queue_name: str, new_ip: str) -> None:
        all_queues = self._call("/queue/simple/print")
        q = next((x for x in all_queues if x.get("name") == queue_name), None)
        if q:
            self._call("/queue/simple/set", **{".id": q[".id"], "target": f"{new_ip}/32"})

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

    def get_system_resources(self) -> Dict:
        raw = self._call("/system/resource/print")
        r = raw[0] if raw else {}
        return {
            "free_hdd_space": int(r.get("free-hdd-space", 0) or 0),
            "total_hdd_space": int(r.get("total-hdd-space", 0) or 0),
            "free_memory": int(r.get("free-memory", 0) or 0),
            "total_memory": int(r.get("total-memory", 0) or 0),
            "cpu_load": int(r.get("cpu-load", 0) or 0),
        }

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

    @staticmethod
    def _parse_limit_bps(limit) -> int:
        """'100M' → 100_000_000 bps, '1G' → 1_000_000_000, '512k' → 512_000."""
        if not limit:
            return 0
        if isinstance(limit, (int, float)):
            return int(limit)
        s = str(limit).strip()
        try:
            if s.endswith("G"):
                return int(float(s[:-1]) * 1_000_000_000)
            if s.endswith("M"):
                return int(float(s[:-1]) * 1_000_000)
            if s.lower().endswith("k"):
                return int(float(s[:-1]) * 1_000)
            return int(s)
        except (ValueError, TypeError):
            return 0

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

    def get_queue_tree_with_stats(self) -> List[Dict]:
        """Queue tree entries with live rate/bytes stats for visualization."""
        raw = self._call("/queue/tree/print")
        result = []
        for r in raw:
            max_limit_str = r.get("max-limit", "") or ""
            limit_at_str = r.get("limit-at", "") or ""
            try:
                rate_bps = int(r.get("rate", "0") or "0")
            except (ValueError, TypeError):
                rate_bps = 0
            try:
                total_bytes = int(r.get("bytes", "0") or "0")
            except (ValueError, TypeError):
                total_bytes = 0
            result.append({
                "id": r.get(".id", ""),
                "name": r.get("name", ""),
                "parent": r.get("parent", "global"),
                "packet_mark": r.get("packet-mark", "") or None,
                "priority": r.get("priority", "8"),
                "limit_at": limit_at_str or None,
                "max_limit": max_limit_str or None,
                "max_limit_bps": self._parse_limit_bps(max_limit_str),
                "rate_bps": rate_bps,
                "total_bytes": total_bytes,
                "disabled": r.get("disabled", "false") in ("true", "yes"),
                "comment": r.get("comment", "") or None,
            })
        return result

    def apply_professional_qos_tree(self, download_mbps: int, upload_mbps: int) -> Dict[str, int]:
        """Deploy a clean professional QoS queue tree + matching mangle marks.

        Marks (mangle prerouting, connection-based for both directions):
          prior.pkt  → ICMP + DNS UDP/53          priority 1
          voip.pkt   → SIP/RTP UDP 5060/10000-20000  priority 1
          https.pkt  → TCP 443                    priority 2
          game.pkt   → common gaming ports        priority 3
          whatsapp.pkt → TCP 5222/5223            priority 3
          http.pkt   → TCP 80                     priority 6
          resto.pkt  → everything else            priority 8

        Tree:
          DOWNLOAD (max=download_mbps) / UPLOAD (max=upload_mbps) — parent=global
            children per mark, same structure for both directions
        """
        added = 0

        # ── 1. Mangle connection marks (prerouting) ─────────────────────────
        CONN_MARKS = [
            # (conn-mark-name, filter-params)
            ("cm-prior",    {"protocol": "icmp"}),
            ("cm-prior",    {"protocol": "udp", "dst-port": "53"}),
            ("cm-voip",     {"protocol": "udp", "dst-port": "5060,5061,10000-20000"}),
            ("cm-https",    {"protocol": "tcp", "dst-port": "443"}),
            ("cm-game",     {"protocol": "udp", "dst-port": "3478-3481,3658,27015-27030"}),
            ("cm-game",     {"protocol": "tcp", "dst-port": "27015-27030,7777,25565"}),
            ("cm-whatsapp", {"protocol": "tcp", "dst-port": "5222,5223"}),
            ("cm-http",     {"protocol": "tcp", "dst-port": "80"}),
        ]
        for conn_mark, extra in CONN_MARKS:
            self._ensure_mangle_rule({
                "chain": "prerouting",
                "action": "mark-connection",
                "new-connection-mark": conn_mark,
                "passthrough": "yes",
                "comment": f"guaynet-pro: conn {conn_mark}",
                **extra,
            })

        # mark resto for unclassified (must be last)
        self._ensure_mangle_rule({
            "chain": "prerouting",
            "action": "mark-connection",
            "new-connection-mark": "cm-resto",
            "connection-mark": "no-mark",
            "passthrough": "yes",
            "comment": "guaynet-pro: conn resto",
        })

        # ── 2. Mangle packet marks from connection marks ────────────────────
        PKT_MARKS = [
            ("cm-prior",    "prior.pkt"),
            ("cm-voip",     "voip.pkt"),
            ("cm-https",    "https.pkt"),
            ("cm-game",     "game.pkt"),
            ("cm-whatsapp", "whatsapp.pkt"),
            ("cm-http",     "http.pkt"),
            ("cm-resto",    "resto.pkt"),
        ]
        for conn_mark, pkt_mark in PKT_MARKS:
            self._ensure_mangle_rule({
                "chain": "prerouting",
                "action": "mark-packet",
                "connection-mark": conn_mark,
                "new-packet-mark": pkt_mark,
                "passthrough": "no",
                "comment": f"guaynet-pro: pkt {pkt_mark}",
            })

        # ── 3. Queue tree structure ─────────────────────────────────────────
        CHILDREN = [
            # (suffix, packet_mark, priority, comment)
            ("Prior",     "prior.pkt",     "1", "DNS + ICMP"),
            ("VoIP",      "voip.pkt",      "1", "VoIP SIP/RTP"),
            ("HTTPS",     "https.pkt",     "2", "HTTPS"),
            ("Juegos",    "game.pkt",      "3", "Gaming"),
            ("WhatsApp",  "whatsapp.pkt",  "3", "WhatsApp"),
            ("HTTP",      "http.pkt",      "6", "HTTP"),
            ("Resto",     "resto.pkt",     "8", "Resto del trafico"),
        ]

        existing = {t["name"]: t for t in self.get_queue_trees()}

        def _ensure_tree_entry(name: str, parent: str, max_limit: str,
                               packet_mark: Optional[str], priority: str, comment: str) -> None:
            nonlocal added
            params: Dict[str, str] = {
                "name": name,
                "parent": parent,
                "priority": priority,
                "comment": comment,
            }
            if max_limit:
                params["max-limit"] = max_limit
            if packet_mark:
                params["packet-mark"] = packet_mark

            entry = existing.get(name)
            if entry:
                set_params = {".id": entry["id"]}
                if max_limit:
                    set_params["max-limit"] = max_limit
                if packet_mark:
                    set_params["packet-mark"] = packet_mark
                set_params["priority"] = priority
                self._call("/queue/tree/set", **set_params)
            else:
                self._call("/queue/tree/add", **params)
                added += 1

        for direction, max_mbps in [("DOWNLOAD", download_mbps), ("UPLOAD", upload_mbps)]:
            root = f"guaynet-{direction}"
            _ensure_tree_entry(root, "global", f"{max_mbps}M", None, "8", f"guaynet-pro: {direction}")
            for suffix, mark, prio, desc in CHILDREN:
                _ensure_tree_entry(
                    f"{root}-{suffix}", root, "",
                    mark, prio, f"guaynet-pro: {desc}"
                )

        return {"added": added}

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


    # ── WAN / Interface control ───────────────────────────────────────────────

    def enable_interface(self, name: str) -> None:
        all_ifaces = self._call("/interface/print")
        iface = next((i for i in all_ifaces if i.get("name") == name), None)
        if not iface:
            raise MikrotikError(f"Interface '{name}' not found")
        self._call("/interface/enable", **{".id": iface[".id"]})

    def disable_interface(self, name: str) -> None:
        all_ifaces = self._call("/interface/print")
        iface = next((i for i in all_ifaces if i.get("name") == name), None)
        if not iface:
            raise MikrotikError(f"Interface '{name}' not found")
        self._call("/interface/disable", **{".id": iface[".id"]})

    def get_interface_bytes(self, name: str) -> Dict[str, int]:
        """Return current rx-byte / tx-byte counters for one interface."""
        all_ifaces = self._call("/interface/print")
        r = next((i for i in all_ifaces if i.get("name") == name), None)
        if not r:
            return {"rx_byte": 0, "tx_byte": 0, "running": False}
        return {
            "rx_byte": int(r.get("rx-byte", 0) or 0),
            "tx_byte": int(r.get("tx-byte", 0) or 0),
            "running": r.get("running", "false") in ("true", "yes"),
            "disabled": r.get("disabled", "false") in ("true", "yes"),
        }

    def set_scheduler_entry(self, entry_name: str, start_time: str, interval: str, script: str, days: str = "mon,tue,wed,thu,fri,sat,sun") -> None:
        """Create or replace a scheduler entry."""
        all_entries = self._call("/system/scheduler/print")
        existing = next((e for e in all_entries if e.get("name") == entry_name), None)
        params = {
            "start-time": start_time,
            "interval": interval,
            "on-event": script,
        }
        logger.error(f"[scheduler] entry={entry_name} existing={existing is not None} params={params}")
        if existing:
            result = self._call("/system/scheduler/set", **{".id": existing.get(".id"), **params})
        else:
            result = self._call("/system/scheduler/add", **{"name": entry_name, **params})
        logger.error(f"[scheduler] result={result}")

    def remove_scheduler_entry(self, entry_name: str) -> None:
        all_entries = self._call("/system/scheduler/print")
        existing = next((e for e in all_entries if e.get("name") == entry_name), None)
        if existing:
            self._call("/system/scheduler/remove", **{".id": existing.get(".id")})

    def get_scheduler_entries(self, prefix: str = "") -> List[Dict]:
        entries = self._call("/system/scheduler/print")
        if prefix:
            entries = [e for e in entries if e.get("name", "").startswith(prefix)]
        return entries

    def _routeros_version(self) -> int:
        """Return major RouterOS version (6 or 7)."""
        try:
            info = self._call("/system/resource/print")
            version = info[0].get("version", "6") if info else "6"
            return int(str(version).split(".")[0])
        except Exception:
            return 6

    def apply_pcc_load_balance(self, wan_configs: List[Dict]) -> Dict[str, int]:
        """
        Configure PCC load balancing for multiple WAN interfaces.
        wan_configs: [{"interface": "ether1", "gateway": "1.2.3.1", "weight": 1}, ...]
        Returns counts of rules added/updated.
        """
        added = 0
        n = len(wan_configs)
        if n < 2:
            raise MikrotikError("Necesitás al menos 2 interfaces WAN para balanceo")

        ros_ver = self._routeros_version()
        # In routes: routing-table (v7) vs routing-mark (v6)
        routing_mark_key = "routing-table" if ros_ver >= 7 else "routing-mark"

        logger.error(f"[wan] RouterOS version: {ros_ver}, routing key: {routing_mark_key}")

        # RouterOS v7 requires routing tables to exist before mangle rules reference them.
        # Try unconditionally — silently ignored on v6 where /routing/table doesn't exist.
        try:
            existing_tables = self._call("/routing/table/print")
            existing_table_names = {t.get("name", "") for t in existing_tables}
            logger.error(f"[wan] existing routing tables: {existing_table_names}")
            for i in range(n):
                table_name = f"wan{i+1}_route"
                if table_name not in existing_table_names:
                    try:
                        self._call("/routing/table/add", name=table_name, fib="yes")
                        logger.error(f"[wan] created routing table: {table_name}")
                    except Exception as e:
                        logger.error(f"[wan] routing table add failed (may already exist): {e}")
        except Exception as e:
            logger.error(f"[wan] /routing/table not available (probably v6): {e}")

        # Bypass established/related replies coming FROM each WAN interface.
        # These packets are internet→LAN replies; they must NOT get routing marks
        # because the WAN routing tables have no LAN routes (only a default gateway).
        for i, wan in enumerate(wan_configs):
            mark = f"wan{i+1}"
            bypass = {
                "chain": "prerouting",
                "in-interface": wan["interface"],
                "connection-state": "established,related",
                "action": "accept",
                "comment": f"guaynet-lb-bypass-{mark}",
                "passthrough": "no",
            }
            self._ensure_mangle_rule(bypass)
            added += 1

        for i, wan in enumerate(wan_configs):
            mark = f"wan{i+1}"

            # Mark new connections per WAN using PCC
            conn_rule = {
                "chain": "prerouting",
                "connection-state": "new",
                "action": "mark-connection",
                "new-connection-mark": f"{mark}_conn",
                "per-connection-classifier": f"both-addresses-and-ports:{n}/{i}",
                "comment": f"guaynet-lb-conn-{mark}",
                "passthrough": "yes",
            }
            # Mark routing for LAN→internet packets (both new and established upstream)
            pkt_rule = {
                "chain": "prerouting",
                "connection-mark": f"{mark}_conn",
                "action": "mark-routing",
                "new-routing-mark": f"{mark}_route",
                "comment": f"guaynet-lb-pkt-{mark}",
                "passthrough": "yes",
            }
            for rule in [conn_rule, pkt_rule]:
                self._ensure_mangle_rule(rule)
                added += 1

        # Add routing table entries
        for i, wan in enumerate(wan_configs):
            mark = f"wan{i+1}"
            gateway = wan.get("gateway")
            if not gateway:
                continue
            # Remove existing guaynet route for this mark before adding
            try:
                existing_routes = self._call("/ip/route/print")
                for r in existing_routes:
                    if str(r.get("comment", "")).startswith(f"guaynet-lb-route-{mark}"):
                        self._call("/ip/route/remove", **{".id": r[".id"]})
            except Exception:
                pass
            try:
                self._call("/ip/route/add", **{
                    "dst-address": "0.0.0.0/0",
                    "gateway": gateway,
                    routing_mark_key: f"{mark}_route",
                    "comment": f"guaynet-lb-route-{mark}",
                    "distance": str(i + 1),
                })
                added += 1
            except Exception as e:
                logger.error(f"[wan] route add error for {mark}: {e}")
                raise

        # Add NAT masquerade per WAN interface so traffic is properly NATted
        for i, wan in enumerate(wan_configs):
            mark = f"wan{i+1}"
            nat_comment = f"guaynet-lb-nat-{mark}"
            existing_nat = self._call("/ip/firewall/nat/print")
            if not any(r.get("comment") == nat_comment for r in existing_nat):
                try:
                    self._call("/ip/firewall/nat/add", **{
                        "chain": "srcnat",
                        "out-interface": wan["interface"],
                        "action": "masquerade",
                        "comment": nat_comment,
                    })
                    added += 1
                    logger.error(f"[wan] added NAT masquerade for {wan['interface']}")
                except Exception as e:
                    logger.error(f"[wan] NAT masquerade error for {wan['interface']}: {e}")

        return {"rules_added": added}

    def remove_pcc_load_balance(self) -> None:
        """Remove all guaynet PCC load balancing rules."""
        mangle = self._call("/ip/firewall/mangle/print")
        for rule in mangle:
            if str(rule.get("comment", "")).startswith("guaynet-lb-"):
                try:
                    self._call("/ip/firewall/mangle/remove", **{".id": rule[".id"]})
                except Exception:
                    pass
        routes = self._call("/ip/route/print")
        for route in routes:
            if str(route.get("comment", "")).startswith("guaynet-lb-route-"):
                try:
                    self._call("/ip/route/remove", **{".id": route[".id"]})
                except Exception:
                    pass
        # Remove NAT rules
        try:
            nat_rules = self._call("/ip/firewall/nat/print")
            for rule in nat_rules:
                if str(rule.get("comment", "")).startswith("guaynet-lb-nat-"):
                    try:
                        self._call("/ip/firewall/nat/remove", **{".id": rule[".id"]})
                    except Exception:
                        pass
        except Exception:
            pass
        # Remove routing tables (RouterOS v7)
        try:
            tables = self._call("/routing/table/print")
            for t in tables:
                if str(t.get("name", "")).startswith("wan") and t.get("name", "").endswith("_route"):
                    try:
                        self._call("/routing/table/remove", **{".id": t[".id"]})
                    except Exception:
                        pass
        except Exception:
            pass


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
