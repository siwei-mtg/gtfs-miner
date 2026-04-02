import pandas as pd
import sys
import pandas as pd
import numpy as np
import os
import chardet
import datetime as dt
from datetime import date, datetime
import time
import scipy as sp
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.cluster.vq import kmeans, kmeans2
from scipy import cluster
import xlrd
from zipfile import ZipFile
import matplotlib.pyplot as plt
import shutil
import pyodbc
import re
import math

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QObject,QVariant
from qgis.core import   (QgsApplication,
  QgsDataSourceUri,
  QgsCategorizedSymbolRenderer,
  QgsClassificationRange,
  QgsPointXY,
  QgsPoint,
  QgsProject,
  QgsExpression,
  QgsField,
  QgsFields,
  QgsFeature,
  QgsFeatureRequest,
  QgsFeatureRenderer,
  QgsGeometry,
  QgsGraduatedSymbolRenderer,
  QgsMarkerSymbol,
  QgsMessageLog,
  QgsRectangle,
  QgsRendererCategory,
  QgsRendererRange,
  QgsSymbol,
  QgsVectorDataProvider,
  QgsVectorLayer,
  QgsVectorFileWriter,
  QgsWkbTypes,
  QgsSpatialIndex,
  QgsVectorLayerUtils,
  QgsVectorLayerExporter, 
  QgsCoordinateTransformContext,
  QgsDistanceArea,
  QgsUnitTypes
)
import processing


def norm_upper_str(pd_series):
    normed = pd_series.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8').str.upper()
    return normed

def str_time_hms_hour(hms):
    h = int(hms.split(':')[0])
    return h

def str_time_hms(hms):
    h,m,s = hms.split(':')
    time = int(h)/24 + int(m)/24/60 + int(s)/24/3600
    return time

def get_sec(input_timedelta):
    sec_list = [input_timedelta[i].total_seconds() for i in range(len(input_timedelta))]
    return sec_list

def get_time_now(datetime_now):
    time_now = '{}:{}:{}'.format(datetime_now.hour, datetime_now.minute, datetime_now.second)
    return time_now

def heure_goal(horaire_excel):
    horaire = f'H{int(math.modf(horaire_excel*24)[1]):02}{int(math.modf(horaire_excel*24)[0]*60):02}'
    return horaire

def heure_from_xsltime(horaire_excel):
    horaire = f'{int(math.modf(horaire_excel*24)[1]):02}:{int(math.modf(horaire_excel*24)[0]*60):02}'
    return horaire

def encoding_guess(acces):
    '''
    detect and return file encoding
    '''
    with open(acces, 'rb') as rawdata:
        encod = chardet.detect(rawdata.read(10000))
    return encod

def rawgtfs(dirpath) :
    '''
    Read raw GTFS data from given directory
    '''
    listfile = os.listdir(dirpath)
    filename = [os.path.splitext(i)[0] for i in listfile]
    filepath = [dirpath +'/' + f for f in listfile]
    rawgtfs = {a:0 for a in filename}
    for i in range(len(filepath)):
        df = pd.read_csv(filepath[i])
        rawgtfs[filename[i]] = df
    return rawgtfs

def raw_from_zip(zippath):
    with ZipFile(zippath, "r") as zfile:
        list_file = [name for name in zfile.namelist()]
    filename = [i.split('.')[0] for i in list_file]
    rawgtfs = {a:0 for a in filename}
    for num, name in enumerate(list_file):
        df = pd.read_csv(zf.open(name))
        rawgtfs[filename[num]] = df
    return rawgtfs

def read_date(plugin_path):
    '''
    Read calendar info for plugin
    '''
    Dates = pd.read_csv((plugin_path+"/Resources/Calendrier.txt"), encoding="utf-8",
                        sep = "\t", parse_dates=['Date_Num'], dtype={'Type_Jour': 'int32'})
    #encoding='utf-8'
    Dates.drop(['Date_Num','Date_Opendata', 'Ferie', 'Vacances_A', 'Vacances_B', 'Vacances_C',
            'Concat_Select_Type_A', 'Concat_Select_Type_B', 'Concat_Select_Type_C','Type_Jour_IDF','Annee_Scolaire'],axis = 1 , inplace = True)
    return Dates

def read_validite(plugin_path):
    '''
    Read validite for plugin
    '''
    validite = pd.read_csv((plugin_path+ "/Resources/Correspondance_Validite.txt"),
        encoding=encoding_guess(plugin_path+"/Resources/Correspondance_Validite.txt")['encoding'],
                        sep = ';', dtype={'valid_01': str, 'valid': 'int32'})
    return validite

def read_input(dirpath,plugin_path):
    '''Combinasion of read_calendar and read_validité'''
    rawGTFS = rawgtfs(dirpath)
    GTFS_norm = gtfs_normalize(rawGTFS)
    Dates = read_date(plugin_path)
    validite = read_validite(plugin_path)
    return GTFS_norm, Dates, validite

def getDistanceByHaversine(loc1, loc2):
    '''Haversine formula - give coordinates as a 2D numpy array of
    (lat_denter link description hereecimal,lon_decimal) pairs'''
    #
    # "unpack" our numpy array, this extracts column wise arrays
    EARTHRADIUS = 6371000.0

    lat1 = loc1[1]
    lon1 = loc1[0]
    lat2 = loc2[1]
    lon2 = loc2[0]
    #
    # convert to radians ##### Completely identical
    lon1 = lon1 * np.pi / 180.0
    lon2 = lon2 * np.pi / 180.0
    lat1 = lat1 * np.pi / 180.0
    lat2 = lat2 * np.pi / 180.0
    #
    # haversine formula #### Same, but atan2 named arctan2 in numpy
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (np.sin(dlat/2))**2 + np.cos(lat1) * np.cos(lat2) * (np.sin(dlon/2.0))**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0-a))
    m = EARTHRADIUS * c
    return m

def getDistHaversine(lat1,lon1,lat2,lon2):
    '''Haversine formula - give coordinates as a 2D numpy array of
    (lat_denter link description hereecimal,lon_decimal) pairs'''
    EARTHRADIUS = 6371000.0
    lon1 = lon1* np.pi / 180.0
    lon2 = lon2* np.pi / 180.0
    lat1 = lat1* np.pi / 180.0
    lat2 = lat2* np.pi / 180.0
    # haversine formula #### Same, but atan2 named arctan2 in numpy
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (np.sin(dlat/2))**2 + np.cos(lat1) * np.cos(lat2) * (np.sin(dlon/2.0))**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0-a))
    m = (EARTHRADIUS * c)
    return m

def getDistHaversine2(lat1,lon1,lat2,lon2):
    '''Haversine formula - give coordinates as a 2D numpy array of
    (lat_denter link description hereecimal,lon_decimal) pairs'''
    EARTHRADIUS = 6371000.0
    lon1 = lon1* np.pi / 180.0
    lon2 = lon2* np.pi / 180.0
    lat1 = lat1* np.pi / 180.0
    lat2 = lat2* np.pi / 180.0
    # haversine formula #### Same, but atan2 named arctan2 in numpy
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (np.sin(dlat/2))**2 + np.cos(lat1) * np.cos(lat2) * (np.sin(dlon/2.0))**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0-a))
    m = EARTHRADIUS * c
    return m

def distmatrice(nparray):
    distmatrix = pdist(nparray, lambda u, v: getDistanceByHaversine(u,v))
    return distmatrix


def agency_norm(raw_agency):
    agency_v =  pd.DataFrame(columns = ['agency_id', 'agency_name', 'agency_url', 'agency_timezone',
            'agency_lang', 'agency_phone', 'agency_fare_url', 'agency_email'], index = None)
    agency = pd.concat([agency_v, raw_agency], ignore_index=True)  
    agency.dropna(axis = 1, how = 'all', inplace =True)
    return agency

def stops_norm(raw_stops):
    stops_v =  pd.DataFrame(columns = ['stop_id', 'stop_code', 'stop_name', 'stop_desc',
        'stop_lat', 'stop_lon', 'zone_id', 'stop_url','location_type', 'parent_station',
        'stop_timezone','wheelchair_boarding','level_id','platform_code'], index = None)
    stops =  pd.concat([stops_v, raw_stops],  ignore_index=True)
    stops.stop_id = stops.stop_id.astype(str)
    try:
        stops.stop_lat = stops.stop_lat.astype(np.float32)
        stops.stop_lon = stops.stop_lon.astype(np.float32)
    except ValueError:
        #Le cas de Mulhouse
        stops.stop_lat = stops.stop_lat.str.strip().replace('', '0')
        stops.stop_lon = stops.stop_lat.str.strip().replace('', '0')
        stops.stop_lat = stops.stop_lat.astype(np.float32)
        stops.stop_lon = stops.stop_lon.astype(np.float32)
    stops.stop_name = norm_upper_str(stops.stop_name)
    any_nan = pd.isnull(stops.location_type.unique()).any()
    if any_nan:
        stops.location_type = stops.location_type.fillna(0).astype(np.int8)
    else:
        stops.location_type = stops.location_type.astype(np.int8)
    try:
        stops.parent_station = nan_in_col_workaround(stops.parent_station)
    except ValueError:
        stops.parent_station = stops.parent_station
    stops_essentials = ['stop_id','stop_lat','stop_lon','stop_name','location_type','parent_station']
    stops = stops[stops_essentials]
    return stops

def routes_norm(raw_routes):
    routes_v = pd.DataFrame(columns = ['route_id', 'agency_id', 'route_short_name', 'route_long_name',
        'route_desc', 'route_type', 'route_url', 'route_color','route_text_color', 'route_sort_order',
        'continuous_pickup','continuous_drop_off'], index = None) 
    routes =  pd.concat([routes_v, raw_routes], ignore_index=True)
    routes.drop(['route_url', 'route_sort_order',
                 'continuous_pickup','continuous_drop_off'],axis = 1, inplace =True)
    routes.dropna(axis = 1, inplace = True, how = 'all')
    routes.route_id = routes.route_id.astype(str)
    routes.route_type = routes.route_type.astype(np.int8)
    #routes.agency_id = routes.agency_id.astype(str)
    #routes.route_short_name = routes.route_short_name.astype(str)
    #routes.route_long_name = routes.route_long_name.astype(str)
    #routes.route_color = routes.route_color.astype(str)
    #routes.route_text_color = routes.route_text_color.astype(str)
    routes['id_ligne_num'] = np.arange(1, len(routes) + 1)
    return routes

