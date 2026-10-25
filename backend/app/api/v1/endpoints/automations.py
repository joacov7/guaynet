from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.models.automation_log import AutomationLog
from app.models.config import SystemConfig

router = APIRouter()

SETTING_KEYS = [
    "auto_suspend_enabled",
    "auto_suspend_days",
    "auto_invoice_enabled",
    "auto_whatsapp_enabled",
    "whatsapp_reminder_days",
]


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    rows = (await db.execute(select(SystemConfig))).scalars().all()
    config = {r.key: r.value for r in rows}
    return {
        "auto_suspend_enabled": config.get("auto_suspend_enabled", "false") == "true",
        "auto_suspend_days": int(config.get("auto_suspend_days", "30")),
        "auto_invoice_enabled": config.get("auto_invoice_enabled", "false") == "true",
        "auto_whatsapp_enabled": config.get("auto_whatsapp_enabled", "false") == "true",
        "whatsapp_reminder_days": int(config.get("whatsapp_reminder_days", "3")),
    }


class AutomationSettings(BaseModel):
    auto_suspend_enabled: Optional[bool] = None
    auto_suspend_days: Optional[int] = None
    auto_invoice_enabled: Optional[bool] = None
    auto_whatsapp_enabled: Optional[bool] = None
    whatsapp_reminder_days: Optional[int] = None


@router.put("/settings")
async def update_settings(body: AutomationSettings, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    updates: dict[str, str] = {}
    if body.auto_suspend_enabled is not None:
        updates["auto_suspend_enabled"] = "true" if body.auto_suspend_enabled else "false"
    if body.auto_suspend_days is not None:
        updates["auto_suspend_days"] = str(body.auto_suspend_days)
    if body.auto_invoice_enabled is not None:
        updates["auto_invoice_enabled"] = "true" if body.auto_invoice_enabled else "false"
    if body.auto_whatsapp_enabled is not None:
        updates["auto_whatsapp_enabled"] = "true" if body.auto_whatsapp_enabled else "false"
    if body.whatsapp_reminder_days is not None:
        updates["whatsapp_reminder_days"] = str(body.whatsapp_reminder_days)

    for key, value in updates.items():
        existing = (await db.execute(select(SystemConfig).where(SystemConfig.key == key))).scalar_one_or_none()
        if existing:
            existing.value = value
        else:
            db.add(SystemConfig(key=key, value=value))
    await db.commit()
    return await get_settings(db)


class LogResponse(BaseModel):
    id: int
    job: str
    status: str
    message: Optional[str]
    affected: int
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/logs", response_model=List[LogResponse])
async def get_logs(
    job: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    q = select(AutomationLog).order_by(AutomationLog.created_at.desc()).limit(limit)
    if job:
        q = q.where(AutomationLog.job == job)
    return (await db.execute(q)).scalars().all()


VALID_JOBS = {"auto_suspend", "auto_invoice", "whatsapp_reminder"}


@router.post("/run/{job_name}", status_code=202)
async def run_job(job_name: str, background_tasks: BackgroundTasks, _=Depends(require_admin)):
    if job_name not in VALID_JOBS:
        raise HTTPException(status_code=404, detail="Job desconocido")

    from app import scheduler as sched_module
    job_fn = {
        "auto_suspend": sched_module.run_auto_suspend,
        "auto_invoice": sched_module.run_auto_invoice,
        "whatsapp_reminder": sched_module.run_whatsapp_reminder,
    }[job_name]

    background_tasks.add_task(job_fn)
    return {"queued": job_name}
