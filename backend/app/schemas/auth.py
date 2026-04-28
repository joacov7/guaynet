from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str = ""
    password: str
    is_superuser: bool = False


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    password: str | None = None


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    username: str
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
