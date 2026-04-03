"""
GTFS 结果导出模块 (gtfs_export.py)

功能：
1. 报表最终格式化 (MEF - Mise En Forme)。
2. 生成供 QGIS 插件显示或导出的展示层 DataFrame。

依赖：gtfs_utils, gtfs_norm
与整体流程的关系：
```plaintext
业务结果 -> [gtfs_export] -> 格式化聚合
                            -> 重构列名与格式
                            -> 最终呈现 CSV/表格 DataFrame
```
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from .gtfs_utils import heure_from_xsltime, heure_from_xsltime_vec

def MEF_ligne(lignes: pd.DataFrame, courses: pd.DataFrame, AG: pd.DataFrame) -> pd.DataFrame:
    """
    格式化线路统计输出。
    Input Schema: 
        lignes: [id_ligne_num, route_short_name, ...]
        courses: [direction_id, id_ligne_num, id_ag_num_debut, id_ag_num_terminus, id_course_num, ...]
        AG: [id_ag_num, stop_name, ...]
    Output Schema: [id_ligne_num, route_short_name, Origin, Destination, ...]
    """
    # 提取线路的主要起点与终点 (OD)
    crs_1dir = courses[courses['direction_id'] == 0]
    if crs_1dir.empty:
        return lignes.copy()
        
    ligne_od = crs_1dir.groupby(['id_ligne_num', 'id_ag_num_debut', 'id_ag_num_terminus'])['id_course_num'].count().reset_index()
    
    # 找到班次最多的 OD
    idx = ligne_od.groupby(['id_ligne_num'])['id_course_num'].idxmax()
    od_main = ligne_od.loc[idx][['id_ligne_num', 'id_ag_num_debut', 'id_ag_num_terminus']]
    
    # 填充名称
    AG_map = AG[['id_ag_num', 'stop_name']]
    od_main = od_main.merge(AG_map, left_on='id_ag_num_debut', right_on='id_ag_num').rename(columns={'stop_name': 'Origin'})
    od_main = od_main.merge(AG_map, left_on='id_ag_num_terminus', right_on='id_ag_num').rename(columns={'stop_name': 'Destination'})
    
    return lignes.merge(od_main[['id_ligne_num', 'Origin', 'Destination']], on='id_ligne_num', how='left')

def MEF_course(courses: pd.DataFrame, trip_id_coor: pd.DataFrame) -> pd.DataFrame:
    """
    格式化班次属性导出。
    Input Schema: 
        courses: [id_course_num, id_ligne_num, sous_ligne, id_service_num, direction_id, heure_depart, heure_arrive, id_ap_num_debut, id_ap_num_terminus, id_ag_num_debut, id_ag_num_terminus, nb_arrets, ...]
        trip_id_coor: [id_course_num, trip_id, ...]
    Output Schema: [trip_id, id_course_num, id_ligne_num, sous_ligne, id_service_num, direction_id, heure_depart, heure_arrive, id_ap_num_debut, id_ap_num_terminus, id_ag_num_debut, id_ag_num_terminus, nb_arrets]
    """
    export_cols = ['trip_id', 'id_course_num', 'id_ligne_num', 'sous_ligne', 'id_service_num',
                   'direction_id', 'heure_depart', 'h_dep_num', 'heure_arrive', 'h_arr_num',
                   'id_ap_num_debut', 'id_ap_num_terminus', 'id_ag_num_debut', 'id_ag_num_terminus',
                   'nb_arrets', 'DIST_Vol_Oiseau']
    
    res = courses.merge(trip_id_coor, left_on='id_course_num', right_on='id_course_num')
    res = res.rename(columns={'heure_depart': 'h_dep_num', 'heure_arrive': 'h_arr_num'})
    
    # 时间数字化转 HH:MM (向量化，参见 OPTIMIZATION_REPORT §5.1)
    res['heure_depart'] = heure_from_xsltime_vec(res['h_dep_num'])
    res['heure_arrive'] = heure_from_xsltime_vec(res['h_arr_num'])

    return res[export_cols]

def MEF_iti(itineraire: pd.DataFrame, courses: pd.DataFrame) -> pd.DataFrame:
    """
    格式化完整的停靠时间点详细。
    Input Schema: 
        itineraire: [id_course_num, stop_sequence, arrival_time, departure_time, ...]
        courses: [id_course_num, sous_ligne, ...]
    Output Schema: [id_course_num, sous_ligne, ordre, h_dep_num, h_arr_num, heure_depart, heure_arrive, ...]
    """
    iti = itineraire.drop(['trip_headsign'], axis=1, errors='ignore').rename(columns={
        'stop_sequence': 'ordre',
        'arrival_time': 'h_dep_num',
        'departure_time': 'h_arr_num'
    })
    
    iti['heure_depart'] = heure_from_xsltime_vec(iti['h_dep_num'])
    iti['heure_arrive'] = heure_from_xsltime_vec(iti['h_arr_num'])
    
    crs_sl = courses[['id_course_num', 'sous_ligne']]
    return crs_sl.merge(iti, on='id_course_num', how='right')

def MEF_iti_arc(itineraire_arc: pd.DataFrame, courses: pd.DataFrame) -> pd.DataFrame:
    """
    格式化运行段导出。
    Input Schema: 
        itineraire_arc: [id_course_num, id_ligne_num, id_service_num, direction_id, ordre_a, heure_depart, heure_arrive, id_ap_num_a, id_ag_num_a, TH_a, ordre_b, id_ap_num_b, id_ag_num_b, TH_b, DIST_Vol_Oiseau, ...]
        courses: [id_course_num, sous_ligne, ...]
    Output Schema: [id_course_num, sous_ligne, id_ligne_num, id_service_num, direction_id, ordre_a, h_dep_num, h_arr_num, heure_depart, heure_arrive, id_ap_num_a, id_ag_num_a, TH_a, ordre_b, id_ap_num_b, id_ag_num_b, TH_b, DIST_Vol_Oiseau, ...]
    """
    itiarc_cols = ['id_course_num', 'id_ligne_num', 'id_service_num', 'direction_id',
                    'ordre_a', 'heure_depart', 'h_dep_num', 'heure_arrive', 'h_arr_num', 
                    'id_ap_num_a', 'id_ag_num_a', 'TH_a', 'ordre_b', 'id_ap_num_b', 
                    'id_ag_num_b', 'TH_b', 'DIST_Vol_Oiseau']
    
    res = itineraire_arc.rename(columns={'heure_depart': 'h_dep_num', 'heure_arrive': 'h_arr_num'})
    res['heure_depart'] = heure_from_xsltime_vec(res['h_dep_num'])
    res['heure_arrive'] = heure_from_xsltime_vec(res['h_arr_num'])

    iti_arc = res[itiarc_cols]
    crs_sl = courses[['id_course_num', 'sous_ligne']]
    return crs_sl.merge(iti_arc, on='id_course_num', how='right')

def MEF_serdate(service_dates: pd.DataFrame, ser_id_coor: pd.DataFrame) -> pd.DataFrame:
    """格式化服务日期表导出。"""
    cols = ['service_id', 'id_service_num', 'Date_GTFS', 'Type_Jour', 'Mois', 'Annee']
    return service_dates.merge(ser_id_coor, on='id_service_num')[cols]

def MEF_servjour(service_jour_type: pd.DataFrame, route_id_coor: pd.DataFrame, ser_id_coor: pd.DataFrame, type_vac: str) -> pd.DataFrame:
    """格式化服务日类型导出。"""
    cols = ['id_ligne_num', 'service_id', 'id_service_num', 'Date_GTFS', type_vac]
    return service_jour_type.merge(ser_id_coor, on='id_service_num')[cols]

def trace_sl_vol_oiseau(iti: pd.DataFrame, AG: pd.DataFrame, sl: pd.DataFrame) -> pd.DataFrame:
    """
    为没有 Shape 的子路线生成直连轨迹数据。
    """
    crs_sample = iti.groupby('sous_ligne')['id_course_num'].first().reset_index()
    iti_sample = iti.merge(crs_sample, on='id_course_num')
    res = iti_sample.merge(AG[['id_ag_num', 'stop_lon', 'stop_lat']], on='id_ag_num')
    sl_sim = sl[['sous_ligne', 'route_short_name', 'route_long_name']]
    return res.merge(sl_sim, on='sous_ligne').sort_values(['id_course_num', 'ordre'])

if __name__ == '__main__':
    print("gtfs_export module loaded.")
