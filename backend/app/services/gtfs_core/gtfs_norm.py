"""
GTFS 标准化模块 (gtfs_norm.py)

功能：
1. 清洗与转换 GTFS 原始表 (Agency, Stops, Routes, Trips, Stop_times, Calendar)。
2. 核心 Schema 校验与列重命名。

与整体流程的关系：
```plaintext
输入 GTFS ZIP / txt 目录 -> [读取/清洗 rawgtfs] 
                       -> [agency/stops/routes/trips 分离规范化] 
                       -> ID 映射绑定 
                       -> 规范化字典集 (normed)
```
"""

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List, Union, TypedDict
from .gtfs_utils import norm_upper_str, nan_in_col_workaround

class NormedGTFS(TypedDict):
    """
    Typed contract for the dict returned by gtfs_normalize().
    TypedDict keeps dict-style access (normed['stops']) while giving IDEs and type-checkers
    full visibility into every key and its type.
    """
    agency:           pd.DataFrame
    routes:           pd.DataFrame
    stops:            pd.DataFrame
    trips:            pd.DataFrame
    stop_times:       pd.DataFrame
    calendar:         Optional[pd.DataFrame]   # None when the feed has no calendar.txt
    calendar_dates:   pd.DataFrame
    shapes:           Optional[pd.DataFrame]   # None when the feed has no shapes.txt
    route_id_coor:    pd.DataFrame             # [route_id, id_ligne_num]
    trip_id_coor:     pd.DataFrame             # [trip_id, id_course_num]
    ser_id_coor:      pd.DataFrame             # [service_id, id_service_num]
    initial_na:       str                      # NA summary before interpolation
    final_na_time_col: int                     # remaining NA count in time columns


# 常量定义
DEFAULT_ROUTE_TYPE = 3
DEFAULT_LOCATION_TYPE = 0

# GTFS route_type → mode 映射表（GTFS spec §1.3）
# 新增交通类型只需在此追加行，ligne_generate() 无需修改
ROUTE_TYPE_MAP: pd.DataFrame = pd.DataFrame({
    'route_type': [0,         1,       2,       3,     4,       5,       6,         7,             11,       12],
    'mode':       ["tramway", "metro", "train", "bus", "ferry", "cable", "telephe", "funiculaire", "trolley", "monorail"],
})

def ensure_columns(df: pd.DataFrame, required_cols: List[str]) -> pd.DataFrame:
    """确保 DataFrame 包含所有必要列，缺失列填充 NaN。
    返回新 DataFrame（已 reset_index），不修改原始数据。
    替代 pd.concat([empty_schema_df, raw_df], ignore_index=True) 模式。
    """
    result = df.copy()
    result.reset_index(drop=True, inplace=True)
    for col in required_cols:
        if col not in result.columns:
            result[col] = np.nan
    return result

def agency_norm(raw_agency: pd.DataFrame) -> pd.DataFrame:
    """
    Input Schema: [agency_name, agency_url, ...]
    Output Schema: [agency_id, agency_name, agency_url, agency_timezone, agency_lang, agency_phone, agency_fare_url, agency_email, ...]
    """
    agency = ensure_columns(raw_agency, ['agency_id', 'agency_name', 'agency_url', 'agency_timezone',
                                          'agency_lang', 'agency_phone', 'agency_fare_url', 'agency_email'])
    agency.dropna(axis=1, how='all', inplace=True)
    return agency

