"""
distmatrice 优化基准测试 v4（最终版）
======================================
对比三种实现：
  A: 原始 meshgrid 版本（含 4 个 N×N 临时数组）
  B: 行批量向量化（只计算上三角，Python loop）
  C: sklearn haversine_distances 向量化（C 实现，直接返回完整矩阵，但无 meshgrid 冗余）

实测关注点（基于 bigvolume 分块场景）：
  - distmatrice 在 ag_ap_generate_bigvolume 中每次对约 500 个站点的子簇调用
  - 典型调用规模: N = 100-600（K-Means 子簇）
  - 测试规模 100-2000 以覆盖所有可能分块大小
"""

import sys, time, tracemalloc, zipfile, io
import numpy as np
import pandas as pd
from scipy.spatial.distance import squareform
from sklearn.metrics.pairwise import haversine_distances
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from gtfs_utils import getDistHaversine

EARTH_R = 6371000.0

# ─── 实现 A：原始 meshgrid 版本 ───────────────────────────────────────────────
def distmatrice_original(nparray: np.ndarray) -> np.ndarray:
    """
    原始：4 个 N×N meshgrid 临时数组 + 结果 N×N → squareform
    内存峰值估计：~5 × N² × 8 bytes
    """
    lon = nparray[:, 0]
    lat = nparray[:, 1]
    lon1, lon2 = np.meshgrid(lon, lon)
    lat1, lat2 = np.meshgrid(lat, lat)
    dist_mat = getDistHaversine(lat1, lon1, lat2, lon2)
    np.fill_diagonal(dist_mat, 0)
    return squareform(dist_mat, checks=False)

