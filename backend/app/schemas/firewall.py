from typing import List, Optional
from pydantic import BaseModel


class DHCPLease(BaseModel):
    address: str
    mac_address: str
    hostname: Optional[str] = None
    comment: Optional[str] = None
    status: str
    is_registered: bool = False
    client_id: Optional[int] = None
    client_name: Optional[str] = None


class DHCPScanResponse(BaseModel):
    total: int
    registered: int
    unregistered: int
    leases: List[DHCPLease]


class FirewallRule(BaseModel):
    id: str
    chain: str
    action: str
    src_address: Optional[str] = None
    dst_address: Optional[str] = None
    protocol: Optional[str] = None
    src_port: Optional[str] = None
    dst_port: Optional[str] = None
    in_interface: Optional[str] = None
    out_interface: Optional[str] = None
    comment: Optional[str] = None
    disabled: bool = False
    bytes: Optional[str] = None
    packets: Optional[str] = None


class MangleRule(BaseModel):
    id: str
    chain: str
    action: str
    new_packet_mark: Optional[str] = None
    new_connection_mark: Optional[str] = None
    src_address: Optional[str] = None
    dst_address: Optional[str] = None
    protocol: Optional[str] = None
    dst_port: Optional[str] = None
    comment: Optional[str] = None
    disabled: bool = False
    passthrough: bool = True


class PCQQueue(BaseModel):
    id: str
    name: str
    kind: str
    pcq_rate: Optional[str] = None
    pcq_limit: Optional[str] = None
    pcq_classifier: Optional[str] = None


class TemplateResult(BaseModel):
    template: str
    rules_added: int
    message: str
