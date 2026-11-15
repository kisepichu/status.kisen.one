"""HTTP で JSON を取る。テストでは同じ形の関数に差し替える。"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Mapping

GetJson = Callable[[str, Mapping[str, str]], "tuple[Any, Mapping[str, str]]"]


def get_json(url: str, headers: Mapping[str, str], timeout: float = 10.0) -> tuple[Any, Mapping[str, str]]:
    req = urllib.request.Request(url, headers=dict(headers))
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res), res.headers
