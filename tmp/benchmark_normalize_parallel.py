"""
gtfs_normalize 并行化基准测试
==============================
对比两种实现：
  A: 串行 — 7 个 norm 函数依次执行
  B: 并行 — 7 个 norm 函数通过 ThreadPoolExecutor 并发执行

关键依赖分析：
  - Phase 1 (可并行): agency/routes/stops/trips/stop_times/calendar/cal_dates
    各自只读取 raw_dict 的独立键，互不依赖，使用 ensure_columns 保证副本独立
  - Phase 2 (必须串行): route_coor/ser_id_coor 映射合并，有严格顺序依赖

测试数据：
  - 使用 IDFM-gtfs.zip 真实数据（若存在）
  - Fallback: 合成数据，规模参照 IDFM 数据集
"""

import sys, time, tracemalloc, zipfile, io
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from gtfs_norm import (agency_norm, routes_norm, stops_norm, trips_norm,
                        stop_times_norm, calendar_norm, cal_dates_norm,
                        gtfs_normalize)

# ─── 串行版本（基线）─────────────────────────────────────────────────────────
def _normalize_phase2(agency, routes, stops, trips, st_processed, st_msg, st_na,
                       cal_normed, cal_dates_normed, raw_dict):
    """Phase 2 合并逻辑（串行/并行共用）"""
    _empty = pd.DataFrame()
    route_coor = routes[['route_id', 'id_ligne_num']]
    trip_coor  = trips[['trip_id', 'id_course_num']]
    trips = trips.merge(route_coor, on='route_id').drop('route_id', axis=1)
    ser_id_coor = pd.DataFrame({'service_id': trips.dropna(subset=['service_id'])['service_id'].unique()})
    ser_id_coor['id_service_num'] = np.arange(1, len(ser_id_coor) + 1)
    trips = trips.merge(ser_id_coor, on='service_id', how='left')
    st_processed = st_processed.merge(trip_coor, on='trip_id').drop('trip_id', axis=1)
    try:
        if raw_dict.get('calendar', _empty).empty or cal_normed.empty:
            calendar = None
        else:
            calendar = cal_normed.merge(ser_id_coor, on='service_id').drop(columns=['service_id'])
            calendar = None if calendar.empty else calendar
    except Exception:
        calendar = None
    if raw_dict.get('calendar_dates', _empty).empty or cal_dates_normed.empty:
        calendar_dates = pd.DataFrame(columns=['service_id', 'date', 'exception_type', 'id_service_num'])
    else:
        calendar_dates = cal_dates_normed.merge(ser_id_coor, on='service_id', how='left')
    return agency, routes, stops, trips, st_processed, st_msg, st_na, calendar, calendar_dates

def normalize_serial(raw_dict: dict) -> dict:
    """串行版本：与优化前 gtfs_normalize 相同的调用顺序"""
    _empty = pd.DataFrame()
    agency                      = agency_norm(    raw_dict.get('agency',         _empty))
    routes                      = routes_norm(    raw_dict.get('routes',         _empty))
    stops                       = stops_norm(     raw_dict.get('stops',          _empty))
    trips                       = trips_norm(     raw_dict.get('trips',          _empty))
    st_processed, st_msg, st_na = stop_times_norm(raw_dict.get('stop_times',     _empty))
    cal_normed                  = calendar_norm(  raw_dict.get('calendar',       _empty))
    cal_dates_normed            = cal_dates_norm( raw_dict.get('calendar_dates', _empty))
    return _normalize_phase2(agency, routes, stops, trips, st_processed, st_msg, st_na,
                              cal_normed, cal_dates_normed, raw_dict)

