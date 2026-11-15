import unittest

from kisenone_status.location import (
    Point,
    fetch_points,
    is_moving,
    location_section,
    parse_point,
    today_km,
)
from kisenone_status.timeutil import fixed_tz

JST = fixed_tz(540)
NOW = 1794711600  # 2026-11-15 12:00 JST
DAY_START = NOW - 12 * 3600


class ParsePointTest(unittest.TestCase):
    def test_reads_dawarich_point(self):
        raw = {"timestamp": NOW, "latitude": "35.68", "longitude": "139.76", "accuracy": 12, "velocity": "0"}
        self.assertEqual(parse_point(raw), Point(NOW, 35.68, 139.76, 12.0))

    def test_missing_accuracy_is_allowed(self):
        raw = {"timestamp": NOW, "latitude": "35.68", "longitude": "139.76", "accuracy": None}
        self.assertIsNone(parse_point(raw).accuracy)

    def test_broken_point_is_none(self):
        self.assertIsNone(parse_point({"timestamp": NOW, "latitude": None, "longitude": "139"}))


class DistanceTest(unittest.TestCase):
    def test_inaccurate_points_are_skipped(self):
        points = [
            Point(NOW - 300, 35.0, 139.0, 10),
            Point(NOW - 200, 35.1, 139.5, 500),  # 精度 500 m: 除く
            Point(NOW - 100, 35.2, 139.0, None),
        ]
        # 経線に沿って 0.2 度 ≒ 22.24 km
        self.assertAlmostEqual(today_km(points), 22.24, places=1)


class MovingTest(unittest.TestCase):
    def test_fast_recent_points_are_moving(self):
        # 2 分で約 1.1 km ≒ 33 km/h
        points = [Point(NOW - 180, 35.0, 139.0, 10), Point(NOW - 60, 35.01, 139.0, 10)]
        self.assertTrue(is_moving(points, NOW))

    def test_old_last_point_is_not_moving(self):
        points = [Point(NOW - 1320, 35.0, 139.0, 10), Point(NOW - 1200, 35.01, 139.0, 10)]
        self.assertFalse(is_moving(points, NOW))

    def test_walking_speed_is_not_moving(self):
        # 2 分で約 110 m ≒ 3.3 km/h
        points = [Point(NOW - 180, 35.0, 139.0, 10), Point(NOW - 60, 35.001, 139.0, 10)]
        self.assertFalse(is_moving(points, NOW))

    def test_single_point_is_not_moving(self):
        self.assertFalse(is_moving([Point(NOW - 60, 35.0, 139.0, 10)], NOW))


class FakeGeo:
    def locate(self, lat, lon):
        return "JP", "東京都"


class LocationSectionTest(unittest.TestCase):
    def test_outputs_no_coordinates(self):
        latest = Point(NOW - 60, 35.68, 139.76, 10)
        section = location_section(latest, [latest], NOW, JST, FakeGeo())
        self.assertEqual(
            section,
            {
                "country": "JP",
                "pref": "東京都",
                "moving": False,
                "today_km": 0.0,
                "point_at": "2026-11-15T11:59:00+09:00",
                "at": "2026-11-15T12:00:00+09:00",
            },
        )

    def test_no_points_at_all_is_none(self):
        self.assertIsNone(location_section(None, [], NOW, JST, FakeGeo()))


class FetchPointsTest(unittest.TestCase):
    def test_reads_latest_and_all_pages_of_today(self):
        calls = []

        def get_json(url, headers):
            calls.append((url, dict(headers)))
            if "order=desc" in url:
                return [{"timestamp": NOW - 10, "latitude": "35", "longitude": "139", "accuracy": 5}], {}
            page = int(url.rsplit("page=", 1)[1])
            batch = [{"timestamp": DAY_START + page, "latitude": "35", "longitude": "139", "accuracy": 5}]
            return batch, {"X-Total-Pages": "2"}

        latest, today = fetch_points(get_json, "http://127.0.0.1:3001/", "k", NOW, JST)
        self.assertEqual(latest.t, NOW - 10)
        self.assertEqual([p.t for p in today], [DAY_START + 1, DAY_START + 2])
        self.assertIn(f"start_at={DAY_START}", calls[1][0])
        for _, headers in calls:
            self.assertEqual(headers["Authorization"], "Bearer k")
            self.assertEqual(headers["X-Forwarded-Proto"], "https")


if __name__ == "__main__":
    unittest.main()
