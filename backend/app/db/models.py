from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, JSON
from datetime import datetime
import uuid
from .database import Base


class CalendarDate(Base):
    """
    日历日期表 — 存储法国学区假期（Zone A/B/C）和法定节假日信息。

    由 calendar_seeder.py 负责初始播种（从 Calendrier.xls）及定期同步（api.gouv.fr）。
    由 DBCalendarProvider 查询，为 GTFS 流水线提供 Type_Jour_Vacances_* 列。
    """
    __tablename__ = "calendar_dates"

    date_gtfs    = Column(String(8), primary_key=True)   # YYYYMMDD
    is_holiday   = Column(Boolean, default=False)        # 法定节假日
    holiday_name = Column(String, nullable=True)         # 节假日名称
    zone_a       = Column(Boolean, default=False)        # Zone A 学区放假
    zone_b       = Column(Boolean, default=False)        # Zone B 学区放假
    zone_c       = Column(Boolean, default=False)        # Zone C 学区放假
    updated_at   = Column(DateTime, default=datetime.utcnow)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    plan = Column(String, default="free")  # free / pro / enterprise
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    role = Column(String, default="member")  # admin / member
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, default="pending")  # pending, processing, completed, failed
    parameters = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(String, nullable=True)
    output_path = Column(String, nullable=True)  # R2 key 或本地路径
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
