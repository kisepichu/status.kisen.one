"""サービスとマシンの死活。systemd / http / tcp と、マシンには push の鮮度も。"""
from __future__ import annotations

import socket
import subprocess
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from typing import Callable, Mapping

from .fetch import with_user_agent
from .human import push_liveness
from .timeutil import iso

TIMEOUT_SEC = 5.0


def check_systemd(unit: str, run: Callable = subprocess.run) -> bool:
    try:
        out = run(
            ["systemctl", "show", "-p", "LoadState", "-p", "ActiveState", "-p", "Result", unit],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    props = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    # 存在しない unit も ActiveState=inactive, Result=success になるので LoadState で弾く
    if props.get("LoadState") != "loaded":
        return False
    state = props.get("ActiveState")
    return state == "active" or (state == "inactive" and props.get("Result") == "success")


def check_http(url: str, headers: Mapping[str, str] | None = None) -> bool:
    req = urllib.request.Request(url, headers=with_user_agent(headers))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as res:
            return res.status < 400
    except urllib.error.HTTPError as e:
        return e.code < 400
    except (urllib.error.URLError, OSError, ValueError):
        return False


def check_tcp(target: str) -> bool:
    host, _, port = target.rpartition(":")
    try:
        with socket.create_connection((host, int(port)), timeout=TIMEOUT_SEC):
            return True
    except (OSError, ValueError):
        return False


def check(spec: dict) -> bool:
    kind = spec["type"]
    if kind == "systemd":
        return check_systemd(spec["target"])
    if kind == "http":
        return check_http(spec["target"], spec.get("headers"))
    if kind == "tcp":
        return check_tcp(spec["target"])
    raise ValueError(f"unknown check type: {kind}")


def services_section(services: list[dict], now: float, tz: timezone, check_fn: Callable[[dict], bool] = check) -> list[dict]:
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda s: check_fn(s["check"]), services))
    checked_at = iso(now, tz)
    out = []
    for service, up in zip(services, results):
        entry = {"name": service["name"], "up": up, "checked_at": checked_at}
        if service.get("url"):
            entry["url"] = service["url"]
        if service.get("private"):
            entry["private"] = True
        if service.get("event_only"):
            entry["event_only"] = True
        out.append(entry)
    return out


def machines_section(machines: list[dict], state_dir: str, now: float, tz: timezone, check_fn: Callable[[dict], bool] = check) -> list[dict]:
    # push の self は送ってくるマシン自身、remote はそのマシンが報告する ssh 先
    self_up, remote_up = push_liveness(state_dir, now)
    pushed = {"self": self_up, "remote": remote_up}

    def up(spec: dict) -> bool | None:
        return pushed[spec["target"]] if spec["type"] == "push" else check_fn(spec)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda m: up(m["check"]), machines))
    checked_at = iso(now, tz)
    return [{"name": m["name"], "up": result, "checked_at": checked_at} for m, result in zip(machines, results)]
