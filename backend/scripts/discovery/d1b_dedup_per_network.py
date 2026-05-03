"""
D1b — Generic GTFS history fetcher with feed_start_date dedup.

compare-transit.fr discovery script. Adapted from prior PAN exploration
work (`C:/Users/wei.si/Projets/GTFS/fetch_dataset_dedup.py`). Validates
spec §6.1 dedup-by-feed_start_date strategy on a single network.

Usage:
    python d1b_dedup_per_network.py --short-id 240 --name transilien
        [--steps fetch resolve dedup download]

Strategy:
1. Pull resources_history_csv for the given short_id.
2. Filter rows that contain feed_info.txt (= GTFS, not NeTEx/other).
3. Group by sha256(feed_info.txt). For each unique sha, fetch only feed_info.txt
   via HTTP Range (remotezip) and parse feed_start_date.
4. Map every GTFS row to its feed_start_date.
5. For each feed_start_date, keep the MOST RECENT zip (highest inserted_at).
6. Optionally download those deduped ZIPs.

Output: backend/storage/discovery/d1_pan/<name>_archive/
    - manifest_raw.parquet
    - sha_to_fsd.csv
    - manifest_dedup.parquet
    - zips/  (only if --steps download specified)
"""
import argparse
import csv
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from remotezip import RemoteZip

BASE = "https://transport.data.gouv.fr"
DISCOVERY_ROOT = Path(__file__).resolve().parents[2] / "storage" / "discovery" / "d1_pan"
csv.field_size_limit(10**7)


def _to_int(x, default=0):
    try:
        return int(x) if x not in (None, "", "null") else default
    except (TypeError, ValueError):
        return default


def _gtfs_signature(zm):
    """Pick the best 'feed-start' fingerprint file from a ZIP's metadata.

    Returns (source, sha256) where source is one of:
      - 'feed_info'      : feed_info.txt exists -> use its feed_start_date
      - 'calendar'       : fallback, parse min(start_date) of calendar.txt
      - 'calendar_dates' : last-resort, parse min(date) of calendar_dates.txt

    Returns (None, None) if the ZIP doesn't look like GTFS (no routes.txt).
    """
    files = {(zf.get("file_name") or "").lower(): zf for zf in zm}
    if "routes.txt" not in files:
        return None, None
    if "feed_info.txt" in files:
        return "feed_info", files["feed_info.txt"].get("sha256")
    if "calendar.txt" in files:
        return "calendar", files["calendar.txt"].get("sha256")
    if "calendar_dates.txt" in files:
        return "calendar_dates", files["calendar_dates.txt"].get("sha256")
    return None, None


def fetch_history_csv(short_id, out_dir):
    print(f"[1/6] Fetching resources_history_csv for short_id={short_id} ...")
    s = requests.Session()
    s.headers["User-Agent"] = "compare-transit-discovery/0.2"
    r = s.get(f"{BASE}/datasets/{short_id}/resources_history_csv", timeout=300)
    r.raise_for_status()
    rows = []
    for rec in csv.DictReader(io.StringIO(r.text)):
        try:
            pl = json.loads(rec["payload"])
        except Exception:
            continue
        zm = pl.get("zip_metadata") or []
        sig_source, sig_sha = _gtfs_signature(zm)
        rows.append({
            "rh_id": _to_int(rec.get("resource_history_id")),
            "resource_id": _to_int(rec.get("resource_id")),
            "permanent_url": rec.get("permanent_url") or pl.get("permanent_url"),
            "inserted_at": rec.get("inserted_at"),
            "filesize": _to_int(pl.get("total_compressed_size") or pl.get("filesize")),
            "sig_source": sig_source,
            "sig_sha": sig_sha,
        })
    df = pd.DataFrame(rows)
    df["inserted_at"] = pd.to_datetime(df["inserted_at"], utc=True, errors="coerce")
    df = df.sort_values("inserted_at").reset_index(drop=True)
    df.to_parquet(out_dir / "manifest_raw.parquet")
    src_counts = df["sig_source"].value_counts(dropna=False).to_dict()
    print(f"      {len(df)} rows | sig_source counts: {src_counts}")
    print(f"      unique sig sha: {df['sig_sha'].nunique()}")
    return df


