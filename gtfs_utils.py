"""
GTFS 基础工具模块 (gtfs_utils.py)

功能：
1. 字符串与时间格式规范化
2. 空间距离计算 (Haversine)
3. 编码检测与通用数据清洗
"""

import math
import numpy as np
import pandas as pd
import chardet
from pathlib import Path
from typing import List, Union, Optional
from scipy.spatial.distance import pdist

# --- 字符串处理 ---

def norm_upper_str(pd_series: pd.Series) -> pd.Series:
    """
    将 Series 转换为大写并去除重音符号。
    Input Schema: pd.Series(str)
    Output Schema: pd.Series(str)
    """
    return pd_series.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8').str.upper()

# --- 时间处理 ---

def str_time_hms_hour(hms: str) -> int:
    """提取 HH:MM:SS 中的小时。"""
    try:
        return int(hms.split(':')[0])
    except (ValueError, IndexError):
        return 0

def str_time_hms(hms: str) -> float:
    """将 HH:MM:SS 转换为天数比例 (用于 Excel 兼容)。"""
    try:
        h, m, s = hms.split(':')
        return int(h)/24 + int(m)/24/60 + int(s)/24/3600
    except (ValueError, IndexError):
        return 0.0

def get_sec(input_timedelta: List) -> List[float]:
    """获取 timedelta 列表的总秒数。"""
    return [td.total_seconds() for td in input_timedelta]

def heure_from_xsltime(horaire_excel: float) -> str:
    """将 Excel 时间比例转换为 HH:MM 格式。"""
    if pd.isna(horaire_excel):
        return "00:00"
    frac, hours = math.modf(horaire_excel * 24)
    return f'{int(hours):02}:{int(frac * 60):02}'

# --- 空间计算 ---

def getDistHaversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    使用 Haversine 公式计算两点间的距离（米）。
    """
    EARTHRADIUS = 6371000.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    
    a = (np.sin(dphi/2))**2 + np.cos(phi1) * np.cos(phi2) * (np.sin(dlambda/2.0))**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0-a))
    return EARTHRADIUS * c

def distmatrice(nparray: np.ndarray) -> np.ndarray:
    """
    计算坐标矩阵的点对点距离矩阵。
    nparray: [[lon, lat], ...]
    """
    from scipy.spatial.distance import squareform
    lon = nparray[:, 0]
    lat = nparray[:, 1]
    lon1, lon2 = np.meshgrid(lon, lon)
    lat1, lat2 = np.meshgrid(lat, lat)
    dist_mat = getDistHaversine(lat1, lon1, lat2, lon2)
    # squareform doesn't accept diagonal with slightly non-zero elements, so fill 0s
    np.fill_diagonal(dist_mat, 0)
    return squareform(dist_mat, checks=False)

# --- 数据清洗 ---

def nan_in_col_workaround(pd_serie: pd.Series) -> pd.Series:
    """
    处理包含 NaN 的 ID 列，将其安全转换为字符串。
    如果是整型则去除 .0，如果是字符串则保持原样，NaN 转为 np.nan。
    """
    if pd_serie.empty: return pd_serie
    
    # 尝试转换为数字，如果失败则按字符串处理
    return pd_serie.astype(str).replace(['nan', 'NaN', 'None', '-1', '-1.0'], np.nan)

def duree_arc(df: pd.DataFrame) -> float:
    """
    Calcule la durée d'un groupe d'arcs (fraction de jour Excel).
    Input Schema: [heure_arrive, heure_depart]
    Output: float — max(heure_arrive) - min(heure_depart)
    """
    return float(df['heure_arrive'].max() - df['heure_depart'].min())

def encoding_guess(acces: Path) -> dict:
    """
    自动检测文件编码。
    """
    with acces.open('rb') as rawdata:
        return chardet.detect(rawdata.read(10000))

if __name__ == '__main__':
    # 快速自测
    print(f"Test Norm: {norm_upper_str(pd.Series(['Étage', 'Café'])).tolist()}")
    print(f"Test Dist: {getDistHaversine(48.8566, 2.3522, 45.7640, 4.8357):.2f} m")
    print(f"Test Time: {heure_from_xsltime(0.5)}")
