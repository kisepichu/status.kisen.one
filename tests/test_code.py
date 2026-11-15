import base64
import unittest

from kisenone_status.code import code_section, fetch_summary
from kisenone_status.timeutil import fixed_tz

JST = fixed_tz(540)
NOW = 1794711600  # 2026-11-15 12:00 JST


class CodeSectionTest(unittest.TestCase):
    def test_top_three_languages_and_other(self):
        summary = {
            "projects": [{"key": "secret-work-repo", "total": 1000}],
            "languages": [
                {"key": "Go", "total": 100},
                {"key": "Nix", "total": 520},
                {"key": "Markdown", "total": 50},
                {"key": "TypeScript", "total": 300},
                {"key": "Bash", "total": 30},
            ],
            "operating_systems": [{"key": "Darwin", "total": 100}, {"key": "Linux", "total": 900}],
            "machines": [{"key": "secret-host", "total": 1000}],
        }
        self.assertEqual(
            code_section(summary, NOW, JST),
            {
                "today_sec": 1000,
                "langs": [["Nix", 0.52], ["TypeScript", 0.3], ["Go", 0.1], ["other", 0.08]],
                "oses": [["Linux", 0.9], ["Darwin", 0.1]],
                "at": "2026-11-15T12:00:00+09:00",
            },
        )

    def test_no_other_when_three_or_fewer(self):
        summary = {"languages": [{"key": "Nix", "total": 60}, {"key": "Go", "total": 0}]}
        self.assertEqual(code_section(summary, NOW, JST)["langs"], [["Nix", 1.0]])

    def test_nothing_today(self):
        section = code_section({"languages": [], "operating_systems": []}, NOW, JST)
        self.assertEqual((section["today_sec"], section["langs"], section["oses"]), (0, [], []))

    def test_unknown_language_is_folded_into_other(self):
        summary = {
            "languages": [
                {"key": "Unknown", "total": 600},
                {"key": "Nix", "total": 200},
                {"key": "Go", "total": 100},
                {"key": "Bash", "total": 50},
                {"key": "Rust", "total": 50},
            ]
        }
        section = code_section(summary, NOW, JST)
        self.assertEqual(section["today_sec"], 1000)
        self.assertEqual(section["langs"], [["Nix", 0.2], ["Go", 0.1], ["Bash", 0.05], ["other", 0.65]])

    def test_only_unknown_language(self):
        section = code_section({"languages": [{"key": "unknown", "total": 90}]}, NOW, JST)
        self.assertEqual((section["today_sec"], section["langs"]), (90, [["other", 1.0]]))

    def test_unknown_os_is_skipped_and_ratio_excludes_it(self):
        summary = {
            "operating_systems": [
                {"key": "Linux", "total": 900},
                {"key": "Unknown", "total": 5000},
                {"key": "Darwin", "total": 100},
            ]
        }
        self.assertEqual(code_section(summary, NOW, JST)["oses"], [["Linux", 0.9], ["Darwin", 0.1]])

    def test_all_unknown_os_is_empty(self):
        summary = {"operating_systems": [{"key": "UNKNOWN", "total": 900}]}
        self.assertEqual(code_section(summary, NOW, JST)["oses"], [])
        self.assertNotIn("os", code_section(summary, NOW, JST))


class FetchSummaryTest(unittest.TestCase):
    def test_api_key_is_sent_base64_encoded(self):
        seen = {}

        def get_json(url, headers):
            seen["url"], seen["headers"] = url, headers
            return {"languages": []}, {}

        fetch_summary(get_json, "http://127.0.0.1:3000/", "my-key")
        self.assertEqual(seen["url"], "http://127.0.0.1:3000/api/summary?interval=today")
        self.assertEqual(seen["headers"]["Authorization"], "Bearer " + base64.b64encode(b"my-key").decode())


if __name__ == "__main__":
    unittest.main()
