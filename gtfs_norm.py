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
import chardet
from zipfile import ZipFile
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List, Union
from gtfs_utils import norm_upper_str, nan_in_col_workaround, encoding_guess

# 常量定义
DEFAULT_ROUTE_TYPE = 3
DEFAULT_LOCATION_TYPE = 0

def agency_norm(raw_agency: pd.DataFrame) -> pd.DataFrame:
    """
    Input Schema: [agency_name, agency_url, ...]
    Output Schema: [agency_id, agency_name, agency_url, agency_timezone, agency_lang, agency_phone, agency_fare_url, agency_email, ...]
    """
    agency_v = pd.DataFrame(columns=['agency_id', 'agency_name', 'agency_url', 'agency_timezone',
                                      'agency_lang', 'agency_phone', 'agency_fare_url', 'agency_email'])
    agency = pd.concat([agency_v, raw_agency], ignore_index=True)
    agency.dropna(axis=1, how='all', inplace=True)
    return agency

def stops_norm(raw_stops: pd.DataFrame) -> pd.DataFrame:
    """
    规范化停车点数据。
    Input Schema: [stop_id, stop_name, stop_lat, stop_lon, location_type, parent_station, ...]
    Output Schema: [stop_id, stop_lat, stop_lon, stop_name, location_type, parent_station]
    """
    stops_v = pd.DataFrame(columns=['stop_id', 'stop_code', 'stop_name', 'stop_desc',
                                     'stop_lat', 'stop_lon', 'zone_id', 'stop_url','location_type', 
                                     'parent_station', 'stop_timezone','wheelchair_boarding',
                                     'level_id','platform_code'])
    stops = pd.concat([stops_v, raw_stops], ignore_index=True)
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
    routes_v = pd.DataFrame(columns=['route_id', 'agency_id', 'route_short_name', 'route_long_name',
                                      'route_desc', 'route_type', 'route_url', 'route_color',
                                      'route_text_color', 'route_sort_order'])
    routes = pd.concat([routes_v, raw_routes], ignore_index=True)
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
    """
    types_map = pd.DataFrame({
        'route_type': [0, 1, 2, 3, 4, 5, 6, 7, 11, 12],
        'mode': ["tramway", "metro", "train", "bus", "ferry", "cable", "telephe", "funiculaire", "trolley", "monorail"]
    })
    return raw_routes.merge(types_map, on='route_type', how='left').dropna(axis=1, how='all')

def trips_norm(raw_trips: pd.DataFrame) -> pd.DataFrame:
    """
    Input Schema: [route_id, service_id, trip_id, ...]
    Output Schema: [route_id, service_id, trip_id, trip_headsign, direction_id, shape_id, id_course_num, ...]
    """
    trips_v = pd.DataFrame(columns=['route_id', 'service_id', 'trip_id', 'trip_headsign', 
                                     'direction_id', 'shape_id'])
    trips = pd.concat([trips_v, raw_trips], ignore_index=True)
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
    stop_times_v = pd.DataFrame(columns=['trip_id', 'arrival_time', 'departure_time', 'stop_id',
                                          'stop_sequence', 'timepoint'])
    stop_times = pd.concat([stop_times_v, raw_stoptimes], ignore_index=True)

    # 统计缺失值
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

    stop_times.dropna(how='all', axis=1, inplace=True)

    return stop_times, na_summary, int(stop_times[time_cols].isna().sum().sum())

def calendar_norm(raw_cal: pd.DataFrame) -> pd.DataFrame:
    """
    规范化 calendar.txt。
    Input Schema: [service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date]
    Output Schema: [service_id, monday, ..., start_date, end_date]
    """
    cal_v = pd.DataFrame(columns=['service_id', 'monday', 'tuesday', 'wednesday',
                                   'thursday', 'friday', 'saturday', 'sunday',
                                   'start_date', 'end_date'])
    calendar = pd.concat([cal_v, raw_cal], ignore_index=True)
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
    cal_dates_v = pd.DataFrame(columns=['service_id', 'date', 'exception_type'])
    calendar_dates = pd.concat([cal_dates_v, raw_caldates], ignore_index=True)
    calendar_dates['service_id'] = calendar_dates['service_id'].astype(str)
    calendar_dates['date'] = pd.to_numeric(calendar_dates['date'], errors='coerce').fillna(0).astype(np.int32)
    calendar_dates['exception_type'] = pd.to_numeric(calendar_dates['exception_type'], errors='coerce').fillna(0).astype(np.int8)
    return calendar_dates

def rawgtfs_from_zip(zippath: Union[str, Path]) -> Dict[str, pd.DataFrame]:
    """
    从 ZIP 文件直接读取 GTFS 原始 CSV 数据。
    """
    result = {}
    with ZipFile(zippath, "r") as zfile:
        for name in zfile.namelist():
            if name.endswith('.txt'):
                basename = Path(name).name
                stem = Path(name).stem
                # 尝试 utf-8, 否则 fallback 到 latin-1
                try:
                    with zfile.open(name) as f:
                        df = pd.read_csv(f, encoding='utf-8', low_memory=False)
                except (UnicodeDecodeError, pd.errors.ParserError):
                    with zfile.open(name) as f:
                        df = pd.read_csv(f, encoding='latin-1', low_memory=False)
                
                result[stem] = df
    return result

def rawgtfs(dirpath: Union[str, Path]) -> Dict[str, pd.DataFrame]:
    """
    从本地目录读取 GTFS 原始 CSV 文件（ZIP 之外的目录输入）。
    """
    result = {}
    for f in Path(dirpath).glob('*.txt'):
        try:
            df = pd.read_csv(f, encoding='utf-8', low_memory=False)
        except UnicodeDecodeError:
            df = pd.read_csv(f, encoding='latin-1', low_memory=False)
        result[f.stem] = df
    return result

def read_date(plugin_path: Path) -> pd.DataFrame:
    """
    读取预定义的日历信息 (Calendrier.txt)。
    Input Schema: N/A
    Output Schema: [Date_GTFS, Type_Jour, Semaine, Mois, Annee, ...]
    """
    p = Path(plugin_path) / "Resources" / "Calendrier.txt"
    dates = pd.read_csv(p, encoding="utf-8", sep="\t", parse_dates=['Date_Num'])
    drop_cols = ['Date_Num', 'Date_Opendata', 'Ferie', 'Vacances_A', 'Vacances_B', 'Vacances_C',
                 'Concat_Select_Type_A', 'Concat_Select_Type_B', 'Concat_Select_Type_C', 
                 'Type_Jour_IDF', 'Annee_Scolaire']
    dates.drop(columns=drop_cols, errors='ignore', inplace=True)
    return dates

def read_validite(plugin_path: Path) -> pd.DataFrame:
    """
    读取有效期对应关系 (Correspondance_Validite.txt)。
    Input Schema: N/A
    Output Schema: [valid_01, valid, ...]
    """
    p = Path(plugin_path) / "Resources" / "Correspondance_Validite.txt"
    return pd.read_csv(p, sep=';', dtype={'valid_01': str, 'valid': 'int32'})

def read_input(dirpath: Union[str, Path], plugin_path: Path) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """
    一键读取 GTFS 目录及辅助资源表。
    Input Schema: N/A
    Output Schema (Tuple): (Normed_Dict, Dates_DataFrame, Validite_DataFrame)
    """
    raw_dict = rawgtfs(dirpath)
    
    normed = gtfs_normalize(raw_dict)
    dates = read_date(plugin_path)
    validite = read_validite(plugin_path)
    return normed, dates, validite

def gtfs_normalize(raw_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    规范化流程总控制器。
    Input Schema (Dict): {"agency": df, "routes": df, "stops": df, "trips": df, "stop_times": df,
                          "calendar": df (optional), "calendar_dates": df (optional)}
    Output Schema (Dict): {"agency": df, "routes": df, "stops": df, "trips": df, "stop_times": df,
                           "calendar": df|None, "calendar_dates": df,
                           "route_id_coor": df, "trip_id_coor": df, "ser_id_coor": df,
                           "initial_na": str, "final_na_time_col": int}
    """
    agency = agency_norm(raw_dict.get('agency', pd.DataFrame()))
    routes = routes_norm(raw_dict.get('routes', pd.DataFrame()))
    stops = stops_norm(raw_dict.get('stops', pd.DataFrame()))
    trips = trips_norm(raw_dict.get('trips', pd.DataFrame()))
    st_processed, st_msg, st_na = stop_times_norm(raw_dict.get('stop_times', pd.DataFrame()))

    # ID 映射准备
    route_coor = routes[['route_id', 'id_ligne_num']]
    trip_coor = trips[['trip_id', 'id_course_num']]

    # 关联映射
    trips = trips.merge(route_coor, on='route_id').drop('route_id', axis=1)

    # 服务 ID 映射
    ser_id_coor = pd.DataFrame({'service_id': trips.dropna(subset=['service_id'])['service_id'].unique()})
    ser_id_coor['id_service_num'] = np.arange(1, len(ser_id_coor) + 1)
    trips = trips.merge(ser_id_coor, on='service_id', how='left')

    st_processed = st_processed.merge(trip_coor, on='trip_id').drop('trip_id', axis=1)

    # Calendar 规范化 (try/except，空表 → None，参见 legacy 352-358)
    try:
        raw_cal = raw_dict.get('calendar', pd.DataFrame())
        if raw_cal.empty:
            calendar = None
        else:
            calendar = calendar_norm(raw_cal)
            calendar = calendar.merge(ser_id_coor, on='service_id').drop(columns=['service_id'])
            if calendar.empty:
                calendar = None
    except Exception:
        calendar = None

    # Calendar dates 规范化
    raw_caldates = raw_dict.get('calendar_dates', pd.DataFrame())
    if raw_caldates.empty:
        calendar_dates = pd.DataFrame(columns=['service_id', 'date', 'exception_type', 'id_service_num'])
    else:
        calendar_dates = cal_dates_norm(raw_caldates)
        calendar_dates = calendar_dates.merge(ser_id_coor, on='service_id', how='left')

    # Shapes (optionnel, transmis tel quel pour corr_sl_shape / kcc, 参见 legacy 362-378)
    shapes = raw_dict.get('shapes', None)
    if shapes is not None and shapes.empty:
        shapes = None

    return {
        'agency': agency,
        'routes': routes,
        'stops': stops,
        'trips': trips,
        'stop_times': st_processed,
        'calendar': calendar,
        'calendar_dates': calendar_dates,
        'shapes': shapes,
        'route_id_coor': route_coor,
        'trip_id_coor': trip_coor,
        'ser_id_coor': ser_id_coor,
        'initial_na': st_msg,
        'final_na_time_col': st_na
    }

if __name__ == '__main__':
    # 简易测试代码可以在此添加
    print("gtfs_norm module loaded.")
