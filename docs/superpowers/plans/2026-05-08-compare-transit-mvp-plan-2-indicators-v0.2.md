# compare-transit.fr MVP — Plan 2: Indicator Pipeline + v0.2 Backend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the v0.2 backend MVP — 38 indicators, reorg detector, DSP timeline loader, audit-grade plumbing, what-if isolation, derived layer (z-score / percentile / YoY / post_reorg_delta), full PAN backfill, and panel API endpoints — so the frontend (Plan 3) and launch (Plan 4) have a complete data substrate.

**Architecture:** All work lives under `backend/app/services/panel_pipeline/` and `backend/app/api/endpoints/panel.py`. The hard rule (§6.2 v0.2): `indicators.compute()` is a pure function — single GTFS ZIP + AomMeta in, 38-indicator dict out, no DB writes, no globals. `panel_pipeline.run` is the DB-bound orchestrator that calls `compute()` then persists. Reorg detector and aggregator key off `panel_feed_diffs` / `panel_reorg_flags`. DSP events arrive via the methodology repo CSV → `load_dsp_events.py`. The KCC equivalence contract test (spec §11) anchors the indicator rollout.

**Tech Stack:** Python 3.11+ · pandas 2.2 · geopandas 1.0 · shapely 2.0 · SQLAlchemy 2.0 · Alembic 1.13 · pytest 8.3 · Celery 5.3 (`-P solo` on Windows) · FastAPI 0.111 · Pydantic v2 · MobilityData GTFS Validator (Java CLI, already wrapped by D3) · ADEME Base Carbone v23+ factors

**Spec reference:** `docs/superpowers/specs/2026-05-06-compare-transit-mvp-design-v0.2.md` — §5 indicators, §6.2 pipeline + what-if rule, §6.3 schema, §8 API, §11 KCC contract, §12 D5/D6 discovery, §22 DSP schema. Predecessor: `docs/superpowers/plans/2026-05-03-compare-transit-mvp-plan-1-discovery-foundation.md` (shipped).

**Estimated time:** 5 weeks (W2.5 → W7 of 16-week roadmap). Single dev. 24 tasks across 7 phases.

**Final plan location** (after `ExitPlanMode` approval, move from harness path to):
`docs/superpowers/plans/2026-05-08-compare-transit-mvp-plan-2-indicators-v0.2.md`

---

## Open assumptions (user-approved during planning)

| # | Assumption | Source |
|---|---|---|
| A1 | Error margin propagation v0 formula: `error_margin_pct = sqrt(Σ w_i · (1 − dq_i/100)²) × scale_factor[indicator]`. Weights from §5.1 G overall_score formula. `scale_factor`: 1.0 for direct-from-feed, 5 for coverage, 30 for env_co2 (matches §5.1 H ±30% callout). Documented as "provisional v0" inline; canonical doc must land in `methodology/error_propagation.md` before W16 launch. | User answer 2026-05-08 |
| A2 | DSP `csv_row_hash` includes `notes` + `boamp_url` → contributor edits insert new rows (audit trail preserved). Network timeline page reads latest by `(network_slug, event_type, event_date)`. | User answer 2026-05-08 |
| A3 | `compute()` may read static versioned YAML files (peer_groups, ademe_factors, reorg_thresholds) — they are functions of methodology_commit, not state. | Plan-agent default |
| A4 | `AomMeta.polygon_l93` is a Shapely geometry; loading from disk is the caller's job. | Plan-agent default |
| A5 | Aggregator recomputes only the touched network's tier on each feed update, not all 463 networks. | Plan-agent default |
| A6 | Derived indicators (z-score, percentile, post_reorg_delta) carry `methodology_commit` for consistency with raw audit response. | Plan-agent default |
| A7 | `cov_pop_freq_300m` definition: stops served by **at least one** route whose **median peak headway ≤ 10 min**. | Plan-agent default; document in methodology repo |
| A8 | `struct_route_directness` without GTFS shapes uses stop-sequence cumulative Haversine vs origin→terminus great-circle. Documented as "shape-free approximation". | Plan-agent default |
| A9 | `peer_groups.classify_tier` `has_metro` flag derived from `route_type=1` presence in any feed of the network; stored in `panel_networks.has_metro` (new column). | Plan-agent default |

---

## File Structure

### New code (this plan)

```
backend/alembic/versions/
└── g2a3b4c5d6e7_add_panel_v02_tables.py    — 3 new tables + 3 new columns

backend/app/db/
└── models.py                                — APPEND: PanelFeedDiff, PanelReorgFlag,
                                                PanelDspEvent + 3 columns + has_metro

backend/app/services/panel_pipeline/
├── compute.py                               — NEW: pure indicators.compute() entrypoint (§6.2)
├── run.py                                   — REWRITE from stub: DB-bound orchestrator
├── aggregator.py                            — REWRITE: zscore, pct, YoY, post_reorg_delta
├── quality.py                               — REWRITE: validator + 6 dq_* + overall score
├── geo.py                                   — APPEND: cov_pop_freq_300m + cov_equity_gini
├── _registry.py                             — NEW: 38-indicator metadata (unit, dq deps, dsp_priority)
├── error_margin.py                          — NEW: provisional v0 propagation
├── diff/
│   ├── __init__.py
│   ├── feed_diff.py                         — NEW: stop/route added/removed/modified
│   ├── reorg_detect.py                      — NEW: Jaccard + thresholds
│   └── persist.py                           — NEW: persist diffs + reorg flags
├── indicators/
│   ├── productivity.py                      — IMPL 8 indicators
│   ├── density.py                           — IMPL 4 indicators
│   ├── structure.py                         — IMPL 7 indicators
│   ├── coverage.py                          — IMPL 6 indicators (wraps geo.py)
│   ├── frequency.py                         — IMPL 4 indicators
│   ├── accessibility.py                     — IMPL 2 indicators
│   ├── environment.py                       — IMPL 1 indicator
│   └── quality_indicators.py                — NEW: 6 dq_* indicators (separate from quality.py wrapper)
├── data/
│   ├── reorg_thresholds.yaml                — NEW: minor/major/massive Jaccard cuts
│   ├── ademe_factors.yaml                   — NEW: CO2 factors per route_type
│   ├── network_tier_overrides.yaml          — NEW: 30 head networks manual tier
│   └── error_margin_scale.yaml              — NEW: per-indicator scale_factor

backend/app/api/endpoints/
└── panel.py                                 — NEW: 13 endpoints (8 v0.1 + 5 v0.2)

backend/app/api/schemas/
└── panel.py                                 — NEW: Pydantic v2 response models (audit-grade)

backend/scripts/
├── load_dsp_events.py                       — NEW: idempotent CSV loader
└── run_panel_backfill.py                    — NEW: PAN full backfill driver

backend/scripts/discovery/
└── d6_reorg_thresholds.py                   — NEW: detector tuning pilot

backend/tests/panel_pipeline/
├── test_compute_purity.py                   — NEW: pure-function contract
├── test_indicators_productivity.py          — NEW
├── test_indicators_density.py               — NEW
├── test_indicators_structure.py             — NEW
├── test_indicators_coverage.py              — NEW (extends D2 fixtures)
├── test_indicators_frequency.py             — NEW
├── test_indicators_accessibility.py         — NEW
├── test_indicators_environment.py           — NEW
├── test_indicators_quality.py               — NEW
├── test_diff_feed_diff.py                   — NEW
├── test_diff_reorg_detect.py                — NEW
├── test_aggregator.py                       — NEW
├── test_error_margin.py                     — NEW
├── test_dsp_loader.py                       — NEW
├── test_run_pipeline.py                     — NEW
├── test_models_v02.py                       — NEW
├── test_kcc_equivalence_contract.py         — UNSKIP + fix bug at line 29
└── data/
    └── aom_meta_fixtures.yaml               — population/area for SEM/SOLEA/ginko

backend/tests/api/
└── test_panel_endpoints.py                  — NEW

docs/superpowers/specs/
├── 2026-05-XX-d5-dsp-timeline-discovery.md  — NEW
└── 2026-05-XX-d6-reorg-detector-discovery.md — NEW
```

### External (parallel, methodology repo — not in this codebase)

```
compare-transit/methodology/                  — separate GitHub repo (Plan 4 W13)
├── data/dsp_timeline.csv                    — POPULATED here in Tasks 4.1 + 4.3
├── methodology/error_propagation.md         — DRAFTED here, finalized W13
└── methodology/reorg_detector.md            — DRAFTED here from D6 output
```

---

## Critical path

```
0.1 migration ──► 0.2 registry ──► 0.3 compute() pure
                                       │
        ┌──────────────────────────────┤
        ▼                              ▼
   1.* reorg detector              2.* batch1 (KCC anchor)
        │                              │
        └────► 1.4 persist ────┐       ▼
                               │   3.* batch2
                               │       │
                               │       ▼
                               │   5.* batch3 + error margin
                               │       │
                               └──►    ▼
                                   6.* aggregator (post_reorg_delta)
                                       │
        4.* DSP loader (parallel)──►   ▼
                                   7.* run + backfill + API
```

**Hard blockers**: 0.1 → all writes; 0.3 → all indicator impls; 1.4 → 6.3; 5.4 → 7.4 API.

---

# Phase 0 — Schema migration + what-if foundation (W2)

## Task 0.1: Alembic migration for v0.2 schema

**Files:**
- Create: `backend/alembic/versions/g2a3b4c5d6e7_add_panel_v02_tables.py`
- Modify: `backend/app/db/models.py` (append 3 classes + extend 3 existing classes)
- Test: `backend/tests/panel_pipeline/test_models_v02.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/panel_pipeline/test_models_v02.py`:

```python
"""v0.2 schema additions — round-trip insert tests."""
from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    PanelDspEvent,
    PanelFeed,
    PanelFeedDiff,
    PanelIndicator,
    PanelIndicatorDerived,
    PanelNetwork,
    PanelReorgFlag,
)


@pytest.fixture()
def network_with_two_feeds(db_session: Session) -> tuple[PanelNetwork, PanelFeed, PanelFeed]:
    network = PanelNetwork(
        slug="lyon",
        pan_dataset_id="pan-lyon",
        display_name="TCL",
        tier="T1",
        population=1_420_000,
        area_km2=538.0,
    )
    db_session.add(network)
    db_session.flush()
    feed_a = PanelFeed(
        network_id=network.network_id,
        pan_resource_id="r1",
        published_at=datetime(2024, 1, 1),
        feed_start_date=datetime(2024, 1, 1),
        gtfs_url="https://example.com/a.zip",
    )
    feed_b = PanelFeed(
        network_id=network.network_id,
        pan_resource_id="r2",
        published_at=datetime(2024, 9, 1),
        feed_start_date=datetime(2024, 9, 1),
        gtfs_url="https://example.com/b.zip",
    )
    db_session.add_all([feed_a, feed_b])
    db_session.commit()
    return network, feed_a, feed_b


def test_panel_feed_diff_roundtrip(db_session, network_with_two_feeds):
    network, feed_a, feed_b = network_with_two_feeds
    diff = PanelFeedDiff(
        network_id=network.network_id,
        feed_from_id=feed_a.feed_id,
        feed_to_id=feed_b.feed_id,
        stops_added=["S100", "S101"],
        stops_removed=[],
        stops_modified={},
        routes_added=["R5"],
        routes_removed=["R3"],
        routes_modified={},
        stop_jaccard=0.95,
        route_jaccard=0.27,
    )
    db_session.add(diff)
    db_session.commit()
    fetched = db_session.query(PanelFeedDiff).first()
    assert fetched.stops_added == ["S100", "S101"]
    assert fetched.route_jaccard == 0.27


def test_panel_reorg_flag_roundtrip(db_session, network_with_two_feeds):
    network, _, feed_b = network_with_two_feeds
    flag = PanelReorgFlag(
        network_id=network.network_id,
        feed_to_id=feed_b.feed_id,
        reorg_detected=True,
        reorg_severity="major",
        stop_jaccard=0.62,
        route_jaccard=0.40,
        threshold_version="v1",
    )
    db_session.add(flag)
    db_session.commit()
    assert db_session.query(PanelReorgFlag).count() == 1


def test_panel_dsp_event_roundtrip(db_session, network_with_two_feeds):
    network, *_ = network_with_two_feeds
    evt = PanelDspEvent(
        network_id=network.network_id,
        event_type="contract_started",
        event_date=datetime(2017, 9, 1).date(),
        operator_after="Keolis",
        source="BOAMP",
        contributor="wei",
        csv_row_hash="abc123",
    )
    db_session.add(evt)
    db_session.commit()
    assert db_session.query(PanelDspEvent).count() == 1


def test_audit_columns_on_indicators(db_session, network_with_two_feeds):
    _, feed_a, _ = network_with_two_feeds
    ind = PanelIndicator(
        feed_id=feed_a.feed_id,
        indicator_id="prod_kcc_year",
        value=24_300_000.0,
        unit="km/year",
        error_margin_pct=2.1,
        methodology_commit="a3f2c1d",
    )
    db_session.add(ind)
    db_session.commit()
    fetched = db_session.query(PanelIndicator).first()
    assert fetched.error_margin_pct == 2.1
    assert fetched.methodology_commit == "a3f2c1d"


def test_post_reorg_delta_column_on_derived(db_session, network_with_two_feeds):
    _, _, feed_b = network_with_two_feeds
    der = PanelIndicatorDerived(
        feed_id=feed_b.feed_id,
        indicator_id="prod_kcc_year",
        post_reorg_delta_pct=-3.0,
    )
    db_session.add(der)
    db_session.commit()
    assert db_session.query(PanelIndicatorDerived).first().post_reorg_delta_pct == -3.0


def test_has_metro_column_on_network(db_session):
    n = PanelNetwork(
        slug="paris",
        pan_dataset_id="pan-paris",
        display_name="IDFM",
        has_metro=True,
    )
    db_session.add(n)
    db_session.commit()
    assert db_session.query(PanelNetwork).filter_by(slug="paris").one().has_metro is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ..\venv\Scripts\pytest tests/panel_pipeline/test_models_v02.py -v`
