import os
import tempfile
import unittest

from kisenone_status.collect import build_status, load_env_file, make_sections
from kisenone_status.timeutil import fixed_tz

JST = fixed_tz(540)
NOW = 1794711600  # 2026-11-15 12:00 JST


class BuildStatusTest(unittest.TestCase):
    def test_failed_section_keeps_previous_value(self):
        prev = {"code": {"today_sec": 60, "at": "2026-11-15T11:00:00+09:00"}, "location": {"pref": "東京都"}}
        logs = []

        def broken():
            raise TimeoutError("timed out")

        status = build_status(NOW, JST, prev, {"code": broken, "location": lambda: None}, logs.append)
        self.assertEqual(status["v"], 1)
        self.assertEqual(status["generated_at"], "2026-11-15T12:00:00+09:00")
        self.assertEqual(status["code"], prev["code"])
        # 取得に成功して「点が無い」になったものは前回の値で埋めない
        self.assertIsNone(status["location"])
        self.assertEqual(logs, ["code: TimeoutError: timed out"])

    def test_failed_section_without_previous_is_none(self):
        def broken():
            raise OSError("refused")

        self.assertIsNone(build_status(NOW, JST, {}, {"code": broken}, lambda m: None)["code"])


class EnvFileTest(unittest.TestCase):
    def test_parses_keys_and_strips_quotes(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "env")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# comment\nDAWARICH_API_KEY=abc\nWAKAPI_API_KEY=\"x=y\"\n\nbroken line\n")
            self.assertEqual(load_env_file(path), {"DAWARICH_API_KEY": "abc", "WAKAPI_API_KEY": "x=y"})

    def test_missing_file_is_empty(self):
        self.assertEqual(load_env_file("/nonexistent/env"), {})


class MakeSectionsTest(unittest.TestCase):
    def test_sources_without_api_key_are_skipped(self):
        cfg = {
            "state_dir": "/s",
            "dawarich": {"url": "http://127.0.0.1:3001"},
            "wakapi": {"url": "http://127.0.0.1:3000"},
            "services": [{"name": "x", "check": {"type": "tcp", "target": "127.0.0.1:1"}}],
        }
        sections = make_sections(cfg, {"WAKAPI_API_KEY": "k"}, NOW, JST, ("jp", "world", "tz"))
        self.assertEqual(sorted(sections), ["code", "human", "services"])


if __name__ == "__main__":
    unittest.main()
