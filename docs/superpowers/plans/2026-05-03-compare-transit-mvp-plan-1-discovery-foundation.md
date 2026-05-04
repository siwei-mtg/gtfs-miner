# compare-transit.fr MVP — Plan 1: Discovery & Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate critical assumptions in spec via 4 discovery tasks (D1–D4), then lay backend foundation (Postgres schema + `panel_pipeline` skeleton) so Plan 2 (Indicator Pipeline) can begin without unknowns.

**Architecture:** Discovery scripts produce markdown reports under `docs/superpowers/specs/`. Foundation code lives in `backend/app/services/panel_pipeline/`, reuses existing `gtfs_core` utilities, persists data via new SQLAlchemy models + Alembic migration. No frontend work in this plan.

**Tech Stack:** Python 3.11+ · httpx 0.27 · pandas 2.2 · geopandas 1.0 · shapely 2.0 · SQLAlchemy 2.0 · Alembic 1.13 · pytest 8.3 · MobilityData GTFS Validator (Java, `gtfs-validator-cli`)

**Spec reference:** `docs/superpowers/specs/2026-05-03-compare-transit-mvp-design.md` (§12 Discovery Tasks · §6.3 Storage Schema · §6.2 Pipeline Design · §11 Engineering Contract)

**Estimated time:** 2 weeks (W1: Discovery 4 tasks · W2: Foundation 6 tasks). Single dev.

---

## File Structure

### Discovery scripts (W1, kept in repo for reproducibility)

```
backend/scripts/discovery/
├── __init__.py
├── d1_pan_history.py        — PAN catalog + history harvester
├── d2_insee_coverage.py     — INSEE/IGN spatial coverage prototype on Strasbourg
├── d3_validator_wrapper.py  — MobilityData validator integration prototype
└── d4_kcc_equivalence.py    — KCC contract test on 3 fixtures (SEM/SOLEA/ginko)
```

### Discovery output documents

```
docs/superpowers/specs/
├── 2026-05-03-pan-history-discovery.md
├── 2026-05-03-insee-integration-discovery.md
├── 2026-05-03-validator-integration-discovery.md
└── 2026-05-03-kcc-equivalence-discovery.md
```

### Foundation code (W2, persistent)

```
backend/app/db/models.py    — APPEND: PanelNetwork, PanelFeed, PanelIndicator,
                              PanelIndicatorDerived, PanelQuality, PanelPeerGroup

backend/alembic/versions/<auto>_add_panel_tables.py

backend/app/services/panel_pipeline/
├── __init__.py
├── run.py                   — entry point: run_panel_pipeline(feed_id) -> None
├── pan_client.py            — PAN API client + R2 caching
├── peer_groups.py           — static tier loader (T1/T2/T3/T4/T5/R/I)
├── aggregator.py            — derived layer (z-score / percentile / YoY) — STUB in Plan 1
├── quality.py               — MobilityData validator wrapper — STUB in Plan 1
├── geo.py                   — INSEE/IGN loaders + buffer ops — STUB in Plan 1
├── types.py                 — TypedDict for indicator output schema
└── indicators/
    ├── __init__.py
    ├── productivity.py      — STUB (Plan 2)
    ├── density.py           — STUB
    ├── structure.py         — STUB
    ├── coverage.py          — STUB
    ├── frequency.py         — STUB
    ├── accessibility.py     — STUB
    └── environment.py       — STUB

backend/tests/panel_pipeline/
├── __init__.py
├── test_models.py           — DB schema integrity (round-trip insert)
├── test_skeleton.py         — module imports + types
├── test_peer_groups.py      — tier classification rules
└── test_pan_client.py       — PAN API with httpx mock
```

### Static config files

```
backend/app/services/panel_pipeline/data/
└── peer_groups.yaml         — T1–T5 + R + I tier rules, exemplar networks
```

---

# Discovery Tasks (Week 1)

## Task 1: D1 — PAN History Harvester (复用现有探索脚本)

**Goal:** Adapt Wei's pre-existing PAN exploration scripts (already executed in `C:/Users/wei.si/Projets/GTFS/`) into the project, run them on demand, capture statistical results in spec dir. **Do not rewrite from scratch** — these scripts use proven endpoints + dedup-by-`feed_start_date` + remotezip Range-fetch strategies that have been validated end-to-end.

**Background — what already exists in `C:/Users/wei.si/Projets/GTFS/`:**

- `verify_transport_gouv_api.py` — Step A (dataset enumeration via `/api/datasets`), Step B (history depth scan via `resources_history_csv`), Step C (cellar download benchmark)
- `fetch_dataset_dedup.py` — Per-network dedup-by-`feed_start_date` flow using `remotezip` HTTP Range to fetch only `feed_info.txt` (~1 KB per probe instead of full ZIP download)
- `fetch_sncf_dedup.py` — SNCF-specific runner; validates approach on the 7,434-row dataset
- Output CSVs already exist: `datasets_gtfs_inventory.csv` (463 rows), `history_depth_by_dataset.csv`, `cellar_sampling_results.csv`, `gtfs_size_ratios.csv`

**Validated PAN endpoints** (from these scripts):
- `GET /api/datasets` — full list, no pagination, ~463 GTFS datasets when filtered to `type == "public-transit"` + `format == "GTFS"`
- `GET /api/datasets/{datagouv_id}` — first `history` entry's `payload.dataset_id` = short integer ID (needed for next call)
- `GET /datasets/{short_id}/resources_history_csv` — full history CSV with `payload.zip_metadata` containing per-file sha256

**Files:**
- Create: `backend/scripts/discovery/__init__.py` (empty)
- Copy + adapt: `backend/scripts/discovery/d1a_pan_inventory.py` (from `verify_transport_gouv_api.py`)
- Copy + adapt: `backend/scripts/discovery/d1b_dedup_per_network.py` (from `fetch_dataset_dedup.py`)
- Create: `backend/scripts/discovery/d1_report.py` (new — aggregates outputs into spec markdown)
- Create: `docs/superpowers/specs/2026-05-03-pan-history-discovery.md`
- Cache: `backend/storage/discovery/d1_pan/` (gitignored — outputs reusable across plans)

- [ ] **Step 1: Add discovery storage to .gitignore + add deps**

Append to `backend/.gitignore`:

```gitignore
storage/discovery/
```

Append to `backend/requirements.txt`:

```text
remotezip==0.12.3
requests==2.32.3
```

Run: `..\venv\Scripts\pip install remotezip==0.12.3 requests==2.32.3`

- [ ] **Step 2: Copy + adapt the inventory + dedup scripts**

Copy `C:\Users\wei.si\Projets\GTFS\verify_transport_gouv_api.py` → `backend/scripts/discovery/d1a_pan_inventory.py`. Apply only these edits:

- Header docstring: replace with reference to compare-transit.fr context
- Change `OUT = Path(__file__).parent` → `OUT = Path(__file__).resolve().parents[2] / "storage" / "discovery" / "d1_pan"`
- Add `OUT.mkdir(parents=True, exist_ok=True)` near top of script

Copy `C:\Users\wei.si\Projets\GTFS\fetch_dataset_dedup.py` → `backend/scripts/discovery/d1b_dedup_per_network.py`. Apply only these edits:

- Default output dir: `out_dir = Path(__file__).resolve().parents[2] / "storage" / "discovery" / "d1_pan" / f"{args.name}_archive"` (instead of CWD-relative)

Both scripts can otherwise be copied verbatim — the API endpoints and dedup logic are validated.

- [ ] **Step 3: Run inventory (Step A — fast)**

```powershell
cd backend
..\venv\Scripts\python scripts\discovery\d1a_pan_inventory.py a
```

Expected: `storage/discovery/d1_pan/datasets_gtfs_inventory.csv` with **463 rows**. Time: ~30s.

- [ ] **Step 4: Run history depth scan (Step B — concurrent, ~10–15 min)**

```powershell
..\venv\Scripts\python scripts\discovery\d1a_pan_inventory.py b
```

Expected: `history_depth_by_dataset.csv`. Logs progress every 25 datasets. Expect ~455 datasets with non-empty history. Total raw rows ~122,558.

- [ ] **Step 5: Skip Step C (cellar sampling) — already done historically**

Wei has `cellar_sampling_results.csv` from previous run. Optionally re-run if PAN performance characteristics may have changed; otherwise copy the existing CSV from `C:\Users\wei.si\Projets\GTFS\cellar_sampling_results.csv` into `backend/storage/discovery/d1_pan/`.

- [ ] **Step 6: Test dedup on 1 sample network — Strasbourg CTS**

Pick a small-medium network from inventory to validate the dedup flow end-to-end:

```powershell
$row = Import-Csv "backend\storage\discovery\d1_pan\history_depth_by_dataset.csv" |
       Where-Object { $_.slug -like "*strasbourg*" -or $_.slug -like "*cts*" } |
       Select-Object -First 1
$short_id = $row.short_id
Write-Host "Using short_id=$short_id slug=$($row.slug)"

..\venv\Scripts\python scripts\discovery\d1b_dedup_per_network.py `
    --short-id $short_id `
    --name strasbourg `
    --steps fetch resolve dedup
```

Expected: produces `backend/storage/discovery/d1_pan/strasbourg_archive/manifest_dedup.parquet`. The dedup ratio (raw_rows / dedup_rows) is the **key metric** to validate spec §6.1's "~7×" assumption.

**Skip the `download` step** — that's Plan 2 backfill territory. We only want to confirm dedup works.

- [ ] **Step 7: Generate the discovery report**

Create `backend/scripts/discovery/d1_report.py`:

```python
"""Aggregate D1 inventory + history outputs into the spec markdown report."""
from __future__ import annotations
from datetime import datetime, UTC
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / "storage" / "discovery" / "d1_pan"
REPORT = (
    Path(__file__).resolve().parents[3]
    / "docs" / "superpowers" / "specs"
    / "2026-05-03-pan-history-discovery.md"
)