def stops_norm(raw_stops: pd.DataFrame) -> pd.DataFrame:
    """
    规范化停车点数据。
    Input Schema: [stop_id, stop_name, stop_lat, stop_lon, location_type, parent_station, ...]
    Output Schema: [stop_id, stop_lat, stop_lon, stop_name, location_type, parent_station]
    """
    stops = ensure_columns(raw_stops, ['stop_id', 'stop_code', 'stop_name', 'stop_desc',
                                       'stop_lat', 'stop_lon', 'zone_id', 'stop_url', 'location_type',
                                       'parent_station', 'stop_timezone', 'wheelchair_boarding',
                                       'level_id', 'platform_code'])
    stops.stop_name = norm_upper_str(stops.stop_name)
    stops.stop_id = nan_in_col_workaround(stops.stop_id)
    
    # 坐标转换与容错 (try/except 覆盖编码异常，如空格、不可见字符，参见 legacy 223-231)
    for col in ['stop_lat', 'stop_lon']:
        try:
            cleaned = stops[col].astype(str).str.strip().replace('', '0')
            stops[col] = pd.to_numeric(cleaned, errors='coerce').fillna(0).astype(np.float32)
        except (ValueError, TypeError):
            stops[col] = np.float32(0.0)
    
    stops.stop_name = norm_upper_str(stops.stop_name)
    stops.location_type = stops.location_type.fillna(DEFAULT_LOCATION_TYPE).astype(np.int8)
    stops.parent_station = nan_in_col_workaround(stops.parent_station)
    
    essentials = ['stop_id','stop_lat','stop_lon','stop_name','location_type','parent_station']
    return stops[essentials]

def routes_norm(raw_routes: pd.DataFrame) -> pd.DataFrame:
    """
    Input Schema: [route_id, route_type, ...]
    Output Schema: [route_id, agency_id, route_short_name, route_long_name, route_desc, route_type, route_color, route_text_color, id_ligne_num, ...]
    """
    routes = ensure_columns(raw_routes, ['route_id', 'agency_id', 'route_short_name', 'route_long_name',
                                          'route_desc', 'route_type', 'route_url', 'route_color',
                                          'route_text_color', 'route_sort_order'])
    routes.drop(['route_url', 'route_sort_order'], axis=1, errors='ignore', inplace=True)
    routes.dropna(axis=1, how='all', inplace=True)
    routes.route_id = routes.route_id.astype(str)
    routes.route_type = pd.to_numeric(routes.route_type, errors='coerce').fillna(DEFAULT_ROUTE_TYPE).astype(np.int8) # Default BUS
    routes['id_ligne_num'] = np.arange(1, len(routes) + 1)
    return routes

def ligne_generate(raw_routes: pd.DataFrame) -> pd.DataFrame:
    """
    解析线路类型 (公交, 地铁, 火车等)。
    Input Schema: [route_type, ...]
    Output Schema: [route_type, mode, ...]
    映射表见模块级常量 ROUTE_TYPE_MAP。
    """
    return raw_routes.merge(ROUTE_TYPE_MAP, on='route_type', how='left').dropna(axis=1, how='all')

def trips_norm(raw_trips: pd.DataFrame) -> pd.DataFrame:
    """
    Input Schema: [route_id, service_id, trip_id, ...]
    Output Schema: [route_id, service_id, trip_id, trip_headsign, direction_id, shape_id, id_course_num, ...]
    """
    trips = ensure_columns(raw_trips, ['route_id', 'service_id', 'trip_id', 'trip_headsign',
                                       'direction_id', 'shape_id'])
    cols = ['route_id', 'service_id', 'trip_id']
    trips[cols] = trips[cols].astype(str)
    if not trips.empty:
        trips['id_course_num'] = np.arange(1, len(trips) + 1)
        if 'shape_id' in trips.columns and trips['shape_id'].isna().all():
            trips.drop(columns=['shape_id'], inplace=True)
    return trips

