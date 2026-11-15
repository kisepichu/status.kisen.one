"""Wakapi の今日の summary から、合計・上位 3 言語・OS を出す。project などは捨てる。"""
from __future__ import annotations

import base64
from datetime import timezone

from .fetch import GetJson
from .timeutil import iso

TOP_LANGS = 3


def _items(summary: dict, key: str) -> list[tuple[str, float]]:
    items = []
    for item in summary.get(key) or []:
        try:
            items.append((str(item["key"]), float(item["total"])))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted((i for i in items if i[1] > 0), key=lambda i: i[1], reverse=True)


def code_section(summary: dict, now: float, tz: timezone) -> dict:
    langs = _items(summary, "languages")
    total = sum(t for _, t in langs)
    out_langs: list[list] = []
    if total > 0:
        top = langs[:TOP_LANGS]
        out_langs = [[name, round(t / total, 2)] for name, t in top]
        rest = total - sum(t for _, t in top)
        if rest > 0:
            out_langs.append(["other", round(rest / total, 2)])
    oses = _items(summary, "operating_systems")
    return {
        "today_sec": int(total),
        "langs": out_langs,
        "os": oses[0][0] if oses else None,
        "at": iso(now, tz),
    }


def fetch_summary(get_json: GetJson, base_url: str, api_key: str) -> dict:
    # Wakapi の API キー認証は base64 にしたキーを Bearer で渡す
    token = base64.b64encode(api_key.encode()).decode()
    data, _ = get_json(
        f"{base_url.rstrip('/')}/api/summary?interval=today",
        {"Authorization": f"Bearer {token}"},
    )
    return data
