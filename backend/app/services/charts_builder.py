"""
charts_builder.py — Phase 2 GROUP C dashboard aggregations.

Exposes four aggregations consumed by the Dashboard page:
  - build_peak_offpeak      (legacy, Task 37 — deprecated; kept for one release)
  - build_courses_by_jour_type
  - build_courses_by_hour
  - build_kpis
"""
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from ..db.result_models import (
    ResultA1ArretGenerique,
    ResultB1Ligne,
    ResultC1Course,
    ResultC2Itineraire,
    ResultD2ServiceJourtype,
    ResultE1PassageAG,
    ResultF1CourseLigne,
    ResultF3KCCLigne,
)
from ..services.gtfs_core.calendar_provider import TYPE_JOUR_VAC_LABELS

_JOUR_TYPE_LABEL_BY_VALUE: dict[int, str] = {v: k for k, v in TYPE_JOUR_VAC_LABELS.items()}

# 24 h "HH:MM:SS" strings — compared lexicographically, which works because
# the format is fixed-width and zero-padded.
#   HPM — morning peak   07:00–09:00
#   HPS — evening peak   16:30–19:00
# Every other time (incl. FM / FS / HC midday) is off-peak.
PEAK_WINDOWS: list[tuple[str, str]] = [
    ("07:00:00", "09:00:00"),
    ("16:30:00", "19:00:00"),
]


def build_peak_offpeak(project_id: str, jour_type: int, db: Session) -> dict:
    """
    Aggregate AG passages into peak / off-peak buckets for a jour_type.

    Join chain (C_2 × D_2 × A_1):
      - C_2 supplies stop-level events and their departure times.
      - D_2 filters rows to the requested jour_type via id_service_num + id_ligne_num.
      - A_1 supplies stop_name (no coordinates needed for chart rendering).

    Returns:
        {"rows": [{
            "id_ag_num": int,
            "stop_name": str,
            "peak_count": int,
            "offpeak_count": int,
        }, ...]}

    Invariant: peak_count + offpeak_count equals the number of matching
    (C_2, D_2) pairs for that AG under the requested jour_type.  When the
    D_2 calendar is fully resolved, this also equals `E_1.nb_passage`.
    """
    peak_expr = case(
        *[
            (
                (ResultC2Itineraire.heure_depart >= start)
                & (ResultC2Itineraire.heure_depart < end),
                1,
            )
            for start, end in PEAK_WINDOWS
        ],
        else_=0,
    )

    rows = (
        db.query(
            ResultC2Itineraire.id_ag_num.label("id_ag_num"),
            ResultA1ArretGenerique.stop_name.label("stop_name"),
            func.sum(peak_expr).label("peak_count"),
            func.sum(1 - peak_expr).label("offpeak_count"),
        )
        .join(
            ResultD2ServiceJourtype,
            and_(
                ResultD2ServiceJourtype.id_service_num == ResultC2Itineraire.id_service_num,
                ResultD2ServiceJourtype.id_ligne_num == ResultC2Itineraire.id_ligne_num,
                ResultD2ServiceJourtype.project_id == ResultC2Itineraire.project_id,
            ),
        )
        .join(
            ResultA1ArretGenerique,
            and_(
                ResultA1ArretGenerique.id_ag_num == ResultC2Itineraire.id_ag_num,
                ResultA1ArretGenerique.project_id == ResultC2Itineraire.project_id,
            ),
        )
        .filter(
            ResultC2Itineraire.project_id == project_id,
            ResultD2ServiceJourtype.Type_Jour == jour_type,
        )
        .group_by(ResultC2Itineraire.id_ag_num, ResultA1ArretGenerique.stop_name)
        .order_by(ResultC2Itineraire.id_ag_num)
        .all()
    )

    return {
        "rows": [
            {
                "id_ag_num": r.id_ag_num,
                "stop_name": r.stop_name,
                "peak_count": int(r.peak_count or 0),
                "offpeak_count": int(r.offpeak_count or 0),
            }
            for r in rows
        ]
    }


