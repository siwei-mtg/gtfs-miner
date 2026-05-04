"""
test_result_api.py — Tests for Task 19: GET /{project_id}/tables/{table_name}

Fixtures: isolated_client_authed (function-scoped, in-memory DB, auth bypassed)
          result_data           (module-scoped, seeds/cleans up test rows)

The fake_user injected by isolated_client_authed has tenant_id="test-tenant-id".
"""
import pytest
from sqlalchemy.orm import sessionmaker

import app.db.result_models  # noqa: F401 — registers result table models with Base
from app.db.models import Project
from app.db.result_models import (
    ResultA1ArretGenerique,
    ResultB1Ligne,
    ResultC2Itineraire,
    ResultF1CourseLigne,
)

# ── Test constants ──────────────────────────────────────────────────────────
PROJECT_ID = "proj-t19"
OTHER_PROJECT_ID = "proj-t19-other"
BASE_URL = f"/api/v1/projects/{PROJECT_ID}/tables"


# ── Module-scoped seed fixture ───────────────────────────────────────────────

@pytest.fixture(scope="module")
def result_data(test_engine):
    """Seed test project + 5 ResultA1 rows; clean up after module."""
    Session = sessionmaker(bind=test_engine)
    session = Session()

    project = Project(id=PROJECT_ID, status="completed", tenant_id="test-tenant-id")
    other_project = Project(id=OTHER_PROJECT_ID, status="completed", tenant_id="other-tenant-id")
    session.add_all([project, other_project])

    rows = [
        ResultA1ArretGenerique(
            project_id=PROJECT_ID,
            id_ag=f"AG00{i}",
            stop_name=f"Stop {chr(64 + i)}",  # Stop A … Stop E
            stop_lat=48.80 + i * 0.01,
            stop_lon=2.30 + i * 0.01,
            id_ag_num=i,
        )
        for i in range(1, 6)
    ]
    session.add_all(rows)

    # B_1 rows for Task 38A enum-filter tests.  route_type values: 3, 3, 0
    # so filter_values="3" returns 2 rows, filter_values="3,0" returns 3 rows.
    session.add_all([
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=1, route_short_name="L1", route_type=3),
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=2, route_short_name="L2", route_type=3),
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=3, route_short_name="T3", route_type=0),
    ])

    # F_1 rows for Task 38A range-filter tests.
    # nb_course values: 10, 25, 50, 80, 150 (single type_jour=1 for simplicity).
    session.add_all([
        ResultF1CourseLigne(project_id=PROJECT_ID, id_ligne_num=i, route_short_name=f"L{i}",
                             type_jour=1, nb_course=v)
        for i, v in enumerate([10.0, 25.0, 50.0, 80.0, 150.0], start=1)
    ])

    # C_2 rows — line × stop bridge used by /resolve to cross-derive ag_ids
    # from a line filter (and ligne_ids from a stop filter).
    #   Ligne 1 serves AGs {1, 2, 3}
    #   Ligne 2 serves AGs {2, 3}
    #   Ligne 3 serves AGs {4, 5}
    session.add_all([
        ResultC2Itineraire(project_id=PROJECT_ID, id_ligne_num=1, id_ag_num=1, ordre=1),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ligne_num=1, id_ag_num=2, ordre=2),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ligne_num=1, id_ag_num=3, ordre=3),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ligne_num=2, id_ag_num=2, ordre=1),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ligne_num=2, id_ag_num=3, ordre=2),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ligne_num=3, id_ag_num=4, ordre=1),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ligne_num=3, id_ag_num=5, ordre=2),
    ])

    session.commit()
    session.close()

    yield

    session = Session()
    for model in (ResultF1CourseLigne, ResultC2Itineraire, ResultB1Ligne, ResultA1ArretGenerique):
        session.query(model).filter(model.project_id == PROJECT_ID).delete(synchronize_session=False)
    session.query(Project).filter(
        Project.id.in_([PROJECT_ID, OTHER_PROJECT_ID])
    ).delete(synchronize_session=False)
    session.commit()
    session.close()


# ── Tests ────────────────────────────────────────────────────────────────────

