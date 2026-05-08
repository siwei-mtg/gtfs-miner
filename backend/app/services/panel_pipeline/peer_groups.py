"""
Peer group tier loader + classification.

Spec §5.3. MVP uses static tier rules (yaml); V2 introduces PCA clustering.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).resolve().parent / "data"
PEER_GROUPS_YAML = DATA_DIR / "peer_groups.yaml"
TIER_OVERRIDES_YAML = DATA_DIR / "network_tier_overrides.yaml"


@lru_cache(maxsize=1)
def load_peer_groups() -> dict[str, dict[str, Any]]:
    """Read peer_groups.yaml; cached after first call."""
    raw = yaml.safe_load(PEER_GROUPS_YAML.read_text(encoding="utf-8"))
    return raw["tiers"]


def classify_tier(
    *,
    population: int,
    has_metro: bool,
    dominant_mode: str,
    cross_commune: bool,
) -> str:
    """
    Map a network's properties to one of T1/T2/T3/T4/T5/R/I.

    Decision order (first match wins):
      1. R if dominant_mode is "train"
      2. I if cross_commune is True (and not regional rail)
      3. Population-based tiers T1–T5; T1 requires has_metro AND pop >= 1M
    """
    if dominant_mode == "train":
        return "R"
    if cross_commune:
        return "I"
    if population >= 1_000_000 and has_metro:
        return "T1"
    if population >= 500_000:
        return "T2"
    if population >= 200_000:
        return "T3"
    if population >= 100_000:
        return "T4"
    return "T5"


def apply_tier_overrides(session, yaml_path: Path | None = None) -> int:
    """Apply tier overrides from network_tier_overrides.yaml to PanelNetwork rows.

    Spec §22.4 — head-network manual tier assignments. Only updates networks whose
    current tier differs from the YAML-mapped tier.

    Args:
        session: SQLAlchemy session.
        yaml_path: optional override; defaults to bundled
            ``data/network_tier_overrides.yaml``.

    Returns:
        Number of PanelNetwork rows whose tier was changed.
    """
    # Lazy import to avoid pulling in the ORM at module load
    from app.db.models import PanelNetwork

    path = yaml_path if yaml_path is not None else TIER_OVERRIDES_YAML
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    n_updated = 0
    for tier, slugs in cfg.items():
        for slug in slugs or []:
            n = session.query(PanelNetwork).filter_by(slug=slug).one_or_none()
            if n is not None and n.tier != tier:
                n.tier = tier
                n_updated += 1
    session.commit()
    return n_updated
