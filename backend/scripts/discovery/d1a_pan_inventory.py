"""
D1a — PAN dataset inventory + history depth scan.

compare-transit.fr discovery script. Adapted from prior PAN exploration
work (`C:/Users/wei.si/Projets/GTFS/verify_transport_gouv_api.py`). The API
endpoints and dedup-by-feed_start_date strategy were validated end-to-end
in 2026-04 against the 463-dataset PAN catalog.

Usage:
    python d1a_pan_inventory.py             # all 3 steps (A, B, C)
    python d1a_pan_inventory.py a           # enumeration only
    python d1a_pan_inventory.py a b         # enumeration + history depth
    python d1a_pan_inventory.py b           # history depth (reuses cached A)
    python d1a_pan_inventory.py c           # cellar download benchmark

Output: backend/storage/discovery/d1_pan/
    - datasets_gtfs_inventory.csv
    - history_depth_by_dataset.csv
    - cellar_sampling_results.csv
"""
from __future__ import annotations

import csv
import io
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

BASE = "https://transport.data.gouv.fr"
UA = "compare-transit-discovery/0.1 (siwei.mtg@gmail.com)"
OUT = Path(__file__).resolve().parents[2] / "storage" / "discovery" / "d1_pan"
OUT.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers["User-Agent"] = UA


def step_a_enumerate_gtfs_datasets():
    r = session.get(f"{BASE}/api/datasets", timeout=120)
    r.raise_for_status()
    datasets = r.json()

    rows = []
    for d in datasets:
        if d.get("type") != "public-transit":
            continue
        gtfs_resources = [
            res for res in (d.get("resources") or [])
            if (res.get("format") or "").upper() == "GTFS"
        ]
        if not gtfs_resources:
            continue
        covered = d.get("covered_area") or {}
        publisher = d.get("publisher") or {}
        rows.append({
            "id": d.get("id"),
            "slug": d.get("slug"),
            "datagouv_id": d.get("datagouv_id"),
            "title": d.get("title"),
            "publisher": publisher.get("name") if isinstance(publisher, dict) else str(publisher),
            "covered_area_name": covered.get("name") if isinstance(covered, dict) else None,
            "covered_area_type": covered.get("type") if isinstance(covered, dict) else None,
            "licence": d.get("licence"),
            "n_gtfs_resources": len(gtfs_resources),
            "gtfs_resource_ids": ",".join(str(res.get("id")) for res in gtfs_resources),
            "page_url": d.get("page_url"),
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "datasets_gtfs_inventory.csv", index=False, encoding="utf-8")
    print(f"[A] {len(df)} GTFS public-transit datasets (from {len(datasets)} total)")
    return df


def _resolve_short_id(datagouv_id):
    """Call /api/datasets/<ObjectId> and extract payload.dataset_id from first history entry."""
    try:
        r = session.get(f"{BASE}/api/datasets/{datagouv_id}", timeout=60)
        if r.status_code != 200:
            return None, f"API {r.status_code}"
        j = r.json()
        history = j.get("history") or []
        if not history:
            return None, "no_history"
        short_id = (history[0].get("payload") or {}).get("dataset_id")
        if not short_id:
            return None, "no_dataset_id_in_payload"
        return int(short_id), None
    except Exception as e:
        return None, f"api_err:{str(e)[:100]}"


def _scan_one_history(datagouv_id, slug):
    short_id, err = _resolve_short_id(datagouv_id)
    if short_id is None:
        return {"datagouv_id": datagouv_id, "short_id": None, "slug": slug,
                "n_rows": 0, "oldest": None, "newest": None,
                "median_gap_days": None, "total_bytes_csv": 0, "error": err}
    url = f"{BASE}/datasets/{short_id}/resources_history_csv"
    try:
        r = session.get(url, timeout=180, stream=True)
        if r.status_code != 200:
            return {"datagouv_id": datagouv_id, "short_id": short_id, "slug": slug,
                    "n_rows": 0, "oldest": None, "newest": None,
                    "median_gap_days": None, "total_bytes_csv": 0,
                    "error": f"CSV HTTP {r.status_code}"}
        buf = io.StringIO()
        size = 0
        for chunk in r.iter_content(chunk_size=65536, decode_unicode=True):
            if chunk:
                buf.write(chunk)
                size += len(chunk)
        buf.seek(0)
        reader = csv.DictReader(buf)
        timestamps = []
        n = 0
        for rec in reader:
            n += 1
            ts = rec.get("inserted_at")
            if ts:
                timestamps.append(ts)
        if n == 0:
            return {"datagouv_id": datagouv_id, "short_id": short_id, "slug": slug,
                    "n_rows": 0, "oldest": None, "newest": None,
                    "median_gap_days": None, "total_bytes_csv": size, "error": "empty_csv"}
        parsed = pd.to_datetime(pd.Series(timestamps), utc=True, errors="coerce").dropna()
        if parsed.empty:
            return {"datagouv_id": datagouv_id, "short_id": short_id, "slug": slug,
                    "n_rows": n, "oldest": None, "newest": None,
                    "median_gap_days": None, "total_bytes_csv": size, "error": "no_valid_ts"}
        parsed = parsed.sort_values().reset_index(drop=True)
        gaps = parsed.diff().dropna().dt.total_seconds() / 86400.0
        return {
            "datagouv_id": datagouv_id, "short_id": short_id, "slug": slug,
            "n_rows": n,
            "oldest": parsed.iloc[0].isoformat(),
            "newest": parsed.iloc[-1].isoformat(),
            "median_gap_days": float(gaps.median()) if len(gaps) else None,
            "total_bytes_csv": size, "error": None,
        }
    except Exception as e:
        return {"datagouv_id": datagouv_id, "short_id": short_id, "slug": slug,
                "n_rows": 0, "oldest": None, "newest": None,
                "median_gap_days": None, "total_bytes_csv": 0, "error": str(e)[:200]}


def step_b_history_depth(df_inventory, concurrency=4):
    tasks = [(row["id"], row["slug"]) for _, row in df_inventory.iterrows()]
    rows = []
    n_total = len(tasks)
    done = 0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(_scan_one_history, dg_id, slug): (dg_id, slug) for dg_id, slug in tasks}
        for f in as_completed(futures):
            rows.append(f.result())
            done += 1
            if done % 25 == 0 or done == n_total:
                print(f"[B] {done}/{n_total} scanned")
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "history_depth_by_dataset.csv", index=False, encoding="utf-8")
    total_rows = int(df["n_rows"].sum())
    non_empty = df[df["n_rows"] > 0]
    print(f"[B] {len(df)} datasets, {total_rows} total history rows, {len(non_empty)} non-empty")
    if len(non_empty):
        print(f"[B] n_rows p10/p50/p90: "
              f"{int(non_empty['n_rows'].quantile(0.1))}/"
              f"{int(non_empty['n_rows'].quantile(0.5))}/"
              f"{int(non_empty['n_rows'].quantile(0.9))}")
    return df