def main() -> None:
    inv = pd.read_csv(CACHE_DIR / "datasets_gtfs_inventory.csv")
    depth = pd.read_csv(CACHE_DIR / "history_depth_by_dataset.csv")

    nonempty = depth[depth["n_rows"] > 0].copy()
    nonempty["oldest_dt"] = pd.to_datetime(nonempty["oldest"], utc=True, errors="coerce")
    earliest_year = nonempty["oldest_dt"].dt.year.value_counts().sort_index()

    # Optional: read Strasbourg dedup test if present
    strasbourg_dedup_ratio: float | None = None
    strasbourg_manifest = CACHE_DIR / "strasbourg_archive" / "manifest_dedup.parquet"
    strasbourg_raw = CACHE_DIR / "strasbourg_archive" / "manifest_raw.parquet"
    if strasbourg_manifest.exists() and strasbourg_raw.exists():
        raw = pd.read_parquet(strasbourg_raw)
        dedup = pd.read_parquet(strasbourg_manifest)
        strasbourg_dedup_ratio = len(raw) / max(len(dedup), 1)

    lines = [
        "# D1 — PAN History Discovery Report",
        f"**Date**: {datetime.now(UTC):%Y-%m-%d}",
        "**Source**: transport.data.gouv.fr `/api/datasets` + `resources_history_csv`",
        "",
        "## Summary",
        f"- Total GTFS datasets (PAN type=public-transit): **{len(inv)}**",
        f"- Datasets with non-empty history: **{len(nonempty)}**",
        f"- Total raw history rows: **{int(depth['n_rows'].sum())}**",
        f"- Estimated dedup'd feed count (raw / 7): **~{int(depth['n_rows'].sum() / 7)}**",
        "",
        "## Raw history rows distribution (datasets with non-empty history)",
        f"- p10 / p50 / p90 / p99 / max:  "
        f"{int(nonempty['n_rows'].quantile(0.1))} / "
        f"{int(nonempty['n_rows'].quantile(0.5))} / "
        f"{int(nonempty['n_rows'].quantile(0.9))} / "
        f"{int(nonempty['n_rows'].quantile(0.99))} / "
        f"{int(nonempty['n_rows'].max())}",
        "",
        "## Earliest publication year",
        "| Year | Datasets |",
        "|------|----------|",
    ]
    for y, n in earliest_year.items():
        lines.append(f"| {int(y)} | {int(n)} |")

    lines += ["", "## Strasbourg CTS dedup test"]
    if strasbourg_dedup_ratio is not None:
        lines.append(
            f"- Dedup ratio: **{strasbourg_dedup_ratio:.2f}×** "
            "(raw_rows / unique_feed_start_date)"
        )
    else:
        lines.append("- Not run yet. Execute Step 6 to populate.")

    lines += [
        "",
        "## Recommendations",
        "- **Cron cadence**: weekly (mid-week, low traffic) — covers most networks' update cycle",
        "- **Backfill batch**: process in tier order (T5 first as smallest, T1 last) "
        "for fastest user-visible coverage",
        "- **AOMs without history**: process current resource only; "
        "mark `history_depth_months=0` in `panel_networks`",
        "",
        "_Generated by `backend/scripts/discovery/d1_report.py` from cached CSVs._",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
```

Run: `..\venv\Scripts\python scripts\discovery\d1_report.py`
Expected: report file created at `docs/superpowers/specs/2026-05-03-pan-history-discovery.md`.

- [ ] **Step 8: Manually verify dedup ratio assumption + commit**

Open the generated report. Verify:
- Total datasets ≈ 463
- p50 raw rows ≈ 47
- max raw rows ≈ 7,434 (SNCF)
- Strasbourg dedup ratio ≈ 5–10× (validates spec §6.1's ~7× assumption)

If Strasbourg ratio is significantly different (e.g., 2× or 30×), update spec §6.1 backfill estimate accordingly.

```powershell
git add backend/scripts/discovery/__init__.py
git add backend/scripts/discovery/d1a_pan_inventory.py
git add backend/scripts/discovery/d1b_dedup_per_network.py
git add backend/scripts/discovery/d1_report.py
git add backend/.gitignore
git add backend/requirements.txt
git add docs/superpowers/specs/2026-05-03-pan-history-discovery.md
git commit -m "discovery: D1 — PAN history harvest + dedup-by-feed_start_date

Adopts proven exploration scripts from prior PAN work. Validates spec
§12 D1 + §6.1 dedup strategy on Strasbourg CTS test."
```


---

## Task 2: D2 — INSEE/IGN Coverage Prototype on Strasbourg

**Goal:** Validate the spatial coverage indicator computation pipeline (`cov_pop_300m`, `cov_surface_300m`, `cov_median_walk`, `cov_pop_weighted_walk`) on a single network end-to-end, before committing to the full implementation in Plan 2.

**Files:**
- Create: `backend/scripts/discovery/d2_insee_coverage.py`
- Create: `docs/superpowers/specs/2026-05-03-insee-integration-discovery.md`
- Cache: `backend/storage/discovery/d2_insee/` (carroyage + ADMIN-EXPRESS extracts)

- [ ] **Step 1: Document the data download URLs**

In `d2_insee_coverage.py`, write the script header with verified data URLs (these are stable INSEE/IGN endpoints):

```python
"""
D2 — INSEE/IGN Coverage Prototype on Strasbourg

Validates spec §12 D2: end-to-end spatial coverage on one network.

Data sources:
  - INSEE 200m carroyage (latest):
    https://www.insee.fr/fr/statistiques/fichier/4176290/Filosofi2017_carreaux_200m_gpkg.zip
  - IGN ADMIN-EXPRESS COG:
    https://geoservices.ign.fr/adminexpress
  - data.gouv.fr aom_2024 (AOM polygons):
    https://www.data.gouv.fr/fr/datasets/r/...  (verify slug)

GTFS fixture: backend/tests/Resources/raw/<strasbourg>.zip
  (NB: project tests/Resources/raw/ does not include Strasbourg by default;
  download Strasbourg GTFS from PAN if missing — or substitute SEM as proxy.)
"""
```

- [ ] **Step 2: Implement data download with caching**

```python
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZipFile

CACHE_DIR = Path(__file__).resolve().parents[2] / "storage" / "discovery" / "d2_insee"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("d2_insee")
logging.basicConfig(level=logging.INFO)


def cached_download(url: str, name: str) -> Path:
    target = CACHE_DIR / name
    if target.exists():
        logger.info("Cache hit: %s", target)
        return target
    logger.info("Downloading %s -> %s", url, target)
    urlretrieve(url, target)
    return target


def cached_unzip(zip_path: Path, into: Path) -> Path:
    if into.exists():
        return into
    into.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path) as zf:
        zf.extractall(into)
    return into
```

- [ ] **Step 3: Implement coverage computation**

Continue `d2_insee_coverage.py`:

```python
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.ops import unary_union

GTFS_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "tests" / "Resources" / "raw" / "SEM-GTFS(2).zip"  # substitute Strasbourg if available
)


def load_gtfs_stops(zip_path: Path) -> gpd.GeoDataFrame:
    """Read stops.txt from GTFS zip, return GeoDataFrame in EPSG:4326."""
    with ZipFile(zip_path) as zf, zf.open("stops.txt") as f:
        df = pd.read_csv(f)
    df = df[df["location_type"].fillna(0).astype(int) == 0]  # physical stops only
    df = df.dropna(subset=["stop_lat", "stop_lon"])
    geom = [Point(lon, lat) for lon, lat in zip(df["stop_lon"], df["stop_lat"])]
    return gpd.GeoDataFrame(df, geometry=geom, crs="EPSG:4326")


def compute_coverage(
    stops: gpd.GeoDataFrame,
    carroyage: gpd.GeoDataFrame,
    aom_polygon: gpd.GeoDataFrame,
    buffer_m: int = 300,
) -> dict:
    """Compute the four coverage indicators in spec §5.1 D."""
    # Project to Lambert-93 (EPSG:2154) for accurate metric buffering in France
    stops_l93 = stops.to_crs("EPSG:2154")
    carroyage_l93 = carroyage.to_crs("EPSG:2154")
    aom_l93 = aom_polygon.to_crs("EPSG:2154")

    # Clip carroyage to AOM
    carroyage_in_aom = gpd.overlay(carroyage_l93, aom_l93, how="intersection")
    total_pop = float(carroyage_in_aom["Ind"].sum())  # Ind = total residents
    total_surface_m2 = float(aom_l93.geometry.area.sum())

    # Build 300m buffer union
    buffer_union = unary_union(stops_l93.geometry.buffer(buffer_m))
    buffer_gdf = gpd.GeoDataFrame(geometry=[buffer_union], crs="EPSG:2154")

    # cov_pop_300m
    cells_in_buffer = gpd.overlay(carroyage_in_aom, buffer_gdf, how="intersection")
    pop_in_buffer = float(cells_in_buffer["Ind"].sum())
    cov_pop_300m = 100.0 * pop_in_buffer / total_pop if total_pop else 0

    # cov_surface_300m
    surface_in_buffer = float(
        gpd.overlay(buffer_gdf, aom_l93, how="intersection").geometry.area.sum()
    )
    cov_surface_300m = 100.0 * surface_in_buffer / total_surface_m2 if total_surface_m2 else 0

    # cov_median_walk: median of (cell_centroid -> nearest stop) distances
    centroids = carroyage_in_aom.geometry.centroid
    centroids_gdf = gpd.GeoDataFrame(
        carroyage_in_aom[["Ind"]].copy(),
        geometry=list(centroids),
        crs="EPSG:2154",
    )
    nearest = gpd.sjoin_nearest(centroids_gdf, stops_l93, distance_col="walk_m")
    cov_median_walk = float(nearest["walk_m"].median())

    # cov_pop_weighted_walk: pop-weighted mean of walk distance
    cov_pop_weighted_walk = float(
        (nearest["walk_m"] * nearest["Ind"]).sum() / nearest["Ind"].sum()
    ) if nearest["Ind"].sum() else 0

    return {
        "cov_pop_300m": cov_pop_300m,
        "cov_surface_300m": cov_surface_300m,
        "cov_median_walk": cov_median_walk,
        "cov_pop_weighted_walk": cov_pop_weighted_walk,
        "total_pop": total_pop,
        "stop_count": len(stops_l93),
    }