def _coerce_route_types(values: list[str] | None) -> list[int]:
    """Accept GTFS route_type strings ("0"…"12"), cast them to int.

    Non-numeric / unknown values are dropped silently so the caller can
    splat unsanitised query strings.
    """
    if not values:
        return []
    out: list[int] = []
    for raw in values:
        try:
            out.append(int(raw))
        except (TypeError, ValueError):
            continue
    return out


def build_courses_by_jour_type(project_id: str, db: Session) -> dict:
    """
    Aggregate F_1 rows by type_jour to give a quick "how many courses per
    day type" overview.  Unfiltered — always returns all jour_types present
    in the project.

    Returns:
        {"rows": [{"jour_type": int, "jour_type_name": str, "nb_courses": int}, ...]}

    Ordered by jour_type ascending.
    """
    rows = (
        db.query(
            ResultF1CourseLigne.type_jour.label("jour_type"),
            func.sum(ResultF1CourseLigne.nb_course).label("nb_courses"),
        )
        .filter(ResultF1CourseLigne.project_id == project_id)
        .filter(ResultF1CourseLigne.type_jour.isnot(None))
        .group_by(ResultF1CourseLigne.type_jour)
        .order_by(ResultF1CourseLigne.type_jour)
        .all()
    )
    return {
        "rows": [
            {
                "jour_type": int(r.jour_type),
                "jour_type_name": _JOUR_TYPE_LABEL_BY_VALUE.get(int(r.jour_type), str(r.jour_type)),
                "nb_courses": int(r.nb_courses or 0),
            }
            for r in rows
        ]
    }


def _coerce_int_list(values: list[int] | list[str] | None) -> list[int]:
    """Cast a heterogeneous list (URL strings or already-int) to ints, dropping
    anything that fails.  Used for ligne_ids / id_ag_num query params."""
    if not values:
        return []
    out: list[int] = []
    for raw in values:
        try:
            out.append(int(raw))
        except (TypeError, ValueError):
            continue
    return out


def _ag_to_lignes(db: Session, project_id: str, ag_ids: list[int]) -> list[int]:
    """Translate a stop set into the lines passing through them via C_2.
    Used to push an `id_ag_num` filter all the way through line-indexed
    aggregations (F_1 / F_3 / B_1) so the dashboard stays coherent."""
    if not ag_ids:
        return []
    rows = (
        db.query(func.distinct(ResultC2Itineraire.id_ligne_num))
        .filter(ResultC2Itineraire.project_id == project_id)
        .filter(ResultC2Itineraire.id_ag_num.in_(ag_ids))
        .filter(ResultC2Itineraire.id_ligne_num.isnot(None))
        .all()
    )
    return [int(r[0]) for r in rows]


