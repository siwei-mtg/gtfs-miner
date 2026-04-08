import argparse
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from .gtfs_norm import gtfs_normalize, ligne_generate
from .gtfs_reader import read_gtfs_zip, read_gtfs_dir
from .calendar_provider import CalendarProvider, LocalXlsCalendarProvider, NullCalendarProvider
from .gtfs_spatial import ag_ap_generate_reshape
from .gtfs_generator import (
    itineraire_generate, itiarc_generate, course_generate,
    sl_generate, service_date_generate, service_jour_type_generate,
    nb_passage_ag, nb_course_ligne, caract_par_sl,
    kcc_course_ligne, kcc_course_sl, passage_arc,
)
from .gtfs_export import (
    MEF_course, MEF_iti, MEF_iti_arc,
    MEF_ligne, MEF_serdate, MEF_servjour,
)

# Module-level constants — kept for backward-compat (worker.py imports these)
DEFAULT_HPM = (7 / 24, 9 / 24)    # 07:00 – 09:00
DEFAULT_HPS = (17 / 24, 19 / 24)  # 17:00 – 19:00
DEFAULT_TYPE_VAC = 'Type_Jour'

CSV_OPTS = dict(sep=';', index=False, encoding='utf-8-sig')


@dataclass
class PipelineConfig:
    """Pipeline execution parameters. Centralises settings shared by CLI and web worker."""
    hpm:      Tuple[float, float] = field(default_factory=lambda: (7 / 24, 9 / 24))
    hps:      Tuple[float, float] = field(default_factory=lambda: (17 / 24, 19 / 24))
    type_vac: str  = DEFAULT_TYPE_VAC
    has_shp:  bool = False  # True when real shape distances are available


def build_dates_table(
    calendar: Optional[pd.DataFrame],
    calendar_dates: pd.DataFrame,
) -> pd.DataFrame:
    """
    Génère le tableau de référence des dates depuis la plage GTFS
    (remplace resources/Calendrier.txt pour le mode standalone).

    Output Schema: [Date_GTFS(int32), Type_Jour, Semaine, Mois, Annee]
    """
    dates_set: set = set()

    if calendar is not None and not calendar.empty:
        for _, row in calendar.iterrows():
            s, e = int(row['start_date']), int(row['end_date'])
            if s > 0 and e > 0:
                try:
                    start    = pd.to_datetime(str(s), format='%Y%m%d')
                    end_date = pd.to_datetime(str(e), format='%Y%m%d')
                    for d in pd.date_range(start, end_date):
                        dates_set.add(d)
                except (ValueError, OverflowError) as exc:
                    logger.warning(
                        "build_dates_table: invalid calendar date range [%s, %s], skipping: %s",
                        s, e, exc,
                    )

    for d_int in calendar_dates['date'].unique():
        d_int = int(d_int)
        if d_int > 0:
            try:
                dates_set.add(pd.to_datetime(str(d_int), format='%Y%m%d'))
            except (ValueError, OverflowError) as exc:
                logger.warning(
                    "build_dates_table: invalid date value %r in calendar_dates, skipping: %s",
                    d_int, exc,
                )

    if not dates_set:
        return pd.DataFrame(columns=['Date_GTFS', 'Type_Jour', 'Semaine', 'Mois', 'Annee'])

    date_index = pd.DatetimeIndex(sorted(dates_set))
    df = pd.DataFrame({'_d': date_index})
    df['Date_GTFS'] = df['_d'].dt.strftime('%Y%m%d').astype(np.int32)
    df['Type_Jour'] = (df['_d'].dt.dayofweek + 1).astype(np.int8)  # Mon=1 … Sun=7
    df['Semaine']   = df['_d'].dt.isocalendar().week.astype(np.int8)
    df['Mois']      = df['_d'].dt.month.astype(np.int8)
    df['Annee']     = df['_d'].dt.year.astype(np.int16)
    return df[['Date_GTFS', 'Type_Jour', 'Semaine', 'Mois', 'Annee']].drop_duplicates()