```

- [ ] **Step 4: Wire up main + report writer**

```python
def main() -> None:
    # NB: real URLs to be confirmed during execution; if download fails,
    # download manually to CACHE_DIR and re-run.
    carroyage_zip = cached_download(
        "https://www.insee.fr/fr/statistiques/fichier/4176290/Filosofi2017_carreaux_200m_gpkg.zip",
        "carroyage_200m.zip",
    )
    cached_unzip(carroyage_zip, CACHE_DIR / "carroyage_200m")
    carroyage_path = next((CACHE_DIR / "carroyage_200m").glob("**/*.gpkg"))
    carroyage = gpd.read_file(carroyage_path)

    # AOM polygon — need to substitute the real source URL during execution
    aom_polygon_path = CACHE_DIR / "aom_2024.geojson"
    if not aom_polygon_path.exists():
        raise FileNotFoundError(
            f"Place AOM polygon (e.g., for SEM=Métropole Grenoble) at {aom_polygon_path}\n"
            "Source: https://www.data.gouv.fr/fr/datasets/aom-2024/"
        )
    aom_polygon = gpd.read_file(aom_polygon_path)

    stops = load_gtfs_stops(GTFS_FIXTURE)
    indicators = compute_coverage(stops, carroyage, aom_polygon)

    report = REPORT_PATH = (
        Path(__file__).resolve().parents[3]
        / "docs" / "superpowers" / "specs"
        / "2026-05-03-insee-integration-discovery.md"
    )
    lines = [
        "# D2 — INSEE/IGN Coverage Prototype",
        "",
        f"**Fixture**: `{GTFS_FIXTURE.name}`",
        f"**Stops loaded**: {indicators['stop_count']}",
        f"**Total AOM population**: {indicators['total_pop']:.0f}",
        "",
        "## Computed indicators",
        "",
        f"- `cov_pop_300m`: **{indicators['cov_pop_300m']:.2f}%**",
        f"- `cov_surface_300m`: **{indicators['cov_surface_300m']:.2f}%**",
        f"- `cov_median_walk`: **{indicators['cov_median_walk']:.0f} m**",
        f"- `cov_pop_weighted_walk`: **{indicators['cov_pop_weighted_walk']:.0f} m**",
        "",
        "## Sanity checks",
        "",
        "- [ ] Compare `cov_pop_300m` against published AOM coverage report (if available)",
        "- [ ] Memory peak observed: ___ MB (set `psutil.Process().memory_info().rss`)",
        "- [ ] Total processing time: ___ s",
        "- [ ] Decisions: confirm Lambert-93 projection sufficient; document edge cases",
        "",
        "_Generated by `backend/scripts/discovery/d2_insee_coverage.py`._",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote %s", report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run on SEM (Grenoble), measure performance**

First, download AOM 2024 polygon manually (this dataset has slug variations on data.gouv.fr — find current one):
- Visit `https://www.data.gouv.fr/fr/datasets/?q=aom+2024`
- Download GeoJSON of AOM polygons; save as `backend/storage/discovery/d2_insee/aom_2024.geojson`
- Filter to "Métropole Grenoble Alpes" (or whichever AOM corresponds to SEM fixture)

Run: `venv/Scripts/python backend/scripts/discovery/d2_insee_coverage.py`
Expected: report file created with 4 indicator values; processing under 2 minutes for SEM.

If memory exceeds 4 GB or processing exceeds 5 minutes, document workaround (chunked overlay, simplified geometry) in report.

- [ ] **Step 6: Manually fill sanity checks in report + commit**

Edit the auto-generated report, fill in:
- Memory peak (use `psutil.Process().memory_info().rss / 1024 / 1024`)
- Processing time
- Comparison with any external reference (e.g., AOM annual report covers ~85% pop)
- Engineering decisions (chunking? caching? CRS choices)

```powershell
git add backend/scripts/discovery/d2_insee_coverage.py
git add docs/superpowers/specs/2026-05-03-insee-integration-discovery.md
git commit -m "discovery: D2 — INSEE/IGN coverage prototype on SEM

Validates spec §12 D2 + §5.1 D coverage formulas. Confirms Lambert-93
projection and sjoin_nearest approach for cov_pop_weighted_walk."
```

---

## Task 3: D3 — MobilityData GTFS Validator Wrapper

**Goal:** Decide and implement the integration approach for the MobilityData GTFS validator (Java CLI). Output `panel_quality.parse_validator_output()` design.

**Files:**
- Create: `backend/scripts/discovery/d3_validator_wrapper.py`
- Create: `docs/superpowers/specs/2026-05-03-validator-integration-discovery.md`
- Cache: `backend/storage/discovery/d3_validator/` (validator JAR + sample outputs)

- [x] **Step 1: Verify Java availability + download validator** — OpenJDK 17 (Adoptium Temurin 17.0.19) installed at `C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot`. Downloaded validator v7.1.0 CLI JAR (38 MB) — superseded the v6.0.0 reference URL.

Run: `java -version` (expect Java 11+ available; the validator needs JDK 11)
If missing, document install path. Document Java version in the report.

Download validator (release URL):

```powershell
$cache = "backend\storage\discovery\d3_validator"
New-Item -ItemType Directory -Path $cache -Force | Out-Null
$url = "https://github.com/MobilityData/gtfs-validator/releases/download/v6.0.0/gtfs-validator-6.0.0-cli.jar"
$jar = "$cache\gtfs-validator-cli.jar"
if (-not (Test-Path $jar)) {
    Invoke-WebRequest -Uri $url -OutFile $jar
}
```

(verify latest release version on https://github.com/MobilityData/gtfs-validator/releases)

- [x] **Step 2: Run validator manually on SEM fixture to inspect JSON shape** — Done. Output structure: `{summary: {...}, notices: [{code, severity, totalNotices, sampleNotices: [...]}]}`. SEM produced 0 errors / 166 warnings / 1 info in 3.5s.

```powershell
$cache = "backend\storage\discovery\d3_validator"
$out = "$cache\sample_sem_output"
New-Item -ItemType Directory -Path $out -Force | Out-Null
& java -jar "$cache\gtfs-validator-cli.jar" `
    --input "backend\tests\Resources\raw\SEM-GTFS(2).zip" `
    --output_base $out `
    --country_code FR
```

Expected: directory with `report.json`, `system_errors_report.json`, `validation_stderr.log`.

- [x] **Step 3: Implement Python wrapper that runs validator + parses JSON** — Implemented at `backend/scripts/discovery/d3_validator_wrapper.py` with `validate_feed()` reusable function + `ValidationReport`/`NoticeCode` dataclasses. Resolution order for Java/JAR documented (env vars → JAVA_HOME → Adoptium fallback → PATH).

Create `d3_validator_wrapper.py`:

```python
"""
D3 — MobilityData GTFS Validator Wrapper

Validates spec §12 D3: validator integration approach + output parsing.

Approach: subprocess-based Java invocation (chosen over REST/Python port
because validator's CLI is stable and JSON output is well-defined).
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, TypedDict

CACHE_DIR = Path(__file__).resolve().parents[2] / "storage" / "discovery" / "d3_validator"
JAR_PATH = CACHE_DIR / "gtfs-validator-cli.jar"
REPORT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs" / "superpowers" / "specs"
    / "2026-05-03-validator-integration-discovery.md"
)
GTFS_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "tests" / "Resources" / "raw" / "SEM-GTFS(2).zip"
)

logger = logging.getLogger("d3_validator")
logging.basicConfig(level=logging.INFO)


class ValidatorOutput(TypedDict):
    error_count: int
    warning_count: int
    info_count: int
    notices_by_code: dict[str, int]
    raw_report: dict[str, Any]


def run_validator(gtfs_zip: Path) -> ValidatorOutput:
    """Run MobilityData validator and parse report.json."""
    if not JAR_PATH.exists():
        raise FileNotFoundError(f"Validator JAR not at {JAR_PATH}")
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "out"
        out_dir.mkdir()
        cmd = [
            "java", "-jar", str(JAR_PATH),
            "--input", str(gtfs_zip),
            "--output_base", str(out_dir),
            "--country_code", "FR",
        ]
        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.warning("Validator exit %d: %s", result.returncode, result.stderr)
        report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    return parse_validator_report(report)


def parse_validator_report(report: dict[str, Any]) -> ValidatorOutput:
    """Convert raw validator JSON into our normalized shape."""
    notices = report.get("notices", [])
    code_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    for n in notices:
        code_counts[n.get("code", "UNKNOWN")] += n.get("totalNotices", 0) or 1
        severity_counts[n.get("severity", "INFO")] += n.get("totalNotices", 0) or 1
    return ValidatorOutput(
        error_count=severity_counts.get("ERROR", 0),
        warning_count=severity_counts.get("WARNING", 0),
        info_count=severity_counts.get("INFO", 0),
        notices_by_code=dict(code_counts),
        raw_report=report,
    )


def write_report(out: ValidatorOutput) -> None:
    lines = [
        "# D3 — GTFS Validator Integration Discovery",
        "",
        f"**Fixture**: `{GTFS_FIXTURE.name}`",
        "**Approach**: subprocess-invoked Java CLI (chosen over REST/Python port)",
        "",
        "## Validator output on SEM",
        "",
        f"- ERROR notices: **{out['error_count']}**",
        f"- WARNING notices: **{out['warning_count']}**",
        f"- INFO notices: **{out['info_count']}**",
        "",
        "## Top notice codes",
        "",
        "| Code | Count |",
        "|------|-------|",
    ]
    top = sorted(out["notices_by_code"].items(), key=lambda kv: -kv[1])[:15]
    for code, n in top:
        lines.append(f"| `{code}` | {n} |")
    lines += [
        "",
        "## Decisions for spec §6.1 quality.py implementation",
        "",
        "- [ ] Confirmed validator version: ___",
        "- [ ] Java installation path: ___",
        "- [ ] Subprocess timeout for IDFM-scale feed: ___ s",
        "- [ ] Notice codes weighted into `dq_field_completeness`: list ___",
        "- [ ] French-specific custom rules to add (per spec §3 `dq_*`): ___",
        "",
        "_Generated by `backend/scripts/discovery/d3_validator_wrapper.py`._",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    out = run_validator(GTFS_FIXTURE)
    write_report(out)
    logger.info("Wrote %s", REPORT_PATH)


if __name__ == "__main__":
    main()
```

- [x] **Step 4: Run wrapper end-to-end** — Ran on all 3 fixtures: SEM (0E/166W/1I, 3.04s), SOLEA (78E/14118W/0I, 2.26s), ginko (33E/4242W/0I, 0.45s). Output cached at `backend/storage/discovery/d3_validator/{sem,solea,ginko}_output/`. JSON shape matched v7.1.0 structure (`notices[].code/severity/totalNotices/sampleNotices`).

Run: `venv/Scripts/python backend/scripts/discovery/d3_validator_wrapper.py`
Expected: report file with notice counts; subprocess returns within 2 minutes for SEM.

- [x] **Step 5: Manually fill decisions in report + commit** — Spec doc written at `docs/superpowers/specs/2026-05-03-validator-integration-discovery.md`. Decisions: subprocess-Java approach confirmed; v7.1.0 JSON schema parsed cleanly; per-feed budget 60s (3-fixture max was 3s).

```powershell
git add backend/scripts/discovery/d3_validator_wrapper.py
git add docs/superpowers/specs/2026-05-03-validator-integration-discovery.md
git commit -m "discovery: D3 — MobilityData validator wrapper

Validates spec §12 D3. Confirms subprocess-Java approach; locks output parsing."
```

---

## Task 4: D4 — KCC Equivalence Contract Test on 3 Fixtures

**Goal:** Verify the spec §11 engineering contract: full pipeline (current `worker.py`) and panel pipeline (Plan 1 stub + Plan 2 implementation) produce KCC values within 0.1% on three test fixtures. In Plan 1, only the **infrastructure** for this test is set up; the panel-side computation is a stub returning the full-pipeline answer (so the contract trivially passes), to be replaced in Plan 2.

**Files:**
- Create: `backend/scripts/discovery/d4_kcc_equivalence.py`
- Create: `docs/superpowers/specs/2026-05-03-kcc-equivalence-discovery.md`
- Create: `backend/tests/panel_pipeline/test_kcc_equivalence_contract.py` (skipped placeholder, activated in Plan 2)

- [ ] **Step 1: Implement KCC extraction from current pipeline output**

Create `d4_kcc_equivalence.py`:

```python
"""
D4 — KCC Equivalence Contract Test (Plan 1: infrastructure only)

Validates spec §11 engineering contract. In Plan 1, this script:
  1. Runs the full pipeline (worker.py) on 3 fixtures
  2. Extracts network-level KCC from F_3_KCC_Lignes
  3. Stores baseline values for Plan 2 to compare against
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.gtfs_core.pipeline import run_pipeline_full  # adjust import path

CACHE_DIR = Path(__file__).resolve().parents[2] / "storage" / "discovery" / "d4_kcc"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FIXTURES = {
    "sem":   "backend/tests/Resources/raw/SEM-GTFS(2).zip",
    "solea": "backend/tests/Resources/raw/SOLEA.GTFS_current.zip",
    "ginko": "backend/tests/Resources/raw/gtfs-20240704-090655.zip",
}

REPORT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs" / "superpowers" / "specs"
    / "2026-05-03-kcc-equivalence-discovery.md"
)

logger = logging.getLogger("d4_kcc")
logging.basicConfig(level=logging.INFO)


def extract_full_pipeline_kcc(zip_path: Path) -> float:
    """Run worker pipeline and return Σ F_3_KCC_Lignes.kcc."""
    import pandas as pd
    with TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "out"
        output_dir.mkdir()
        # Adjust this call to match the actual signature of run_pipeline_full
        run_pipeline_full(input_zip=zip_path, output_dir=output_dir)
        kcc_csv = output_dir / "F_3_KCC_Lignes.csv"
        if not kcc_csv.exists():
            raise FileNotFoundError(f"Pipeline did not produce {kcc_csv}")
        df = pd.read_csv(kcc_csv, sep=";", encoding="utf-8-sig")
        # KCC column name from spec §3 — verify exact
        kcc_col = next(c for c in df.columns if "kcc" in c.lower())
        return float(df[kcc_col].sum())


def main() -> None:
    baselines: dict[str, float] = {}
    for name, path in FIXTURES.items():
        zip_path = Path(path)
        if not zip_path.exists():
            logger.warning("Fixture missing: %s", zip_path)
            continue
        logger.info("Running full pipeline on %s ...", name)
        kcc = extract_full_pipeline_kcc(zip_path)
        baselines[name] = kcc
        logger.info("%s KCC = %.2f km", name, kcc)

    cache_path = CACHE_DIR / "baselines.json"
    cache_path.write_text(json.dumps(baselines, indent=2), encoding="utf-8")

    lines = [
        "# D4 — KCC Equivalence Contract Test (Plan 1 baseline)",
        "",
        f"**Fixtures**: {', '.join(FIXTURES.keys())}",
        f"**Cached baselines**: `{cache_path.relative_to(Path.cwd())}`",
        "",
        "## Baseline KCC (full pipeline)",
        "",
        "| Fixture | KCC (km) |",
        "|---------|----------|",
    ]
    for name, kcc in baselines.items():
        lines.append(f"| {name} | {kcc:,.2f} |")
    lines += [
        "",
        "## Plan 2 contract",
        "",
        "When the panel_pipeline implements `prod_kcc_year`, the value computed",
        "on each fixture **must** be within 0.1% of the corresponding baseline above.",
        "",
        "Test: `backend/tests/panel_pipeline/test_kcc_equivalence_contract.py` (currently skipped).",
        "",
        "_Generated by `backend/scripts/discovery/d4_kcc_equivalence.py`._",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote %s", REPORT_PATH)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the import path for full pipeline**

Run: `venv/Scripts/python -c "from app.services.gtfs_core.pipeline import run_pipeline_full; print('OK')"`
If import fails, fix the import in the script to match the actual public API.
If `pipeline.py` exposes a different function name (e.g., `run_full`, `process_gtfs`), update the import + call accordingly.

- [ ] **Step 3: Run baseline extraction**

Run from `backend/` directory:
```powershell
cd backend
..\venv\Scripts\python scripts\discovery\d4_kcc_equivalence.py
```
Expected: 3 baseline KCC values logged + JSON file at `storage/discovery/d4_kcc/baselines.json` + report file.
Time: ~30s for SEM, ~1min for SOLEA, ~30s for ginko.

- [ ] **Step 4: Create the placeholder contract test**

Create `backend/tests/panel_pipeline/__init__.py` (empty) and `backend/tests/panel_pipeline/test_kcc_equivalence_contract.py`:

```python
"""
KCC equivalence contract test — spec §11.
Activates in Plan 2 once panel_pipeline.run computes prod_kcc_year.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

BASELINES_PATH = (
    Path(__file__).resolve().parents[2]
    / "storage" / "discovery" / "d4_kcc" / "baselines.json"
)


@pytest.mark.skip(reason="Activated in Plan 2 once prod_kcc_year is implemented")
@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_kcc_equivalence(fixture: str) -> None:
    """Spec §11 contract: panel KCC and full pipeline KCC must be within 0.1%."""
    baselines = json.loads(BASELINES_PATH.read_text(encoding="utf-8"))
    expected = baselines[fixture]
    # Plan 2 will replace this stub:
    from app.services.panel_pipeline.run import run_panel_pipeline_for_fixture
    panel = run_panel_pipeline_for_fixture(fixture)
    actual = panel["prod_kcc_year"]
    assert abs(actual - expected) / expected < 0.001, (
        f"{fixture}: panel={actual:.2f} vs full={expected:.2f}"
    )
```

- [ ] **Step 5: Verify test discovery (skip status)**

Run: `cd backend && ..\venv\Scripts\python -m pytest tests/panel_pipeline/test_kcc_equivalence_contract.py -v`
Expected: 3 tests, all reported as SKIPPED.

- [ ] **Step 6: Commit**

```powershell
git add backend/scripts/discovery/d4_kcc_equivalence.py
git add backend/tests/panel_pipeline/__init__.py
git add backend/tests/panel_pipeline/test_kcc_equivalence_contract.py
git add docs/superpowers/specs/2026-05-03-kcc-equivalence-discovery.md
git add backend/storage/discovery/d4_kcc/baselines.json  # consider committing baselines OR adding to .gitignore — see step 7
git commit -m "discovery: D4 — KCC baseline + contract test stub

Validates spec §12 D4 + §11. Captures 3 fixture baselines for Plan 2
to verify panel_pipeline KCC equivalence within 0.1%."
```

- [ ] **Step 7: Decide baselines.json git policy**

Open `.gitignore`. Choose:
- **Commit baselines** (recommended): they are reproducibility artifacts, small, deterministic given fixture + pipeline version. Comment in `.gitignore`: `# d4_kcc/baselines.json — committed, do not ignore`.
- **Ignore baselines**: every Plan 2 contributor regenerates. Add `backend/storage/discovery/d4_kcc/baselines.json` to ignore.

Document choice in the D4 report.

---

# Foundation Tasks (Week 2)

## Task 5: panel_pipeline Module Skeleton

**Goal:** Create the directory structure + module-level imports + types so Plan 2 can drop indicator implementations into clearly-named slots without touching infrastructure.

**Files:**
- Create: `backend/app/services/panel_pipeline/__init__.py`
- Create: `backend/app/services/panel_pipeline/types.py`
- Create: `backend/app/services/panel_pipeline/run.py`
- Create: `backend/app/services/panel_pipeline/quality.py` (stub)
- Create: `backend/app/services/panel_pipeline/geo.py` (stub)
- Create: `backend/app/services/panel_pipeline/aggregator.py` (stub)
- Create: `backend/app/services/panel_pipeline/indicators/__init__.py`
- Create: `backend/app/services/panel_pipeline/indicators/{productivity,density,structure,coverage,frequency,accessibility,environment}.py` (stubs)
- Create: `backend/tests/panel_pipeline/test_skeleton.py`

- [ ] **Step 1: Write the failing skeleton test**

Create `backend/tests/panel_pipeline/test_skeleton.py`:

```python
"""Smoke test: all panel_pipeline modules importable + types stable."""
from __future__ import annotations


def test_imports() -> None:
    from app.services.panel_pipeline import run, pan_client, peer_groups, aggregator, quality, geo, types
    from app.services.panel_pipeline.indicators import (
        productivity, density, structure, coverage,
        frequency, accessibility, environment,
    )


def test_indicator_set_constant_present() -> None:
    """Spec §5.1 lists 38 indicators; INDICATOR_IDS must enumerate them."""
    from app.services.panel_pipeline.types import INDICATOR_IDS
    assert isinstance(INDICATOR_IDS, frozenset)
    assert len(INDICATOR_IDS) == 38, f"Expected 38 indicators, got {len(INDICATOR_IDS)}"


def test_indicator_result_typed_dict_shape() -> None:
    from app.services.panel_pipeline.types import IndicatorValue
    val: IndicatorValue = {"value": 1.0, "unit": "km"}
    assert val["unit"] == "km"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ..\venv\Scripts\python -m pytest tests/panel_pipeline/test_skeleton.py -v`
Expected: FAIL on import error (module does not exist).

- [ ] **Step 3: Create types.py**

Create `backend/app/services/panel_pipeline/types.py`:

```python
"""Type definitions for panel_pipeline outputs (spec §5.1)."""
from __future__ import annotations

from typing import TypedDict


class IndicatorValue(TypedDict):
    value: float
    unit: str


# Spec §5.1: 38 core indicators across 8 categories
INDICATOR_IDS: frozenset[str] = frozenset({
    # A. Productivity (8)
    "prod_kcc_year", "prod_courses_day_avg", "prod_peak_hour_courses",
    "prod_service_amplitude", "prod_lines_count", "prod_stops_count",
    "prod_network_length_km", "prod_peak_vehicles_needed",
    # B. Density (4)
    "dens_stops_km2", "dens_lines_100k_pop", "dens_kcc_capita", "dens_kcc_km2",
    # C. Structure (7)
    "struct_modal_mix_bus", "struct_modal_mix_tram", "struct_modal_mix_metro",
    "struct_modal_mix_train", "struct_peak_amplification",
    "struct_multi_route_stops_pct", "struct_route_directness",
    # D. Coverage (6)
    "cov_pop_300m", "cov_pop_freq_300m", "cov_surface_300m",
    "cov_median_walk", "cov_pop_weighted_walk", "cov_equity_gini",
    # E. Frequency & Speed (4)
    "freq_peak_headway_median", "freq_high_freq_lines_pct",
    "freq_daily_service_hours", "freq_commercial_speed_kmh",
    # F. Accessibility (2)
    "acc_wheelchair_stops_pct", "acc_wheelchair_trips_pct",
    # G. Data Quality (6)
    "dq_validator_errors", "dq_validator_warnings", "dq_field_completeness",
    "dq_coord_quality", "dq_route_type_completeness", "dq_freshness",
    # H. Environment (1)
    "env_co2_year_estimated",
})

assert len(INDICATOR_IDS) == 38, f"INDICATOR_IDS count mismatch: {len(INDICATOR_IDS)}"
```

- [ ] **Step 4: Create stub modules**

Create `backend/app/services/panel_pipeline/__init__.py`:

```python
"""
compare-transit.fr panel pipeline.

See spec: docs/superpowers/specs/2026-05-03-compare-transit-mvp-design.md §6.2
"""
```

Create `backend/app/services/panel_pipeline/run.py`:

```python
"""Pipeline entry point. Plan 2 implements full body."""
from __future__ import annotations

from typing import Any


def run_panel_pipeline(feed_id: str) -> None:
    """
    Process one PAN GTFS feed end-to-end.

    Plan 1 stub. Plan 2 implements:
      1. Load feed from R2 (or download from PAN if absent)
      2. Reuse gtfs_core: rawgtfs_from_zip, gtfs_normalize, ligne_generate,
         service_date_generate, service_jour_type_generate
      3. Compute 38 indicators via indicators.* modules
      4. Run quality.compute_quality()
      5. Persist to panel_indicators + panel_quality
      6. Trigger aggregator.recompute_derived(network_id)
    """
    raise NotImplementedError("Implemented in Plan 2 Task 1")
```

Create stubs for `quality.py`, `geo.py`, `aggregator.py` with one-line docstring + `raise NotImplementedError("Implemented in Plan 2 Task <N>")`.

Create `backend/app/services/panel_pipeline/indicators/__init__.py` (empty).
Create stubs for each `indicators/<category>.py` with module docstring referencing spec §5.1 category.

Example `indicators/productivity.py`:

```python
"""Spec §5.1 A. Productivity indicators (8 items). Plan 2 Task 2."""
from __future__ import annotations

# Stubs — implemented in Plan 2.
```

- [ ] **Step 5: Run skeleton test to verify it passes**

Run: `cd backend && ..\venv\Scripts\python -m pytest tests/panel_pipeline/test_skeleton.py -v`
Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/panel_pipeline/
git add backend/tests/panel_pipeline/test_skeleton.py
git commit -m "feat(panel): scaffold panel_pipeline module + 38-indicator types

Implements spec §6.2 module structure. Stub modules raise NotImplementedError
to be filled in Plan 2."
```

---

## Task 6: SQLAlchemy Models for 6 panel_* Tables

**Goal:** Define ORM models for all panel persistence (spec §6.3). Test via in-memory SQLite round-trip.

**Files:**
- Modify: `backend/app/db/models.py` (append at end)
- Create: `backend/tests/panel_pipeline/test_models.py`

- [ ] **Step 1: Write failing model test**

Create `backend/tests/panel_pipeline/test_models.py`:

```python
"""Spec §6.3 storage schema — round-trip insert tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import (
    PanelNetwork, PanelFeed, PanelIndicator,
    PanelIndicatorDerived, PanelQuality, PanelPeerGroup,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_panel_network_roundtrip(session) -> None:
    n = PanelNetwork(
        slug="lyon",
        pan_dataset_id="abc-123",
        display_name="Métropole de Lyon — TCL",
        aom_id="69123",
        tier="T1",
        population=1_420_000,
        area_km2=538.0,
    )
    session.add(n)
    session.commit()
    fetched = session.query(PanelNetwork).filter_by(slug="lyon").one()
    assert fetched.tier == "T1"
    assert fetched.population == 1_420_000


def test_panel_feed_indicator_chain(session) -> None:
    # peer group required by FK conceptually; for SQLite we just need rows
    network = PanelNetwork(slug="t", pan_dataset_id="t", display_name="t",
                           aom_id="t", tier="T5", population=10000, area_km2=1.0)
    session.add(network)
    session.commit()

    feed = PanelFeed(
        network_id=network.network_id,
        pan_resource_id="r1",
        pan_resource_history_id="rh1",
        published_at=datetime.now(timezone.utc),
        feed_start_date=datetime(2025, 1, 1),
        feed_info_sha256="abcd" * 16,
        feed_info_source="feed_info",
        gtfs_url="https://example/feed.zip",
        filesize=1024 * 500,
        process_status="done",
    )
    session.add(feed)
    session.commit()

    ind = PanelIndicator(
        feed_id=feed.feed_id,
        indicator_id="prod_kcc_year",
        value=12345.6,
        unit="km",
    )
    session.add(ind)
    session.commit()

    fetched = session.query(PanelIndicator).filter_by(indicator_id="prod_kcc_year").one()
    assert fetched.value == pytest.approx(12345.6)


def test_panel_quality_jsonb(session) -> None:
    network = PanelNetwork(slug="q", pan_dataset_id="q", display_name="q",
                           aom_id="q", tier="T5", population=10000, area_km2=1.0)
    session.add(network); session.commit()
    feed = PanelFeed(
        network_id=network.network_id,
        pan_resource_id="qr1",
        pan_resource_history_id="qrh1",
        published_at=datetime.now(timezone.utc),
        feed_start_date=datetime(2025, 6, 1),
        feed_info_sha256="ef00" * 16,
        feed_info_source="feed_info",
        gtfs_url="https://example/q.zip",
        process_status="done",
    )
    session.add(feed); session.commit()

    q = PanelQuality(
        feed_id=feed.feed_id,
        validator_errors={"system_errors": [], "notices": []},
        overall_grade="A-",
        overall_score=87.0,
    )
    session.add(q); session.commit()
    fetched = session.query(PanelQuality).one()
    assert fetched.overall_grade == "A-"
    assert "notices" in fetched.validator_errors
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ..\venv\Scripts\python -m pytest tests/panel_pipeline/test_models.py -v`
Expected: FAIL on import error (models do not exist).

- [ ] **Step 3: Add models to backend/app/db/models.py**

Append at end of `backend/app/db/models.py`:

```python
# ────────────────────────────────────────────────────────
# compare-transit.fr panel models — spec §6.3
# ────────────────────────────────────────────────────────


class PanelNetwork(Base):
    __tablename__ = "panel_networks"

    network_id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slug                 = Column(String, unique=True, index=True, nullable=False)
    pan_dataset_id       = Column(String, unique=True, index=True, nullable=False)
    display_name         = Column(String, nullable=False)
    aom_id               = Column(String, index=True)
    tier                 = Column(String, index=True)        # T1/T2/T3/T4/T5/R/I
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
    pan_resource_id         = Column(String, index=True, nullable=False)             # Most recent representative resource (after dedup)
    pan_resource_history_id = Column(String, index=True)                              # resource_history_id from PAN CSV
    published_at            = Column(DateTime, nullable=False, index=True)            # PAN inserted_at
    feed_start_date         = Column(DateTime, nullable=False, index=True)            # dedup key — from feed_info.txt
    feed_end_date           = Column(DateTime)
    feed_info_sha256        = Column(String, index=True)                              # sig_sha — feed_info.txt hash
    feed_info_source        = Column(String)                                          # 'feed_info' | 'calendar' | 'calendar_dates'
    gtfs_url                = Column(String, nullable=False)                          # permanent_url
    r2_path                 = Column(String)
    checksum_sha256         = Column(String)                                          # ZIP-level sha256 (different from feed_info_sha256)
    filesize                = Column(Integer)                                         # compressed bytes
    process_status          = Column(String, default="pending", index=True)
    process_duration_s      = Column(Float)
    error_message           = Column(String)
    created_at              = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ux_panel_feeds_network_fsd", "network_id", "feed_start_date", unique=True),
    )


class PanelIndicator(Base):
    __tablename__ = "panel_indicators"

    feed_id      = Column(String, ForeignKey("panel_feeds.feed_id"), primary_key=True)
    indicator_id = Column(String, primary_key=True, index=True)
    value        = Column(Float)
    unit         = Column(String, nullable=False)
    computed_at  = Column(DateTime, default=datetime.utcnow)


class PanelIndicatorDerived(Base):
    __tablename__ = "panel_indicators_derived"

    feed_id          = Column(String, ForeignKey("panel_feeds.feed_id"), primary_key=True)
    indicator_id     = Column(String, primary_key=True, index=True)
    zscore           = Column(Float)
    percentile       = Column(Float)
    yoy_delta_pct    = Column(Float)
    peer_group_size  = Column(Integer)
    computed_at      = Column(DateTime, default=datetime.utcnow)


class PanelQuality(Base):
    __tablename__ = "panel_quality"

    feed_id          = Column(String, ForeignKey("panel_feeds.feed_id"), primary_key=True)
    validator_errors = Column(JSON)
    overall_grade    = Column(String)
    overall_score    = Column(Float)
    computed_at      = Column(DateTime, default=datetime.utcnow)


class PanelPeerGroup(Base):
    __tablename__ = "panel_peer_groups"

    group_id     = Column(String, primary_key=True)  # T1/T2/T3/T4/T5/R/I
    display_name = Column(String, nullable=False)
    definition   = Column(JSON)
    member_count = Column(Integer, default=0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ..\venv\Scripts\python -m pytest tests/panel_pipeline/test_models.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/db/models.py
git add backend/tests/panel_pipeline/test_models.py
git commit -m "feat(panel): add 6 SQLAlchemy models for panel_* tables

Spec §6.3 storage schema. SQLite round-trip tests verify shape."
```

---

## Task 7: Alembic Migration for panel_* Tables

**Goal:** Generate Alembic migration so Postgres schema matches the new ORM models.

**Files:**
- Create: `backend/alembic/versions/<auto>_add_panel_tables.py`

- [ ] **Step 1: Generate migration**

Run from `backend/` directory:
```powershell
cd backend
..\venv\Scripts\python -m alembic revision --autogenerate -m "add_panel_tables"
```
Expected: a new file in `backend/alembic/versions/<hash>_add_panel_tables.py` with `op.create_table("panel_networks", ...)` for each of the 6 tables.

- [ ] **Step 2: Inspect and clean the migration**

Open the new migration file. Verify:
- All 6 `op.create_table(...)` calls present (panel_networks, panel_feeds, panel_indicators, panel_indicators_derived, panel_quality, panel_peer_groups)
- Foreign keys correct (panel_feeds.network_id → panel_networks.network_id; etc.)
- Index columns marked with `index=True` produce `op.create_index(...)` lines
- `down_revision` points to the latest existing revision (`0860c465c5b6` per recent commits)

If the autogenerate produces noise (like recreating existing tables), manually trim those.

- [ ] **Step 3: Apply migration to dev DB**

```powershell
cd backend
..\venv\Scripts\python -m alembic upgrade head
```
Expected: log lines `INFO  [alembic.runtime.migration] Running upgrade <prev> -> <new>, add_panel_tables`. No errors.

- [ ] **Step 4: Verify schema in DB**

```powershell
..\venv\Scripts\python -c "
from app.db.database import engine
from sqlalchemy import inspect
i = inspect(engine)
for t in ['panel_networks','panel_feeds','panel_indicators','panel_indicators_derived','panel_quality','panel_peer_groups']:
    print(t, ':', i.has_table(t))
"
```
Expected: all 6 tables print `True`.

- [ ] **Step 5: Test rollback (sanity)**

```powershell
..\venv\Scripts\python -m alembic downgrade -1
..\venv\Scripts\python -m alembic upgrade head
```
Expected: down then up clean. All 6 tables present after re-upgrade.

- [ ] **Step 6: Commit**

```powershell
git add backend/alembic/versions/*_add_panel_tables.py
git commit -m "feat(panel): alembic migration for 6 panel_* tables"
```

---

## Task 8: PAN Client Module (`pan_client.py`)

**Goal:** A reusable `panel_pipeline.pan_client` that handles PAN API enumeration, dataset detail fetching, **resources_history_csv parsing**, and feed downloading. Tested with httpx mocks (no live calls in unit tests).

**Scope note:** The full **dedup-by-feed_start_date workflow** lives in `backend/scripts/discovery/d1b_dedup_per_network.py` (Task 1) for now and is exercised at backfill time. In Plan 2 it will be promoted to `panel_pipeline/history_resolver.py`. This Task 8 focuses on the runtime API client for monthly cron + on-demand fetching.

**Files:**
- Create: `backend/app/services/panel_pipeline/pan_client.py`
- Create: `backend/tests/panel_pipeline/test_pan_client.py`

- [ ] **Step 1: Write failing PAN client tests**

Create `backend/tests/panel_pipeline/test_pan_client.py`:

```python
"""Spec §6.1 PAN integration — covered by httpx mock to avoid live PAN calls."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.panel_pipeline.pan_client import (
    PANClient, PANDataset, PANResource,
)


@pytest.fixture()
def fake_dataset_response() -> dict:
    return {
        "id": "abc-123",
        "slug": "lyon-tcl",
        "title": "Métropole de Lyon — TCL",
        "type": "public-transit",
        "resources": [
            {
                "id": "r1",
                "format": "GTFS",
                "url": "https://example/r1.zip",
                "modified": "2024-01-01T00:00:00Z",
            }
        ],
        "history": [
            {
                "id": "r0",
                "url": "https://example/r0.zip",
                "inserted_at": "2023-06-01T00:00:00Z",
            }
        ],
    }


def test_fetch_dataset_parses_resources(fake_dataset_response):
    client = PANClient()
    with patch.object(client, "_get") as mock_get:
        mock_get.return_value = fake_dataset_response
        ds: PANDataset = client.fetch_dataset("lyon-tcl")
    assert ds.slug == "lyon-tcl"
    assert len(ds.all_resources) == 2
    assert any(r.is_history for r in ds.all_resources)


def test_resource_dataclass_normalizes_dates(fake_dataset_response):
    client = PANClient()
    with patch.object(client, "_get") as mock_get:
        mock_get.return_value = fake_dataset_response
        ds = client.fetch_dataset("lyon-tcl")
    current = next(r for r in ds.all_resources if not r.is_history)
    assert current.published_at.year == 2024


def test_resolve_short_id():
    """Spec §6.1: history[0].payload.dataset_id holds the integer short ID."""
    client = PANClient()
    fake = {
        "id": "abc-123",
        "history": [{"payload": {"dataset_id": "999"}}],
    }
    with patch.object(client, "_get", return_value=fake):
        assert client.resolve_short_id("abc-123") == 999

    with patch.object(client, "_get", return_value={"id": "abc-123", "history": []}):
        assert client.resolve_short_id("abc-123") is None


def test_fetch_history_csv_parses_payload():
    """Spec §6.1 dedup workflow: resources_history_csv parsing."""
    import json
    csv_text = (
        "resource_history_id,resource_id,permanent_url,inserted_at,payload\n"
        '"rh1","r1","https://example/feed1.zip","2024-01-01T00:00:00Z","'
        + json.dumps({
            "permanent_url": "https://example/feed1.zip",
            "total_compressed_size": 102400,
            "zip_metadata": [
                {"file_name": "feed_info.txt", "sha256": "deadbeef" * 8},
                {"file_name": "routes.txt", "sha256": "00ff" * 16},
            ],
        }).replace('"', '""')
        + '"\n'
    )

    class FakeResp:
        text = csv_text
        def raise_for_status(self): return None

    client = PANClient()
    with patch.object(client._client, "get", return_value=FakeResp()):
        rows = client.fetch_history_csv(short_id=999)
    assert len(rows) == 1
    assert rows[0]["resource_history_id"] == "rh1"
    assert rows[0]["payload"]["zip_metadata"][0]["file_name"] == "feed_info.txt"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ..\venv\Scripts\python -m pytest tests/panel_pipeline/test_pan_client.py -v`
Expected: FAIL on import error.

- [ ] **Step 3: Implement pan_client.py**

Create `backend/app/services/panel_pipeline/pan_client.py`:

```python
"""
PAN (transport.data.gouv.fr) API client + R2 caching layer.

Spec §6.1 / §6.4. Endpoint paths confirmed in D1 discovery.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

PAN_BASE = "https://transport.data.gouv.fr/api"
DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class PANResource:
    """A single GTFS resource (current or historical) from PAN."""
    pan_resource_id: str
    url: str
    published_at: datetime
    is_history: bool


@dataclass(frozen=True)
class PANDataset:
    """A PAN dataset (one network) with all current + historical resources."""
    pan_dataset_id: str
    slug: str
    title: str
    current_resources: list[PANResource] = field(default_factory=list)
    history_resources: list[PANResource] = field(default_factory=list)

    @property
    def all_resources(self) -> list[PANResource]:
        return [*self.current_resources, *self.history_resources]


def _parse_dt(s: str | None) -> datetime:
    if not s:
        return datetime.fromtimestamp(0)
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class PANClient:
    """Thin wrapper around the PAN public API."""

    def __init__(self, base_url: str = PAN_BASE, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def _get(self, path: str, **params: Any) -> dict:
        r = self._client.get(f"{self._base}{path}", params=params)
        r.raise_for_status()
        return r.json()

    def fetch_dataset(self, dataset_id: str) -> PANDataset:
        """Get one dataset by ID or slug, normalize resources + history."""
        data = self._get(f"/datasets/{dataset_id}")
        gtfs_only = lambda r: (r.get("format") or "").lower() in ("gtfs", "application/zip")
        current = [
            PANResource(
                pan_resource_id=r["id"],
                url=r.get("url") or r.get("original_url") or "",
                published_at=_parse_dt(r.get("modified") or r.get("last_update")),
                is_history=False,
            )
            for r in data.get("resources", [])
            if gtfs_only(r)
        ]
        history = [
            PANResource(
                pan_resource_id=h["id"],
                url=h.get("url") or h.get("original_url") or "",
                published_at=_parse_dt(h.get("inserted_at") or h.get("modified")),
                is_history=True,
            )
            for h in data.get("history", []) or data.get("resources_history", [])
        ]
        return PANDataset(
            pan_dataset_id=data["id"],
            slug=data.get("slug", data["id"]),
            title=data.get("title", ""),
            current_resources=current,
            history_resources=history,
        )

    def list_datasets(self, page_size: int = 100) -> list[dict]:
        """List all public-transit datasets (paginated)."""
        out: list[dict] = []
        page = 1
        while True:
            body = self._get("/datasets", page=page, page_size=page_size, type="public-transit")
            items = body.get("data", body) if isinstance(body, dict) else body
            if not items:
                break
            out.extend(items)
            if isinstance(body, dict) and not body.get("links", {}).get("next"):
                break
            page += 1
            if page > 50:
                break
        return out

    def download_resource(self, resource: PANResource, dest: Path) -> Path:
        """Stream-download a GTFS zip to dest. Idempotent if dest exists."""
        if dest.exists():
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._client.stream("GET", resource.url) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_bytes(chunk_size=64 * 1024):
                    f.write(chunk)
        return dest

    def resolve_short_id(self, datagouv_id: str) -> int | None:
        """
        Resolve a datagouv ObjectId-style ID to PAN short integer ID
        (needed for resources_history_csv endpoint).

        Spec §6.1: short_id is in `history[0].payload.dataset_id`.
        """
        data = self._get(f"/datasets/{datagouv_id}")
        history = data.get("history") or []
        if not history:
            return None
        short_id = (history[0].get("payload") or {}).get("dataset_id")
        return int(short_id) if short_id else None

    def fetch_history_csv(self, short_id: int) -> list[dict[str, Any]]:
        """
        Fetch the full resources_history_csv for a network.

        Returns: list of {resource_history_id, resource_id, permanent_url,
                          inserted_at, payload (dict — incl. zip_metadata)}.

        Used for dedup-by-feed_start_date workflow (Plan 2 backfill).
        """
        import csv
        import io
        import json

        url = f"{self._base.replace('/api', '')}/datasets/{short_id}/resources_history_csv"
        r = self._client.get(url, timeout=300.0)
        r.raise_for_status()
        rows: list[dict[str, Any]] = []
        for rec in csv.DictReader(io.StringIO(r.text)):
            try:
                payload = json.loads(rec.get("payload", "{}") or "{}")
            except json.JSONDecodeError:
                payload = {}
            rows.append({
                "resource_history_id": rec.get("resource_history_id"),
                "resource_id": rec.get("resource_id"),
                "permanent_url": rec.get("permanent_url") or payload.get("permanent_url"),
                "inserted_at": rec.get("inserted_at"),
                "payload": payload,
            })
        return rows

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ..\venv\Scripts\python -m pytest tests/panel_pipeline/test_pan_client.py -v`
Expected: 4 tests PASS (fetch_dataset_parses_resources, resource_dataclass_normalizes_dates, resolve_short_id, fetch_history_csv_parses_payload).

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/panel_pipeline/pan_client.py
git add backend/tests/panel_pipeline/test_pan_client.py
git commit -m "feat(panel): PAN API client + history_csv parser

Spec §6.1 / §6.4. httpx-based; mocked tests cover both /api/datasets
and resources_history_csv endpoints (the latter feeds Plan 2 dedup workflow)."
```

---

## Task 9: Peer Group Static Loader

**Goal:** Implement `panel_pipeline.peer_groups` — load tier definitions from YAML, classify networks by population/mode mix into T1/T2/T3/T4/T5/R/I.

**Files:**
- Create: `backend/app/services/panel_pipeline/data/peer_groups.yaml`
- Create: `backend/app/services/panel_pipeline/peer_groups.py`
- Create: `backend/tests/panel_pipeline/test_peer_groups.py`
- Modify: `backend/requirements.txt` (add `pyyaml`)

- [ ] **Step 1: Add pyyaml dep**

Append to `backend/requirements.txt`:
```text
pyyaml==6.0.2
```
Run: `..\venv\Scripts\pip install pyyaml==6.0.2`

- [ ] **Step 2: Create peer_groups.yaml**

Create `backend/app/services/panel_pipeline/data/peer_groups.yaml`:

```yaml
# Spec §5.3 — peer group tier definitions
tiers:
  T1:
    display_name: "Grandes métropoles avec métro"
    rules:
      population_min: 1000000
      requires_mode: metro
    examples: [paris-idfm, lyon-tcl, marseille-rtm, lille-ilevia, toulouse-tisseo]
  T2:
    display_name: "Grandes métropoles sans métro"
    rules:
      population_min: 500000
      population_max: 1000000
    examples: [bordeaux-tbm, nantes-tan, nice, strasbourg-cts, montpellier, rennes-star]
  T3:
    display_name: "Villes moyennes"
    rules:
      population_min: 200000
      population_max: 500000
    examples: [grenoble-tag, tours-filbleu, reims, le-havre, brest]
  T4:
    display_name: "Petites villes"
    rules:
      population_min: 100000
      population_max: 200000
    examples: []
  T5:
    display_name: "Petits AOM"
    rules:
      population_max: 100000
    examples: []
  R:
    display_name: "Réseaux régionaux"
    rules:
      dominant_mode: train
    examples: [ter-grand-est, ter-paca, ter-nouvelle-aquitaine]
  I:
    display_name: "Réseaux interurbains / départementaux"
    rules:
      cross_commune: true
    examples: []
```

- [ ] **Step 3: Write failing peer_groups test**

Create `backend/tests/panel_pipeline/test_peer_groups.py`:

```python
"""Spec §5.3 — tier classification rules."""
from __future__ import annotations

import pytest

from app.services.panel_pipeline.peer_groups import (
    classify_tier, load_peer_groups,
)


def test_load_peer_groups_returns_seven_tiers():
    groups = load_peer_groups()
    assert set(groups.keys()) == {"T1", "T2", "T3", "T4", "T5", "R", "I"}


@pytest.mark.parametrize("pop,has_metro,dominant_mode,cross_commune,expected", [
    (1_500_000, True, "metro", False, "T1"),
    (1_500_000, False, "tram", False, "T2"),  # large but no metro → T2 by pop
    (700_000, False, "bus", False, "T2"),
    (300_000, False, "bus", False, "T3"),
    (150_000, False, "bus", False, "T4"),
    (50_000, False, "bus", False, "T5"),
    (0, False, "train", False, "R"),
    (0, False, "bus", True, "I"),
])
def test_classify_tier(pop, has_metro, dominant_mode, cross_commune, expected):
    assert classify_tier(
        population=pop,
        has_metro=has_metro,
        dominant_mode=dominant_mode,
        cross_commune=cross_commune,
    ) == expected
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && ..\venv\Scripts\python -m pytest tests/panel_pipeline/test_peer_groups.py -v`
Expected: FAIL on import.

- [ ] **Step 5: Implement peer_groups.py**

Create `backend/app/services/panel_pipeline/peer_groups.py`:

```python
"""
Peer group tier loader + classification.

Spec §5.3. MVP uses static tier rules (yaml); V2 introduces PCA clustering.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).resolve().parent / "data"
PEER_GROUPS_YAML = DATA_DIR / "peer_groups.yaml"


