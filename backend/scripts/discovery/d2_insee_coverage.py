"""
D2 — INSEE/IGN Coverage Prototype on Grenoble (SEM fixture)

Validates spec §12 D2 + spec §5.1 D coverage formulas end-to-end.

Inputs the script expects (place manually before running):
  1. backend/storage/discovery/d2/Filosofi2017_carreaux_200m.gpkg
       Source: https://www.insee.fr/fr/statistiques/6215138 (~205 MB zip,
               wraps a 215 MB .7z; extract twice).
  2. backend/storage/discovery/d2/aom_2024.geojson
       Source: https://www.data.gouv.fr/fr/datasets/les-autorites-organisatrices-de-la-mobilite-aom/
               (Cerema; ~10 MB GeoJSON of all 470+ AOMs)
  3. backend/storage/discovery/d2/aom_target.json   (optional override)
       Two keys: ``field`` and ``value``. Defaults to
       {field: "Nom_AOM", value: "Métropole Grenoble Alpes"} for the SEM fixture.

Outputs:
  - backend/storage/discovery/d2/sem_coverage.json   (machine-readable summary)
  - docs/superpowers/specs/2026-05-03-insee-integration-discovery.md
    (replaces the deferral note with a completion note)
"""
from __future__ import annotations

import json
import logging
import sys
import time
import tracemalloc
from pathlib import Path

# Add backend root to sys.path for `app.*` imports when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.gtfs_core.gtfs_reader import read_gtfs_zip
from app.services.panel_pipeline.geo import (
    compute_coverage,
    gtfs_stops_to_geodataframe,
    load_aom_polygon,
    load_carroyage_200m,
)

logger = logging.getLogger("d2_insee")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = BACKEND_ROOT / "storage" / "discovery" / "d2"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CARROYAGE_PATH = CACHE_DIR / "Filosofi2017_carreaux_200m.gpkg"
AOM_GEOJSON_PATH = CACHE_DIR / "aom_2024.geojson"
TARGET_OVERRIDE_PATH = CACHE_DIR / "aom_target.json"

GTFS_FIXTURE = BACKEND_ROOT / "tests" / "Resources" / "raw" / "SEM-GTFS(2).zip"
SUMMARY_PATH = CACHE_DIR / "sem_coverage.json"

REPORT_PATH = (
    BACKEND_ROOT.parent
    / "docs" / "superpowers" / "specs"
    / "2026-05-03-insee-integration-discovery.md"
)

# Default AOM target for the SEM fixture (Grenoble).
DEFAULT_TARGET_FIELD = "Nom_AOM"
DEFAULT_TARGET_VALUE = "Métropole Grenoble Alpes"


def load_target() -> tuple[str, str]:
    if TARGET_OVERRIDE_PATH.exists():
        cfg = json.loads(TARGET_OVERRIDE_PATH.read_text(encoding="utf-8"))
        return cfg["field"], cfg["value"]
    return DEFAULT_TARGET_FIELD, DEFAULT_TARGET_VALUE


def load_stops_lambert93():
    raw = read_gtfs_zip(GTFS_FIXTURE)
    stops_df = raw["stops"]
    return gtfs_stops_to_geodataframe(stops_df)


def carroyage_bbox_from_aom(aom_gdf, *, padding_m: float = 1000.0):
    """Compute a (xmin, ymin, xmax, ymax) bbox in Lambert-93 around the AOM."""
    minx, miny, maxx, maxy = aom_gdf.total_bounds
    return (minx - padding_m, miny - padding_m, maxx + padding_m, maxy + padding_m)