def normalize_parallel(raw_dict: dict) -> dict:
    """并行版本：Phase 1 用 ThreadPoolExecutor，Phase 2 串行"""
    _empty = pd.DataFrame()
    with ThreadPoolExecutor(max_workers=7) as pool:
        f_agency     = pool.submit(agency_norm,     raw_dict.get('agency',         _empty))
        f_routes     = pool.submit(routes_norm,     raw_dict.get('routes',         _empty))
        f_stops      = pool.submit(stops_norm,      raw_dict.get('stops',          _empty))
        f_trips      = pool.submit(trips_norm,      raw_dict.get('trips',          _empty))
        f_stop_times = pool.submit(stop_times_norm, raw_dict.get('stop_times',     _empty))
        f_cal        = pool.submit(calendar_norm,   raw_dict.get('calendar',       _empty))
        f_cal_dates  = pool.submit(cal_dates_norm,  raw_dict.get('calendar_dates', _empty))
    agency                      = f_agency.result()
    routes                      = f_routes.result()
    stops                       = f_stops.result()
    trips                       = f_trips.result()
    st_processed, st_msg, st_na = f_stop_times.result()
    cal_normed                  = f_cal.result()
    cal_dates_normed            = f_cal_dates.result()
    return _normalize_phase2(agency, routes, stops, trips, st_processed, st_msg, st_na,
                              cal_normed, cal_dates_normed, raw_dict)

# ─── 测量工具 ─────────────────────────────────────────────────────────────────
def measure(fn, *args):
    tracemalloc.start()
    t0 = time.perf_counter()
    result = fn(*args)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, elapsed, peak / 1024 / 1024

# ─── 各 norm 函数单独计时（展示瓶颈分布）────────────────────────────────────
def time_each_norm(raw_dict: dict) -> dict:
    _empty = pd.DataFrame()
    funcs = {
        'agency_norm':     (agency_norm,     raw_dict.get('agency',         _empty)),
        'routes_norm':     (routes_norm,     raw_dict.get('routes',         _empty)),
        'stops_norm':      (stops_norm,      raw_dict.get('stops',          _empty)),
        'trips_norm':      (trips_norm,      raw_dict.get('trips',          _empty)),
        'stop_times_norm': (stop_times_norm, raw_dict.get('stop_times',     _empty)),
        'calendar_norm':   (calendar_norm,   raw_dict.get('calendar',       _empty)),
        'cal_dates_norm':  (cal_dates_norm,  raw_dict.get('calendar_dates', _empty)),
    }
    timings = {}
    for name, (fn, arg) in funcs.items():
        _, t, _ = measure(fn, arg)
        timings[name] = t
    return timings

# ─── 加载 IDFM 数据 ───────────────────────────────────────────────────────────
def load_idfm(zip_path: str) -> dict:
    tables = ['agency', 'routes', 'stops', 'trips', 'stop_times', 'calendar', 'calendar_dates']
    raw_dict = {}
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        for table in tables:
            fname = f'{table}.txt'
            if fname in names:
                with zf.open(fname) as f:
                    raw_dict[table] = pd.read_csv(io.TextIOWrapper(f, encoding='utf-8'), low_memory=False)
            else:
                raw_dict[table] = pd.DataFrame()
    sizes = {k: len(v) for k, v in raw_dict.items()}
    print(f"   数据规模: " + " | ".join(f"{k}={v:,}" for k, v in sizes.items() if v > 0))
    return raw_dict

# ─── 合成数据（fallback）─────────────────────────────────────────────────────
def make_synthetic(n_stop_times: int = 200_000) -> dict:
    rng = np.random.default_rng(42)
    n_stops, n_trips, n_routes = 5000, 10000, 200
    stops = pd.DataFrame({
        'stop_id': [f'S{i}' for i in range(n_stops)],
        'stop_name': [f'Stop {i}' for i in range(n_stops)],
        'stop_lat': rng.uniform(48.0, 49.5, n_stops),
        'stop_lon': rng.uniform(1.5, 3.5, n_stops),
        'location_type': rng.integers(0, 2, n_stops),
    })
    routes = pd.DataFrame({
        'route_id': [f'R{i}' for i in range(n_routes)],
        'route_short_name': [f'L{i}' for i in range(n_routes)],
        'route_type': rng.integers(0, 4, n_routes),
    })
    trips = pd.DataFrame({
        'route_id': [f'R{i % n_routes}' for i in range(n_trips)],
        'service_id': [f'SVC{i % 50}' for i in range(n_trips)],
        'trip_id': [f'T{i}' for i in range(n_trips)],
        'direction_id': rng.integers(0, 2, n_trips),
    })
    stop_times = pd.DataFrame({
        'trip_id': [f'T{i % n_trips}' for i in range(n_stop_times)],
        'arrival_time': [f'{h:02d}:{m:02d}:00' for h, m in zip(rng.integers(0, 24, n_stop_times), rng.integers(0, 60, n_stop_times))],
        'departure_time': [f'{h:02d}:{m:02d}:00' for h, m in zip(rng.integers(0, 24, n_stop_times), rng.integers(0, 60, n_stop_times))],
        'stop_id': [f'S{i % n_stops}' for i in range(n_stop_times)],
        'stop_sequence': rng.integers(1, 50, n_stop_times),
    })
    cal_dates = pd.DataFrame({
        'service_id': [f'SVC{i % 50}' for i in range(500)],
        'date': rng.integers(20230101, 20241231, 500),
        'exception_type': rng.integers(1, 3, 500),
    })
    print(f"   合成数据: stops={n_stops:,} | routes={n_routes:,} | trips={n_trips:,} | stop_times={n_stop_times:,} | cal_dates=500")
    return {
        'agency': pd.DataFrame({'agency_id': ['A1'], 'agency_name': ['Test']}),
        'routes': routes,
        'stops': stops,
        'trips': trips,
        'stop_times': stop_times,
        'calendar': pd.DataFrame(),
        'calendar_dates': cal_dates,
    }

