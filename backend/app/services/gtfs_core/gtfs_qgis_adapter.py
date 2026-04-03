"""
GTFS QGIS 适配器 (gtfs_qgis_adapter.py)

功能：
1. 将 DataFrame 转换为 QGIS 内存图层 (Point/LineString)。
2. 调用 QGIS 处理算法 (Processing) 进行空间关联 (Join)。
3. 使用 QgsVectorFileWriter 导出 SHP 文件。

约束：
本模块是唯一允许导入 qgis.core 的算法相关模块。
"""

from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature, QgsGeometry, 
    QgsPointXY, QgsPoint, QgsProject, QgsVectorFileWriter,
    QgsDistanceArea, QgsCoordinateTransformContext, QgsUnitTypes,
    QgsMessageLog, Qgis
)
from qgis.PyQt.QtCore import QVariant
import processing
import pandas as pd
from typing import Optional

def shapefileWriter(layer: QgsVectorLayer, output_path: str, fileName: str) -> bool:
    """
    将 QGIS 图层保存为 ESRI Shapefile。
    """
    save_options = QgsVectorFileWriter.SaveVectorOptions()
    save_options.driverName = "ESRI Shapefile"
    save_options.fileEncoding = "UTF-8"
    transform_context = QgsProject.instance().transformContext()
    
    dest_path = f"{output_path}/{fileName}.shp"
    error = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, dest_path, transform_context, save_options
    )
    
    if error[0] == QgsVectorFileWriter.NoError:
        print(f"Success: {dest_path} saved.")
        return True
    else:
        print(f"Error saving {dest_path}: {error}")
        return False

def create_qgsLines(df: pd.DataFrame, layerName: str, lon_col: str, lat_col: str) -> QgsVectorLayer:
    """
    根据坐标点序列生成 QGIS 线路图层。
    Input Schema: [sous_ligne, id_ligne_num, route_short_name, route_long_name, {lon_col}, {lat_col}]
    """
    layer = QgsVectorLayer("LineString?crs=EPSG:4326", layerName, "memory")
    pr = layer.dataProvider()
    pr.addAttributes([
        QgsField("sous_ligne", QVariant.String),
        QgsField("id_ligne_num", QVariant.Int),
        QgsField("route_short_name", QVariant.String),
        QgsField("route_long_name", QVariant.String),
        QgsField("length", QVariant.Double)
    ])
    layer.updateFields()

    dist_calc = QgsDistanceArea()
    dist_calc.setEllipsoid('WGS84')
    dist_calc.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())

    # 按子路线分组生成线路
    groups = df.groupby(['sous_ligne', 'id_ligne_num', 'route_short_name', 'route_long_name'])
    for (sl, id_l, rsn, rln), tbl in groups:
        points = [QgsPointXY(row[lon_col], row[lat_col]) for _, row in tbl.iterrows()]
        if len(points) < 2: continue
        
        line_geom = QgsGeometry.fromPolylineXY(points)
        length = dist_calc.measureLength(line_geom)
        
        feat = QgsFeature(layer.fields())
        feat.setGeometry(line_geom)
        feat.setAttributes([sl, id_l, rsn, rln, length])
        pr.addFeature(feat)
        
    layer.updateExtents()
    return layer

def Qgs_PassageAG(nb_passage_df: pd.DataFrame, csv_path: str) -> Optional[QgsVectorLayer]:
    """
    生成站点经过次数图层，并关联 CSV 属性。
    """
    # 1. 创建基础位置点层
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "temp_ag", "memory")
    pr = layer.dataProvider()
    pr.addAttributes([QgsField("id_ag_num", QVariant.Int)])
    layer.updateFields()

    for _, row in nb_passage_df.iterrows():
        feat = QgsFeature(layer.fields())
        feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(row['stop_lon'], row['stop_lat'])))
        feat.setAttributes([row['id_ag_num']])
        pr.addFeature(feat)
    
    # 2. 加载 CSV 虚拟图层用于 Join
    uri = f"file:///{csv_path}?type=csv&delimiter=;&detectTypes=yes"
    csv_layer = QgsVectorLayer(uri, 'temp_csv', 'delimitedtext')
    QgsProject.instance().addMapLayer(csv_layer)
    QgsProject.instance().addMapLayer(layer)

    # 3. 使用 Processing 进行属性挂接
    result = processing.run('qgis:joinattributestable', {
        'INPUT': layer,
        'FIELD': 'id_ag_num',
        'INPUT_2': csv_layer,
        'FIELD_2': 'id_ag_num',
        'OUTPUT': 'TEMPORARY_OUTPUT'
    })
    
    # 4. 清理临时层
    QgsProject.instance().removeMapLayer(layer)
    QgsProject.instance().removeMapLayer(csv_layer)
    
    return result['OUTPUT']

def aggregate_polylines_by_category(layer: QgsVectorLayer, layerName: str) -> QgsVectorLayer:
    """
    将子路线段聚合为完整的线路。
    """
    # 聚合逻辑依赖于 QGIS 几何合并
    geom_dict = {}
    attr_dict = {}

    for feat in layer.getFeatures():
        key = feat["id_ligne_num"]
        geom = feat.geometry()
        if key in geom_dict:
            geom_dict[key] = geom_dict[key].combine(geom)
        else:
            geom_dict[key] = geom
            attr_dict[key] = (feat["route_short_name"], feat["route_long_name"])

    out_layer = QgsVectorLayer("MultiLineString?crs=" + layer.crs().toWkt(), layerName, "memory")
    pr = out_layer.dataProvider()
    pr.addAttributes([
        QgsField("id_ligne_num", QVariant.Int),
        QgsField("route_short_name", QVariant.String),
        QgsField("route_long_name", QVariant.String),
        QgsField("Distance", QVariant.Double)
    ])
    out_layer.updateFields()

    dist_calc = QgsDistanceArea()
    dist_calc.setEllipsoid('WGS84')
    
    for id_l, geom in geom_dict.items():
        rsn, rln = attr_dict[id_l]
        dist = dist_calc.measureLength(geom)
        out_feat = QgsFeature(out_layer.fields())
        out_feat.setGeometry(geom)
        out_feat.setAttributes([id_l, rsn, rln, dist])
        pr.addFeature(out_feat)
        
    return out_layer
