"""Panel API endpoints — compare-transit Plan 2 spec §8.

Public, no auth. CORS open. Cache headers: ``public, max-age=3600,
s-maxage=86400`` so the CDN can absorb the long tail.

13 endpoints (8 v0.1 + 5 v0.2 audit-grade) under ``/api/v1/panel/``.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.schemas.panel import (
    DspEventOut,
    DspEventsOut,
    FeedDiffOut,
    HistoryOut,
    HistoryPointOut,
    IndicatorRankingOut,
    IndicatorValueOut,
    NetworkDetailOut,
    NetworkListOut,
    NetworkSummary,
    PeerGroupListOut,
    PeerGroupOut,
    PeerOut,
    PeersOut,
    QualityDetailOut,
    QualityRankingOut,
    ReorgEventOut,
    ReorgEventsOut,
)
from app.db.database import get_db
from app.db.models import (
    PanelDspEvent,
    PanelFeed,
    PanelFeedDiff,
    PanelIndicator,
    PanelNetwork,
    PanelPeerGroup,
    PanelQuality,
    PanelReorgFlag,
)


router = APIRouter()

CACHE_HEADERS = {"Cache-Control": "public, max-age=3600, s-maxage=86400"}
METHODOLOGY_REPO_URL = "https://github.com/compare-transit/methodology"


def _methodology_url(indicator_id: str, commit: str | None) -> str | None:
    if not commit or commit == "unknown":
        return None
    return (
        f"{METHODOLOGY_REPO_URL}/blob/{commit}/indicators_formulas/"
        f"{indicator_id}.py"
    )


def _indicator_to_out(ind: PanelIndicator) -> IndicatorValueOut:
    return IndicatorValueOut(
        value=ind.value,
        unit=ind.unit,
        error_margin_pct=ind.error_margin_pct,
        source_feed_id=ind.feed_id,
        computed_at=ind.computed_at,
        methodology_commit=ind.methodology_commit,
        methodology_url=_methodology_url(ind.indicator_id, ind.methodology_commit),
    )


@router.get("/networks", response_model=NetworkListOut)
def list_networks(
    response: Response,
    tier: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> NetworkListOut:
    response.headers.update(CACHE_HEADERS)
    q = db.query(PanelNetwork)
    if tier:
        q = q.filter(PanelNetwork.tier == tier)
    total = q.count()
    rows = q.order_by(PanelNetwork.slug).offset(offset).limit(limit).all()
    return NetworkListOut(
        networks=[
            NetworkSummary(
                slug=r.slug,
                display_name=r.display_name,
                tier=r.tier,
                population=r.population,
                area_km2=r.area_km2,
                history_depth_months=r.history_depth_months,
                last_feed_date=r.last_feed_date,
            )
            for r in rows
        ],
        total=total,
    )


@router.get("/networks/{slug}", response_model=NetworkDetailOut)
def network_detail(
    slug: str, response: Response, db: Session = Depends(get_db)
) -> NetworkDetailOut:
    response.headers.update(CACHE_HEADERS)
    n = db.query(PanelNetwork).filter_by(slug=slug).one_or_none()
    if n is None:
        raise HTTPException(status_code=404, detail=f"network not found: {slug}")
    latest = (
        db.query(PanelFeed)
        .filter_by(network_id=n.network_id)
        .order_by(PanelFeed.feed_start_date.desc())
        .first()
    )
    indicators: dict[str, IndicatorValueOut] = {}
    quality_grade: str | None = None
    quality_score: float | None = None
    if latest:
        for ind in db.query(PanelIndicator).filter_by(feed_id=latest.feed_id):
            indicators[ind.indicator_id] = _indicator_to_out(ind)
        q = (
            db.query(PanelQuality)
            .filter_by(feed_id=latest.feed_id)
            .one_or_none()
        )
        if q:
            quality_grade = q.overall_grade
            quality_score = q.overall_score
    return NetworkDetailOut(
        slug=n.slug,
        display_name=n.display_name,
        tier=n.tier,
        population=n.population,
        area_km2=n.area_km2,
        history_depth_months=n.history_depth_months,
        last_feed_date=n.last_feed_date,
        indicators=indicators,
        quality_grade=quality_grade,
        quality_score=quality_score,
    )


@router.get("/networks/{slug}/history", response_model=HistoryOut)
def network_history(
    slug: str,
    response: Response,
    indicator_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> HistoryOut:
    response.headers.update(CACHE_HEADERS)
    n = db.query(PanelNetwork).filter_by(slug=slug).one_or_none()
    if n is None:
        raise HTTPException(404, f"network not found: {slug}")
    feed_ids = [
        f.feed_id
        for f in db.query(PanelFeed).filter_by(network_id=n.network_id)
    ]
    if not feed_ids:
        return HistoryOut(slug=slug, points=[])
    q = (
        db.query(PanelIndicator, PanelFeed.feed_start_date)
        .join(PanelFeed, PanelIndicator.feed_id == PanelFeed.feed_id)
        .filter(PanelFeed.feed_id.in_(feed_ids))
    )
    if indicator_id:
        q = q.filter(PanelIndicator.indicator_id == indicator_id)
    points: list[HistoryPointOut] = []
    for ind, fsd in q.order_by(PanelFeed.feed_start_date):
        points.append(
            HistoryPointOut(
                feed_start_date=fsd,
                indicator_id=ind.indicator_id,
                value=ind.value,
            )
        )
    return HistoryOut(slug=slug, points=points)


@router.get("/networks/{slug}/peers", response_model=PeersOut)
def network_peers(
    slug: str, response: Response, db: Session = Depends(get_db)
) -> PeersOut:
    response.headers.update(CACHE_HEADERS)
    n = db.query(PanelNetwork).filter_by(slug=slug).one_or_none()
    if n is None:
        raise HTTPException(404, f"network not found: {slug}")
    if not n.tier:
        return PeersOut(slug=slug, tier=None, peers_by_indicator={})
    peers = db.query(PanelNetwork).filter(PanelNetwork.tier == n.tier).all()
    return PeersOut(
        slug=slug,
        tier=n.tier,
        peers_by_indicator={
            "prod_kcc_year": [
                PeerOut(
                    slug=p.slug,
                    display_name=p.display_name,
                    rank=i + 1,
                    indicator_value=None,
                )
                for i, p in enumerate(peers)
            ]
        },
    )


@router.get("/networks/{slug}/quality", response_model=QualityDetailOut)
def network_quality(
    slug: str, response: Response, db: Session = Depends(get_db)
) -> QualityDetailOut:
    response.headers.update(CACHE_HEADERS)
    n = db.query(PanelNetwork).filter_by(slug=slug).one_or_none()
    if n is None:
        raise HTTPException(404, f"network not found: {slug}")
    latest = (
        db.query(PanelFeed)
        .filter_by(network_id=n.network_id)
        .order_by(PanelFeed.feed_start_date.desc())
        .first()
    )
    if latest is None:
        return QualityDetailOut(
            slug=slug, overall_score=None, overall_grade=None
        )
    q = (
        db.query(PanelQuality)
        .filter_by(feed_id=latest.feed_id)
        .one_or_none()
    )
    dq_inds: dict[str, IndicatorValueOut] = {}
    for ind in db.query(PanelIndicator).filter(
        PanelIndicator.feed_id == latest.feed_id,
        PanelIndicator.indicator_id.like("dq_%"),
    ):
        dq_inds[ind.indicator_id] = _indicator_to_out(ind)
    return QualityDetailOut(
        slug=slug,
        overall_score=q.overall_score if q else None,
        overall_grade=q.overall_grade if q else None,
        dq_indicators=dq_inds,
    )


@router.get(
    "/indicators/{indicator_id}/ranking", response_model=IndicatorRankingOut
)
def indicator_ranking(
    indicator_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> IndicatorRankingOut:
    response.headers.update(CACHE_HEADERS)
    rankings: list[dict] = []
    for n in db.query(PanelNetwork):
        latest = (
            db.query(PanelFeed)
            .filter_by(network_id=n.network_id)
            .order_by(PanelFeed.feed_start_date.desc())
            .first()
        )
        if not latest:
            continue
        ind = (
            db.query(PanelIndicator)
            .filter_by(feed_id=latest.feed_id, indicator_id=indicator_id)
            .one_or_none()
        )
        if ind and ind.value is not None:
            rankings.append(
                {
                    "slug": n.slug,
                    "display_name": n.display_name,
                    "value": ind.value,
                }
            )
    rankings.sort(key=lambda r: r["value"], reverse=True)
    for i, r in enumerate(rankings):
        r["rank"] = i + 1
    return IndicatorRankingOut(indicator_id=indicator_id, rankings=rankings)


@router.get("/quality/ranking", response_model=QualityRankingOut)
def quality_ranking(
    response: Response, db: Session = Depends(get_db)
) -> QualityRankingOut:
    response.headers.update(CACHE_HEADERS)
    rankings: list[dict] = []
    for n in db.query(PanelNetwork):
        latest = (
            db.query(PanelFeed)
            .filter_by(network_id=n.network_id)
            .order_by(PanelFeed.feed_start_date.desc())
            .first()
        )
        if not latest:
            continue
        q = (
            db.query(PanelQuality)
            .filter_by(feed_id=latest.feed_id)
            .one_or_none()
        )
        if q and q.overall_score is not None:
            rankings.append(
                {
                    "slug": n.slug,
                    "display_name": n.display_name,
                    "score": q.overall_score,
                    "grade": q.overall_grade,
                }
            )
    rankings.sort(key=lambda r: r["score"], reverse=True)
    return QualityRankingOut(rankings=rankings)


@router.get("/peer-groups", response_model=PeerGroupListOut)
def peer_groups(
    response: Response, db: Session = Depends(get_db)
) -> PeerGroupListOut:
    response.headers.update(CACHE_HEADERS)
    return PeerGroupListOut(
        groups=[
            PeerGroupOut(
                group_id=pg.group_id,
                display_name=pg.display_name,
                member_count=pg.member_count or 0,
            )
            for pg in db.query(PanelPeerGroup)
        ]
    )


# ── v0.2 additions ────────────────────────────────────────────────────────


@router.get(
    "/networks/{slug}/dsp-events", response_model=DspEventsOut
)
def network_dsp_events(
    slug: str, response: Response, db: Session = Depends(get_db)
) -> DspEventsOut:
    response.headers.update(CACHE_HEADERS)
    n = db.query(PanelNetwork).filter_by(slug=slug).one_or_none()
    if n is None:
        raise HTTPException(404, f"network not found: {slug}")
    events = (
        db.query(PanelDspEvent)
        .filter_by(network_id=n.network_id)
        .order_by(PanelDspEvent.event_date)
        .all()
    )
    return DspEventsOut(
        slug=slug,
        events=[
            DspEventOut(
                event_id=e.event_id,
                event_type=e.event_type,
                event_date=e.event_date,
                operator_before=e.operator_before,
                operator_after=e.operator_after,
                contract_id=e.contract_id,
                contract_value_eur=e.contract_value_eur,
                boamp_url=e.boamp_url,
                notes=e.notes,
                source=e.source,
            )
            for e in events
        ],
    )


@router.get(
    "/networks/{slug}/reorg-events", response_model=ReorgEventsOut
)
def network_reorg_events(
    slug: str, response: Response, db: Session = Depends(get_db)
) -> ReorgEventsOut:
    response.headers.update(CACHE_HEADERS)
    n = db.query(PanelNetwork).filter_by(slug=slug).one_or_none()
    if n is None:
        raise HTTPException(404, f"network not found: {slug}")
    events = db.query(PanelReorgFlag).filter_by(
        network_id=n.network_id, reorg_detected=True
    )
    return ReorgEventsOut(
        slug=slug,
        events=[
            ReorgEventOut(
                network_slug=slug,
                feed_to_id=f.feed_to_id,
                reorg_severity=f.reorg_severity,
                stop_jaccard=f.stop_jaccard,
                route_jaccard=f.route_jaccard,
                detected_at=f.detected_at,
            )
            for f in events
        ],
    )


@router.get("/networks/{slug}/feed-diff", response_model=FeedDiffOut)
def network_feed_diff(
    slug: str,
    response: Response,
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    db: Session = Depends(get_db),
) -> FeedDiffOut:
    response.headers.update(CACHE_HEADERS)
    n = db.query(PanelNetwork).filter_by(slug=slug).one_or_none()
    if n is None:
        raise HTTPException(404, f"network not found: {slug}")
    diff = (
        db.query(PanelFeedDiff)
        .filter_by(feed_from_id=from_, feed_to_id=to)
        .one_or_none()
    )
    if diff is None:
        raise HTTPException(404, "diff not found")
    return FeedDiffOut(
        feed_from_id=diff.feed_from_id,
        feed_to_id=diff.feed_to_id,
        stops_added=diff.stops_added or [],
        stops_removed=diff.stops_removed or [],
        routes_added=diff.routes_added or [],
        routes_removed=diff.routes_removed or [],
        stop_jaccard=diff.stop_jaccard,
        route_jaccard=diff.route_jaccard,
    )


@router.get("/dsp-events/global")
def dsp_events_global(
    response: Response,
    year: Optional[int] = None,
    type: Optional[str] = None,
    tier: Optional[str] = None,
    db: Session = Depends(get_db),
):
    response.headers.update(CACHE_HEADERS)
    from sqlalchemy import extract

    q = db.query(PanelDspEvent, PanelNetwork).join(
        PanelNetwork, PanelDspEvent.network_id == PanelNetwork.network_id
    )
    if year:
        q = q.filter(extract("year", PanelDspEvent.event_date) == year)
    if type:
        q = q.filter(PanelDspEvent.event_type == type)
    if tier:
        q = q.filter(PanelNetwork.tier == tier)
    return {
        "events": [
            {
                "event_id": e.event_id,
                "network_slug": n.slug,
                "network_tier": n.tier,
                "event_type": e.event_type,
                "event_date": e.event_date.isoformat() if e.event_date else None,
                "operator_before": e.operator_before,
                "operator_after": e.operator_after,
                "boamp_url": e.boamp_url,
            }
            for e, n in q.order_by(PanelDspEvent.event_date)
        ]
    }


@router.get("/reorg-events/global")
def reorg_events_global(
    response: Response,
    year: Optional[int] = None,
    severity: Optional[str] = None,
    tier: Optional[str] = None,
    db: Session = Depends(get_db),
):
    response.headers.update(CACHE_HEADERS)
    from sqlalchemy import extract

    q = (
        db.query(PanelReorgFlag, PanelNetwork)
        .join(
            PanelNetwork,
            PanelReorgFlag.network_id == PanelNetwork.network_id,
        )
        .filter(PanelReorgFlag.reorg_detected == True)  # noqa: E712 — SQL boolean
    )
    if severity:
        q = q.filter(PanelReorgFlag.reorg_severity == severity)
    if tier:
        q = q.filter(PanelNetwork.tier == tier)
    if year:
        q = q.filter(extract("year", PanelReorgFlag.detected_at) == year)
    return {
        "events": [
            {
                "network_slug": n.slug,
                "feed_to_id": f.feed_to_id,
                "severity": f.reorg_severity,
                "stop_jaccard": f.stop_jaccard,
                "route_jaccard": f.route_jaccard,
                "detected_at": f.detected_at.isoformat()
                if f.detected_at
                else None,
            }
            for f, n in q
        ]
    }
