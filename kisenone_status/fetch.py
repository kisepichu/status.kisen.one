"""HTTP で JSON を取る。テストでは同じ形の関数に差し替える。"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Mapping

GetJson = Callable[[str, Mapping[str, str]], "tuple[Any, Mapping[str, str]]"]

USER_AGENT = "kisenone-status/0.1 (+https://status.kisen.one)"


def with_user_agent(headers: Mapping[str, str] | None) -> dict[str, str]:
    """呼び出し側が User-Agent を指定していればそれを優先する。"""
    merged = dict(headers or {})
    if not any(k.lower() == "user-agent" for k in merged):
        merged["User-Agent"] = USER_AGENT
    return merged


def get_json(url: str, headers: Mapping[str, str], timeout: float = 10.0) -> tuple[Any, Mapping[str, str]]:
    req = urllib.request.Request(url, headers=with_user_agent(headers))
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res), res.headers
