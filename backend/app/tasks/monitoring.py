"""
Network monitoring tasks.
- check_routers_health: pings all routers, sends Telegram alert on status change.
- collect_bandwidth_samples: snapshots queue byte counters every 5 min.
"""
import asyncio
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app


def _run(coro):
    return asyncio.run(coro)


from app.services.telegram import send_telegram as _send_telegram


@celery_app.task(name="app.tasks.monitoring.check_routers_health")
def check_routers_health():
    async def _execute():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.alarm import Alarm, AlarmStatus, AlarmType
        from app.models.config import SystemConfig
        from app.models.router import DeviceStatus, MikrotikRouter
        from app.services.mikrotik import MikrotikError, build_service_from_router

        now = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as db:
            cfg = (await db.execute(
                select(SystemConfig).where(SystemConfig.key == "cpu_alert_threshold")
            )).scalar_one_or_none()
            cpu_threshold = int(cfg.value) if cfg else 85

        async with AsyncSessionLocal() as db:
            routers = (await db.execute(select(MikrotikRouter))).scalars().all()

        status_changes = []
        alarm_events = []  # (router, alarm_type, is_triggering, details)

        for router in routers:
            prev_status = router.status
            system_info = None
            iface_stats = None

            def _probe(r=router):
                svc = build_service_from_router(r)
                with svc:
                    info = svc.get_system_info()
                    ifaces = svc.get_interface_stats() if r.uplink_interface else []
                    return info, ifaces

            try:
                system_info, iface_stats = await asyncio.to_thread(_probe)
                new_status = DeviceStatus.online
            except (MikrotikError, Exception):
                new_status = DeviceStatus.offline

            async with AsyncSessionLocal() as db:
                r = await db.get(MikrotikRouter, router.id)
                if r:
                    r.status = new_status
                    if new_status == DeviceStatus.online:
                        r.last_seen = now
                    db.add(r)
                    await db.commit()

            if new_status != prev_status:
                status_changes.append((router, prev_status, new_status))

            # Alarm: router_offline
            async with AsyncSessionLocal() as db:
                active_offline = (await db.execute(
                    select(Alarm).where(
                        Alarm.router_id == router.id,
                        Alarm.type == AlarmType.router_offline,
                        Alarm.status == AlarmStatus.active,
                    )
                )).scalar_one_or_none()

                if new_status == DeviceStatus.offline and not active_offline:
                    db.add(Alarm(
                        router_id=router.id,
                        type=AlarmType.router_offline,
                        status=AlarmStatus.active,
                        triggered_at=now,
                        details={"host": router.host},
                    ))
                    await db.commit()
                    alarm_events.append((router, AlarmType.router_offline, True, {}))
                elif new_status == DeviceStatus.online and active_offline:
                    active_offline.status = AlarmStatus.resolved
                    active_offline.resolved_at = now
                    db.add(active_offline)
                    await db.commit()
                    alarm_events.append((router, AlarmType.router_offline, False, {}))

            if system_info is None:
                continue

            # Alarm: cpu_high (streak-based — requires N consecutive high readings)
            try:
                cpu_val = int(str(system_info.get("cpu_load", "0")).replace("%", "") or 0)
            except (ValueError, TypeError):
                cpu_val = 0

            async with AsyncSessionLocal() as db:
                cfg_consec = (await db.execute(
                    select(SystemConfig).where(SystemConfig.key == "cpu_consecutive_checks")
                )).scalar_one_or_none()
                cpu_consecutive_required = max(1, int(cfg_consec.value) if cfg_consec else 2)

                streak_key = f"_cpu_streak_{router.id}"
                streak_cfg = (await db.execute(
                    select(SystemConfig).where(SystemConfig.key == streak_key)
                )).scalar_one_or_none()
                cpu_streak = int(streak_cfg.value) if streak_cfg else 0

                if cpu_val >= cpu_threshold:
                    cpu_streak += 1
                else:
                    cpu_streak = 0

                if streak_cfg:
                    streak_cfg.value = str(cpu_streak)
                    db.add(streak_cfg)
                else:
                    db.add(SystemConfig(key=streak_key, value=str(cpu_streak)))
                await db.commit()

            async with AsyncSessionLocal() as db:
                active_cpu = (await db.execute(
                    select(Alarm).where(
                        Alarm.router_id == router.id,
                        Alarm.type == AlarmType.cpu_high,
                        Alarm.status == AlarmStatus.active,
                    )
                )).scalar_one_or_none()

                if cpu_streak >= cpu_consecutive_required and not active_cpu:
                    db.add(Alarm(
                        router_id=router.id,
                        type=AlarmType.cpu_high,
                        status=AlarmStatus.active,
                        triggered_at=now,
                        details={"cpu_load": cpu_val, "threshold": cpu_threshold, "consecutive": cpu_streak},
                    ))
                    await db.commit()
                    alarm_events.append((router, AlarmType.cpu_high, True, {"cpu_load": cpu_val}))
                elif cpu_streak == 0 and active_cpu:
                    active_cpu.status = AlarmStatus.resolved
                    active_cpu.resolved_at = now
                    db.add(active_cpu)
                    await db.commit()
                    alarm_events.append((router, AlarmType.cpu_high, False, {"cpu_load": cpu_val}))

            # Alarm: ram_high (streak-based — requires N consecutive high readings)
            try:
                free_mem = int(str(system_info.get("free_memory", "0")).replace("KiB", "").replace("MiB", "").strip() or 0)
                total_mem = int(str(system_info.get("total_memory", "1")).replace("KiB", "").replace("MiB", "").strip() or 1)
                free_pct = round(free_mem / total_mem * 100, 1) if total_mem > 0 else 100.0
                free_mb = round(free_mem / 1024, 1)
            except (ValueError, TypeError, ZeroDivisionError):
                free_pct = 100.0
                free_mb = 0.0

            async with AsyncSessionLocal() as db:
                cfg_ram_thresh = (await db.execute(
                    select(SystemConfig).where(SystemConfig.key == "ram_alert_threshold")
                )).scalar_one_or_none()
                ram_threshold_pct = int(cfg_ram_thresh.value) if cfg_ram_thresh else 20

                cfg_ram_consec = (await db.execute(
                    select(SystemConfig).where(SystemConfig.key == "cpu_consecutive_checks")
                )).scalar_one_or_none()
                ram_consecutive_required = max(1, int(cfg_ram_consec.value) if cfg_ram_consec else 2)

                ram_streak_key = f"_ram_streak_{router.id}"
                ram_streak_cfg = (await db.execute(
                    select(SystemConfig).where(SystemConfig.key == ram_streak_key)
                )).scalar_one_or_none()
                ram_streak = int(ram_streak_cfg.value) if ram_streak_cfg else 0

                if free_pct <= ram_threshold_pct:
                    ram_streak += 1
                else:
                    ram_streak = 0

                if ram_streak_cfg:
                    ram_streak_cfg.value = str(ram_streak)
                    db.add(ram_streak_cfg)
                else:
                    db.add(SystemConfig(key=ram_streak_key, value=str(ram_streak)))
                await db.commit()

            async with AsyncSessionLocal() as db:
                active_ram = (await db.execute(
                    select(Alarm).where(
                        Alarm.router_id == router.id,
                        Alarm.type == AlarmType.ram_high,
                        Alarm.status == AlarmStatus.active,
                    )
                )).scalar_one_or_none()

                if ram_streak >= ram_consecutive_required and not active_ram:
                    db.add(Alarm(
                        router_id=router.id,
                        type=AlarmType.ram_high,
                        status=AlarmStatus.active,
                        triggered_at=now,
                        details={"free_pct": free_pct, "free_mb": free_mb, "threshold": ram_threshold_pct},
                    ))
                    await db.commit()
                    alarm_events.append((router, AlarmType.ram_high, True, {"free_pct": free_pct, "free_mb": free_mb}))
                elif ram_streak == 0 and active_ram:
                    active_ram.status = AlarmStatus.resolved
                    active_ram.resolved_at = now
                    db.add(active_ram)
                    await db.commit()
                    alarm_events.append((router, AlarmType.ram_high, False, {"free_pct": free_pct, "free_mb": free_mb}))

            # Alarm: wan_down
            if router.uplink_interface and iface_stats is not None:
                uplink = next(
                    (i for i in iface_stats if i["name"] == router.uplink_interface), None
                )
                wan_is_down = uplink is not None and not uplink["running"]

                async with AsyncSessionLocal() as db:
                    active_wan = (await db.execute(
                        select(Alarm).where(
                            Alarm.router_id == router.id,
                            Alarm.type == AlarmType.wan_down,
                            Alarm.status == AlarmStatus.active,
                        )
                    )).scalar_one_or_none()

                    if wan_is_down and not active_wan:
                        db.add(Alarm(
                            router_id=router.id,
                            type=AlarmType.wan_down,
                            status=AlarmStatus.active,
                            triggered_at=now,
                            details={"interface": router.uplink_interface},
                        ))
                        await db.commit()
                        alarm_events.append((router, AlarmType.wan_down, True, {"interface": router.uplink_interface}))
                    elif not wan_is_down and active_wan:
                        active_wan.status = AlarmStatus.resolved
                        active_wan.resolved_at = now
                        db.add(active_wan)
                        await db.commit()
                        alarm_events.append((router, AlarmType.wan_down, False, {"interface": router.uplink_interface}))

            # Alarm: uplink_saturated
            if (
                router.uplink_interface
                and router.uplink_download_mbps
                and iface_stats is not None
            ):
                uplink = next(
                    (i for i in iface_stats if i["name"] == router.uplink_interface), None
                )
                if uplink:
                    rx_bytes_sec = uplink.get("rx_rate", 0)
                    capacity_bytes_sec = router.uplink_download_mbps * 125_000
                    sat_pct = (rx_bytes_sec / capacity_bytes_sec * 100) if capacity_bytes_sec > 0 else 0

                    async with AsyncSessionLocal() as db:
                        cfg_sat = (await db.execute(
                            select(SystemConfig).where(SystemConfig.key == "uplink_saturation_threshold")
                        )).scalar_one_or_none()
                        sat_threshold = int(cfg_sat.value) if cfg_sat else 90

                        active_sat = (await db.execute(
                            select(Alarm).where(
                                Alarm.router_id == router.id,
                                Alarm.type == AlarmType.uplink_saturated,
                                Alarm.status == AlarmStatus.active,
                            )
                        )).scalar_one_or_none()

                        if sat_pct >= sat_threshold and not active_sat:
                            db.add(Alarm(
                                router_id=router.id,
                                type=AlarmType.uplink_saturated,
                                status=AlarmStatus.active,
                                triggered_at=now,
                                details={
                                    "interface": router.uplink_interface,
                                    "utilization_pct": round(sat_pct, 1),
                                    "threshold": sat_threshold,
                                },
                            ))
                            await db.commit()
                            alarm_events.append((router, AlarmType.uplink_saturated, True, {
                                "utilization_pct": round(sat_pct, 1),
                                "interface": router.uplink_interface,
                            }))
                        elif sat_pct < sat_threshold and active_sat:
                            active_sat.status = AlarmStatus.resolved
                            active_sat.resolved_at = now
                            db.add(active_sat)
                            await db.commit()
                            alarm_events.append((router, AlarmType.uplink_saturated, False, {
                                "utilization_pct": round(sat_pct, 1),
                            }))

        # Telegram notifications for alarms
        type_labels = {
            AlarmType.router_offline: "fuera de línea",
            AlarmType.cpu_high: "CPU alta",
            AlarmType.wan_down: "WAN caída",
            AlarmType.uplink_saturated: "uplink saturado",
            AlarmType.ram_high: "RAM alta",
        }
        for router, atype, is_trigger, details in alarm_events:
            label = type_labels.get(atype, str(atype))
            if is_trigger:
                msg = f"🚨 *Alarma*: Router *{router.name}* ({router.host}) — {label}"
                if atype == AlarmType.cpu_high:
                    msg += f" ({details.get('cpu_load')}%)"
                elif atype == AlarmType.wan_down:
                    msg += f" (interfaz {details.get('interface')})"
                elif atype == AlarmType.uplink_saturated:
                    msg += f" ({details.get('utilization_pct')}% uso en {details.get('interface')})"
                elif atype == AlarmType.ram_high:
                    msg += f" (libre: {details.get('free_pct')}%, {details.get('free_mb')} MB)"
            else:
                msg = f"✅ *Resuelta*: Router *{router.name}* — {label} normalizado"
            await _send_telegram(msg)

        # Email for status changes
        for router, prev, new in status_changes:
            async with AsyncSessionLocal() as db:
                from app.services.email import send_email_alert
                estado = "en línea" if new == DeviceStatus.online else "fuera de línea"
                await send_email_alert(
                    f"Router {router.name} {estado}",
                    f"Router: {router.name}\nHost: {router.host}\nEstado anterior: {prev}\nEstado actual: {new}\n",
                    db,
                )

        return {"checked": len(routers), "alarm_events": len(alarm_events)}

    return _run(_execute())