def trips_norm(raw_trips):
    trips_v =  pd.DataFrame(
        columns = ['route_id', 'service_id', 'trip_id', 'trip_headsign','trip_short_name','direction_id',
                  'block_id','shape_id','wheelchair_accessible' ,'bikes_allowed'], index = None)
    trips =  pd.concat([trips_v, raw_trips],  ignore_index=True)
    trips.drop(['trip_short_name',
                'block_id','wheelchair_accessible' ,'bikes_allowed'],axis = 1, inplace =True)
    tps_cols = ['route_id','service_id','trip_id']
    trips[tps_cols] = trips[tps_cols].apply(lambda x:x.astype(str))
    if pd.isnull(trips.shape_id).all():
        trips.drop('shape_id',axis = 1, inplace = True)
    else:
        trips.shape_id = trips.shape_id.astype(str)
    trips['id_course_num'] = np.arange(1, len(trips) + 1)
    return trips

def stop_times_norm(raw_stoptimes):
    stop_times_v =  pd.DataFrame(columns = ['trip_id', 'arrival_time', 'departure_time','stop_id', 'stop_sequence',
        'stop_headsign', 'pickup_type', 'drop_off_type', 'continuous_pickup',
        'continuous_drop_off', 'shape_dist_traveled','timepoint'], index = None)
    stop_times =  pd.concat([stop_times_v, raw_stoptimes],  ignore_index=True)
    stop_times.drop(['stop_headsign', 'pickup_type', 'drop_off_type', 'continuous_pickup',
                     'continuous_drop_off'], axis = 1,  inplace =True)
    
    # Check for NA values for the whole table
    na_counts = stop_times.isna().sum()
    columns_with_na = ', '.join([f"{col}: {count}" for col, count in na_counts.items() if count > 0]) + f'. La table a au total {len(stop_times)} lignes.'
    # check for NA in time cols
    time_cols_na = sum(stop_times[['arrival_time','departure_time']].isna().sum())
    # Traitement NA
    if time_cols_na > 0 :
        stop_times = stop_times.loc[stop_times['timepoint'] == 1]
        time_cols_na2 = sum(stop_times[['arrival_time','departure_time']].isna().sum())
        if time_cols_na2 > 0:
            stop_times['arrival_time'] = stop_times.groupby('trip_id')['arrival_time'].transform(lambda x: x.ffill().bfill())
            stop_times['departure_time'] = stop_times.groupby('trip_id')['departure_time'].transform(lambda x: x.ffill().bfill())
            time_cols_na3 = sum(stop_times[['arrival_time','departure_time']].isna().sum())
            if time_cols_na3 > 0:
                condition1 = stop_times['arrival_time'].notna()
                condition2 = stop_times['departure_time'].notna()
                stop_times = stop_times.loc[condition1 | condition2]
    time_cols_na4 = sum(stop_times[['arrival_time','departure_time']].isna().sum())
    stp_t_cols = ['trip_id','arrival_time','departure_time','stop_id']
    stop_times[stp_t_cols] = stop_times[stp_t_cols].apply(lambda x:x.astype(str))
    stop_times['stop_sequence'] = stop_times['stop_sequence'].astype(np.int8)
    stop_times['shape_dist_traveled'] = stop_times['shape_dist_traveled'].astype(np.float32)
    stop_times.dropna(how = 'all', axis = 1, inplace = True)
    return stop_times, columns_with_na,time_cols_na4

def calendar_norm(raw_cal):
    calendar_v = pd.DataFrame(
        columns =['service_id', 'monday', 'tuesday', 'wednesday',
                  'thursday', 'friday','saturday', 'sunday', 'start_date', 'end_date'], index = None)
    calendar =  pd.concat([calendar_v, raw_cal],  ignore_index=True)
    calendar.service_id = calendar.service_id.astype(str)
    week_cols = ['monday', 'tuesday','wednesday','thursday','friday','saturday', 'sunday']
    calendar[week_cols] = calendar[week_cols].apply(lambda x: x.astype(np.bool8))
    calendar.start_date = calendar.start_date.astype(np.int32)
    calendar.end_date = calendar.end_date.astype(np.int32)
    return calendar

def cal_dates_norm(raw_caldates):
    calendar_dates_v = pd.DataFrame(columns =['service_id', 'date', 'exception_type'], index = None)
    calendar_dates =  pd.concat([calendar_dates_v, raw_caldates],  ignore_index=True)
    calendar_dates.date = calendar_dates.date.astype(np.int32)
    calendar_dates.service_id = calendar_dates.service_id.astype(str)
    calendar_dates.exception_type = calendar_dates.exception_type.astype(np.int8)
    return calendar_dates

def gtfs_normalize(rawgtfs):
    '''
    adapt gtfs data to standard form. Give a dict with normalized gtfs raw data
    '''
    agency = agency_norm(rawgtfs['agency'])
    routes = routes_norm(rawgtfs['routes'])
    route_id_coor = routes[['route_id','id_ligne_num']]
    stops = stops_norm(rawgtfs['stops'])
    trips = trips_norm(rawgtfs['trips'])
    trip_id_coor = trips[['trip_id','id_course_num']]
    trips = trips.merge(route_id_coor, on = 'route_id').drop('route_id',axis =1)
    service_id = trips.service_id.unique()
    ser_id_coor = pd.DataFrame(service_id,columns = ['service_id'])
    ser_id_coor['id_service_num'] = np.arange(1, len(ser_id_coor) + 1)
    trips = trips.merge(ser_id_coor, on ='service_id').drop(['service_id'],axis = 1)
    stop_times, initial_na, final_na_time_col = stop_times_norm(rawgtfs['stop_times'])
    # id num stop_times
    stop_times = stop_times.merge(trip_id_coor, on = 'trip_id').drop('trip_id',axis =1)
    trips = trips.drop(['trip_id'],axis = 1)
    try :
        calendar = calendar_norm(rawgtfs['calendar'])
        calendar = calendar.merge(ser_id_coor, on ='service_id').drop(['service_id'],axis = 1)
        if len(calendar)==0:
            calendar = None
    except:
        calendar = None
    calendar_dates = cal_dates_norm(rawgtfs['calendar_dates'])
    calendar_dates = calendar_dates.merge(ser_id_coor, on ='service_id').drop(['service_id'],axis = 1)
    try :
        shapes = rawgtfs['shapes']
        if len(shapes)==0:
            shapes = None
    except:
        shapes = None

    if 'shapes' in rawgtfs.keys():
            result = {'agency' :agency, 'stops' :stops, 'stop_times':stop_times,'routes': routes,'trips': trips,
                      'calendar': calendar,'calendar_dates': calendar_dates,'route_id_coor':route_id_coor,
                      'trip_id_coor':trip_id_coor,'ser_id_coor':ser_id_coor, 'shapes':shapes, 
                      'initial_na':initial_na, 'final_na_time_col':final_na_time_col}
    else: 
            result = {'agency' :agency, 'stops' :stops, 'stop_times':stop_times,'routes': routes,'trips': trips,
                      'calendar': calendar,'calendar_dates': calendar_dates,'route_id_coor':route_id_coor,
                      'trip_id_coor':trip_id_coor,'ser_id_coor':ser_id_coor,
                      'initial_na':initial_na, 'final_na_time_col':final_na_time_col}

    return result

def ag_ap_generate_hcluster(raw_stops):
    '''In cases of non-existance of parent station, or incomplete parent station grouping, create AG by hcluster'''
    AP = raw_stops.loc[raw_stops.location_type == 0,:].reset_index(drop=True)
    AP_coor = AP.loc[:,['stop_lon','stop_lat']].to_numpy()

    distmatrix = pdist(AP_coor, lambda u, v: getDistanceByHaversine(u,v))
    cut = cluster.hierarchy.cut_tree(linkage(distmatrix, method='complete'), height = 100)
    AP['id_ag'] = cut + 1
    AP['id_ag_num'] =  AP['id_ag']+10000
    AP['id_ag'] = AP['id_ag'].astype(str)
    AP['id_ap_num'] = np.arange(1, len(AP) + 1)+100000

    AG = AP.groupby(
                 ['id_ag', 'id_ag_num'], as_index = False).agg(
                 {'stop_name':'first',
                  'stop_lat' : 'mean',
                  'stop_lon' : 'mean'}, as_index = False).reset_index(drop=True)
    return AP,AG


def ag_ap_generate_asit(raw_stops):
    '''When parent station exist in good form, take the existing AG'''
    AG = raw_stops.loc[raw_stops.location_type == 1].drop(
        ['parent_station','location_type'], axis = 1).rename(
        {'stop_id':'id_ag'}, axis = 1).groupby(
        ['id_ag'], as_index = False).agg(
        {'stop_name':'first',
         'stop_lat' : 'mean',
         'stop_lon' : 'mean'}, as_index = False).reset_index(drop=True)
    AP = raw_stops.loc[raw_stops.location_type == 0].drop(
        ['location_type'], axis = 1).reset_index(drop=True).rename({'stop_id':'id_ap', 'parent_station':'id_ag'}, axis = 1)
    AP['id_ap_num'] = np.arange(1, len(AP) + 1)+100000
    AG['id_ag_num']= np.arange(1, len(AG) + 1)+10000
    AP = AP.merge(AG[['id_ag', 'id_ag_num']], how = 'left',
                  on='id_ag', suffixes=('','_y'))
    return AP, AG

def ag_ap_generate_bigvolume(rawstops):
    AP = rawstops.loc[rawstops.location_type ==0,:].reset_index(drop=True)
    ap_coor = AP.loc[:,['stop_lon','stop_lat']].to_numpy()
    kcentroids = round(len(ap_coor)/500)
    id_centroid = kmeans2(ap_coor, kcentroids, minit = 'points')[1]
    AP['kmean_id'] = id_centroid
    for i in range(kcentroids):
        AP_kmeaned_coor = AP.loc[AP.kmean_id==i,['stop_lat','stop_lon']]
        AP_kmeaned_coornp = AP_kmeaned_coor.to_numpy()
        distmat = distmatrice(AP_kmeaned_coornp)
        distmat_cutree = cluster.hierarchy.cut_tree(linkage(distmat, method='complete'), height = 100)
        AP.loc[AP.kmean_id==i,'clust_id'] = distmat_cutree
    AP['id_ag'] = AP['kmean_id'].astype(str) + '_' + AP['clust_id'].astype(int).astype(str)
    AP['id_ap_num'] = np.arange(1, len(AP) + 1)+100000
    AG = AP.groupby(
                 ['id_ag'], as_index = False).agg(
                 {'stop_name':'first',
                  'stop_lat' : 'mean',
                  'stop_lon' : 'mean'}, as_index = False).reset_index(drop=True)
    AG['id_ag_num'] = np.arange(1, len(AG) + 1)+100000
    AP = AP.merge(AG[['id_ag','id_ag_num']])
    return AP, AG