@lru_cache(maxsize=1)
def load_peer_groups() -> dict[str, dict[str, Any]]:
    """Read peer_groups.yaml; cached after first call."""
    raw = yaml.safe_load(PEER_GROUPS_YAML.read_text(encoding="utf-8"))
    return raw["tiers"]


def classify_tier(
    *,
    population: int,
    has_metro: bool,
    dominant_mode: str,
    cross_commune: bool,
) -> str:
    """
    Map a network's properties to one of T1/T2/T3/T4/T5/R/I.

    Decision order (first match wins):
      1. R if dominant_mode is "train"
      2. I if cross_commune is True (and not regional rail)
      3. Population-based tiers T1–T5; T1 requires has_metro AND pop >= 1M
    """
    if dominant_mode == "train":
        return "R"
    if cross_commune:
        return "I"
    if population >= 1_000_000 and has_metro:
        return "T1"
    if population >= 500_000:
        return "T2"
    if population >= 200_000:
        return "T3"
    if population >= 100_000:
        return "T4"
    return "T5"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && ..\venv\Scripts\python -m pytest tests/panel_pipeline/test_peer_groups.py -v`
Expected: 9 tests PASS (1 load test + 8 parametrize cases).

- [ ] **Step 7: Commit**

```powershell
git add backend/requirements.txt
git add backend/app/services/panel_pipeline/data/peer_groups.yaml
git add backend/app/services/panel_pipeline/peer_groups.py
git add backend/tests/panel_pipeline/test_peer_groups.py
git commit -m "feat(panel): peer group tier classifier + YAML config

