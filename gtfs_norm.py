"""
GTFS 标准化模块 (gtfs_norm.py)

功能：
1. 清洗与转换 GTFS 原始表 (Agency, Stops, Routes, Trips, Stop_times, Calendar)。
2. 核心 Schema 校验与列重命名。

与整体流程的关系：
输入原始字典 -> [gtfs_norm] -> 规范化字典
"""

import numpy as np
import pandas as pd
import chardet
from zipfile import ZipFile
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List, Union
from scipy.cluster.vq import kmeans2
from gtfs_utils import norm_upper_str, nan_in_col_workaround, encoding_guess

def agency_norm(raw_agency: pd.DataFrame) -> pd.DataFrame:
    """
    Input Schema: [agency_name, agency_url, ...]
    """
    agency_v = pd.DataFrame(columns=['agency_id', 'agency_name', 'agency_url', 'agency_timezone',
                                      'agency_lang', 'agency_phone', 'agency_fare_url', 'agency_email'])
    agency = pd.concat([agency_v, raw_agency], ignore_index=True)
    agency.dropna(axis=1, how='all', inplace=True)
    return agency

def stops_norm(raw_stops: pd.DataFrame) -> pd.DataFrame:
    """
    规范化停车点数据。
    Input Schema: [stop_id, stop_name, stop_lat, stop_lon, location_type, parent_station]
    """
    stops_v = pd.DataFrame(columns=['stop_id', 'stop_code', 'stop_name', 'stop_desc',
                                     'stop_lat', 'stop_lon', 'zone_id', 'stop_url','location_type', 
                                     'parent_station', 'stop_timezone','wheelchair_boarding',
                                     'level_id','platform_code'])
    stops = pd.concat([stops_v, raw_stops], ignore_index=True)
    stops.stop_name = norm_upper_str(stops.stop_name)
    stops.stop_id = nan_in_col_workaround(stops.stop_id)
    
    # 坐标转换与容错
    for col in ['stop_lat', 'stop_lon']:
        stops[col] = pd.to_numeric(stops[col].astype(str).str.strip(), errors='coerce').fillna(0).astype(np.float32)
    
    stops.stop_name = norm_upper_str(stops.stop_name)
    stops.location_type = stops.location_type.fillna(0).astype(np.int8)
    stops.parent_station = nan_in_col_workaround(stops.parent_station)
    
    essentials = ['stop_id','stop_lat','stop_lon','stop_name','location_type','parent_station']
    return stops[essentials]

def routes_norm(raw_routes: pd.DataFrame) -> pd.DataFrame:
    """
    Input Schema: [route_id, route_type, ...]
    """
    routes_v = pd.DataFrame(columns=['route_id', 'agency_id', 'route_short_name', 'route_long_name',
                                      'route_desc', 'route_type', 'route_url', 'route_color',
                                      'route_text_color', 'route_sort_order'])
    routes = pd.concat([routes_v, raw_routes], ignore_index=True)
    routes.drop(['route_url', 'route_sort_order'], axis=1, errors='ignore', inplace=True)
    routes.dropna(axis=1, how='all', inplace=True)
    routes.route_id = routes.route_id.astype(str)
    routes.route_type = pd.to_numeric(routes.route_type, errors='coerce').fillna(3).astype(np.int8) # Default BUS
    routes['id_ligne_num'] = np.arange(1, len(routes) + 1)
    return routes

def ligne_generate(raw_routes: pd.DataFrame) -> pd.DataFrame:
    """
    解析线路类型 (公交, 地铁, 火车等)。
    """
    types_map = pd.DataFrame({
        'route_type': [0, 1, 2, 3, 4, 5, 6, 7, 11, 12],
        'mode': ["tramway", "metro", "train", "bus", "ferry", "cable", "telephe", "funiculaire", "trolley", "monorail"]
    })
    return raw_routes.merge(types_map, on='route_type', how='left').dropna(axis=1, how='all')

def trips_norm(raw_trips: pd.DataFrame) -> pd.DataFrame:
    """
    Input Schema: [route_id, service_id, trip_id]
    """
    trips_v = pd.DataFrame(columns=['route_id', 'service_id', 'trip_id', 'trip_headsign', 
                                     'direction_id', 'shape_id'])
    trips = pd.concat([trips_v, raw_trips], ignore_index=True)
    cols = ['route_id', 'service_id', 'trip_id']
    trips[cols] = trips[cols].astype(str)
    if not trips.empty:
        trips['id_course_num'] = np.arange(1, len(trips) + 1)
    return trips

