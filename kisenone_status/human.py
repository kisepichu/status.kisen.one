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
MAX_AGENTS = 99


class PushError(ValueError):
    pass


def _digits(text: str) -> bool:
    return text.isascii() and text.isdigit()


def parse_push(command: str, now: float) -> tuple[str, int, int | None]:
    parts = command.split()
    if len(parts) not in (2, 3):
        raise PushError("usage: <category> <since-epoch> [<agents>]")
    category, since_text = parts[0], parts[1]
    if category not in CATEGORIES:
        raise PushError(f"unknown category: {category}")
    if not _digits(since_text):
        raise PushError("since must be epoch seconds")
    since = int(since_text)
    if not now - MAX_PAST_SEC < since <= now + MAX_FUTURE_SEC:
        raise PushError("since is out of range")
    agents = None
    if len(parts) == 3:
        if not _digits(parts[2]) or int(parts[2]) > MAX_AGENTS:
            raise PushError(f"agents must be 0-{MAX_AGENTS}")
        agents = int(parts[2])
    return category, since, agents


def read_samples(path: str) -> list[tuple[int, str, int | None]]:
    samples = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                t, category, agents = (line.rstrip("\n").split("\t") + ["", ""])[:3]
                if not _digits(t) or category not in CATEGORIES:
                    continue
                if agents and not (_digits(agents) and int(agents) <= MAX_AGENTS):
                    continue
                samples.append((int(t), category, int(agents) if agents else None))
    except OSError:
        pass
    samples.sort(key=lambda s: s[0])
    return samples


def record_push(state_dir: str, category: str, since: int, now: float, agents: int | None) -> None:
    write_json_atomic(
        os.path.join(state_dir, "human.json"),
        {"state": category, "since": since, "pushed_at": int(now), "agents": agents},
        mode=0o640,
    )
    log = os.path.join(state_dir, "human.log")
    kept = [s for s in read_samples(log) if s[0] >= now - LOG_KEEP_SEC]
    kept.append((int(now), category, agents))
    write_text_atomic(
        log,
        "".join(f"{t}\t{c}\t{'' if a is None else a}\n" for t, c, a in kept),
        mode=0o640,
    )


def ai_ratio(samples: list[tuple[int, str, int | None]], start: float, now: float) -> float | None:
    """computering と delegating の時間のうち、delegating か agents が 1 以上だった時間の割合。"""
    total = 0.0
    ai = 0.0
    for i, (t, category, agents) in enumerate(samples):
        if category not in ("computering", "delegating"):
            continue
        end = samples[i + 1][0] if i + 1 < len(samples) else now
        end = min(end, t + SAMPLE_GAP_SEC, now)
        begin = max(t, start)
        if end <= begin:
            continue
        total += end - begin
        if category == "delegating" or (agents or 0) >= 1:
            ai += end - begin
    if total < 60:
        return None
    return round(ai / total, 2)


def human_section(state_dir: str, now: float, tz: timezone) -> dict | None:
    h = read_json(os.path.join(state_dir, "human.json"))
    if not isinstance(h, dict) or h.get("state") not in CATEGORIES:
        return None
    samples = read_samples(os.path.join(state_dir, "human.log"))
    return {
        "state": h["state"],
        "since": iso(h["since"], tz),
        "pushed_at": iso(h["pushed_at"], tz),
        "agents": h.get("agents"),
        "ai_ratio_today": ai_ratio(samples, day_start(now, tz), now),
    }
