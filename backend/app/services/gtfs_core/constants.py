"""
Constantes métier et algorithmiques de gtfs_core.
Toutes les valeurs sont listées dans CLAUDE.md §硬编码常量.
Ne pas modifier avant la V5.
"""

# ── Clustering spatial ──────────────────────────────────────────────────────

BIG_VOLUME_THRESHOLD: int = 5_000
"""Nombre de stops au-delà duquel le pipeline bascule de DBSCAN vers K-Means + hiérarchique."""

KMEANS_CHUNK_DIVISOR: int = 500
"""k = max(1, round(len(stops) / KMEANS_CHUNK_DIVISOR))"""

STOP_MERGE_RADIUS_METERS: float = 100.0
"""Distance maximale (m) pour fusionner deux stops dans le même arrêt générique (AG)."""

EARTH_RADIUS_METERS: float = 6_371_000.0
"""Rayon moyen de la Terre WGS-84 en mètres (conversion mètres ↔ radians)."""

# ── Périodes journalières ───────────────────────────────────────────────────

class Period:
    """Codes de période utilisés dans les calculs de fréquence (headway)."""
    EARLY_MORNING = 'FM'   # Avant HPM — faible trafic matinal
    PEAK_MORNING  = 'HPM'  # Heure de Pointe Matin
    OFF_PEAK      = 'HC'   # Heure Creuse
    PEAK_EVENING  = 'HPS'  # Heure de Pointe Soir
    LATE_EVENING  = 'FS'   # Fin de Service — faible trafic en soirée


ALL_PERIODS: list = [
    Period.EARLY_MORNING,
    Period.PEAK_MORNING,
    Period.OFF_PEAK,
    Period.PEAK_EVENING,
    Period.LATE_EVENING,
]

# ── Valeurs GTFS par défaut ─────────────────────────────────────────────────

MISSING_ROUTE_TYPE: int = 3
"""route_type par défaut quand le flux GTFS l'omet (3 = bus, spec GTFS §1.3)."""

MISSING_DIRECTION_ID: int = 999
"""direction_id placeholder quand le flux GTFS l'omet."""

# ── I/O ─────────────────────────────────────────────────────────────────────

ENCODING_SAMPLE_BYTES: int = 10_000
"""Nombre d'octets transmis à chardet pour la détection d'encodage."""
