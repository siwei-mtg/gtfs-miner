"""
map_builder.py — Service functions for Phase 2 map data APIs.

Builds GeoJSON payloads derived from Phase 1 result tables.
No schema changes required; all data already exists post-pipeline.
"""
import math
import tempfile
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point, Polygon
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.result_models import (
    ResultE1PassageAG,
    ResultC2Itineraire,
    ResultB1Ligne,
    ResultE4PassageArc,
    ResultA1ArretGenerique,
    ResultC3ItineraireArc,
    ResultD1ServiceDate,
    ResultA2ArretPhysique,
)

_GPKG_BATCH = 500  # max AG ids per GeoDataFrame chunk for memory-efficient export


def build_passage_ag_geojson(project_id: str, jour_type: int, db: Session) -> dict:
    """
    Build a GeoJSON FeatureCollection of AG (generic stop) points with
    passage counts disaggregated by route_type.

    Join chain:
        E1 (filtered by type_jour) → C2 on id_ag_num → B1 on id_ligne_num
        COUNT(DISTINCT id_course_num) GROUP BY (id_ag_num, route_type)

    nb_passage_total == sum(by_route_type.values()) is guaranteed by
    construction: both values derive from the same course-count query.

    Args:
        project_id: Project identifier (tenant-scoped by caller).
        jour_type:  Day-type integer used to filter E1 rows.
        db:         SQLAlchemy session.

    Returns:
        GeoJSON FeatureCollection dict.
    """
    # Step 1: fetch all AGs present in E1 for this project + jour_type.
    # E1 carries stop coordinates so no A1 join is needed.
    e1_rows = (
        db.query(ResultE1PassageAG)
        .filter(
            ResultE1PassageAG.project_id == project_id,
            ResultE1PassageAG.type_jour == jour_type,
        )
        .all()
    )
    if not e1_rows:
        return {"type": "FeatureCollection", "features": []}

    ag_meta: dict[int, tuple[str | None, float | None, float | None]] = {
        r.id_ag_num: (r.stop_name, r.stop_lat, r.stop_lon)
        for r in e1_rows
    }
    ag_ids = list(ag_meta.keys())

    # Step 2: count distinct courses per (id_ag_num, route_type).
    # C2 links courses to lines (id_ligne_num); B1 carries route_type.
    count_rows = (
        db.query(
            ResultC2Itineraire.id_ag_num,
            ResultB1Ligne.route_type,
            func.count(ResultC2Itineraire.id_course_num.distinct()).label("n"),
        )
        .join(
            ResultB1Ligne,
            (ResultB1Ligne.id_ligne_num == ResultC2Itineraire.id_ligne_num)
            & (ResultB1Ligne.project_id == ResultC2Itineraire.project_id),
        )
        .filter(
            ResultC2Itineraire.project_id == project_id,
            ResultC2Itineraire.id_ag_num.in_(ag_ids),
        )
        .group_by(ResultC2Itineraire.id_ag_num, ResultB1Ligne.route_type)
        .all()
    )

    # Collect counts per AG
    by_ag: dict[int, dict[int, int]] = defaultdict(dict)
    for ag_num, route_type, count in count_rows:
        by_ag[ag_num][route_type] = count

    # Step 3: assemble GeoJSON features
    features = []
    for ag_num in ag_ids:
        stop_name, lat, lon = ag_meta[ag_num]
        if lat is None or lon is None:
            continue
        by_rt = by_ag.get(ag_num, {})
        total = sum(by_rt.values())
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
                "properties": {
                    "id_ag_num": ag_num,
                    "stop_name": stop_name,
                    "nb_passage_total": total,
                    "by_route_type": {str(k): v for k, v in by_rt.items()},
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def build_passage_arc_geojson(

    project_id: str,
    jour_type: int,
    db: Session,
    split_by: str = "none",
) -> dict:
    """
    Build a GeoJSON FeatureCollection of directed arcs (E_4) for
    AequilibraE-style bandwidth rendering.

    split_by="none":
        One Feature per arc. Properties: direction, weight (global-normalised 0–1),
        nb_passage, split_by="none".

    split_by="route_type":
        One Feature per (arc, route_type). Extra properties:
        category_value, fraction_of_direction, cumulative_fraction_start.
        Fractions derived by joining C3 → D1 (type_jour filter) → B1.

    Frontend rendering formula (pixel-based, zoom-independent):
        // split_by="none":
        line_width  = weight × max_width_px
        line_offset = sign(direction) × (gap_px/2 + line_width/2)

        // split_by="route_type":
        sub_width   = fraction_of_direction × weight × max_width_px
        line_offset = sign(direction) × (gap_px/2
                      + cumulative_fraction_start × weight × max_width_px
                      + sub_width/2)

        sign(direction): AB → +1, BA → -1
        max_width_px and gap_px are user-adjustable frontend sliders (default 40px / 4px).

    Args:
        project_id: tenant-scoped project identifier.
        jour_type:  day-type integer (matches E4.type_jour).
        db:         SQLAlchemy session.
        split_by:   "none" or "route_type".

    Returns:
        GeoJSON FeatureCollection dict.
    """
    # 1. Fetch E4 rows filtered by project + day-type
    e4_rows = (
        db.query(ResultE4PassageArc)
        .filter(
            ResultE4PassageArc.project_id == project_id,
            ResultE4PassageArc.type_jour  == jour_type,
        )
        .all()
    )
    if not e4_rows:
        return {"type": "FeatureCollection", "features": []}

    # 2. Fetch A1 stop coordinates for all unique AG ids in E4
    ag_ids = {r.id_ag_num_a for r in e4_rows} | {r.id_ag_num_b for r in e4_rows}
    coords: dict[int, tuple[float, float]] = {
        r.id_ag_num: (r.stop_lat, r.stop_lon)
        for r in db.query(ResultA1ArretGenerique).filter(
            ResultA1ArretGenerique.project_id == project_id,
            ResultA1ArretGenerique.id_ag_num.in_(list(ag_ids)),
        ).all()
        if r.stop_lat is not None and r.stop_lon is not None
    }

    # 3. Global normalisation denominator
    max_passage = max((r.nb_passage for r in e4_rows), default=1.0) or 1.0

    # 4. Build arc → nb_passage lookup
    arc_map: dict[tuple[int, int], float] = {
        (r.id_ag_num_a, r.id_ag_num_b): r.nb_passage for r in e4_rows
    }

    # 5. Optional route_type breakdown: C3 → D1 → B1
    # arc_rt_counts[(a, b)][route_type] = count of distinct courses
    arc_rt_counts: dict[tuple[int, int], dict[int, int]] = {}
    if split_by == "route_type":
        rt_rows = (
            db.query(
                ResultC3ItineraireArc.id_ag_num_a,
                ResultC3ItineraireArc.id_ag_num_b,
                ResultB1Ligne.route_type,
                func.count(ResultC3ItineraireArc.id_course_num.distinct()).label("n"),
            )
            .join(
                ResultD1ServiceDate,
                (ResultD1ServiceDate.id_service_num == ResultC3ItineraireArc.id_service_num)
                & (ResultD1ServiceDate.project_id   == ResultC3ItineraireArc.project_id),
            )
            .join(
                ResultB1Ligne,
                (ResultB1Ligne.id_ligne_num == ResultC3ItineraireArc.id_ligne_num)
                & (ResultB1Ligne.project_id == ResultC3ItineraireArc.project_id),
            )
            .filter(
                ResultC3ItineraireArc.project_id == project_id,
                ResultD1ServiceDate.Type_Jour    == jour_type,
            )
            .group_by(
                ResultC3ItineraireArc.id_ag_num_a,
                ResultC3ItineraireArc.id_ag_num_b,
                ResultB1Ligne.route_type,
            )
            .all()
        )
        for a, b, rt, n in rt_rows:
            arc_rt_counts.setdefault((a, b), {})[rt] = n

    # 6. Assemble GeoJSON features
    features = []
    for (a, b), nb_passage in arc_map.items():
        if a not in coords or b not in coords:
            continue
        lat_a, lon_a = coords[a]
        lat_b, lon_b = coords[b]
        direction = "AB" if a <= b else "BA"
        weight    = round(nb_passage / max_passage, 6)
        geom      = {
            "type": "LineString",
            "coordinates": [[lon_a, lat_a], [lon_b, lat_b]],
        }

        if split_by == "route_type" and (a, b) in arc_rt_counts:
            rt_dict  = arc_rt_counts[(a, b)]
            total_rt = sum(rt_dict.values()) or 1
            cumul    = 0.0
            for rt in sorted(rt_dict):          # deterministic order by route_type value
                fraction = rt_dict[rt] / total_rt
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "id_ag_num_a":               a,
                        "id_ag_num_b":               b,
                        "direction":                 direction,
                        "weight":                    weight,
                        "split_by":                  "route_type",
                        "category_value":            str(rt),
                        "nb_passage_category":       round(nb_passage * fraction, 2),
                        "fraction_of_direction":     round(fraction, 6),
                        "cumulative_fraction_start": round(cumul, 6),
                    },
                })
                cumul += fraction
        else:
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "id_ag_num_a": a,
                    "id_ag_num_b": b,
                    "nb_passage":  nb_passage,
                    "direction":   direction,
                    "weight":      weight,
                    "split_by":    "none",
                },
            })

    return {"type": "FeatureCollection", "features": features}


