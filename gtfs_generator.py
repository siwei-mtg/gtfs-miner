"""
GTFS 业务生成模块 (gtfs_generator.py)

功能：
1. 生成行程序列 (Itinerary)。
2. 生成服务日期矩阵 (Service Dates)。
3. 计算班次、经过次数、班次特征 (Headway) 等。

依赖：gtfs_utils, gtfs_norm
与整体流程的关系：
```plaintext
规范化数据 -> [gtfs_generator] -> 生成行程 (itineraire_generate)
                                 -> 班次聚合 (course_generate)
                                 -> 生成 Arc (itiarc_generate)
                                 -> 计算其它业务指标
                                 -> 业务报表 DataFrame
```
"""

# 常量定义
DEFAULT_DIRECTION_ID = 999
DEFAULT_TRIP_HEADSIGN = '999'

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List
from gtfs_utils import str_time_hms_hour, str_time_hms, getDistHaversine

def itineraire_generate(stop_times: pd.DataFrame, AP: pd.DataFrame, trips: pd.DataFrame) -> pd.DataFrame:
    """
    生成行程序列。
    Input Schema:
        stop_times: [id_ap, arrival_time, departure_time, ...]
        AP: [id_ap, id_ap_num, id_ag_num, ...]
        trips: [id_course_num, id_ligne_num, id_service_num, direction_id, trip_headsign, ...]
    Output Schema: [id_course_num, id_ligne_num, id_service_num, direction_id, stop_sequence, id_ap_num, id_ag_num, arrival_time, departure_time, TH, trip_headsign, ...]
    """
    st = stop_times.copy().rename(columns={'stop_id': 'id_ap'})
    st['TH'] = pd.to_numeric(st['arrival_time'].str.split(':').str[0], errors='coerce').fillna(0).astype(int)
    # Recalage des heures >= 24 (trajets de nuit GTFS, ex. 25:30:00 -> 1)
    st['TH'] = np.where(st['TH'] >= 24, st['TH'] - 24, st['TH'])
    
    arr_parts = st['arrival_time'].str.split(':', expand=True).astype(float)
    st['arrival_time'] = arr_parts[0] / 24.0 + arr_parts[1] / 1440.0 + arr_parts[2] / 86400.0
    
    dep_parts = st['departure_time'].str.split(':', expand=True).astype(float)
    st['departure_time'] = dep_parts[0] / 24.0 + dep_parts[1] / 1440.0 + dep_parts[2] / 86400.0
    
    itnry_1 = st.merge(AP[['id_ap', 'id_ap_num', 'id_ag_num']], on='id_ap', how='left')
    itnry_2 = itnry_1.merge(trips[['id_course_num', 'id_ligne_num', 'id_service_num', 'direction_id', 'trip_headsign']], 
                             on='id_course_num', how='left')
    
    cols = ['id_course_num', 'id_ligne_num', 'id_service_num', 'direction_id', 'stop_sequence',
            'id_ap_num', 'id_ag_num', 'arrival_time', 'departure_time', 'TH', 'trip_headsign']
    itineraire = itnry_2[cols].copy()
    itineraire['stop_sequence'] = itineraire.groupby(['id_course_num']).cumcount() + 1
    
    itineraire.fillna({'direction_id': DEFAULT_DIRECTION_ID, 'trip_headsign': DEFAULT_TRIP_HEADSIGN}, inplace=True)
    return itineraire

