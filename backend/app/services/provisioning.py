"""
Single place that applies a client's desired state to its MikroTik router.

Every path that creates, edits, suspends, reactivates or re-syncs a client goes
through here (endpoints, billing jobs, payments, the Telegram bot), so the router
always ends up the same way:

- The client's simple queue (target = its IP, the plan's speed) is always ENABLED.
  A disabled queue in RouterOS stops *limiting*: disabling it never cut anyone.
- Suspension mode "block" (default): the client's IP goes into the address list
  ``guaynet-morosos``. Firewall rules at the top of the router (added on the first
  suspension) drop everything for that list except DNS, the overdue-notice page and
  the payment sites; plain-HTTP requests are redirected to the notice page. Open
  connections of the client are removed so nothing keeps working.
- Suspension mode "throttle": the queue drops to the configured speed instead.

Router calls run in a thread with a time limit, so saving a client never hangs on
an unreachable router: the result says what happened and the change can be re-sent
later with "Sincronizar".
"""
import asyncio
import ipaddress
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.config import SystemConfig
from app.models.plan import Plan
from app.models.router import MikrotikRouter
from app.services.mikrotik import MikrotikError, MikrotikService, build_service_from_router

logger = logging.getLogger(__name__)

SUSPENDED_LIST = "guaynet-morosos"
PAYMENT_LIST = "guaynet-pago-permitido"
RULE_PREFIX = "guaynet-morosos:"
PAYMENT_COMMENT = "guaynet-pago"
PROVISION_TIMEOUT = 15  # seconds a request waits for one client's router

DEFAULT_NOTICE_PORT = 8081
# Hosts a suspended client can still reach to pay. RouterOS resolves domain
# entries of an address list by itself (RouterOS 6.36+).
DEFAULT_PAYMENT_HOSTS = [
    "mercadopago.com.ar", "www.mercadopago.com.ar", "mercadopago.com", "www.mercadopago.com",
    "api.mercadopago.com", "secure.mlstatic.com", "http2.mlstatic.com", "www.mercadolibre.com",
]
_HOST_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")

CONFIG_KEYS = [
    "suspension_action", "suspension_speed", "suspension_notice_ip",
    "suspension_notice_port", "suspension_payment_hosts",
]


@dataclass
class SuspensionConfig:
    mode: str = "block"            # "block" | "throttle"
    speed: str = "64k"             # throttle speed
    notice_ip: Optional[str] = None  # Guaynet server as the routers reach it
    notice_port: int = DEFAULT_NOTICE_PORT
    payment_hosts: List[str] = field(default_factory=lambda: list(DEFAULT_PAYMENT_HOSTS))


def parse_suspension_config(raw: Dict[str, str]) -> SuspensionConfig:
    """Build the config from system_config values, ignoring anything unsafe."""
    cfg = SuspensionConfig()
    action = (raw.get("suspension_action") or "").strip()
    cfg.mode = "throttle" if action == "throttle" else "block"  # old "disable" = block
    speed = (raw.get("suspension_speed") or "").strip()
    if re.fullmatch(r"\d{1,6}[kM]?", speed):
        cfg.speed = speed
    ip = (raw.get("suspension_notice_ip") or "").strip()
    if ip:
        try:
            cfg.notice_ip = str(ipaddress.IPv4Address(ip))
        except ValueError:
            logger.warning("suspension_notice_ip inválida: %r (se ignora)", ip)
    port = (raw.get("suspension_notice_port") or "").strip()
    if port.isdigit() and 1 <= int(port) <= 65535:
        cfg.notice_port = int(port)
    hosts = raw.get("suspension_payment_hosts")
    if hosts is not None:
        cfg.payment_hosts = [
            h for h in (x.strip().lower() for x in re.split(r"[,\s]+", hosts)) if h and _HOST_RE.match(h)
        ]
    return cfg


async def load_suspension_config(db: AsyncSession) -> SuspensionConfig:
    rows = (await db.execute(select(SystemConfig).where(SystemConfig.key.in_(CONFIG_KEYS)))).scalars().all()
    return parse_suspension_config({r.key: r.value or "" for r in rows})


