"""Write the wave pane as JSON. Desk HTTP must not import Mag."""
from __future__ import annotations
import json, sys
from pathlib import Path
CACHE = Path("/app/memory/working/wave_view.json")

def refresh(session_id: str = "") -> dict:
    from mag.wave import snapshot_fast
    out = snapshot_fast(session_id=session_id)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out, default=str), encoding="utf-8")
    return out

def main() -> int:
    sid = sys.argv[1] if len(sys.argv) > 1 else ""
    print(json.dumps(refresh(sid), default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
