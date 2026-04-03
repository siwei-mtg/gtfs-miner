import argparse
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Import the decoupled pipeline modules
from gtfs_norm import rawgtfs_from_zip, gtfs_normalize, ligne_generate
from gtfs_spatial import ag_ap_generate_reshape
from gtfs_generator import (
    itineraire_generate, itiarc_generate, course_generate,
    sl_generate, service_date_generate, service_jour_type_generate,
    nb_passage_ag, nb_course_ligne, caract_par_sl,
    kcc_course_ligne, kcc_course_sl, passage_arc,
)
from gtfs_export import (
    MEF_course, MEF_iti, MEF_iti_arc,
    MEF_ligne, MEF_serdate, MEF_servjour,
)

# Plages horaires HPM / HPS par défaut (fraction de jour)
DEFAULT_HPM = (7 / 24, 9 / 24)    # 07:00 – 09:00
DEFAULT_HPS = (17 / 24, 19 / 24)  # 17:00 – 19:00
DEFAULT_TYPE_VAC = 'Type_Jour'

CSV_OPTS = dict(sep=';', index=False, encoding='utf-8-sig')


def build_dates_table(
    calendar: Optional[pd.DataFrame],
    calendar_dates: pd.DataFrame,
) -> pd.DataFrame:
    """
    Génère le tableau de référence des dates depuis la plage GTFS
    (remplace Resources/Calendrier.txt pour le mode standalone).

    Output Schema: [Date_GTFS(int32), Type_Jour, Semaine, Mois, Annee]
    """
    dates_set: set = set()

    if calendar is not None and not calendar.empty:
        for _, row in calendar.iterrows():
            s, e = int(row['start_date']), int(row['end_date'])
            if s > 0 and e > 0:
                try:
                    start = pd.to_datetime(str(s), format='%Y%m%d')
                    end   = pd.to_datetime(str(e), format='%Y%m%d')
                    for d in pd.date_range(start, end):
                        dates_set.add(d)
                except Exception:
                    pass

    for d_int in calendar_dates['date'].unique():
        d_int = int(d_int)
        if d_int > 0:
            try:
                dates_set.add(pd.to_datetime(str(d_int), format='%Y%m%d'))
            except Exception:
                pass

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
    type_vac   = args.type_vac

    if not input_path.exists():
        print(f"Error: Input path '{input_path}' does not exist.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== GTFS Miner Standalone CLI ===")
    print(f"Input:    {input_path}")
    print(f"Output:   {output_dir}")
    print(f"Type-vac: {type_vac}\n")

    start_time = time.time()

    # ------------------------------------------------------------------
    # 1. Load & normalise
    # ------------------------------------------------------------------
    print("[1/7] Loading raw GTFS data...")
    if input_path.is_dir():
        raw_dict = {}
        for f in input_path.glob('*.txt'):
            raw_dict[f.stem] = pd.read_csv(f, low_memory=False)
    else:
        raw_dict = rawgtfs_from_zip(input_path)

    if not raw_dict:
        print("Error: No GTFS .txt tables found in the input.")
        return
    print(f"  -> Loaded tables: {', '.join(raw_dict.keys())}")

    print("[2/7] Normalizing schema...")
    normed = gtfs_normalize(raw_dict)
    shapes_exist = normed.get('shapes') is not None
    print(f"  -> {len(normed['stops'])} stops | {len(normed['routes'])} routes | {len(normed['trips'])} trips")
    print(f"  -> shapes: {'yes' if shapes_exist else 'no'}")

    # ------------------------------------------------------------------
    # 2. Spatial (A_1 / A_2)
    # ------------------------------------------------------------------
    print("[3/7] Generating spatial mappings (AG / AP)...")
    AP, AG, marker = ag_ap_generate_reshape(normed['stops'])
    print(f"  -> Clustering: {marker}")
    print(f"  -> {len(AG)} AG | {len(AP)} AP")

    AG.to_csv(output_dir / "A_1_Arrets_Generiques.csv", **CSV_OPTS)
    AP.to_csv(output_dir / "A_2_Arrets_Physiques.csv",  **CSV_OPTS)

    # ------------------------------------------------------------------
    # 3. Itinerary & courses (C_1 / C_2 / C_3)
    # ------------------------------------------------------------------
    print("[4/7] Generating itineraries, arcs and courses...")
    lignes    = ligne_generate(normed['routes'])
    itineraire     = itineraire_generate(normed['stop_times'], AP, normed['trips'])
    itineraire_arc = itiarc_generate(itineraire, AG)
    courses        = course_generate(itineraire, itineraire_arc)
    print(f"  -> {len(itineraire)} stop-time records | {len(itineraire_arc)} arcs | {len(courses)} courses")

    courses_export   = MEF_course(courses, normed['trip_id_coor'])
    itineraire_export    = MEF_iti(itineraire, courses)
    iti_arc_export   = MEF_iti_arc(itineraire_arc, courses)

    courses_export.to_csv(output_dir   / "C_1_Courses.csv",       **CSV_OPTS)
    itineraire_export.to_csv(output_dir    / "C_2_Itineraire.csv",    **CSV_OPTS)
    iti_arc_export.to_csv(output_dir   / "C_3_Itineraire_Arc.csv", **CSV_OPTS)

    # ------------------------------------------------------------------
    # 4. Lignes & sous-lignes (B_1 / B_2)
    # ------------------------------------------------------------------
    print("[5/7] Generating lignes and sous-lignes...")
    sous_ligne   = sl_generate(courses, AG, lignes)
    lignes_export = MEF_ligne(lignes, courses_export, AG)
    print(f"  -> {len(lignes_export)} lignes | {len(sous_ligne)} sous-lignes")

    lignes_export.to_csv(output_dir / "B_1_Lignes.csv",     **CSV_OPTS)
    sous_ligne.to_csv(output_dir    / "B_2_Sous_Lignes.csv", **CSV_OPTS)

    # ------------------------------------------------------------------
    # 5. Service dates (D_1 / D_2)
    # ------------------------------------------------------------------
    print("[6/7] Generating service dates and day-types...")
    Dates = build_dates_table(normed['calendar'], normed['calendar_dates'])
    service_dates, msg = service_date_generate(
        normed['calendar'], normed['calendar_dates'], Dates
    )
    print(f"  -> {msg}")

    service_jour_type = service_jour_type_generate(service_dates, courses, type_vac)
    print(f"  -> {len(service_dates)} service-date rows | {len(service_jour_type)} jour-type rows")

    MEF_serdate(service_dates, normed['ser_id_coor']).to_csv(
        output_dir / "D_1_Service_Dates.csv", **CSV_OPTS)
    MEF_servjour(service_jour_type, normed['route_id_coor'], normed['ser_id_coor'], type_vac).to_csv(
        output_dir / "D_2_Service_Jourtype.csv", **CSV_OPTS)

    # ------------------------------------------------------------------
    # 6. Passage counts & KCC (E_1 / E_4 / F_1 / F_2 / F_3 / F_4)
    # ------------------------------------------------------------------
    print("[7/7] Generating passage counts and KCC metrics...")

    # E_1 – passages par AG
    nb_psg_ag = nb_passage_ag(service_jour_type, itineraire_export, AG, type_vac)
    nb_psg_ag.to_csv(output_dir / "E_1_Nombre_Passage_AG.csv", **CSV_OPTS)

    # E_4 – passages par arc
    pnode = AG[['id_ag_num', 'stop_name', 'stop_lon', 'stop_lat']].rename(
        columns={'id_ag_num': 'NO', 'stop_name': 'NAME', 'stop_lon': 'LON', 'stop_lat': 'LAT'}
    )
    nb_psg_arc = passage_arc(iti_arc_export, service_jour_type, pnode, type_vac)
    nb_psg_arc.to_csv(output_dir / "E_4_Nombre_Passage_Arc.csv", **CSV_OPTS)

    # F_1 – nb courses par ligne
    nb_crs_ligne = nb_course_ligne(service_jour_type, courses_export, type_vac, lignes_export)
    nb_crs_ligne.to_csv(output_dir / "F_1_Nombre_Courses_Lignes.csv", **CSV_OPTS)

    # F_2 – caractéristiques par sous-ligne (headway / périodes)
    caract_sl = caract_par_sl(
        service_jour_type, courses_export,
        DEFAULT_HPM, DEFAULT_HPS,
        type_vac, sous_ligne
    )
    caract_sl.to_csv(output_dir / "F_2_Caract_SousLignes.csv", **CSV_OPTS)

    # F_3 / F_4 – KCC lignes & sous-lignes
    # Dist_shape requiert QGIS pour calculer la longueur réelle des tracés ;
    # en mode standalone on utilise toujours DIST_Vol_Oiseau (has_shp=False).
    kcc_ligne = kcc_course_ligne(service_jour_type, courses_export, type_vac, lignes_export, False)
    kcc_ligne.to_csv(output_dir / "F_3_KCC_Lignes.csv", **CSV_OPTS)

    kcc_sl = kcc_course_sl(service_jour_type, courses_export, type_vac, sous_ligne, False)
    kcc_sl.to_csv(output_dir / "F_4_KCC_Sous_Ligne.csv", **CSV_OPTS)

    elapsed = time.time() - start_time
    print(f"\nDone. Processing completed in {elapsed:.2f} seconds.")
    print(f"Output files written to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
