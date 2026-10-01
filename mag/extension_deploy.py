"""Extension deploy — copy vscode-mag-map files to the installed extension dir.

Gives the extension-deploy op an architecture path (REST / direct module call)
instead of a manual terminal copy (which was triggering allow-prompts). Deterministic,
idempotent, reuses only file copy.

REST: POST /api/v1/extension/deploy   -> deploy()
CLI:  python -m mag.extension_deploy
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SRC = ROOT / "vscode-mag-map"
FILES = [
    "extension.js", "package.json", "mag_views.js", "graph.js",
    "control_room.js", "README.md",
]


def installed_dir() -> Path | None:
    home = Path.home() / ".vscode" / "extensions"
    if not home.is_dir():
        return None
    for d in sorted(home.iterdir(), reverse=True):
        if d.is_dir() and d.name.startswith("mag.mag-framework-map"):
            return d
    return None


def deploy() -> dict:
    """Copy the workspace extension files to the installed extension dir."""
    dst = installed_dir()
    if not dst:
        return {"ok": False, "error": "installed MAG extension dir not found under ~/.vscode/extensions"}
    copied: list[str] = []
    missing: list[str] = []
    for f in FILES:
        s = SRC / f
        if s.is_file():
            shutil.copy2(s, dst / f)
            copied.append(f)
        else:
            missing.append(f)
    return {"ok": True, "schema": "ext_deploy.v1", "src": str(SRC),
            "dst": str(dst), "copied": copied, "missing": missing}


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(deploy(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