Expected: FAIL — `AttributeError: type object 'PanelIndicator' has no attribute 'error_margin_pct'` (or `PanelFeedDiff` not importable).

- [ ] **Step 3: Extend `backend/app/db/models.py`**

Append to bottom of file:

```python
class PanelFeedDiff(Base):
    """Stop/route diff between two adjacent feeds — spec §6.3.2."""
    __tablename__ = "panel_feed_diffs"

    diff_id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    network_id       = Column(String, ForeignKey("panel_networks.network_id"), index=True, nullable=False)
    feed_from_id     = Column(String, ForeignKey("panel_feeds.feed_id"), nullable=False)
    feed_to_id       = Column(String, ForeignKey("panel_feeds.feed_id"), nullable=False)
    stops_added      = Column(JSON)
    stops_removed    = Column(JSON)
    stops_modified   = Column(JSON)
    routes_added     = Column(JSON)
    routes_removed   = Column(JSON)
    routes_modified  = Column(JSON)
    stop_jaccard     = Column(Float)
    route_jaccard    = Column(Float)
    computed_at      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ux_panel_feed_diffs_pair", "feed_from_id", "feed_to_id", unique=True),
    )


class PanelReorgFlag(Base):
    """Reorg detection per (network, feed_to) — spec §6.3.2."""
    __tablename__ = "panel_reorg_flags"

    network_id        = Column(String, ForeignKey("panel_networks.network_id"), primary_key=True)
    feed_to_id        = Column(String, ForeignKey("panel_feeds.feed_id"), primary_key=True)
    reorg_detected    = Column(Boolean, default=False)
    reorg_severity    = Column(String)            # 'minor' | 'major' | 'massive' | None
    stop_jaccard      = Column(Float)
    route_jaccard     = Column(Float)
    threshold_version = Column(String)
    notes             = Column(String)
    detected_at       = Column(DateTime, default=datetime.utcnow)


class PanelDspEvent(Base):
    """DSP contract timeline events from methodology repo dsp_timeline.csv — spec §6.3.2."""
    __tablename__ = "panel_dsp_events"

    event_id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    network_id         = Column(String, ForeignKey("panel_networks.network_id"), index=True, nullable=False)
    event_type         = Column(String, nullable=False, index=True)   # tender_published / awarded / contract_started / ended / amendment
    event_date         = Column(DateTime, nullable=False, index=True)
    operator_before    = Column(String)
    operator_after     = Column(String)
    contract_id        = Column(String)
    contract_value_eur = Column(Float)
    boamp_url          = Column(String)
    notes              = Column(String)
    source             = Column(String, nullable=False)
    contributor        = Column(String, nullable=False)
    csv_row_hash       = Column(String, unique=True, index=True, nullable=False)
    imported_at        = Column(DateTime, default=datetime.utcnow)
```

Also add to `PanelIndicator`:

```python
    error_margin_pct   = Column(Float)
    methodology_commit = Column(String)
```

Add to `PanelIndicatorDerived`:

```python
    post_reorg_delta_pct = Column(Float)
    methodology_commit   = Column(String)
```

Add to `PanelNetwork`:

```python
    has_metro = Column(Boolean, default=False)
```

- [ ] **Step 4: Generate Alembic migration**

```powershell
cd backend
..\venv\Scripts\alembic revision -m "add_panel_v02_tables_and_audit_columns" --rev-id g2a3b4c5d6e7
```

Then edit the new file to set `down_revision = 'f1a2b3c4d5e6'` and fill `upgrade()` / `downgrade()` with `op.create_table` / `op.add_column` matching the model classes above. Use `sa.JSON()` (portable to SQLite + Postgres). Mirror the index naming in models.

- [ ] **Step 5: Run migration + tests**

```powershell
..\venv\Scripts\alembic upgrade head
..\venv\Scripts\pytest tests/panel_pipeline/test_models_v02.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/g2a3b4c5d6e7_add_panel_v02_tables.py \
        backend/app/db/models.py \
        backend/tests/panel_pipeline/test_models_v02.py
git commit -m "feat(panel): add v0.2 schema (feed_diffs, reorg_flags, dsp_events) + audit columns"
```

---

## Task 0.2: Indicator metadata registry

**Files:**
- Create: `backend/app/services/panel_pipeline/_registry.py`
- Create: `backend/app/services/panel_pipeline/data/error_margin_scale.yaml`
- Test: append to `backend/tests/panel_pipeline/test_skeleton.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/panel_pipeline/test_skeleton.py`:

```python
def test_registry_complete():
    from app.services.panel_pipeline._registry import INDICATOR_REGISTRY
    from app.services.panel_pipeline.types import INDICATOR_IDS
    assert set(INDICATOR_REGISTRY.keys()) == INDICATOR_IDS
    for ind_id, meta in INDICATOR_REGISTRY.items():
        assert meta.unit
        assert meta.category in {"productivity", "density", "structure", "coverage",
                                 "frequency", "accessibility", "quality", "environment"}
        assert meta.dsp_priority in {"P0", "P1", "P2"}
        # dq deps must be subset of dq_* indicators
        for dep in meta.dq_dependencies:
            assert dep.startswith("dq_"), f"{ind_id} bad dq dep {dep}"


def test_registry_dsp_p0_count():
    """Spec §5.1 names exactly 7 P0 indicators."""
    from app.services.panel_pipeline._registry import INDICATOR_REGISTRY
    p0 = [k for k, v in INDICATOR_REGISTRY.items() if v.dsp_priority == "P0"]
    assert set(p0) == {
        "prod_kcc_year", "prod_peak_vehicles_needed", "freq_commercial_speed_kmh",
        "prod_lines_count", "prod_stops_count", "cov_pop_300m", "cov_pop_freq_300m",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\venv\Scripts\pytest tests/panel_pipeline/test_skeleton.py::test_registry_complete -v`
Expected: FAIL — `ModuleNotFoundError: app.services.panel_pipeline._registry`.

- [ ] **Step 3: Create registry**

Create `backend/app/services/panel_pipeline/_registry.py`:

```python
"""Per-indicator metadata: unit, category, DSP priority, error-margin dependencies.

Used by _compute._, error_margin._, and api.schemas.panel for audit-grade responses.
Reading this dict is allowed inside compute() (versioned, no global state — A3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Category = Literal["productivity", "density", "structure", "coverage",
                   "frequency", "accessibility", "quality", "environment"]
DspPriority = Literal["P0", "P1", "P2"]


@dataclass(frozen=True, slots=True)
class IndicatorMeta:
    unit: str
    category: Category
    dsp_priority: DspPriority
    dq_dependencies: tuple[str, ...] = field(default_factory=tuple)


# All 6 dq_* indicators; used as default propagation set for direct-feed indicators.
ALL_DQ: tuple[str, ...] = (
    "dq_validator_errors", "dq_validator_warnings", "dq_field_completeness",
    "dq_coord_quality", "dq_route_type_completeness", "dq_freshness",
)


INDICATOR_REGISTRY: dict[str, IndicatorMeta] = {
    # A. Productivity (8) — KCC/counts depend on field completeness + route_type
    "prod_kcc_year":            IndicatorMeta("km", "productivity", "P0", ALL_DQ),
    "prod_courses_day_avg":     IndicatorMeta("trips/day", "productivity", "P1", ALL_DQ),
    "prod_peak_hour_courses":   IndicatorMeta("trips/h", "productivity", "P1", ALL_DQ),
    "prod_service_amplitude":   IndicatorMeta("h", "productivity", "P1", ("dq_field_completeness",)),
    "prod_lines_count":         IndicatorMeta("count", "productivity", "P0", ("dq_field_completeness",)),
    "prod_stops_count":         IndicatorMeta("count", "productivity", "P0", ("dq_field_completeness",)),
    "prod_network_length_km":   IndicatorMeta("km", "productivity", "P1", ("dq_coord_quality",)),
    "prod_peak_vehicles_needed":IndicatorMeta("count", "productivity", "P0", ALL_DQ),
    # B. Density (4) — propagate from numerator deps
    "dens_stops_km2":           IndicatorMeta("stops/km2", "density", "P2", ("dq_field_completeness",)),
    "dens_lines_100k_pop":      IndicatorMeta("lines/100K", "density", "P1", ("dq_field_completeness",)),
    "dens_kcc_capita":          IndicatorMeta("km/capita", "density", "P1", ALL_DQ),
    "dens_kcc_km2":             IndicatorMeta("km/km2", "density", "P2", ALL_DQ),
    # C. Structure (7)
    "struct_modal_mix_bus":     IndicatorMeta("%", "structure", "P1", ("dq_route_type_completeness",)),
    "struct_modal_mix_tram":    IndicatorMeta("%", "structure", "P1", ("dq_route_type_completeness",)),
    "struct_modal_mix_metro":   IndicatorMeta("%", "structure", "P1", ("dq_route_type_completeness",)),
    "struct_modal_mix_train":   IndicatorMeta("%", "structure", "P1", ("dq_route_type_completeness",)),
    "struct_peak_amplification":IndicatorMeta("ratio", "structure", "P2", ALL_DQ),
    "struct_multi_route_stops_pct": IndicatorMeta("%", "structure", "P2", ("dq_field_completeness",)),
    "struct_route_directness":  IndicatorMeta("ratio", "structure", "P2", ("dq_coord_quality",)),
    # D. Coverage (6)
    "cov_pop_300m":             IndicatorMeta("%", "coverage", "P0", ("dq_coord_quality",)),
    "cov_pop_freq_300m":        IndicatorMeta("%", "coverage", "P0", ALL_DQ),
    "cov_surface_300m":         IndicatorMeta("%", "coverage", "P1", ("dq_coord_quality",)),
    "cov_median_walk":          IndicatorMeta("m", "coverage", "P1", ("dq_coord_quality",)),
    "cov_pop_weighted_walk":    IndicatorMeta("m", "coverage", "P1", ("dq_coord_quality",)),
    "cov_equity_gini":          IndicatorMeta("0-1", "coverage", "P2", ("dq_coord_quality",)),
    # E. Frequency & Speed (4)
    "freq_peak_headway_median": IndicatorMeta("min", "frequency", "P1", ALL_DQ),
    "freq_high_freq_lines_pct": IndicatorMeta("%", "frequency", "P1", ALL_DQ),
    "freq_daily_service_hours": IndicatorMeta("h", "frequency", "P1", ALL_DQ),
    "freq_commercial_speed_kmh":IndicatorMeta("km/h", "frequency", "P0", ALL_DQ),
    # F. Accessibility (2)
    "acc_wheelchair_stops_pct": IndicatorMeta("%", "accessibility", "P1", ("dq_field_completeness",)),
    "acc_wheelchair_trips_pct": IndicatorMeta("%", "accessibility", "P1", ("dq_field_completeness",)),
    # G. Quality (6) — self-referential; error margin = 0 for these
    "dq_validator_errors":      IndicatorMeta("count", "quality", "P1"),
    "dq_validator_warnings":    IndicatorMeta("count", "quality", "P1"),
    "dq_field_completeness":    IndicatorMeta("0-100", "quality", "P1"),
    "dq_coord_quality":         IndicatorMeta("%", "quality", "P1"),
    "dq_route_type_completeness": IndicatorMeta("%", "quality", "P1"),
    "dq_freshness":             IndicatorMeta("days", "quality", "P1"),
    # H. Environment (1)
    "env_co2_year_estimated":   IndicatorMeta("tCO2/year", "environment", "P2", ALL_DQ),
}

assert len(INDICATOR_REGISTRY) == 38, f"Registry count mismatch: {len(INDICATOR_REGISTRY)}"
```

Create `backend/app/services/panel_pipeline/data/error_margin_scale.yaml`:

```yaml
# Per-indicator scale_factor for provisional v0 error-margin propagation (Assumption A1).
# Canonical doc lands in methodology/error_propagation.md before W16 launch.
default: 1.0
overrides:
  cov_pop_300m: 5.0
  cov_pop_freq_300m: 5.0
  cov_surface_300m: 5.0
  cov_median_walk: 5.0
  cov_pop_weighted_walk: 5.0
  cov_equity_gini: 5.0
  env_co2_year_estimated: 30.0
  # All dq_* implicitly carry margin=0 (registered with empty dq_dependencies)
```

- [ ] **Step 4: Run test**

Run: `..\venv\Scripts\pytest tests/panel_pipeline/test_skeleton.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/panel_pipeline/_registry.py \
        backend/app/services/panel_pipeline/data/error_margin_scale.yaml \
        backend/tests/panel_pipeline/test_skeleton.py
git commit -m "feat(panel): indicator registry with DSP priority + error-margin dependencies"
```

