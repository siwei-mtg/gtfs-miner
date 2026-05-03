"""
PAN (transport.data.gouv.fr) API client.

Spec §6.1 / §6.4. Endpoints validated in D1 discovery (see
docs/superpowers/specs/2026-05-03-pan-history-discovery.md).

This client provides the runtime API surface for monthly cron + on-demand
fetching. The full **dedup-by-feed_start_date workflow** lives in
backend/scripts/discovery/d1b_dedup_per_network.py and will be promoted to
panel_pipeline/history_resolver.py in Plan 2.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

PAN_BASE = "https://transport.data.gouv.fr/api"
DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class PANResource:
    """A single GTFS resource (current or historical) from PAN."""
    pan_resource_id: str
    url: str
    published_at: datetime
    is_history: bool


@dataclass(frozen=True)
class PANDataset:
    """A PAN dataset (one network) with all current + historical resources."""
    pan_dataset_id: str
    slug: str
    title: str
    current_resources: list[PANResource] = field(default_factory=list)
    history_resources: list[PANResource] = field(default_factory=list)

    @property
    def all_resources(self) -> list[PANResource]:
        return [*self.current_resources, *self.history_resources]


def _parse_dt(s: str | None) -> datetime:
    if not s:
        return datetime.fromtimestamp(0)
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class PANClient:
    """Thin wrapper around the PAN public API."""

    def __init__(self, base_url: str = PAN_BASE, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def _get(self, path: str, **params: Any) -> dict:
        r = self._client.get(f"{self._base}{path}", params=params)
        r.raise_for_status()
        return r.json()

    def fetch_dataset(self, dataset_id: str) -> PANDataset:
        """Get one dataset by ID or slug, normalize resources + history."""
        data = self._get(f"/datasets/{dataset_id}")
        gtfs_only = lambda r: (r.get("format") or "").lower() in ("gtfs", "application/zip")
        current = [
            PANResource(
                pan_resource_id=str(r["id"]),
                url=r.get("url") or r.get("original_url") or "",
                published_at=_parse_dt(r.get("modified") or r.get("last_update")),
                is_history=False,
            )
            for r in data.get("resources", [])
            if gtfs_only(r)
        ]
        history = [
            PANResource(
                pan_resource_id=str(h["id"]),
                url=h.get("url") or h.get("original_url") or "",
                published_at=_parse_dt(h.get("inserted_at") or h.get("modified")),
                is_history=True,
            )
            for h in data.get("history", []) or data.get("resources_history", [])
        ]
        return PANDataset(
            pan_dataset_id=str(data["id"]),
            slug=data.get("slug", str(data["id"])),
            title=data.get("title", ""),
            current_resources=current,
            history_resources=history,
        )

    def list_datasets(self) -> list[dict]:
        """List all public-transit datasets. PAN /api/datasets returns all in one call (no pagination)."""
        data = self._get("/datasets")
        if isinstance(data, list):
            return [d for d in data if d.get("type") == "public-transit"]
        # Fallback for paginated form (defensive, current PAN doesn't paginate)
        items = data.get("data", []) if isinstance(data, dict) else []
        return [d for d in items if d.get("type") == "public-transit"]

    def download_resource(self, resource: PANResource, dest: Path) -> Path:
        """Stream-download a GTFS zip to dest. Idempotent if dest exists."""
        if dest.exists():
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._client.stream("GET", resource.url) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_bytes(chunk_size=64 * 1024):
                    f.write(chunk)
        return dest

    def resolve_short_id(self, datagouv_id: str) -> int | None:
        """
        Resolve a datagouv ObjectId-style ID to PAN short integer ID
        (needed for resources_history_csv endpoint).

        Spec §6.1: short_id is in `history[0].payload.dataset_id`.
        """
        data = self._get(f"/datasets/{datagouv_id}")
        history = data.get("history") or []
        if not history:
            return None
        short_id = (history[0].get("payload") or {}).get("dataset_id")
        return int(short_id) if short_id else None

    def fetch_history_csv(self, short_id: int) -> list[dict[str, Any]]:
        """
        Fetch the full resources_history_csv for a network.

        Returns list of dicts: {resource_history_id, resource_id, permanent_url,
                                inserted_at, payload (dict — incl. zip_metadata)}.

        Used for dedup-by-feed_start_date workflow (Plan 2 backfill).
        Note: this endpoint is NOT under /api — it's at /datasets/{id}/resources_history_csv.
        """
        import csv
        import io
        import json

        # Strip /api suffix from base since this endpoint is at the site root
        site_base = self._base[:-4] if self._base.endswith("/api") else self._base
        url = f"{site_base}/datasets/{short_id}/resources_history_csv"
        r = self._client.get(url, timeout=300.0)
        r.raise_for_status()
        rows: list[dict[str, Any]] = []
        for rec in csv.DictReader(io.StringIO(r.text)):
            try:
                payload = json.loads(rec.get("payload", "{}") or "{}")
            except json.JSONDecodeError:
                payload = {}
            rows.append({
                "resource_history_id": rec.get("resource_history_id"),
                "resource_id": rec.get("resource_id"),
                "permanent_url": rec.get("permanent_url") or payload.get("permanent_url"),
                "inserted_at": rec.get("inserted_at"),
                "payload": payload,
            })
        return rows

    def close(self) -> None:
        self._client.close()