def ag_ap_generate_reshape(raw_stops):
    nb_location_type = len(raw_stops.location_type.unique())
    ap_not_in_any_ag = raw_stops[raw_stops['location_type'] == 0]['parent_station'].isnull().sum()
    if nb_location_type == 1:
        AP,AG = ag_ap_generate_hcluster(raw_stops)
        marker = 'cluster méthode'

    elif nb_location_type >= 2:
        if ap_not_in_any_ag == 0 :
            AP,AG = ag_ap_generate_asit(raw_stops)
            marker = 'original parent station'
        elif ap_not_in_any_ag > 0:
            ap_potentiel = len(raw_stops.loc[raw_stops['location_type'] == 0,:])
            if ap_potentiel <5000:
                AP,AG = ag_ap_generate_hcluster(raw_stops)
                marker = 'cluster méthode'
            else:
                AP, AG = ag_ap_generate_bigvolume(raw_stops)
                marker = 'cluster méthode pour grand volume'
    AP = AP.rename({'stop_id':'id_ap'},axis = 1)
    AP.dropna(axis = 'columns', how = 'all', inplace = True)
    AG.dropna(axis = 'columns', how = 'all', inplace = True)
    return AP,AG,marker

def ag_ap_generate_reshape_sncf(raw_stops):
    nb_location_type = len(raw_stops.location_type.unique())
    ap_not_in_any_ag = raw_stops[raw_stops['location_type'] == 0]['parent_station'].isnull().sum()
    if nb_location_type == 1:
        AP,AG = ag_ap_generate_hcluster(raw_stops)
        marker = 'cluster méthode'

    elif nb_location_type >= 2:
        if ap_not_in_any_ag == 0 :
            AP,AG = ag_ap_generate_asit(raw_stops)
            marker = 'original parent station'
        elif ap_not_in_any_ag > 0:
            ap_potentiel = len(raw_stops.loc[raw_stops['location_type'] == 0,:])
            if ap_potentiel <5000:
                AP,AG = ag_ap_generate_hcluster(raw_stops)
                marker = 'cluster méthode'
            else:
                AP, AG = ag_ap_generate_bigvolume(raw_stops)
                marker = 'cluster méthode pour grand volume'
    AP = AP.rename({'stop_id':'id_ap'},axis = 1)
    AP.loc[:,'id_ag_num'] =AP.loc[:,'id_ag'].str.replace('StopArea:OCE','').astype(np.int64)
    AG.loc[:,'id_ag_num'] =AG.loc[:,'id_ag'].str.replace('StopArea:OCE','').astype(np.int64)
    AP.dropna(axis = 'columns', how = 'all', inplace = True)
    AG.dropna(axis = 'columns', how = 'all', inplace = True)
    return AP,AG,marker

def ligne_generate(raw_routes):
    route_type = pd.DataFrame({'route_type' : pd.Series([0,1,2,3,4,5,6,7,11,12]),
                               'mode' : pd.Series(["tramway", "metro", "train", "bus","ferry", "tramway par cable",
                                                   "téléphérique", "funiculaire", "trolleybus", "monorail"])})
    lignes = raw_routes.merge(route_type, on = 'route_type', how = 'left')
    lignes.dropna(axis = 'columns', how = 'all', inplace = True)
    return lignes

def itineraire_generate(raw_stoptimes, AP, raw_trips):
    stop_times = raw_stoptimes.rename({'stop_id':'id_ap'},axis = 1).dropna(axis = 'columns', how = 'all')
    stop_times['TH'] = np.vectorize(str_time_hms_hour)(stop_times.arrival_time)
    stop_times['TH'] = np.where(stop_times['TH']>=24, stop_times['TH']-24,stop_times['TH'])
    stop_times['arrival_time'] = np.vectorize(str_time_hms)(stop_times.arrival_time)
    stop_times['departure_time'] = np.vectorize(str_time_hms)(stop_times.departure_time)
    itnry_1 = stop_times.merge(AP[['id_ap','id_ap_num', 'id_ag_num']], how = 'left', on = 'id_ap')
    itnry_2 = itnry_1.merge(raw_trips[['id_course_num', 'id_ligne_num', 'id_service_num','direction_id', 'trip_headsign']], how = 'left', on ='id_course_num')
    itineraire = itnry_2[['id_course_num','id_ligne_num','id_service_num','direction_id','stop_sequence',
                          'id_ap_num','id_ag_num','arrival_time','departure_time','TH', 'trip_headsign']]
    itineraire['stop_sequence'] = itineraire.groupby(['id_course_num']).cumcount()+1
    if itineraire['direction_id'].isnull().sum() >0:
        itineraire['direction_id'] = 999
    if itineraire['trip_headsign'].isnull().sum() >0:
        itineraire['trip_headsign'] = 999
    return itineraire

def itiarc_generate(itineraire,AG):
    iti_arc_R = itineraire.copy().drop(['departure_time','id_service_num','id_ligne_num'], axis = 1)
    iti_arc_L = itineraire.copy().drop(['arrival_time'], axis = 1)
    iti_arc_L['ordre_b'] = iti_arc_R['stop_sequence'] +1
    iti_arc = iti_arc_L.merge(iti_arc_R, how ='left', left_on = ['id_course_num','ordre_b','direction_id'], right_on = ['id_course_num', 'stop_sequence','direction_id'], suffixes = ('_a','_b')).dropna(subset=['id_ag_num_b']).reset_index(drop = True)
    iti_arc_dist = iti_arc.merge(AG[['id_ag_num','stop_lon','stop_lat']], left_on = 'id_ag_num_a',right_on = 'id_ag_num',how = 'left').merge(AG[['id_ag_num','stop_lon','stop_lat']], left_on = 'id_ag_num_b',right_on = 'id_ag_num',how = 'left')
    iti_arc_dist['DIST_Vol_Oiseau'] = np.around(np.vectorize(getDistHaversine)(iti_arc_dist.stop_lat_x,iti_arc_dist.stop_lon_x,iti_arc_dist.stop_lat_y,iti_arc_dist.stop_lon_y ),0)
    cols = ['id_course_num','id_ligne_num','id_service_num','direction_id','stop_sequence_a','departure_time','id_ap_num_a','id_ag_num_a','TH_a','stop_sequence_b','arrival_time','id_ap_num_b', 'id_ag_num_b','TH_b','DIST_Vol_Oiseau']
    iti_arc_f = iti_arc_dist[cols].rename({'stop_sequence_a':'ordre_a','arrival_time':'heure_arrive',
                                      'stop_sequence_b':'ordre_b','departure_time':'heure_depart'},axis =1)
    return iti_arc_f

def course_generate(itineraire,itineraire_arc):
    course = itineraire.groupby(
    ['id_ligne_num', 'id_service_num','id_course_num','direction_id', 'trip_headsign'], as_index=False).agg(
    {'arrival_time': 'min',
    'departure_time': 'max',
    'id_ap_num': ['first', 'last'],
    'id_ag_num': ['first', 'last'],
    'stop_sequence': 'max'})
    course.columns = course.columns.map(''.join)
    dist = itineraire_arc.groupby('id_course_num',as_index = False)['DIST_Vol_Oiseau'].sum()
    course = course.merge(dist, on = 'id_course_num', how = 'left')
    course['sous_ligne'] = course['id_ligne_num'].astype('str') + '_' + course['direction_id'].astype('str')+ '_' + course['id_ag_numfirst'].astype('str') + '_' + course['id_ag_numlast'].astype('str') + '_' + course['stop_sequencemax'].astype('str') +'_' +  course['DIST_Vol_Oiseau'].astype('str')
    course.rename({'arrival_timemin':'heure_depart', 'departure_timemax':'heure_arrive',
                'id_ap_numfirst':'id_ap_num_debut', 'id_ap_numlast':'id_ap_num_terminus',
                'id_ag_numfirst':'id_ag_num_debut', 'id_ag_numlast':'id_ag_num_terminus',
                'stop_sequencemax':'nb_arrets'}, axis = 1, inplace = True)
    return course

def sl_generate(course, ag,ligne):
    sous_ligne = course.groupby(['sous_ligne', 'id_ligne_num','id_ag_num_debut', 'id_ag_num_terminus', 'direction_id','nb_arrets','DIST_Vol_Oiseau'], as_index=False).id_course_num.count()
    sous_ligne.drop('id_course_num',axis = 1, inplace = True)
    ag_simple = ag[['id_ag_num','stop_name']]
    sous_ligne_merge = pd.merge(sous_ligne, ag_simple, left_on = 'id_ag_num_debut', right_on= 'id_ag_num')
    sous_ligne_merge2 = pd.merge(sous_ligne_merge, ag_simple, left_on = 'id_ag_num_terminus', right_on= 'id_ag_num')
    sous_ligne_merge2.drop(['id_ag_num_x','id_ag_num_y'],axis = 1, inplace = True)
    sous_ligne_merge2.rename({'stop_name_x':'ag_origin_name',
                              'stop_name_y':'ag_destination_name'}, axis = 1, inplace = True)
    ligne_names = ligne[['id_ligne_num','route_short_name','route_long_name']]
    result = ligne_names.merge(sous_ligne_merge2, on = ['id_ligne_num'])
    return result

