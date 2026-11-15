"""同梱する実際の境界データでの判定。データの path を環境変数で渡したとき (nix flake check) だけ走る。"""
import os
import unittest

from kisenone_status.geo import GeoIndex

JP = os.environ.get("KISENONE_GEO_JP")
WORLD = os.environ.get("KISENONE_GEO_WORLD")


@unittest.skipUnless(JP and WORLD, "KISENONE_GEO_JP / KISENONE_GEO_WORLD が無い")
class RealBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geo = GeoIndex(JP, WORLD)

    def test_points_near_tokyo_borders(self):
        cases = {
            "羽田空港": ((35.5494, 139.7798), "東京都"),
            "お台場": ((35.6267, 139.7765), "東京都"),
            "二子玉川": ((35.6116, 139.6268), "東京都"),
            "武蔵小杉": ((35.5765, 139.6596), "神奈川県"),
            "和光市": ((35.7812, 139.6057), "埼玉県"),
            "町田駅": ((35.5422, 139.4455), "東京都"),
            "相模大野": ((35.5326, 139.4378), "神奈川県"),
            "八丈島": ((33.1100, 139.7900), "東京都"),
        }
        for name, ((lat, lon), pref) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.geo.locate(lat, lon), ("JP", pref))

    def test_middle_of_tokyo_bay_has_no_prefecture(self):
        self.assertIsNone(self.geo.locate(35.45, 139.85)[1])

    def test_abroad_gives_country_only(self):
        self.assertEqual(self.geo.locate(37.5665, 126.9780), ("KR", None))
        self.assertEqual(self.geo.locate(21.3069, -157.8583), ("US", None))


if __name__ == "__main__":
    unittest.main()