def parse_feed_start_date(url, source):
    """source: 'feed_info' | 'calendar' | 'calendar_dates'"""
    target = {"feed_info": "feed_info.txt",
              "calendar": "calendar.txt",
              "calendar_dates": "calendar_dates.txt"}[source]
    try:
        with RemoteZip(url, support_suffix_range=False) as rz:
            # Match case-insensitively in case archive uses uppercase
            names = {n.lower(): n for n in rz.namelist()}
            real_name = names.get(target.lower())
            if real_name is None:
                return f"ERR:NoTarget"
            with rz.open(real_name) as f:
                content = f.read().decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(content))
        if source == "feed_info":
            for row in reader:
                v = row.get("feed_start_date")
                return v if v else None
            return None
        # calendar.txt -> min(start_date), calendar_dates.txt -> min(date)
        date_col = "start_date" if source == "calendar" else "date"
        dates = []
        for row in reader:
            v = (row.get(date_col) or "").strip()
            if v.isdigit() and len(v) == 8:
                dates.append(v)
        return min(dates) if dates else None
    except Exception as e:
        return f"ERR:{type(e).__name__}"


def resolve_feed_start_dates(df, out_dir, concurrency=8):
    print("[2/6] Resolving feed_start_date for each unique sig sha ...")
    reps = (df.dropna(subset=["sig_sha"])
              .sort_values("inserted_at")
              .groupby("sig_sha", as_index=False)
              .last()
              .reset_index(drop=True))
    print(f"      {len(reps)} unique sig shas to probe")
    sha_to_fsd = {}
    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(parse_feed_start_date, r["permanent_url"], r["sig_source"]):
                   r["sig_sha"] for _, r in reps.iterrows()}
        for f in as_completed(futures):
            sha = futures[f]
            sha_to_fsd[sha] = f.result()
            done += 1
            if done % 50 == 0 or done == len(reps):
                print(f"      {done}/{len(reps)}  ({time.time()-t0:.0f}s)")
    pd.Series(sha_to_fsd, name="feed_start_date").to_csv(out_dir / "sha_to_fsd.csv",
                                                         index_label="sha")
    return sha_to_fsd


def dedup_by_feed_start_date(df, sha_to_fsd, out_dir):
    print("[3/6] Mapping feed_start_date back to all rows ...")
    df = df.copy()
    df["feed_start_date"] = df["sig_sha"].map(sha_to_fsd)
    n_non_gtfs = df["sig_sha"].isna().sum()
    print(f"      filtered out {n_non_gtfs} non-GTFS rows (no routes.txt or no calendar fingerprint)")
    gtfs = df[df["sig_sha"].notna()].copy()
    valid = gtfs[gtfs["feed_start_date"].notna()
                 & ~gtfs["feed_start_date"].astype(str).str.startswith("ERR:")]
    n_unresolved = len(gtfs) - len(valid)
    if n_unresolved:
        print(f"      WARNING: {n_unresolved} rows had unresolved feed_start_date")
    print(f"      unique feed_start_date values: {valid['feed_start_date'].nunique()}")
    keep = (valid.sort_values("inserted_at")
                 .groupby("feed_start_date", as_index=False)
                 .last())
    print(f"[4/6] Dedup result: {len(df)} -> {len(keep)} rows kept")
    keep.to_parquet(out_dir / "manifest_dedup.parquet")
    return keep


