"""One table turn as JSON. Desk must not import Mag."""
from __future__ import annotations
import json, sys

def main() -> int:
    body = json.loads(sys.stdin.read() or "{}")
    from mag.table_turn import handle
    print(json.dumps(handle(body), default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
