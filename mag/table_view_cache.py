"""Write / read the table view as a JSON file. Desk HTTP must not import Mag."""
from __future__ import annotations

import json
import sys
from pathlib import Path

CACHE = Path("/app/memory/working/table_view.json")


def refresh(campaign_id: str = "") -> dict:
    from mag.game_view import handle_table_view
    out = handle_table_view({}, {"campaign_id": campaign_id} if campaign_id else {})
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out, default=str), encoding="utf-8")
    return out


def read() -> dict | None:
    if not CACHE.is_file():
        return None
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    cid = sys.argv[1] if len(sys.argv) > 1 else ""
    out = refresh(cid)
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
