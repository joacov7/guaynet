from pydantic import BaseModel


class RolePermissionResponse(BaseModel):
    role: str
    section: str
    can_view: bool
    can_edit: bool

    model_config = {"from_attributes": True}


class RolePermissionUpdate(BaseModel):
    can_view: bool
    can_edit: bool


class MyPermissions(BaseModel):
    role: str
    is_admin: bool
    permissions: dict[str, dict[str, bool]]