@celery_app.task(name="app.tasks.monitoring.check_ubiquiti_health")
def check_ubiquiti_health():
    async def _execute():
        from datetime import datetime, timezone
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.alarm import Alarm, AlarmStatus, AlarmType
        from app.models.client import Client, ClientStatus
        from app.models.router import DeviceStatus, UbiquitiDevice

        now = datetime.now(timezone.utc)
        alarm_events = []  # (client_name, device, is_triggering)

        async def _tcp_reachable(host: str, timeout: float = 4.0) -> bool:
            for port in (80, 443, 22):
                try:
                    _, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=timeout
                    )
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    return True
                except Exception:
                    continue
            return False

        # Load all devices assigned to at least one active client
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(UbiquitiDevice, Client)
                .join(Client, Client.ubiquiti_device_id == UbiquitiDevice.id)
                .where(Client.status == ClientStatus.active)
            )).all()
            # unique devices; keep first active client per device
            device_clients: dict[int, tuple] = {}
            for dev, client in rows:
                if dev.id not in device_clients:
                    device_clients[dev.id] = (dev, client)

        # Load all currently active client_device_offline alarms keyed by device_id
        async with AsyncSessionLocal() as db:
            active_alarms: dict[int, Alarm] = {}
            for alarm in (await db.execute(
                select(Alarm).where(
                    Alarm.type == AlarmType.client_device_offline,
                    Alarm.status == AlarmStatus.active,
                )
            )).scalars().all():
                if alarm.details:
                    did = alarm.details.get("device_id")
                    if did is not None:
                        active_alarms[int(did)] = alarm

        for dev_id, (dev, client) in device_clients.items():
            is_reachable = await _tcp_reachable(dev.host)
            new_status = DeviceStatus.online if is_reachable else DeviceStatus.offline

            async with AsyncSessionLocal() as db:
                d = await db.get(UbiquitiDevice, dev.id)
                if d is None:
                    continue
                d.status = new_status
                if new_status == DeviceStatus.online:
                    d.last_seen = now
                db.add(d)
                await db.commit()

            existing_alarm = active_alarms.get(dev_id)
            client_fullname = f"{client.first_name} {client.last_name}"

            if new_status == DeviceStatus.offline and not existing_alarm:
                async with AsyncSessionLocal() as db:
                    db.add(Alarm(
                        router_id=client.router_id,
                        type=AlarmType.client_device_offline,
                        status=AlarmStatus.active,
                        triggered_at=now,
                        details={
                            "client_id": client.id,
                            "client_name": client_fullname,
                            "device_id": dev.id,
                            "device_name": dev.name,
                            "device_host": dev.host,
                        },
                    ))
                    await db.commit()
                alarm_events.append((client_fullname, dev, True))

            elif new_status == DeviceStatus.online and existing_alarm:
                async with AsyncSessionLocal() as db:
                    a = await db.get(Alarm, existing_alarm.id)
                    if a:
                        a.status = AlarmStatus.resolved
                        a.resolved_at = now
                        db.add(a)
                        await db.commit()
                alarm_events.append((client_fullname, dev, False))

        for client_name, device, is_trigger in alarm_events:
            if is_trigger:
                msg = (
                    f"⚠️ *Antena offline — cliente activo sin conexión*\n"
                    f"Cliente: {client_name}\n"
                    f"Antena: {device.name} ({device.host})"
                )
            else:
                msg = (
                    f"✅ *Antena recuperada*\n"
                    f"Cliente: {client_name}\n"
                    f"Antena: {device.name} ({device.host})"
                )
            await _send_telegram(msg)

        return {"devices_checked": len(device_clients), "alarm_events": len(alarm_events)}

    return _run(_execute())