def step_c_cellar_sampling(df_depth, n_sample=50, concurrency=8):
    """df_depth: output of step B, must contain short_id and n_rows."""
    df_have = df_depth[(df_depth["n_rows"] > 0) & df_depth["short_id"].notna()]
    sample_urls = []
    candidates = df_have.sample(min(n_sample * 3, len(df_have)), random_state=42)
    for _, row in candidates.iterrows():
        short_id = int(row["short_id"])
        url = f"{BASE}/datasets/{short_id}/resources_history_csv"
        try:
            r = session.get(url, timeout=30)
            if r.status_code != 200:
                continue
            reader = csv.DictReader(io.StringIO(r.text))
            recs = [rec for rec in reader if rec.get("permanent_url", "").startswith("http")]
            if not recs:
                continue
            sample_urls.append(random.choice(recs)["permanent_url"])
        except Exception:
            continue
        if len(sample_urls) >= n_sample:
            break

    print(f"[C] sampling {len(sample_urls)} URLs at concurrency={concurrency}")

    def fetch(url):
        t0 = time.time()
        try:
            r = session.get(url, timeout=120, stream=True)
            size = 0
            for chunk in r.iter_content(chunk_size=65536):
                size += len(chunk)
            elapsed = time.time() - t0
            return {
                "url": url, "status": r.status_code,
                "elapsed_s": round(elapsed, 3), "bytes": size,
                "mbps": round(size / 1_000_000 / elapsed, 3) if elapsed > 0 else None,
                "retry_after": r.headers.get("retry-after"),
                "x_amz_request_id": r.headers.get("x-amz-request-id"),
                "server": r.headers.get("server"),
                "content_type": r.headers.get("content-type"),
                "error": None,
            }
        except Exception as e:
            return {"url": url, "status": None,
                    "elapsed_s": round(time.time() - t0, 3), "bytes": 0,
                    "mbps": None, "retry_after": None, "x_amz_request_id": None,
                    "server": None, "content_type": None, "error": str(e)[:200]}

    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(fetch, u) for u in sample_urls]
        for f in as_completed(futures):
            results.append(f.result())

    df = pd.DataFrame(results)
    df.to_csv(OUT / "cellar_sampling_results.csv", index=False, encoding="utf-8")

    ok = df[df["status"] == 200]
    n_fail = len(df) - len(ok)
    n_429 = int((df["status"] == 429).sum())
    n_5xx = int(df["status"].between(500, 599, inclusive="both").sum())
    print(f"[C] {len(df)} requests | {len(ok)} ok | {n_fail} fail ({n_429}x429, {n_5xx}x5xx)")
    if len(ok):
        print(f"[C] mbps mean/median: {ok['mbps'].mean():.2f} / {ok['mbps'].median():.2f}")
        print(f"[C] bytes mean/p50/p90: "
              f"{int(ok['bytes'].mean())} / {int(ok['bytes'].quantile(0.5))} / "
              f"{int(ok['bytes'].quantile(0.9))}")
    return df


if __name__ == "__main__":
    steps = sys.argv[1:] or ["a", "b", "c"]
    inv = None
    depth = None
    if "a" in steps:
        print("=== Step A ===")
        inv = step_a_enumerate_gtfs_datasets()
    if "b" in steps or "c" in steps:
        if inv is None:
            inv = pd.read_csv(OUT / "datasets_gtfs_inventory.csv")
    if "b" in steps:
        print("=== Step B ===")
        depth = step_b_history_depth(inv)
    if "c" in steps:
        print("=== Step C ===")
        if depth is None:
            depth = pd.read_csv(OUT / "history_depth_by_dataset.csv")
        step_c_cellar_sampling(depth)
    print("Done.")