def stop_times_norm(raw_stoptimes: pd.DataFrame) -> Tuple[pd.DataFrame, str, int]:
    """
    规范化停靠时间并处理缺失值。
    Input Schema: [trip_id, arrival_time, departure_time, stop_id, stop_sequence, timepoint, ...]
    Output Schema: [trip_id, arrival_time, departure_time, stop_id, stop_sequence, timepoint, ...]
    Return: (DataFrame, NA_Summary_String, NA_Count_in_Time_Cols)
    """
    stop_times = ensure_columns(raw_stoptimes, ['trip_id', 'arrival_time', 'departure_time',
                                                 'stop_id', 'stop_sequence', 'timepoint'])

    # 早期列裁剪：仅保留下游实际使用的列，避免对宽 DataFrame 做全列 NA 扫描（参见 OPTIMIZATION_REPORT §2.5）
    _keep = ['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence', 'timepoint']
    if 'shape_dist_traveled' in stop_times.columns:
        _keep.append('shape_dist_traveled')
    stop_times = stop_times[_keep]

    # 统计缺失值（仅报告裁剪后的必要列）
    na_summary = f"Total: {len(stop_times)}. NAs: {stop_times.isna().sum().to_dict()}"

    time_cols = ['arrival_time', 'departure_time']
    time_na_count = int(stop_times[time_cols].isna().sum().sum())

    if time_na_count > 0:
        # Si timepoint est renseigné, filtrer les arrêts chronométrés avant interpolation (参见 legacy 295)
        has_timepoint = ('timepoint' in stop_times.columns
                         and stop_times['timepoint'].notna().any())
        if has_timepoint:
            timed = stop_times.loc[stop_times['timepoint'] == 1].copy()
            timed[time_cols] = timed.groupby('trip_id')[time_cols].transform(lambda x: x.ffill().bfill())
            # Retirer les lignes toujours sans heure après interpolation
            timed = timed.loc[timed[time_cols[0]].notna() | timed[time_cols[1]].notna()]
            stop_times = timed
        else:
            stop_times.loc[:, time_cols] = stop_times.groupby('trip_id')[time_cols].transform(
                lambda x: x.ffill().bfill())

    stop_times[['trip_id', 'stop_id']] = stop_times[['trip_id', 'stop_id']].astype(str)
    stop_times['stop_sequence'] = pd.to_numeric(stop_times['stop_sequence'], errors='coerce').fillna(0).astype(np.int32)

    # Conserver shape_dist_traveled si présent (参见 legacy 309)
    if 'shape_dist_traveled' in stop_times.columns:
        stop_times['shape_dist_traveled'] = pd.to_numeric(
            stop_times['shape_dist_traveled'], errors='coerce').astype(np.float32)

    # dropna(axis=1) 已由早期列裁剪替代，无需再扫描全列
    return stop_times, na_summary, int(stop_times[time_cols].isna().sum().sum())

def calendar_norm(raw_cal: pd.DataFrame) -> pd.DataFrame:
    """
    规范化 calendar.txt。
    Input Schema: [service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date]
    Output Schema: [service_id, monday, ..., start_date, end_date]
    """
    calendar = ensure_columns(raw_cal, ['service_id', 'monday', 'tuesday', 'wednesday',
                                        'thursday', 'friday', 'saturday', 'sunday',
                                        'start_date', 'end_date'])
    calendar['service_id'] = calendar['service_id'].astype(str)
    week_cols = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    calendar[week_cols] = calendar[week_cols].fillna(0).astype(np.int8)
    calendar['start_date'] = pd.to_numeric(calendar['start_date'], errors='coerce').fillna(0).astype(np.int32)
    calendar['end_date'] = pd.to_numeric(calendar['end_date'], errors='coerce').fillna(0).astype(np.int32)
    return calendar

def cal_dates_norm(raw_caldates: pd.DataFrame) -> pd.DataFrame:
    """
    规范化 calendar_dates.txt。
    Input Schema: [service_id, date, exception_type]
    Output Schema: [service_id, date, exception_type]
    """
    calendar_dates = ensure_columns(raw_caldates, ['service_id', 'date', 'exception_type'])
    calendar_dates['service_id'] = calendar_dates['service_id'].astype(str)
    calendar_dates['date'] = pd.to_numeric(calendar_dates['date'], errors='coerce').fillna(0).astype(np.int32)
    calendar_dates['exception_type'] = pd.to_numeric(calendar_dates['exception_type'], errors='coerce').fillna(0).astype(np.int8)
    return calendar_dates