def download_zips(keep_df, name, out_dir, concurrency=8):
    print(f"[5/6] Downloading {len(keep_df)} ZIPs to {out_dir.resolve()} ...")
    zip_dir = out_dir / "zips"
    zip_dir.mkdir(exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = "compare-transit-discovery/0.2"

    def fetch_one(row):
        fsd = row["feed_start_date"]
        rh_id = row["rh_id"]
        out_path = zip_dir / f"{name}_{fsd}_rh{rh_id}.zip"
        if out_path.exists() and out_path.stat().st_size == row["filesize"]:
            return {"rh_id": rh_id, "path": str(out_path), "skipped": True,
                    "bytes": out_path.stat().st_size}
        try:
            t0 = time.time()
            with s.get(row["permanent_url"], timeout=300, stream=True) as r:
                if r.status_code != 200:
                    return {"rh_id": rh_id, "path": None, "error": f"HTTP {r.status_code}"}
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        f.write(chunk)
            return {"rh_id": rh_id, "path": str(out_path),
                    "bytes": out_path.stat().st_size, "elapsed": time.time() - t0}
        except Exception as e:
            return {"rh_id": rh_id, "path": None, "error": str(e)[:200]}

    results = []
    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(fetch_one, row) for _, row in keep_df.iterrows()]
        for f in as_completed(futures):
            results.append(f.result())
            done += 1
            if done % 25 == 0 or done == len(keep_df):
                ok = sum(1 for r in results if r.get("path"))
                print(f"      {done}/{len(keep_df)}  ok={ok}  ({time.time()-t0:.0f}s)")
    res_df = pd.DataFrame(results)
    res_df.to_csv(out_dir / "download_log.csv", index=False)

    # Retry failures inline
    fails = res_df[res_df["path"].isna()]
    if len(fails):
        print(f"      retrying {len(fails)} failed downloads ...")
        manifest = keep_df.set_index("rh_id")
        for _, r in fails.iterrows():
            rh_id = int(r["rh_id"])
            row = manifest.loc[rh_id]
            fsd = row["feed_start_date"]
            out_path = zip_dir / f"{name}_{fsd}_rh{rh_id}.zip"
            for attempt in range(3):
                try:
                    with s.get(row["permanent_url"], timeout=600, stream=True) as resp:
                        if resp.status_code != 200:
                            break
                        with open(out_path, "wb") as fh:
                            for chunk in resp.iter_content(1024 * 1024):
                                fh.write(chunk)
                    print(f"        rh_id={rh_id} OK on retry {attempt+1}")
                    break
                except Exception:
                    time.sleep(3)

    total = sum(p.stat().st_size for p in zip_dir.glob("*.zip"))
    n = len(list(zip_dir.glob("*.zip")))
    print(f"[6/6] Done. {n} zips on disk, {total/1e9:.2f} GB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--short-id", type=int, required=True,
                    help="PAN internal short dataset id (e.g. 240 for Transilien)")
    ap.add_argument("--name", required=True,
                    help="Short name for output dir + filename prefix (e.g. transilien)")
    ap.add_argument("--steps", nargs="+",
                    default=["fetch", "resolve", "dedup", "download"],
                    choices=["fetch", "resolve", "dedup", "download"])
    args = ap.parse_args()

    out_dir = DISCOVERY_ROOT / f"{args.name}_archive"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_p = out_dir / "manifest_raw.parquet"
    map_p = out_dir / "sha_to_fsd.csv"
    dedup_p = out_dir / "manifest_dedup.parquet"

    df = pd.read_parquet(raw_p) if raw_p.exists() else None
    sha_map = (pd.read_csv(map_p, index_col=0)["feed_start_date"].to_dict()
               if map_p.exists() else None)
    keep = pd.read_parquet(dedup_p) if dedup_p.exists() else None

    if "fetch" in args.steps:
        df = fetch_history_csv(args.short_id, out_dir)
    if "resolve" in args.steps:
        sha_map = resolve_feed_start_dates(df, out_dir)
    if "dedup" in args.steps:
        keep = dedup_by_feed_start_date(df, sha_map, out_dir)
    if "download" in args.steps:
        download_zips(keep, args.name, out_dir)


if __name__ == "__main__":
    main()