def service_date_generate(calendar,calendar_dates,Dates):
    cal_cols = ['id_service_num','Date_GTFS','Type_Jour','Semaine','Mois','Annee','Type_Jour_Vacances_A','Type_Jour_Vacances_B','Type_Jour_Vacances_C']
    if calendar is None:
        cal_final = calendar_dates.merge(Dates, left_on = 'date', right_on = 'Date_GTFS',how = 'left')[cal_cols].sort_values(['id_service_num','Date_GTFS']).reset_index(drop = True)
    elif sum(calendar['monday']) + sum(calendar['tuesday']) + sum(calendar['wednesday']) + sum(calendar['thursday']) + sum(calendar['friday']) + sum(calendar['saturday']) + sum(calendar['sunday'])  ==0:
        cal_final = calendar_dates.merge(Dates, left_on = 'date', right_on = 'Date_GTFS',how = 'left')[cal_cols].sort_values(['id_service_num','Date_GTFS']).reset_index(drop = True)
    else :
        cal_remove =calendar_dates.loc[calendar_dates['exception_type'] ==2 ]
        cal_add =calendar_dates.loc[calendar_dates['exception_type'] ==1 ]
        cal_add_date = Dates.merge(cal_add,how = 'right', left_on = ['Date_GTFS'], right_on = ['date'])
        search_cal = pd.DataFrame(columns=['Date_GTFS','id_service_num'])

        for idx, row in calendar.iterrows():
            if row['monday'] == 1:
                df_lookup = pd.DataFrame(Dates.loc[(Dates['Type_Jour']==1)&(Dates['Date_GTFS']>=row['start_date']) & (Dates['Date_GTFS']<=row['end_date']),'Date_GTFS'])
                df_lookup['id_service_num'] = row['id_service_num']
                search_cal =  pd.concat([search_cal, df_lookup], ignore_index=True)
            if row['tuesday'] == 1 :
                df_lookup = pd.DataFrame(Dates.loc[(Dates['Type_Jour']==2)&(Dates['Date_GTFS']>=row['start_date']) & (Dates['Date_GTFS']<=row['end_date']),'Date_GTFS'])
                df_lookup['id_service_num'] = row['id_service_num']
                search_cal =  pd.concat([search_cal, df_lookup], ignore_index=True)
            if row['wednesday'] == 1 :
                df_lookup = pd.DataFrame(Dates.loc[(Dates['Type_Jour']==3)&(Dates['Date_GTFS']>=row['start_date']) & (Dates['Date_GTFS']<=row['end_date']),'Date_GTFS'])
                df_lookup['id_service_num'] = row['id_service_num']
                search_cal =  pd.concat([search_cal, df_lookup], ignore_index=True)
            if row['thursday'] == 1 :
                df_lookup = pd.DataFrame(Dates.loc[(Dates['Type_Jour']==4)&(Dates['Date_GTFS']>=row['start_date']) & (Dates['Date_GTFS']<=row['end_date']),'Date_GTFS'])
                df_lookup['id_service_num'] = row['id_service_num']
                search_cal =  pd.concat([search_cal, df_lookup], ignore_index=True)
            if row['friday'] == 1 :
                df_lookup = pd.DataFrame(Dates.loc[(Dates['Type_Jour']==5)&(Dates['Date_GTFS']>=row['start_date']) & (Dates['Date_GTFS']<=row['end_date']),'Date_GTFS'])
                df_lookup['id_service_num'] = row['id_service_num']
                search_cal =  pd.concat([search_cal, df_lookup], ignore_index=True)
            if row['saturday'] == 1 :
                df_lookup = pd.DataFrame(Dates.loc[(Dates['Type_Jour']==6)&(Dates['Date_GTFS']>=row['start_date']) & (Dates['Date_GTFS']<=row['end_date']),'Date_GTFS'])
                df_lookup['id_service_num'] = row['id_service_num']
                search_cal =  pd.concat([search_cal, df_lookup], ignore_index=True)
            if row['sunday'] == 1 :
                df_lookup = pd.DataFrame(Dates.loc[(Dates['Type_Jour']==7)&(Dates['Date_GTFS']>=row['start_date']) & (Dates['Date_GTFS']<=row['end_date']),'Date_GTFS'])
                df_lookup['id_service_num'] = row['id_service_num']
                search_cal =  pd.concat([search_cal, df_lookup], ignore_index=True)

        calendar_trait = search_cal.merge(Dates, on = 'Date_GTFS',how = 'left')
        calendar_trait = calendar_trait.merge(cal_remove, left_on = ['Date_GTFS','id_service_num'], right_on = ['date','id_service_num'],how = 'left')
        calendar_trait = calendar_trait.loc[calendar_trait['exception_type']!=2]
        cal_final =  pd.concat([calendar_trait, cal_add_date], ignore_index=True)
        cal_final = cal_final[cal_cols].drop_duplicates().sort_values(['id_service_num','Date_GTFS']).reset_index(drop = True)
    mindate = min(cal_final['Date_GTFS'])
    maxdate = max(cal_final['Date_GTFS'])
    msg_date = f"Le présent jeu de donnée a une validité de {mindate} à {maxdate}"
    return cal_final, msg_date

def service_jour_type_generate(service_date,course, type_vacances):
    crs_simplifie = course[['id_course_num', 'id_ligne_num', 'id_service_num']]
    crs_et_plage_date = pd.merge(crs_simplifie, service_date, how = 'left', on = 'id_service_num')
    nb_crs_parligne_parjtype = crs_et_plage_date.groupby(
    ['Date_GTFS','id_ligne_num',type_vacances], as_index = False)['id_course_num'].count().rename(
    {'id_course_num':'count'}, axis=1)
    nb_jr_per_nb_crs = nb_crs_parligne_parjtype.groupby(
    ['id_ligne_num', type_vacances, 'count'], as_index=False)['Date_GTFS'].count().rename(
    {'Date_GTFS':'count_days'}, axis=1)
    max_nb_jr_zb = nb_jr_per_nb_crs.groupby(
    ['id_ligne_num', type_vacances], as_index=False)['count_days'].max().rename(
    {'count_days':'max_days'}, axis=1)
    ncours_jtype = nb_jr_per_nb_crs.merge(max_nb_jr_zb, how = 'left', on = ['id_ligne_num', type_vacances])
    choix_jtype_1 = nb_crs_parligne_parjtype.merge(
    ncours_jtype, how = 'left', on = ['id_ligne_num',type_vacances,'count'])
    choix_jtype = choix_jtype_1[
    choix_jtype_1['count_days']==choix_jtype_1['max_days']].groupby(
    ['id_ligne_num',type_vacances],as_index=False ).agg(
    {'Date_GTFS':'first','count':'max'},as_index=False )
    service_jtype_1 = crs_et_plage_date.merge(
    choix_jtype, how = 'left', on=['id_ligne_num',type_vacances ,'Date_GTFS']).dropna().reset_index(drop = True)
    service_jtype = service_jtype_1.groupby(
    ['id_ligne_num', 'id_service_num', type_vacances], as_index = False).agg({'Date_GTFS':'first'}, as_index = False)
    return service_jtype

def nb_passage_ag(service_jour_type_export, itineraire_export,AG,type_vac):
    iti_typejour = itineraire_export.merge(service_jour_type_export, on =['id_ligne_num','id_service_num'])
    nb_passage = iti_typejour.groupby(
        ['id_ag_num', type_vac], as_index = False)['id_course_num'].count().sort_values(['id_ag_num'])
    nb_passage_ag = nb_passage.merge(AG)
    nb_passage_ag = nb_passage_ag.reset_index(drop=True).rename({'id_course_num':'nb_passage'},axis = 1)
    nb_passage_ag_pv = pd.pivot_table(nb_passage_ag,values = 'nb_passage', index = ['id_ag_num','stop_name', 'stop_lat','stop_lon' ], columns = type_vac, fill_value = 0,  aggfunc=np.sum).reset_index()
    return nb_passage_ag_pv

def nb_course_ligne(service_jour_type_export, courses_export,type_vac, ligne):
    courses_jtype =  courses_export.merge(service_jour_type_export, on =['id_ligne_num','id_service_num'])
    nb_courses_par_ligne = courses_jtype.groupby(
        ['id_ligne_num',type_vac], as_index = False)['id_course_num'].count().sort_values(
        ['id_ligne_num']).rename({'id_course_num':'nb_courses'},axis = 1)
    nb_courses_par_ligne_pv = pd.pivot_table(nb_courses_par_ligne,
                                             values = 'nb_courses', 
                                             index = ['id_ligne_num'], 
                                             columns = type_vac, 
                                             fill_value = 0,  
                                             aggfunc=np.sum).reset_index()
    ligne_names = ligne[['id_ligne_num','route_short_name','route_long_name']]
    result = ligne_names.merge(nb_courses_par_ligne_pv, on = ['id_ligne_num'])
    return result

def kcc_course_ligne(service_jour_type_export, courses_export,type_vac, ligne, isShapeExist):
    courses_jtype =  courses_export.merge(service_jour_type_export, on =['id_ligne_num','id_service_num'])
    if isShapeExist:
        m_par_ligne = courses_jtype.groupby(
            ['id_ligne_num',type_vac], as_index = False)['Dist_shape'].sum().sort_values(
            ['id_ligne_num'])
        m_par_ligne['Dist_shape'] = m_par_ligne['Dist_shape']/1000
        m_par_ligne_pv = pd.pivot_table(m_par_ligne,
                                                values = 'Dist_shape', 
                                                index = ['id_ligne_num'], 
                                                columns = type_vac, 
                                                fill_value = 0,  
                                                aggfunc=np.sum).reset_index()
    else:
        m_par_ligne = courses_jtype.groupby(
            ['id_ligne_num',type_vac], as_index = False)['DIST_Vol_Oiseau'].sum().sort_values(
            ['id_ligne_num'])
        m_par_ligne['DIST_Vol_Oiseau'] = m_par_ligne['DIST_Vol_Oiseau']/1000
        m_par_ligne_pv = pd.pivot_table(m_par_ligne,
                                                values = 'DIST_Vol_Oiseau', 
                                                index = ['id_ligne_num'], 
                                                columns = type_vac, 
                                                fill_value = 0,  
                                                aggfunc=np.sum).reset_index()
    ligne_names = ligne[['id_ligne_num','route_short_name','route_long_name']]
    result = ligne_names.merge(m_par_ligne_pv, on = ['id_ligne_num'])
    return result

def kcc_course_sl(service_jour_type_export, courses_export,type_vac, sous_ligne, isShapeExist):
    courses_jtype =  courses_export.merge(service_jour_type_export, on =['id_ligne_num','id_service_num'])
    if isShapeExist:
        m_par_ligne = courses_jtype.groupby(
            ['sous_ligne',type_vac], as_index = False)['Dist_shape'].sum().sort_values(
            ['sous_ligne'])
        m_par_ligne['Dist_shape'] = m_par_ligne['Dist_shape']/1000
        m_par_ligne_pv = pd.pivot_table(m_par_ligne,
                                                values = 'Dist_shape', 
                                                index = ['sous_ligne'], 
                                                columns = type_vac, 
                                                fill_value = 0,  
                                                aggfunc=np.sum).reset_index()
    else:
        m_par_ligne = courses_jtype.groupby(
            ['sous_ligne',type_vac], as_index = False)['DIST_Vol_Oiseau'].sum().sort_values(
            ['sous_ligne'])
        m_par_ligne['DIST_Vol_Oiseau'] = m_par_ligne['DIST_Vol_Oiseau']/1000
        m_par_ligne_pv = pd.pivot_table(m_par_ligne,
                                                values = 'DIST_Vol_Oiseau', 
                                                index = ['sous_ligne'], 
                                                columns = type_vac, 
                                                fill_value = 0,  
                                                aggfunc=np.sum).reset_index()
    ligne_names = sous_ligne[['sous_ligne','id_ligne_num','route_short_name','route_long_name']]
    result = ligne_names.merge(m_par_ligne_pv, on = ['sous_ligne'])
    return result

