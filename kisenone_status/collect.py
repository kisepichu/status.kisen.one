"""status.json を作る。取得に失敗したセクションは前回の値を残す。"""
from __future__ import annotations

import os
import sys
import time
from datetime import timezone
from typing import Callable

from .code import code_section, fetch_summary
from .fetch import get_json
from .geo import GeoIndex
from .human import human_section
from .jsonio import read_json, write_json_atomic
from .location import fetch_points, location_section
from .services import machines_section, services_section
from .timeutil import fixed_tz, iso

SCHEMA_VERSION = 2


def load_env_file(path: str) -> dict[str, str]:
    env = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip("\"'")
    except OSError:
        pass
    return env


def build_status(now: float, tz: timezone, prev: dict, sections: dict[str, Callable[[], object]], log: Callable[[str], None]) -> dict:
    status: dict = {"v": SCHEMA_VERSION, "generated_at": iso(now, tz)}
    for name, produce in sections.items():
        try:
            status[name] = produce()
        except Exception as e:  # 取得元ごとの失敗は、そのセクションだけ前回の値にする
            log(f"{name}: {type(e).__name__}: {e}")
            status[name] = prev.get(name)
    return status


def make_sections(cfg: dict, secrets: dict[str, str], now: float, tz: timezone, geo_paths: tuple[str, str, str]) -> dict[str, Callable[[], object]]:
    sections: dict[str, Callable[[], object]] = {
        "human": lambda: human_section(cfg["state_dir"], now, tz),
    }
    dawarich, dawarich_key = cfg.get("dawarich"), secrets.get("DAWARICH_API_KEY")
    if dawarich and dawarich_key:
        def location() -> object:
            latest, today = fetch_points(get_json, dawarich["url"], dawarich_key, now, tz)
            return location_section(latest, today, now, tz, GeoIndex(*geo_paths))

        sections["location"] = location
    wakapi, wakapi_key = cfg.get("wakapi"), secrets.get("WAKAPI_API_KEY")
    if wakapi and wakapi_key:
        sections["code"] = lambda: code_section(fetch_summary(get_json, wakapi["url"], wakapi_key), now, tz)
    if cfg.get("services"):
        sections["services"] = lambda: services_section(cfg["services"], now, tz)
    if cfg.get("machines"):
        sections["machines"] = lambda: machines_section(cfg["machines"], cfg["state_dir"], now, tz)
    return sections


def main() -> int:
    cfg = read_json(os.environ["KISENONE_STATUS_CONFIG"])
    credentials = os.environ.get("CREDENTIALS_DIRECTORY")
    secrets = load_env_file(os.path.join(credentials, "env")) if credentials else {}
    tz = fixed_tz(cfg.get("utc_offset_minutes", 540))
    now = time.time()
    path = os.path.join(cfg["public_dir"], "status.json")
    prev = read_json(path, {})
    if not isinstance(prev, dict):
        prev = {}
    geo_paths = (os.environ["KISENONE_GEO_JP"], os.environ["KISENONE_GEO_WORLD"], os.environ["KISENONE_GEO_TZ"])
    sections = make_sections(cfg, secrets, now, tz, geo_paths)
    status = build_status(now, tz, prev, sections, lambda m: print(m, file=sys.stderr))
    write_json_atomic(path, status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
