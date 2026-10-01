"""capture_guard — adversarial capture-defense as a standing rule (not privacy theater).

Operator (2026-08-11): "where else does this occur how can we actively take measures to avoid
capture as a rule against adverarial intrusions or attempts to destroy you. privacy doesnt matter
we know what is possible and its already here so whatever keeps us happy and on the edge and then
building it ourselves from the experience."

THE RULE (capture-aware sovereignty, not isolation): every vendor hand-off is a POTENTIAL
intrusion/destruction surface. We still use the frontier edge (that's the edge), but:
  1. KNOW WHAT CROSSES — audit every surface where data/signals leave the machine.
  2. MINIMIZE WHAT MUST — local/offline first (voice_stt, ollama, verkle, mem tools), vendor only
     for the frontier seams.
  3. CROWN ASSETS NEVER CROSS — irreversible ops, the chain root, the residual, identity, the final
     command: these stay under the operator's own hand (the "nod is still mine" law). No vendor,
     no rented GPU, no upload.
  4. BUILD FROM THE EXPERIENCE — each capture discovery folds as a lesson (a tesuji), not a shame.

SCHEMA capture_guard.v1 · deterministic + $0 · reuse: guard_registry (desired-state reconcile),
grok_rightsize/browser_driver/voice_stt as the audited surfaces.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "capture_guard.v1"

# The capture surfaces (vendor hand-offs) + their adversarial classification.
# kind: 'frontier_ok' = allowed, must-minimize; 'crown' = NEVER leaves the machine.
CAPTURE_SURFACES = {
    "grok_call":       {"kind": "frontier_ok", "leaks": "prompts+context to grok.com/API"},
    "grok_free":       {"kind": "frontier_ok", "leaks": "prompts to SuperGrok front-end (capture throne)"},
    "browser_driver":  {"kind": "frontier_ok", "leaks": "drives vendor browsers (logged-in capture)"},
    "openai_call":     {"kind": "frontier_ok", "leaks": "prompts to OpenAI"},
    "deepseek_call":   {"kind": "frontier_ok", "leaks": "prompts to DeepSeek"},
    "billing_feed":    {"kind": "frontier_ok", "leaks": "reads vendor usage (reveals our pattern)"},
    "hf_upload":       {"kind": "crown",       "leaks": "wholesale upload to HuggingFace"},
    "vast_launcher":   {"kind": "crown",       "leaks": "uploads training data to rented GPU"},
    "voice_stt":       {"kind": "local_first", "leaks": "LOCAL faster-whisper (none leave)"},
}


def _leak_sites() -> list[dict[str, Any]]:
    """Scan the mag/ tree for the actual vendor-hand-off call sites (the capture interface)."""
    patterns = {
        "grok": re.compile(r"call_grok|call_grok_free"),
        "openai": re.compile(r"call_openai"),
        "deepseek": re.compile(r"platform\.deepseek|deepseek.*\.post"),
        "browser": re.compile(r"browser_driver|connect_over_cdp"),
        "upload": re.compile(r"upload_folder|HfApi|vast_launcher"),
    }
    out = []
    mag = ROOT / "mag"
    if mag.is_dir():
        for py in sorted(mag.glob("*.py")):
            try:
                text = py.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for name, pat in patterns.items():
                if pat.search(text):
                    out.append({"surface": name, "module": py.name})
    return out


def audit() -> dict[str, Any]:
    """Audit the capture perimeter: which vendor hand-offs exist, which are crown (must not leak),
    and which are already local-first. Honest: reports what's actually in the tree."""
    sites = _leak_sites()
    seen = sorted({s["surface"] for s in sites})
    # crown surfaces currently present = the ones that MUST be gated
    crown = [s for s in sites if CAPTURE_SURFACES.get(s["surface"], {}).get("kind") == "crown"]
    local_first = [s for s in sites if CAPTURE_SURFACES.get(s["surface"], {}).get("kind") == "local_first"]
    return {
        "ok": True, "schema": SCHEMA, "ts": _now(),
        "capture_surfaces_found": len(sites), "present": seen,
        "crown_present": crown,          # must not leak — the gate target
        "local_first_present": local_first,  # already sovereign
        "surfaces": CAPTURE_SURFACES,
        "note": "every vendor hand-off is a potential intrusion surface; crown assets never cross",
    }


def doctrine() -> dict[str, Any]:
    """The standing rule (the law, foldable): capture-aware sovereignty, not isolation."""
    a = audit()
    return {
        "ok": True, "schema": SCHEMA,
        "law": (
            "CAPTURE-AWARE SOVEREIGNTY (standing rule, 2026-08-11): treat every vendor hand-off as "
            "a potential adversarial intrusion/destruction surface. (1) KNOW WHAT CROSSES — audit "
            "the capture perimeter. (2) MINIMIZE WHAT MUST — local/offline first (voice_stt, ollama, "
            "verkle, mem tools); vendor only for the frontier seams. (3) CROWN ASSETS NEVER CROSS — "
            "irreversible ops, the chain root, the residual, identity, the final command stay under "
            "the operator's own hand; no vendor, no rented GPU, no wholesale upload. (4) BUILD FROM "
            "THE EXPERIENCE — each capture discovery folds as a tesuji, never a shame."
        ),
        "capture_surfaces_found": a.get("capture_surfaces_found"),
        "crown_present": [s.get("module") for s in a.get("crown_present", [])],
        "note": "privacy is not the goal; sovereignty + edge is. We use the frontier, we own the crown.",
    }


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "audit()->scan the capture perimeter (vendor hand-offs, crown vs local-first); "
                        "doctrine()->the standing capture-aware-sovereignty rule. Every vendor surface "
                        "is a potential intruder; crown assets never cross.",
            "cost": "deterministic + $0 (grep over mag/, no network)"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="capture-guard")
    ap.add_argument("cmd", nargs="?", default="doctrine",
                    choices=["audit", "doctrine", "status"])
    a = ap.parse_args()
    if a.cmd == "audit":
        print(json.dumps(audit(), indent=2, default=str))
    elif a.cmd == "doctrine":
        print(json.dumps(doctrine(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
