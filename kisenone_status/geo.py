"""座標から国と都道府県を出す。境界データは GeoJSON (Polygon / MultiPolygon)。"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Callable

# 日本の多角形に入らなくても、この距離までなら一番近い都道府県にする (埋立地や海岸線の簡略化の誤差)
NEAR_JP_KM = 3.0
# 近さを測る候補を bbox で絞るときの余白 (度)。3 km より広くとる
_NEAR_MARGIN_DEG = 0.05
_KM_PER_DEG = 111.32


@dataclass
class Region:
    name: str | None
    bbox: tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat
    polygons: list  # [[outer, hole, ...], ...]。点は [lon, lat]


def _polygons(geometry: dict | None) -> list:
    if not geometry:
        return []
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    return []


def _bbox(polygons: list) -> tuple[float, float, float, float]:
    xs = [p[0] for poly in polygons for p in poly[0]]
    ys = [p[1] for poly in polygons for p in poly[0]]
    return (min(xs), min(ys), max(xs), max(ys))


def load_regions(path: str, name_of: Callable[[dict], str | None]) -> list[Region]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    regions = []
    for feature in data["features"]:
        polygons = _polygons(feature.get("geometry"))
        if polygons:
            regions.append(Region(name_of(feature.get("properties") or {}), _bbox(polygons), polygons))
    return regions


def _in_bbox(b: tuple[float, float, float, float], lon: float, lat: float, margin: float = 0.0) -> bool:
    return b[0] - margin <= lon <= b[2] + margin and b[1] - margin <= lat <= b[3] + margin


def _in_ring(ring: list, lon: float, lat: float) -> bool:
    inside = False
    for i in range(len(ring)):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[i - 1][0], ring[i - 1][1]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def contains(region: Region, lon: float, lat: float) -> bool:
    if not _in_bbox(region.bbox, lon, lat):
        return False
    for poly in region.polygons:
        if _in_ring(poly[0], lon, lat) and not any(_in_ring(hole, lon, lat) for hole in poly[1:]):
            return True
    return False


def _segment_km(lon: float, lat: float, a: list, b: list) -> float:
    k = math.cos(math.radians(lat))
    px, py = lon * k, lat
    ax, ay, bx, by = a[0] * k, a[1], b[0] * k, b[1]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        t = 0.0
    else:
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy)) * _KM_PER_DEG


def distance_km(region: Region, lon: float, lat: float) -> float:
    best = math.inf
    for poly in region.polygons:
        ring = poly[0]
        for i in range(len(ring)):
            best = min(best, _segment_km(lon, lat, ring[i - 1], ring[i]))
    return best


def _country_code(properties: dict) -> str | None:
    code = properties.get("ISO_A2_EH")
    return None if code in (None, "-99") else code


class GeoIndex:
    def __init__(self, jp_path: str, world_path: str):
        self.prefectures = load_regions(jp_path, lambda p: p.get("N03_001"))
        self.countries = load_regions(world_path, _country_code)

    def locate(self, lat: float, lon: float) -> tuple[str | None, str | None]:
        for region in self.prefectures:
            if contains(region, lon, lat):
                return "JP", region.name
        near = [
            (distance_km(r, lon, lat), r.name)
            for r in self.prefectures
            if _in_bbox(r.bbox, lon, lat, _NEAR_MARGIN_DEG)
        ]
        if near:
            d, name = min(near)
            if d <= NEAR_JP_KM:
                return "JP", name
        for region in self.countries:
            if region.name and contains(region, lon, lat):
                return region.name, None
        return None, None
