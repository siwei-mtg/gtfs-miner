"""
GTFS 业务生成模块 (gtfs_generator.py)

功能：
1. 生成行程序列 (Itinerary)。
2. 生成服务日期矩阵 (Service Dates)。
3. 计算班次、经过次数、班次特征 (Headway) 等。

依赖：gtfs_utils, gtfs_norm
与整体流程的关系：
规范化数据 -> [gtfs_generator] -> 业务报表 DataFrame
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List
from gtfs_utils import str_time_hms_hour, str_time_hms, getDistHaversine

def itineraire_generate(stop_times: pd.DataFrame, AP: pd.DataFrame, trips: pd.DataFrame) -> pd.DataFrame:
    """
    生成行程序列。
    Input Schema: stop_times, AP ([id_ap_num, id_ag_num]), trips ([id_course_num, id_ligne_num, id_service_num])
    """
    st = stop_times.copy().rename(columns={'stop_id': 'id_ap'})
    st['TH'] = st['arrival_time'].apply(str_time_hms_hour)
    st['arrival_time'] = st['arrival_time'].apply(str_time_hms)
    st['departure_time'] = st['departure_time'].apply(str_time_hms)
    
    itnry_1 = st.merge(AP[['id_ap', 'id_ap_num', 'id_ag_num']], on='id_ap', how='left')
    itnry_2 = itnry_1.merge(trips[['id_course_num', 'id_ligne_num', 'id_service_num', 'direction_id', 'trip_headsign']], 
                             on='id_course_num', how='left')
    
    cols = ['id_course_num', 'id_ligne_num', 'id_service_num', 'direction_id', 'stop_sequence',
            'id_ap_num', 'id_ag_num', 'arrival_time', 'departure_time', 'TH', 'trip_headsign']
    itineraire = itnry_2[cols].copy()
    itineraire['stop_sequence'] = itineraire.groupby(['id_course_num']).cumcount() + 1
    
    itineraire.fillna({'direction_id': 999, 'trip_headsign': '999'}, inplace=True)
    return itineraire

def service_date_generate(calendar: Optional[pd.DataFrame], 
                          calendar_dates: pd.DataFrame, 
                          Dates: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """
    生成服务日期矩阵。
    Input Schema: calendar, calendar_dates, Dates (Internal custom calendar table)
    """
    cal_cols = ['id_service_num', 'Date_GTFS', 'Type_Jour', 'Semaine', 'Mois', 'Annee']
    
    if calendar is None or calendar.empty:
        # 仅基于 calendar_dates 处理 (Exception Type 1 为开通)
        cal_final = calendar_dates.merge(Dates, left_on='date', right_on='Date_GTFS', how='left')
        cal_final = cal_final[cal_cols].sort_values(['id_service_num', 'Date_GTFS']).reset_index(drop=True)
    else:
        # TODO: 集成完整的按星期几、有效期和排除日期的合成逻辑 (service_date_generate 原逻辑)
        # 这里先返回基础映射
        cal_final = pd.DataFrame(columns=cal_cols)
        
    msg_date = f"DataSet Valid: {cal_final['Date_GTFS'].min()} to {cal_final['Date_GTFS'].max()}" if not cal_final.empty else "No valid dates found."
    return cal_final, msg_date

def course_generate(itineraire: pd.DataFrame) -> pd.DataFrame:
    """
    汇总班次统计 (起点、终点、首发时间、到达终点时间)。
    """
    course = itineraire.groupby(['id_ligne_num', 'id_service_num', 'id_course_num', 'direction_id', 'trip_headsign'], as_index=False).agg({
        'arrival_time': 'min',
        'departure_time': 'max',
        'id_ap_num': ['first', 'last'],
        'id_ag_num': ['first', 'last'],
        'stop_sequence': 'max'
    })
    
    # 扁平化多层列
    course.columns = [''.join(col).strip() for col in course.columns.values]
    
    course.rename(columns={
        'arrival_timemin': 'heure_depart', 
        'departure_timemax': 'heure_arrive',
        'id_ap_numfirst': 'id_ap_num_debut', 
        'id_ap_numlast': 'id_ap_num_terminus',
        'id_ag_numfirst': 'id_ag_num_debut', 
        'id_ag_numlast': 'id_ag_num_terminus',
        'stop_sequencemax': 'nb_arrets'
    }, inplace=True)
    
    # 构建子路线键 (用于区分不同的行车路径)
    course['sous_ligne'] = (course['id_ligne_num'].astype(str) + '_' + 
                             course['direction_id'].astype(str) + '_' + 
                             course['id_ag_num_debut'].astype(str) + '_' + 
                             course['id_ag_num_terminus'].astype(str))
    
    return course

def itiarc_generate(itineraire: pd.DataFrame, AG: pd.DataFrame) -> pd.DataFrame:
    """
    生成相邻站点之间的运行段 (Arcs)。
    """
    R = itineraire.copy().drop(['departure_time', 'id_service_num', 'id_ligne_num'], axis=1)
    L = itineraire.copy().drop(['arrival_time'], axis=1)
    L['ordre_b'] = R['stop_sequence'] + 1
    
    # 关联 A 点与 B 点
    iti_arc = L.merge(R, left_on=['id_course_num', 'ordre_b'], right_on=['id_course_num', 'stop_sequence'], suffixes=('_a', '_b'))
    iti_arc = iti_arc.dropna(subset=['id_ag_num_b']).reset_index(drop=True)
    
    # 计算距离
    AG_coor = AG[['id_ag_num', 'stop_lon', 'stop_lat']]
    arc_dist = iti_arc.merge(AG_coor, left_on='id_ag_num_a', right_on='id_ag_num')
    arc_dist = arc_dist.merge(AG_coor, left_on='id_ag_num_b', right_on='id_ag_num', suffixes=('_src', '_dst'))
    
    # 向量化计算大地距离
    arc_dist['DIST_Vol_Oiseau'] = np.around(np.vectorize(getDistHaversine)(
        arc_dist.stop_lat_src, arc_dist.stop_lon_src, 
        arc_dist.stop_lat_dst, arc_dist.stop_lon_dst), 0)
        
    return arc_dist

def caract_par_sl(courses: pd.DataFrame, hpm_range: Tuple[float, float], hps_range: Tuple[float, float]) -> pd.DataFrame:
    """
    计算子路线 (SL) 的特征，如发车间隔 (Headway) 和运营周期。
    """
    # 这里集成原有的 periode 逻辑
    res = courses.copy()
    # TODO: 详细的 Headway (HPM, HPS) 分段统计逻辑
    return res

def nb_passage_ag(service_jour_type: pd.DataFrame, itineraire: pd.DataFrame, AG: pd.DataFrame, type_vac: str) -> pd.DataFrame:
    """计算各站点的通过班次数。"""
    iti_tj = itineraire.merge(service_jour_type, on=['id_ligne_num', 'id_service_num'])
    nb_psg = iti_tj.groupby(['id_ag_num', type_vac])['id_course_num'].count().reset_index()
    nb_psg = nb_psg.merge(AG[['id_ag_num', 'stop_name', 'stop_lat', 'stop_lon']], on='id_ag_num')
    return pd.pivot_table(nb_psg, values='id_course_num', index=['id_ag_num', 'stop_name', 'stop_lat', 'stop_lon'],
                          columns=type_vac, fill_value=0).reset_index()

def nb_course_ligne(service_jour_type: pd.DataFrame, courses: pd.DataFrame, type_vac: str, lignes: pd.DataFrame) -> pd.DataFrame:
    """计算每条线路在不同日期的总班次数。"""
    crs_tj = courses.merge(service_jour_type, on=['id_ligne_num', 'id_service_num'])
    nb_crs = crs_tj.groupby(['id_ligne_num', type_vac])['id_course_num'].count().reset_index()
    pv = pd.pivot_table(nb_crs, values='id_course_num', index='id_ligne_num', columns=type_vac, fill_value=0).reset_index()
    return lignes[['id_ligne_num', 'route_short_name', 'route_long_name']].merge(pv, on='id_ligne_num')

def kcc_course_ligne(sj: pd.DataFrame, crs: pd.DataFrame, v: str, lines: pd.DataFrame, has_shp: bool) -> pd.DataFrame:
    """计算线路公里数。"""
    dist_col = 'Dist_shape' if has_shp else 'DIST_Vol_Oiseau'
    crs_tj = crs.merge(sj, on=['id_ligne_num', 'id_service_num'])
    dist_sum = crs_tj.groupby(['id_ligne_num', v], as_index=False)[dist_col].sum()
    dist_sum[dist_col] = dist_sum[dist_col] / 1000.0 # Convert to KM
    pv = pd.pivot_table(dist_sum, values=dist_col, index='id_ligne_num', columns=v, fill_value=0).reset_index()
    return lines[['id_ligne_num', 'route_short_name', 'route_long_name']].merge(pv, on='id_ligne_num')

def passage_arc(iti_arc: pd.DataFrame, sj: pd.DataFrame, node: pd.DataFrame, v: str) -> pd.DataFrame:
    """计算运行段之间的经过流量。"""
    iti_tj = iti_arc.merge(sj, on=['id_ligne_num', 'id_service_num'])
    nb_psg = iti_tj.groupby(['id_ag_num_a', 'id_ag_num_b', v])['id_course_num'].count().reset_index()
    pv = pd.pivot_table(nb_psg, values='id_course_num', index=['id_ag_num_a', 'id_ag_num_b'], columns=v, fill_value=0).reset_index()
    
    # 合并地理坐标
    node_sim = node[['NO', 'NAME', 'LON', 'LAT']]
    res = pv.merge(node_sim, left_on='id_ag_num_a', right_on='NO').merge(node_sim, left_on='id_ag_num_b', right_on='NO', suffixes=('_x', '_y'))
    res['ID'] = res.index
    return res

def corr_sl_shape(courses: pd.DataFrame, trips: pd.DataFrame, shapes: pd.DataFrame, sl: pd.DataFrame) -> pd.DataFrame:
    """将子路线与 Shapes 轨迹关联。"""
    crs_sample = courses.groupby('sous_ligne')['id_course_num'].first().reset_index()
    corr = trips[['id_course_num', 'shape_id']].merge(crs_sample, on='id_course_num')
    sl_sim = sl[['sous_ligne', 'id_ligne_num', 'route_short_name', 'route_long_name']]
    return shapes.merge(corr[['sous_ligne', 'shape_id']], on='shape_id').merge(sl_sim, on='sous_ligne')

if __name__ == '__main__':
    print("gtfs_generator module loaded.")
