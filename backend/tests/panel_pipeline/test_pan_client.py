"""Spec §6.1 PAN integration — covered by httpx mock to avoid live PAN calls."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.services.panel_pipeline.pan_client import (
    PANClient,
    PANDataset,
)


@pytest.fixture()
def fake_dataset_response() -> dict:
    return {
        "id": "abc-123",
        "slug": "lyon-tcl",
        "title": "Métropole de Lyon — TCL",
        "type": "public-transit",
        "resources": [
            {
                "id": "r1",
                "format": "GTFS",
                "url": "https://example/r1.zip",
                "modified": "2024-01-01T00:00:00Z",
            }
        ],
        "history": [
            {
                "id": "r0",
                "url": "https://example/r0.zip",
                "inserted_at": "2023-06-01T00:00:00Z",
            }
        ],
    }


def test_fetch_dataset_parses_resources(fake_dataset_response):
    client = PANClient()
    with patch.object(client, "_get", return_value=fake_dataset_response):
        ds: PANDataset = client.fetch_dataset("lyon-tcl")
    assert ds.slug == "lyon-tcl"
    assert len(ds.all_resources) == 2
    assert any(r.is_history for r in ds.all_resources)


def test_resource_dataclass_normalizes_dates(fake_dataset_response):
    client = PANClient()
    with patch.object(client, "_get", return_value=fake_dataset_response):
        ds = client.fetch_dataset("lyon-tcl")
    current = next(r for r in ds.all_resources if not r.is_history)
    assert current.published_at.year == 2024


def test_resolve_short_id():
    """Spec §6.1: history[0].payload.dataset_id holds the integer short ID."""
    client = PANClient()
    fake = {
        "id": "abc-123",
        "history": [{"payload": {"dataset_id": "999"}}],
    }
    with patch.object(client, "_get", return_value=fake):
        assert client.resolve_short_id("abc-123") == 999

    with patch.object(client, "_get", return_value={"id": "abc-123", "history": []}):
        assert client.resolve_short_id("abc-123") is None


def test_fetch_history_csv_parses_payload():
    """Spec §6.1 dedup workflow: resources_history_csv parsing."""
    payload = {
        "permanent_url": "https://example/feed1.zip",
        "total_compressed_size": 102400,
        "zip_metadata": [
            {"file_name": "feed_info.txt", "sha256": "deadbeef" * 8},
            {"file_name": "routes.txt", "sha256": "00ff" * 16},
        ],
    }
    csv_text = (
        "resource_history_id,resource_id,permanent_url,inserted_at,payload\n"
        + 'rh1,r1,https://example/feed1.zip,2024-01-01T00:00:00Z,'
        + '"' + json.dumps(payload).replace('"', '""') + '"' + "\n"
    )

    class FakeResp:
        text = csv_text

        def raise_for_status(self):
            return None

    client = PANClient()
    with patch.object(client._client, "get", return_value=FakeResp()):
        rows = client.fetch_history_csv(short_id=999)
    assert len(rows) == 1
    assert rows[0]["resource_history_id"] == "rh1"
    assert rows[0]["payload"]["zip_metadata"][0]["file_name"] == "feed_info.txt"


def test_list_datasets_filters_public_transit():
    client = PANClient()
    fake_list = [
        {"id": "1", "type": "public-transit", "title": "Net1"},
        {"id": "2", "type": "other", "title": "NotTransit"},
        {"id": "3", "type": "public-transit", "title": "Net2"},
    ]
    with patch.object(client, "_get", return_value=fake_list):
        datasets = client.list_datasets()
    assert len(datasets) == 2
    assert {d["title"] for d in datasets} == {"Net1", "Net2"}