@celery_app.task(name="app.tasks.monitoring.collect_bandwidth_samples")
def collect_bandwidth_samples():
    async def _execute():
        from datetime import datetime, timezone
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.bandwidth import BandwidthSample
        from app.models.client import Client
        from app.models.router import DeviceStatus, MikrotikRouter
        from app.services.mikrotik import MikrotikError, build_service_from_router

        now = datetime.now(timezone.utc)
        total = 0

        async with AsyncSessionLocal() as db:
            routers = (await db.execute(
                select(MikrotikRouter).where(MikrotikRouter.status == DeviceStatus.online)
            )).scalars().all()

            clients = (await db.execute(select(Client))).scalars().all()
            ip_to_client = {c.ip_address: c.id for c in clients}

        for router in routers:
            def _queues(r=router):
                svc = build_service_from_router(r)
                with svc:
                    return svc.get_queues_with_bytes()

            try:
                queues = await asyncio.to_thread(_queues)
            except (MikrotikError, Exception):
                continue

            async with AsyncSessionLocal() as db:
                for q in queues:
                    ip = q.get("target", "").rstrip("/32")
                    sample = BandwidthSample(
                        router_id=router.id,
                        client_id=ip_to_client.get(ip),
                        ip_address=ip,
                        queue_name=q.get("name", ""),
                        upload_bytes=int(q.get("upload_bytes", 0)),
                        download_bytes=int(q.get("download_bytes", 0)),
                        sampled_at=now,
                    )
                    db.add(sample)
                    total += 1
                await db.commit()

        return {"samples_saved": total}

    return _run(_execute())