def build_courses_by_hour(
    project_id: str,
    jour_type: int,
    route_types: list[str] | None,
    db: Session,
    *,
    ligne_ids: list[int] | None = None,
    ag_ids: list[int] | None = None,
) -> dict:
    """
    Aggregate distinct C_1 courses into 24 hourly buckets (0..23) for a
    jour_type, optionally restricted to a list of GTFS route_types and/or
    canonical ligne / stop IDs (from a table filter or a map click).

    Hour is extracted from `C_1.heure_depart` (HH:MM:SS) via substr; values
    >= 24 (GTFS next-day notation) are wrapped into 0..23 with `% 24`.

    Join chain (C_1 × D_2 × B_1):
      - D_2 filters courses to those running on `jour_type`
      - B_1 is joined only when `route_types` is non-empty
      - `ag_ids` is funneled through C_2.id_ligne_num so we keep the chart
        as a course-count (not a stop-passage count).
    """
    from sqlalchemy import Integer

    rt_ints = _coerce_route_types(route_types)
    ll_ints = _coerce_int_list(ligne_ids)
    ag_ints = _coerce_int_list(ag_ids)
    if ag_ints:
        # Intersect with the ligne_ids filter when both are present so the
        # narrower of the two wins.
        derived = _ag_to_lignes(db, project_id, ag_ints)
        ll_ints = sorted(set(ll_ints) & set(derived)) if ll_ints else derived

    # Raw hour int from "HH:MM:SS" via substr; wrapping > 23 is done in Python
    # below so GTFS next-day notation (24/25/26…) still falls into a bucket.
    hour_int = func.cast(func.substr(ResultC1Course.heure_depart, 1, 2), Integer)

    q = (
        db.query(
            hour_int.label("heure_raw"),
            func.count(func.distinct(ResultC1Course.id_course_num)).label("nb_courses"),
        )
        .join(
            ResultD2ServiceJourtype,
            and_(
                ResultD2ServiceJourtype.id_service_num == ResultC1Course.id_service_num,
                ResultD2ServiceJourtype.id_ligne_num == ResultC1Course.id_ligne_num,
                ResultD2ServiceJourtype.project_id == ResultC1Course.project_id,
            ),
        )
        .filter(
            ResultC1Course.project_id == project_id,
            ResultD2ServiceJourtype.Type_Jour == jour_type,
            ResultC1Course.heure_depart.isnot(None),
        )
    )

    if ll_ints:
        q = q.filter(ResultC1Course.id_ligne_num.in_(ll_ints))

    if rt_ints:
        q = q.join(
            ResultB1Ligne,
            and_(
                ResultB1Ligne.id_ligne_num == ResultC1Course.id_ligne_num,
                ResultB1Ligne.project_id == ResultC1Course.project_id,
            ),
        ).filter(ResultB1Ligne.route_type.in_(rt_ints))

    rows = q.group_by(hour_int).order_by(hour_int).all()

    # Wrap next-day GTFS hours (24, 25, 26…) into 0..23.
    bucket: dict[int, int] = {h: 0 for h in range(24)}
    for r in rows:
        if r.heure_raw is None:
            continue
        h = int(r.heure_raw) % 24
        bucket[h] += int(r.nb_courses or 0)

    return {"rows": [{"heure": h, "nb_courses": bucket[h]} for h in range(24)]}


