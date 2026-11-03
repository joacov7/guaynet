from typing import List
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.security import encrypt_value
from app.models.network_controller import NetworkController
from app.schemas.ubiquiti import (
    NetworkControllerCreate,
    NetworkControllerResponse,
    NetworkControllerUpdate,
)

router = APIRouter()


def _validate_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=422,
            detail="La URL debe comenzar con http:// o https:// y contener un host válido",
        )
    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=422,
            detail="No incluyas credenciales dentro de la URL del controlador",
        )
    return value


def _response(controller: NetworkController) -> NetworkControllerResponse:
    # Never expose encrypted credentials or a password through the API.
    return NetworkControllerResponse.model_validate(controller)


@router.get("/", response_model=List[NetworkControllerResponse])
async def list_controllers(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(NetworkController).order_by(NetworkController.name.asc())
    )
    return [_response(item) for item in result.scalars().all()]


@router.post("/", response_model=NetworkControllerResponse, status_code=status.HTTP_201_CREATED)
async def create_controller(
    body: NetworkControllerCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    data = body.model_dump()
    password = data.pop("password", None)
    data["base_url"] = _validate_base_url(data["base_url"])
    data["credentials_encrypted"] = encrypt_value(password) if password else None
    controller = NetworkController(**data)
    db.add(controller)
    await db.commit()
    await db.refresh(controller)
    return _response(controller)


@router.get("/{controller_id}", response_model=NetworkControllerResponse)
async def get_controller(
    controller_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    controller = await db.get(NetworkController, controller_id)
    if controller is None:
        raise HTTPException(status_code=404, detail="Controlador no encontrado")
    return _response(controller)


@router.put("/{controller_id}", response_model=NetworkControllerResponse)
async def update_controller(
    controller_id: int,
    body: NetworkControllerUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    controller = await db.get(NetworkController, controller_id)
    if controller is None:
        raise HTTPException(status_code=404, detail="Controlador no encontrado")

    updates = body.model_dump(exclude_unset=True)
    if "base_url" in updates and updates["base_url"] is not None:
        updates["base_url"] = _validate_base_url(updates["base_url"])
    if "password" in updates:
        password = updates.pop("password")
        if password:
            controller.credentials_encrypted = encrypt_value(password)
    for key, value in updates.items():
        setattr(controller, key, value)

    await db.commit()
    await db.refresh(controller)
    return _response(controller)


@router.delete("/{controller_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_controller(
    controller_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    controller = await db.get(NetworkController, controller_id)
    if controller is None:
        raise HTTPException(status_code=404, detail="Controlador no encontrado")
    await db.delete(controller)
    await db.commit()
