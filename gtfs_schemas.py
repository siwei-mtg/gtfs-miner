"""
GTFS Miner DataFrame Schema 定义模块

功能：
定义核心 DataFrame 的列名、类型和值域约束，
用于模块边界的运行时校验。
"""

import pandera as pa
from pandera import Column, DataFrameSchema, Check

# 注：使用 "Int64" (Pandas Nullable Integer) 替代 standard int/pa.Int64，
# 以便在源数据不一致（如 stop_times 引用了不存在的 stop_id）时，
# 依然保持整型特征而不退化为 float64，同时允许 NaN 存在。
# 注意：必须使用字符串 "Int64" 以触发 pandas 扩展类型，而非 numpy.int64。

# ---- 空间模块输出 (gtfs_spatial) ----

APSchema = DataFrameSchema({
    "id_ap":     Column(str, nullable=False),
    "id_ag":     Column(str, nullable=False),
    "id_ap_num": Column("Int64", Check.ge(100000), nullable=True),
    "id_ag_num": Column("Int64", Check.ge(10000),  nullable=True),
    "stop_name": Column(str, nullable=True),
    "stop_lat":  Column(float, Check.in_range(-90, 90), nullable=True),
    "stop_lon":  Column(float, Check.in_range(-180, 180), nullable=True),
}, coerce=True)

AGSchema = DataFrameSchema({
    "id_ag":     Column(str, nullable=False),
    "id_ag_num": Column("Int64", Check.ge(10000), nullable=True),
    "stop_name": Column(str, nullable=True),
    "stop_lat":  Column(float, Check.in_range(-90, 90), nullable=True),
    "stop_lon":  Column(float, Check.in_range(-180, 180), nullable=True),
}, coerce=True)

# ---- 业务生成模块输出 (gtfs_generator) ----

ItineraireSchema = DataFrameSchema({
    "id_course_num":  Column("Int64", nullable=False),
    "id_ligne_num":   Column("Int64", nullable=False),
    "id_service_num": Column("Int64", nullable=False),
    "direction_id":   Column("Int64", nullable=True),
    "stop_sequence":  Column("Int64", Check.ge(1), nullable=True),
    "id_ap_num":      Column("Int64", nullable=True),
    "id_ag_num":      Column("Int64", nullable=True),
    "arrival_time":   Column(float, nullable=True),
    "departure_time": Column(float, nullable=True),
    "TH":             Column("Int64", nullable=True),
    "trip_headsign":  Column(str, nullable=True),
}, coerce=True)

CourseSchema = DataFrameSchema({
    "id_course_num":      Column("Int64", nullable=False),
    "id_ligne_num":       Column("Int64", nullable=False),
    "id_service_num":     Column("Int64", nullable=True),
    "direction_id":       Column("Int64", nullable=True),
    "trip_headsign":      Column(str, nullable=True),
    "heure_depart":       Column(float, nullable=True),
    "heure_arrive":       Column(float, nullable=True),
    "id_ap_num_debut":    Column("Int64", nullable=True),
    "id_ap_num_terminus": Column("Int64", nullable=True),
    "id_ag_num_debut":    Column("Int64", nullable=True),
    "id_ag_num_terminus": Column("Int64", nullable=True),
    "nb_arrets":          Column("Int64", Check.ge(1), nullable=True),
    "DIST_Vol_Oiseau":    Column(float, Check.ge(0), nullable=True),
    "sous_ligne":         Column(str, nullable=False),
}, coerce=True)

ItiArcSchema = DataFrameSchema({
    "id_course_num":  Column("Int64", nullable=False),
    "id_ligne_num":   Column("Int64", nullable=False),
    "id_service_num": Column("Int64", nullable=False),
    "direction_id":   Column("Int64", nullable=True),
    "ordre_a":        Column("Int64", nullable=True),
    "heure_depart":   Column(float, nullable=True),
    "id_ap_num_a":    Column("Int64", nullable=True),
    "id_ag_num_a":    Column("Int64", nullable=True),
    "TH_a":           Column("Int64", nullable=True),
    "ordre_b":        Column("Int64", nullable=True),
    "heure_arrive":   Column(float, nullable=True),
    "id_ap_num_b":    Column("Int64", nullable=True),
    "id_ag_num_b":    Column("Int64", nullable=True),
    "TH_b":           Column("Int64", nullable=True),
    "DIST_Vol_Oiseau": Column(float, Check.ge(0), nullable=True),
}, coerce=True)

ServiceDateSchema = DataFrameSchema({
    "id_service_num": Column("Int64", nullable=False),
    "Date_GTFS":      Column(str, nullable=False),
    "Type_Jour":      Column(str, nullable=True),
    "Semaine":        Column("Int64", nullable=True),
    "Mois":           Column("Int64", Check.in_range(1, 12), nullable=True),
    "Annee":          Column("Int64", nullable=True),
}, coerce=True)