# ──────────────────────────────────────────────────────────────────────────────
# GeoPackage export (Task 32)
# ──────────────────────────────────────────────────────────────────────────────

def _make_bandwidth_polygon(
    lat_a: float, lon_a: float,
    lat_b: float, lon_b: float,
    width_m: float,
) -> Polygon:
    """Build a right-side rectangular Polygon of width_m along the A→B arc.

    The four corners are A, B, B_right, A_right (closed), where *_right are
    the original points shifted perpendicularly to the right of travel by
    width_m metres (approximate planar conversion at the midpoint latitude).
    """
    lat_mid = math.radians((lat_a + lat_b) / 2)
    east_m  = (lon_b - lon_a) * 111_000 * math.cos(lat_mid)
    north_m = (lat_b - lat_a) * 111_000
    length_m = math.hypot(east_m, north_m)
    if length_m < 1e-9:
        return Polygon([(lon_a, lat_a)] * 4)
    perp_east  =  north_m / length_m
    perp_north = -east_m  / length_m
    d_lon = perp_east  * width_m / (111_000 * math.cos(lat_mid))
    d_lat = perp_north * width_m / 111_000
    return Polygon([
        (lon_a,          lat_a        ),
        (lon_b,          lat_b        ),
        (lon_b + d_lon,  lat_b + d_lat),
        (lon_a + d_lon,  lat_a + d_lat),
        (lon_a,          lat_a        ),
    ])