---

## Task 0.3: What-if isolation — pure compute() entrypoint

**Files:**
- Create: `backend/app/services/panel_pipeline/compute.py`
- Test: `backend/tests/panel_pipeline/test_compute_purity.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/panel_pipeline/test_compute_purity.py`:

```python
"""Spec §6.2 v0.2 hard rule: indicators.compute() is a pure function.
- No DB session created.
- No global state mutation.
- Identical input → identical output (modulo computed_at).
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pytest
from shapely.geometry import box

from app.services.panel_pipeline.compute import AomMeta, IndicatorBundle, compute


FIXTURES = Path(__file__).resolve().parents[1] / "Resources" / "raw"
SEM_ZIP = FIXTURES / "SEM-GTFS(2).zip"


@pytest.fixture()
def sem_meta() -> AomMeta:
    # Real Grenoble polygon comes from D2 cache; for purity test, a coarse bbox suffices.
    return AomMeta(
        slug="grenoble-sem",
        population=445_000,
        area_km2=541.0,
        polygon_l93=box(910_000, 6_440_000, 950_000, 6_490_000),
        methodology_commit="test-deadbeef",
    )


def test_compute_returns_38_indicators(sem_meta):
    bundle = compute(SEM_ZIP, sem_meta)
    assert isinstance(bundle, IndicatorBundle)
    assert len(bundle.values) == 38


def test_compute_no_db_access(sem_meta):
    """Pure-function rule: compute() must not touch the DB."""
    with patch("app.db.database.SessionLocal") as session_factory:
        compute(SEM_ZIP, sem_meta)
        session_factory.assert_not_called()


def test_compute_deterministic(sem_meta):
    """Same input twice → identical numeric output (computed_at field excluded)."""
    a = compute(SEM_ZIP, sem_meta)
    b = compute(SEM_ZIP, sem_meta)
    for ind_id in a.values:
        va, vb = a.values[ind_id], b.values[ind_id]
        assert va.value == vb.value, f"{ind_id} non-deterministic: {va.value} vs {vb.value}"
        assert va.unit == vb.unit
        assert va.error_margin_pct == vb.error_margin_pct


def test_compute_methodology_commit_passes_through(sem_meta):
    bundle = compute(SEM_ZIP, sem_meta)
    for v in bundle.values.values():
        assert v.methodology_commit == "test-deadbeef"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\venv\Scripts\pytest tests/panel_pipeline/test_compute_purity.py -v`
Expected: FAIL — `ModuleNotFoundError` or `NotImplementedError`.

- [ ] **Step 3: Implement `compute.py`**

Create `backend/app/services/panel_pipeline/compute.py`:

```python
"""Pure compute() entrypoint — spec §6.2 v0.2 hard rule.

No DB writes. No global state. Same input → same output. Used by:
  1. panel_pipeline.run (production: load feed → compute → persist)
  2. V1 Pro what-if simulator (user-uploaded ZIP → preview indicators)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from shapely.geometry.base import BaseGeometry

from app.services.panel_pipeline._registry import INDICATOR_REGISTRY
from app.services.panel_pipeline.types import INDICATOR_IDS


@dataclass(frozen=True, slots=True)
class AomMeta:
    """Caller-supplied AOM metadata. Polygon must already be Lambert-93 (EPSG:2154)."""
    slug: str
    population: int
    area_km2: float
    polygon_l93: BaseGeometry
    methodology_commit: str


class IndicatorValue(TypedDict):
    value: float | None
    unit: str
    error_margin_pct: float | None
    source_feed_id: str | None      # None during what-if; filled by run.py
    computed_at: str                # ISO 8601 UTC
    methodology_commit: str


@dataclass(frozen=True, slots=True)
class IndicatorBundle:
    values: dict[str, IndicatorValue]
    errors: dict[str, str] = field(default_factory=dict)   # {indicator_id: reason}


def compute(zip_path: Path, meta: AomMeta) -> IndicatorBundle:
    """Run the 38-indicator pipeline on a single GTFS ZIP. Pure function.

    Args:
        zip_path: Path to GTFS ZIP. Must exist.
        meta: AOM metadata frozen dataclass with population, area, polygon, commit.

    Returns:
        IndicatorBundle with 38 IndicatorValue entries (or fewer if errors filled).
    """
    from app.services.gtfs_core.gtfs_reader import read_gtfs_zip
    from app.services.gtfs_core.gtfs_norm import gtfs_normalize, ligne_generate
    from app.services.gtfs_core.gtfs_generator import (
        service_date_generate,
        service_jour_type_generate,
    )
    from app.services.panel_pipeline.indicators import (
        accessibility, coverage, density, environment, frequency,
        productivity, quality_indicators, structure,
    )
    from app.services.panel_pipeline.error_margin import propagate

    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    # 1. Read + normalize (reuse gtfs_core)
    raw = read_gtfs_zip(zip_path)
    normed = gtfs_normalize(raw)
    lignes = ligne_generate(raw["routes"])
    service_date = service_date_generate(normed.get("calendar"), normed.get("calendar_dates"))
    sjt = service_jour_type_generate(service_date, ...)   # exact signature in indicators/productivity.py

    # 2. Compute each category
    raw_values: dict[str, float | None] = {}
    errors: dict[str, str] = {}

    raw_values.update(productivity.compute_all(raw, normed, lignes, sjt))
    raw_values.update(density.compute_all(raw_values, meta))
    raw_values.update(structure.compute_all(raw, normed))
    try:
        raw_values.update(coverage.compute_all(raw, normed, meta))
    except FileNotFoundError as e:
        for cov_id in [k for k, v in INDICATOR_REGISTRY.items() if v.category == "coverage"]:
            raw_values[cov_id] = None
            errors[cov_id] = f"aom_polygon_or_carroyage_missing: {e}"
    raw_values.update(frequency.compute_all(raw, normed, sjt))
    raw_values.update(accessibility.compute_all(raw))
    raw_values.update(quality_indicators.compute_all(zip_path, raw))
    raw_values.update(environment.compute_all(raw_values))

    # 3. Wrap as IndicatorValue + error margin propagation
    now = datetime.now(timezone.utc).isoformat()
    bundle: dict[str, IndicatorValue] = {}
    for ind_id in INDICATOR_IDS:
        meta_ind = INDICATOR_REGISTRY[ind_id]
        val = raw_values.get(ind_id)
        margin = propagate(ind_id, raw_values) if val is not None else None
        bundle[ind_id] = IndicatorValue(
            value=val,
            unit=meta_ind.unit,
            error_margin_pct=margin,
            source_feed_id=None,
            computed_at=now,
            methodology_commit=meta.methodology_commit,
        )
    return IndicatorBundle(values=bundle, errors=errors)
```

> **Note**: at this commit, `compute()` will not run end-to-end (sub-modules are still stubs). That's fine — Phase 0 just establishes the interface and the purity contract. The two purity tests (`test_compute_no_db_access`, `test_compute_methodology_commit_passes_through`) need a stub that *returns* a bundle without crashing. Add a `try/except NotImplementedError` wrapper that fills `errors[]` for unimplemented categories:

```python
    try:
        raw_values.update(productivity.compute_all(...))
    except NotImplementedError:
        for k in [k for k,v in INDICATOR_REGISTRY.items() if v.category == "productivity"]:
            raw_values[k] = None
            errors[k] = "not_implemented_yet"
    # ... repeat for each category
```

This bridge stays until Phase 5 closes; remove the `try/except NotImplementedError` blocks then.

Add a stub `propagate()` returning `0.0` in `error_margin.py` (full impl in Task 5.4).

- [ ] **Step 4: Run tests**

Run: `..\venv\Scripts\pytest tests/panel_pipeline/test_compute_purity.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/panel_pipeline/compute.py \
        backend/app/services/panel_pipeline/error_margin.py \
        backend/tests/panel_pipeline/test_compute_purity.py
git commit -m "feat(panel): pure compute() entrypoint — what-if isolation hard rule"
```

---

# Phase 1 — Reorg detector (W2.5)

## Task 1.1: Feed diff (stop/route added/removed/modified)

**Files:**
- Create: `backend/app/services/panel_pipeline/diff/__init__.py` (empty)
- Create: `backend/app/services/panel_pipeline/diff/feed_diff.py`
- Test: `backend/tests/panel_pipeline/test_diff_feed_diff.py`

- [ ] **Step 1: Write the failing test**

Create `test_diff_feed_diff.py`:

```python
from __future__ import annotations

import pandas as pd
import pytest

from app.services.panel_pipeline.diff.feed_diff import FeedDiff, feed_diff


def _stops(rows):
    return pd.DataFrame(rows, columns=["stop_id", "stop_name", "stop_lat", "stop_lon"])


def _routes(rows):
    return pd.DataFrame(rows, columns=["route_id", "route_short_name", "route_type"])


def test_feed_diff_added_removed():
    a = {"stops": _stops([("S1", "A", 0.0, 0.0), ("S2", "B", 1.0, 1.0)]),
         "routes": _routes([("R1", "1", 3)])}
    b = {"stops": _stops([("S2", "B", 1.0, 1.0), ("S3", "C", 2.0, 2.0)]),
         "routes": _routes([("R1", "1", 3), ("R2", "2", 3)])}
    d = feed_diff(a, b)
    assert d.stops_added == ["S3"]
    assert d.stops_removed == ["S1"]
    assert d.stops_modified == {}
    assert d.routes_added == ["R2"]
    assert d.routes_removed == []
    assert pytest.approx(d.stop_jaccard, abs=1e-6) == 1 / 3   # |∩|=1, |∪|=3
    assert pytest.approx(d.route_jaccard, abs=1e-6) == 1 / 2  # |∩|=1, |∪|=2


def test_feed_diff_modified_field():
    a = {"stops": _stops([("S1", "Old", 0.0, 0.0)]), "routes": _routes([])}
    b = {"stops": _stops([("S1", "New", 0.001, 0.0)]), "routes": _routes([])}
    d = feed_diff(a, b)
    assert d.stops_modified == {"S1": {"stop_name": ["Old", "New"], "stop_lat": [0.0, 0.001]}}
    assert d.stops_added == []
    assert d.stops_removed == []


def test_feed_diff_identical_full_jaccard():
    a = {"stops": _stops([("S1", "A", 0.0, 0.0)]), "routes": _routes([("R1", "1", 3)])}
    d = feed_diff(a, a)
    assert d.stop_jaccard == 1.0
    assert d.route_jaccard == 1.0
    assert d.stops_added == [] and d.stops_removed == [] and d.stops_modified == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\venv\Scripts\pytest tests/panel_pipeline/test_diff_feed_diff.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `diff/feed_diff.py`**

```python
"""Feed-pair diff: added/removed/modified for stops and routes. Pure function.

Input schema (per side):
    stops: DataFrame[stop_id, stop_name, stop_lat, stop_lon, ...]
    routes: DataFrame[route_id, route_short_name, route_type, ...]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import pandas as pd


STOP_TRACKED_FIELDS = ("stop_name", "stop_lat", "stop_lon", "location_type")
ROUTE_TRACKED_FIELDS = ("route_short_name", "route_long_name", "route_type")


@dataclass(frozen=True, slots=True)
class FeedDiff:
    stops_added: list[str]
    stops_removed: list[str]
    stops_modified: dict[str, dict[str, list]]
    routes_added: list[str]
    routes_removed: list[str]
    routes_modified: dict[str, dict[str, list]]
    stop_jaccard: float
    route_jaccard: float


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _ne(x: object, y: object) -> bool:
    """Compare two scalars, treating NaN-on-both-sides as equal."""
    if pd.isna(x) and pd.isna(y):
        return False
    return x != y


def _diff_records(
    a: pd.DataFrame, b: pd.DataFrame, key: str, tracked: Sequence[str],
) -> tuple[list[str], list[str], dict[str, dict[str, list]]]:
    if a[key].duplicated().any():
        dup_ids = a.loc[a[key].duplicated(), key].astype(str).head().tolist()
        raise ValueError(f"duplicate {key} in feed a: {dup_ids}")
    if b[key].duplicated().any():
        dup_ids = b.loc[b[key].duplicated(), key].astype(str).head().tolist()
        raise ValueError(f"duplicate {key} in feed b: {dup_ids}")
    a_ids = set(a[key].astype(str))
    b_ids = set(b[key].astype(str))
    added = sorted(b_ids - a_ids)
    removed = sorted(a_ids - b_ids)
    modified: dict[str, dict[str, list]] = {}
    common = a_ids & b_ids
    if common:
        a_idx = a.set_index(a[key].astype(str))
        b_idx = b.set_index(b[key].astype(str))
        for cid in sorted(common):
            ra, rb = a_idx.loc[cid], b_idx.loc[cid]
            field_diffs = {
                f: [ra.get(f), rb.get(f)]
                for f in tracked
                if f in a.columns and f in b.columns and _ne(ra.get(f), rb.get(f))
            }
            if field_diffs:
                modified[cid] = field_diffs
    return added, removed, modified


def feed_diff(a: Mapping[str, pd.DataFrame], b: Mapping[str, pd.DataFrame]) -> FeedDiff:
    s_added, s_removed, s_modified = _diff_records(
        a["stops"], b["stops"], key="stop_id", tracked=STOP_TRACKED_FIELDS,
    )
    r_added, r_removed, r_modified = _diff_records(
        a["routes"], b["routes"], key="route_id", tracked=ROUTE_TRACKED_FIELDS,
    )
    return FeedDiff(
        stops_added=s_added, stops_removed=s_removed, stops_modified=s_modified,
        routes_added=r_added, routes_removed=r_removed, routes_modified=r_modified,
        stop_jaccard=_jaccard(set(a["stops"]["stop_id"].astype(str)),
                              set(b["stops"]["stop_id"].astype(str))),
        route_jaccard=_jaccard(set(a["routes"]["route_id"].astype(str)),
                               set(b["routes"]["route_id"].astype(str))),
    )
```

- [ ] **Step 4: Run tests + commit**

```powershell
..\venv\Scripts\pytest tests/panel_pipeline/test_diff_feed_diff.py -v
```

Expected: 3 PASS.

```bash
git add backend/app/services/panel_pipeline/diff/__init__.py \
        backend/app/services/panel_pipeline/diff/feed_diff.py \
        backend/tests/panel_pipeline/test_diff_feed_diff.py
git commit -m "feat(panel.diff): feed-pair stop/route diff"
```

---

## Task 1.2: Reorg detector with Jaccard thresholds

**Files:**
- Create: `backend/app/services/panel_pipeline/diff/reorg_detect.py`
- Create: `backend/app/services/panel_pipeline/data/reorg_thresholds.yaml`
- Test: `backend/tests/panel_pipeline/test_diff_reorg_detect.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import pytest

from app.services.panel_pipeline.diff.feed_diff import FeedDiff
from app.services.panel_pipeline.diff.reorg_detect import ReorgVerdict, detect_reorg


def _diff(stop_j: float, route_j: float) -> FeedDiff:
    return FeedDiff([], [], {}, [], [], {}, stop_j, route_j)


def test_no_reorg_at_full_jaccard():
    v = detect_reorg(_diff(1.0, 1.0))
    assert v.detected is False
    assert v.severity is None


def test_minor_reorg():
    v = detect_reorg(_diff(0.95, 0.78))
    assert v.detected is True
    assert v.severity == "minor"


def test_major_reorg():
    v = detect_reorg(_diff(0.80, 0.55))
    assert v.detected is True
    assert v.severity == "major"


def test_massive_reorg():
    v = detect_reorg(_diff(0.50, 0.27))
    assert v.detected is True
    assert v.severity == "massive"


def test_route_jaccard_dominates():
    """If stops are stable but routes are gutted, severity should still escalate."""
    v = detect_reorg(_diff(stop_j=0.99, route_j=0.30))
    assert v.severity == "massive"
```

- [ ] **Step 2: Run test → fails**

- [ ] **Step 3: Implement `reorg_detect.py`**

```python
"""Reorg detector. Verdict driven by min(stop_jaccard, route_jaccard) per spec §3.1.