def caract_par_sl(service_jour_type_export,courses_export,debut_HPM , fin_HPM, debut_HPS ,fin_HPS, type_vac,sous_ligne):
    courses_jtype =  courses_export.merge(service_jour_type_export,  on =['id_ligne_num','id_service_num'])
    # Premier et dernier départ et nb courses par jour type
    caract = courses_jtype.groupby(['sous_ligne', type_vac],as_index = False).agg(
                 {'h_dep_num':'min',
                  'h_arr_num' : 'max',
                  'id_course' : 'count'}, as_index = False).reset_index(drop=True).rename({'id_course':'Nb_courses', 'h_dep_num' : 'Debut', 'h_arr_num': 'Fin'},axis = 1)
    caract.loc[:,'Duree'] = caract.loc[:,'Fin'] - caract.loc[:,'Debut']
    # mask pour filtrer
    mask_FM = courses_jtype['h_dep_num'] < debut_HPM
    mask_HPM = (courses_jtype['h_dep_num'] >= debut_HPM) & (courses_jtype['h_dep_num'] < fin_HPM)
    mask_HC = (courses_jtype['h_dep_num'] >= fin_HPM) & (courses_jtype['h_dep_num'] < debut_HPS)
    mask_HPS = (courses_jtype['h_dep_num'] >= debut_HPS) & (courses_jtype['h_dep_num'] < fin_HPS)
    mask_FS = (courses_jtype['h_dep_num'] >= fin_HPS)

    courses_jtype.loc[mask_FM,'periode'] = 'FM'
    courses_jtype.loc[mask_HPM,'periode'] = 'HPM'
    courses_jtype.loc[mask_HC,'periode'] = 'HC'
    courses_jtype.loc[mask_HPS,'periode'] = 'HPS'
    courses_jtype.loc[mask_FS,'periode'] = 'FS'

    headway = courses_jtype.groupby([type_vac, 'sous_ligne','periode'],as_index = False)['id_course_num'].count().rename({'id_course_num':'nb_courses'},axis = 1)
    headway_pv = pd.pivot_table(headway,values = 'nb_courses', index = ['sous_ligne',type_vac], columns = 'periode', fill_value = 0,  aggfunc=np.sum).reset_index()
    duration_FM = (debut_HPM - min(courses_jtype['h_dep_num']))*24*60
    duration_HPM = (fin_HPM - debut_HPM)*24*60
    duration_HC = (debut_HPS - fin_HPM)*24*60
    duration_HPS = (fin_HPS - debut_HPS)*24*60
    duration_FS = (max(courses_jtype['h_dep_num']) - fin_HPS)*24*60
    headway_pv.loc[:,'Headway_FM'] = duration_FM/headway_pv.loc[:,'FM']
    headway_pv.loc[:,'Headway_HPM'] = duration_HPM/headway_pv.loc[:,'HPM']
    headway_pv.loc[:,'Headway_HC'] = duration_HC/headway_pv.loc[:,'HC']
    headway_pv.loc[:,'Headway_HPS'] = duration_HPS/headway_pv.loc[:,'HPS']
    headway_pv.loc[:,'Headway_FS'] = duration_FS/headway_pv.loc[:,'FS']
    headway_pv = headway_pv.replace(np.inf, np.nan).drop(['FM','HPM','HC','HPS','FS'],axis = 1)
    caract_fin = caract.merge(headway_pv,  on =['sous_ligne',type_vac])
    ligne_names = sous_ligne[['sous_ligne','id_ligne_num','route_short_name','route_long_name']]
    result = ligne_names.merge(caract_fin, on = ['sous_ligne'])
    return result

def nan_in_col_workaround(pd_serie):
    a = pd_serie.astype('float64')
    b = a.fillna(-1)
    c = b.astype(np.int64)
    d = c.astype(str)
    e = d.replace('-1', np.nan)
    return e

def MEF_ligne(lignes,courses, AG):
    lignes_export = lignes.rename({'route_id':'id_ligne'},axis = 1)
    #Afficher OD principal
    crs_1dir = courses[courses['direction_id'] == 0]
    ligne_od_count = crs_1dir.groupby(['id_ligne_num', 'id_ag_num_debut', 'id_ag_num_terminus'])['id_course_num'].count().reset_index()
    idx = ligne_od_count.groupby(['id_ligne_num'])['id_course_num'].idxmax()
    od_principal = ligne_od_count.loc[idx]
    od_principal_simplify = od_principal[['id_ligne_num','id_ag_num_debut','id_ag_num_terminus']]
    AG_simplify = AG[['id_ag_num', 'stop_name']]
    od_principal1 = pd.merge(od_principal_simplify, AG_simplify, left_on = 'id_ag_num_debut', right_on= 'id_ag_num').rename(columns={'stop_name':'Origin'})
    od_principal = pd.merge(od_principal1, AG_simplify, left_on = 'id_ag_num_terminus', right_on= 'id_ag_num').rename(columns={'stop_name':'Destination'})
    result = pd.merge(lignes_export, od_principal, on = 'id_ligne_num')
    result = result.drop(['id_ag_num_x','id_ag_num_y'], axis = 1)
    return result

def MEF_course(courses,trip_id_coor):
    crs_cols = ['trip_id','id_course_num','id_ligne_num', 'sous_ligne' ,'id_service_num','direction_id','heure_depart','heure_arrive', 'id_ap_num_debut', 'id_ap_num_terminus','id_ag_num_debut', 'id_ag_num_terminus', 'nb_arrets','DIST_Vol_Oiseau']
    courses_export = courses.merge(
    trip_id_coor)[crs_cols].rename({'trip_id':'id_course', 'heure_depart' : 'h_dep_num','heure_arrive' : 'h_arr_num'},axis = 1)
    courses_export.loc[:,'heure_depart'] = np.vectorize(heure_from_xsltime)(courses_export.loc[:,'h_dep_num'])
    courses_export.loc[:,'heure_arrive'] = np.vectorize(heure_from_xsltime)(courses_export.loc[:,'h_arr_num'])
    crs_cols = ['id_course','id_course_num','id_ligne_num','id_service_num', 'sous_ligne','direction_id', 'id_ap_num_debut','id_ag_num_debut','h_dep_num','heure_depart','id_ap_num_terminus','id_ag_num_terminus', 'heure_arrive','h_arr_num', 'nb_arrets','DIST_Vol_Oiseau']
    return courses_export[crs_cols]

def MEF_iti(itineraire, courses):
    iti_exp = itineraire.drop(['trip_headsign'],axis =1).rename({'stop_sequence':'ordre','arrival_time':'h_dep_num','departure_time':'h_arr_num'},axis = 1)
    iti_exp.loc[:,'heure_depart'] = np.vectorize(heure_from_xsltime)(iti_exp.loc[:,'h_dep_num'])
    iti_exp.loc[:,'heure_arrive'] = np.vectorize(heure_from_xsltime)(iti_exp.loc[:,'h_arr_num'])
    iti_cols = ['id_course_num','id_ligne_num','id_service_num','direction_id','ordre','id_ap_num','id_ag_num','heure_depart','h_dep_num','heure_arrive','h_arr_num','TH']
    iti = iti_exp[iti_cols]
    crs_simple = courses[['id_course_num','sous_ligne']]
    result = crs_simple.merge(iti, on = 'id_course_num')
    return result

def MEF_iti_arc(itineraire_arc,courses):
    itiarc_cols = [ 'id_course_num', 'id_ligne_num','id_service_num','direction_id',
                   'ordre_a','heure_depart','h_dep_num','heure_arrive','h_arr_num' ,'id_ap_num_a', 'id_ag_num_a', 'TH_a', 'ordre_b',
                    'id_ap_num_b', 'id_ag_num_b', 'TH_b','DIST_Vol_Oiseau']
    iti_arc_export = itineraire_arc.rename({
        'heure_depart':'h_dep_num','heure_arrive':'h_arr_num'},axis = 1)
    iti_arc_export.loc[:,'heure_depart'] = np.vectorize(heure_from_xsltime)(iti_arc_export.loc[:,'h_dep_num'])
    iti_arc_export.loc[:,'heure_arrive'] = np.vectorize(heure_from_xsltime)(iti_arc_export.loc[:,'h_arr_num'])
    iti_arc = iti_arc_export[itiarc_cols]
    crs_simple = courses[['id_course_num','sous_ligne']]
    result = crs_simple.merge(iti_arc, on = 'id_course_num')
    return result

def MEF_serdate(service_dates, ser_id_coor):
    ser_cols = ['service_id','id_service_num','Date_GTFS', 'Type_Jour', 'Mois', 'Annee','Type_Jour_Vacances_A', 'Type_Jour_Vacances_B', 'Type_Jour_Vacances_C']
    service_dates_export = service_dates.merge(
        ser_id_coor)[ser_cols]
    return service_dates_export

def MEF_servjour(service_jour_type,route_id_coor,ser_id_coor,type_vac):
    servjour_cols = ['id_ligne_num', 'service_id','id_service_num', 'Date_GTFS', type_vac]
    service_jour_type_export = service_jour_type.merge(
        ser_id_coor)
    return service_jour_type_export[servjour_cols]

def MEF_course_sncf(courses,trip_id_coor):
    crs_cols = ['trip_id','id_course_num','id_ligne_num', 'sous_ligne' ,'id_service_num','direction_id','heure_depart','heure_arrive', 'id_ap_num_debut', 'id_ap_num_terminus','id_ag_num_debut', 'id_ag_num_terminus', 'nb_arrets','DIST_Vol_Oiseau', 'trip_headsign']
    courses_export = courses.merge(
        trip_id_coor)[crs_cols].rename({'trip_id':'id_course','trip_headsign' : 'N_train', 'heure_depart' : 'h_dep_num','heure_arrive' : 'h_arr_num', 'id_ag_num_debut':'UIC_A','id_ag_num_terminus':'UIC_B'},axis = 1)
    courses_export.loc[:,'heure_depart'] = np.vectorize(heure_from_xsltime)(courses_export.loc[:,'h_dep_num'])
    courses_export.loc[:,'heure_arrive'] = np.vectorize(heure_from_xsltime)(courses_export.loc[:,'h_arr_num'])
    crs_cols = ['id_course','id_course_num','id_ligne_num','id_service_num', 'sous_ligne', 'N_train','direction_id','id_ap_num_debut','UIC_A','h_dep_num','heure_depart','id_ap_num_terminus','UIC_B', 'heure_arrive','h_arr_num', 'nb_arrets','DIST_Vol_Oiseau']
    return courses_export.reindex(columns=crs_cols)