# ── Router-side work (runs in a thread, no ORM objects) ─────────────────────────

@dataclass
class ClientSnapshot:
    id: int
    name: str
    ip: str
    queue_name: str
    status: str                    # active | suspended | cancelled
    max_limit: Optional[str]       # plan speed, "up/down"
    burst_limit: Optional[str] = None
    burst_threshold: Optional[str] = None
    burst_time: Optional[str] = None


def snapshot(client: Client, plan: Optional[Plan]) -> ClientSnapshot:
    status = client.status.value if hasattr(client.status, "value") else str(client.status)
    return ClientSnapshot(
        id=client.id,
        name=client.full_name,
        ip=client.ip_address,
        queue_name=client.mikrotik_queue_name,
        status=status,
        max_limit=plan.mikrotik_max_limit if plan else None,
        burst_limit=plan.mikrotik_burst_limit if plan and plan.mikrotik_burst_threshold else None,
        burst_threshold=plan.mikrotik_burst_threshold if plan and plan.mikrotik_burst_limit else None,
        burst_time=plan.mikrotik_burst_time if plan and plan.mikrotik_burst_limit else None,
    )


def ensure_suspension_rules(svc: MikrotikService, cfg: SuspensionConfig) -> None:
    """Firewall rules that make the address list cut the service. Idempotent (by comment)."""
    # Allowed payment hosts
    entries = svc.get_address_list(PAYMENT_LIST)
    present = {e["address"] for e in entries if e["comment"] == PAYMENT_COMMENT}
    for host in cfg.payment_hosts:
        if host not in present:
            svc.add_address_list_entry(PAYMENT_LIST, host, PAYMENT_COMMENT)
    for e in entries:
        if e["comment"] == PAYMENT_COMMENT and e["address"] not in cfg.payment_hosts:
            svc.remove_address_list_entry(e["id"])

    flt = "/ip/firewall/filter"
    drop_id = svc.ensure_rule(flt, {
        "chain": "forward", "src-address-list": SUSPENDED_LIST, "action": "drop",
        "comment": RULE_PREFIX + "bloqueo",
    }, place_before="top")
    accepts = [
        {"chain": "forward", "src-address-list": SUSPENDED_LIST, "protocol": "udp", "dst-port": "53",
         "action": "accept", "comment": RULE_PREFIX + "dns-udp"},
        {"chain": "forward", "src-address-list": SUSPENDED_LIST, "protocol": "tcp", "dst-port": "53",
         "action": "accept", "comment": RULE_PREFIX + "dns-tcp"},
        {"chain": "forward", "src-address-list": SUSPENDED_LIST, "dst-address-list": PAYMENT_LIST,
         "action": "accept", "comment": RULE_PREFIX + "pago"},
    ]
    if cfg.notice_ip:
        accepts.append({"chain": "forward", "src-address-list": SUSPENDED_LIST, "dst-address": cfg.notice_ip,
                        "action": "accept", "comment": RULE_PREFIX + "aviso"})
    for rule in accepts:
        svc.ensure_rule(flt, rule, place_before=drop_id)  # accepts always above the drop

    nat = "/ip/firewall/nat"
    if cfg.notice_ip:
        svc.ensure_rule(nat, {
            "chain": "dstnat", "src-address-list": SUSPENDED_LIST, "protocol": "tcp", "dst-port": "80",
            "dst-address-list": "!" + PAYMENT_LIST, "action": "dst-nat",
            "to-addresses": cfg.notice_ip, "to-ports": str(cfg.notice_port),
            "comment": RULE_PREFIX + "redireccion",
        }, place_before="top")
    else:
        svc.remove_rules_by_comment(nat, [RULE_PREFIX + "redireccion"])
        svc.remove_rules_by_comment(flt, [RULE_PREFIX + "aviso"])


UPLINK_PARENT = "guaynet-uplink"


def router_state(router: MikrotikRouter) -> Dict:
    """Per-connection cache seed: the router's uplink (for the parent queue)."""
    up, down = router.uplink_upload_mbps, router.uplink_download_mbps
    return {"uplink": f"{up}M/{down}M" if up and down else None}


