"""時刻の変換。tzdata に頼らないよう、固定のオフセットだけを扱う。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def fixed_tz(offset_minutes: int) -> timezone:
    return timezone(timedelta(minutes=offset_minutes))


def iso(epoch: float, tz: timezone) -> str:
    return datetime.fromtimestamp(epoch, tz).isoformat(timespec="seconds")


def day_start(epoch: float, tz: timezone) -> float:
    d = datetime.fromtimestamp(epoch, tz)
    return d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
