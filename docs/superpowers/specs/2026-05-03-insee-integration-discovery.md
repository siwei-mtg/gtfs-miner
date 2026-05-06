# D2 — INSEE/IGN Coverage Prototype Discovery

**Status**: 🟡 Code ready, awaiting data download for end-to-end validation

**Date**: 2026-05-05

## Summary

| Layer | Status |
|-------|--------|
| Reusable module `app/services/panel_pipeline/geo.py` | ✅ Complete (4 indicators) |
| Unit tests on synthetic Lambert-93 fixtures | ✅ 13/13 passing |
| Discovery script `backend/scripts/discovery/d2_insee_coverage.py` | ✅ Complete (driver only) |
| INSEE Filosofi 2017 200m carroyage (~205 MB) | ⏸️ Manual download pending |
| AOM 2024 polygons GeoJSON (~10 MB) | ⏸️ Manual download pending |
| End-to-end run on SEM (Métropole Grenoble Alpes) | ⏸️ Blocked on data above |

## Implementation

### `panel_pipeline/geo.py` — public API

```python
from app.services.panel_pipeline.geo import (
    load_carroyage_200m,        # bbox-filtered GeoPackage read, returns GDF
    load_aom_polygon,           # by attribute match, normalises to Lambert-93
    gtfs_stops_to_geodataframe, # WGS84 stops_df → Lambert-93 GDF
    compute_coverage,           # the 4 indicators
)
```

`compute_coverage(stops, carroyage, aom_polygon, *, buffer_m=300)` returns a
`CoverageIndicators` TypedDict:

| Field | Unit | Definition |
|-------|------|------------|
| `cov_pop_300m` | % | AOM population in cells overlapping the 300m buffer / total AOM pop |
| `cov_surface_300m` | % | AOM-clipped buffer area / total AOM area |
| `cov_median_walk` | m | median centroid → nearest-stop distance (over AOM cells) |
| `cov_pop_weighted_walk` | m | population-weighted mean of the same distance |
| `total_pop` | residents | sum of `Ind` across AOM-clipped carreaux |
| `total_surface_km2` | km² | AOM polygon area |
| `stop_count` | int | physical GTFS stops post-filter |
| `cell_count` | int | carreaux clipped to AOM |

### CRS contract

All metric ops happen in **EPSG:2154 (Lambert-93)**. Inputs in WGS84 are
re-projected silently — `gtfs_stops_to_geodataframe` and `load_*` helpers
handle this so callers don't need to think about it.

### Algorithm

1. Clip carroyage to the AOM polygon (denominator).
2. Build the union of stop-buffered geometries (300m default).
3. `cov_pop_300m`: cells **intersecting** the buffer count their full
   population (cell-level intersection, not area-weighted) — mirrors INSEE's
   typical reporting convention.
4. `cov_surface_300m`: AOM ∩ buffer area / AOM area (continuous).
5. Walk distances: `sjoin_nearest` from each cell centroid to the nearest
   stop, taking median + population-weighted mean.

## Data sources to download

### INSEE Filosofi 2017 carreaux 200m

- **Landing**: https://www.insee.fr/fr/statistiques/6215138?sommaire=6215217
- **Direct ZIP**: https://www.insee.fr/fr/statistiques/fichier/6215138/Filosofi2017_carreaux_200m_gpkg.zip (205 MB)
- **Format note**: the ZIP wraps a 215 MB **.7z** archive containing the
  GeoPackage. Extract twice; on Windows, 7-Zip handles both layers.
- **Place at**: `backend/storage/discovery/d2/Filosofi2017_carreaux_200m.gpkg`

### AOM 2024 polygons (Cerema)

- **Landing**: https://www.data.gouv.fr/fr/datasets/les-autorites-organisatrices-de-la-mobilite-aom/
- **Format**: GeoJSON of all ~470 AOMs across France
- **Place at**: `backend/storage/discovery/d2/aom_2024.geojson`
- **Target row** for the SEM fixture: `Nom_AOM == "Métropole Grenoble Alpes"`
  (override via optional `backend/storage/discovery/d2/aom_target.json` —
  `{"field": "...", "value": "..."}`).

## Running end-to-end

After both files are in place:

```powershell
backend\venv\Scripts\python.exe backend\scripts\discovery\d2_insee_coverage.py
```

Expected:
- 4 indicator values + AOM denominators + cell/stop counts logged
- `backend/storage/discovery/d2/sem_coverage.json` written
- This spec file overwritten with measured numbers + memory/time

The discovery script bbox-filters the carroyage at read time (AOM bbox +
1 km padding) so the working set stays bounded — full-Métropole reads peak
~3-4 GB RAM, AOM-scoped reads stay well under 500 MB for SEM-class networks.

## Plan 2 integration

`panel_pipeline.indicators.coverage` will call `compute_coverage` with:
- per-feed AOM polygon (resolved via `panel_network.aom_id` — Plan 2 Task 4)
- bbox-filtered carroyage (cached once per pipeline run)

V1+ indicators not covered here:
- `cov_pop_freq_300m` — same buffer logic but stops filtered by HF service
  (departures/hour during peak); layered on top of this primitive.
- `cov_equity_gini` — Gini coefficient of walk-distance distribution across
  the AOM's deciles of household income (uses INSEE Filosofi income fields,
  not just `Ind`).

## Open questions for Plan 2

| ID | Question | Resolution path |
|----|----------|-----------------|
| Q3 | INSEE 200m carroyage processing memory peak / time | Measured by `d2_insee_coverage.py` once data lands |
| Q3a | AOM ID field stability across years (siren vs Code_AOM vs Nom_AOM) | Verify Cerema 2024 vs 2025 schema; pick the most stable |
| Q3b | DOM coverage (Martinique / Réunion / Guadeloupe carreaux) | INSEE GPKG includes them; check `Nom_AOM` matches Cerema's DOM AOMs |

_Generated by `backend/scripts/discovery/d2_insee_coverage.py` (geo.py + tests path)._
