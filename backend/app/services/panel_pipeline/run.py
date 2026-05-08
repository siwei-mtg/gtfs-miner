"""Pipeline entry point — Plan 2 Task 7.1.

Production orchestrator: load feed → compute() → persist 38 indicators +
quality + diff/reorg → trigger derived aggregator. Spec §6.4 data flow.

Idempotent on indicator/quality/diff/flag rows (existing rows are updated
rather than duplicated). Diff failures on a malformed prior feed are
swallowed — diff is a lineage hook; the indicator persistence is the
primary value of the pipeline.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from app.db.models import PanelFeed, PanelNetwork


def run_panel_pipeline(feed_id: str) -> None:
    """Process one PAN GTFS feed end-to-end (Spec §6.4).

    Steps:
        1. Load feed + network rows from DB.
        2. Resolve a local Path for the GTFS ZIP (R2 cache, else download).
        3. Build AomMeta and call the pure compute() (38 indicators).
        4. Persist 38 PanelIndicator rows + 1 aggregated PanelQuality row.
        5. Diff against the prior feed → persist PanelFeedDiff + PanelReorgFlag.
        6. Trigger aggregator (z-score/percentile, YoY, post_reorg_delta).

    Idempotent: re-running on the same feed_id updates existing rows in place.

    Raises:
        ValueError: feed_id not in panel_feeds.
        FileNotFoundError: GTFS ZIP cannot be resolved (no r2_path, no live URL).
    """
    # Local imports keep top-level light and let test patches target them.
    from app.db.database import SessionLocal
    from app.db.models import (
        PanelFeed,
        PanelIndicator,
        PanelNetwork,
        PanelQuality,
    )
    from app.services.gtfs_core.gtfs_reader import read_gtfs_zip
    from app.services.panel_pipeline.aggregator import (
        recompute_post_reorg_delta,
        recompute_yoy,
        recompute_zscore_pct,
    )
    from app.services.panel_pipeline.compute import AomMeta, compute
    from app.services.panel_pipeline.diff.feed_diff import feed_diff
    from app.services.panel_pipeline.diff.persist import persist_diff_and_flag
    from app.services.panel_pipeline.diff.reorg_detect import detect_reorg
    from app.services.panel_pipeline.quality import compute_overall

    methodology_commit = _resolve_methodology_commit()
    network_id_for_aggregator: str | None = None

    with SessionLocal() as session:
        feed = session.query(PanelFeed).filter_by(feed_id=feed_id).one_or_none()
        if feed is None:
            raise ValueError(f"feed_id={feed_id} not found in panel_feeds")
        network = session.query(PanelNetwork).filter_by(network_id=feed.network_id).one()
        network_id_for_aggregator = network.network_id

        # 1. Resolve local ZIP. R2 cache preferred; fall back to gtfs_url download.
        zip_path = _ensure_local(feed)

        # 2. Build AomMeta — polygon may be a stub for AOMs without geometry data.
        meta = AomMeta(
            slug=network.slug,
            population=int(network.population or 0),
            area_km2=float(network.area_km2 or 0.0),
            polygon_l93=_load_aom_polygon_or_stub(network),
            methodology_commit=methodology_commit,
        )

        # 3. Pure compute. On failure, mark feed as failed and re-raise.
        try:
            bundle = compute(zip_path, meta)
        except Exception as e:
            feed.process_status = "failed"
            feed.error_message = f"{type(e).__name__}: {e}"[:1000]
            session.commit()
            raise

        # 4. Persist indicators (idempotent upsert).
        for ind_id, v in bundle.values.items():
            existing = (
                session.query(PanelIndicator)
                .filter_by(feed_id=feed.feed_id, indicator_id=ind_id)
                .one_or_none()
            )
            if existing is None:
                session.add(
                    PanelIndicator(
                        feed_id=feed.feed_id,
                        indicator_id=ind_id,
                        value=v["value"],
                        unit=v["unit"],
                        error_margin_pct=v["error_margin_pct"],
                        methodology_commit=v["methodology_commit"],
                    )
                )
            else:
                existing.value = v["value"]
                existing.unit = v["unit"]
                existing.error_margin_pct = v["error_margin_pct"]
                existing.methodology_commit = v["methodology_commit"]

        # 5. Compute and persist overall quality (idempotent upsert).
        dq_values = {
            k: bundle.values[k]["value"]
            for k in bundle.values
            if k.startswith("dq_")
        }
        score, grade = compute_overall(dq_values)
        existing_q = (
            session.query(PanelQuality)
            .filter_by(feed_id=feed.feed_id)
            .one_or_none()
        )
        if existing_q is None:
            session.add(
                PanelQuality(
                    feed_id=feed.feed_id,
                    overall_score=score,
                    overall_grade=grade,
                )
            )
        else:
            existing_q.overall_score = score
            existing_q.overall_grade = grade

        # 6. Diff against prior feed (if any). Failures here must NOT abort
        #    the indicator persistence — diff is a lineage hook, not a hard
        #    requirement. A malformed prior feed (duplicate stop_id, etc.)
        #    should still allow the current feed's indicators to land.
        prior = (
            session.query(PanelFeed)
            .filter(
                PanelFeed.network_id == network.network_id,
                PanelFeed.feed_start_date < feed.feed_start_date,
            )
            .order_by(PanelFeed.feed_start_date.desc())
            .first()
        )
        if prior is not None:
            try:
                prior_zip = _ensure_local(prior)
                feed_a = read_gtfs_zip(prior_zip)
                feed_b = read_gtfs_zip(zip_path)
                d = feed_diff(feed_a, feed_b)
                v = detect_reorg(d)
                persist_diff_and_flag(
                    session,
                    network.network_id,
                    prior.feed_id,
                    feed.feed_id,
                    d,
                    v,
                )
            except Exception:
                # Don't fail the whole run if diff blows up on a malformed
                # prior feed; indicators have already landed above.
                pass

        feed.process_status = "ok"
        feed.error_message = None
        session.commit()

    # 7. Trigger aggregator in a fresh session.
    with SessionLocal() as session:
        recompute_zscore_pct(session, network_id_for_aggregator, methodology_commit)
        recompute_yoy(session, network_id_for_aggregator, methodology_commit)
        recompute_post_reorg_delta(
            session, network_id_for_aggregator, methodology_commit
        )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _resolve_methodology_commit() -> str:
    """Read methodology repo HEAD short-commit. Falls back to env var or 'unknown'.

    Resolution order:
        1. ``METHODOLOGY_COMMIT`` env var (CI/explicit override).
        2. ``compare-transit-methodology`` sibling repo's git HEAD.
        3. Literal ``"unknown"`` so persistence still has a non-NULL value.
    """
    env_commit = os.environ.get("METHODOLOGY_COMMIT")
    if env_commit:
        return env_commit
    repo_path = Path(__file__).resolve().parents[4] / "compare-transit-methodology"
    if repo_path.exists():
        try:
            out = subprocess.check_output(
                ["git", "-C", str(repo_path), "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            return out.decode().strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return "unknown"


def _ensure_local(feed: "PanelFeed") -> Path:
    """Resolve a local Path for the given feed's GTFS ZIP.

    Order of resolution:
        1. ``feed.r2_path`` if set and the file exists.
        2. Live download from ``feed.gtfs_url`` to a tempfile (cached by feed_id).

    Raises:
        FileNotFoundError: download failed AND no r2_path is usable.
    """
    if feed.r2_path:
        candidate = Path(feed.r2_path)
        if candidate.exists():
            return candidate
    # Fallback: download to a stable tempfile per feed_id (cheap re-runs).
    tmp = Path(tempfile.gettempdir()) / f"panel_feed_{feed.feed_id}.zip"
    if not tmp.exists():
        try:
            urllib.request.urlretrieve(feed.gtfs_url, tmp)
        except Exception as e:
            raise FileNotFoundError(
                f"Cannot resolve GTFS ZIP for feed_id={feed.feed_id}: "
                f"r2_path={feed.r2_path!r} unusable, download from "
                f"{feed.gtfs_url!r} failed: {e}"
            ) from e
    return tmp


def _load_aom_polygon_or_stub(network: "PanelNetwork") -> "BaseGeometry":
    """Load AOM polygon for the network, or return a stub bbox if unavailable.

    In Phase 0/1 there's no AOM polygon storage in panel_networks — defer to
    V1 (Cerema GeoJSON ingestion). For now, return a Lambert-93 unit-bbox
    placeholder; coverage indicators degrade to None gracefully.
    """
    from shapely.geometry import box

    return box(0, 0, 1, 1)


# ──────────────────────────────────────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────────────────────────────────────

_FIXTURES_ROOT = (
    Path(__file__).resolve().parents[3] / "tests" / "Resources" / "raw"
)
_FIXTURE_PATHS: dict[str, Path] = {
    "sem":   _FIXTURES_ROOT / "SEM-GTFS(2).zip",
    "solea": _FIXTURES_ROOT / "SOLEA.GTFS_current.zip",
    "ginko": _FIXTURES_ROOT / "gtfs-20240704-090655.zip",
}

_AOM_FIXTURES_YAML = (
    Path(__file__).resolve().parents[3]
    / "tests" / "panel_pipeline" / "data" / "aom_meta_fixtures.yaml"
)


def _load_aom_fixture(fixture: str) -> dict:
    """Load AOM population/area for one of the 3 packaged GTFS fixtures.

    Falls back to a stub (population=1, area_km2=1.0) if the YAML file is
    absent (e.g. production-only deploys without test data). Density tests
    run only when the YAML is present, so this fallback keeps the helper
    safe for non-test contexts.
    """
    if not _AOM_FIXTURES_YAML.exists():
        return {"population": 1, "area_km2": 1.0, "display_name": fixture}
    return yaml.safe_load(_AOM_FIXTURES_YAML.read_text(encoding="utf-8"))[fixture]


def run_panel_pipeline_for_fixture(fixture: str) -> dict[str, float]:
    """Test helper: run pure compute() on a packaged test fixture with real AomMeta.

    Used by `test_kcc_equivalence_contract.py` to verify the panel KCC matches
    the full pipeline KCC within 0.1% (spec §11), and by Task 2.4 density
    tests which need real population/area to verify the ratio arithmetic.

    AomMeta values come from `tests/panel_pipeline/data/aom_meta_fixtures.yaml`.
    The polygon is still stubbed (1×1 box at origin in L93) — coverage
    indicators populate as None for these fixtures, which is fine for the
    contract / productivity / density tests that consume this helper.

    Args:
        fixture: One of "sem", "solea", "ginko" (matches d4_kcc/baselines.json keys).

    Returns:
        Flat dict {indicator_id: value} for indicators that computed
        (None values dropped).
    """
    from shapely.geometry import box

    from app.services.panel_pipeline.compute import AomMeta, compute

    aom = _load_aom_fixture(fixture)
    meta = AomMeta(
        slug=fixture,
        population=int(aom["population"]),
        area_km2=float(aom["area_km2"]),
        polygon_l93=box(0, 0, 1, 1),  # stub — coverage indicators degrade None
        methodology_commit="test",
    )
    bundle = compute(_FIXTURE_PATHS[fixture], meta)
    return {
        k: v["value"]
        for k, v in bundle.values.items()
        if v["value"] is not None
    }
