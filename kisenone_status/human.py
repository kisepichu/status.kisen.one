"""人間の状態: push の入力チェック、human.json と human.log、AI に任せた時間の割合。"""
from __future__ import annotations

import os
from datetime import timezone

from .jsonio import read_json, write_json_atomic, write_text_atomic
from .timeutil import day_start, iso

CATEGORIES = frozenset(
    {"computering", "delegating", "reading", "chore", "eating", "sleeping", "working", "away"}
)
MAX_PAST_SEC = 7 * 86400
MAX_FUTURE_SEC = 60
LOG_KEEP_SEC = 2 * 86400
# push の間隔 (既定 5 分) の 2 倍。これより長い空白は PC が止まっていたとみなし、数えない
SAMPLE_GAP_SEC = 600


class PushError(ValueError):
    pass


def parse_push(command: str, now: float) -> tuple[str, int]:
    parts = command.split()
    if len(parts) != 2:
        raise PushError("usage: <category> <since-epoch>")
    category, since_text = parts
    if category not in CATEGORIES:
        raise PushError(f"unknown category: {category}")
    if not since_text.isdigit():
        raise PushError("since must be epoch seconds")
    since = int(since_text)
    if not now - MAX_PAST_SEC < since <= now + MAX_FUTURE_SEC:
        raise PushError("since is out of range")
    return category, since


def read_samples(path: str) -> list[tuple[int, str]]:
    samples = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                t, _, category = line.rstrip("\n").partition("\t")
                if t.isdigit() and category in CATEGORIES:
                    samples.append((int(t), category))
    except OSError:
        pass
    samples.sort()
    return samples


def record_push(state_dir: str, category: str, since: int, now: float) -> None:
    write_json_atomic(
        os.path.join(state_dir, "human.json"),
        {"state": category, "since": since, "pushed_at": int(now)},
        mode=0o640,
    )
    log = os.path.join(state_dir, "human.log")
    kept = [s for s in read_samples(log) if s[0] >= now - LOG_KEEP_SEC]
    kept.append((int(now), category))
    write_text_atomic(log, "".join(f"{t}\t{c}\n" for t, c in kept), mode=0o640)


def delegated_ratio(samples: list[tuple[int, str]], start: float, now: float) -> float | None:
    totals = {"delegating": 0.0, "computering": 0.0}
    for i, (t, category) in enumerate(samples):
        if category not in totals:
            continue
        end = samples[i + 1][0] if i + 1 < len(samples) else now
        end = min(end, t + SAMPLE_GAP_SEC, now)
        begin = max(t, start)
        if end > begin:
            totals[category] += end - begin
    hands_on = totals["delegating"] + totals["computering"]
    if hands_on < 60:
        return None
    return round(totals["delegating"] / hands_on, 2)


def human_section(state_dir: str, now: float, tz: timezone) -> dict | None:
    h = read_json(os.path.join(state_dir, "human.json"))
    if not isinstance(h, dict) or h.get("state") not in CATEGORIES:
        return None
    samples = read_samples(os.path.join(state_dir, "human.log"))
    return {
        "state": h["state"],
        "since": iso(h["since"], tz),
        "pushed_at": iso(h["pushed_at"], tz),
        "delegated_ratio_today": delegated_ratio(samples, day_start(now, tz), now),
    }
