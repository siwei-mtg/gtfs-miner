"""
GTFS 核心模块单元测试 (test_gtfs_core.py)
用于验证 gtfs_utils 和 gtfs_norm 的正确性。
"""

import pandas as pd
import numpy as np
import unittest
from app.services.gtfs_core.gtfs_utils import norm_upper_str, getDistHaversine, heure_from_xsltime
from app.services.gtfs_core.gtfs_norm import stops_norm, trips_norm

class TestGTFSCore(unittest.TestCase):
    
    def test_utils_norm(self):
        s = pd.Series(["À la Gare", "Café-Restaurant"])
        normed = norm_upper_str(s)
        self.assertEqual(normed.tolist(), ["A LA GARE", "CAFE-RESTAURANT"])
        
    def test_utils_dist(self):
        # Paris (48.8566, 2.3522) to Lyon (45.7640, 4.8357) ~391 km
        dist = getDistHaversine(48.8566, 2.3522, 45.7640, 4.8357)
        self.assertAlmostEqual(dist / 1000, 391.0, delta=1.0)
        
    def test_utils_time(self):
        # 0.5 day = 12:00
        self.assertEqual(heure_from_xsltime(0.5), "12:00")
        
    def test_norm_stops(self):
        raw_stops = pd.DataFrame({
            'stop_id': [1, 2],
            'stop_name': ['A', 'B'],
            'stop_lat': [' 48.12 ', '48.13'],
            'stop_lon': [2.1, 2.2],
            'location_type': [np.nan, 1],
            'parent_station': [np.nan, '100']
        })
        processed = stops_norm(raw_stops)
        self.assertEqual(processed.stop_name.tolist(), ["A", "B"])
        self.assertEqual(processed.location_type.tolist(), [0, 1])
        self.assertEqual(processed.stop_lat.dtype, np.float32)

    def test_norm_trips(self):
        raw_trips = pd.DataFrame({
            'route_id': ['R1'],
            'service_id': ['S1'],
            'trip_id': ['T1']
        })
        processed = trips_norm(raw_trips)
        self.assertIn('id_course_num', processed.columns)
        self.assertEqual(processed.trip_id.iloc[0], 'T1')

if __name__ == '__main__':
    unittest.main()
