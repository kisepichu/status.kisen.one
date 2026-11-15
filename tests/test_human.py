import json
import os
import tempfile
import unittest

from kisenone_status.human import (
    PushError,
    ai_ratio,
    human_section,
    parse_push,
    read_samples,
    record_push,
)
from kisenone_status.timeutil import fixed_tz

JST = fixed_tz(540)
NOW = 1794711600  # 2026-11-15 12:00 JST


class ParsePushTest(unittest.TestCase):
    def test_two_words_have_no_agents(self):
        self.assertEqual(parse_push(f"reading {NOW - 600}", NOW), ("reading", NOW - 600, None))

    def test_three_words_carry_agents(self):
        self.assertEqual(parse_push(f"computering {NOW - 600} 3", NOW), ("computering", NOW - 600, 3))
        self.assertEqual(parse_push(f"computering {NOW - 600} 99", NOW), ("computering", NOW - 600, 99))
        self.assertEqual(parse_push(f"computering {NOW - 600} 0", NOW), ("computering", NOW - 600, 0))

    def test_rejects_malformed_commands(self):
        for command in [
            "",
            "reading",
            f"hacking {NOW}",
            f"reading {NOW} ; rm -rf /",
            "reading 2026-11-15T12:00",
            f"reading {NOW - 8 * 86400}",
            f"reading {NOW + 3600}",
            f"computering {NOW} 100",
            f"computering {NOW} -1",
            f"computering {NOW} ²",
            f"computering {NOW} x",
            f"computering {NOW} 1 2",
            f"computering {NOW}² 1",
            f"computering {NOW}²",
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
        record_push(self.dir, "reading", NOW - 60, NOW - 30, None)
        record_push(self.dir, "computering", NOW, NOW, 2)
        with open(os.path.join(self.dir, "human.json"), encoding="utf-8") as f:
            self.assertEqual(
                json.load(f), {"state": "computering", "since": NOW, "pushed_at": NOW, "agents": 2}
            )
        self.assertEqual(read_samples(self.log), [(NOW - 30, "reading", None), (NOW, "computering", 2)])
        with open(self.log, encoding="utf-8") as f:
            self.assertEqual(f.read(), f"{NOW - 30}\treading\t\n{NOW}\tcomputering\t2\n")

    def test_drops_samples_older_than_two_days(self):
        with open(self.log, "w", encoding="utf-8") as f:
            f.write(f"{NOW - 3 * 86400}\taway\n{NOW - 3600}\treading\n")
        record_push(self.dir, "eating", NOW, NOW, None)
        self.assertEqual(read_samples(self.log), [(NOW - 3600, "reading", None), (NOW, "eating", None)])

    def test_reads_old_two_column_lines(self):
        with open(self.log, "w", encoding="utf-8") as f:
            f.write(f"{NOW - 60}\tdelegating\n{NOW - 30}\tcomputering\t4\nbroken\n{NOW}\tcomputering\tx\n")
        self.assertEqual(
            read_samples(self.log), [(NOW - 60, "delegating", None), (NOW - 30, "computering", 4)]
        )


class AiRatioTest(unittest.TestCase):
    START = NOW - 12 * 3600

    def test_agents_count_as_ai_time(self):
        samples = [(NOW - 1200, "computering", 2), (NOW - 600, "computering", 0)]
        self.assertEqual(ai_ratio(samples, self.START, NOW), 0.5)

    def test_delegating_counts_without_agents(self):
        samples = [(NOW - 1200, "delegating", None), (NOW - 600, "computering", None)]
        self.assertEqual(ai_ratio(samples, self.START, NOW), 0.5)

    def test_gap_longer_than_ten_minutes_is_not_counted(self):
        samples = [(NOW - 7200, "delegating", None), (NOW - 600, "computering", None)]
        self.assertEqual(ai_ratio(samples, self.START, NOW), 0.5)

    def test_time_before_day_start_is_not_counted(self):
        start = NOW - 400
        samples = [(start - 300, "delegating", None), (start + 100, "computering", None)]
        self.assertEqual(ai_ratio(samples, start, NOW), 0.25)

    def test_none_under_one_minute(self):
        self.assertIsNone(ai_ratio([(NOW - 30, "computering", 1)], self.START, NOW))

    def test_other_categories_are_ignored_even_with_agents(self):
        samples = [(NOW - 1200, "reading", 3), (NOW - 600, "computering", 0)]
        self.assertEqual(ai_ratio(samples, self.START, NOW), 0.0)


class HumanSectionTest(unittest.TestCase):
    def test_none_without_push(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(human_section(d, NOW, JST))

    def test_times_are_iso_in_local_offset(self):
        with tempfile.TemporaryDirectory() as d:
            record_push(d, "computering", NOW - 600, NOW - 600, 2)
            self.assertEqual(
                human_section(d, NOW, JST),
                {
                    "state": "computering",
                    "since": "2026-11-15T11:50:00+09:00",
                    "pushed_at": "2026-11-15T11:50:00+09:00",
                    "agents": 2,
                    "ai_ratio_today": 1.0,
                },
            )

    def test_agents_none_for_old_push(self):
        with tempfile.TemporaryDirectory() as d:
            record_push(d, "computering", NOW - 600, NOW - 600, None)
            section = human_section(d, NOW, JST)
            self.assertIsNone(section["agents"])
            self.assertEqual(section["ai_ratio_today"], 0.0)


if __name__ == "__main__":
    unittest.main()