# ─── 主函数 ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    zip_path = r"C:\Users\wei.si\Projets\GTFS Miner\Resources\raw\IDFM-gtfs.zip"

    print("=" * 70)
    print(" gtfs_normalize 并行化基准测试")
    print("=" * 70)

    # 加载数据
    print("\n📂 加载数据...")
    if Path(zip_path).exists():
        raw_dict = load_idfm(zip_path)
        data_src = "IDFM-gtfs.zip"
    else:
        raw_dict = make_synthetic(n_stop_times=200_000)
        data_src = "合成数据"
    print(f"   数据来源: {data_src}")

    # 各函数耗时分布
    print("\n⏱  各 norm 函数单独耗时（串行基线，了解瓶颈）：")
    timings = time_each_norm(raw_dict)
    total_serial_norm = sum(timings.values())
    for name, t in timings.items():
        bar = '█' * int(t / max(timings.values()) * 30)
        pct = t / total_serial_norm * 100
        print(f"  {name:<20} {t:6.3f}s  {pct:5.1f}%  {bar}")
    print(f"  {'合计':<20} {total_serial_norm:6.3f}s")

    # 基准对比（含 Phase 2，完整 gtfs_normalize）
    reps = 3
    print(f"\n⏱  完整 gtfs_normalize 对比（每次重复 {reps} 次取最小值）：")
    print(f"\n{'实现':>10} | {'时间(s)':>8} | {'内存(MB)':>9} | {'vs 串行':>8}")
    print(f"{'─'*10}─┼─{'─'*8}─┼─{'─'*9}─┼─{'─'*8}")

    t_serial_list, t_parallel_list = [], []
    m_serial = m_parallel = 0.0

    for _ in range(reps):
        _, t, m = measure(normalize_serial,   raw_dict)
        t_serial_list.append(t); m_serial = max(m_serial, m)

        _, t, m = measure(normalize_parallel, raw_dict)
        t_parallel_list.append(t); m_parallel = max(m_parallel, m)

    t_serial   = min(t_serial_list)
    t_parallel = min(t_parallel_list)
    speedup    = t_serial / t_parallel if t_parallel > 0 else float('nan')

    print(f"{'串行 A':>10} | {t_serial:>8.3f} | {m_serial:>9.1f} | {'—':>8}")
    print(f"{'并行 B':>10} | {t_parallel:>8.3f} | {m_parallel:>9.1f} | {speedup:>7.2f}x")
    print(f"{'─'*46}")

    print(f"\n📋 汇总：")
    print(f"  ⏱  时间加速: {speedup:.2f}x（串行 {t_serial:.3f}s → 并行 {t_parallel:.3f}s）")
    print(f"  🧠 Phase 1 norm 函数合计耗时（串行）: {total_serial_norm:.3f}s")
    bottleneck = max(timings.values())
    bottleneck_fn = max(timings, key=lambda k: timings[k])
    print(f"  🔑 最慢 norm 函数（并行下决定 Phase 1 时长）: {bottleneck_fn} = {bottleneck:.3f}s")
    print(f"  📐 理论最大 Phase 1 加速: {total_serial_norm / bottleneck:.2f}x（Amdahl 上界）")

    print("\n✅ 基准测试完成。\n")
