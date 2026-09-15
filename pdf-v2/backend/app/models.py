import uuid, enum
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, Enum, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base

def gen_uuid():
    return str(uuid.uuid4())

class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    USER = "USER"

class JobStatus(str, enum.Enum):
    queued = "queued"
    validating = "validating"
    processing = "processing"
    packaging = "packaging"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=True, index=True)
    username = Column(String, unique=True, nullable=True, index=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String, default=RoleEnum.USER)
    quota_daily = Column(Integer, default=100)
    max_file_mb = Column(Integer, default=100)
    must_change_password = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)

class File(Base):
    __tablename__ = "files"
    id = Column(String, primary_key=True, default=gen_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
    original_name = Column(String, nullable=False)
    stored_name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    mime = Column(String, nullable=True)
    size = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, default=gen_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
    tool = Column(String, nullable=False)
    status = Column(String, default=JobStatus.queued)
    progress = Column(Integer, default=0)
    message = Column(String, default="")
    params = Column(Text, default="{}")
    input_file_id = Column(String, ForeignKey("files.id"), nullable=True)
    output_file_id = Column(String, ForeignKey("files.id"), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)

class SystemSetting(Base):
    __tablename__ = "system_settings"
    id = Column(String, primary_key=True, default=gen_uuid)
    key = Column(String, unique=True)
    value = Column(String)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=gen_uuid)
    actor_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    target = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