def run_pipeline(
    raw_dict: Dict[str, pd.DataFrame],
    config: Optional[PipelineConfig] = None,
    on_progress: Optional[Callable[[str], None]] = None,
    calendar_provider: Optional[CalendarProvider] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Orchestrates the full GTFS processing pipeline.
    Pure computation — no file I/O, no print statements.

    Args:
        raw_dict:    Raw GTFS tables keyed by file stem (e.g. 'stops', 'trips').
        config:      Pipeline parameters; defaults to PipelineConfig() if None.
        on_progress: Optional callback called with a step-label string at each stage.

    Returns:
        Dict of output DataFrames keyed by CSV stem name (e.g. 'A_1_Arrets_Generiques').
    """
    if config is None:
        config = PipelineConfig()
    _progress = on_progress or (lambda _: None)
    _calendar = calendar_provider or NullCalendarProvider()

    # ── 1. Normalize ──────────────────────────────────────────────────────────
    _progress("[1/7] Normalizing GTFS tables...")
    normed = gtfs_normalize(raw_dict)

    # ── 2. Spatial clustering (A_1 / A_2) ────────────────────────────────────
    _progress("[2/7] Generating spatial mappings (AG / AP)...")
    AP, AG, _marker = ag_ap_generate_reshape(normed['stops'])

    # ── 3. Itineraries, arcs & courses (C_1 / C_2 / C_3) ────────────────────
    _progress("[3/7] Generating itineraries, arcs and courses...")
    lignes         = ligne_generate(normed['routes'])
    itineraire     = itineraire_generate(normed['stop_times'], AP, normed['trips'])
    itineraire_arc = itiarc_generate(itineraire, AG)
    courses        = course_generate(itineraire, itineraire_arc)

    courses_export    = MEF_course(courses, normed['trip_id_coor'])
    itineraire_export = MEF_iti(itineraire, courses)
    iti_arc_export    = MEF_iti_arc(itineraire_arc, courses)

    # ── 4. Lignes & sous-lignes (B_1 / B_2) ──────────────────────────────────
    _progress("[4/7] Generating lignes and sous-lignes...")
    sous_ligne    = sl_generate(courses, AG, lignes)
    lignes_export = MEF_ligne(lignes, courses_export, AG)

    # ── 5. Service dates (D_1 / D_2) ─────────────────────────────────────────
    _progress("[5/7] Generating service dates and day-types...")
    Dates = build_dates_table(normed['calendar'], normed['calendar_dates'])
    Dates = _calendar.enrich(Dates)  # inject Type_Jour_Vacances_* via provider
    service_dates, _msg = service_date_generate(
        normed['calendar'], normed['calendar_dates'], Dates
    )

    # Graceful fallback: provider may not cover all dates or be NullCalendarProvider.
    type_vac = config.type_vac
    if type_vac not in service_dates.columns:
        type_vac = "Type_Jour"

    service_jour_type = service_jour_type_generate(service_dates, courses, type_vac)
    ser_dates_export  = MEF_serdate(service_dates, normed['ser_id_coor'])
    serv_jour_export  = MEF_servjour(
        service_jour_type, normed['route_id_coor'], normed['ser_id_coor'], type_vac
    )

    # ── 6. Passage counts & KCC (E_1 / E_4 / F_1–F_4) ───────────────────────
    _progress("[6/7] Generating passage counts and KCC metrics...")
    pnode = AG[['id_ag_num', 'stop_name', 'stop_lon', 'stop_lat']].rename(
        columns={'id_ag_num': 'NO', 'stop_name': 'NAME', 'stop_lon': 'LON', 'stop_lat': 'LAT'}
    )

    nb_psg_ag    = nb_passage_ag(service_jour_type, itineraire_export, AG, type_vac)
    nb_psg_arc   = passage_arc(iti_arc_export, service_jour_type, pnode, type_vac)
    nb_crs_ligne = nb_course_ligne(service_jour_type, courses_export, type_vac, lignes_export)
    caract_sl    = caract_par_sl(
        service_jour_type, courses_export, config.hpm, config.hps, type_vac, sous_ligne
    )
    kcc_ligne = kcc_course_ligne(
        service_jour_type, courses_export, type_vac, lignes_export, config.has_shp
    )
    kcc_sl = kcc_course_sl(
        service_jour_type, courses_export, type_vac, sous_ligne, config.has_shp
    )

    _progress("[7/7] Done.")

    return {
        "A_1_Arrets_Generiques":     AG,
        "A_2_Arrets_Physiques":      AP,
        "B_1_Lignes":                lignes_export,
        "B_2_Sous_Lignes":           sous_ligne,
        "C_1_Courses":               courses_export,
        "C_2_Itineraire":            itineraire_export,
        "C_3_Itineraire_Arc":        iti_arc_export,
        "D_1_Service_Dates":         ser_dates_export,
        "D_2_Service_Jourtype":      serv_jour_export,
        "E_1_Nombre_Passage_AG":     nb_psg_ag,
        "E_4_Nombre_Passage_Arc":    nb_psg_arc,
        "F_1_Nombre_Courses_Lignes": nb_crs_ligne,
        "F_2_Caract_SousLignes":     caract_sl,
        "F_3_KCC_Lignes":            kcc_ligne,
        "F_4_KCC_Sous_Ligne":        kcc_sl,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GTFS Miner pipeline without QGIS.")
    parser.add_argument("--input",  required=True, help="Path to the GTFS .zip or directory of .txt files.")
    parser.add_argument("--output", default="output", help="Directory to save output CSV files.")
    parser.add_argument("--type-vac", default=DEFAULT_TYPE_VAC,
                        choices=['Type_Jour', 'Type_Jour_Vacances_A', 'Type_Jour_Vacances_B', 'Type_Jour_Vacances_C'],
                        help="Vacation zone for day-type analysis (default: Type_Jour).")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input path '{input_path}' does not exist.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== GTFS Miner Standalone CLI ===")
    print(f"Input:    {input_path}")
    print(f"Output:   {output_dir}")
    print(f"Type-vac: {args.type_vac}\n")

    start_time = time.time()

    # CLI-only I/O: load raw GTFS tables from ZIP or directory
    if input_path.is_dir():
        raw_dict = read_gtfs_dir(input_path)
    else:
        raw_dict = read_gtfs_zip(input_path)
    if not raw_dict:
        print("Error: No GTFS .txt tables found in the input.")
        return
    print(f"  -> Loaded tables: {', '.join(raw_dict.keys())}")

    config    = PipelineConfig(type_vac=args.type_vac)
    provider  = LocalXlsCalendarProvider()
    results   = run_pipeline(raw_dict, config, on_progress=print, calendar_provider=provider)

    for name, df in results.items():
        df.to_csv(output_dir / f"{name}.csv", **CSV_OPTS)

    elapsed = time.time() - start_time
    print(f"\nDone. Processing completed in {elapsed:.2f} seconds.")
    print(f"Output files written to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
