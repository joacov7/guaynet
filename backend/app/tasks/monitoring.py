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


async def _send_telegram(text: str):
    from app.core.config import settings
    if not settings.TELEGRAM_BOT_TOKEN or not settings.telegram_allowed_ids_list:
        return
    from telegram import Bot
    async with Bot(settings.TELEGRAM_BOT_TOKEN) as bot:
        for chat_id in settings.telegram_allowed_ids_list:
            try:
                await bot.send_message(chat_id=chat_id, text=text)
            except Exception:
                pass


@celery_app.task(name="app.tasks.monitoring.check_routers_health")
def check_routers_health():
    async def _execute():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.router import DeviceStatus, MikrotikRouter
        from app.services.mikrotik import MikrotikError, build_service_from_router

        async with AsyncSessionLocal() as db:
            routers = (await db.execute(select(MikrotikRouter))).scalars().all()

        alerts = []
        for router in routers:
            prev_status = router.status

            def _ping(r=router):
                svc = build_service_from_router(r)
                with svc:
                    return svc.get_system_info()

            try:
                await asyncio.to_thread(_ping)
                new_status = DeviceStatus.online
            except (MikrotikError, Exception):
                new_status = DeviceStatus.offline

            if new_status != prev_status:
                alerts.append((router, prev_status, new_status))

            async with AsyncSessionLocal() as db:
                r = await db.get(MikrotikRouter, router.id)
                if r:
                    r.status = new_status
                    if new_status == DeviceStatus.online:
                        r.last_seen = datetime.now(timezone.utc)
                    db.add(r)
                    await db.commit()

        for router, prev, new in alerts:
            emoji = "✅" if new == DeviceStatus.online else "🔴"
            await _send_telegram(
                f"{emoji} Router *{router.name}* ({router.host}) "
                f"cambió de {prev} a {new}."
            )

        return {"checked": len(routers), "alerts": len(alerts)}

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