Spec §5.3 MVP simplified version. PCA clustering deferred to V2."
```

---

## Task 10: Final Wire-Up + End-of-Plan Smoke Test

**Goal:** Ensure all foundation pieces hang together: full test suite green, panel modules importable end-to-end, alembic clean. Tag the foundation milestone.

**Files:**
- Create: `backend/tests/panel_pipeline/test_foundation_smoke.py`

- [ ] **Step 1: Write the smoke test**

Create `backend/tests/panel_pipeline/test_foundation_smoke.py`:

```python
"""End-of-Plan-1 smoke test: foundation wired up + ready for Plan 2."""
from __future__ import annotations

import pytest

from app.services.panel_pipeline import (
    pan_client, peer_groups, run, types,
    aggregator, quality, geo,
)
from app.services.panel_pipeline.indicators import (
    productivity, density, structure, coverage,
    frequency, accessibility, environment,
)


def test_all_modules_imported():
    """Every panel module must be importable for Plan 2 to layer on top."""
    for mod in [pan_client, peer_groups, run, types, aggregator, quality, geo,
                productivity, density, structure, coverage,
                frequency, accessibility, environment]:
        assert mod.__name__.startswith("app.services.panel_pipeline")


def test_run_pipeline_raises_until_plan2():
    """run_panel_pipeline is a stub; Plan 2 implements."""
    with pytest.raises(NotImplementedError):
        run.run_panel_pipeline("any-feed-id")