def test_get_table_a1_paginated(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/a1")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert len(body["rows"]) == 5
    assert "id" not in body["columns"]
    assert "project_id" not in body["columns"]
    assert "stop_name" in body["columns"]
    for row in body["rows"]:
        assert "id" not in row
        assert "project_id" not in row


def test_get_table_unknown(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/zzz")
    assert r.status_code == 404


def test_get_table_wrong_project(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"/api/v1/projects/{OTHER_PROJECT_ID}/tables/a1")
    assert r.status_code == 404


def test_sort_by_column(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/a1?sort_by=stop_name&sort_order=desc")
    assert r.status_code == 200
    names = [row["stop_name"] for row in r.json()["rows"]]
    assert names == sorted(names, reverse=True)


def test_text_search(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/a1?q=Stop+A")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) >= 1
    for row in rows:
        assert "Stop A" in row["stop_name"]


def test_limit_max_200(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/a1?limit=500")
    assert r.status_code == 200
    assert len(r.json()["rows"]) <= 200


def test_total_count_correct(isolated_client_authed, result_data, test_db):
    r = isolated_client_authed.get(f"{BASE_URL}/a1")
    assert r.status_code == 200
    expected = test_db.query(ResultA1ArretGenerique).filter(
        ResultA1ArretGenerique.project_id == PROJECT_ID
    ).count()
    assert r.json()["total"] == expected


# ── Task 20: single-table CSV download ──────────────────────────────────────

DOWNLOAD_URL = f"/api/v1/projects/{PROJECT_ID}/tables/a1/download"


def test_single_table_csv_download(isolated_client_authed, result_data):
    r = isolated_client_authed.get(DOWNLOAD_URL)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    # UTF-8 BOM: first 3 bytes must be EF BB BF
    assert r.content[:3] == b"\xef\xbb\xbf"
    # semicolon-delimited: header line contains ";"
    first_line = r.content.decode("utf-8-sig").splitlines()[0]
    assert ";" in first_line


def test_single_table_csv_columns(isolated_client_authed, result_data):
    r = isolated_client_authed.get(DOWNLOAD_URL)
    assert r.status_code == 200
    first_line = r.content.decode("utf-8-sig").splitlines()[0]
    csv_cols = first_line.split(";")
    # internal fields must not appear
    assert "id" not in csv_cols
    assert "project_id" not in csv_cols
    # domain columns must be present
    for col in ("id_ag", "stop_name", "stop_lat", "stop_lon", "id_ag_num"):
        assert col in csv_cols


# ── Task 38A: enum multi-select + numeric range filters ─────────────────────

def test_filter_values_single_value(isolated_client_authed, result_data):
    """filter_field=route_type&filter_values=3 returns only the matching rows."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1?filter_field=route_type&filter_values=3"
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 2
    assert all(row["route_type"] == 3 for row in rows)


def test_filter_values_csv_list(isolated_client_authed, result_data):
    """filter_values accepts a comma-separated list — SQL IN (...) semantics."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1?filter_field=route_type&filter_values=3,0"
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 3
    assert all(row["route_type"] in (3, 0) for row in rows)


def test_range_filter(isolated_client_authed, result_data):
    """range_min / range_max clip rows to [min, max] inclusive."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/f1?range_field=nb_course&range_min=20&range_max=100"
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    # Fixture values 10, 25, 50, 80, 150 → inside [20, 100] = 25, 50, 80
    assert {row["nb_course"] for row in rows} == {25.0, 50.0, 80.0}


def test_range_filter_min_only(isolated_client_authed, result_data):
    """Supplying only range_min applies a lower bound without an upper bound."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/f1?range_field=nb_course&range_min=50"
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert {row["nb_course"] for row in rows} == {50.0, 80.0, 150.0}


def test_invalid_filter_field_returns_400(isolated_client_authed, result_data):
    """Requesting filter_field=<unknown column> must error out with 400."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1?filter_field=nonexistent&filter_values=x"
    )
    assert r.status_code == 400


def test_invalid_range_field_returns_400(isolated_client_authed, result_data):
    """Requesting range_field=<unknown column> must error out with 400."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/f1?range_field=nonexistent&range_min=0"
    )
    assert r.status_code == 400


def test_internal_field_not_filterable(isolated_client_authed, result_data):
    """project_id / id must never be filterable via the public API (tenant leak)."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1?filter_field=project_id&filter_values={PROJECT_ID}"
    )
    assert r.status_code == 400


# ── Task 38B: generic per-column filter[<col>]=op:val ───────────────────────

def test_filter_in_via_bracket_syntax(isolated_client_authed, result_data):
    """filter[route_type]=in:3 returns the same rows as the legacy syntax."""
    r = isolated_client_authed.get(f"{BASE_URL}/b1?filter[route_type]=in:3")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 2
    assert all(row["route_type"] == 3 for row in rows)


def test_filter_in_csv_list_via_bracket(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/b1?filter[route_type]=in:3,0")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 3
    assert all(row["route_type"] in (3, 0) for row in rows)


def test_filter_range_open_lower(isolated_client_authed, result_data):
    """range:lo: (no upper bound) clips to col >= lo."""
    r = isolated_client_authed.get(f"{BASE_URL}/f1?filter[nb_course]=range:50:")
    assert r.status_code == 200
    assert {row["nb_course"] for row in r.json()["rows"]} == {50.0, 80.0, 150.0}


def test_filter_range_open_upper(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/f1?filter[nb_course]=range::40")
    assert r.status_code == 200
    assert {row["nb_course"] for row in r.json()["rows"]} == {10.0, 25.0}


def test_range_filter_on_integer_column_does_not_400(isolated_client_authed, result_data):
    # Regression: id_ligne_num is Integer; the URL parser produces float bounds
    # (1.0 / 2.0).  Coercing back through int(str(1.0)) used to raise
    # ValueError("invalid literal for int() with base 10: '1.0'").
    r = isolated_client_authed.get(f"{BASE_URL}/b1?filter[id_ligne_num]=range:1:2")
    assert r.status_code == 200
    assert {row["id_ligne_num"] for row in r.json()["rows"]} == {1, 2}


# ── Phase 2: /tables/{name}/resolve — pre-resolution for cross-pane sync ────


def test_resolve_endpoint_returns_distinct_canonical_ids(
    isolated_client_authed, result_data
):
    # B_1 fixture: (id_ligne_num=1, route_short_name=L1, route_type=3),
    #              (2, L2, 3), (3, T3, 0).  Filtering on a non-canonical column
    #              (route_short_name) must collapse to canonical ligne_ids /
    #              route_types of matching rows.  ag_ids derives from C_2:
    #              lignes 1+2 serve AGs {1, 2, 3}.
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1/resolve?filter[route_short_name]=in:L1,L2"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ligne_ids"] == [1, 2]
    assert body["route_types"] == ["3"]
    assert body["ag_ids"] == [1, 2, 3]


def test_resolve_endpoint_no_filters_returns_all(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/b1/resolve")
    assert r.status_code == 200
    body = r.json()
    assert body["ligne_ids"] == [1, 2, 3]
    assert body["route_types"] == ["0", "3"]
    # Union of AGs served by every line via C_2 = {1, 2, 3, 4, 5}.
    assert body["ag_ids"] == [1, 2, 3, 4, 5]


def test_resolve_endpoint_cross_table_ag_to_ligne(
    isolated_client_authed, result_data
):
    # Filter A_1 by stop_name → ag_ids comes from the source table directly,
    # ligne_ids is cross-derived from C_2 (which lines pass through that AG).
    # AG 2 is served by lignes 1 and 2; route_types of {1, 2} = {3}.
    r = isolated_client_authed.get(
        f"{BASE_URL}/a1/resolve?filter[stop_name]=in:Stop B"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ag_ids"] == [2]
    assert body["ligne_ids"] == [1, 2]
    assert body["route_types"] == ["3"]


def test_resolve_endpoint_404_for_unknown_table(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/zzz/resolve")
    assert r.status_code == 404


def test_resolve_endpoint_400_for_unknown_column(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/b1/resolve?filter[bogus]=in:x")
    assert r.status_code == 400


def test_resolve_endpoint_empty_when_table_lacks_canonical_columns(
    isolated_client_authed, result_data
):
    # D_1 has neither id_ligne_num nor id_ag_num nor route_type — every list
    # must be empty (no source projection, no C_2 derivation possible).
    r = isolated_client_authed.get(f"{BASE_URL}/d1/resolve")
    assert r.status_code == 200
    assert r.json() == {"ligne_ids": [], "route_types": [], "ag_ids": []}


def test_resolve_endpoint_wrong_project(isolated_client_authed, result_data):
    r = isolated_client_authed.get(
        f"/api/v1/projects/{OTHER_PROJECT_ID}/tables/b1/resolve"
    )
    assert r.status_code == 404


def test_filter_contains_case_insensitive(isolated_client_authed, result_data):
    """contains:<term> matches case-insensitively on a text column."""
    r = isolated_client_authed.get(f"{BASE_URL}/a1?filter[stop_name]=contains:STOP+a")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["stop_name"] == "Stop A"


def test_filter_contains_escapes_wildcards(isolated_client_authed, result_data):
    """A user typing ``%`` should match the literal char, not every row."""
    r = isolated_client_authed.get(f"{BASE_URL}/a1?filter[stop_name]=contains:%25")
    assert r.status_code == 200
    # No stop_name contains '%' literally → no rows.
    assert r.json()["rows"] == []


def test_filter_multi_columns_AND(isolated_client_authed, result_data):
    """Two filter[…] params combine with AND: only rows matching both."""
    # B1 fixture has 3 rows (route_type=3, 3, 0).  Stack a contains filter on
    # route_short_name to slice further.
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1?filter[route_type]=in:3&filter[route_short_name]=contains:L1"
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["route_short_name"] == "L1"
    assert rows[0]["route_type"] == 3


def test_filter_invalid_column_via_bracket_400(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/b1?filter[bogus]=in:x")
    assert r.status_code == 400


def test_filter_unknown_op_422(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/b1?filter[route_type]=lt:3")
    assert r.status_code == 422


def test_filter_internal_column_blocked_via_bracket(isolated_client_authed, result_data):
    """Tenant-leak guard: filter[project_id] must be rejected at the service."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1?filter[project_id]=in:{PROJECT_ID}"
    )
    assert r.status_code == 400


def test_column_meta_only_when_requested(isolated_client_authed, result_data):
    """column_meta absent by default to avoid the cardinality scan on every page."""
    r = isolated_client_authed.get(f"{BASE_URL}/b1")
    assert r.status_code == 200
    assert "column_meta" not in r.json()


def test_column_meta_classifies_columns(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/b1?column_meta=true")
    assert r.status_code == 200
    meta = r.json()["column_meta"]
    # B1 columns: id_ligne_num (int → numeric), route_short_name (3 distinct strings → enum),
    # route_type (int → numeric).
    assert meta["id_ligne_num"]["type"] == "numeric"
    assert meta["route_type"]["type"] == "numeric"
    assert meta["route_short_name"]["type"] == "enum"
    assert meta["route_short_name"]["total_distinct"] == 3


# ── Task 38B: distinct-values endpoint for the filter popover ───────────────

def test_distinct_returns_values_with_counts(isolated_client_authed, result_data):
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1/columns/route_type/distinct"
    )
    assert r.status_code == 200
    body = r.json()
    # B1 fixture: route_type=3 (×2), route_type=0 (×1).
    by_value = {entry["value"]: entry["count"] for entry in body["values"]}
    assert by_value == {3: 2, 0: 1}
    assert body["total_distinct"] == 2
    assert body["truncated"] is False


def test_distinct_q_filters_substring(isolated_client_authed, result_data):
    r = isolated_client_authed.get(
        f"{BASE_URL}/a1/columns/stop_name/distinct?q=Stop+A"
    )
    assert r.status_code == 200
    values = [v["value"] for v in r.json()["values"]]
    assert values == ["Stop A"]


def test_distinct_q_escapes_wildcards(isolated_client_authed, result_data):
    """``q='%'`` must match the literal char, not every row."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/a1/columns/stop_name/distinct?q=%25"
    )
    assert r.status_code == 200
    assert r.json()["values"] == []


def test_distinct_invalid_column_400(isolated_client_authed, result_data):
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1/columns/bogus/distinct"
    )
    assert r.status_code == 400


def test_distinct_internal_column_blocked(isolated_client_authed, result_data):
    """``project_id`` must not be reachable via the distinct API either."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1/columns/project_id/distinct"
    )
    assert r.status_code == 400


def test_distinct_truncated_flag(isolated_client_authed, result_data):
    """Limit lower than the row count flips ``truncated`` to True."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/a1/columns/stop_name/distinct?limit=2"
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["values"]) == 2
    assert body["truncated"] is True
    assert body["total_distinct"] == 5  # all 5 fixture stops