def apply_on_router(svc: MikrotikService, c: ClientSnapshot, cfg: SuspensionConfig, state: Dict) -> List[str]:
    """Bring one client to its desired state on an open connection. `state` caches what
    the calls of one connection share (queues, address list, rules already checked)."""
    done: List[str] = []
    suspended = c.status == "suspended"
    cancelled = c.status == "cancelled"
    block = suspended and cfg.mode == "block"

    if "queues" not in state:
        state["queues"] = {q["name"]: q for q in svc.get_simple_queues()}
        state["sfq"] = svc.has_queue_type("guaynet-sfq")
        state["suspended_entries"] = svc.get_address_list(SUSPENDED_LIST)
        state["parent"] = None
        if state.get("uplink"):
            try:
                svc.ensure_parent_queue(UPLINK_PARENT, state["uplink"])
                state["parent"] = UPLINK_PARENT
            except MikrotikError:
                pass

    queue = state["queues"].get(c.queue_name)
    if cancelled:
        if queue:
            svc.remove_queue(queue["id"])
            state["queues"].pop(c.queue_name, None)
            done.append("cola eliminada")
    elif c.max_limit:
        throttled = suspended and cfg.mode == "throttle"
        params: Dict = {
            "max_limit": f"{cfg.speed}/{cfg.speed}" if throttled else c.max_limit,
            "disabled": False,
            "comment": f"guaynet:{c.id}|{c.name}",
        }
        if not throttled and c.burst_limit:
            params.update(burst_limit=c.burst_limit, burst_threshold=c.burst_threshold, burst_time=c.burst_time)
        if state["sfq"]:
            params["queue_type"] = "guaynet-sfq"
        if state["parent"]:
            params["parent"] = state["parent"]
        if queue:
            target_ok = queue.get("target", "").split(",")[0] in (c.ip, f"{c.ip}/32")
            same = (
                target_ok
                and queue.get("max_limit") == params["max_limit"]
                and not queue.get("disabled")
                and queue.get("comment") == params["comment"]
                and (not state["parent"] or queue.get("parent") == state["parent"])
            )
            if not same:
                svc.update_simple_queue(queue["id"], **params)
                if not target_ok:
                    svc.update_queue_target(c.queue_name, c.ip)
                    done.append(f"cola apuntada a {c.ip}")
                done.append(f"velocidad {params['max_limit']}")
        else:
            svc.add_simple_queue(name=c.queue_name, target=f"{c.ip}/32", **params)
            state["queues"][c.queue_name] = {"name": c.queue_name, "target": f"{c.ip}/32", **params}
            done.append(f"cola creada ({params['max_limit']})")

    # Address-list entries of this client (by IP, or by our comment after an IP change)
    tag = f"guaynet:{c.id}"
    entries = state["suspended_entries"]
    mine = [e for e in entries if e["comment"] == tag or e["address"] == c.ip]
    if block:
        if not state.get("rules_ready"):
            ensure_suspension_rules(svc, cfg)
            state["rules_ready"] = True
        for e in [e for e in mine if e["address"] != c.ip]:
            svc.remove_address_list_entry(e["id"])
            entries.remove(e)
        if not any(e["address"] == c.ip for e in mine):
            svc.add_address_list_entry(SUSPENDED_LIST, c.ip, tag)
            entries.append({"id": "", "address": c.ip, "comment": tag})
            dropped = svc.drop_connections(c.ip)
            done.append(f"bloqueado ({dropped} conexiones cortadas)")
    else:
        for e in mine:
            if e["id"]:
                svc.remove_address_list_entry(e["id"])
            entries.remove(e)
        if mine:
            done.append("desbloqueado")
    return done


# ── Async entry points ──────────────────────────────────────────────────────────

@dataclass
class ProvisionResult:
    ok: bool
    message: str


