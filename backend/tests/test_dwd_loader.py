"""Tests for dwd_loader.load_outputs_to_dwd (Task 20b).

Uses minimal CSV fixtures created in tmp_path — no full pipeline run needed.
"""
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from app.services.dwd_loader import load_outputs_to_dwd

PROJECT_ID = "proj-dwd-test"

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, df: pd.DataFrame) -> None:
    """Write a semicolon-separated UTF-8-BOM CSV (matches pipeline CSV_OPTS)."""
    df.to_csv(path, sep=";", encoding="utf-8-sig", index=False)


def _make_wide_csv(out_dir: Path, filename: str, id_cols: list[str],
                   n_rows: int = 2, day_cols: list[str] | None = None) -> int:
    """Create a wide-format pivot CSV with day-type columns '1','2','3'."""
    if day_cols is None:
        day_cols = ["1", "2", "3"]
    data: dict = {col: [f"val_{i}" for i in range(n_rows)] for col in id_cols}
    data.update({dc: [float(i + 1) for i in range(n_rows)] for dc in day_cols})
    df = pd.DataFrame(data)
    _write_csv(out_dir / filename, df)
    return n_rows


def _make_direct_csv(out_dir: Path, filename: str, cols: list[str],
                     n_rows: int = 3) -> int:
    """Create a simple (non-pivot) CSV with n_rows rows."""
    data = {col: [f"{col}_{i}" for i in range(n_rows)] for col in cols}
    df = pd.DataFrame(data)
    _write_csv(out_dir / filename, df)
    return n_rows


@pytest.fixture()
def output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory populated with all 14 minimal CSVs."""
    d = tmp_path / "output"
    d.mkdir()

    # A_* (direct)
    _make_direct_csv(d, "A_1_Arrets_Generiques.csv",
                     ["id_ag_num", "stop_name", "stop_lat", "stop_lon"], n_rows=3)
    _make_direct_csv(d, "A_2_Arrets_Physiques.csv",
                     ["id_ap_num", "stop_lat", "stop_lon"])
    # B_* (direct)
    _make_direct_csv(d, "B_1_Lignes.csv",
                     ["id_ligne_num", "route_short_name", "route_long_name"])
    _make_direct_csv(d, "B_2_Sous_Lignes.csv",
                     ["sous_ligne", "id_ligne_num", "route_short_name"])
    # C_* (direct)
    _make_direct_csv(d, "C_1_Courses.csv",
                     ["id_course_num", "id_ligne_num", "sous_ligne"])
    _make_direct_csv(d, "C_2_Itineraire.csv",
                     ["id_course_num", "ordre", "id_ag_num"])
    _make_direct_csv(d, "C_3_Itineraire_Arc.csv",
                     ["id_course_num", "ordre_a", "ordre_b"])
    # D_* (direct)
    _make_direct_csv(d, "D_1_Service_Dates.csv",
                     ["id_service_num", "Date_GTFS", "Type_Jour"])
    _make_direct_csv(d, "D_2_Service_Jourtype.csv",
                     ["id_ligne_num", "id_service_num", "Type_Jour"])
    # E_* (pivot — wide format)
    _make_wide_csv(d, "E_1_Nombre_Passage_AG.csv",
                   ["id_ag_num", "stop_name", "stop_lat", "stop_lon"])
    _make_wide_csv(d, "E_4_Nombre_Passage_Arc.csv",
                   ["id_ag_num_a", "id_ag_num_b", "lat_a", "lon_a"])
    # F_* (F_2 direct, others pivot)
    _make_wide_csv(d, "F_1_Nombre_Courses_Lignes.csv",
                   ["id_ligne_num", "route_short_name", "route_long_name"])
    _make_direct_csv(d, "F_2_Caract_SousLignes.csv",
                     ["sous_ligne", "id_ligne_num", "Type_Jour", "Nb_courses"])
    _make_wide_csv(d, "F_3_KCC_Lignes.csv",
                   ["id_ligne_num", "route_short_name", "route_long_name"])
    _make_wide_csv(d, "F_4_KCC_Sous_Ligne.csv",
                   ["sous_ligne", "id_ligne_num", "route_short_name", "route_long_name"])

    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_load_creates_sqlite(output_dir: Path) -> None:
    """SQLite file is created at the expected path."""
    result = load_outputs_to_dwd(PROJECT_ID, output_dir)

    assert result == output_dir / f"{PROJECT_ID}_query.sqlite"
    assert result.exists()


def test_all_15_tables_loaded(output_dir: Path) -> None:
    """SQLite contains exactly 15 tables (one per CSV: 9 direct + 6 E_*/F_*)."""
    sqlite_path = load_outputs_to_dwd(PROJECT_ID, output_dir)

    with sqlite3.connect(sqlite_path) as con:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert len(tables) == 15


def test_e1_melted_schema(output_dir: Path) -> None:
    """passage_ag table has jour_type + nb_passages columns; no digit column names."""
    sqlite_path = load_outputs_to_dwd(PROJECT_ID, output_dir)

    with sqlite3.connect(sqlite_path) as con:
        df = pd.read_sql("SELECT * FROM passage_ag LIMIT 1", con)

    assert "jour_type" in df.columns
    assert "nb_passages" in df.columns
    # No raw digit-named pivot columns should remain
    digit_cols = [c for c in df.columns if str(c).isdigit()]
    assert digit_cols == [], f"Unexpected pivot columns: {digit_cols}"


def test_f3_melted_schema(output_dir: Path) -> None:
    """kcc_lignes table has jour_type + kcc_km columns."""
    sqlite_path = load_outputs_to_dwd(PROJECT_ID, output_dir)

    with sqlite3.connect(sqlite_path) as con:
        df = pd.read_sql("SELECT * FROM kcc_lignes LIMIT 1", con)

    assert "jour_type" in df.columns
    assert "kcc_km" in df.columns


def test_a1_row_count_matches_csv(output_dir: Path) -> None:
    """arrets_generiques row count equals the source CSV row count (3)."""
    sqlite_path = load_outputs_to_dwd(PROJECT_ID, output_dir)

    source_rows = len(pd.read_csv(
        output_dir / "A_1_Arrets_Generiques.csv", sep=";", encoding="utf-8-sig"
    ))

    with sqlite3.connect(sqlite_path) as con:
        (db_rows,) = con.execute("SELECT COUNT(*) FROM arrets_generiques").fetchone()

    assert db_rows == source_rows == 3


def test_idempotent_reload(output_dir: Path) -> None:
    """Running load_outputs_to_dwd twice does not double the row count."""
    load_outputs_to_dwd(PROJECT_ID, output_dir)
    sqlite_path = load_outputs_to_dwd(PROJECT_ID, output_dir)

    # passage_ag: 2 id-rows × 3 day cols = 6 melted rows
    with sqlite3.connect(sqlite_path) as con:
        (count_after_two,) = con.execute(
            "SELECT COUNT(*) FROM passage_ag"
        ).fetchone()

    # Expected: 2 rows × 3 day-type cols = 6 (not 12)
    assert count_after_two == 6
