from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VpnConnection(Base, TimestampMixin):
    __tablename__ = "vpn_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    vpn_type: Mapped[str] = mapped_column(String(20))  # wireguard | l2tp
    router_id: Mapped[Optional[int]] = mapped_column(ForeignKey("mikrotik_routers.id", ondelete="SET NULL"), nullable=True)
    router_name: Mapped[Optional[str]] = mapped_column(String(100))

    # WireGuard
    wg_server_endpoint: Mapped[Optional[str]] = mapped_column(String(255))
    wg_server_port: Mapped[Optional[int]] = mapped_column(Integer, default=51820)
    wg_server_public_key: Mapped[Optional[str]] = mapped_column(String(100))
    wg_client_private_key: Mapped[Optional[str]] = mapped_column(String(100))
    wg_client_public_key: Mapped[Optional[str]] = mapped_column(String(100))
    wg_client_ip: Mapped[Optional[str]] = mapped_column(String(50))
    wg_server_wg_ip: Mapped[Optional[str]] = mapped_column(String(50))
    wg_keepalive: Mapped[Optional[int]] = mapped_column(Integer, default=25)

    # L2TP/IPsec
    l2tp_server_host: Mapped[Optional[str]] = mapped_column(String(255))
    l2tp_username: Mapped[Optional[str]] = mapped_column(String(100))
    l2tp_password: Mapped[Optional[str]] = mapped_column(String(100))
    l2tp_ipsec_secret: Mapped[Optional[str]] = mapped_column(String(100))
    l2tp_local_ip: Mapped[Optional[str]] = mapped_column(String(50))
    l2tp_remote_ip: Mapped[Optional[str]] = mapped_column(String(50))

    notes: Mapped[Optional[str]] = mapped_column(Text)
