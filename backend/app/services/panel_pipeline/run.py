"""Pipeline entry point. Plan 2 implements full body."""
from __future__ import annotations


def run_panel_pipeline(feed_id: str) -> None:
    """
    Process one PAN GTFS feed end-to-end.

    Plan 1 stub. Plan 2 implements:
      1. Load feed from R2 (or download from PAN if absent)
      2. Reuse gtfs_core: rawgtfs_from_zip, gtfs_normalize, ligne_generate,
         service_date_generate, service_jour_type_generate
      3. Compute 38 indicators via indicators.* modules
      4. Run quality.compute_quality()
      5. Persist to panel_indicators + panel_quality
      6. Trigger aggregator.recompute_derived(network_id)
    """
    raise NotImplementedError("Implemented in Plan 2 Task 1")
