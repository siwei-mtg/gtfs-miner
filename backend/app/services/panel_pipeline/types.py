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