def MEF_iti_sncf(itineraire):
    iti_exp = itineraire.rename({'stop_sequence':'ordre',
                                 'arrival_time':'h_dep_num',
                                 'departure_time':'h_arr_num',
                                 'trip_headsign':'N_train'},axis = 1)
    iti_exp.loc[:,'heure_depart'] = np.vectorize(heure_from_xsltime)(iti_exp.loc[:,'h_dep_num'])
    iti_exp.loc[:,'heure_arrive'] = np.vectorize(heure_from_xsltime)(iti_exp.loc[:,'h_arr_num'])
    iti_cols = ['id_course_num','id_ligne_num','id_service_num','N_train','direction_id','ordre','id_ap_num','id_ag_num','heure_depart','h_dep_num','heure_arrive','h_arr_num','TH']
    return iti_exp[iti_cols]

def MEF_iti_arc_sncf(itineraire_arc,courses_export):
    itiarc_cols = [ 'id_course_num', 'id_ligne_num','id_service_num', 'N_train','direction_id',
                   'ordre_a','heure_depart','h_dep_num','heure_arrive','h_arr_num' ,'id_ap_num_a', 'id_ag_num_a', 'TH_a', 'ordre_b',
                    'id_ap_num_b', 'id_ag_num_b', 'TH_b','DIST_Vol_Oiseau']
    iti_arc_export = itineraire_arc.merge(courses_export[['id_course_num','N_train']]).rename({
        'heure_depart':'h_dep_num','heure_arrive':'h_arr_num'},axis = 1)
    iti_arc_export.loc[:,'heure_depart'] = np.vectorize(heure_from_xsltime)(iti_arc_export.loc[:,'h_dep_num'])
    iti_arc_export.loc[:,'heure_arrive'] = np.vectorize(heure_from_xsltime)(iti_arc_export.loc[:,'h_arr_num'])
    return iti_arc_export[itiarc_cols]

def GOAL_train(AG,courses,calendar,calendar_dates, lignes,Dates):
    ag_name = AG[['id_ag_num','stop_name']]
    ag_name.loc[:,'nom_gare'] = AG.loc[:,'stop_name'].str.replace('GARE DE ','')
    ag_simp = ag_name.loc[:,['id_ag_num','nom_gare']]
    cols_train = ['id_course_num','N_train','id_ligne_num','id_service_num','UIC_A','UIC_B']
    crs_train = courses[cols_train].merge(
        ag_simp, left_on = 'UIC_A', right_on = 'id_ag_num').merge(
        ag_simp, left_on = 'UIC_B', right_on = 'id_ag_num').drop(['id_ag_num_x','id_ag_num_y'],axis = 1)
    crs_train.loc[:,'DESCRIPTION'] = crs_train.loc[:,'nom_gare_x'] + ' < > ' + crs_train.loc[:,'nom_gare_y']
    if calendar is None :
        cal_date_traitem = calendar_dates.merge(Dates, left_on = 'date',right_on = 'Date_GTFS')
        cal_date_traitem = cal_date_traitem.loc[cal_date_traitem['exception_type']==1]
        debut_fin_serv = cal_date_traitem.groupby('id_service_num',as_index = False).agg(date_debut = ('date','min'),date_fin = ('date','max'))
        serv_type_jour_count = cal_date_traitem.groupby(['id_service_num','Type_Jour'],as_index = False)['Date_GTFS'].count()
        serv_type_jour_count.loc[:,'exist'] = np.where(serv_type_jour_count.loc[:,'Date_GTFS']>0,1,0)
        regime_circ = pd.pivot_table(serv_type_jour_count,values = 'exist', index = ['id_service_num'], columns = 'Type_Jour', fill_value = 0,  aggfunc=np.sum).reset_index()
        regime_circ.loc[:,'JOURS_CIRCULATION'] = 'J'+ regime_circ.loc[:,1].astype(str)+ regime_circ.loc[:,2].astype(str) + regime_circ.loc[:,3].astype(str)+ regime_circ.loc[:,4].astype(str)+ regime_circ.loc[:,5].astype(str) + regime_circ.loc[:,6].astype(str)+ regime_circ.loc[:,7].astype(str)
        regime_circ = regime_circ[['id_service_num','JOURS_CIRCULATION']]
        goal_train_1 = crs_train.merge(regime_circ, how = 'left')[['id_course_num','N_train','id_ligne_num','DESCRIPTION','JOURS_CIRCULATION']]
        goal_train_1.loc[goal_train_1['JOURS_CIRCULATION'].isnull()] = '0000000'
        goal_train = goal_train_1.merge(lignes[['id_ligne_num','mode']])
    elif sum(calendar['monday']) + sum(calendar['tuesday']) + sum(calendar['wednesday']) + sum(calendar['thursday']) + sum(calendar['friday']) + sum(calendar['saturday']) + sum(calendar['sunday'])  !=0:
        calendar.loc[:,'JOURS_CIRCULATION'] = 'J'+calendar.loc[:,'monday'].astype(int).astype(str)+ calendar.loc[:,'tuesday'].astype(int).astype(str)+ calendar.loc[:,'wednesday'].astype(int).astype(str)+ calendar.loc[:,'thursday'].astype(int).astype(str)+ calendar.loc[:,'friday'].astype(int).astype(str)+ calendar.loc[:,'saturday'].astype(int).astype(str)+ calendar.loc[:,'sunday'].astype(int).astype(str)
        goal_train_1 = crs_train.merge(calendar, how = 'left')[['id_course_num','N_train','id_ligne_num','DESCRIPTION','JOURS_CIRCULATION']]
        goal_train_1.loc[goal_train_1['JOURS_CIRCULATION'].isnull()] = '0000000'
        goal_train = goal_train_1.merge(lignes[['id_ligne_num','mode']])
    else :
        cal_date_traitem = calendar_dates.merge(Dates, left_on = 'date',right_on = 'Date_GTFS')
        cal_date_traitem = cal_date_traitem.loc[cal_date_traitem['exception_type']==1]
        debut_fin_serv = cal_date_traitem.groupby('id_service_num',as_index = False).agg(date_debut = ('date','min'),date_fin = ('date','max'))
        serv_type_jour_count = cal_date_traitem.groupby(['id_service_num','Type_Jour'],as_index = False)['Date_GTFS'].count()
        serv_type_jour_count.loc[:,'exist'] = np.where(serv_type_jour_count.loc[:,'Date_GTFS']>0,1,0)
        regime_circ = pd.pivot_table(serv_type_jour_count,values = 'exist', index = ['id_service_num'], columns = 'Type_Jour', fill_value = 0,  aggfunc=np.sum).reset_index()
        regime_circ.loc[:,'JOURS_CIRCULATION'] = 'J'+ regime_circ.loc[:,1].astype(str)+ regime_circ.loc[:,2].astype(str) + regime_circ.loc[:,3].astype(str)+ regime_circ.loc[:,4].astype(str)+ regime_circ.loc[:,5].astype(str) + regime_circ.loc[:,6].astype(str)+ regime_circ.loc[:,7].astype(str)
        regime_circ = regime_circ[['id_service_num','JOURS_CIRCULATION']]
        goal_train_1 = crs_train.merge(regime_circ, how = 'left')[['id_course_num','N_train','id_ligne_num','DESCRIPTION','JOURS_CIRCULATION']]
        goal_train_1.loc[goal_train_1['JOURS_CIRCULATION'].isnull()] = '0000000'
        goal_train = goal_train_1.merge(lignes[['id_ligne_num','mode']])
    return goal_train

def base_ferro_tbls(BaseFerro_PATH='C:/Users/wei.si/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/gtfs_miner/Resources/Base_Ferroviaire_User.accdb'):
    access_driver = pyodbc.dataSources()['MS Access Database']
    path_BF = (BaseFerro_PATH)
    with pyodbc.connect(driver = access_driver, dbq = path_BF) as conn_BF:
        arc_elem_corr = pd.read_sql_query('SELECT * FROM Corr_Arcs_Elémentaires_Liaisons',conn_BF)
        arc_elem = pd.read_sql_query('SELECT * FROM Arcs_Elémentaires',conn_BF)
        gares = pd.read_sql_query('SELECT * FROM Codes_Gares',conn_BF)
    return arc_elem_corr,arc_elem,gares

def export_access(table_name, var_name,str_create_table, str_insert, access_path='./GTFS.accdb' ):
    access_driver = pyodbc.dataSources()['MS Access Database']
    con = pyodbc.connect(driver = access_driver, dbq = access_path)
    cur = con.cursor()
    try:
        cur.execute(f"DROP TABLE [{table_name}]")
        cur.execute(str_create_table)
        cur.executemany(str_insert,var_name.itertuples(index=False))
    except pyodbc.ProgrammingError:
        cur.execute(str_create_table)
        cur.executemany(str_insert,var_name.itertuples(index=False))
    con.commit()
    cur.close()
    con.close()
    del con,cur

