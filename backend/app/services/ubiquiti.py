"""
Ubiquiti AirOS 8.x HTTP API service.
Uses httpx in sync mode — call via asyncio.to_thread() from async endpoints.
Handles self-signed TLS certs (verify=False by default).
"""
from typing import Any, Dict, List, Optional

import httpx


class UbiquitiError(Exception):
    pass


class UbiquitiAirOSService:
    def __init__(self, host: str, username: str = "ubnt", password: str = "ubnt"):
        self.host = host
        self.username = username
        self.password = password
        self._client: Optional[httpx.Client] = None

    def connect(self) -> "UbiquitiAirOSService":
        self._client = httpx.Client(
            base_url=f"https://{self.host}",
            verify=False,
            timeout=15.0,
            follow_redirects=True,
        )
        try:
            res = self._client.post(
                "/api/auth",
                json={"username": self.username, "password": self.password},
            )
        except httpx.ConnectError as e:
            # Fallback to HTTP for older firmware
            self._client = httpx.Client(
                base_url=f"http://{self.host}",
                verify=False,
                timeout=15.0,
                follow_redirects=True,
            )
            try:
                res = self._client.post(
                    "/api/auth",
                    json={"username": self.username, "password": self.password},
                )
            except httpx.ConnectError as e2:
                raise UbiquitiError(f"No se pudo conectar a {self.host}: {e2}")
        except httpx.TimeoutException:
            raise UbiquitiError(f"Timeout al conectar a {self.host}")

        if res.status_code in (401, 403):
            raise UbiquitiError(f"Credenciales incorrectas en {self.host}")
        if res.status_code not in (200, 201):
            raise UbiquitiError(f"Auth falló HTTP {res.status_code} en {self.host}")

        try:
            data = res.json()
            token = data.get("authToken") or data.get("token", "")
            if token:
                self._client.headers.update({"X-Auth-Token": token})
        except Exception:
            pass  # cookie-based auth, no token needed

        return self

    def disconnect(self):
        if self._client:
            try:
                self._client.post("/api/auth/logout")
            except Exception:
                pass
            self._client.close()
            self._client = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.disconnect()

    def _get(self, path: str) -> Any:
        if not self._client:
            raise UbiquitiError("No hay conexión activa")
        try:
            res = self._client.get(path)
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            raise UbiquitiError(f"HTTP {e.response.status_code} en {path}")
        except httpx.RequestError as e:
            raise UbiquitiError(f"Error de red: {e}")

    def _put(self, path: str, data: Dict) -> Any:
        if not self._client:
            raise UbiquitiError("No hay conexión activa")
        try:
            res = self._client.put(path, json=data)
            res.raise_for_status()
            return res.json() if res.content else {}
        except httpx.HTTPStatusError as e:
            raise UbiquitiError(f"HTTP {e.response.status_code} en {path}")
        except httpx.RequestError as e:
            raise UbiquitiError(f"Error de red: {e}")

    # ── Device info ───────────────────────────────────────────────────────────

    def get_device_info(self) -> Dict:
        data = self._get("/api/v1.0/device/info")
        mem = data.get("memory", {})
        total = mem.get("total", 1) or 1
        used = mem.get("used", 0)
        return {
            "model": data.get("model") or data.get("board", ""),
            "firmware": data.get("firmware") or data.get("version", ""),
            "hostname": data.get("hostname", ""),
            "uptime_seconds": data.get("uptime", 0),
            "cpu_load": data.get("cpu_load") or data.get("cpu", 0),
            "ram_used_pct": round(used / total * 100, 1) if total else 0,
        }

    # ── Wireless config ───────────────────────────────────────────────────────

    def get_wireless(self) -> Dict:
        data = self._get("/api/v1.0/wireless")
        return {
            "mode": data.get("mode", ""),
            "ssid": data.get("ssid", ""),
            "frequency_mhz": data.get("frequency") or data.get("freq"),
            "channel_width_mhz": data.get("channel_width") or data.get("chwidth"),
            "tx_power_dbm": data.get("tx_power") or data.get("txpower"),
            "security": data.get("security", ""),
        }

    def set_wireless(
        self,
        frequency_mhz: Optional[int] = None,
        channel_width_mhz: Optional[int] = None,
        tx_power_dbm: Optional[int] = None,
    ) -> Dict:
        payload: Dict = {}
        if frequency_mhz is not None:
            payload["frequency"] = frequency_mhz
        if channel_width_mhz is not None:
            payload["channel_width"] = channel_width_mhz
        if tx_power_dbm is not None:
            payload["tx_power"] = tx_power_dbm
        return self._put("/api/v1.0/wireless", payload)

    # ── Link quality (station mode) ───────────────────────────────────────────

    def get_link(self) -> Dict:
        data = self._get("/api/v1.0/link")
        return {
            "remote_name": data.get("remote_name") or data.get("remote", ""),
            "remote_mac": data.get("remote_mac", ""),
            "signal_dbm": data.get("signal") or data.get("rssi"),
            "noise_dbm": data.get("noise") or data.get("noisefloor"),
            "snr_db": data.get("snr"),
            "ccq": data.get("ccq"),
            "rx_rate_mbps": data.get("rx_rate") or data.get("rxrate"),
            "tx_rate_mbps": data.get("tx_rate") or data.get("txrate"),
            "distance_m": data.get("distance"),
        }

    # ── Connected stations (AP mode) ──────────────────────────────────────────

    def get_stations(self) -> List[Dict]:
        data = self._get("/api/v1.0/stations")
        stations = data.get("stations", []) if isinstance(data, dict) else (data or [])
        result = []
        for s in stations:
            result.append({
                "mac": s.get("mac", ""),
                "ip": s.get("ip", ""),
                "name": s.get("name") or s.get("hostname", ""),
                "signal_dbm": s.get("signal") or s.get("rssi"),
                "noise_dbm": s.get("noise"),
                "ccq": s.get("ccq"),
                "rx_rate_mbps": s.get("rx_rate") or s.get("rxrate"),
                "tx_rate_mbps": s.get("tx_rate") or s.get("txrate"),
                "uptime_seconds": s.get("uptime"),
            })
        return result

    # ── Site survey ───────────────────────────────────────────────────────────

    def site_survey(self) -> List[Dict]:
        data = self._get("/api/v1.0/wireless/survey")
        networks = (
            data.get("results") or data.get("networks") or []
            if isinstance(data, dict) else data or []
        )
        result = []
        for n in networks:
            freq = n.get("frequency") or n.get("freq") or n.get("channel_frequency")
            result.append({
                "ssid": n.get("ssid", ""),
                "mac": n.get("mac") or n.get("bssid", ""),
                "frequency_mhz": freq,
                "channel_width_mhz": n.get("channel_width") or n.get("chwidth"),
                "signal_dbm": n.get("signal") or n.get("rssi"),
                "security": n.get("security", ""),
            })
        return result

    def recommend_frequencies(self) -> List[Dict]:
        """Analyze site survey and return frequencies sorted by congestion (best first)."""
        try:
            networks = self.site_survey()
        except UbiquitiError:
            return []

        freq_data: Dict[int, Dict] = {}
        for net in networks:
            freq = net.get("frequency_mhz")
            if not freq:
                continue
            signal = net.get("signal_dbm") or -90
            penalty = max(0, 100 + int(signal))  # -90 dBm → 10, -50 dBm → 50
            if freq not in freq_data:
                freq_data[freq] = {"score": 0, "count": 0, "networks": []}
            freq_data[freq]["score"] += penalty
            freq_data[freq]["count"] += 1
            freq_data[freq]["networks"].append(net.get("ssid", ""))

        result = []
        for freq, d in sorted(freq_data.items(), key=lambda x: x[1]["score"]):
            score = d["score"]
            result.append({
                "frequency_mhz": freq,
                "network_count": d["count"],
                "congestion_score": round(score, 1),
                "recommendation": "Excelente" if score < 20 else "Buena" if score < 50 else "Regular" if score < 100 else "Congestionada",
                "networks": d["networks"][:5],
            })
        return result


def build_service_from_device(device) -> UbiquitiAirOSService:
    from app.core.security import decrypt_value
    password = decrypt_value(device.password_encrypted) if device.password_encrypted else "ubnt"
    return UbiquitiAirOSService(
        host=device.host,
        username=device.username or "ubnt",
        password=password,
    )
