"""
GTFS 空间分析模块 (gtfs_spatial.py)

功能：
1. 停车点聚类 (Agglomerative Clustering / K-Means)。
2. 停车点与父站点 (AG/AP) 的重构与生成。

与整体流程的关系：
```plaintext
规范化 Stops 数据 -> 判断 Parent Station 覆盖度
                  -> [包含足够 Parent Station] -> 按层级生成 AG/AP (asit算法)
                  -> [缺少 Parent Station] -> 层级聚类/Kmeans 生成 AG/AP
                  -> 包含聚类归属与重构 ID 的 DataFrame
```
"""

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.cluster.vq import kmeans2
from sklearn.cluster import DBSCAN
from typing import Protocol, Tuple, Dict
from .gtfs_utils import distmatrice, getDistHaversine
from .gtfs_schemas import APSchema, AGSchema
from .constants import (
    BIG_VOLUME_THRESHOLD,
    KMEANS_CHUNK_DIVISOR,
    STOP_MERGE_RADIUS_METERS,
    EARTH_RADIUS_METERS,
)


class ClusteringStrategy(Protocol):
    """
    Strategy protocol for AG/AP generation algorithms.
    Implement this to add a new clustering approach without modifying ag_ap_generate_reshape().
    """
    marker: str

    def cluster(self, stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]: ...