def main() -> int:
    field, value = load_target()
    logger.info("Target AOM: %s = %r", field, value)

    if not GTFS_FIXTURE.exists():
        logger.error("GTFS fixture missing: %s", GTFS_FIXTURE)
        return 1

    tracemalloc.start()
    t0 = time.perf_counter()

    logger.info("Loading AOM polygon ...")
    aom_gdf = load_aom_polygon(AOM_GEOJSON_PATH, field=field, value=value)
    logger.info("AOM bounds (Lambert-93): %s", aom_gdf.total_bounds)

    logger.info("Loading carroyage 200m (bbox-filtered to AOM) ...")
    bbox = carroyage_bbox_from_aom(aom_gdf, padding_m=1000.0)
    carroyage = load_carroyage_200m(CARROYAGE_PATH, bbox_l93=bbox)
    logger.info("Loaded %d carreaux in AOM bbox", len(carroyage))

    logger.info("Loading GTFS stops from %s ...", GTFS_FIXTURE.name)
    stops = load_stops_lambert93()
    logger.info("Loaded %d physical stops", len(stops))

    logger.info("Computing coverage indicators (buffer=300m) ...")
    indicators = compute_coverage(stops, carroyage, aom_gdf, buffer_m=300)

    elapsed = time.perf_counter() - t0
    _, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_mem / 1024 / 1024

    summary = {
        "fixture": GTFS_FIXTURE.name,
        "aom_field": field,
        "aom_value": value,
        "indicators": dict(indicators),
        "performance": {
            "elapsed_seconds": round(elapsed, 2),
            "peak_memory_mb": round(peak_mb, 1),
        },
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Wrote %s", SUMMARY_PATH)

    _write_report(summary)
    logger.info("Wrote %s", REPORT_PATH)
    logger.info(
        "cov_pop_300m=%.2f%%  cov_surface_300m=%.2f%%  median_walk=%.0fm  pop_weighted_walk=%.0fm",
        indicators["cov_pop_300m"],
        indicators["cov_surface_300m"],
        indicators["cov_median_walk"],
        indicators["cov_pop_weighted_walk"],
    )
    return 0


def _write_report(summary: dict) -> None:
    ind = summary["indicators"]
    perf = summary["performance"]
    lines = [
        "# D2 — INSEE/IGN Coverage Prototype (Plan 1 Task 2)",
        "",
        "**Status**: ✅ Completed",
        "",
        "**Date**: 2026-05-05",
        f"**Fixture**: `{summary['fixture']}` (Métropole Grenoble Alpes — SEM)",
        f"**AOM target**: `{summary['aom_field']}` = `{summary['aom_value']}`",
        "**CRS**: EPSG:2154 (Lambert-93) for all metric ops",
        "",
        "## Inputs",
        "",
        f"- INSEE Filosofi 2017 carreaux 200m (Métropole + DOM): `Filosofi2017_carreaux_200m.gpkg` (~215 MB unzipped)",
        f"- AOM polygons (Cerema 2024): `aom_2024.geojson` (~10 MB)",
        f"- GTFS stops: `{summary['fixture']}` → physical stops only (`location_type == 0`)",
        "",
        "## Computed indicators (spec §5.1 D)",
        "",
        "| Indicator | Value | Unit |",
        "|-----------|-------|------|",
        f"| `cov_pop_300m` | **{ind['cov_pop_300m']:.2f}** | % |",
        f"| `cov_surface_300m` | **{ind['cov_surface_300m']:.2f}** | % |",
        f"| `cov_median_walk` | **{ind['cov_median_walk']:.0f}** | m |",
        f"| `cov_pop_weighted_walk` | **{ind['cov_pop_weighted_walk']:.0f}** | m |",
        "",
        f"AOM denominators: total population = **{ind['total_pop']:.0f}** residents · "
        f"total surface = **{ind['total_surface_km2']:.1f} km²** · "
        f"{ind['cell_count']} carreaux clipped · {ind['stop_count']} stops",
        "",
        "## Performance (single-network run)",
        "",
        f"- Wall-clock: **{perf['elapsed_seconds']} s**",
        f"- Peak Python memory (tracemalloc): **{perf['peak_memory_mb']} MB**",
        "",
        "Bbox-filtered carroyage read keeps the working set bounded at AOM scale "
        "(metropole-wide read peaks ~3-4 GB). All metric ops in Lambert-93.",
        "",
        "## Wrapper API (for Plan 2)",
        "",
        "Reusable functions: `backend/app/services/panel_pipeline/geo.py`",
        "",
        "```python",
        "from app.services.panel_pipeline.geo import (",
        "    load_carroyage_200m, load_aom_polygon, gtfs_stops_to_geodataframe,",
        "    compute_coverage,",
        ")",
        "",
        "carroyage = load_carroyage_200m(gpkg_path, bbox_l93=aom_bbox)",
        "aom = load_aom_polygon(geojson_path, field='Nom_AOM', value='...')",
        "stops = gtfs_stops_to_geodataframe(stops_df)",
        "indicators = compute_coverage(stops, carroyage, aom, buffer_m=300)",
        "# → dict with cov_pop_300m, cov_surface_300m, cov_median_walk, cov_pop_weighted_walk",
        "```",
        "",
        "## Plan 2 integration",
        "",
        "- `panel_pipeline.indicators.coverage` calls `compute_coverage` with",
        "  per-feed AOM polygon + bbox-filtered carroyage. Cache the carroyage",
        "  read once per pipeline run (it's the most expensive step).",
        "- Pipeline must accept the AOM identifier as feed metadata (one new",
        "  column on `panel_network` — TODO Plan 2 Task 4).",
        "- Indicators NOT covered here (`cov_pop_freq_300m`, `cov_equity_gini`)",
        "  are V1+, layered on top of this same buffer/clip primitive.",
        "",
        "_Generated by `backend/scripts/discovery/d2_insee_coverage.py`._",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
