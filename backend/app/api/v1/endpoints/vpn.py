import base64
import secrets
import string
from typing import List, Optional

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_admin
from app.models.vpn import VpnConnection

router = APIRouter()


def _gen_wg_keypair() -> tuple[str, str]:
    priv = X25519PrivateKey.generate()
    priv_b64 = base64.b64encode(
        priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode()
    pub_b64 = base64.b64encode(
        priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode()
    return priv_b64, pub_b64


def _gen_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class VpnCreate(BaseModel):
    name: str
    vpn_type: str  # wireguard | l2tp
    router_id: Optional[int] = None
    router_name: Optional[str] = None
    # WireGuard
    wg_server_endpoint: Optional[str] = None
    wg_server_port: Optional[int] = 51820
    wg_server_public_key: Optional[str] = None
    wg_client_private_key: Optional[str] = None
    wg_client_public_key: Optional[str] = None
    wg_client_ip: Optional[str] = None
    wg_server_wg_ip: Optional[str] = None
    wg_keepalive: Optional[int] = 25
    # L2TP
    l2tp_server_host: Optional[str] = None
    l2tp_username: Optional[str] = None
    l2tp_password: Optional[str] = None
    l2tp_ipsec_secret: Optional[str] = None
    l2tp_local_ip: Optional[str] = None
    l2tp_remote_ip: Optional[str] = None
    notes: Optional[str] = None


class VpnUpdate(VpnCreate):
    name: Optional[str] = None
    vpn_type: Optional[str] = None


def _row_to_dict(v: VpnConnection) -> dict:
    return {
        "id": v.id,
        "name": v.name,
        "vpn_type": v.vpn_type,
        "router_id": v.router_id,
        "router_name": v.router_name,
        "wg_server_endpoint": v.wg_server_endpoint,
        "wg_server_port": v.wg_server_port,
        "wg_server_public_key": v.wg_server_public_key,
        "wg_client_private_key": v.wg_client_private_key,
        "wg_client_public_key": v.wg_client_public_key,
        "wg_client_ip": v.wg_client_ip,
        "wg_server_wg_ip": v.wg_server_wg_ip,
        "wg_keepalive": v.wg_keepalive,
        "l2tp_server_host": v.l2tp_server_host,
        "l2tp_username": v.l2tp_username,
        "l2tp_password": v.l2tp_password,
        "l2tp_ipsec_secret": v.l2tp_ipsec_secret,
        "l2tp_local_ip": v.l2tp_local_ip,
        "l2tp_remote_ip": v.l2tp_remote_ip,
        "notes": v.notes,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.get("/generate-wg-keys")
async def generate_wg_keys(_=Depends(get_current_user)):
    priv, pub = _gen_wg_keypair()
    return {"private_key": priv, "public_key": pub}


@router.get("/generate-l2tp-creds")
async def generate_l2tp_creds(_=Depends(get_current_user)):
    return {
        "password": _gen_password(16),
        "ipsec_secret": _gen_password(20),
    }


@router.get("/")
async def list_vpn(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rows = (await db.execute(select(VpnConnection).order_by(VpnConnection.id))).scalars().all()
    return [_row_to_dict(r) for r in rows]


@router.post("/", status_code=201)
async def create_vpn(
    body: VpnCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    if body.vpn_type not in ("wireguard", "l2tp"):
        raise HTTPException(400, "vpn_type debe ser 'wireguard' o 'l2tp'")
    vpn = VpnConnection(**body.model_dump())
    db.add(vpn)
    await db.commit()
    await db.refresh(vpn)
    return _row_to_dict(vpn)


@router.put("/{vpn_id}")
async def update_vpn(
    vpn_id: int,
    body: VpnUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    vpn = (await db.execute(select(VpnConnection).where(VpnConnection.id == vpn_id))).scalar_one_or_none()
    if not vpn:
        raise HTTPException(404, "VPN no encontrada")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(vpn, field, value)
    await db.commit()
    await db.refresh(vpn)
    return _row_to_dict(vpn)


@router.delete("/{vpn_id}", status_code=204)
async def delete_vpn(
    vpn_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    vpn = (await db.execute(select(VpnConnection).where(VpnConnection.id == vpn_id))).scalar_one_or_none()
    if not vpn:
        raise HTTPException(404, "VPN no encontrada")
    await db.delete(vpn)
    await db.commit()


@router.get("/{vpn_id}/commands")
async def get_commands(
    vpn_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    vpn = (await db.execute(select(VpnConnection).where(VpnConnection.id == vpn_id))).scalar_one_or_none()
    if not vpn:
        raise HTTPException(404, "VPN no encontrada")

    if vpn.vpn_type == "wireguard":
        iface = f"wg-{vpn.name.lower().replace(' ', '-')}"
        mikrotik = (
            f"/interface wireguard add name={iface} private-key=\"{vpn.wg_client_private_key}\"\n"
            f"/interface wireguard peers add \\\n"
            f"  interface={iface} \\\n"
            f"  public-key=\"{vpn.wg_server_public_key}\" \\\n"
            f"  endpoint-address={vpn.wg_server_endpoint} \\\n"
            f"  endpoint-port={vpn.wg_server_port} \\\n"
            f"  allowed-address=0.0.0.0/0 \\\n"
            f"  persistent-keepalive={vpn.wg_keepalive}s\n"
            f"/ip address add address={vpn.wg_client_ip} interface={iface}\n"
            f"/ip route add dst-address={vpn.wg_server_wg_ip} gateway={iface}"
        )
        server_peer = (
            f"# Agregar al wg0.conf del servidor:\n"
            f"[Peer]\n"
            f"# {vpn.name} ({vpn.router_name or 'router'})\n"
            f"PublicKey = {vpn.wg_client_public_key}\n"
            f"AllowedIPs = {vpn.wg_client_ip}\n\n"
            f"# Luego: sudo wg syncconf wg0 <(wg-quick strip wg0)"
        )
        return {"mikrotik": mikrotik, "server": server_peer}

    else:  # l2tp
        iface = f"l2tp-{vpn.name.lower().replace(' ', '-')}"
        mikrotik = (
            f"/interface l2tp-client add \\\n"
            f"  name={iface} \\\n"
            f"  connect-to={vpn.l2tp_server_host} \\\n"
            f"  user={vpn.l2tp_username} \\\n"
            f"  password={vpn.l2tp_password} \\\n"
            f"  use-ipsec=yes \\\n"
            f"  ipsec-secret={vpn.l2tp_ipsec_secret} \\\n"
            f"  add-default-route=no \\\n"
            f"  disabled=no\n"
            f"/ip address add address={vpn.l2tp_local_ip}/32 interface={iface}"
        )
        server = (
            f"# /etc/ppp/chap-secrets — agregar línea:\n"
            f"{vpn.l2tp_username}  l2tpd  {vpn.l2tp_password}  {vpn.l2tp_remote_ip}\n\n"
            f"# /etc/xl2tpd/xl2tpd.conf — en [lns default]:\n"
            f"ip range = {vpn.l2tp_remote_ip} - {vpn.l2tp_remote_ip}\n"
            f"local ip = {vpn.l2tp_local_ip}\n\n"
            f"# /etc/ipsec.secrets — agregar:\n"
            f"%any  %any  : PSK \"{vpn.l2tp_ipsec_secret}\"\n\n"
            f"# Reiniciar servicios:\n"
            f"sudo systemctl restart strongswan xl2tpd"
        )
        return {"mikrotik": mikrotik, "server": server}