Thresholds in data/reorg_thresholds.yaml — overridden per Discovery Task D6 output.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from app.services.panel_pipeline.diff.feed_diff import FeedDiff


THRESHOLDS_PATH = Path(__file__).resolve().parent.parent / "data" / "reorg_thresholds.yaml"


Severity = Literal["minor", "major", "massive"]


@dataclass(frozen=True, slots=True)
class ReorgVerdict:
    detected: bool
    severity: Severity | None
    stop_jaccard: float
    route_jaccard: float
    threshold_version: str


def _load_thresholds() -> dict:
    return yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8"))


def detect_reorg(diff: FeedDiff) -> ReorgVerdict:
    cfg = _load_thresholds()
    j = min(diff.stop_jaccard, diff.route_jaccard)
    if j >= cfg["minor_min"]:        # j ∈ [0.85, 1.0] → no reorg
        return ReorgVerdict(False, None, diff.stop_jaccard, diff.route_jaccard, cfg["version"])
    if j >= cfg["major_min"]:        # [0.7, 0.85)
        sev: Severity = "minor"
    elif j >= cfg["massive_min"]:    # [0.5, 0.7)
        sev = "major"
    else:                            # < 0.5
        sev = "massive"
    return ReorgVerdict(True, sev, diff.stop_jaccard, diff.route_jaccard, cfg["version"])
```

Create `data/reorg_thresholds.yaml`:

```yaml
# Initial provisional cuts. Refined by D6 (Task 1.3).
version: v1-provisional
minor_min: 0.85       # j ≥ 0.85 → no reorg
major_min: 0.70       # [0.70, 0.85) → minor
massive_min: 0.50     # [0.50, 0.70) → major; < 0.50 → massive
```

- [ ] **Step 4: Run tests + commit**

```bash
..\venv\Scripts\pytest tests/panel_pipeline/test_diff_reorg_detect.py -v
git add backend/app/services/panel_pipeline/diff/reorg_detect.py \
        backend/app/services/panel_pipeline/data/reorg_thresholds.yaml \
        backend/tests/panel_pipeline/test_diff_reorg_detect.py
git commit -m "feat(panel.diff): reorg detector with tunable Jaccard thresholds"
```

---

## Task 1.3: D6 — threshold tuning pilot

**Files:**
- Create: `backend/scripts/discovery/d6_reorg_thresholds.py`
- Create: `docs/superpowers/specs/2026-05-XX-d6-reorg-detector-discovery.md` (script-generated)

- [ ] **Step 1: Pull pilot feeds**

Three known-reorg pairs + one known-stable pair; download via Plan 1's `d1b_dedup_per_network`:

```powershell
# True positives (known reorgs)
..\venv\Scripts\python scripts\discovery\d1b_dedup_per_network.py --short-id <bordeaux> --name bordeaux --steps fetch resolve dedup download
..\venv\Scripts\python scripts\discovery\d1b_dedup_per_network.py --short-id <toulouse> --name toulouse --steps fetch resolve dedup download
..\venv\Scripts\python scripts\discovery\d1b_dedup_per_network.py --short-id <nantes>  --name nantes  --steps fetch resolve dedup download
# True negative
..\venv\Scripts\python scripts\discovery\d1b_dedup_per_network.py --short-id <strasbourg> --name strasbourg --steps fetch resolve dedup download
```

Pick the dedup'd feeds straddling the known reorg dates (Bordeaux Sep 2024, Toulouse 2024, Nantes 2023), and 5 sequential Strasbourg pairs (2018-2022, no known reorg).

- [ ] **Step 2: Implement script**

Create `backend/scripts/discovery/d6_reorg_thresholds.py`:

```python
"""D6 — Reorg detector threshold tuning. Spec §12 v0.2.

Output:
  - docs/superpowers/specs/2026-05-XX-d6-reorg-detector-discovery.md
  - Updated reorg_thresholds.yaml (or recommendation block if user must adjust manually)
"""
from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path

import pandas as pd

from app.services.gtfs_core.gtfs_reader import read_gtfs_zip
from app.services.panel_pipeline.diff.feed_diff import feed_diff
from app.services.panel_pipeline.diff.reorg_detect import detect_reorg


CACHE = Path(__file__).resolve().parents[2] / "storage" / "discovery"
REPORT = (
    Path(__file__).resolve().parents[3]
    / "docs" / "superpowers" / "specs"
    / f"2026-05-{datetime.now().day:02d}-d6-reorg-detector-discovery.md"
)


PAIRS = [
    # (label, network_dir, feed_a_zip, feed_b_zip, expected_reorg)
    ("bordeaux-2024", "bordeaux", "pre_2024_09.zip", "post_2024_09.zip", True),
    ("toulouse-2024", "toulouse", "pre_2024.zip", "post_2024.zip", True),
    ("nantes-2023",   "nantes",   "pre_2023.zip", "post_2023.zip", True),
    ("strasbourg-2018-2019", "strasbourg", "2018.zip", "2019.zip", False),
    ("strasbourg-2019-2020", "strasbourg", "2019.zip", "2020.zip", False),
    ("strasbourg-2020-2021", "strasbourg", "2020.zip", "2021.zip", False),
    ("strasbourg-2021-2022", "strasbourg", "2021.zip", "2022.zip", False),
]


def main() -> None:
    rows: list[dict] = []
    for label, net, a, b, expected in PAIRS:
        zip_a = CACHE / "d1_pan" / f"{net}_archive" / a
        zip_b = CACHE / "d1_pan" / f"{net}_archive" / b
        feed_a = read_gtfs_zip(zip_a)
        feed_b = read_gtfs_zip(zip_b)
        d = feed_diff(feed_a, feed_b)
        v = detect_reorg(d)
        rows.append({
            "pair": label, "expected_reorg": expected,
            "stop_jaccard": d.stop_jaccard, "route_jaccard": d.route_jaccard,
            "detected": v.detected, "severity": v.severity,
            "correct": v.detected == expected,
        })
    df = pd.DataFrame(rows)

    # Confusion matrix
    tp = df.query("expected_reorg & detected").shape[0]
    fp = df.query("not expected_reorg & detected").shape[0]
    fn = df.query("expected_reorg & not detected").shape[0]
    tn = df.query("not expected_reorg & not detected").shape[0]
    fpr = fp / max(fp + tn, 1)
    fnr = fn / max(tp + fn, 1)

    REPORT.write_text(
        "# D6 — Reorg Detector Threshold Discovery\n\n"
        f"**Date**: {datetime.now(UTC):%Y-%m-%d}\n\n"
        "## Confusion matrix\n"
        f"- TP {tp} · FP {fp} · FN {fn} · TN {tn}\n"
        f"- FPR {fpr:.1%} (target <5%)\n"
        f"- FNR {fnr:.1%} (target <10%)\n\n"
        "## Per-pair scores\n\n"
        + df.to_markdown(index=False)
        + "\n\n## Recommendation\n\n"
        "If FPR > 5% or FNR > 10%, adjust thresholds in "
        "`backend/app/services/panel_pipeline/data/reorg_thresholds.yaml`. "
        "Bump version to `v1` once values stabilize.\n",
        encoding="utf-8",
    )
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run + verify**

```powershell
..\venv\Scripts\python scripts\discovery\d6_reorg_thresholds.py
```

Expected: report file created. Inspect — adjust `reorg_thresholds.yaml` if FPR > 5% (e.g. lower minor_min to 0.80) or FNR > 10%. Bump `version: v1` once stable.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/discovery/d6_reorg_thresholds.py \
        backend/app/services/panel_pipeline/data/reorg_thresholds.yaml \
        docs/superpowers/specs/2026-05-*-d6-reorg-detector-discovery.md
git commit -m "chore(d6): tune reorg detector thresholds on real fixtures"
```

---

## Task 1.4: Persist diffs + reorg flags

**Files:**
- Create: `backend/app/services/panel_pipeline/diff/persist.py`
- Append: `backend/tests/panel_pipeline/test_diff_persist.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime
import pandas as pd

from app.db.models import PanelFeed, PanelFeedDiff, PanelNetwork, PanelReorgFlag
from app.services.panel_pipeline.diff.feed_diff import FeedDiff
from app.services.panel_pipeline.diff.persist import persist_diff_and_flag
from app.services.panel_pipeline.diff.reorg_detect import ReorgVerdict


def test_persist_idempotent(db_session):
    n = PanelNetwork(slug="lyon", pan_dataset_id="pan-lyon", display_name="TCL")
    db_session.add(n); db_session.flush()
    fa = PanelFeed(network_id=n.network_id, pan_resource_id="r1",
                   published_at=datetime(2024,1,1), feed_start_date=datetime(2024,1,1),
                   gtfs_url="a.zip")
    fb = PanelFeed(network_id=n.network_id, pan_resource_id="r2",
                   published_at=datetime(2024,9,1), feed_start_date=datetime(2024,9,1),
                   gtfs_url="b.zip")
    db_session.add_all([fa, fb]); db_session.commit()

    d = FeedDiff(["S1"], [], {}, ["R1"], [], {}, 0.95, 0.27)
    v = ReorgVerdict(True, "massive", 0.95, 0.27, "v1")

    persist_diff_and_flag(db_session, n.network_id, fa.feed_id, fb.feed_id, d, v)
    persist_diff_and_flag(db_session, n.network_id, fa.feed_id, fb.feed_id, d, v)  # twice
    assert db_session.query(PanelFeedDiff).count() == 1
    assert db_session.query(PanelReorgFlag).count() == 1
