"""JSON の読み書き。書くときは一時ファイルに書いてから rename で置き換える。"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any


def read_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_text_atomic(path: str, text: str, mode: int = 0o644) -> None:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_json_atomic(path: str, data: Any, mode: int = 0o644) -> None:
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, separators=(",", ":")), mode)
