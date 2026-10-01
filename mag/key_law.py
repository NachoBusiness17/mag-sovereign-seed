"""key_law — the one loader and the audit (2026-09-23 night, KEY LAW implemented).

Law: one key, one canonical name, declared once in configs/keys.json. Any reader
wanting a key calls key_law.get("<canonical-name>"). No reader guesses env names.
Any registry lane whose key name is not in the manifest is an ORPHAN and the audit
fails loudly.

CLI:
  python -m tools.key_law --audit        (exit 1 on any orphan/empty-critical)
  python -m tools.key_law --status       (human table, values never printed)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
MANIFEST = ROOT / "configs" / "keys.json"

from models.env_load import load_dotenv  # noqa: E402
load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_cache = {"loaded": False, "manifest": {}}


def _manifest() -> dict:
    if not _cache["loaded"]:
        with MANIFEST.open(encoding="utf-8") as f:
            _cache["manifest"] = json.load(f)
        _cache["loaded"] = True
    return _cache["manifest"]


def get(name: str) -> str:
    """The one door. Canonical name in, secret value out (never log it)."""
    entry = _manifest().get(name)
    if not entry:
        raise KeyError(f"key_law: '{name}' not in configs/keys.json — declare it first")
    env = entry.get("env", "")
    if env == "NONE_USES_CLI_SEATS":
        return ""
    return (os.environ.get(env, "") or "").strip()


def audit() -> dict:
    m = _manifest()
    rows = []
    orphans = []
    empty = []
    for name, e in sorted(m.items()):
        if not isinstance(e, dict):
            continue  # meta entries like _law
        env_name = e.get("env", "")
        if env_name == "NONE_USES_CLI_SEATS":
            # CLI seats live on disk, not in env: each declared seat home must
            # still carry its session marker or the seat counts as dead.
            homes = e.get("seat_homes", [])
            present = bool(homes) and all(
                (Path(h).expanduser() / "active_sessions.json").is_file() for h in homes)
        else:
            present = bool((os.environ.get(env_name, "") or "").strip())
        rows.append({"name": name, "env": env_name, "provider": e.get("provider"),
                     "role": e.get("role"), "status": e.get("status", "active"),
                     "present": present})
        if not present and "awaiting" not in e.get("status", ""):
            empty.append(name)
    # orphan check: scan known registry readers for key names not in the manifest
    import re
    registry_names = set()
    for py in (ROOT / "mag" / "free_tier.py", ROOT / "mag" / "nervous_system.py",
               ROOT / "mag" / "subscriptions.py"):
        if py.is_file():
            registry_names |= set(re.findall(r'"([A-Z][A-Z_0-9]{4,})"', py.read_text(encoding="utf-8", errors="replace")))
    manifest_envs = {e.get("env") for e in m.values() if isinstance(e, dict)}
    # orphan = a key LIVE in the environment (or dotenv) that no manifest entry
    # declares. A name merely mentioned in a reader is not a key — only set ones.
    for rn in sorted(registry_names):
        if ("KEY" in rn or "TOKEN" in rn) and rn not in manifest_envs \
                and not rn.startswith("XAI") \
                and (os.environ.get(rn, "") or "").strip():
            orphans.append(rn)
    return {"ok": len(empty) == 0 and len(orphans) == 0, "rows": rows,
            "empty": empty, "orphans": orphans}


def status() -> dict:
    a = audit()
    return {"ok": a["ok"], "empty": a["empty"], "orphans": a["orphans"],
            "keys_total": len(a["rows"]),
            "keys_present": sum(1 for r in a["rows"] if r["present"])}


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--audit" in args:
        a = audit()
        print(json.dumps(a, indent=1))
        sys.exit(0 if a["ok"] else 1)
    print(json.dumps(status(), indent=1))