# ─── 实现 B：行批量向量化 ────────────────────────────────────────────────────
def distmatrice_rowbatch(nparray: np.ndarray) -> np.ndarray:
    """
    只计算上三角 N(N-1)/2 个元素，每行一次 numpy 调用。
    内存峰值：condensed 数组 + O(N) 临时向量
    """
    n = len(nparray)
    result = np.empty(n * (n - 1) // 2, dtype=np.float64)
    lons = nparray[:, 0]
    lats = nparray[:, 1]
    idx = 0
    for i in range(n - 1):
        count = n - i - 1
        result[idx:idx + count] = getDistHaversine(
            lats[i], lons[i], lats[i+1:], lons[i+1:]
        )
        idx += count
    return result

# ─── 实现 C：sklearn haversine_distances（最优） ─────────────────────────────
def distmatrice_sklearn(nparray: np.ndarray) -> np.ndarray:
    """
    使用 sklearn 的 haversine_distances（C 实现，无冗余中间数组）：
    1. 输入 [[lon, lat]] → 转为弧度 [[lat_rad, lon_rad]]
    2. 调用 sklearn haversine_distances（内部只分配 N×N 结果）
    3. 乘以地球半径转为米，填充对角线，squareform
    这比原始节省 4 个 N×N 临时数组（meshgrid lons/lats）
    """
    lat_lon_rad = np.radians(nparray[:, [1, 0]])   # [lat, lon] in radians
    dist_mat = haversine_distances(lat_lon_rad) * EARTH_R
    np.fill_diagonal(dist_mat, 0.0)
    return squareform(dist_mat, checks=False)

# ─── 测量工具 ─────────────────────────────────────────────────────────────────
def measure(fn, *args):
    tracemalloc.start()
    t0 = time.perf_counter()
    result = fn(*args)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, elapsed, peak / 1024 / 1024

def verify_equal(a, b, tol=2.0):
    """误差容忍 2 米"""
    return np.allclose(a, b, atol=tol)

# ─── 加载 IDFM stops 数据 ─────────────────────────────────────────────────────
def load_stops(zip_path: str) -> np.ndarray:
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open('stops.txt') as f:
            stops = pd.read_csv(io.TextIOWrapper(f, encoding='utf-8'))
    stops = stops[stops['location_type'] == 0].dropna(subset=['stop_lat', 'stop_lon'])
    coords = stops[['stop_lon', 'stop_lat']].to_numpy(dtype=float)
    print(f"   IDFM 站点总数 (location_type=0): {len(coords):,}")
    return coords

# ─── 基准对比 ─────────────────────────────────────────────────────────────────
def run_benchmark(coords, sizes, reps=3):
    """每个规模重复测量 reps 次取最小值（减少 OS 噪声）"""
    all_rows = []
    
    print(f"\n{'N':>7} | {'原始A(s)':>9} | {'行批量B(s)':>10} | {'sklearn C(s)':>12} | {'A→B加速':>8} | {'A→C加速':>8} | {'内存A(MB)':>9} | {'内存C(MB)':>9} | {'内存节省':>8} | {'正确性':>6}")
    print(f"{'─'*7}─┼─{'─'*9}─┼─{'─'*10}─┼─{'─'*12}─┼─{'─'*8}─┼─{'─'*8}─┼─{'─'*9}─┼─{'─'*9}─┼─{'─'*8}─┼─{'─'*6}")
    
    for n in sizes:
        if n > len(coords):
            print(f"  ⚠️  N={n} 超过数据集大小，跳过")
            continue
        
        sample = coords[:n]
        
        # 重复测量取最小时间
        t_a_list, t_b_list, t_c_list = [], [], []
        r_a = r_b = r_c = None
        m_a = m_b = m_c = 0
        
        for _ in range(reps):
            try:
                r_a, t, m = measure(distmatrice_original, sample)
                t_a_list.append(t); m_a = max(m_a, m)
            except MemoryError:
                t_a_list.append(float('nan'))
            
            r_b, t, m = measure(distmatrice_rowbatch, sample)
            t_b_list.append(t); m_b = max(m_b, m)
            
            r_c, t, m = measure(distmatrice_sklearn, sample)
            t_c_list.append(t); m_c = max(m_c, m)
        
        t_a = min(t_a_list) if t_a_list else float('nan')
        t_b = min(t_b_list)
        t_c = min(t_c_list)
        
        sp_b = t_a / t_b if not np.isnan(t_a) else float('nan')
        sp_c = t_a / t_c if not np.isnan(t_a) else float('nan')
        mr   = m_a / m_c  if m_c > 0 and not np.isnan(m_a) else float('nan')
        
        ok_b = verify_equal(r_a, r_b) if r_a is not None else None
        ok_c = verify_equal(r_a, r_c) if r_a is not None else None
        eq_str = f"{'✅' if ok_b else '❌'}B/{'✅' if ok_c else '❌'}C" if r_a is not None else "OOM"
        
        row = dict(N=n, t_a=t_a, t_b=t_b, t_c=t_c,
                   sp_b=sp_b, sp_c=sp_c,
                   m_a=m_a, m_c=m_c, mr=mr,
                   ok_b=ok_b, ok_c=ok_c)
        all_rows.append(row)
        
        def fmt(v, fmt_str):
            return format(v, fmt_str) if not np.isnan(v) else 'OOM'
        
        print(f"{n:>7,} | {fmt(t_a,'9.4f')} | {t_b:>10.4f} | {t_c:>12.4f} | "
              f"{fmt(sp_b,'8.2f')+'x':>9} | {fmt(sp_c,'8.2f')+'x':>9} | "
              f"{fmt(m_a,'9.1f')} | {m_c:>9.1f} | {fmt(mr,'8.2f')+'x':>9} | {eq_str}")
    
    print(f"{'─'*105}")
    return all_rows

# ─── 理论分析 ─────────────────────────────────────────────────────────────────
def print_theory(sizes):
    print("\n📊 理论内存占用分析（float64 = 8 bytes/element）")
    print(f"  原始实现工作内存峰值：meshgrid × 4（lon1,lon2,lat1,lat2 各 N²）+ dist_mat(N²) = 5N² 元素")
    print(f"  优化实现工作内存峰值：仅 dist_mat(N²) + 无临时中间数组 → squareform 输出 N(N-1)/2\n")
    print(f"{'N':>8} │ {'原始估算 5N²(MB)':>18} │ {'sklearn 1N²(MB)':>17} │ {'condensed(MB)':>14} │ {'节省(原→cond)':>14}")
    print("─"*8 + "─┼─" + "─"*18 + "─┼─" + "─"*17 + "─┼─" + "─"*14 + "─┼─" + "─"*14)
    for n in sizes:
        orig_est = 5 * n**2 * 8 / 1024**2
        sk_mb = n**2 * 8 / 1024**2
        cond_mb = n*(n-1)//2 * 8 / 1024**2
        saving_pct = (1 - cond_mb / orig_est) * 100
        print(f"{n:>8,} │ {orig_est:>18.1f} │ {sk_mb:>17.1f} │ {cond_mb:>14.1f} │ {saving_pct:>13.1f}%")

# ─── 主函数 ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    zip_path = r"C:\Users\wei.si\Projets\GTFS Miner\Resources\raw\IDFM-gtfs.zip"
    test_sizes = [100, 300, 500, 800, 1000, 1500, 2000]
    theory_sizes = test_sizes + [5000, 10000, 45000]
    
    print("=" * 70)
    print(" distmatrice() 优化基准测试 — IDFM-gtfs.zip 真实数据")
    print("=" * 70)
    
    print_theory(theory_sizes)
    
    print(f"\n📂 加载 IDFM stops 数据...")
    coords = load_stops(zip_path)
    
    print(f"\n⏱  开始基准测试（每规模重复 3 次，取最快）...")
    results = run_benchmark(coords, test_sizes, reps=3)
    
    print("\n📋 汇总统计（优化方案 C: sklearn haversine_distances vs 原始 A）:")
    valid = [r for r in results if not np.isnan(r['sp_c'])]
    if valid:
        sps = [r['sp_c'] for r in valid]
        mrs = [r['mr'] for r in valid if not np.isnan(r['mr'])]
        okc = all(r['ok_c'] for r in valid if r['ok_c'] is not None)
        print(f"  ⏱  时间加速:  {min(sps):.2f}x ~ {max(sps):.2f}x  │  中位数: {np.median(sps):.2f}x")
        if mrs:
            print(f"  🧠 内存节省:  {min(mrs):.1f}x ~ {max(mrs):.1f}x  │  中位数: {np.median(mrs):.1f}x")
        print(f"  ✅ 正确性:   {'全部通过（容忍 ≤ 2m 误差）' if okc else '存在偏差，请检查'}")
    
    print("\n✅ 基准测试完成。\n")
