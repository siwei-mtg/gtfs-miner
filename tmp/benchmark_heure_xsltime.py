"""
heure_from_xsltime 优化基准测试
================================
对比两种实现：
  A: 原始 .apply(heure_from_xsltime) — 逐行 Python 标量调用
  B: heure_from_xsltime_vec()         — 向量化 pandas Series 运算

典型调用场景：MEF_course / MEF_iti / MEF_iti_arc 中的时间列格式化
  - MEF_course     : 班次数量（通常 1k–100k 行）
  - MEF_iti        : 行程停靠点（通常 10k–1M 行）
  - MEF_iti_arc    : 运行段（通常 10k–1M 行）
"""

import sys, time, tracemalloc, zipfile, io
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from gtfs_utils import heure_from_xsltime, heure_from_xsltime_vec

# ─── 实现 A：原始逐行 apply ───────────────────────────────────────────────────
def heure_original(series: pd.Series) -> pd.Series:
    return series.apply(heure_from_xsltime)

# ─── 实现 B：向量化（优化版） ─────────────────────────────────────────────────
def heure_vectorized(series: pd.Series) -> pd.Series:
    return heure_from_xsltime_vec(series)

# ─── 测量工具 ─────────────────────────────────────────────────────────────────
def measure(fn, *args):
    tracemalloc.start()
    t0 = time.perf_counter()
    result = fn(*args)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, elapsed, peak / 1024 / 1024

def verify_equal(a: pd.Series, b: pd.Series) -> bool:
    return (a.reset_index(drop=True) == b.reset_index(drop=True)).all()

# ─── 生成测试数据 ─────────────────────────────────────────────────────────────
def make_series(n: int, rng: np.random.Generator) -> pd.Series:
    """生成 n 个随机 Excel 时间分数（含约 2% NaN）"""
    vals = rng.uniform(0.0, 1.0, n)
    nan_mask = rng.random(n) < 0.02
    series = pd.Series(vals, dtype=float)
    series[nan_mask] = np.nan
    return series

# ─── 加载 IDFM stop_times 数据并转换为 xsltime ───────────────────────────────
def load_idfm_times(zip_path: str, n: int) -> pd.Series:
    """
    从 IDFM stop_times.txt 加载真实 arrival_time，
    转换为 Excel 时间分数（HH:MM:SS → day fraction）。
    """
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open('stop_times.txt') as f:
            st = pd.read_csv(io.TextIOWrapper(f, encoding='utf-8'),
                             usecols=['arrival_time'], nrows=n)
    # HH:MM:SS → day fraction
    parts = st['arrival_time'].str.split(':', expand=True).astype(float)
    fracs = parts[0] / 24.0 + parts[1] / 1440.0 + parts[2] / 86400.0
    return fracs.reset_index(drop=True)

# ─── 基准对比 ─────────────────────────────────────────────────────────────────
def run_benchmark(sizes, zip_path=None, reps=3):
    rng = np.random.default_rng(42)

    print(f"\n{'N':>9} | {'原始A(s)':>9} | {'向量化B(s)':>10} | {'加速比':>7} | {'内存A(MB)':>9} | {'内存B(MB)':>9} | {'正确性':>6}")
    print(f"{'─'*9}─┼─{'─'*9}─┼─{'─'*10}─┼─{'─'*7}─┼─{'─'*9}─┼─{'─'*9}─┼─{'─'*6}")

    all_rows = []
    for n in sizes:
        # 优先使用真实 IDFM 数据，fallback 到合成数据
        if zip_path and Path(zip_path).exists():
            try:
                series = load_idfm_times(zip_path, n)
                data_src = "IDFM"
            except Exception:
                series = make_series(n, rng)
                data_src = "synthetic"
        else:
            series = make_series(n, rng)
            data_src = "synthetic"

        t_a_list, t_b_list = [], []
        r_a = r_b = None
        m_a = m_b = 0.0

        for _ in range(reps):
            r_a, t, m = measure(heure_original, series)
            t_a_list.append(t); m_a = max(m_a, m)

            r_b, t, m = measure(heure_vectorized, series)
            t_b_list.append(t); m_b = max(m_b, m)

        t_a = min(t_a_list)
        t_b = min(t_b_list)
        sp  = t_a / t_b if t_b > 0 else float('nan')
        ok  = verify_equal(r_a, r_b)

        all_rows.append(dict(N=n, t_a=t_a, t_b=t_b, sp=sp, m_a=m_a, m_b=m_b, ok=ok))

        print(f"{n:>9,} | {t_a:>9.4f} | {t_b:>10.4f} | {sp:>6.2f}x | {m_a:>9.2f} | {m_b:>9.2f} | {'✅' if ok else '❌'} ({data_src})")

    print(f"{'─'*95}")
    return all_rows

# ─── 主函数 ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    zip_path = r"C:\Users\wei.si\Projets\GTFS Miner\Resources\raw\IDFM-gtfs.zip"
    test_sizes = [1_000, 10_000, 100_000, 500_000, 1_000_000]

    print("=" * 70)
    print(" heure_from_xsltime 优化基准测试")
    print("=" * 70)

    results = run_benchmark(test_sizes, zip_path=zip_path, reps=3)

    print("\n📋 汇总统计（向量化 B vs 原始 A）:")
    valid = [r for r in results if not np.isnan(r['sp'])]
    if valid:
        sps = [r['sp'] for r in valid]
        okall = all(r['ok'] for r in valid)
        print(f"  ⏱  时间加速:  {min(sps):.2f}x ~ {max(sps):.2f}x  │  中位数: {np.median(sps):.2f}x")
        print(f"  ✅ 正确性:   {'全部通过' if okall else '存在偏差，请检查'}")

    print("\n✅ 基准测试完成。\n")
