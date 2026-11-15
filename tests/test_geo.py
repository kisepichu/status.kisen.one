import json
import os
import tempfile
import unittest

from kisenone_status.geo import GeoIndex


def square(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def feature(properties, geometry):
    return {"type": "Feature", "properties": properties, "geometry": geometry}


class GeoIndexTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        jp = {
            "type": "FeatureCollection",
            "features": [
                # A 県は真ん中に穴がある
                feature({"N03_001": "A県"}, {"type": "Polygon", "coordinates": [square(139, 35, 140, 36), square(139.4, 35.4, 139.6, 35.6)]}),
                feature({"N03_001": "B県"}, {"type": "MultiPolygon", "coordinates": [[square(140, 35, 141, 36)], [square(142, 37, 142.1, 37.1)]]}),
            ],
        }
        world = {
            "type": "FeatureCollection",
            "features": [
                feature({"ISO_A2_EH": "XX"}, {"type": "Polygon", "coordinates": [square(130, 30, 150, 40)]}),
                feature({"ISO_A2_EH": "-99"}, {"type": "Polygon", "coordinates": [square(100, 0, 110, 10)]}),
            ],
        }
        jp_path = os.path.join(tmp.name, "jp.json")
        world_path = os.path.join(tmp.name, "world.json")
        for path, data in [(jp_path, jp), (world_path, world)]:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        self.geo = GeoIndex(jp_path, world_path)

    def test_point_inside_prefecture(self):
        self.assertEqual(self.geo.locate(35.5, 139.2), ("JP", "A県"))
        self.assertEqual(self.geo.locate(37.05, 142.05), ("JP", "B県"))

    def test_point_in_hole_is_not_in_prefecture(self):
        self.assertEqual(self.geo.locate(35.5, 139.5), ("XX", None))

    def test_point_just_outside_japan_snaps_to_nearest_prefecture(self):
        # B 県の東端から約 1.8 km
        self.assertEqual(self.geo.locate(35.5, 141.02), ("JP", "B県"))

    def test_point_farther_than_three_km_falls_back_to_country(self):
        # B 県の東端から約 3.6 km
        self.assertEqual(self.geo.locate(35.5, 141.04), ("XX", None))

    def test_unknown_country_code_and_open_sea_are_none(self):
        self.assertEqual(self.geo.locate(5, 105), (None, None))
        self.assertEqual(self.geo.locate(-30, -150), (None, None))


if __name__ == "__main__":
    unittest.main()