def build_kpis(
    project_id: str,
    jour_type: int,
    route_types: list[str] | None,
    db: Session,
    *,
    ligne_ids: list[int] | None = None,
    ag_ids: list[int] | None = None,
) -> dict:
    """
    Compute 4 dashboard KPIs in a single pass:
      - nb_lignes  : distinct lines with > 0 courses on `jour_type`
      - nb_arrets  : distinct AGs with > 0 passages on `jour_type`
      - nb_courses : SUM(F_1.nb_course) on `jour_type`
      - kcc_total  : SUM(F_3.kcc) on `jour_type` (rounded to 2 decimals)

    Filters (all optional, all AND-combined):
      - ``route_types`` narrows the line-indexed KPIs via B_1 join.
      - ``ligne_ids`` directly restricts every KPI to the given lines (and
        ``nb_arrets`` to AGs served by them via C_2).
      - ``ag_ids`` directly restricts ``nb_arrets``; for the line-indexed
        KPIs it's translated through C_2 to "lines passing through any of
        these stops" so the four numbers stay mutually coherent.

    Composition rule when both ``ligne_ids`` and ``ag_ids`` are present:
    intersect (lines AND stops-of-stops), so narrower wins.
    """
    rt_ints = _coerce_route_types(route_types)
    ll_ints = _coerce_int_list(ligne_ids)
    ag_ints = _coerce_int_list(ag_ids)

    # If only stops are filtered, still constrain line-indexed KPIs by the
    # set of lines those stops belong to.  Intersect with explicit ligne_ids
    # when both are present so the narrower wins (rather than overwriting).
    line_constraint: list[int] = list(ll_ints)
    if ag_ints:
        derived = _ag_to_lignes(db, project_id, ag_ints)
        if line_constraint:
            line_constraint = sorted(set(line_constraint) & set(derived))
        else:
            line_constraint = derived

    def _join_b1(q, model):
        """Join `model` onto B_1 (same project) so we can filter on route_type."""
        return q.join(
            ResultB1Ligne,
            and_(
                ResultB1Ligne.id_ligne_num == model.id_ligne_num,
                ResultB1Ligne.project_id == model.project_id,
            ),
        ).filter(ResultB1Ligne.route_type.in_(rt_ints))

    def _apply_line_constraint(q, model):
        if not line_constraint:
            return q
        return q.filter(model.id_ligne_num.in_(line_constraint))

    # --- nb_lignes ---------------------------------------------------------
    lignes_q = db.query(
        func.count(func.distinct(ResultF1CourseLigne.id_ligne_num))
    ).filter(
        ResultF1CourseLigne.project_id == project_id,
        ResultF1CourseLigne.type_jour == jour_type,
        ResultF1CourseLigne.nb_course > 0,
    )
    if rt_ints:
        lignes_q = _join_b1(lignes_q, ResultF1CourseLigne)
    lignes_q = _apply_line_constraint(lignes_q, ResultF1CourseLigne)
    nb_lignes = int(lignes_q.scalar() or 0)

    # --- nb_arrets ---------------------------------------------------------
    arrets_q = db.query(
        func.count(func.distinct(ResultE1PassageAG.id_ag_num))
    ).filter(
        ResultE1PassageAG.project_id == project_id,
        ResultE1PassageAG.type_jour == jour_type,
    )
    if ag_ints:
        arrets_q = arrets_q.filter(ResultE1PassageAG.id_ag_num.in_(ag_ints))
    elif line_constraint:
        # Lines without an explicit stop set → AGs served by those lines.
        served_ag = _lignes_to_ags(db, project_id, line_constraint)
        if served_ag:
            arrets_q = arrets_q.filter(ResultE1PassageAG.id_ag_num.in_(served_ag))
        else:
            arrets_q = arrets_q.filter(ResultE1PassageAG.id_ag_num.in_([]))  # empty -> 0
    nb_arrets = int(arrets_q.scalar() or 0)

    # --- nb_courses --------------------------------------------------------
    courses_q = db.query(
        func.sum(ResultF1CourseLigne.nb_course)
    ).filter(
        ResultF1CourseLigne.project_id == project_id,
        ResultF1CourseLigne.type_jour == jour_type,
    )
    if rt_ints:
        courses_q = _join_b1(courses_q, ResultF1CourseLigne)
    courses_q = _apply_line_constraint(courses_q, ResultF1CourseLigne)
    nb_courses = int(courses_q.scalar() or 0)

    # --- kcc_total ---------------------------------------------------------
    kcc_q = db.query(
        func.sum(ResultF3KCCLigne.kcc)
    ).filter(
        ResultF3KCCLigne.project_id == project_id,
        ResultF3KCCLigne.type_jour == jour_type,
    )
    if rt_ints:
        kcc_q = _join_b1(kcc_q, ResultF3KCCLigne)
    kcc_q = _apply_line_constraint(kcc_q, ResultF3KCCLigne)
    kcc_total = float(kcc_q.scalar() or 0.0)

    return {
        "nb_lignes": nb_lignes,
        "nb_arrets": nb_arrets,
        "nb_courses": nb_courses,
        "kcc_total": round(kcc_total, 2),
    }


def _lignes_to_ags(db: Session, project_id: str, ligne_ids: list[int]) -> list[int]:
    """Translate a line set into the AGs served by them via C_2.  Symmetric to
    `_ag_to_lignes` — used by ``build_kpis`` to narrow ``nb_arrets`` when
    only a line filter is set."""
    if not ligne_ids:
        return []
    rows = (
        db.query(func.distinct(ResultC2Itineraire.id_ag_num))
        .filter(ResultC2Itineraire.project_id == project_id)
        .filter(ResultC2Itineraire.id_ligne_num.in_(ligne_ids))
        .filter(ResultC2Itineraire.id_ag_num.isnot(None))
        .all()
    )
    return [int(r[0]) for r in rows]
