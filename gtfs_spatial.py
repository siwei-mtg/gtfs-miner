"""
GTFS 空间分析模块 (gtfs_spatial.py)

功能：
1. 停车点聚类 (Agglomerative Clustering / K-Means)。
2. 停车点与父站点 (AG/AP) 的重构与生成。

与整体流程的关系：
输入规范化的 Stops -> [gtfs_spatial] -> 包含 AG/AP 映射的 DataFrame
"""

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.cluster.vq import kmeans2
from typing import Tuple, Dict
from gtfs_utils import distmatrice, getDistHaversine

def ag_ap_generate_hcluster(raw_stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    通过层次聚类生成父站点 (AG/AP)。
    Input Schema: [stop_id, stop_name, stop_lat, stop_lon, location_type]
    """
    AP = raw_stops.loc[raw_stops.location_type == 0, :].reset_index(drop=True)
    if AP.empty:
        return AP, pd.DataFrame()
        
    AP_coor = AP[['stop_lon', 'stop_lat']].to_numpy()
    dist_mat = distmatrice(AP_coor)
    
    # 层次聚类，高度 100 对应约 100 米
    Z = linkage(dist_mat, method='complete')
    cut = cut_tree(Z, height=100)
    
    AP['id_ag'] = (cut + 1).astype(str)
    AP['id_ag_num'] = cut.flatten() + 10000
    AP['id_ap_num'] = np.arange(1, len(AP) + 1) + 100000
    
    AP = AP.rename(columns={'stop_id': 'id_ap'})

    AG = AP.groupby(['id_ag', 'id_ag_num'], as_index=False).agg({
        'stop_name': 'first',
        'stop_lat': 'mean',
        'stop_lon': 'mean'
    }).reset_index(drop=True)
    
    return AP, AG

def ag_ap_generate_asit(raw_stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    根据原始 parent_station 生成 AG/AP。
    Input Schema: [stop_id, stop_name, stop_lat, stop_lon, location_type, parent_station]
    """
    # 提取所有 AG (location_type=1)
    AG = raw_stops.loc[raw_stops.location_type == 1].copy()
    AG = AG.drop(['parent_station', 'location_type'], axis=1, errors='ignore')
    AG = AG.rename(columns={'stop_id': 'id_ag'})
    
    AG = AG.groupby(['id_ag'], as_index=False).agg({
        'stop_name': 'first',
        'stop_lat': 'mean',
        'stop_lon': 'mean'
    }).reset_index(drop=True)
    AG['id_ag_num'] = np.arange(1, len(AG) + 1) + 10000
    
    # 提取所有 AP (location_type=0)
    AP = raw_stops.loc[raw_stops.location_type == 0].copy()
    AP = AP.drop(['location_type'], axis=1, errors='ignore')
    AP = AP.rename(columns={'stop_id': 'id_ap', 'parent_station': 'id_ag'})
    AP['id_ap_num'] = np.arange(1, len(AP) + 1) + 100000
    
    AP = AP.merge(AG[['id_ag', 'id_ag_num']], on='id_ag', how='left')
    return AP, AG

def ag_ap_generate_reshape(raw_stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    自适应重构 AG/AP。
    逻辑：若无 ParentStation 则聚类；若有则根据数量决定聚类算法。
    """
    nb_types = len(raw_stops.location_type.unique())
    ap_no_parent = raw_stops[raw_stops['location_type'] == 0]['parent_station'].isnull().sum()
    
    if nb_types == 1 or ap_no_parent > 0:
        # TODO: 集成 bigvolume (K-Means) 逻辑
        AP, AG = ag_ap_generate_hcluster(raw_stops)
        marker = 'cluster_method'
    else:
        AP, AG = ag_ap_generate_asit(raw_stops)
        marker = 'original_parent_station'
        
    return AP, AG, marker

if __name__ == '__main__':
    print("gtfs_spatial module loaded.")
