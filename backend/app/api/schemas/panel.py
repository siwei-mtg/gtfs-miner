"""Pydantic v2 response schemas for ``/api/v1/panel/*`` — spec §8.

Audit-grade payloads (v0.2): every numeric indicator carries unit,
methodology commit (with permalink), error margin and provenance feed_id.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IndicatorValueOut(BaseModel):
    """Audit-grade indicator value per spec §8.2 v0.2."""

    value: float | None
    unit: str
    error_margin_pct: float | None
    source_feed_id: str | None
    computed_at: datetime | None
    methodology_commit: str | None
    methodology_url: str | None = Field(
        None,
        description="GitHub permalink to the formula at methodology_commit",
    )


class NetworkSummary(BaseModel):
    slug: str
    display_name: str
    tier: str | None
    population: int | None
    area_km2: float | None
    history_depth_months: int | None
    last_feed_date: datetime | None


class NetworkListOut(BaseModel):
    networks: list[NetworkSummary]
    total: int


class NetworkDetailOut(NetworkSummary):
    indicators: dict[str, IndicatorValueOut] = {}
    quality_grade: str | None = None
    quality_score: float | None = None


class HistoryPointOut(BaseModel):
    feed_start_date: datetime
    indicator_id: str
    value: float | None


class HistoryOut(BaseModel):
    slug: str
    points: list[HistoryPointOut]


class PeerOut(BaseModel):
    slug: str
    display_name: str
    rank: int  # 1-based, in same tier
    indicator_value: float | None


class PeersOut(BaseModel):
    slug: str
    tier: str | None
    peers_by_indicator: dict[str, list[PeerOut]] = {}


class QualityDetailOut(BaseModel):
    slug: str
    overall_score: float | None
    overall_grade: str | None
    dq_indicators: dict[str, IndicatorValueOut] = {}


class IndicatorRankingOut(BaseModel):
    indicator_id: str
    rankings: list[dict[str, Any]]   # {slug, display_name, value, rank}


class QualityRankingOut(BaseModel):
    rankings: list[dict[str, Any]]   # {slug, display_name, score, grade}


class PeerGroupOut(BaseModel):
    group_id: str
    display_name: str
    member_count: int


class PeerGroupListOut(BaseModel):
    groups: list[PeerGroupOut]


# v0.2 additions ────────────────────────────────────────────────────────────


class DspEventOut(BaseModel):
    event_id: str
    event_type: str
    event_date: datetime
    operator_before: str | None
    operator_after: str | None
    contract_id: str | None
    contract_value_eur: float | None
    boamp_url: str | None
    notes: str | None
    source: str


class DspEventsOut(BaseModel):
    slug: str
    events: list[DspEventOut]


class ReorgEventOut(BaseModel):
    network_slug: str
    feed_to_id: str
    reorg_severity: str | None
    stop_jaccard: float | None
    route_jaccard: float | None
    detected_at: datetime | None


class ReorgEventsOut(BaseModel):
    slug: str | None
    events: list[ReorgEventOut]


class FeedDiffOut(BaseModel):
    feed_from_id: str
    feed_to_id: str
    stops_added: list[str] = []
    stops_removed: list[str] = []
    routes_added: list[str] = []
    routes_removed: list[str] = []
    stop_jaccard: float | None
    route_jaccard: float | None
