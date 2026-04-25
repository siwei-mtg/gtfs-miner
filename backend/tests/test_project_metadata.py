import pandas as pd

from app.services.project_metadata import extract_reseau, extract_validite


class TestExtractReseau:
    def test_none_df(self):
        assert extract_reseau(None) is None

    def test_empty_df(self):
        assert extract_reseau(pd.DataFrame()) is None

    def test_missing_column(self):
        assert extract_reseau(pd.DataFrame({"agency_id": ["a"]})) is None

    def test_single_agency(self):
        df = pd.DataFrame({"agency_name": ["SEM"]})
        assert extract_reseau(df) == "SEM"

    def test_multiple_distinct(self):
        df = pd.DataFrame({"agency_name": ["SEM", "TAG", "TAM"]})
        assert extract_reseau(df) == "SEM / TAG / TAM"

    def test_deduplicates(self):
        df = pd.DataFrame({"agency_name": ["RATP", "SNCF", "RATP"]})
        assert extract_reseau(df) == "RATP / SNCF"

    def test_strips_whitespace(self):
        df = pd.DataFrame({"agency_name": ["  RATP ", "SNCF"]})
        assert extract_reseau(df) == "RATP / SNCF"

    def test_drops_empty_strings_and_na(self):
        df = pd.DataFrame({"agency_name": ["SEM", "", None, "   "]})
        assert extract_reseau(df) == "SEM"

    def test_all_empty_returns_none(self):
        df = pd.DataFrame({"agency_name": ["", None, "  "]})
        assert extract_reseau(df) is None

    def test_truncation(self):
        names = [f"Agence-{i:02d}" for i in range(50)]
        df = pd.DataFrame({"agency_name": names})
        result = extract_reseau(df, max_len=50)
        assert result is not None
        assert len(result) == 50
        assert result.endswith("…")


class TestExtractValidite:
    def test_none_df(self):
        assert extract_validite(None) == (None, None)

    def test_empty_df(self):
        assert extract_validite(pd.DataFrame()) == (None, None)

    def test_missing_column(self):
        assert extract_validite(pd.DataFrame({"other": [1, 2]})) == (None, None)

    def test_all_nan(self):
        df = pd.DataFrame({"Date_GTFS": [None, None]})
        assert extract_validite(df) == (None, None)

    def test_single_date(self):
        df = pd.DataFrame({"Date_GTFS": [20240704]})
        assert extract_validite(df) == (20240704, 20240704)

    def test_range(self):
        df = pd.DataFrame({"Date_GTFS": [20240704, 20241231, 20240901]})
        assert extract_validite(df) == (20240704, 20241231)

    def test_string_values_cast(self):
        df = pd.DataFrame({"Date_GTFS": ["20240704", "20241231"]})
        assert extract_validite(df) == (20240704, 20241231)

    def test_mixed_garbage_skipped(self):
        df = pd.DataFrame({"Date_GTFS": ["20240704", "not-a-date", 20241231]})
        assert extract_validite(df) == (20240704, 20241231)
