from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from datetime import datetime


class TenantCreate(BaseModel):
    name: str


class TenantResponse(BaseModel):
    id: str
    name: str
    plan: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    tenant_name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    tenant_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: str | None = None
