from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.security.report import SecurityMonthlyReport, SecurityMonthlyReportStatus

router = APIRouter()


class MonthlyReportResponse(BaseModel):
    id: int
    subscription_id: int
    period: str
    status: str
    generated_at: Optional[datetime]
    event_count: int
    alert_count: int
    test_count: int

    class Config:
        from_attributes = True


@router.get("/{subscription_id}/monthly-reports", response_model=List[MonthlyReportResponse])
async def list_monthly_reports(
    subscription_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SecurityMonthlyReport)
        .where(SecurityMonthlyReport.subscription_id == subscription_id)
        .order_by(SecurityMonthlyReport.period.desc())
    )
    return result.scalars().all()


@router.get("/{subscription_id}/monthly-reports/{period}/download")
async def download_monthly_report(
    subscription_id: int,
    period: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SecurityMonthlyReport).where(
            SecurityMonthlyReport.subscription_id == subscription_id,
            SecurityMonthlyReport.period == period,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    if report.status != SecurityMonthlyReportStatus.ready or not report.file_path:
        raise HTTPException(status_code=404, detail="El reporte aún no está disponible")

    import os
    if not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor")

    year_str, month_str = period.split("-")
    filename = f"reporte_seguridad_{subscription_id}_{year_str}_{month_str}.pdf"
    return FileResponse(
        report.file_path,
        media_type="application/pdf",
        filename=filename,
    )
