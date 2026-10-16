import asyncio
import csv
import io
import ipaddress
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.security import encrypt_value
from app.models.client import Client
from app.models.router import DeviceStatus, MikrotikRouter, UbiquitiDevice
from app.schemas.ubiquiti import (
    DeviceInfo,
    DiscoverRequest,
    DiscoveredDevice,
    FrequencyRecommendation,
    LinkInfo,
    StationInfo,
    SurveyScan,
    UbiquitiDeviceCreate,
    UbiquitiDeviceResponse,
    UbiquitiDeviceUpdate,
    WirelessConfig,
    WirelessUpdate,
)
from app.services.ubiquiti import UbiquitiError, build_service_from_device, quick_probe

router = APIRouter()


async def _device_response(dev: UbiquitiDevice, db: AsyncSession) -> UbiquitiDeviceResponse:
    count = (
        await db.execute(select(func.count()).where(Client.ubiquiti_device_id == dev.id))
    ).scalar_one()
    data = UbiquitiDeviceResponse.model_validate(dev)
    data.client_count = count
    return data


async def _get_or_404(device_id: int, db: AsyncSession) -> UbiquitiDevice:
    dev = await db.get(UbiquitiDevice, device_id)
    if not dev:
        raise HTTPException(404, "Dispositivo no encontrado")
    return dev


# ── Discovery ─────────────────────────────────────────────────────────────────

@router.post("/discover", response_model=List[DiscoveredDevice])
async def discover_devices(
    body: DiscoverRequest,
    _=Depends(get_current_user),
):
    """Scan a subnet for Ubiquiti devices. Max /24 (254 hosts)."""
    try:
        network = ipaddress.ip_network(body.subnet, strict=False)
    except ValueError:
        raise HTTPException(400, "Subred inválida. Usá formato CIDR como 192.168.1.0/24")

    if network.num_addresses > 256:
        raise HTTPException(400, "Subred demasiado grande. Máximo /24 (254 hosts)")

    hosts = list(network.hosts())
    sem = asyncio.Semaphore(30)

    async def probe(ip: str):
        async with sem:
            return await asyncio.to_thread(quick_probe, ip, body.username, body.password)

    results = await asyncio.gather(*[probe(str(ip)) for ip in hosts])
    return [DiscoveredDevice(**r) for r in results if r is not None]


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[UbiquitiDeviceResponse])
async def list_devices(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(UbiquitiDevice).order_by(UbiquitiDevice.name))
    return [await _device_response(d, db) for d in result.scalars().all()]