async def provision_client(
    db: AsyncSession, client: Client, *, timeout: Optional[float] = PROVISION_TIMEOUT
) -> ProvisionResult:
    """Apply one client's state to its router. Never raises: the result says what happened."""
    if not client.router_id:
        return ProvisionResult(False, "El cliente no tiene router asignado")
    router = await db.get(MikrotikRouter, client.router_id)
    if not router:
        return ProvisionResult(False, "Router no encontrado")
    plan = await db.get(Plan, client.plan_id) if client.plan_id else None
    cfg = await load_suspension_config(db)
    snap = snapshot(client, plan)

    def _work() -> List[str]:
        with build_service_from_router(router) as svc:
            return apply_on_router(svc, snap, cfg, router_state(router))

    try:
        job = asyncio.to_thread(_work)
        done = await (asyncio.wait_for(job, timeout) if timeout else job)
        return ProvisionResult(True, "; ".join(done) or "sin cambios")
    except asyncio.TimeoutError:
        logger.warning("MikroTik %s did not answer in %ss for client %s", router.name, timeout, client.id)
        return ProvisionResult(False, f"El router {router.name} no respondió a tiempo: guardado en Guaynet, "
                                      "aplicalo después con «Sincronizar»")
    except Exception as exc:  # MikrotikError, connection errors
        logger.warning("Provisioning client %s on router %s failed: %s", client.id, router.name, exc)
        return ProvisionResult(False, f"No se pudo aplicar en el router {router.name}: {exc}")


async def provision_clients(db: AsyncSession, clients: Iterable[Client]) -> Dict[int, ProvisionResult]:
    """Apply many clients, ONE connection per router (billing jobs, bulk syncs).
    No overall time limit: meant for background jobs."""
    cfg = await load_suspension_config(db)
    by_router: Dict[int, List[ClientSnapshot]] = {}
    results: Dict[int, ProvisionResult] = {}
    for client in clients:
        if not client.router_id:
            results[client.id] = ProvisionResult(False, "sin router")
            continue
        plan = await db.get(Plan, client.plan_id) if client.plan_id else None
        by_router.setdefault(client.router_id, []).append(snapshot(client, plan))

    for router_id, snaps in by_router.items():
        router = await db.get(MikrotikRouter, router_id)
        if not router:
            for s in snaps:
                results[s.id] = ProvisionResult(False, "router no encontrado")
            continue

        def _work(router=router, snaps=snaps) -> Dict[int, ProvisionResult]:
            out: Dict[int, ProvisionResult] = {}
            with build_service_from_router(router) as svc:
                state: Dict = router_state(router)
                for s in snaps:
                    try:
                        out[s.id] = ProvisionResult(True, "; ".join(apply_on_router(svc, s, cfg, state)) or "sin cambios")
                    except MikrotikError as exc:
                        out[s.id] = ProvisionResult(False, str(exc))
            return out

        try:
            results.update(await asyncio.to_thread(_work))
        except Exception as exc:
            logger.warning("Bulk provisioning on router %s failed: %s", router.name, exc)
            for s in snaps:
                results.setdefault(s.id, ProvisionResult(False, f"router {router.name}: {exc}"))
    return results


async def remove_from_router(
    db: AsyncSession, client: Client, router_id: Optional[int] = None,
    *, timeout: Optional[float] = PROVISION_TIMEOUT,
) -> ProvisionResult:
    """Remove the client's queue and suspension entry from a router (cancel, delete,
    or the OLD router when the client moves to another one)."""
    router = await db.get(MikrotikRouter, router_id or client.router_id) if (router_id or client.router_id) else None
    if not router:
        return ProvisionResult(True, "sin router")
    snap = snapshot(client, None)
    snap.status = "cancelled"
    cfg = await load_suspension_config(db)

    def _work() -> List[str]:
        with build_service_from_router(router) as svc:
            return apply_on_router(svc, snap, cfg, router_state(router))

    try:
        job = asyncio.to_thread(_work)
        done = await (asyncio.wait_for(job, timeout) if timeout else job)
        return ProvisionResult(True, "; ".join(done) or "sin cambios")
    except asyncio.TimeoutError:
        return ProvisionResult(False, f"El router {router.name} no respondió a tiempo")
    except Exception as exc:
        logger.warning("Removing client %s from router %s failed: %s", client.id, router.name, exc)
        return ProvisionResult(False, f"No se pudo quitar del router {router.name}: {exc}")
