"""Dawarich の点から、国・都道府県・今日の移動距離・移動中かを出す。座標は外に出さない。"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timezone
from urllib.parse import urlencode

from .fetch import GetJson
from .timeutil import day_start, iso

ACCURACY_MAX_M = 100.0
MOVING_RECENT_SEC = 15 * 60
MOVING_KMH = 15.0
PER_PAGE = 1000
MAX_PAGES = 20
EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class Point:
    t: int
    lat: float
    lon: float
    accuracy: float | None


def parse_point(raw: dict) -> Point | None:
    try:
        accuracy = raw.get("accuracy")
        return Point(
            int(raw["timestamp"]),
            float(raw["latitude"]),
            float(raw["longitude"]),
            None if accuracy is None else float(accuracy),
        )
    except (KeyError, TypeError, ValueError):
        return None


def haversine_km(a: Point, b: Point) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _good(points: list[Point]) -> list[Point]:
    return sorted(
        (p for p in points if p.accuracy is None or p.accuracy <= ACCURACY_MAX_M),
        key=lambda p: p.t,
    )


def today_km(points: list[Point]) -> float:
    good = _good(points)
    return sum(haversine_km(a, b) for a, b in zip(good, good[1:]))


def is_moving(points: list[Point], now: float) -> bool:
    good = _good(points)
    if len(good) < 2:
        return False
    a, b = good[-2], good[-1]
    if now - b.t > MOVING_RECENT_SEC or b.t <= a.t:
        return False
    return haversine_km(a, b) / ((b.t - a.t) / 3600) >= MOVING_KMH


def location_section(latest: Point | None, today: list[Point], now: float, tz: timezone, geo) -> dict | None:
    if latest is None:
        return None
    country, pref = geo.locate(latest.lat, latest.lon)
    return {
        "country": country,
        "pref": pref,
        "moving": is_moving(today, now),
        "today_km": round(today_km(today), 1),
        "point_at": iso(latest.t, tz),
        "at": iso(now, tz),
    }


def fetch_points(get_json: GetJson, base_url: str, api_key: str, now: float, tz: timezone) -> tuple[Point | None, list[Point]]:
    # Dawarich は https を強制するので、loopback で叩くときも https 経由に見せる
    headers = {"Authorization": f"Bearer {api_key}", "X-Forwarded-Proto": "https"}
    url = f"{base_url.rstrip('/')}/api/v1/points"
    latest_raw, _ = get_json(f"{url}?{urlencode({'order': 'desc', 'per_page': 1})}", headers)
    latest = parse_point(latest_raw[0]) if latest_raw else None
    today: list[Point] = []
    start = int(day_start(now, tz))
    for page in range(1, MAX_PAGES + 1):
        query = urlencode(
            {"start_at": start, "end_at": int(now), "order": "asc", "per_page": PER_PAGE, "page": page}
        )
        batch, res_headers = get_json(f"{url}?{query}", headers)
        today.extend(p for p in map(parse_point, batch) if p is not None)
        if page >= int(res_headers.get("X-Total-Pages") or 1):
            break
    return latest, today