def gtfs_normalize(raw_dict: Dict[str, pd.DataFrame]) -> NormedGTFS:
    """
    规范化流程总控制器。
    Input Schema (Dict): {"agency": df, "routes": df, "stops": df, "trips": df, "stop_times": df,
                          "calendar": df (optional), "calendar_dates": df (optional)}
    Output: NormedGTFS — see TypedDict definition above for the full key/type contract.

    处理流程：
    ```
    Phase 1 (并行): agency/routes/stops/trips/stop_times/calendar/cal_dates — 互相独立
         ↓
    Phase 2 (顺序): route_coor → ser_id_coor → trips/stop_times/calendar 关联映射
    ```
    """
    # ── Phase 1: 并行规范化（7 个函数互相独立，各自操作独立副本）───────────────
    _empty = pd.DataFrame()
    with ThreadPoolExecutor(max_workers=7) as pool:
        f_agency     = pool.submit(agency_norm,     raw_dict.get('agency',          _empty))
        f_routes     = pool.submit(routes_norm,     raw_dict.get('routes',          _empty))
        f_stops      = pool.submit(stops_norm,      raw_dict.get('stops',           _empty))
        f_trips      = pool.submit(trips_norm,      raw_dict.get('trips',           _empty))
        f_stop_times = pool.submit(stop_times_norm, raw_dict.get('stop_times',      _empty))
        f_cal        = pool.submit(calendar_norm,   raw_dict.get('calendar',        _empty))
        f_cal_dates  = pool.submit(cal_dates_norm,  raw_dict.get('calendar_dates',  _empty))

    agency                      = f_agency.result()
    routes                      = f_routes.result()
    stops                       = f_stops.result()
    trips                       = f_trips.result()
    st_processed, st_msg, st_na = f_stop_times.result()
    cal_normed                  = f_cal.result()
    cal_dates_normed            = f_cal_dates.result()

    # ── Phase 2: 顺序合并（有严格依赖关系，不可并行）────────────────────────────
    # ID 映射准备
    route_coor = routes[['route_id', 'id_ligne_num']]
    trip_coor  = trips[['trip_id', 'id_course_num']]

    # 关联映射
    trips = trips.merge(route_coor, on='route_id').drop('route_id', axis=1)

    # 服务 ID 映射
    ser_id_coor = pd.DataFrame({'service_id': trips.dropna(subset=['service_id'])['service_id'].unique()})
    ser_id_coor['id_service_num'] = np.arange(1, len(ser_id_coor) + 1)
    trips = trips.merge(ser_id_coor, on='service_id', how='left')

    st_processed = st_processed.merge(trip_coor, on='trip_id').drop('trip_id', axis=1)

    # Calendar 合并 ser_id_coor (try/except，空表 → None，参见 legacy 352-358)
    try:
        raw_cal_empty = raw_dict.get('calendar', _empty).empty
        if raw_cal_empty or cal_normed.empty:
            calendar = None
        else:
            calendar = cal_normed.merge(ser_id_coor, on='service_id').drop(columns=['service_id'])
            if calendar.empty:
                calendar = None
    except Exception:
        calendar = None

    # Calendar dates 合并 ser_id_coor
    if raw_dict.get('calendar_dates', _empty).empty or cal_dates_normed.empty:
        calendar_dates = pd.DataFrame(columns=['service_id', 'date', 'exception_type', 'id_service_num'])
    else:
        calendar_dates = cal_dates_normed.merge(ser_id_coor, on='service_id', how='left')

    # Shapes (optionnel, transmis tel quel pour corr_sl_shape / kcc, 参见 legacy 362-378)
    shapes = raw_dict.get('shapes', None)
    if shapes is not None and shapes.empty:
        shapes = None

    return {
        'agency':            agency,
        'routes':            routes,
        'stops':             stops,
        'trips':             trips,
        'stop_times':        st_processed,
        'calendar':          calendar,
        'calendar_dates':    calendar_dates,
        'shapes':            shapes,
        'route_id_coor':     route_coor,
        'trip_id_coor':      trip_coor,
        'ser_id_coor':       ser_id_coor,
        'initial_na':        st_msg,
        'final_na_time_col': st_na
    }

if __name__ == '__main__':
    # 简易测试代码可以在此添加
    print("gtfs_norm module loaded.")