```

- [ ] **Step 2: Run + fail**

- [ ] **Step 3: Implement `persist.py`**

```python
"""Persist FeedDiff + ReorgVerdict. Idempotent on (feed_from, feed_to) and (network, feed_to)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import PanelFeedDiff, PanelReorgFlag
from app.services.panel_pipeline.diff.feed_diff import FeedDiff
from app.services.panel_pipeline.diff.reorg_detect import ReorgVerdict


def persist_diff_and_flag(
    session: Session,
    network_id: str,
    feed_from_id: str,
    feed_to_id: str,
    diff: FeedDiff,
    verdict: ReorgVerdict,
) -> None:
    existing_diff = (
        session.query(PanelFeedDiff)
        .filter_by(feed_from_id=feed_from_id, feed_to_id=feed_to_id)
        .one_or_none()
    )
    if existing_diff is None:
        session.add(PanelFeedDiff(
            network_id=network_id, feed_from_id=feed_from_id, feed_to_id=feed_to_id,
            stops_added=diff.stops_added, stops_removed=diff.stops_removed,
            stops_modified=diff.stops_modified,
            routes_added=diff.routes_added, routes_removed=diff.routes_removed,
            routes_modified=diff.routes_modified,
            stop_jaccard=diff.stop_jaccard, route_jaccard=diff.route_jaccard,
        ))

    existing_flag = (
        session.query(PanelReorgFlag)
        .filter_by(network_id=network_id, feed_to_id=feed_to_id)
        .one_or_none()
    )
    if existing_flag is None:
        session.add(PanelReorgFlag(
            network_id=network_id, feed_to_id=feed_to_id,
            reorg_detected=verdict.detected, reorg_severity=verdict.severity,
            stop_jaccard=verdict.stop_jaccard, route_jaccard=verdict.route_jaccard,
            threshold_version=verdict.threshold_version,
        ))
    session.commit()
```

- [ ] **Step 4: Run + commit**

```bash
..\venv\Scripts\pytest tests/panel_pipeline/test_diff_persist.py -v
git add backend/app/services/panel_pipeline/diff/persist.py \
        backend/tests/panel_pipeline/test_diff_persist.py
git commit -m "feat(panel.diff): persist diffs + reorg flags"
```

---

# Phase 2 — Indicator Batch 1 (W3): Productivity + Density + Structure (19)

## Task 2.1: `prod_kcc_year` + activate KCC equivalence contract

**Files:**
- Modify: `backend/app/services/panel_pipeline/indicators/productivity.py`
- Modify: `backend/tests/panel_pipeline/test_kcc_equivalence_contract.py` (unskip + fix line 29 bug)
- Modify: `backend/app/services/panel_pipeline/run.py` (add `run_panel_pipeline_for_fixture` helper for the contract test)

- [ ] **Step 1: Fix the contract test**

Edit `backend/tests/panel_pipeline/test_kcc_equivalence_contract.py`:

Remove `@pytest.mark.skip` decorator. Replace line 29 (`expected_kcc = next(iter(expected["kcc_total_per_column"].values()))`) with:

```python
    expected_kcc = expected["kcc_grand_total"]
```

(The baselines.json key is `kcc_grand_total`, not `kcc_total_per_column` — Plan 1 had a stale reference. Verified at `backend/storage/discovery/d4_kcc/baselines.json:22`.)

- [ ] **Step 2: Run test → fails (NotImplementedError)**

```powershell
..\venv\Scripts\pytest tests/panel_pipeline/test_kcc_equivalence_contract.py -v
```

Expected: 3 FAILs — `NotImplementedError: Implemented in Plan 2 Task 1` from `run_panel_pipeline_for_fixture`.

- [ ] **Step 3: Implement `productivity.compute_all` for `prod_kcc_year`**

Edit `backend/app/services/panel_pipeline/indicators/productivity.py`:

```python
"""Spec §5.1 A. Productivity indicators (8 items)."""
from __future__ import annotations

from typing import Mapping

import pandas as pd

from app.services.gtfs_core.gtfs_generator import kcc_course_sl


def compute_all(
    raw: Mapping[str, pd.DataFrame],
    normed: dict,
    lignes: pd.DataFrame,
    sjt: pd.DataFrame,
) -> dict[str, float | None]:
    """Compute all 8 productivity indicators.

    Returns:
        {indicator_id: value}. Missing/unavailable → None.
    """
    out: dict[str, float | None] = {}
    out["prod_kcc_year"] = _kcc_year(normed, lignes, sjt)
    out["prod_lines_count"] = float(raw["routes"]["route_id"].nunique())
    out["prod_stops_count"] = float(
        normed["stops"][normed["stops"].get("location_type", 0).fillna(0).astype(int) == 0]
        ["stop_id"].nunique()
    )
    # Phase 2 Task 2.2/2.3 fill the rest
    return out


def _kcc_year(normed, lignes, sjt) -> float:
    """Spec §11 contract anchor: must match worker pipeline F_3_KCC_Lignes total within 0.1%."""
    # Reproduce the worker pipeline's KCC chain. The exact orchestration
    # (itineraire_generate → itiarc_generate → course_generate → caract_par_sl
    #  → kcc_course_sl) lives in `backend/app/services/worker.py`. Copy the
    # call sequence verbatim — do NOT factor a shared helper yet (premature
    # abstraction risks breaking spec §11 contract). Pass `has_shp=False`
    # so we use Vol_Oiseau Haversine instead of GTFS shape geometries
    # (panel pipeline keeps shape work for V1).
    from app.services.gtfs_core.gtfs_generator import (
        course_generate, itiarc_generate, itineraire_generate, kcc_course_sl,
    )
    iti = itineraire_generate(normed["stop_times"], normed["AP"], normed["trips"])
    iti_arc = itiarc_generate(iti, normed["AG"])
    courses = course_generate(iti, iti_arc)
    # Worker pipeline computes KCC per type_vacances (Hors_Vacances, Vac_A, Vac_B, Vac_C).
    # For prod_kcc_year we sum across all four to match F_3_KCC_Lignes grand total.
    total = 0.0
    for type_vac in ("Hors_Vacances", "Vac_A", "Vac_B", "Vac_C"):
        kcc_df = kcc_course_sl(sjt, courses, type_vac, lignes, has_shp=False)
        total += float(kcc_df["kcc"].sum())
    return total
```

> **NOTE**: The exact intermediate-DataFrame chain to reach `kcc_course_sl(has_shp=False)` is non-trivial — the worker pipeline (`backend/app/services/worker.py`) is the source of truth. Step 3 may need to copy that orchestration verbatim into `productivity._kcc_year` or factor a shared helper. Do whichever keeps the 3-fixture contract green; do not abstract prematurely.

Also implement `run_panel_pipeline_for_fixture` in `run.py`:

```python
from pathlib import Path

from app.services.panel_pipeline.compute import AomMeta, compute

FIXTURE_PATHS = {
    "sem":   Path(__file__).resolve().parents[3] / "tests" / "Resources" / "raw" / "SEM-GTFS(2).zip",
    "solea": Path(__file__).resolve().parents[3] / "tests" / "Resources" / "raw" / "SOLEA.GTFS_current.zip",
    "ginko": Path(__file__).resolve().parents[3] / "tests" / "Resources" / "raw" / "gtfs-20240704-090655.zip",
}


def run_panel_pipeline_for_fixture(fixture: str) -> dict[str, float]:
    """Test helper: run compute() on a packaged fixture with stub AomMeta."""
    from shapely.geometry import box
    meta = AomMeta(slug=fixture, population=1, area_km2=1.0,
                   polygon_l93=box(0, 0, 1, 1), methodology_commit="test")
    bundle = compute(FIXTURE_PATHS[fixture], meta)
    return {k: v["value"] for k, v in bundle.values.items() if v["value"] is not None}
```

- [ ] **Step 4: Run contract test for SEM only first**

```powershell
..\venv\Scripts\pytest tests/panel_pipeline/test_kcc_equivalence_contract.py::test_kcc_equivalence[sem] -v
```

Expected: PASS (panel KCC within 0.1% of `186_963.442`).

- [ ] **Step 5: Then SOLEA, then ginko**

```powershell
..\venv\Scripts\pytest tests/panel_pipeline/test_kcc_equivalence_contract.py -v
```

Expected: 3 PASS. **Do not commit until all three pass.**

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/panel_pipeline/indicators/productivity.py \
        backend/app/services/panel_pipeline/run.py \
        backend/tests/panel_pipeline/test_kcc_equivalence_contract.py
git commit -m "feat(panel.indicators): prod_kcc_year + activate KCC equivalence contract"
```

---

## Task 2.2: Productivity counts (5 indicators)

**Files:** modify `productivity.py`; create `test_indicators_productivity.py`

- [ ] **Step 1: Write tests for `prod_courses_day_avg`, `prod_peak_hour_courses`, `prod_service_amplitude`** (`prod_lines_count`, `prod_stops_count` already covered in Task 2.1)

Test against the 3-fixture cadence: each indicator gets one assertion per fixture comparing against the Plan 1 D4 baseline `courses_grand_total / total_days_in_baseline`.

```python
import pytest
from app.services.panel_pipeline.run import run_panel_pipeline_for_fixture

EXPECTED = {
    "sem":   {"prod_lines_count": 54, "prod_stops_count": ..., "prod_courses_day_avg": ...},
    "solea": {"prod_lines_count": 33, ...},
    "ginko": {"prod_lines_count": ..., ...},
}


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_productivity_counts(fixture: str) -> None:
    out = run_panel_pipeline_for_fixture(fixture)
    for key, val in EXPECTED[fixture].items():
        assert out[key] == pytest.approx(val, rel=0.01), \
            f"{fixture}.{key}: got {out[key]} expected {val}"
```

Fill the `EXPECTED` dict from baselines.json (`n_lines`, `courses_grand_total`) and from running the worker pipeline once to read the actual stops_count. Document the expected values inline.

- [ ] **Step 2: Implement** the 3 missing functions in `productivity.py`. Each is a small dataframe operation (count distinct route_id, sum trips × days_active, etc.). Reuse `sjt` for "active days" weighting.

- [ ] **Step 3: SEM → SOLEA → ginko, then commit**

```bash
git commit -m "feat(panel.indicators): productivity counts (5 indicators)"
```

---

## Task 2.3: Productivity advanced — `prod_network_length_km` + `prod_peak_vehicles_needed`

- [ ] **Step 1: Write tests** — for SEM, expected network length matches the worker pipeline's `network_km` (from `result_*` query); peak_vehicles formula = `Σ_route ⌈peak_round_trip_time / peak_headway⌉`.

- [ ] **Step 2: Implement**:

`prod_network_length_km`: distinct stop-pair Haversine sum per route, then network-wide deduplication of segments (use a set of `frozenset({stop_a, stop_b})` keyed segments).

`prod_peak_vehicles_needed`: per route, find peak hour (HPM 07:00-09:00 or HPS 17:00-19:00), compute `⌈round_trip_min / peak_headway_min⌉`, sum across routes.

- [ ] **Step 3: 3-fixture green → commit**

```bash
git commit -m "feat(panel.indicators): network length + peak vehicles needed"
```

---

## Task 2.4: Density (4)

- [ ] **Step 1: Create `tests/panel_pipeline/data/aom_meta_fixtures.yaml`**:

```yaml
sem:   {population: 445000, area_km2: 541.0}
solea: {population: 220000, area_km2: 380.0}
ginko: {population: 192000, area_km2: 213.0}
```

- [ ] **Step 2: Test all 4 density ratios** as plain arithmetic against Task 2.1–2.3 outputs.

- [ ] **Step 3: Implement `density.compute_all`** — pure arithmetic on `(prev_values, meta)`.

- [ ] **Step 4: 3-fixture green → commit**

```bash
git commit -m "feat(panel.indicators): density (4 indicators)"
```

---

## Task 2.5: Structure modal mix (4)

- [ ] **Step 1: Test** `struct_modal_mix_{bus,tram,metro,train}` — fractions of trips per route_type, must sum to ≤ 1.0.

- [ ] **Step 2: Implement** as `(trips × routes).groupby('route_type').size() / total_trips`.

- [ ] **Step 3: 3-fixture green** (ginko has bus only → 100% bus, 0% others — null guards needed).

```bash
git commit -m "feat(panel.indicators): structure modal mix (4 indicators)"
```

---

## Task 2.6: Structure remaining 3

- [ ] **Step 1: Test**:
  - `struct_peak_amplification`: peak / off-peak trip count ratio.
  - `struct_multi_route_stops_pct`: % of stops served by ≥2 routes.
  - `struct_route_directness`: median over routes of `cumulative_haversine(stop_seq) / great_circle(origin, terminus)`. Document Assumption A8 ("shape-free approximation") in docstring.

- [ ] **Step 2: Implement** in `structure.compute_all`. Gracefully handle single-stop or single-route edge cases.

- [ ] **Step 3: 3-fixture green → commit**

```bash
git commit -m "feat(panel.indicators): structure peak/multi-route/directness"
```

---

# Phase 3 — Indicator Batch 2 (W4): Frequency + Coverage (10)

> **Order note**: Frequency tasks land BEFORE Coverage because `coverage.compute_all`
> consumes `frequency._peak_headway_per_route` to identify high-frequency stops
> (Assumption A7). Implementing Coverage first would import an undefined helper.

## Task 3.1: Coverage geo.py extensions — `cov_pop_freq_300m` + `cov_equity_gini`

**Files:** modify `geo.py`; extend `test_geo.py`

- [ ] **Step 1: Test** synthetic 4-cell carroyage where 3 cells have stops in high-freq lines → assert `cov_pop_freq_300m`. Synthetic Gini=0.25 case for `cov_equity_gini`.

- [ ] **Step 2: Implement**:

```python
def compute_freq_coverage(
    stops_freq: gpd.GeoDataFrame,           # stops served by ≥1 high-freq line (caller filters)
    carroyage: gpd.GeoDataFrame,
    aom_polygon: gpd.GeoDataFrame,
    *, buffer_m: int = DEFAULT_BUFFER_M,
) -> dict[str, float]:
    """Return cov_pop_freq_300m. Reuses compute_coverage internals on filtered stops."""
    if len(stops_freq) == 0:
        return {"cov_pop_freq_300m": 0.0}
    res = compute_coverage(stops_freq, carroyage, aom_polygon, buffer_m=buffer_m)
    return {"cov_pop_freq_300m": res["cov_pop_300m"]}


def compute_equity_gini(carroyage_in_aom_with_coverage: gpd.GeoDataFrame) -> dict[str, float]:
    """Per-IRIS coverage rate Gini.

    Input: carroyage_in_aom annotated with `is_covered` (bool) per cell.
    Aggregates to IRIS via cell→IRIS field if present, else returns Gini over cell-level.
    """
    # Standard Gini formula
    rates = carroyage_in_aom_with_coverage["coverage_rate"].sort_values().values
    n = len(rates)
    if n < 2:
        return {"cov_equity_gini": 0.0}
    cumvals = (rates * (n - 2 * (rates.argsort().argsort() + 1) + n + 1)).sum()
    gini = cumvals / (n * rates.sum()) if rates.sum() > 0 else 0.0
    return {"cov_equity_gini": float(gini)}
```

- [ ] **Step 3: 3-fixture green → commit**

```bash
git commit -m "feat(panel.geo): coverage freq-stops + IRIS Gini"
```

---

## Task 3.2: Frequency & speed (4) — implements `_peak_headway_per_route`

**Files:** modify `indicators/frequency.py`; create `test_indicators_frequency.py`

- [ ] **Step 1: Test** all 4 frequency indicators across 3 fixtures.

- [ ] **Step 2: Implement** `frequency.compute_all(raw, normed, sjt)`:

```python
def _peak_headway_per_route(raw, normed, sjt) -> dict[str, float | None]:
    """Median peak headway (minutes) per route_id. Used by coverage.cov_pop_freq_300m too."""
    # Filter stop_times to peak hour windows (HPM 07:00-09:00, HPS 17:00-19:00)
    # Group by (route_id, stop_id, hour) → count trips → headway = 60 / count
    # Return {route_id: median_over_(stops, hours) of headway}
    ...


def compute_all(raw, normed, sjt) -> dict[str, float | None]:
    headways = _peak_headway_per_route(raw, normed, sjt)
    valid = [h for h in headways.values() if h is not None]
    out = {
        "freq_peak_headway_median": float(median(valid)) if valid else None,
        "freq_high_freq_lines_pct": (
            100 * sum(1 for h in valid if h <= 10) / len(valid) if valid else 0.0
        ),
        "freq_daily_service_hours": _mean_amplitude_weekdays(normed, sjt),
        "freq_commercial_speed_kmh": _commercial_speed(normed),
    }
    return out
```

`freq_commercial_speed_kmh = Σ trip_distance_km / Σ trip_duration_hours`. Reuse trip distance dict cached from Task 2.1's KCC computation by stashing it on `raw` (sentinel key `_kcc_trip_distance_km`).

- [ ] **Step 3: 3-fixture green → commit**

```bash
git commit -m "feat(panel.indicators): frequency & speed (4 indicators)"
```

---

## Task 3.3: Coverage adapter in `indicators/coverage.py`

**Files:** modify `coverage.py` (currently a stub)

- [ ] **Step 1: Test** end-to-end via D2 cached carroyage subset — Grenoble/SEM produces all 6 cov_* indicators non-null.

- [ ] **Step 2: Implement `coverage.compute_all(raw, normed, meta)`**:

```python
"""Wraps panel_pipeline.geo for the 6 coverage indicator IDs."""
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

from app.services.panel_pipeline.geo import (
    compute_coverage, compute_equity_gini, compute_freq_coverage,
    gtfs_stops_to_geodataframe, load_carroyage_200m,
)


CARROYAGE_PATH = Path(__file__).resolve().parents[2] / "data" / "Filosofi2017_carreaux_200m.gpkg"


def compute_all(raw, normed, meta) -> dict[str, float | None]:
    if not CARROYAGE_PATH.exists():
        raise FileNotFoundError(CARROYAGE_PATH)
    aom = gpd.GeoDataFrame(geometry=[meta.polygon_l93], crs="EPSG:2154")
    bbox = aom.total_bounds
    carro = load_carroyage_200m(CARROYAGE_PATH, bbox_l93=tuple(bbox))
    stops_gdf = gtfs_stops_to_geodataframe(normed["stops"])
    base = compute_coverage(stops_gdf, carro, aom)
    # Assumption A7: a route is "high-frequency" iff its median peak headway ≤ 10 min.
    # Compute peak headway per route from sjt + stop_times, then filter stop_ids.
    from app.services.panel_pipeline.indicators.frequency import _peak_headway_per_route
    headways = _peak_headway_per_route(raw, normed, sjt)            # {route_id: median_min}
    high_freq_routes = {r for r, h in headways.items() if h is not None and h <= 10}
    high_freq_stop_ids = set(
        normed["stop_times"]
        .merge(normed["trips"][["trip_id", "route_id"]], on="trip_id")
        .loc[lambda d: d["route_id"].isin(high_freq_routes), "stop_id"]
        .unique()
    )
    freq_stops = stops_gdf[stops_gdf["stop_id"].isin(high_freq_stop_ids)]
    freq = compute_freq_coverage(freq_stops, carro, aom) if len(freq_stops) else {"cov_pop_freq_300m": 0.0}
    # Build per-cell coverage_rate for Gini: 1.0 if cell intersects 300m buffer, else 0.0
    carroyage_in_aom = gpd.overlay(carro, aom, how="intersection")
    buffer_union = stops_gdf.geometry.buffer(300).unary_union
    carroyage_in_aom["coverage_rate"] = carroyage_in_aom.geometry.intersects(buffer_union).astype(float)
    gini = compute_equity_gini(carroyage_in_aom)
    return {
        "cov_pop_300m": base["cov_pop_300m"],
        "cov_pop_freq_300m": freq["cov_pop_freq_300m"],
        "cov_surface_300m": base["cov_surface_300m"],
        "cov_median_walk": base["cov_median_walk"],
        "cov_pop_weighted_walk": base["cov_pop_weighted_walk"],
        "cov_equity_gini": gini["cov_equity_gini"],
    }
```

- [ ] **Step 3: 3-fixture green** — note that ginko AOM polygon may not be in D2 cache yet; if missing, `coverage.compute_all` raises FileNotFoundError, and `compute()` (Task 0.3) catches it and fills 6 cov_* with `None` + `errors[]`. Test for both happy path (SEM) and missing-AOM path (synthetic).

```bash
git commit -m "feat(panel.indicators): coverage (6 indicators)"
```

---

# Phase 4 — DSP Loader (W4.5, parallel-safe)

## Task 4.1: D5 — DSP timeline curation pilot (5 networks)

**Files:**
- Create: `methodology/data/dsp_timeline.csv` (in the methodology repo, NOT this repo)
- Create: `docs/superpowers/specs/2026-05-XX-d5-dsp-timeline-discovery.md`

- [ ] **Step 1: Initialize methodology repo skeleton**

```powershell
cd C:\Users\wei.si\Projets
mkdir compare-transit-methodology
cd compare-transit-methodology
git init
mkdir -p data methodology indicators_formulas
```

Create `data/dsp_timeline.csv` with the schema header from spec §22.2:

```csv
network_slug,event_type,event_date,operator_before,operator_after,contract_id,contract_value_eur,boamp_url,notes,source,contributor
```

- [ ] **Step 2: Curate 5 pilot networks** (Lyon, Bordeaux, Strasbourg, Nantes, Toulouse) — search BOAMP / GART annual reports / Mobilités Magazine archives for past 8 years of DSP events. Estimated 5 events × 5 networks × 5 min ≈ 2 hours.

- [ ] **Step 3: Generate D5 report** at `docs/superpowers/specs/2026-05-XX-d5-dsp-timeline-discovery.md`:

```markdown
# D5 — DSP Timeline Curation Pilot

**Date**: 2026-05-XX
**Networks**: Lyon TCL, Bordeaux TBM, Strasbourg CTS, Nantes TAN, Toulouse Tisséo
**Output**: methodology/data/dsp_timeline.csv (25–35 rows)

## Workload measurement
- Time per event (median, IQR): _____
- Hardest event types: _____
- Verifiable source URL coverage: ___% of rows

## Recommendation
- Extrapolation to 30 networks: ~12 hours (1.5 days)
- V1 BOAMP automation priority: _____
```

- [ ] **Step 4: Commit (in methodology repo + this repo)**

```bash
# In methodology repo
git -C ../compare-transit-methodology add data/dsp_timeline.csv
git -C ../compare-transit-methodology commit -m "chore(d5): DSP timeline pilot (5 networks)"

# In this repo
git add docs/superpowers/specs/2026-05-*-d5-dsp-timeline-discovery.md
git commit -m "docs(d5): DSP timeline curation pilot report"
```

---

## Task 4.2: `load_dsp_events.py` with row-hash idempotency

**Files:**
- Create: `backend/scripts/load_dsp_events.py`
- Create: `backend/tests/panel_pipeline/test_dsp_loader.py`
- Create: `backend/tests/fixtures/dsp_timeline_sample.csv`

- [ ] **Step 1: Test** (per Assumption A2 — hash includes notes)

```python
import hashlib
from pathlib import Path

from app.db.models import PanelDspEvent, PanelNetwork
from scripts.load_dsp_events import compute_row_hash, load_dsp_events


SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "dsp_timeline_sample.csv"


def test_compute_row_hash_includes_notes():
    base = {"network_slug": "lyon", "event_type": "contract_started",
            "event_date": "2017-09-01", "operator_before": "",
            "operator_after": "Keolis", "source": "BOAMP",
            "boamp_url": "https://boamp.fr/...", "notes": "v1"}
    h1 = compute_row_hash(base)
    h2 = compute_row_hash({**base, "notes": "v2"})
    assert h1 != h2


def test_load_dsp_events_idempotent(db_session):
    db_session.add(PanelNetwork(slug="lyon", pan_dataset_id="x", display_name="TCL"))
    db_session.commit()

    n_inserted_a = load_dsp_events(db_session, SAMPLE)
    n_inserted_b = load_dsp_events(db_session, SAMPLE)
    assert n_inserted_a > 0
    assert n_inserted_b == 0    # all hashes already present


def test_load_dsp_events_edit_appends_new_row(db_session, tmp_path):
    db_session.add(PanelNetwork(slug="lyon", pan_dataset_id="x", display_name="TCL"))
    db_session.commit()
    load_dsp_events(db_session, SAMPLE)
    initial = db_session.query(PanelDspEvent).count()

    # Mutate notes column on row 1
    edited = tmp_path / "edited.csv"
    edited.write_text(SAMPLE.read_text(encoding="utf-8").replace("v1-pilot", "v2-revised"),
                      encoding="utf-8")
    n_inserted_b = load_dsp_events(db_session, edited)
    assert n_inserted_b > 0
    assert db_session.query(PanelDspEvent).count() == initial + n_inserted_b
```

Sample CSV at `backend/tests/fixtures/dsp_timeline_sample.csv`:

```csv
network_slug,event_type,event_date,operator_before,operator_after,contract_id,contract_value_eur,boamp_url,notes,source,contributor
lyon,contract_started,2017-09-01,,Keolis,LYO-2017,,https://boamp.fr/sample,v1-pilot,BOAMP,wei
lyon,tender_published,2024-03-01,Keolis,,LYO-2024,,https://boamp.fr/sample2,v1-pilot,BOAMP,wei
```

- [ ] **Step 2: Implement** `backend/scripts/load_dsp_events.py`:

```python
"""Idempotent loader: methodology/data/dsp_timeline.csv → panel_dsp_events.