def test_indicator_count_matches_spec():
    """Spec §3.1 mandates 38 core indicators in MVP."""
    assert len(types.INDICATOR_IDS) == 38


def test_peer_group_yaml_loads():
    """Spec §5.3 — 7 tiers."""
    groups = peer_groups.load_peer_groups()
    assert set(groups.keys()) == {"T1", "T2", "T3", "T4", "T5", "R", "I"}
```

- [ ] **Step 2: Run full panel_pipeline test suite**

Run: `cd backend && ..\venv\Scripts\python -m pytest tests/panel_pipeline/ -v`
Expected output (counts may vary by exact parametrize structure):
- `test_kcc_equivalence_contract.py` — 3 SKIPPED
- `test_models.py` — 3 PASSED
- `test_pan_client.py` — 4 PASSED
- `test_peer_groups.py` — 9 PASSED
- `test_skeleton.py` — 3 PASSED
- `test_foundation_smoke.py` — 4 PASSED
- **Total: ~23 PASSED + 3 SKIPPED, 0 FAILED**

- [ ] **Step 3: Run the existing test suite to confirm no regression**

Run: `cd backend && ..\venv\Scripts\python -m pytest -v`
Expected: previous suite still green; only addition is the new panel tests.

- [ ] **Step 4: Tag the foundation milestone**

```powershell
git tag -a plan1-foundation-complete -m "compare-transit.fr Plan 1 complete: discovery + foundation"
```
(do NOT push the tag yet — user controls remote pushes)

- [ ] **Step 5: Commit smoke test**

```powershell
git add backend/tests/panel_pipeline/test_foundation_smoke.py
git commit -m "test(panel): end-of-Plan-1 foundation smoke test"
```

- [ ] **Step 6: Update spec §17 open questions with discovery findings**

Open `docs/superpowers/specs/2026-05-03-compare-transit-mvp-design.md` §17. For each Q1–Q5, append answer based on the 4 discovery reports (cross-reference the discovery doc paths).

Example:
```markdown
| Q1 | PAN 历史数据可追溯到哪一年？每网络平均多少版本？ | D1 → 见 `docs/superpowers/specs/2026-05-03-pan-history-discovery.md`：最早 2018，中位数 X 版本 |
| Q2 | 月度 cron 是否合适？ | D1 → 中位发布间隔 X 天，建议 cron 节奏 ___ |
| Q3 | INSEE 200m carroyage 数据量级与处理性能 | D2 → 内存峰值 ___ MB；SEM 处理 ___ s |
| Q4 | MobilityData validator Java vs Python 端口选择 | D3 → subprocess Java；validator vX.Y.Z |
| Q5 | 双管线 KCC 误差实际值是否 < 0.1%？ | D4 → 基线已捕获；Plan 2 W3 实施后验证 |
```

Commit:
```powershell
git add docs/superpowers/specs/2026-05-03-compare-transit-mvp-design.md
git commit -m "docs(spec): backfill §17 open questions with discovery findings"
```

---

# Self-Review

After implementing this plan, the following spec sections should be covered:

| Spec section | Plan 1 task |
|--------------|-------------|
| §6.1 数据源 (PAN, INSEE, IGN, validator) | T1 (PAN), T2 (INSEE/IGN), T3 (validator) |
| §6.2 Pipeline 局部复用方案 | T5 (skeleton + reuse imports declared) |
| §6.3 存储模型（6 张 panel 表） | T6 (models) + T7 (migration) |
| §11 工程契约 — 双管线 KCC 一致性 | T4 (baseline) + skipped contract test |
| §12 Discovery Tasks D1–D4 | T1 / T2 / T3 / T4 |
| §5.3 Peer Group 定义 | T9 |
| §17 开放问题 Q1–Q5 | T10 step 6 |

**Not in this plan** (Plans 2–4):
- §5.1 indicator implementations (Plan 2)
- §5.2 derived layer (Plan 2)
- §7 frontend (Plan 3)
- §8 API (Plan 3)
- §9 governance / GitHub repo (Plan 4)
- §10 商业模式 (deferred V1)
- §13 风险缓解（partial — covered as guardrails throughout）
- §14 路线图 W3+（subsequent plans）

## Plan completeness check

- ✅ All 10 tasks have exact file paths
- ✅ Every code step contains complete code (no "TBD")
- ✅ Every command shows expected output
- ✅ TDD pattern (write test → fail → implement → pass) for all foundation tasks
- ✅ Discovery tasks adapt TDD to research scripts (probe → implement → run → report)
- ✅ Type consistency: `INDICATOR_IDS` (frozenset), `IndicatorValue` (TypedDict), `PanelNetwork` (Column-based), `PANDataset/PANResource` (frozen dataclass) used consistently
- ✅ Naming consistency: `panel_pipeline.run.run_panel_pipeline()` referenced uniformly
- ✅ Cross-task references (Plan 2 will replace stubs in T5, contract test in T4 activates in Plan 2 W3) documented inline

## Known unknowns deferred to discovery results

These will be filled in during execution by the discovery scripts:

- D1: exact PAN endpoint shape, history field name
- D2: exact data.gouv.fr AOM 2024 dataset slug
- D3: validator JSON schema version (v6.x assumed but verify)
- D4: full pipeline `run_pipeline_full` signature (verify after first import)

The plan is structured so these can be confirmed by running the scripts and adjusting in-place — without breaking the foundation work in W2.

---

*Plan 1 complete. Plan 2 (Indicator Pipeline, W3–W7) will be written after Plan 1 execution to incorporate discovery findings.*