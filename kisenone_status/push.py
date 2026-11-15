"""ssh の forced command。SSH_ORIGINAL_COMMAND の「<category> <since>」を記録する。"""
from __future__ import annotations

import os
import sys
import time

from .human import PushError, parse_push, record_push

STATE_DIR = "/var/lib/kisenone-status"


def main() -> int:
    state_dir = os.environ.get("KISENONE_STATUS_STATE_DIR", STATE_DIR)
    now = time.time()
    try:
        category, since = parse_push(os.environ.get("SSH_ORIGINAL_COMMAND", ""), now)
    except PushError as e:
        print(f"kisenone-status-push: {e}", file=sys.stderr)
        return 1
    record_push(state_dir, category, since, now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
