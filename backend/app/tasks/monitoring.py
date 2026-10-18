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

            # Alarm: cpu_high
            try:
                cpu_val = int(str(system_info.get("cpu_load", "0")).replace("%", "") or 0)
            except (ValueError, TypeError):
                cpu_val = 0

            async with AsyncSessionLocal() as db:
                active_cpu = (await db.execute(
                    select(Alarm).where(
                        Alarm.router_id == router.id,
                        Alarm.type == AlarmType.cpu_high,
                        Alarm.status == AlarmStatus.active,
                    )
                )).scalar_one_or_none()

                if cpu_val >= cpu_threshold and not active_cpu:
                    db.add(Alarm(
                        router_id=router.id,
                        type=AlarmType.cpu_high,
                        status=AlarmStatus.active,
                        triggered_at=now,
                        details={"cpu_load": cpu_val, "threshold": cpu_threshold},
                    ))
                    await db.commit()
                    alarm_events.append((router, AlarmType.cpu_high, True, {"cpu_load": cpu_val}))
                elif cpu_val < cpu_threshold and active_cpu:
                    active_cpu.status = AlarmStatus.resolved
                    active_cpu.resolved_at = now
                    db.add(active_cpu)
                    await db.commit()
                    alarm_events.append((router, AlarmType.cpu_high, False, {"cpu_load": cpu_val}))

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
