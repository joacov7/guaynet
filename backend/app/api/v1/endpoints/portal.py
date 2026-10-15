"""
Client self-service portal.
Clients are identified by their source IP address — no password required
(the ISP controls the network, so IP ≡ identity on the local network).
"""
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.client import Client
from app.models.invoice import Invoice, InvoiceStatus
from app.models.plan import Plan

router = APIRouter()

_SPEEDTEST_BLOB = os.urandom(5 * 1024 * 1024)  # 5 MB random payload, generated once at startup


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


async def _get_client_by_ip(ip: str, db: AsyncSession) -> Optional[Client]:
    result = await db.execute(select(Client).where(Client.ip_address == ip))
    return result.scalar_one_or_none()


# ── Identify ──────────────────────────────────────────────────────────────────

@router.get("/me")
async def portal_me(request: Request, db: AsyncSession = Depends(get_db)):
    """Return the client record that matches the caller's IP, plus plan and recent invoices."""
    ip = _client_ip(request)
    client = await _get_client_by_ip(ip, db)
    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró ningún cliente registrado para la IP {ip}. "
                   "Si creés que es un error, contactá a tu proveedor.",
        )

    plan = await db.get(Plan, client.plan_id)

    invoices_result = await db.execute(
        select(Invoice)
        .where(Invoice.client_id == client.id)
        .order_by(Invoice.due_date.desc())
        .limit(6)
    )
    invoices = invoices_result.scalars().all()

    return {
        "client": {
            "id": client.id,
            "full_name": client.full_name,
            "ip_address": client.ip_address,
            "status": client.status,
        },
        "plan": {
            "name": plan.name if plan else "—",
            "download_mbps": plan.download_mbps if plan else 0,
            "upload_mbps": plan.upload_mbps if plan else 0,
            "burst_download_mbps": plan.burst_download_mbps if plan else None,
            "burst_upload_mbps": plan.burst_upload_mbps if plan else None,
        } if plan else None,
        "invoices": [
            {
                "id": inv.id,
                "amount": float(inv.amount),
                "status": inv.status,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "period": inv.period if hasattr(inv, "period") else None,
            }
            for inv in invoices
        ],
    }


# ── Speed test ────────────────────────────────────────────────────────────────

@router.get("/speedtest/download")
async def speedtest_download():
    """Returns a fixed 5 MB payload for download speed measurement."""
    return Response(
        content=_SPEEDTEST_BLOB,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "Content-Length": str(len(_SPEEDTEST_BLOB)),
        },
    )


@router.post("/speedtest/upload")
async def speedtest_upload(request: Request):
    """Receives upload payload and returns the number of bytes received."""
    body = await request.body()
    return {"received_bytes": len(body)}
