"""
charts_builder.py — Phase 2 GROUP C dashboard aggregations (Task 37).

Currently exposes `build_peak_offpeak`, which buckets each AG passage
into peak or off-peak based on the course's stop departure time
(`C_2.heure_depart`).
"""
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from ..db.result_models import (
    ResultA1ArretGenerique,
    ResultC2Itineraire,
    ResultD2ServiceJourtype,
)

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