Row hash includes `notes` + `boamp_url` (Assumption A2): contributor edits insert
new rows, preserving audit trail. Network timeline UI reads the latest row per
(network, event_type, event_date) tuple.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import PanelDspEvent, PanelNetwork


HASH_FIELDS = (
    "network_slug", "event_type", "event_date",
    "operator_before", "operator_after",
    "source", "boamp_url", "notes",
)


def compute_row_hash(row: dict) -> str:
    payload = "|".join(str(row.get(f, "")) for f in HASH_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_dsp_events(session: Session, csv_path: Path) -> int:
    """Load dsp_timeline.csv into panel_dsp_events. Returns number of rows inserted."""
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    slugs = set(df["network_slug"].unique())
    networks = {
        n.slug: n.network_id
        for n in session.query(PanelNetwork).filter(PanelNetwork.slug.in_(slugs))
    }
    inserted = 0
    for _, r in df.iterrows():
        if r["network_slug"] not in networks:
            print(f"WARN: skipping unknown network_slug={r['network_slug']}")
            continue
        h = compute_row_hash(r.to_dict())
        if session.query(PanelDspEvent).filter_by(csv_row_hash=h).first():
            continue
        session.add(PanelDspEvent(
            network_id=networks[r["network_slug"]],
            event_type=r["event_type"],
            event_date=datetime.fromisoformat(r["event_date"]),
            operator_before=r["operator_before"] or None,
            operator_after=r["operator_after"] or None,
            contract_id=r["contract_id"] or None,
            contract_value_eur=float(r["contract_value_eur"]) if r["contract_value_eur"] else None,
            boamp_url=r["boamp_url"] or None,
            notes=r["notes"] or None,
            source=r["source"],
            contributor=r["contributor"],
            csv_row_hash=h,
        ))
        inserted += 1
    session.commit()
    return inserted


if __name__ == "__main__":
    import sys
    csv = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../compare-transit-methodology/data/dsp_timeline.csv")
    with SessionLocal() as s:
        n = load_dsp_events(s, csv)
        print(f"Loaded {n} new DSP events from {csv}")
```

- [ ] **Step 3: Run + commit**

```bash
..\venv\Scripts\pytest tests/panel_pipeline/test_dsp_loader.py -v
git add backend/scripts/load_dsp_events.py \
        backend/tests/panel_pipeline/test_dsp_loader.py \
        backend/tests/fixtures/dsp_timeline_sample.csv
git commit -m "feat(panel): DSP events loader with row-hash idempotency"
```

---

## Task 4.3: D5 expansion to 30 networks (T1+T2+R/I)

- [ ] **Step 1: Curate** the remaining 25 networks per spec §22.4. ~12 hours.

- [ ] **Step 2: Validate** by running `load_dsp_events.py` against a local DB seeded with all 30 PanelNetworks. Expect ~150 rows inserted.

- [ ] **Step 3: Commit (methodology repo)**

```bash
git -C ../compare-transit-methodology add data/dsp_timeline.csv
git -C ../compare-transit-methodology commit -m "chore(methodology): DSP timeline 30 networks (T1+T2+R/I)"
```

---

# Phase 5 — Indicator Batch 3 (W5): Accessibility + Quality + Environment + Error Margin

## Task 5.1: Accessibility (2)

- [ ] **Step 1: Verify** `gtfs_normalize` preserves `wheelchair_boarding` (stops) and `wheelchair_accessible` (trips). If `stops_norm` (`gtfs_norm.py:81`) strips them, read directly from `raw["stops"]` / `raw["trips"]` rather than touching the worker-pipeline contract.

- [ ] **Step 2: Test + implement**:
```python
out["acc_wheelchair_stops_pct"] = (raw["stops"]["wheelchair_boarding"].fillna(0).astype(int) == 1).mean() * 100
out["acc_wheelchair_trips_pct"] = (raw["trips"]["wheelchair_accessible"].fillna(0).astype(int) == 1).mean() * 100
```
Null guards: if column absent → return None.

- [ ] **Step 3: 3-fixture green → commit**

```bash
git commit -m "feat(panel.indicators): accessibility (2 indicators)"
```

---

## Task 5.2: Promote validator wrapper + 6 dq_* indicators

**Files:** modify `panel_pipeline/quality.py`; create `indicators/quality_indicators.py`

- [ ] **Step 1: Test** validator wrapper on SEM/SOLEA/ginko (D3 already produces JSON reports — re-use cached outputs). Expected: validator_errors count, warnings count, freshness in days, etc.

- [ ] **Step 2: Move** core of `scripts/discovery/d3_validator_wrapper.py` into `panel_pipeline/quality.py` as `run_validator(zip_path: Path) -> ValidationReport`. Keep the discovery script as a thin re-exporter so existing callers don't break.

- [ ] **Step 3: Implement `indicators/quality_indicators.py`** computing all 6 `dq_*`:

```python
def compute_all(zip_path: Path, raw: Mapping[str, pd.DataFrame]) -> dict[str, float]:
    from app.services.panel_pipeline.quality import run_validator
    report = run_validator(zip_path)
    return {
        "dq_validator_errors":       float(report.error_count),
        "dq_validator_warnings":     float(report.warning_count),
        "dq_field_completeness":     _field_completeness(raw),
        "dq_coord_quality":          _coord_quality(raw),
        "dq_route_type_completeness":_route_type_completeness(raw),
        "dq_freshness":              _freshness_days(raw),
    }
```

- [ ] **Step 4: 3-fixture green → commit**

```bash
git commit -m "feat(panel.quality): 6 data-quality indicators on top of MobilityData validator"
```

---

## Task 5.3: Overall quality score + letter grade

**Files:** modify `quality.py`

- [ ] **Step 1: Test** the §5.1 G weighted aggregation:

```python
overall = (0.25 * dq_validator_errors_norm + 0.20 * dq_field_completeness
         + 0.15 * dq_coord_quality + 0.15 * dq_route_type_completeness
         + 0.15 * dq_freshness_score + 0.10 * dq_validator_warnings_norm)
```

Letter grade bands: ≥90 A+, [85,90) A, [80,85) A-, [75,80) B+, ..., <40 F.

- [ ] **Step 2: Implement** `compute_overall(dq_values: dict) -> tuple[float, str]`. Persist via `run.py` (Task 7.1).

- [ ] **Step 3: 3-fixture green → commit**

```bash
git commit -m "feat(panel.quality): overall_score weighted aggregation + letter grade"
```

---

## Task 5.4: Error margin propagation (provisional v0)

**Files:** modify `error_margin.py`; create `test_error_margin.py`

- [ ] **Step 1: Test** the v0 formula (Assumption A1):

```python
import math

import pytest

from app.services.panel_pipeline.error_margin import propagate


def test_zero_error_when_dq_perfect():
    raw = {f"dq_{k}": 100.0 for k in ("validator_errors","validator_warnings",
            "field_completeness","coord_quality","route_type_completeness","freshness")}
    raw["prod_kcc_year"] = 1_000_000.0
    assert propagate("prod_kcc_year", raw) == pytest.approx(0.0)


def test_max_error_when_dq_zero():
    raw = {f"dq_{k}": 0.0 for k in ("validator_errors","validator_warnings",
            "field_completeness","coord_quality","route_type_completeness","freshness")}
    raw["prod_kcc_year"] = 1.0
    margin = propagate("prod_kcc_year", raw)
    expected = math.sqrt(sum([0.25, 0.10, 0.20, 0.15, 0.15, 0.15])) * 1.0
    assert margin == pytest.approx(expected, rel=0.01)


def test_co2_scaled_to_30():
    raw = {f"dq_{k}": 0.0 for k in ("validator_errors","validator_warnings",
            "field_completeness","coord_quality","route_type_completeness","freshness")}
    raw["env_co2_year_estimated"] = 1000.0
    margin = propagate("env_co2_year_estimated", raw)
    expected = math.sqrt(sum([0.25, 0.10, 0.20, 0.15, 0.15, 0.15])) * 30.0
    assert margin == pytest.approx(expected, rel=0.01)


def test_dq_indicator_self_zero():
    """dq_* indicators have empty dq_dependencies → margin = 0."""
    raw = {"dq_validator_errors": 5.0}
    assert propagate("dq_validator_errors", raw) == 0.0
```

- [ ] **Step 2: Implement** `error_margin.py`:

```python
"""Provisional v0 error-margin propagation (Assumption A1).

Formula:
    margin = sqrt(Σ w_i · (1 − dq_i/100)²) × scale_factor[indicator]

Weights from spec §5.1 G overall_score formula. Scale factor in
data/error_margin_scale.yaml. Canonical replacement lands in
methodology/error_propagation.md before W16 launch.
"""
from __future__ import annotations

import math
from pathlib import Path

import yaml

from app.services.panel_pipeline._registry import INDICATOR_REGISTRY


SCALE_PATH = Path(__file__).resolve().parent / "data" / "error_margin_scale.yaml"


# Weights per dq_* — must match §5.1 G overall_score
DQ_WEIGHTS: dict[str, float] = {
    "dq_validator_errors": 0.25,
    "dq_field_completeness": 0.20,
    "dq_coord_quality": 0.15,
    "dq_route_type_completeness": 0.15,
    "dq_freshness": 0.15,
    "dq_validator_warnings": 0.10,
}


def _scale_factor(indicator_id: str) -> float:
    cfg = yaml.safe_load(SCALE_PATH.read_text(encoding="utf-8"))
    return float(cfg["overrides"].get(indicator_id, cfg["default"]))


def propagate(indicator_id: str, raw_values: dict[str, float | None]) -> float:
    """Returns error_margin_pct in [0, 100+] range.

    Args:
        indicator_id: target indicator.
        raw_values: dict containing dq_* values (0-100). Missing → treated as dq_=100 (no degradation).
    """
    meta = INDICATOR_REGISTRY[indicator_id]
    deps = meta.dq_dependencies
    if not deps:
        return 0.0
    sum_sq = 0.0
    for dq in deps:
        w = DQ_WEIGHTS.get(dq, 0.0)
        v = raw_values.get(dq)
        if v is None:
            v = 100.0
        deviation = max(0.0, 1.0 - v / 100.0)
        sum_sq += w * deviation ** 2
    return math.sqrt(sum_sq) * _scale_factor(indicator_id)
```

- [ ] **Step 3: Run + commit**

```bash
..\venv\Scripts\pytest tests/panel_pipeline/test_error_margin.py -v
git add backend/app/services/panel_pipeline/error_margin.py \
        backend/tests/panel_pipeline/test_error_margin.py
git commit -m "feat(panel): error-margin propagation v0 (provisional formula pending methodology repo)"
```

---

## Task 5.5: Environment — `env_co2_year_estimated`

**Files:** modify `environment.py`; create `data/ademe_factors.yaml`

- [ ] **Step 1: Test** the formula = `Σ (KCC_by_route_type × ADEME_factor)`:

```python
def test_co2_pure_bus_network(synthetic_kcc_per_mode):
    out = compute_all({"prod_kcc_year": 1_000_000.0, "kcc_by_route_type": {3: 1_000_000.0}})
    expected_kgCO2 = 1_000_000.0 * ADEME_FACTORS[3]   # bus
    assert out["env_co2_year_estimated"] == pytest.approx(expected_kgCO2 / 1000.0)
```

- [ ] **Step 2: Create** `data/ademe_factors.yaml` with ADEME Base Carbone v23+ values per route_type (cite source URL in YAML comment).

- [ ] **Step 3: Implement** `environment.compute_all(raw_values)`. Requires `kcc_by_route_type` dict — modify `productivity._kcc_year` to also emit per-route_type breakdown into `raw_values["kcc_by_route_type"]` (sentinel key, not a published indicator).

- [ ] **Step 4: 3-fixture green → commit**

```bash
git commit -m "feat(panel.indicators): env_co2_year_estimated with ADEME factors"
```

---

## Task 5.6: End-to-end smoke — `compute()` returns 38 keys

- [ ] **Step 1: Remove** the `try/except NotImplementedError` bridge blocks from `compute.py` (Phase 0 left them in).

- [ ] **Step 2: Test**:

```python
@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_full_38_indicators(fixture: str):
    out = run_panel_pipeline_for_fixture(fixture)
    # ginko may have missing AOM polygon → 6 cov_* values None — accept that
    non_null_count = sum(1 for v in out.values() if v is not None)
    assert non_null_count >= 32, f"{fixture}: only {non_null_count}/38 indicators populated"
```

- [ ] **Step 3: Run + commit**

```bash
..\venv\Scripts\pytest tests/panel_pipeline/ -v
git commit -m "test(panel): full 38-indicator end-to-end on 3 fixtures"
```

---

# Phase 6 — Aggregator + Peer Group manual tier (W6)

## Task 6.1: Z-score + percentile within peer group

**Files:** rewrite `aggregator.py`; create `test_aggregator.py`

- [ ] **Step 1: Test** synthetic peer group of 5 networks with known mean/std → assert z-scores + percentiles correct.

- [ ] **Step 2: Implement** `recompute_zscore_pct(session, network_id)`:

```python
def recompute_zscore_pct(session: Session, network_id: str) -> int:
    """Recompute z-score + percentile for the latest feed of every network in the same tier."""
    network = session.query(PanelNetwork).get(network_id)
    peers = (
        session.query(PanelNetwork)
        .filter(PanelNetwork.tier == network.tier, PanelNetwork.tier.isnot(None))
        .all()
    )
    # Map peer → latest feed_id
    latest = {p.network_id: _latest_feed_id(session, p.network_id) for p in peers}
    n_updated = 0
    for ind_id in INDICATOR_REGISTRY:
        values = {
            net_id: session.query(PanelIndicator.value)
                .filter_by(feed_id=latest[net_id], indicator_id=ind_id).scalar()
            for net_id in latest if latest[net_id]
        }
        clean = {k: v for k, v in values.items() if v is not None}
        if len(clean) < 3:
            continue
        mean = statistics.mean(clean.values())
        stdev = statistics.pstdev(clean.values()) or 1.0
        for net_id, val in clean.items():
            z = (val - mean) / stdev
            pct = sum(1 for v in clean.values() if v <= val) / len(clean) * 100
            _upsert_derived(session, latest[net_id], ind_id,
                            zscore=z, percentile=pct, peer_group_size=len(clean))
            n_updated += 1
    session.commit()
    return n_updated
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(panel.aggregator): z-score + percentile within peer group"
```

---

## Task 6.2: YoY delta vs t−12m feed

- [ ] **Step 1: Test** synthetic feed sequence with known t and t−12m values → expected YoY%.

- [ ] **Step 2: Implement** `recompute_yoy(session, network_id)`. Match feed at t − 12 months ± 30 days. If no match → `yoy_delta_pct = None`.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(panel.aggregator): YoY delta vs t-12m feed"
```

---

## Task 6.3: post_reorg_delta keyed off panel_reorg_flags

- [ ] **Step 1: Test** 4 null cases (no flag, first feed, latest feed, missing prior value) + 1 happy case.

- [ ] **Step 2: Implement** `recompute_post_reorg_delta(session, network_id)`. For each `PanelReorgFlag` of the network: locate the feed immediately before reorg_feed and the reorg_feed itself; compute delta as `(post − pre) / pre × 100` per indicator. Emit None where any precondition fails.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(panel.aggregator): post_reorg_delta keyed off panel_reorg_flags"
```

---

## Task 6.4: Manual tier overrides for 30 head networks + has_metro auto-detect

- [ ] **Step 1: Create** `data/network_tier_overrides.yaml`:

```yaml
# 30 head networks per spec §22.4. T3-T5 fall through to peer_groups.classify_tier.
T1: [paris-idfm, lyon, marseille, lille, toulouse]
T2: [bordeaux, nantes, nice, strasbourg, montpellier, rennes, grenoble, tours, reims, brest]
R: [ter-grand-est, ter-paca, ter-aura, ter-occitanie, ter-na, ter-hdf, ter-normandie, ter-bfc,
    ter-cvl, ter-pdl, ter-bretagne, transilien, rer-bd]
I: []   # 2 specific conseils départementaux added during Task 4.3 expansion (spec §22.4 leaves these unspecified — pick during curation)
```

- [ ] **Step 2: Implement** `peer_groups.apply_tier_overrides(session) -> int` that reads the YAML and updates `PanelNetwork.tier` + `panel_networks.has_metro` (derived from any feed having `route_type=1`). Test: 30 specific slugs end up with the configured tier.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(panel): manual tier overrides for 30 head networks"
```

---

# Phase 7 — Run pipeline + Backfill + API (W7)

## Task 7.1: `run_panel_pipeline(feed_id)` orchestrator

**Files:** rewrite `run.py`; create `test_run_pipeline.py`

- [ ] **Step 1: Test** end-to-end on a fixture with a fake `panel_feeds` row pointing at a packaged ZIP. Assert: 38 rows in `panel_indicators`, 1 row in `panel_quality`, derived row written for known peer group.

- [ ] **Step 2: Implement**:

```python
def run_panel_pipeline(feed_id: str) -> None:
    """Production path: load feed → compute → persist → trigger aggregator."""
    with SessionLocal() as session:
        feed = session.query(PanelFeed).get(feed_id)
        network = session.query(PanelNetwork).get(feed.network_id)

        # 1. Resolve local ZIP (R2 cache or download)
        zip_path = _ensure_local(feed)

        # 2. Build AomMeta — methodology_commit resolved here once
        from app.services.panel_pipeline.geo import load_aom_polygon
        polygon = load_aom_polygon(...)
        meta = AomMeta(slug=network.slug, population=network.population,
                       area_km2=network.area_km2, polygon_l93=polygon.geometry.iloc[0],
                       methodology_commit=_resolve_methodology_commit())

        # 3. Pure compute
        bundle = compute(zip_path, meta)

        # 4. Persist indicators
        for ind_id, v in bundle.values.items():
            session.merge(PanelIndicator(
                feed_id=feed.feed_id, indicator_id=ind_id,
                value=v["value"], unit=v["unit"],
                error_margin_pct=v["error_margin_pct"],
                methodology_commit=v["methodology_commit"],
            ))

        # 5. Persist quality (overall_score + grade)
        dq_values = {k: bundle.values[k]["value"] for k in bundle.values if k.startswith("dq_")}
        score, grade = compute_overall(dq_values)
        validator_report = run_validator(zip_path)
        session.merge(PanelQuality(
            feed_id=feed.feed_id,
            overall_score=score, overall_grade=grade,
            validator_errors=validator_report.to_dict(),
        ))

        # 6. Diff against previous feed + reorg flag
        prev = _previous_feed(session, network.network_id, feed.feed_start_date)
        if prev:
            diff = feed_diff(read_gtfs_zip(_ensure_local(prev)), read_gtfs_zip(zip_path))
            verdict = detect_reorg(diff)
            persist_diff_and_flag(session, network.network_id, prev.feed_id, feed.feed_id,
                                  diff, verdict)

        feed.process_status = "ok"
        session.commit()

    # 7. Trigger aggregator (separate session)
    with SessionLocal() as session:
        recompute_zscore_pct(session, feed.network_id)
        recompute_yoy(session, feed.network_id)
        recompute_post_reorg_delta(session, feed.network_id)
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(panel.run): full feed pipeline orchestration"
```

---

## Task 7.2: Celery task + monthly beat schedule

**Files:** modify `backend/app/services/worker.py` (add panel task) + Celery beat config

- [ ] **Step 1: Test** Celery task invocation via `celery_app.send_task('panel.run', args=[feed_id])` in test mode.

- [ ] **Step 2: Implement**:

```python
@celery_app.task(name="panel.run", bind=True, max_retries=2)
def panel_run_task(self, feed_id: str) -> None:
    try:
        run_panel_pipeline(feed_id)
    except Exception as e:
        with SessionLocal() as s:
            feed = s.query(PanelFeed).get(feed_id)
            feed.process_status = "failed"
            feed.error_message = str(e)[:1000]
            s.commit()
        raise self.retry(exc=e, countdown=60)
```

Plus monthly beat in `celery_app.conf.beat_schedule` triggering `panel.discover_new_feeds` (a future task — placeholder).

- [ ] **Step 3: Verify** Windows-friendly via `celery -A app.services.worker worker -P solo` (CLAUDE.md feedback).

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(panel.celery): monthly cron + per-feed failure isolation"
```

---

## Task 7.3: Full PAN backfill driver

**Files:**
- Create: `backend/scripts/run_panel_backfill.py`
- Promote: `backend/scripts/discovery/d1b_dedup_per_network.py` core into `panel_pipeline/history_resolver.py` (per `pan_client.py:11` TODO)

- [ ] **Step 1: Test** by running the driver against a 3-network subset (Strasbourg, Lyon, SEM) with `--limit 3`. Assert: feeds enqueued, 38 indicators landed for each.

- [ ] **Step 2: Implement** `scripts/run_panel_backfill.py`:

```python
"""PAN full backfill driver.

Reads d1_pan/datasets_gtfs_inventory.csv → for each dataset, runs the dedup'd
history resolver → enqueues panel.run for each distinct feed.

Estimated runtime: 463 networks × ~65 feeds avg × ~30s/feed / 4 workers ≈ 63h.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from app.db.database import SessionLocal
from app.services.panel_pipeline.history_resolver import resolve_distinct_feeds
from app.services.panel_pipeline.pan_client import register_network
from app.services.worker import panel_run_task


def main(limit: int | None) -> None:
    inv = pd.read_csv("storage/discovery/d1_pan/datasets_gtfs_inventory.csv")
    if limit:
        inv = inv.head(limit)
    with SessionLocal() as s:
        for _, row in inv.iterrows():
            net = register_network(s, row)        # idempotent upsert
            for feed in resolve_distinct_feeds(s, net):
                panel_run_task.delay(feed.feed_id)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int)
    main(p.parse_args().limit)
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(panel): full PAN backfill driver"
```

---

## Task 7.4: Panel API endpoints (8 v0.1 + 5 v0.2)

**Files:**
- Create: `backend/app/api/endpoints/panel.py`
- Create: `backend/app/api/schemas/panel.py`
- Create: `backend/tests/api/test_panel_endpoints.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: Test** one endpoint per spec §8.1. Happy-path only — verify status 200, audit-grade structure, Cache-Control header.

```python
def test_get_network(client, seeded_db):
    r = client.get("/api/v1/panel/networks/lyon")
    assert r.status_code == 200
    j = r.json()
    assert j["slug"] == "lyon"
    assert "indicators" in j
    sample = j["indicators"]["prod_kcc_year"]
    # Audit-grade required fields per §8.2
    assert "value" in sample and "error_margin_pct" in sample
    assert "source_feed_id" in sample and "computed_at" in sample
    assert "methodology_commit" in sample and "methodology_url" in sample
    assert sample["methodology_url"].startswith("https://github.com/")


def test_dsp_events_per_network(client, seeded_db):
    r = client.get("/api/v1/panel/networks/lyon/dsp-events")
    assert r.status_code == 200
    assert isinstance(r.json()["events"], list)


def test_reorg_events_global_filter(client, seeded_db):
    r = client.get("/api/v1/panel/reorg-events/global?year=2024&severity=major")
    assert r.status_code == 200


def test_cache_headers(client, seeded_db):
    r = client.get("/api/v1/panel/networks")
    assert r.headers["Cache-Control"] == "public, max-age=3600, s-maxage=86400"
```

- [ ] **Step 2: Implement** Pydantic v2 response schemas in `app/api/schemas/panel.py`:

```python
from pydantic import BaseModel, Field


class IndicatorValueOut(BaseModel):
    value: float | None
    unit: str
    error_margin_pct: float | None
    source_feed_id: str | None
    computed_at: str
    methodology_commit: str
    methodology_url: str = Field(
        description="GitHub permalink to formula at methodology_commit"
    )


class NetworkDetailOut(BaseModel):
    slug: str
    display_name: str
    tier: str | None
    population: int | None
    area_km2: float | None
    indicators: dict[str, IndicatorValueOut]


class DspEventOut(BaseModel):
    event_id: str
    event_type: str
    event_date: str
    operator_before: str | None
    operator_after: str | None
    boamp_url: str | None
    notes: str | None
    source: str


class ReorgEventOut(BaseModel):
    network_slug: str
    feed_to_id: str
    severity: str
    stop_jaccard: float
    route_jaccard: float
    detected_at: str


# ... etc per §8 (8 v0.1 + 5 v0.2 response models)
```

- [ ] **Step 3: Implement** the 13 endpoints in `app/api/endpoints/panel.py`. Mount under `/api/v1/panel/`. Add `Cache-Control: public, max-age=3600, s-maxage=86400` middleware. URL of methodology files computed as:

```python
def _methodology_url(indicator_id: str, commit: str) -> str:
    return (
        f"https://github.com/compare-transit/methodology/blob/{commit}"
        f"/indicators_formulas/{indicator_id}.py"
    )
```

- [ ] **Step 4: Register router** in `main.py`:

```python
from app.api.endpoints import panel
app.include_router(panel.router, prefix="/api/v1/panel", tags=["panel"])
```

- [ ] **Step 5: 13 endpoint tests green → commit**

```bash
..\venv\Scripts\pytest tests/api/test_panel_endpoints.py -v
git add backend/app/api/endpoints/panel.py \
        backend/app/api/schemas/panel.py \
        backend/tests/api/test_panel_endpoints.py \
        backend/app/main.py
git commit -m "feat(api): panel endpoints (v0.1 + v0.2 audit-grade)"
```

---

## Task 7.5: R2 archival hook

- [ ] **Step 1: Test** double-archive idempotency on checksum.

- [ ] **Step 2: Implement** in `pan_client.py`:

```python
def archive_to_r2(zip_bytes: bytes, sha256: str) -> str:
    """Idempotent R2 PUT keyed by sha256. Returns r2_path."""
    key = f"feeds/{sha256[:2]}/{sha256}.zip"
    if not _r2_exists(key):
        _r2_put(key, zip_bytes)
    return key
```

Wire `run_panel_pipeline` Step 4 (Task 7.1) to call this after compute, populate `PanelFeed.r2_path`.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(panel): R2 archival of fetched feeds"
```

---

# Verification

End-to-end smoke (run after Task 7.5):

```powershell
cd backend

# 1. Run full test suite
..\venv\Scripts\pytest -v

# 2. Run a real backfill on 3 networks
..\venv\Scripts\python scripts\run_panel_backfill.py --limit 3

# 3. Start API, query an endpoint
..\venv\Scripts\uvicorn app.main:app --reload &
curl http://localhost:8000/api/v1/panel/networks/lyon | jq .indicators.prod_kcc_year
```

Expected output (jq):
```json
{
  "value": 24300000,
  "unit": "km",
  "error_margin_pct": 2.1,
  "source_feed_id": "uuid-...",
  "computed_at": "2026-04-01T12:00:00+00:00",
  "methodology_commit": "a3f2c1d",
  "methodology_url": "https://github.com/compare-transit/methodology/blob/a3f2c1d/indicators_formulas/prod_kcc_year.py"
}
```

Acceptance:
- [ ] All 24 tasks committed
- [ ] `pytest` green (all v0.1 + v0.2 panel tests + KCC contract activated + 38-indicator end-to-end)
- [ ] Backfill driver smoke-runs on 3 networks
- [ ] One API call returns audit-grade structure
- [ ] D5 + D6 reports landed in `docs/superpowers/specs/`
- [ ] `methodology/data/dsp_timeline.csv` populated with 30 networks
- [ ] `panel_reorg_flags` non-empty for known-reorg fixtures (Bordeaux 2024, Toulouse 2024, Nantes 2023)

---

# Open questions deferred to Plan 3+

| # | Question | Where it surfaces |
|---|---|---|
| Q-EM-canon | Canonical error-margin formula in `methodology/error_propagation.md` | Must land before W16 launch (Plan 4) |
| Q-API-pagination | `/feed-diff?from=&to=` payload size on large networks | If JSON > 500 KB on IDFM, add `?limit=` param |
| Q-METHO-URL-cdn | `methodology_url` 302-redirect through compare-transit.fr to avoid GitHub rate limits? | Plan 3 / Plan 4 launch hardening |
| Q-V1-private-upload | Pro tier private GTFS upload — reuses pure `compute()` from Task 0.3 | V1 (post-MVP) |