def service_date_generate(calendar: Optional[pd.DataFrame], 
                          calendar_dates: pd.DataFrame, 
                          Dates: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """
    生成服务日期矩阵。
    Input Schema: 
        calendar: [service_id, ...]
        calendar_dates: [date, exception_type, ...]
        Dates: [Date_GTFS, ...]
    Output Schema (Tuple): 
        cal_final: [id_service_num, Date_GTFS, Type_Jour, Semaine, Mois, Annee, ...]
        msg_date: str
    """
    # Inclure les colonnes vacances si présentes dans Dates (参见 legacy 560)
    _vac_cols = ['Type_Jour_Vacances_A', 'Type_Jour_Vacances_B', 'Type_Jour_Vacances_C']
    cal_cols = ['id_service_num', 'Date_GTFS', 'Type_Jour', 'Semaine', 'Mois', 'Annee'] + \
               [c for c in _vac_cols if c in Dates.columns]

    # calendar 全零：所有 weekday 标志为 0，等同于无 calendar
    calendar_all_zero = (
        calendar is not None
        and not calendar.empty
        and calendar[['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']].sum().sum() == 0
    )

    if calendar is None or calendar.empty or calendar_all_zero:
        # 仅基于 calendar_dates 处理 (exception_type=1 为开通日期)
        cal_final = calendar_dates.merge(Dates, left_on='date', right_on='Date_GTFS', how='left')
        cal_final = cal_final[cal_cols].sort_values(['id_service_num', 'Date_GTFS']).reset_index(drop=True)
    else:
        # calendar.txt 有效：按星期几 + start_date/end_date 展开，再叠加 calendar_dates 例外
        # Type_Jour 约定: 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat, 7=Sun
        weekday_map = [
            ('monday',    1),
            ('tuesday',   2),
            ('wednesday', 3),
            ('thursday',  4),
            ('friday',    5),
            ('saturday',  6),
            ('sunday',    7),
        ]

        cal_remove = calendar_dates.loc[calendar_dates['exception_type'] == 2]
        cal_add    = calendar_dates.loc[calendar_dates['exception_type'] == 1]
        cal_add_dated = Dates.merge(cal_add, how='right', left_on='Date_GTFS', right_on='date')

        chunks: list = []
        for _, row in calendar.iterrows():
            for col, type_jour in weekday_map:
                if row[col] == 1:
                    mask = (
                        (Dates['Type_Jour'] == type_jour)
                        & (Dates['Date_GTFS'] >= row['start_date'])
                        & (Dates['Date_GTFS'] <= row['end_date'])
                    )
                    df_day = Dates.loc[mask, ['Date_GTFS']].copy()
                    df_day['id_service_num'] = row['id_service_num']
                    chunks.append(df_day)

        if chunks:
            search_cal = pd.concat(chunks, ignore_index=True)
        else:
            search_cal = pd.DataFrame(columns=['Date_GTFS', 'id_service_num'])

        # Joindre les infos Dates, puis exclure les jours supprimés (exception_type=2)
        calendar_trait = search_cal.merge(Dates, on='Date_GTFS', how='left')
        calendar_trait = calendar_trait.merge(
            cal_remove[['date', 'id_service_num']],
            left_on=['Date_GTFS', 'id_service_num'],
            right_on=['date', 'id_service_num'],
            how='left'
        )
        calendar_trait = calendar_trait.loc[calendar_trait['date'].isna()].drop(columns=['date'])

        cal_final = pd.concat([calendar_trait, cal_add_dated], ignore_index=True)
        cal_final = (
            cal_final[cal_cols]
            .drop_duplicates()
            .sort_values(['id_service_num', 'Date_GTFS'])
            .reset_index(drop=True)
        )

    msg_date = (
        f"DataSet Valid: {cal_final['Date_GTFS'].min()} to {cal_final['Date_GTFS'].max()}"
        if not cal_final.empty
        else "No valid dates found."
    )
    return cal_final, msg_date

def course_generate(itineraire: pd.DataFrame, itineraire_arc: pd.DataFrame) -> pd.DataFrame:
    """
    汇总班次统计 (起点、终点、首发时间、到达终点时间、总距离)。
    Input Schema:
        itineraire: [id_ligne_num, id_service_num, id_course_num, direction_id, trip_headsign, arrival_time, departure_time, id_ap_num, id_ag_num, stop_sequence, ...]
        itineraire_arc: [id_course_num, DIST_Vol_Oiseau, ...]
    Output Schema: [id_ligne_num, id_service_num, id_course_num, direction_id, trip_headsign, heure_depart, heure_arrive, id_ap_num_debut, id_ap_num_terminus, id_ag_num_debut, id_ag_num_terminus, nb_arrets, DIST_Vol_Oiseau, sous_ligne, ...]
    """
    course = itineraire.groupby(
        ['id_ligne_num', 'id_service_num', 'id_course_num', 'direction_id', 'trip_headsign'],
        as_index=False
    ).agg({
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

    # Agréger la distance vol d'oiseau depuis les arcs (参见 legacy 537-538)
    dist = itineraire_arc.groupby('id_course_num', as_index=False)['DIST_Vol_Oiseau'].sum()
    course = course.merge(dist, on='id_course_num', how='left')

    # Clé sous-ligne incluant la distance (参见 legacy 539)
    course['sous_ligne'] = (course['id_ligne_num'].astype(str) + '_' +
                             course['direction_id'].astype(str) + '_' +
                             course['id_ag_num_debut'].astype(str) + '_' +
                             course['id_ag_num_terminus'].astype(str) + '_' +
                             course['nb_arrets'].astype(str) + '_' +
                             course['DIST_Vol_Oiseau'].astype(str))

    return course

def itiarc_generate(itineraire: pd.DataFrame, AG: pd.DataFrame) -> pd.DataFrame:
    """
    生成相邻站点之间的运行段 (Arcs)。
    Input Schema:
        itineraire: [id_course_num, id_ligne_num, id_service_num, direction_id, stop_sequence, id_ap_num, id_ag_num, arrival_time, departure_time, TH, trip_headsign, ...]
        AG: [id_ag_num, stop_lat, stop_lon, ...]
    Output Schema: [id_course_num, id_ligne_num, id_service_num, direction_id, ordre_a, heure_depart, id_ap_num_a, id_ag_num_a, TH_a, ordre_b, heure_arrive, id_ap_num_b, id_ag_num_b, TH_b, DIST_Vol_Oiseau]
    """
    R = itineraire.copy().drop(['departure_time', 'id_service_num', 'id_ligne_num'], axis=1)
    L = itineraire.copy().drop(['arrival_time'], axis=1)
    L['ordre_b'] = R['stop_sequence'] + 1

    # Joindre A et B en incluant direction_id comme clé (参见 legacy 520)
    iti_arc = L.merge(
        R,
        how='left',
        left_on=['id_course_num', 'ordre_b', 'direction_id'],
        right_on=['id_course_num', 'stop_sequence', 'direction_id'],
        suffixes=('_a', '_b')
    )
    iti_arc = iti_arc.dropna(subset=['id_ag_num_b']).reset_index(drop=True)

    # Coordonnées des AG pour calcul de distance
    AG_coor = AG[['id_ag_num', 'stop_lon', 'stop_lat']]
    arc_dist = iti_arc.merge(AG_coor, left_on='id_ag_num_a', right_on='id_ag_num', how='left') \
                      .merge(AG_coor, left_on='id_ag_num_b', right_on='id_ag_num', how='left',
                             suffixes=('_src', '_dst'))

    # Calcul vectorisé (直接传 numpy array，非 np.vectorize，参见 OPTIMIZATION_REPORT §4.2)
    arc_dist['DIST_Vol_Oiseau'] = np.around(
        getDistHaversine(
            arc_dist['stop_lat_src'].values, arc_dist['stop_lon_src'].values,
            arc_dist['stop_lat_dst'].values, arc_dist['stop_lon_dst'].values
        ), 0)

    # Sélection et renommage final (参见 legacy 523-525)
    cols = ['id_course_num', 'id_ligne_num', 'id_service_num', 'direction_id',
            'stop_sequence_a', 'departure_time', 'id_ap_num_a', 'id_ag_num_a', 'TH_a',
            'stop_sequence_b', 'arrival_time', 'id_ap_num_b', 'id_ag_num_b', 'TH_b',
            'DIST_Vol_Oiseau']
    return arc_dist[cols].rename(columns={
        'stop_sequence_a': 'ordre_a',
        'departure_time':  'heure_depart',
        'stop_sequence_b': 'ordre_b',
        'arrival_time':    'heure_arrive',
    })

def caract_par_sl(
    service_jour_type: pd.DataFrame,
    courses: pd.DataFrame,
    hpm_range: Tuple[float, float],
    hps_range: Tuple[float, float],
    type_vac: str,
    sous_ligne: pd.DataFrame
) -> pd.DataFrame:
    """
    计算子路线 (SL) 的特征：首末班、班次数及 5 段发车间隔 (Headway)。
    Input Schema:
        service_jour_type: [id_ligne_num, id_service_num, <type_vac>, Date_GTFS]
        courses: [id_course_num, id_ligne_num, id_service_num, sous_ligne, h_dep_num, h_arr_num, ...]
        hpm_range: (debut_HPM, fin_HPM) en fraction de jour (ex. 7/24, 9/24)
        hps_range: (debut_HPS, fin_HPS) en fraction de jour (ex. 17/24, 19/24)
        type_vac: colonne jour-type (ex. 'Type_Jour', 'Type_Jour_Vacances_A')
        sous_ligne: [sous_ligne, id_ligne_num, route_short_name, route_long_name]
    Output Schema: [sous_ligne, id_ligne_num, route_short_name, route_long_name, <type_vac>,
                    Debut, Fin, Duree, Nb_courses,
                    Headway_FM, Headway_HPM, Headway_HC, Headway_HPS, Headway_FS]
    """
    debut_HPM, fin_HPM = hpm_range
    debut_HPS, fin_HPS = hps_range

    # Jointure avec le jour-type (参见 legacy 717)
    courses_jtype = courses.merge(service_jour_type, on=['id_ligne_num', 'id_service_num'])

    # Statistiques globales par sous-ligne / jour-type (参见 legacy 719-722)
    caract = courses_jtype.groupby(['sous_ligne', type_vac], as_index=False).agg(
        Debut=('h_dep_num', 'min'),
        Fin=('h_arr_num', 'max'),
        Nb_courses=('id_course_num', 'count')
    )
    caract['Duree'] = caract['Fin'] - caract['Debut']

    # Affectation des périodes (参见 legacy 725-735)
    h = courses_jtype['h_dep_num']
    courses_jtype = courses_jtype.copy()
    courses_jtype['periode'] = np.select(
        [
            h < debut_HPM,
            (h >= debut_HPM) & (h < fin_HPM),
            (h >= fin_HPM)   & (h < debut_HPS),
            (h >= debut_HPS) & (h < fin_HPS),
            h >= fin_HPS,
        ],
        ['FM', 'HPM', 'HC', 'HPS', 'FS'],
        default='HC'
    )

    # Nombre de courses par période (参见 legacy 737-738)
    headway = courses_jtype.groupby([type_vac, 'sous_ligne', 'periode'], as_index=False)['id_course_num'].count() \
                           .rename(columns={'id_course_num': 'nb_courses'})
    headway_pv = pd.pivot_table(
        headway, values='nb_courses',
        index=['sous_ligne', type_vac], columns='periode',
        fill_value=0, aggfunc=np.sum
    ).reset_index()
    # S'assurer que toutes les colonnes période existent
    for p in ['FM', 'HPM', 'HC', 'HPS', 'FS']:
        if p not in headway_pv.columns:
            headway_pv[p] = 0

    # Durées des plages en minutes (参见 legacy 739-743)
    h_min = courses_jtype['h_dep_num'].min()
    h_max = courses_jtype['h_dep_num'].max()
    duration_FM  = (debut_HPM - h_min)  * 24 * 60
    duration_HPM = (fin_HPM   - debut_HPM) * 24 * 60
    duration_HC  = (debut_HPS - fin_HPM)   * 24 * 60
    duration_HPS = (fin_HPS   - debut_HPS) * 24 * 60
    duration_FS  = (h_max     - fin_HPS)   * 24 * 60

    # Calcul Headway = durée_plage / nb_courses (参见 legacy 744-749)
    headway_pv['Headway_FM']  = duration_FM  / headway_pv['FM']
    headway_pv['Headway_HPM'] = duration_HPM / headway_pv['HPM']
    headway_pv['Headway_HC']  = duration_HC  / headway_pv['HC']
    headway_pv['Headway_HPS'] = duration_HPS / headway_pv['HPS']
    headway_pv['Headway_FS']  = duration_FS  / headway_pv['FS']
    headway_pv = headway_pv.replace(np.inf, np.nan).drop(columns=['FM', 'HPM', 'HC', 'HPS', 'FS'])

    caract_fin = caract.merge(headway_pv, on=['sous_ligne', type_vac])
    ligne_names = sous_ligne[['sous_ligne', 'id_ligne_num', 'route_short_name', 'route_long_name']]
    return ligne_names.merge(caract_fin, on='sous_ligne')

def sl_generate(course: pd.DataFrame, AG: pd.DataFrame, lignes: pd.DataFrame) -> pd.DataFrame:
    """
    Génère la table des sous-lignes (B_2) par déduplication des courses.
    Input Schema:
        course: [sous_ligne, id_ligne_num, id_ag_num_debut, id_ag_num_terminus, direction_id, nb_arrets, DIST_Vol_Oiseau, id_course_num, ...]
        AG: [id_ag_num, stop_name, ...]
        lignes: [id_ligne_num, route_short_name, route_long_name, ...]
    Output Schema: [sous_ligne, id_ligne_num, route_short_name, route_long_name, id_ag_num_debut, id_ag_num_terminus, direction_id, nb_arrets, DIST_Vol_Oiseau, ag_origin_name, ag_destination_name]
    """
    sous_ligne = course.groupby(
        ['sous_ligne', 'id_ligne_num', 'id_ag_num_debut', 'id_ag_num_terminus',
         'direction_id', 'nb_arrets', 'DIST_Vol_Oiseau'],
        as_index=False
    )['id_course_num'].count().drop(columns=['id_course_num'])

    ag_simple = AG[['id_ag_num', 'stop_name']]
    sl_merge = sous_ligne.merge(ag_simple, left_on='id_ag_num_debut', right_on='id_ag_num') \
                         .merge(ag_simple, left_on='id_ag_num_terminus', right_on='id_ag_num',
                                suffixes=('_origin', '_dest'))
    sl_merge.drop(columns=['id_ag_num_origin', 'id_ag_num_dest'], inplace=True)
    sl_merge.rename(columns={'stop_name_origin': 'ag_origin_name',
                              'stop_name_dest':   'ag_destination_name'}, inplace=True)
    ligne_names = lignes[['id_ligne_num', 'route_short_name', 'route_long_name']]
    return ligne_names.merge(sl_merge, on='id_ligne_num')

def service_jour_type_generate(service_date: pd.DataFrame,
                                course: pd.DataFrame,
                                type_vacances: str) -> pd.DataFrame:
    """
    Génère la matrice jour-type de service (D_2).
    Pour chaque (id_ligne_num, id_service_num), sélectionne le jour représentatif
    (le jour où le nombre de courses est le plus fréquent).
    Input Schema:
        service_date: [id_service_num, Date_GTFS, <type_vacances>, ...]
        course: [id_course_num, id_ligne_num, id_service_num, ...]
        type_vacances: str — colonne jour-type (ex. 'Type_Jour', 'Type_Jour_Vacances_A')
    Output Schema: [id_ligne_num, id_service_num, <type_vacances>, Date_GTFS]
    """
    crs_simple = course[['id_course_num', 'id_ligne_num', 'id_service_num']]
    crs_dates = crs_simple.merge(service_date, how='left', on='id_service_num')

    # Nombre de courses par jour et type
    nb_crs = crs_dates.groupby(['Date_GTFS', 'id_ligne_num', type_vacances], as_index=False) \
                      ['id_course_num'].count().rename(columns={'id_course_num': 'count'})

    # Nombre de jours ayant ce nb de courses
    nb_jr = nb_crs.groupby(['id_ligne_num', type_vacances, 'count'], as_index=False) \
                  ['Date_GTFS'].count().rename(columns={'Date_GTFS': 'count_days'})

    max_jr = nb_jr.groupby(['id_ligne_num', type_vacances], as_index=False)['count_days'].max() \
                  .rename(columns={'count_days': 'max_days'})

    ncours_jtype = nb_jr.merge(max_jr, how='left', on=['id_ligne_num', type_vacances])

    # Jour représentatif = jour le plus fréquent avec le nb de courses max
    choix = nb_crs.merge(ncours_jtype, how='left', on=['id_ligne_num', type_vacances, 'count'])
    choix = choix[choix['count_days'] == choix['max_days']] \
                .groupby(['id_ligne_num', type_vacances], as_index=False) \
                .agg(Date_GTFS=('Date_GTFS', 'first'), count=('count', 'max'))

    sj_1 = crs_dates.merge(choix, how='left', on=['id_ligne_num', type_vacances, 'Date_GTFS']) \
                    .dropna(subset=['count']).reset_index(drop=True)

    return sj_1.groupby(['id_ligne_num', 'id_service_num', type_vacances], as_index=False) \
               .agg(Date_GTFS=('Date_GTFS', 'first'))

def kcc_course_sl(service_jour_type: pd.DataFrame,
                  courses: pd.DataFrame,
                  type_vac: str,
                  sous_ligne: pd.DataFrame,
                  has_shp: bool) -> pd.DataFrame:
    """
    Calcule les kilomètres-course par sous-ligne (F_3/F_4).
    Input Schema:
        service_jour_type: [id_ligne_num, id_service_num, <type_vac>, ...]
        courses: [id_course_num, id_ligne_num, id_service_num, sous_ligne, DIST_Vol_Oiseau | Dist_shape, ...]
        type_vac: colonne jour-type
        sous_ligne: [sous_ligne, id_ligne_num, route_short_name, route_long_name, ...]
        has_shp: True → utiliser 'Dist_shape', False → 'DIST_Vol_Oiseau'
    Output Schema: [sous_ligne, id_ligne_num, route_short_name, route_long_name, <type_vac>_cols_km...]
    """
    dist_col = 'Dist_shape' if has_shp else 'DIST_Vol_Oiseau'
    crs_tj = courses.merge(service_jour_type, on=['id_ligne_num', 'id_service_num'])
    dist_sum = crs_tj.groupby(['sous_ligne', type_vac], as_index=False)[dist_col].sum()
    dist_sum[dist_col] = dist_sum[dist_col] / 1000.0
    pv = pd.pivot_table(dist_sum, values=dist_col, index='sous_ligne',
                        columns=type_vac, fill_value=0, aggfunc=np.sum).reset_index()
    sl_names = sous_ligne[['sous_ligne', 'id_ligne_num', 'route_short_name', 'route_long_name']]
    return sl_names.merge(pv, on='sous_ligne')

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
