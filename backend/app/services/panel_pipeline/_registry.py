"""Per-indicator metadata: unit, category, DSP priority, error-margin dependencies.

Spec §5.1 (38 indicators) + v0.2 §5.1 DSP priority annotations.

Used by `compute()`, `error_margin.propagate()`, and the panel API response builder
for audit-grade output. Reading this module is permitted inside `compute()` (it is
a versioned static mapping, not state — Plan 2 Assumption A3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Category = Literal[
    "productivity", "density", "structure", "coverage",
    "frequency", "accessibility", "quality", "environment",
]
DspPriority = Literal["P0", "P1", "P2"]


@dataclass(frozen=True, slots=True)
class IndicatorMeta:
    unit: str
    category: Category
    dsp_priority: DspPriority
    dq_dependencies: tuple[str, ...] = field(default_factory=tuple)


# All 6 dq_* indicators — used as default propagation set for direct-feed indicators.
ALL_DQ: tuple[str, ...] = (
    "dq_validator_errors", "dq_validator_warnings", "dq_field_completeness",
    "dq_coord_quality", "dq_route_type_completeness", "dq_freshness",
)


INDICATOR_REGISTRY: dict[str, IndicatorMeta] = {
    # A. Productivity (8)
    "prod_kcc_year":              IndicatorMeta("km", "productivity", "P0", ALL_DQ),
    "prod_courses_day_avg":       IndicatorMeta("trips/day", "productivity", "P1", ALL_DQ),
    "prod_peak_hour_courses":     IndicatorMeta("trips/h", "productivity", "P1", ALL_DQ),
    "prod_service_amplitude":     IndicatorMeta("h", "productivity", "P1", ("dq_field_completeness",)),
    "prod_lines_count":           IndicatorMeta("count", "productivity", "P0", ("dq_field_completeness",)),
    "prod_stops_count":           IndicatorMeta("count", "productivity", "P0", ("dq_field_completeness",)),
    "prod_network_length_km":     IndicatorMeta("km", "productivity", "P1", ("dq_coord_quality",)),
    "prod_peak_vehicles_needed":  IndicatorMeta("count", "productivity", "P0", ALL_DQ),
    # B. Density (4)
    "dens_stops_km2":             IndicatorMeta("stops/km2", "density", "P2", ("dq_field_completeness",)),
    "dens_lines_100k_pop":        IndicatorMeta("lines/100K", "density", "P1", ("dq_field_completeness",)),
    "dens_kcc_capita":            IndicatorMeta("km/capita", "density", "P1", ALL_DQ),
    "dens_kcc_km2":               IndicatorMeta("km/km2", "density", "P2", ALL_DQ),
    # C. Structure (7)
    "struct_modal_mix_bus":       IndicatorMeta("%", "structure", "P1", ("dq_route_type_completeness",)),
    "struct_modal_mix_tram":      IndicatorMeta("%", "structure", "P1", ("dq_route_type_completeness",)),
    "struct_modal_mix_metro":     IndicatorMeta("%", "structure", "P1", ("dq_route_type_completeness",)),
    "struct_modal_mix_train":     IndicatorMeta("%", "structure", "P1", ("dq_route_type_completeness",)),
    "struct_peak_amplification": IndicatorMeta("ratio", "structure", "P2", ALL_DQ),
    "struct_multi_route_stops_pct": IndicatorMeta("%", "structure", "P2", ("dq_field_completeness",)),
    "struct_route_directness":    IndicatorMeta("ratio", "structure", "P2", ("dq_coord_quality",)),
    # D. Coverage (6)
    "cov_pop_300m":               IndicatorMeta("%", "coverage", "P0", ("dq_coord_quality",)),
    "cov_pop_freq_300m":          IndicatorMeta("%", "coverage", "P0", ALL_DQ),
    "cov_surface_300m":           IndicatorMeta("%", "coverage", "P1", ("dq_coord_quality",)),
    "cov_median_walk":            IndicatorMeta("m", "coverage", "P1", ("dq_coord_quality",)),
    "cov_pop_weighted_walk":      IndicatorMeta("m", "coverage", "P1", ("dq_coord_quality",)),
    "cov_equity_gini":            IndicatorMeta("0-1", "coverage", "P2", ("dq_coord_quality",)),
    # E. Frequency & Speed (4)
    "freq_peak_headway_median":   IndicatorMeta("min", "frequency", "P1", ALL_DQ),
    "freq_high_freq_lines_pct":   IndicatorMeta("%", "frequency", "P1", ALL_DQ),
    "freq_daily_service_hours":   IndicatorMeta("h", "frequency", "P1", ALL_DQ),
    "freq_commercial_speed_kmh":  IndicatorMeta("km/h", "frequency", "P0", ALL_DQ),
    # F. Accessibility (2)
    "acc_wheelchair_stops_pct":   IndicatorMeta("%", "accessibility", "P1", ("dq_field_completeness",)),
    "acc_wheelchair_trips_pct":   IndicatorMeta("%", "accessibility", "P1", ("dq_field_completeness",)),
    # G. Data Quality (6) — self-referential; error_margin = 0 for these.
    "dq_validator_errors":        IndicatorMeta("count", "quality", "P1"),
    "dq_validator_warnings":      IndicatorMeta("count", "quality", "P1"),
    "dq_field_completeness":      IndicatorMeta("0-100", "quality", "P1"),
    "dq_coord_quality":           IndicatorMeta("%", "quality", "P1"),
    "dq_route_type_completeness": IndicatorMeta("%", "quality", "P1"),
    "dq_freshness":               IndicatorMeta("days", "quality", "P1"),
    # H. Environment (1)
    "env_co2_year_estimated":     IndicatorMeta("tCO2/year", "environment", "P2", ALL_DQ),
}

assert len(INDICATOR_REGISTRY) == 38, f"Registry count mismatch: {len(INDICATOR_REGISTRY)}"
