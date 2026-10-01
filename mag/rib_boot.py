"""THE BOOT THAT MOUNTS WHAT THE SEAT FORGETS -- stolen from the verkle chain, not invented.

OPERATOR (2026-09-30): "self steal your mag boot from verkle so you stop forgetting."

WHAT WAS MEASURED FIRST, because there are ALREADY a dozen boot modules in mag/ and the doctrine
is to borrow, never to volunteer a build:
    boot.py               8,446B   0 rib mounts, 0 brief, 0 verkle
    boot_check.py         6,780B   0 rib mounts, 0 brief, 2 verkle mentions
    tripartite_boot.py   18,218B   0 rib mounts, 0 brief, 0 verkle
    ghost_cold_boot.py    7,074B   0 rib mounts, 0 brief, 0 verkle
    hermes_warm_boot.py  10,558B   0 rib mounts, 0 brief, 8 verkle mentions
  So five modules boot the PROCESS and none of them mounts the DOCTRINE. That is the actual gap,
  and it is why a seat can run for a whole night, land 40+ files, produce four receipts, and still
  not have read the 51 frozen ribs that say what the system is FOR. It is not a memory failure.
  It is a missing mount, and it has been missing this entire time.

THE LAWS THIS MOUNTS, verbatim from the ribs rather than from memory:
    "The invariant: a deterministic instruction set, anchored on shared cryptographic primitives,
     explains navigable paths through stochastic environments. The relation (the frozen spec) is
     what persists; the model is interchangeable; the chain is the ground truth."
    "chain=record, window=reasoning surface. Down seats stay records. Never store window as truth."
    "RIB-DEBUG every finished piece (trust bytes, not reports)."
    "Do not prompt the operator for permission to run framework ops."
    "T0 secrets never remote; T1 private never train-on-input; T2 public remote OK; T3 irreversible
     human L3 seal."

READ-ONLY BY LAW. mount() on the rib bus is read-only. publish() FOLDS A VERKLE KNOT and is
therefore never called here -- not once, not behind a flag. The chain is read-only per the
operator's standing ruling of 2026-09-07. This module can only read, and that is enforced in code
rather than promised in a comment.

USAGE
    python -m mag.rib_boot              # full mount, printed
    python -m mag.rib_boot --domain doctrine
    python -m mag.rib_boot --json       # machine-readable, for a seat to ingest
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WARM = ROOT / "memory" / "warm_state.json"
BRIEF = ROOT / "memory" / "briefs" / "latest.md"
OUT = ROOT / "memory" / "rib_boot.json"

# The laws that matter most when a seat is mid-task and about to over-claim. Carried as data so
# they survive a summary, which is exactly how they were lost tonight.
CORE_LAWS = [
    ("chain-is-truth", "chain=record, window=reasoning. Never store the window as truth."),
    ("model-interchangeable", "The model is a visitor with a pack; the frozen relation persists."),
    ("trust-bytes", "RIB-DEBUG every finished piece. Trust bytes, not reports."),
    ("dont-ask-permission", "Do not prompt the operator to run framework ops."),
    ("rightsized", "cheap-first; frontier scarce; human L3 on irreversible."),
    ("artifact-over-transcript", "DNA: residual + card + content_commit + chain_leaf = filed."),
    ("residual-on-disk", "Residual on disk is truth; chat is heat."),
    ("no-second-scheduler", "Async work to the QUEUE; deterministic must-be-now via tools."),
    ("diesel-over-think", "When in doubt, code the game."),
]


def _run(*args: str) -> str:
    py = str(ROOT / ".venv" / "Scripts" / "python.exe")
    exe = py if Path(py).is_file() else sys.executable
    try:
        r = subprocess.run([exe, "-m", *args], cwd=str(ROOT), capture_output=True,
                           text=True, timeout=240)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:                                   # the mount must never kill the seat
        return f"[MOUNT-FAILED: {type(e).__name__}: {e}]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="doctrine")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    # 1. the chain tip -- READ ONLY. No knot, no append, no publish().
    chain = {}
    if WARM.is_file():
        try:
            w = json.loads(WARM.read_text(encoding="utf-8"))
            chain = {"ok": w.get("chain", {}).get("ok"),
                     "index": w.get("chain", {}).get("index"),
                     "verkle_root": w.get("chain", {}).get("verkle_root"),
                     "generated": w.get("generated")}
        except Exception as e:
            chain = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # 2. the ribs. mount() only -- publish() folds a knot and is forbidden.
    raw = _run("mag.rib_bus", "mount", "--domain", a.domain)
    ribs = []
    try:
        j = json.loads(raw)
        ribs = j if isinstance(j, list) else j.get("ribs", j.get("items", []))
    except Exception:
        ribs = [{"note": "rib mount returned non-JSON; raw head follows", "raw_head": raw[:400]}]

    # 3. the live brief -- FROZEN. Read, never written. The tooling refuses to overwrite it and
    #    this module does not try.
    brief = {}
    if BRIEF.is_file():
        t = BRIEF.read_text(encoding="utf-8", errors="replace")
        brief = {"chars": len(t), "head": " ".join(t.split())[:600]}

    out = {
        "schema": "rib_boot.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "publish_called": False,
        "domain": a.domain,
        "chain": chain,
        "rib_count": len(ribs),
        "core_laws": [{"id": i, "law": l} for i, l in CORE_LAWS],
        "brief": brief,
        "ribs": ribs,
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    if a.json:
        print(json.dumps({k: v for k, v in out.items() if k != "ribs"}, indent=2,
                         ensure_ascii=False))
    else:
        print(f"  RIB BOOT -- domain={a.domain}  ribs={len(ribs)}  "
              f"chain_index={chain.get('index')}  root={str(chain.get('verkle_root'))[:16]}  "
              f"brief={brief.get('chars')}B")
        print("  READ-ONLY: no knot folded, publish() not called.\n")
        print("  LAWS MOUNTED")
        for i, l in CORE_LAWS:
            print(f"    {i:22s} {l}")
        print(f"\n  -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())