class BigVolumeStrategy:
    """Two-phase K-Means + hierarchical clustering for large datasets (>= 5000 stops)."""
    marker = 'cluster_method'

    def cluster(self, stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        return ag_ap_generate_bigvolume(stops)


class HClusterStrategy:
    """DBSCAN-based clustering for small/medium datasets (< 5000 stops)."""
    marker = 'cluster_method'

    def cluster(self, stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        return ag_ap_generate_hcluster(stops)


class AsitStrategy:
    """Uses existing parent_station hierarchy when all stops have a parent."""
    marker = 'original_parent_station'

    def cluster(self, stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        return ag_ap_generate_asit(stops)


def select_strategy(raw_stops: pd.DataFrame) -> ClusteringStrategy:
    """
    Factory: inspect raw_stops and return the appropriate ClusteringStrategy.
    To add a new algorithm: implement ClusteringStrategy, add a branch here.
    """
    nb_types    = len(raw_stops['location_type'].unique())
    ap_potentiel = len(raw_stops.loc[raw_stops['location_type'] == 0])
    ap_no_parent = raw_stops[raw_stops['location_type'] == 0]['parent_station'].isnull().sum()

    if nb_types > 1 and ap_no_parent == 0:
        return AsitStrategy()
    return BigVolumeStrategy() if ap_potentiel >= BIG_VOLUME_THRESHOLD else HClusterStrategy()


def ag_ap_generate_bigvolume(raw_stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    针对大数据量 (>5000 个站点) 的两阶段聚类：K-Means 粗分组 + 组内层次聚类细化。
    Input Schema: [stop_id, stop_name, stop_lat, stop_lon, location_type, ...]
    Output Schema (Tuple):
        AP: [id_ap, id_ag, id_ag_num, id_ap_num, stop_name, stop_lat, stop_lon, ...]
        AG: [id_ag, id_ag_num, stop_name, stop_lat, stop_lon, ...]
    """
    AP = raw_stops.loc[raw_stops.location_type == 0, :].reset_index(drop=True)
    if AP.empty:
        return AP, pd.DataFrame()

    # 阶段 1: K-Means 粗分组 (每组约 500 站点)
    coor = AP[['stop_lon', 'stop_lat']].to_numpy()
    k = max(1, round(len(coor) / KMEANS_CHUNK_DIVISOR))
    _, labels = kmeans2(coor, k, minit='points')
    AP['kmean_id'] = labels

    # 阶段 2: 各 K-Means 簇内做层次聚类细化 (100 米截断，参见 legacy 424-429)
    AP['clust_id'] = 0
    for i in range(k):
        cluster_mask = AP['kmean_id'] == i
        AP_sub = AP.loc[cluster_mask, ['stop_lat', 'stop_lon']]
        if len(AP_sub) < 2:
            AP.loc[cluster_mask, 'clust_id'] = 0
            continue
        distmat = distmatrice(AP_sub.to_numpy())
        sub_labels = cut_tree(linkage(distmat, method='complete'), height=STOP_MERGE_RADIUS_METERS).flatten()
        AP.loc[cluster_mask, 'clust_id'] = sub_labels

    AP['id_ag'] = AP['kmean_id'].astype(str) + '_' + AP['clust_id'].astype(int).astype(str)
    AP['id_ap_num'] = np.arange(1, len(AP) + 1) + 100000

    AG = AP.groupby('id_ag', as_index=False).agg(
        stop_name=('stop_name', 'first'),
        stop_lat=('stop_lat', 'mean'),
        stop_lon=('stop_lon', 'mean')
    )
    AG['id_ag_num'] = np.arange(1, len(AG) + 1) + 10000

    AP = AP.merge(AG[['id_ag', 'id_ag_num']], on='id_ag')
    AP = AP.rename(columns={'stop_id': 'id_ap'})
    return APSchema.validate(AP), AGSchema.validate(AG)


def ag_ap_generate_hcluster(raw_stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    通过层次聚类生成父站点 (AG/AP)。
    Input Schema: [stop_id, stop_name, stop_lat, stop_lon, location_type, ...]
    Output Schema (Tuple):
        AP: [id_ap, id_ag, id_ag_num, id_ap_num, stop_name, stop_lat, stop_lon, ...]
        AG: [id_ag, id_ag_num, stop_name, stop_lat, stop_lon, ...]
    """
    AP = raw_stops.loc[raw_stops.location_type == 0, :].reset_index(drop=True)
    if AP.empty:
        return AP, pd.DataFrame()
        
    coords_rad = np.radians(AP[['stop_lat', 'stop_lon']].to_numpy())
    labels = DBSCAN(eps=STOP_MERGE_RADIUS_METERS / EARTH_RADIUS_METERS, min_samples=1, metric='haversine', algorithm='ball_tree', n_jobs=-1).fit_predict(coords_rad)
    
    AP['id_ag'] = (labels + 1).astype(str)
    AP['id_ag_num'] = labels + 10000
    AP['id_ap_num'] = np.arange(1, len(AP) + 1) + 100000
    
    AP = AP.rename(columns={'stop_id': 'id_ap'})

    AG = AP.groupby(['id_ag', 'id_ag_num'], as_index=False).agg({
        'stop_name': 'first',
        'stop_lat': 'mean',
        'stop_lon': 'mean'
    }).reset_index(drop=True)
    
    return APSchema.validate(AP), AGSchema.validate(AG)


def ag_ap_generate_asit(raw_stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    根据原始 parent_station 生成 AG/AP。
    Input Schema: [stop_id, stop_name, stop_lat, stop_lon, location_type, parent_station, ...]
    Output Schema (Tuple):
        AP: [id_ap, id_ag, id_ap_num, id_ag_num, stop_name, stop_lat, stop_lon, ...]
        AG: [id_ag, id_ag_num, stop_name, stop_lat, stop_lon, ...]
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
    return APSchema.validate(AP), AGSchema.validate(AG)


def ag_ap_generate_reshape(raw_stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    自适应重构 AG/AP。策略由 select_strategy() 决定，此函数仅负责调度。
    Input Schema: [stop_id, stop_name, stop_lat, stop_lon, location_type, parent_station, ...]
    Output Schema (Tuple):
        AP: [id_ap, ...]
        AG: [id_ag, ...]
        marker: str (cluster_method/original_parent_station)
    """
    strategy = select_strategy(raw_stops)
    AP, AG = strategy.cluster(raw_stops)
    return AP, AG, strategy.marker

if __name__ == '__main__':
    print("gtfs_spatial module loaded.")