@router.post("/import")
async def import_devices_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Bulk import Ubiquiti devices from a CSV file.
    Expected columns: nombre, host, tipo, usuario, contraseña
    Optional columns: ubicacion, router_id, latitud, longitud
    """
    content = (await file.read()).decode("utf-8-sig")  # utf-8-sig strips BOM
    reader = csv.DictReader(io.StringIO(content))

    VALID_TYPES = {"airmax_ap", "airmax_station", "airmax_ac_ap", "airmax_ac_station",
                   "unifi_ap", "unifi_switch", "unifi_gateway"}

    created = 0
    errors = []

    for i, row in enumerate(reader, start=2):  # row 1 = header
        nombre = (row.get("nombre") or row.get("name") or "").strip()
        host = (row.get("host") or row.get("ip") or "").strip()
        tipo = (row.get("tipo") or row.get("type") or "airmax_ac_ap").strip()
        usuario = (row.get("usuario") or row.get("username") or "ubnt").strip()
        password = (row.get("contraseña") or row.get("password") or "ubnt").strip()
        ubicacion = (row.get("ubicacion") or row.get("location") or "").strip() or None
        router_id_s = (row.get("router_id") or "").strip()

        if not nombre:
            errors.append({"row": i, "error": "Falta el nombre"})
            continue
        if not host:
            errors.append({"row": i, "error": "Falta el host/IP"})
            continue
        if tipo not in VALID_TYPES:
            errors.append({"row": i, "error": f"Tipo inválido: {tipo}"})
            continue

        router_id = None
        if router_id_s:
            try:
                router_id = int(router_id_s)
            except ValueError:
                errors.append({"row": i, "error": f"router_id inválido: {router_id_s}"})
                continue

        try:
            dev = UbiquitiDevice(
                name=nombre,
                host=host,
                device_type=tipo,
                username=usuario,
                password_encrypted=encrypt_value(password) if password else None,
                location=ubicacion,
                router_id=router_id,
                status=DeviceStatus.unknown,
            )
            db.add(dev)
            await db.flush()
            created += 1
        except Exception as e:
            errors.append({"row": i, "error": str(e)})

    await db.commit()
    return {"created": created, "errors": errors}


@router.post("/", response_model=UbiquitiDeviceResponse, status_code=201)
async def create_device(
    body: UbiquitiDeviceCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    data = body.model_dump()
    pw = data.pop("password", None)
    dev = UbiquitiDevice(**data)
    if pw:
        dev.password_encrypted = encrypt_value(pw)
    db.add(dev)
    await db.commit()
    await db.refresh(dev)
    return await _device_response(dev, db)


@router.get("/{device_id}", response_model=UbiquitiDeviceResponse)
async def get_device(device_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    return await _device_response(await _get_or_404(device_id, db), db)


@router.put("/{device_id}", response_model=UbiquitiDeviceResponse)
async def update_device(
    device_id: int,
    body: UbiquitiDeviceUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    dev = await _get_or_404(device_id, db)
    updates = body.model_dump(exclude_unset=True)
    if "password" in updates:
        pw = updates.pop("password")
        dev.password_encrypted = encrypt_value(pw) if pw else dev.password_encrypted
    for k, v in updates.items():
        setattr(dev, k, v)
    db.add(dev)
    await db.commit()
    await db.refresh(dev)
    return await _device_response(dev, db)


@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    dev = await _get_or_404(device_id, db)
    await db.delete(dev)
    await db.commit()


# ── Live data ─────────────────────────────────────────────────────────────────

@router.post("/{device_id}/test", response_model=UbiquitiDeviceResponse)
async def test_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    dev = await _get_or_404(device_id, db)
    svc = build_service_from_device(dev)

    def _test():
        with svc:
            info = svc.get_device_info()
            wireless = svc.get_wireless()
            link = None
            try:
                link = svc.get_link()
            except UbiquitiError:
                pass
            return info, wireless, link

    try:
        info, wireless, link = await asyncio.to_thread(_test)
        dev.status = DeviceStatus.online
        dev.last_seen = datetime.now(timezone.utc)
        dev.model_name = info.get("model") or dev.model_name
        dev.firmware_version = info.get("firmware") or dev.firmware_version
        dev.ssid = wireless.get("ssid") or dev.ssid
        dev.frequency_mhz = wireless.get("frequency_mhz") or dev.frequency_mhz
        dev.channel_width_mhz = wireless.get("channel_width_mhz") or dev.channel_width_mhz
        if link:
            dev.signal_dbm = link.get("signal_dbm")
            dev.ccq = link.get("ccq")
    except UbiquitiError as e:
        dev.status = DeviceStatus.offline
        db.add(dev)
        await db.commit()
        raise HTTPException(503, str(e))

    db.add(dev)
    await db.commit()
    await db.refresh(dev)
    return await _device_response(dev, db)


@router.get("/{device_id}/info", response_model=DeviceInfo)
async def get_device_info(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    dev = await _get_or_404(device_id, db)
    svc = build_service_from_device(dev)

    def _get():
        with svc:
            return svc.get_device_info()

    try:
        return DeviceInfo(**await asyncio.to_thread(_get))
    except UbiquitiError as e:
        raise HTTPException(503, str(e))


@router.get("/{device_id}/wireless", response_model=WirelessConfig)
async def get_wireless(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    dev = await _get_or_404(device_id, db)
    svc = build_service_from_device(dev)

    def _get():
        with svc:
            return svc.get_wireless()

    try:
        return WirelessConfig(**await asyncio.to_thread(_get))
    except UbiquitiError as e:
        raise HTTPException(503, str(e))


@router.put("/{device_id}/wireless", response_model=WirelessConfig)
async def set_wireless(
    device_id: int,
    body: WirelessUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    dev = await _get_or_404(device_id, db)
    svc = build_service_from_device(dev)

    def _set():
        with svc:
            svc.set_wireless(
                frequency_mhz=body.frequency_mhz,
                channel_width_mhz=body.channel_width_mhz,
                tx_power_dbm=body.tx_power_dbm,
            )
            return svc.get_wireless()

    try:
        result = await asyncio.to_thread(_set)
        # Update cached values
        dev.frequency_mhz = result.get("frequency_mhz") or body.frequency_mhz
        dev.channel_width_mhz = result.get("channel_width_mhz") or body.channel_width_mhz
        db.add(dev)
        await db.commit()
        return WirelessConfig(**result)
    except UbiquitiError as e:
        raise HTTPException(503, str(e))


@router.get("/{device_id}/link", response_model=LinkInfo)
async def get_link(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    dev = await _get_or_404(device_id, db)
    svc = build_service_from_device(dev)

    def _get():
        with svc:
            return svc.get_link()

    try:
        return LinkInfo(**await asyncio.to_thread(_get))
    except UbiquitiError as e:
        raise HTTPException(503, str(e))


@router.get("/{device_id}/stations", response_model=List[StationInfo])
async def get_stations(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    dev = await _get_or_404(device_id, db)
    svc = build_service_from_device(dev)

    def _get():
        with svc:
            return svc.get_stations()

    try:
        return [StationInfo(**s) for s in await asyncio.to_thread(_get)]
    except UbiquitiError as e:
        raise HTTPException(503, str(e))


@router.get("/{device_id}/survey", response_model=List[SurveyScan])
async def site_survey(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    dev = await _get_or_404(device_id, db)
    svc = build_service_from_device(dev)

    def _get():
        with svc:
            return svc.site_survey()

    try:
        return [SurveyScan(**n) for n in await asyncio.to_thread(_get)]
    except UbiquitiError as e:
        raise HTTPException(503, str(e))


@router.get("/{device_id}/recommendations", response_model=List[FrequencyRecommendation])
async def get_recommendations(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    dev = await _get_or_404(device_id, db)
    svc = build_service_from_device(dev)

    def _get():
        with svc:
            return svc.recommend_frequencies()

    try:
        return [FrequencyRecommendation(**r) for r in await asyncio.to_thread(_get)]
    except UbiquitiError as e:
        raise HTTPException(503, str(e))


@router.post("/{device_id}/firmware")
async def upload_firmware(
    device_id: int,
    firmware: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    dev = await _get_or_404(device_id, db)
    svc = build_service_from_device(dev)
    firmware_bytes = await firmware.read()
    filename = firmware.filename or "firmware.bin"

    def _upload():
        with svc:
            return svc.upload_firmware(firmware_bytes, filename)

    try:
        return await asyncio.to_thread(_upload)
    except UbiquitiError as e:
        raise HTTPException(503, str(e))


@router.get("/{device_id}/clients")
async def get_device_clients(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Clients in DB linked to this Ubiquiti device."""
    await _get_or_404(device_id, db)
    result = await db.execute(
        select(Client).where(Client.ubiquiti_device_id == device_id)
    )
    clients = result.scalars().all()
    return [
        {
            "id": c.id,
            "full_name": c.full_name,
            "ip_address": c.ip_address,
            "mac_address": c.mac_address,
            "status": c.status,
        }
        for c in clients
    ]