def iti_elem_lookup(to_do,table_arc_elem):
    debut_liaison = to_do[0]
    fin_de_liaison = to_do[1]
    # Prepare empty table
    iti_potentiel = pd.DataFrame(columns=['ID_ARC','FROMNODE','TONODE','LENGTH','order'])
    iti_potentiel['order'] = 0
    # First step : look for first iti_elem
    etape1 = table_arc_elem.loc[table_arc_elem['FROMNODE']==debut_liaison]
    etape1['order'] = 1
    iti_potentiel = pd.concat([iti_potentiel,etape1], ignore_index=True)
    if (debut_liaison not in table_arc_elem['FROMNODE'].values) or (fin_de_liaison not in table_arc_elem['TONODE'].values) :
        pathnotfound = pd.DataFrame({'FROM_Liaison' : [debut_liaison],'TO_Liaison' : [fin_de_liaison]})
        iti_arc_elem_final = pd.DataFrame(columns=['FROM_Liaison','TO_Liaison','ID_ARC','FROMNODE','TONODE','LENGTH','order'])
    else :
        # Loop until find the end of UIC_B_LIAISON
        max_iter = 500
        for i in range(1,max_iter):
            if fin_de_liaison in iti_potentiel.loc[:,'TONODE'].values:
                break
            etape = table_arc_elem.loc[table_arc_elem['FROMNODE'].isin(iti_potentiel.loc[iti_potentiel['order']==i,'TONODE'].values) &
                                 ~table_arc_elem['TONODE'].isin(iti_potentiel.loc[iti_potentiel['order']==i,'FROMNODE'].values)]
            etape['order'] = 1+i
            iti_potentiel = pd.concat([iti_potentiel,etape],ignore_index=True)
        # Remove unused itinerary
        iti_keep = iti_potentiel.loc[iti_potentiel['ID_ARC']==0]
        select_fin = iti_potentiel.loc[iti_potentiel['TONODE']==fin_de_liaison]
        iti_keep = pd.concat([iti_keep, select_fin],ignore_index=True)
        max_order = max(iti_potentiel['order'])
        for i in reversed(range(1,max_order+1)):
            gare_A_to_look = iti_keep.loc[iti_keep['order']==i,'FROMNODE'].values
            select = iti_potentiel.loc[iti_potentiel['TONODE'].isin(gare_A_to_look)& (iti_potentiel['order']==i-1)]
            iti_keep = pd.concat([iti_keep, select], ignore_index=True) 
        iti_arc_elem_final = iti_keep.sort_values(by='order', ascending=True)
        iti_arc_elem_final['FROM_Liaison'] = to_do[0]
        iti_arc_elem_final['TO_Liaison'] = to_do[1]
        iti_arc_elem_final = iti_arc_elem_final[['FROM_Liaison','TO_Liaison','ID_ARC','FROMNODE','TONODE','LENGTH','order']]
        pathnotfound = pd.DataFrame(columns=['FROM_Liaison' ,'TO_Liaison'])
    return(iti_arc_elem_final,pathnotfound)

def duree_arc(df):
    duree = max(df['heure_arrive']) - min(df['heure_depart'])
    return duree

def heure_goal(horaire_excel):
    horaire = f'H{int(math.modf(horaire_excel*24)[1]):02}{int(math.modf(horaire_excel*24)[0]*60):02}'
    return horaire

def GOAL_trainmarche(iti_arc_export,goal_train):
    cols_trainmarche = ['id_course_num','id_ligne_num','N_train','FROMNODE','TONODE','order','h_dep_2','h_arr_2']
    train_marche = iti_arc_export.merge(goal_train[['id_course_num']])[cols_trainmarche]
    train_marche.order = train_marche.order.astype(np.int8)+1
    train_marche['HEURE_SORTIE'] = np.vectorize(heure_goal)(train_marche['h_dep_2'])
    train_marche['HEURE_ARRIVEE'] = np.vectorize(heure_goal)(train_marche['h_arr_2'])
    Goal_trainmarche = train_marche.drop(['h_dep_2','h_arr_2'],axis = 1).rename({'order':'SEQUENCE'},axis = 1)
    return Goal_trainmarche

def arc_elementaire_create(itineraire_export,iti_arc_export,lignes_export,AG,node_df, link_df):
    node = node_df[['NO','NAME']]
    link = link_df[['ID_ARC','FROMNODE','TONODE','LENGTH']]
    iti_mode = itineraire_export.merge(lignes_export[['id_ligne_num','mode']])
    iti_lourd = iti_mode.loc[iti_mode['mode'].isin(['train','tramway'])]
    toute_gares = iti_lourd.groupby(['id_ag_num'],as_index = False)['id_course_num'].count()
    toute_gares['Dans_Base'] = toute_gares['id_ag_num'].isin(node['NO'])
    gare_non_exist = toute_gares.loc[~toute_gares['Dans_Base'],'id_ag_num']
    list_gare_a_ajouter = AG.loc[AG['id_ag_num'].isin(gare_non_exist)]
    itiarc_mode = iti_arc_export.merge(lignes_export[['id_ligne_num','mode']])
    itiarc_lourd = itiarc_mode.loc[itiarc_mode['mode'].isin(['train','tramway'])]
    liaison_GTFS = itiarc_lourd.groupby(['id_ag_num_a','id_ag_num_b']).count().reset_index()[['id_ag_num_a','id_ag_num_b']].rename({'id_ag_num_a':'FROM_Liaison','id_ag_num_b':'TO_Liaison'},axis = 1)
    liaison_GTFS_f =  liaison_GTFS.loc[~(liaison_GTFS['FROM_Liaison'].isin(gare_non_exist)|liaison_GTFS['TO_Liaison'].isin(gare_non_exist))]
    list_arc_non_exist = pd.DataFrame(columns=['FROMNODE','TONODE'])
    iti_elem_to_add = pd.DataFrame(columns=['FROM_Liaison','TO_Liaison','ID_ARC','FROMNODE','TONODE','LENGTH','order'])

    for i, row in liaison_GTFS_f.iterrows():
        liais_arc, empty_arc = iti_elem_lookup(row,link)
        list_arc_non_exist = pd.concat([list_arc_non_exist , empty_arc],ignore_index=True)
        iti_elem_to_add = pd.concat([iti_elem_to_add,liais_arc],ignore_index=True)
    # jointure avec itineraire arc
    iti_arc_elem = itiarc_lourd.merge(iti_elem_to_add, left_on=['id_ag_num_a','id_ag_num_b'], right_on=['FROM_Liaison','TO_Liaison'],how = 'left')
    iti_arc_elem.loc[iti_arc_elem['FROMNODE'].isna(),'NON_EXIST'] =1
    list_arc_non_trouve = iti_arc_elem.loc[iti_arc_elem['FROMNODE'].isna(),['id_ap_num_a','id_ag_num_a','NON_EXIST']].groupby(['id_ap_num_a','id_ag_num_a'],as_index = False)['NON_EXIST'].count()
    iti_arc_elem.loc[iti_arc_elem['NON_EXIST']==1,'FROMNODE' ] = iti_arc_elem.loc[iti_arc_elem['NON_EXIST']==1,'id_ag_num_a' ]
    iti_arc_elem.loc[iti_arc_elem['NON_EXIST']==1,'TONODE' ] = iti_arc_elem.loc[iti_arc_elem['NON_EXIST']==1,'id_ag_num_b' ]
    iti_arc_elem.reset_index(drop = True, inplace = True)
    iti_arc_elem['order'] = iti_arc_elem.groupby('id_course_num').cumcount()
    iti_arc_elem['sum_length'] = iti_arc_elem.groupby(['id_course_num', 'ordre_a'])['LENGTH'].transform(np.sum)
    iti_arc_elem['ratio'] = iti_arc_elem['LENGTH']/iti_arc_elem['sum_length']
    iti_arc_elem['min_dep'] = iti_arc_elem.groupby(['id_course_num', 'ordre_a'])['h_dep_num'].transform(min)
    iti_arc_elem['max_arr'] = iti_arc_elem.groupby(['id_course_num', 'ordre_a'])['h_arr_num'].transform(max)
    iti_arc_elem['duree'] = iti_arc_elem['max_arr'] - iti_arc_elem['min_dep']
    iti_arc_elem['tps_arc'] = iti_arc_elem['ratio'] * iti_arc_elem['duree']
    iti_arc_elem['tps_arc_csum'] = iti_arc_elem.groupby(['id_course_num', 'ordre_a'])['tps_arc'].transform(np.cumsum)
    iti_arc_elem['h_arr_2'] =  iti_arc_elem['min_dep'] + iti_arc_elem['tps_arc_csum']
    iti_arc_elem['h_arr_2'] = np.where(iti_arc_elem['h_arr_2'].isna(), iti_arc_elem['h_arr_num'], iti_arc_elem['h_arr_2'])
    iti_arc_elem['h_dep_2'] = iti_arc_elem.groupby(['id_course_num', 'ordre_a'])['h_arr_2'].shift(1)
    iti_arc_elem['h_dep_2'] = np.where(iti_arc_elem['h_dep_2'].isna(), iti_arc_elem['min_dep'], iti_arc_elem['h_dep_2'])
    iti_arc_elem['h_arr_2'] = np.where(iti_arc_elem['h_arr_2'].isna(), iti_arc_elem['h_arr_num'], iti_arc_elem['h_arr_2'])
    iti_arc_elem_f = iti_arc_elem[['id_course_num', 'id_ligne_num',    'id_service_num', 'ordre_a',  'h_dep_num',
       'id_ap_num_a',   'id_ag_num_a', 'TH_a',       'ordre_b',  'h_arr_num',   'id_ap_num_b', 'id_ag_num_b',
       'TH_b',       'N_train',          'mode', 'FROMNODE', 'TONODE',        'LENGTH',         'order',
        'NON_EXIST',  'h_dep_2', 'h_arr_2']]
    return iti_arc_elem_f,list_arc_non_exist,list_gare_a_ajouter

def passage_arc_elem(iti_arc_elem, service_jour_type, node_df,type_vac):
    iti_typejour = iti_arc_elem.merge(service_jour_type, on =['id_ligne_num','id_service_num'])
    nb_passage = iti_typejour.groupby(
        ['FROMNODE', 'TONODE', type_vac], as_index = False)['id_course_num'].count().sort_values(['FROMNODE', 'TONODE']).rename({'id_course_num':'nb_passage'},axis = 1)
    nb_passage_pv = pd.pivot_table(nb_passage,values = 'nb_passage', index = ['FROMNODE','TONODE'], columns = type_vac, fill_value = 0,  aggfunc=np.sum).reset_index()
    nb_passage_pv = nb_passage_pv.merge(node_df[['NO','NAME','LON','LAT']], left_on = 'FROMNODE', right_on = 'NO').merge(node_df[['NO','NAME','LON','LAT']], left_on = 'TONODE', right_on = 'NO').drop(['NO_x', 'NO_y'], axis=1).reset_index(drop = True)
    nb_passage_pv['ID']= nb_passage_pv.index
    return nb_passage_pv

def passage_arc(iti_arc, service_jour_type, node,type_vac):
    iti_typejour = iti_arc.merge(service_jour_type, on =['id_ligne_num','id_service_num'])
    nb_passage = iti_typejour.groupby(
        ['id_ag_num_a', 'id_ag_num_b', type_vac], as_index = False)['id_course_num'].count().sort_values(['id_ag_num_a', 'id_ag_num_b']).rename({'id_course_num':'nb_passage', 'id_ag_num_a' : 'FROMNODE', 'id_ag_num_b': 'TONODE'},axis = 1)
    nb_passage_pv = pd.pivot_table(nb_passage,values = 'nb_passage', index = ['FROMNODE','TONODE'], columns = type_vac, fill_value = 0,  aggfunc=np.sum).reset_index()
    nb_passage_pv = nb_passage_pv.merge(node[['NO','NAME','LON','LAT']], left_on = 'FROMNODE', right_on = 'NO').merge(node[['NO','NAME','LON','LAT']], left_on = 'TONODE', right_on = 'NO').drop(['NO_x', 'NO_y'], axis=1).reset_index(drop = True)
    nb_passage_pv['ID']= nb_passage_pv.index
    return nb_passage_pv