@celery_app.task(name="app.tasks.monitoring.sample_wan_bytes")
def sample_wan_bytes():
    """Sample WAN interface byte counters and accumulate into DB (delta from last reading)."""
    async def _execute():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.router import MikrotikRouter
        from app.models.wan import WanInterface
        from app.services.mikrotik import MikrotikError, build_service_from_router

        async with AsyncSessionLocal() as db:
            wans = (await db.execute(select(WanInterface))).scalars().all()
            router_ids = list({w.router_id for w in wans})
            routers = {
                r.id: r
                for r in (await db.execute(
                    select(MikrotikRouter).where(MikrotikRouter.id.in_(router_ids))
                )).scalars().all()
            }

        updated = 0
        for wan in wans:
            rt = routers.get(wan.router_id)
            if not rt:
                continue

            def _get_bytes(iface=wan.interface_name, router=rt):
                svc = build_service_from_router(router)
                with svc:
                    return svc.get_interface_bytes(iface)

            try:
                stats = await asyncio.to_thread(_get_bytes)
            except (MikrotikError, Exception):
                continue

            rx = stats.get("rx_byte", 0)
            tx = stats.get("tx_byte", 0)

            async with AsyncSessionLocal() as db:
                w = await db.get(WanInterface, wan.id)
                if w is None:
                    continue
                if w.last_rx_bytes is not None and rx >= w.last_rx_bytes:
                    w.accumulated_rx_bytes = (w.accumulated_rx_bytes or 0) + (rx - w.last_rx_bytes)
                if w.last_tx_bytes is not None and tx >= w.last_tx_bytes:
                    w.accumulated_tx_bytes = (w.accumulated_tx_bytes or 0) + (tx - w.last_tx_bytes)
                w.last_rx_bytes = rx
                w.last_tx_bytes = tx

                # Check cap and disable if exceeded
                if w.cap_gb and w.cap_gb > 0:
                    cap_bytes = w.cap_gb * 1024 ** 3
                    used = (w.accumulated_rx_bytes or 0) + (w.accumulated_tx_bytes or 0)
                    if used >= cap_bytes and w.enabled:
                        def _disable(iface=w.interface_name, router=rt):
                            svc = build_service_from_router(router)
                            with svc:
                                svc.disable_interface(iface)
                        try:
                            await asyncio.to_thread(_disable)
                            w.enabled = False
                        except Exception:
                            pass

                await db.commit()
                updated += 1

        return {"wan_interfaces_sampled": updated}

    return _run(_execute())


@celery_app.task(name="app.tasks.monitoring.reset_wan_counters")
def reset_wan_counters():
    """Reset monthly WAN consumption counters. Run on 1st of each month."""
    async def _execute():
        from sqlalchemy import select, update
        from app.core.database import AsyncSessionLocal
        from app.models.wan import WanInterface

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(WanInterface).values(
                    accumulated_rx_bytes=0,
                    accumulated_tx_bytes=0,
                    last_rx_bytes=None,
                    last_tx_bytes=None,
                )
            )
            await db.commit()

        return {"reset": True}

    return _run(_execute())
