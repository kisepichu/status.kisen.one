import json
import os
import tempfile
import unittest

from kisenone_status.human import (
    PushError,
    delegated_ratio,
    human_section,
    parse_push,
    read_samples,
    record_push,
)
from kisenone_status.timeutil import fixed_tz

JST = fixed_tz(540)
NOW = 1794711600  # 2026-11-15 12:00 JST


class ParsePushTest(unittest.TestCase):
    def test_accepts_category_and_recent_epoch(self):
        self.assertEqual(parse_push(f"reading {NOW - 600}", NOW), ("reading", NOW - 600))

    def test_rejects_malformed_commands(self):
        for command in [
            "",
            "reading",
            f"hacking {NOW}",
            f"reading {NOW} ; rm -rf /",
            "reading 2026-11-15T12:00",
            f"reading {NOW - 8 * 86400}",
            f"reading {NOW + 3600}",
        ]:
            with self.subTest(command=command), self.assertRaises(PushError):
                parse_push(command, NOW)


class RecordPushTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.log = os.path.join(self.dir, "human.log")

    def test_keeps_latest_state_and_every_sample(self):
        record_push(self.dir, "reading", NOW - 60, NOW - 30)
        record_push(self.dir, "eating", NOW, NOW)
        with open(os.path.join(self.dir, "human.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"state": "eating", "since": NOW, "pushed_at": NOW})
        self.assertEqual(read_samples(self.log), [(NOW - 30, "reading"), (NOW, "eating")])

    def test_drops_samples_older_than_two_days(self):
        with open(self.log, "w", encoding="utf-8") as f:
            f.write(f"{NOW - 3 * 86400}\taway\n{NOW - 3600}\treading\n")
        record_push(self.dir, "eating", NOW, NOW)
        self.assertEqual(read_samples(self.log), [(NOW - 3600, "reading"), (NOW, "eating")])


class DelegatedRatioTest(unittest.TestCase):
    START = NOW - 12 * 3600

    def test_delegating_share_of_hands_on_time(self):
        samples = [(NOW - 1200, "computering"), (NOW - 600, "delegating")]
        self.assertEqual(delegated_ratio(samples, self.START, NOW), 0.5)

    def test_gap_longer_than_ten_minutes_is_not_counted(self):
        samples = [(NOW - 7200, "delegating"), (NOW - 600, "computering")]
        self.assertEqual(delegated_ratio(samples, self.START, NOW), 0.5)

    def test_time_before_day_start_is_not_counted(self):
        start = NOW - 400
        samples = [(start - 300, "delegating"), (start + 100, "computering")]
        self.assertEqual(delegated_ratio(samples, start, NOW), 0.25)

    def test_other_categories_do_not_count(self):
        samples = [(NOW - 1200, "reading"), (NOW - 600, "computering")]
        self.assertEqual(delegated_ratio(samples, self.START, NOW), 0.0)

    def test_none_under_one_minute(self):
        self.assertIsNone(delegated_ratio([(NOW - 30, "computering")], self.START, NOW))


class HumanSectionTest(unittest.TestCase):
    def test_none_without_push(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(human_section(d, NOW, JST))

    def test_times_are_iso_in_local_offset(self):
        with tempfile.TemporaryDirectory() as d:
            record_push(d, "computering", NOW - 600, NOW - 600)
            self.assertEqual(
                human_section(d, NOW, JST),
                {
                    "state": "computering",
                    "since": "2026-11-15T11:50:00+09:00",
                    "pushed_at": "2026-11-15T11:50:00+09:00",
                    "delegated_ratio_today": 0.0,
                },
            )


if __name__ == "__main__":
    unittest.main()