def export_geopackage(
    project_id: str,
    jour_type: int,
    db: Session,
    scale_m: float = 5.0,
) -> Path:
    """Export map layers to a temporary GeoPackage file.

    Layers written (in order):
        passage_ag        — Point,   E_1 stop passages for jour_type
        passage_arc       — Polygon, E_4 directed arc bandwidths (AB + BA)
        arrets_generiques — Point,   A_1 generic stops
        arrets_physiques  — Point,   A_2 physical stops

    Memory strategy: each GeoDataFrame is built, written, then deleted
    before the next layer starts.  Large layers are fetched in batches of
    ≤ _GPKG_BATCH AG ids to cap peak memory.

    Args:
        project_id: tenant-scoped project identifier.
        jour_type:  day-type integer (filters passage layers).
        db:         SQLAlchemy session.
        scale_m:    metres per passage unit for arc polygon width.

    Returns:
        Path to a temporary .gpkg file — caller must delete it when done.
    """
    out_path = Path(tempfile.mktemp(suffix=".gpkg"))
    gpkg_created = False  # True after the first layer has been written

    def _write(gdf: gpd.GeoDataFrame, layer: str) -> None:
        nonlocal gpkg_created
        gdf.to_file(
            out_path, layer=layer, driver="GPKG",
            mode="a" if gpkg_created else "w",
        )
        gpkg_created = True

    # ── 1. passage_ag (Point) ─────────────────────────────────────────────────
    ag_ids = [
        r.id_ag_num
        for r in db.query(ResultE1PassageAG.id_ag_num)
        .filter(
            ResultE1PassageAG.project_id == project_id,
            ResultE1PassageAG.type_jour  == jour_type,
        )
        .distinct()
        .all()
    ]
    first_chunk = True
    for i in range(0, len(ag_ids), _GPKG_BATCH):
        chunk = ag_ids[i : i + _GPKG_BATCH]
        rows = (
            db.query(ResultE1PassageAG)
            .filter(
                ResultE1PassageAG.project_id == project_id,
                ResultE1PassageAG.type_jour  == jour_type,
                ResultE1PassageAG.id_ag_num.in_(chunk),
            )
            .all()
        )
        records = [
            {
                "id_ag_num":  r.id_ag_num,
                "stop_name":  r.stop_name,
                "nb_passage": r.nb_passage,
                "geometry":   Point(r.stop_lon, r.stop_lat),
            }
            for r in rows
            if r.stop_lat is not None and r.stop_lon is not None
        ]
        if not records:
            continue
        gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
        if first_chunk:
            _write(gdf, "passage_ag")
            first_chunk = False
        else:
            gdf.to_file(out_path, layer="passage_ag", driver="GPKG", mode="a")
        del gdf

    # ── 2. passage_arc (Polygon) ──────────────────────────────────────────────
    e4_rows = (
        db.query(ResultE4PassageArc)
        .filter(
            ResultE4PassageArc.project_id == project_id,
            ResultE4PassageArc.type_jour  == jour_type,
        )
        .all()
    )
    if e4_rows:
        all_arc_ag_ids = list(
            {r.id_ag_num_a for r in e4_rows} | {r.id_ag_num_b for r in e4_rows}
        )
        coords: dict[int, tuple[float, float]] = {}
        for i in range(0, len(all_arc_ag_ids), _GPKG_BATCH):
            chunk = all_arc_ag_ids[i : i + _GPKG_BATCH]
            for r in (
                db.query(ResultA1ArretGenerique)
                .filter(
                    ResultA1ArretGenerique.project_id == project_id,
                    ResultA1ArretGenerique.id_ag_num.in_(chunk),
                )
                .all()
            ):
                if r.stop_lat is not None and r.stop_lon is not None:
                    coords[r.id_ag_num] = (r.stop_lat, r.stop_lon)

        buf: list[dict] = []
        first_arc_chunk = True

        def _flush_arc() -> None:
            nonlocal first_arc_chunk
            if not buf:
                return
            gdf = gpd.GeoDataFrame(buf.copy(), geometry="geometry", crs="EPSG:4326")
            if first_arc_chunk:
                _write(gdf, "passage_arc")
                first_arc_chunk = False
            else:
                gdf.to_file(out_path, layer="passage_arc", driver="GPKG", mode="a")
            del gdf
            buf.clear()

        for row in e4_rows:
            a, b = row.id_ag_num_a, row.id_ag_num_b
            if a not in coords or b not in coords:
                continue
            direction = "AB" if a <= b else "BA"
            # AB: polygon on right of A→B; BA: swap coords so polygon is on
            # right of B→A (= left of A→B), matching the API band layout.
            if direction == "AB":
                lat_s, lon_s = coords[a]
                lat_e, lon_e = coords[b]
            else:
                lat_s, lon_s = coords[b]
                lat_e, lon_e = coords[a]
            width_m = row.nb_passage * scale_m
            buf.append({
                "id_ag_num_a": a,
                "id_ag_num_b": b,
                "nb_passage":  row.nb_passage,
                "direction":   direction,
                "width_m":     round(width_m, 2),
                "geometry":    _make_bandwidth_polygon(lat_s, lon_s, lat_e, lon_e, width_m),
            })
            if len(buf) >= _GPKG_BATCH:
                _flush_arc()
        _flush_arc()

    # ── 3. arrets_generiques (Point) ──────────────────────────────────────────
    a1_ids = [
        r.id_ag_num
        for r in db.query(ResultA1ArretGenerique.id_ag_num)
        .filter(ResultA1ArretGenerique.project_id == project_id)
        .distinct()
        .all()
    ]
    first_chunk = True
    for i in range(0, len(a1_ids), _GPKG_BATCH):
        chunk = a1_ids[i : i + _GPKG_BATCH]
        rows = (
            db.query(ResultA1ArretGenerique)
            .filter(
                ResultA1ArretGenerique.project_id == project_id,
                ResultA1ArretGenerique.id_ag_num.in_(chunk),
            )
            .all()
        )
        records = [
            {
                "id_ag_num": r.id_ag_num,
                "id_ag":     r.id_ag,
                "stop_name": r.stop_name,
                "geometry":  Point(r.stop_lon, r.stop_lat),
            }
            for r in rows
            if r.stop_lat is not None and r.stop_lon is not None
        ]
        if not records:
            continue
        gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
        if first_chunk:
            _write(gdf, "arrets_generiques")
            first_chunk = False
        else:
            gdf.to_file(out_path, layer="arrets_generiques", driver="GPKG", mode="a")
        del gdf

    # ── 4. arrets_physiques (Point) ───────────────────────────────────────────
    a2_ids = [
        r.id_ap_num
        for r in db.query(ResultA2ArretPhysique.id_ap_num)
        .filter(ResultA2ArretPhysique.project_id == project_id)
        .distinct()
        .all()
    ]
    first_chunk = True
    for i in range(0, len(a2_ids), _GPKG_BATCH):
        chunk = a2_ids[i : i + _GPKG_BATCH]
        rows = (
            db.query(ResultA2ArretPhysique)
            .filter(
                ResultA2ArretPhysique.project_id == project_id,
                ResultA2ArretPhysique.id_ap_num.in_(chunk),
            )
            .all()
        )
        records = [
            {
                "id_ap_num": r.id_ap_num,
                "id_ag_num": r.id_ag_num,
                "id_ap":     r.id_ap,
                "stop_name": r.stop_name,
                "geometry":  Point(r.stop_lon, r.stop_lat),
            }
            for r in rows
            if r.stop_lat is not None and r.stop_lon is not None
        ]
        if not records:
            continue
        gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
        if first_chunk:
            _write(gdf, "arrets_physiques")
            first_chunk = False
        else:
            gdf.to_file(out_path, layer="arrets_physiques", driver="GPKG", mode="a")
        del gdf

    return out_path
