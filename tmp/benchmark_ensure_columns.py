"""
ensure_columns 优化基准测试
============================
对比两种"补全缺失列"实现：
  A: 原始 pd.concat([empty_schema_df, raw_df], ignore_index=True)
  B: ensure_columns(df, cols) — df.copy() + reset_index + 仅补缺失列

测试场景（模拟真实 norm 函数调用规模）：
  - stop_times 场景：6 列，N = 1k / 10k / 100k / 500k / 1M 行（最关键）
  - stops 场景：14 列，N = 1k / 10k / 100k（站点数量通常较小）

场景 A：输入数据含所有必要列（正常 GTFS，concat 纯开销）
场景 B：输入数据缺少 1 列（需补列，ensure_columns 有额外赋值步骤）
"""

import sys, time, tracemalloc
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from gtfs_norm import ensure_columns

# ─── 实现 A：原始 concat 模式 ─────────────────────────────────────────────────
def concat_fill(df: pd.DataFrame, required_cols: list) -> pd.DataFrame:
    empty_v = pd.DataFrame(columns=required_cols)
    return pd.concat([empty_v, df], ignore_index=True)

# ─── 实现 B：ensure_columns ───────────────────────────────────────────────────
def ensure_fill(df: pd.DataFrame, required_cols: list) -> pd.DataFrame:
    return ensure_columns(df, required_cols)

# ─── 测量工具 ─────────────────────────────────────────────────────────────────
def measure(fn, *args):
    tracemalloc.start()
    t0 = time.perf_counter()
    result = fn(*args)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, elapsed, peak / 1024 / 1024

def verify_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """验证列集合相同、值相等（忽略列顺序）"""
    if set(a.columns) != set(b.columns):
        return False
    for col in a.columns:
        if not a[col].equals(b[col]):
            # 允许 NaN 等值
            if not (a[col].isna() == b[col].isna()).all():
                return False
            non_na = a[col].notna()
            if not (a[col][non_na] == b[col][non_na]).all():
                return False
    return True

# ─── 生成测试数据 ─────────────────────────────────────────────────────────────
def make_stop_times(n: int, rng: np.random.Generator, missing_col: bool = False) -> tuple:
    """生成模拟 stop_times DataFrame"""
    cols = ['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence', 'timepoint']
    required = cols[:]
    data = {
        'trip_id':         [f'T{i//10}' for i in range(n)],
        'arrival_time':    [f'{h:02d}:{m:02d}:00' for h, m in zip(rng.integers(0,24,n), rng.integers(0,60,n))],
        'departure_time':  [f'{h:02d}:{m:02d}:00' for h, m in zip(rng.integers(0,24,n), rng.integers(0,60,n))],
        'stop_id':         [f'S{i}' for i in range(n)],
        'stop_sequence':   rng.integers(1, 50, n).tolist(),
    }
    if not missing_col:
        data['timepoint'] = rng.integers(0, 2, n).tolist()
    df = pd.DataFrame(data)
    return df, required

def make_stops(n: int, rng: np.random.Generator, missing_col: bool = False) -> tuple:
    """生成模拟 stops DataFrame（含部分列）"""
    required = ['stop_id', 'stop_code', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon',
                'zone_id', 'stop_url', 'location_type', 'parent_station', 'stop_timezone',
                'wheelchair_boarding', 'level_id', 'platform_code']
    # 正常 GTFS 通常只有部分列
    present_cols = ['stop_id', 'stop_name', 'stop_lat', 'stop_lon', 'location_type']
    if not missing_col:
        present_cols += ['parent_station']
    data = {
        'stop_id':       [f'S{i}' for i in range(n)],
        'stop_name':     [f'Stop {i}' for i in range(n)],
        'stop_lat':      rng.uniform(48.0, 49.5, n).tolist(),
        'stop_lon':      rng.uniform(1.5, 3.5, n).tolist(),
        'location_type': rng.integers(0, 2, n).tolist(),
    }
    if not missing_col:
        data['parent_station'] = [f'PS{i//5}' if rng.random() > 0.5 else None for i in range(n)]
    df = pd.DataFrame(data)
    return df, required

# ─── 基准对比 ─────────────────────────────────────────────────────────────────
def run_scenario(label: str, sizes: list, make_fn, missing_col: bool, reps: int = 3):
    rng = np.random.default_rng(42)
    miss_tag = "缺1列" if missing_col else "全列齐"

    print(f"\n📊 场景：{label}（{miss_tag}）")
    print(f"{'N':>9} | {'concat A(s)':>11} | {'ensure B(s)':>11} | {'加速比':>7} | {'内存A(MB)':>9} | {'内存B(MB)':>9} | {'正确性':>6}")
    print(f"{'─'*9}─┼─{'─'*11}─┼─{'─'*11}─┼─{'─'*7}─┼─{'─'*9}─┼─{'─'*9}─┼─{'─'*6}")

    rows = []
    for n in sizes:
        df, required = make_fn(n, rng, missing_col=missing_col)

        t_a_list, t_b_list = [], []
        r_a = r_b = None
        m_a = m_b = 0.0

        for _ in range(reps):
            r_a, t, m = measure(concat_fill, df, required)
            t_a_list.append(t); m_a = max(m_a, m)

            r_b, t, m = measure(ensure_fill, df, required)
            t_b_list.append(t); m_b = max(m_b, m)

        t_a = min(t_a_list)
        t_b = min(t_b_list)
        sp  = t_a / t_b if t_b > 0 else float('nan')
        ok  = verify_equal(r_a, r_b)

        rows.append(dict(N=n, t_a=t_a, t_b=t_b, sp=sp, m_a=m_a, m_b=m_b, ok=ok))
        print(f"{n:>9,} | {t_a:>11.5f} | {t_b:>11.5f} | {sp:>6.2f}x | {m_a:>9.2f} | {m_b:>9.2f} | {'✅' if ok else '❌'}")

    print(f"{'─'*95}")
    return rows

# ─── 主函数 ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 70)
    print(" ensure_columns 优化基准测试")
    print("=" * 70)

    # stop_times：关键路径，可达数百万行
    st_sizes = [1_000, 10_000, 100_000, 500_000, 1_000_000]
    # stops：通常较小
    stops_sizes = [1_000, 10_000, 100_000]

    all_rows = []

    # 场景1: stop_times，所有列均存在（无缺失列）
    r1 = run_scenario("stop_times (6列)", st_sizes, make_stop_times, missing_col=False)
    all_rows.extend(r1)

    # 场景2: stop_times，缺少 timepoint 列（需补列）
    r2 = run_scenario("stop_times (6列)", st_sizes, make_stop_times, missing_col=True)
    all_rows.extend(r2)

    # 场景3: stops，8列已有 + 需补6列
    r3 = run_scenario("stops (14列)", stops_sizes, make_stops, missing_col=True)
    all_rows.extend(r3)

    print("\n📋 汇总统计（ensure_columns B vs concat A）：")
    valid = [r for r in all_rows]
    sps = [r['sp'] for r in valid if not (r['sp'] != r['sp'])]  # exclude NaN
    okall = all(r['ok'] for r in valid)
    if sps:
        print(f"  ⏱  时间加速:  {min(sps):.2f}x ~ {max(sps):.2f}x  │  中位数: {np.median(sps):.2f}x")
    print(f"  ✅ 正确性:   {'全部通过' if okall else '存在偏差，请检查'}")

    print("\n✅ 基准测试完成。\n")
