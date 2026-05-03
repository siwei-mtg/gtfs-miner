from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, JSON
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
    reseau = Column(String, nullable=True)
    validite_debut = Column(Integer, nullable=True)  # YYYYMMDD
    validite_fin = Column(Integer, nullable=True)  # YYYYMMDD


class ProgressEvent(Base):
    """
    Trace durable des événements de progression émis par le worker pendant
    l'exécution du pipeline GTFS.

    Rejouée à chaque nouvelle connexion WebSocket (`/api/v1/projects/{id}/ws`)
    pour qu'un utilisateur revenant sur un projet — en cours ou terminé —
    retrouve l'intégralité de l'historique (steps faits, step courant, durées)
    au lieu de repartir d'un état vide.
    """
    __tablename__ = "progress_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq = Column(Integer, nullable=False)  # ordre strict par project_id
    status = Column(String, nullable=False)  # pending / processing / completed / failed
    step = Column(String, nullable=False)  # ex: "[3/9] Spatial clustering…"
    time_elapsed = Column(Float, nullable=False)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_progress_events_project_seq", "project_id", "seq"),
    )


# ────────────────────────────────────────────────────────
# compare-transit.fr panel models — spec §6.3
# ────────────────────────────────────────────────────────


class PanelNetwork(Base):
    """One row per French AOM / GTFS dataset on PAN — spec §6.3."""
    __tablename__ = "panel_networks"

    network_id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slug                 = Column(String, unique=True, index=True, nullable=False)
    pan_dataset_id       = Column(String, unique=True, index=True, nullable=False)
    display_name         = Column(String, nullable=False)
    aom_id               = Column(String, index=True)
    tier                 = Column(String, index=True)            # T1/T2/T3/T4/T5/R/I
    population           = Column(Integer)
    area_km2             = Column(Float)
    first_feed_date      = Column(DateTime)
    last_feed_date       = Column(DateTime)
    history_depth_months = Column(Integer)
    created_at           = Column(DateTime, default=datetime.utcnow)
    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PanelFeed(Base):
    """One row per *distinct* feed (after dedup-by-feed_start_date) — spec §6.3."""
    __tablename__ = "panel_feeds"

    feed_id                 = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    network_id              = Column(String, ForeignKey("panel_networks.network_id"), index=True, nullable=False)
    pan_resource_id         = Column(String, index=True, nullable=False)             # latest representative resource
    pan_resource_history_id = Column(String, index=True)                              # resource_history_id from PAN CSV
    published_at            = Column(DateTime, nullable=False, index=True)            # PAN inserted_at
    feed_start_date         = Column(DateTime, nullable=False, index=True)            # dedup key
    feed_end_date           = Column(DateTime)
    feed_info_sha256        = Column(String, index=True)                              # sig_sha — feed_info.txt hash
    feed_info_source        = Column(String)                                          # 'feed_info' | 'calendar' | 'calendar_dates'
    gtfs_url                = Column(String, nullable=False)                          # permanent_url
    r2_path                 = Column(String)
    checksum_sha256         = Column(String)                                          # ZIP-level sha256
    filesize                = Column(Integer)
    process_status          = Column(String, default="pending", index=True)
    process_duration_s      = Column(Float)
    error_message           = Column(String)
    created_at              = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ux_panel_feeds_network_fsd", "network_id", "feed_start_date", unique=True),
    )


class PanelIndicator(Base):
    """Computed indicator value per (feed, indicator_id) — spec §6.3."""
    __tablename__ = "panel_indicators"

    feed_id      = Column(String, ForeignKey("panel_feeds.feed_id"), primary_key=True)
    indicator_id = Column(String, primary_key=True, index=True)
    value        = Column(Float)
    unit         = Column(String, nullable=False)
    computed_at  = Column(DateTime, default=datetime.utcnow)


class PanelIndicatorDerived(Base):
    """Z-score, percentile, YoY delta per (feed, indicator_id) — spec §5.2."""
    __tablename__ = "panel_indicators_derived"

    feed_id          = Column(String, ForeignKey("panel_feeds.feed_id"), primary_key=True)
    indicator_id     = Column(String, primary_key=True, index=True)
    zscore           = Column(Float)
    percentile       = Column(Float)
    yoy_delta_pct    = Column(Float)
    peer_group_size  = Column(Integer)
    computed_at      = Column(DateTime, default=datetime.utcnow)


class PanelQuality(Base):
    """GTFS validator output + overall quality grade per feed — spec §5.1 G."""
    __tablename__ = "panel_quality"

    feed_id          = Column(String, ForeignKey("panel_feeds.feed_id"), primary_key=True)
    validator_errors = Column(JSON)                      # full MobilityData report
    overall_grade    = Column(String)                    # A+/A/A-/.../F
    overall_score    = Column(Float)                     # 0–100
    computed_at      = Column(DateTime, default=datetime.utcnow)


class PanelPeerGroup(Base):
    """Tier definition metadata — spec §5.3."""
    __tablename__ = "panel_peer_groups"

    group_id     = Column(String, primary_key=True)      # T1/T2/T3/T4/T5/R/I
    display_name = Column(String, nullable=False)
    definition   = Column(JSON)
    member_count = Column(Integer, default=0)