def trace_sl_vol_oiseau(iti,ag, sl):
    crs_sample = iti.groupby(['sous_ligne'])['id_course_num'].first().reset_index()
    iti_sample = iti.loc[iti['id_course_num'].isin(crs_sample['id_course_num'])]
    ag_simple = ag[['id_ag_num','stop_lon','stop_lat']]
    iti_merge_ag = iti_sample.merge(ag_simple, on = 'id_ag_num') # get stop_lon/lat 
    sl_simple = sl[['sous_ligne','route_short_name','route_long_name']]
    iti_merge_ag_sl = iti_merge_ag.merge(sl_simple, on = 'sous_ligne')
    result = iti_merge_ag_sl.sort_values(['id_course_num','ordre'])
    return result




def create_qgsLines(tbl_trace_sl, layerName, lon, lat):
    # create a new memory layer
    layer = QgsVectorLayer("LineString?crs=EPSG:4326", layerName, "memory")
    layer_pr = layer.dataProvider()
    layer_pr.addAttributes([QgsField("sous_ligne", QVariant.String),
                            QgsField("id_ligne_num", QVariant.Int),
                            QgsField("route_short_name", QVariant.String),
                            QgsField("route_long_name", QVariant.String),
                            QgsField("length", QVariant.Double)])
    layer.updateFields()

    # calculer distance with long/lat
    dist_calculator = QgsDistanceArea()
    dist_calculator.setEllipsoid('WGS84')
    dist_calculator.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())

    sl_grp = tbl_trace_sl.groupby(['sous_ligne',"id_ligne_num","route_short_name","route_long_name"]).size().reset_index()
    for idx1,row1 in sl_grp.iterrows():
        tbl = tbl_trace_sl.loc[tbl_trace_sl['sous_ligne'] == row1['sous_ligne']]
        points = []
        for idx2, row2 in tbl.iterrows():
            pts = QgsPointXY(row2[lon] ,row2[lat])
            points.append(pts)
        line = QgsGeometry.fromPolylineXY(points)
        length = dist_calculator.measureLength(line)
        # create a new feature
        seg = QgsFeature()
        # add the geometry to the feature,
        seg.setGeometry(line)
        seg.setAttributes([row1['sous_ligne'],row1["id_ligne_num"],row1["route_short_name"],row1["route_long_name"], length])
        # ...it was here that you can add attributes, after having defined....
        # add the geometry to the layer
        layer_pr.addFeatures( [ seg ] )
        # update extent of the layer (not necessary)
        layer.updateExtents()
    return layer

def Qgs_PassageAG(nb_passage_ag_typejour,output_path):
    #Create a new memory layer
    psg_ag_layer = QgsVectorLayer("Point", "passage_ag_layer", "memory")
    psg_ag_layer_pr = psg_ag_layer.dataProvider()
    psg_ag_layer_pr.addAttributes([QgsField("id_ag_num", QVariant.Int)])    
    psg_ag_layer.updateFields()

    for idx, row in nb_passage_ag_typejour.iterrows():
        point = QgsPointXY(row['stop_lon'], row['stop_lat'])
        point_geom = QgsGeometry.fromPointXY(point)
        point_feat = QgsFeature()
        point_feat.setGeometry(point_geom)
        point_feat.setAttributes([row['id_ag_num']])
        psg_ag_layer_pr.addFeatures( [ point_feat ] )
        psg_ag_layer.updateExtents()
    QgsProject.instance().addMapLayer(psg_ag_layer)
    
    nb_psg_ag_uri = f"file:///{output_path}/E_1_Nombre_Passage_AG.csv?type=csv&delimiter=;&detectTypes=yes"
    nb_psg_ag_csv = QgsVectorLayer(nb_psg_ag_uri, 'tbl_Nombre_Passage_AG', 'delimitedtext')
    QgsProject.instance().addMapLayer(nb_psg_ag_csv)

    result = processing.run('qgis:joinattributestable', 
        {'INPUT':psg_ag_layer,
        'FIELD': 'id_ag_num',
        'INPUT_2':nb_psg_ag_csv,
        'FIELD_2':'id_ag_num',
        'OUTPUT':'TEMPORARY_OUTPUT'})#
    # Load the output layer into the QGIS project
    psg_ag = result['OUTPUT'] 
    QgsProject.instance().removeMapLayer(psg_ag_layer)
    QgsProject.instance().removeMapLayer(nb_psg_ag_csv)      
    return psg_ag

def Qgs_PassageArc(nb_passage_arc, output_path):
    psg_arc_layer = QgsVectorLayer("LineString", "passage_arc_layer", "memory")
    psg_arc_layer_pr = psg_arc_layer.dataProvider()
    psg_arc_layer_pr.addAttributes([QgsField("ID", QVariant.Int),
        QgsField("FROMNODE",  QVariant.Int),
        QgsField("TONODE", QVariant.Int)])
    psg_arc_layer.updateFields()

    for idx, row in nb_passage_arc.iterrows():
        line_start = QgsPoint(row['LON_x'] ,row['LAT_x'])
        line_end = QgsPoint(row['LON_y'],row['LAT_y'])
        line = QgsGeometry.fromPolyline([line_start,line_end])
        # create a new feature
        seg = QgsFeature()
        # add the geometry to the feature,
        seg.setGeometry(line)
        seg.setAttributes([row['ID'], row['FROMNODE'],row['TONODE'] ])
        # ...it was here that you can add attributes, after having defined....
        # add the geometry to the layer
        psg_arc_layer_pr.addFeatures( [ seg ] )
        # update extent of the layer (not necessary)
        psg_arc_layer.updateExtents()
        # show the line
    QgsProject.instance().addMapLayer(psg_arc_layer)

    nb_psg_arc_uri = f"file:///{output_path}/E_4_Nombre_Passage_Arc.csv?type=csv&delimiter=;&maxFields=10000&detectTypes=yes"
    nb_psg_arc_csv = QgsVectorLayer(nb_psg_arc_uri, 'tbl_Nombre_Passage_Arc', 'delimitedtext')
    QgsProject.instance().addMapLayer(nb_psg_arc_csv)
    shpField='ID'
    csvField='ID'
    result = processing.run('qgis:joinattributestable', 
        {'INPUT':psg_arc_layer,
        'FIELD': 'ID',
        'INPUT_2':nb_psg_arc_csv,
        'FIELD_2':'ID',
        'OUTPUT':'TEMPORARY_OUTPUT'})#
    
    psg_arc = result['OUTPUT']
    QgsProject.instance().removeMapLayer(nb_psg_arc_csv)
    QgsProject.instance().removeMapLayer(psg_arc_layer)
    return psg_arc

def shapefileWriter(QgsLayerObject, output_path, fileName):          
    save_options = QgsVectorFileWriter.SaveVectorOptions()
    save_options.driverName = "ESRI Shapefile"
    save_options.fileEncoding = "UTF-8"
    transform_context = QgsProject.instance().transformContext()
    error = QgsVectorFileWriter.writeAsVectorFormatV3(QgsLayerObject,
                                              f"{output_path}/{fileName}.shp",
                                              transform_context,
                                              save_options)
    if error[0] == QgsVectorFileWriter.NoError:
        print("success again!")
    else:
      print(error)
    return error

def corr_sl_shape(courses, trips, shapes, sl):
    '''
    A appliquer après création de la table courses
    '''
    crs_sample = courses.groupby(['sous_ligne'])['id_course_num'].first().reset_index()
    corr = trips[['id_course_num','shape_id']]
    corr_sl_shp = crs_sample.merge(corr, on = 'id_course_num')
    corr = corr_sl_shp[['sous_ligne','shape_id']]
    sl_simple = sl[['sous_ligne','id_ligne_num','route_short_name','route_long_name']]
    corr2 = sl_simple.merge(corr, on = 'sous_ligne')
    result = shapes.merge(corr2, on = 'shape_id')
    return result

def aggregate_polylines_by_category(layer, layerName):
    """
    Aggregates polylines by category.
    
    :param layer: QgsVectorLayer - The input polyline layer containing polylines and a category field.
    :return: None
    """
    # Prepare dictionaries to store geometry unions and distance sums
    geom_dict = {}
    distance_sum_dict = {}

    # Iterate over features in the layer
    for feature in layer.getFeatures():
        id_ligne_num = feature["id_ligne_num"]
        route_short_name = feature["route_short_name"]
        route_long_name = feature["route_long_name"]
        length = feature["length"]

        # Use tuple of (id_line, line_name) as a key for grouping
        key = (id_ligne_num, route_short_name,route_long_name)

        # Get the geometry of the feature
        geom = feature.geometry()

        # If key exists, union the geometries and sum the distances
        if key in geom_dict:
            geom_dict[key] = geom_dict[key].combine(geom)
            distance_sum_dict[key] += length
        else:
            geom_dict[key] = geom
            distance_sum_dict[key] = length

    # Now create a new output layer to store the results
    output_layer = QgsVectorLayer("MultiLineString?crs=" + layer.crs().toWkt(), layerName, "memory")
    output_provider = output_layer.dataProvider()

    # Add necessary fields
    output_provider.addAttributes([QgsField("id_ligne_num", QVariant.Int),
                                   QgsField("route_short_name", QVariant.String),
                                   QgsField("route_long_name", QVariant.String),
                                   QgsField("Distance", QVariant.Double)])
    output_layer.updateFields()

    # calculer distance with long/lat
    dist_calculator = QgsDistanceArea()
    dist_calculator.setEllipsoid('WGS84')
    dist_calculator.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
    # Add the aggregated features to the output layer
    for key, geom in geom_dict.items():
        id_ligne_num, route_short_name,route_long_name = key
        Distance = dist_calculator.measureLength(geom)

        # Create a new feature
        out_feature = QgsFeature(output_layer.fields())
        out_feature.setGeometry(geom)
        out_feature.setAttributes([id_ligne_num, route_short_name,route_long_name,Distance])

        # Add the feature to the output layer
        output_provider.addFeature(out_feature)

    # Add the output layer to the QGIS project    
    return output_layer