def stop_times_norm(raw_stoptimes: pd.DataFrame) -> Tuple[pd.DataFrame, str, int]:
    """
    规范化停靠时间并处理缺失值。
    Return: (DataFrame, NA_Summary_String, NA_Count_in_Time_Cols)
    """
    stop_times_v = pd.DataFrame(columns=['trip_id', 'arrival_time', 'departure_time','stop_id', 
                                          'stop_sequence', 'timepoint'])
    stop_times = pd.concat([stop_times_v, raw_stoptimes], ignore_index=True)
    
    # 统计缺失值
    na_summary = f"Total: {len(stop_times)}. NAs: {stop_times.isna().sum().to_dict()}"
    
    # 时间列清洗逻辑 (简化版，保留原逻辑)
    time_cols = ['arrival_time', 'departure_time']
    time_na_count = stop_times[time_cols].isna().sum().sum()
    
    if time_na_count > 0:
        # 如果是 timepoint 模式，尝试填充
        stop_times.loc[:, time_cols] = stop_times.groupby('trip_id')[time_cols].transform(lambda x: x.ffill().bfill())
        
    stop_times[['trip_id', 'stop_id']] = stop_times[['trip_id', 'stop_id']].astype(str)
    stop_times['stop_sequence'] = pd.to_numeric(stop_times['stop_sequence'], errors='coerce').fillna(0).astype(np.int32)
    
    return stop_times, na_summary, int(stop_times[time_cols].isna().sum().sum())

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

def read_date(plugin_path: Union[str, Path]) -> pd.DataFrame:
    """读取预定义的日历信息 (Calendrier.txt)。"""
    p = Path(plugin_path) / "Resources" / "Calendrier.txt"
    dates = pd.read_csv(p, encoding="utf-8", sep="\t", parse_dates=['Date_Num'])
    drop_cols = ['Date_Num', 'Date_Opendata', 'Ferie', 'Vacances_A', 'Vacances_B', 'Vacances_C',
                 'Concat_Select_Type_A', 'Concat_Select_Type_B', 'Concat_Select_Type_C', 
                 'Type_Jour_IDF', 'Annee_Scolaire']
    dates.drop(columns=drop_cols, errors='ignore', inplace=True)
    return dates

def read_validite(plugin_path: Union[str, Path]) -> pd.DataFrame:
    """读取有效期对应关系 (Correspondance_Validite.txt)。"""
    p = Path(plugin_path) / "Resources" / "Correspondance_Validite.txt"
    return pd.read_csv(p, sep=';', dtype={'valid_01': str, 'valid': 'int32'})

def read_input(dirpath: Union[str, Path], plugin_path: Union[str, Path]) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """
    一键读取 GTFS 目录及辅助资源表。
    """
    # 模拟 rawgtfs 逻辑
    raw_dict = {}
    p = Path(dirpath)
    for f in p.glob('*.txt'):
        raw_dict[f.stem] = pd.read_csv(f)
    
    normed = gtfs_normalize(raw_dict)
    dates = read_date(plugin_path)
    validite = read_validite(plugin_path)
    return normed, dates, validite

def ag_ap_generate_bigvolume(raw_stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    针对大数据量的 K-Means 聚类生成逻辑。
    """
    AP = raw_stops.loc[raw_stops.location_type == 0, :].reset_index(drop=True)
    if AP.empty: return AP, pd.DataFrame()
    
    # 粗聚类
    coor = AP[['stop_lon', 'stop_lat']].to_numpy()
    k = max(1, round(len(coor) / 500))
    _, labels = kmeans2(coor, k, minit='points')
    AP['kmean_id'] = labels
    
    # 子簇细化逻辑在此处省略，目前返回粗聚类结果
    AP['id_ag'] = AP['kmean_id'].astype(str)
    AG = AP.groupby('id_ag', as_index=False).agg({
        'stop_name': 'first', 'stop_lat': 'mean', 'stop_lon': 'mean'
    })
    AG['id_ag_num'] = np.arange(1, len(AG) + 1) + 10000
    AP = AP.merge(AG[['id_ag', 'id_ag_num']], on='id_ag')
    AP['id_ap_num'] = np.arange(1, len(AP) + 1) + 100000
    
    return AP, AG

def gtfs_normalize(raw_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    规范化流程总控制器。
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
    st_processed = st_processed.merge(trip_coor, on='trip_id').drop('trip_id', axis=1)
    
    return {
        'agency': agency,
        'routes': routes,
        'stops': stops,
        'trips': trips,
        'stop_times': st_processed,
        'route_id_coor': route_coor,
        'trip_id_coor': trip_coor,
        'initial_na': st_msg,
        'final_na_time_col': st_na
    }

if __name__ == '__main__':
    # 简易测试代码可以在此添加
    print("gtfs_norm module loaded.")
