from pydantic import BaseModel, EmailStr
from typing import Optional, Any
from datetime import datetime

class LoginIn(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    identifier: Optional[str] = None
    password: str

class RegisterIn(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    identifier: Optional[str] = None
    password: str

class UserOut(BaseModel):
    id: str
    email: Optional[str] = None
    username: Optional[str] = None
    identifier: Optional[str] = None
    role: str
    is_active: bool
    quota_daily: int = 100
    max_file_mb: int = 100
    must_change_password: bool = False
    created_at: datetime
    class Config: from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        return super().from_orm(obj)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    must_change_password: bool = False

class ToolInfo(BaseModel):
    id: str
    name: str
    category: str
    description: str
    accepts: list[str]

class JobCreate(BaseModel):
    tool: str
    params: Optional[dict[str, Any]] = {}

class JobOut(BaseModel):
    id: str
    tool: str
    status: str
    progress: int
    message: str
    params: str
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
    class Config: from_attributes = True

class FileOut(BaseModel):
    id: str
    original_name: str
    mime: Optional[str]
    size: int
    created_at: datetime
    class Config: from_attributes = True
