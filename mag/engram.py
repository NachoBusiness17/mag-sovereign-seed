"""engram — the chain IS the engram: resident template layer, v0 (2026-09-13).

The fold (watch/inbox/ENGRAM_FOLD_20260913.md) converged 7/8: 95% of session context
is shared template; the engram stores only the delta. Three tiers — chain (permanent)
→ engram (template + deltas) → working set (the bobbin). This module is the two
functions the fold demanded, plus the leaf type, with the falsifier wired in:
decompressed sessions must match the original >=95% (v0 bar: byte-exact = 100%).

Leaf type (engram.v1): {template_id, delta, payload_hash, verdict, ts}
  - template_id = sha256 of the shared template text (stored once in the template store)
  - delta       = the session text minus the template prefix ("" if pure template)
  - payload_hash= sha256 of the ORIGINAL text — the verify-on-read receipt
Compression ratio = 1 - len(delta)/len(original) when the template matches.

Dogfood (selftest --file F): treats F's shared head (everything before the first
"## " section) as the resident template and each "## " section as a session leaf —
the same shape a wave pack has (one shared head, N lane bodies). Round-trip every
leaf byte-exact, report the ratio, verify payload hashes.

Wiring note (honest): fanout integration is DECLARED, not done — wave_fire phase 2
would call compress() on the shared pack head per lane. The organ and receipt land first.

CLI:
  python -m mag.engram compress --file F --template-head-to "## TARGET"
  python -m mag.engram selftest --file F
State: state/engram_templates.json (template store, content-addressed).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "state" / "engram_templates.json"
SCHEMA = "engram.v1"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _store() -> dict:
    if STORE.is_file():
        try:
            return json.loads(STORE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"schema": SCHEMA, "templates": {}}


def compress(text: str, template: str) -> dict:
    """Split a session into {template_id, delta}. Template prefix stripped when present."""
    tid = _sha(template)
    st = _store()
    if tid not in st["templates"]:
        st["templates"][tid] = {"template": template, "ts": datetime.now(timezone.utc).isoformat()}
        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    delta = text[len(template):] if template and text.startswith(template) else text
    return {"schema": SCHEMA, "template_id": tid, "delta": delta,
            "template_applied": bool(template and text.startswith(template)),
            "payload_hash": _sha(text), "verdict": "engram",
            "ts": datetime.now(timezone.utc).isoformat(),
            "ratio": round(1 - len(delta) / max(len(text), 1), 3)}


def decompress(leaf: dict) -> str:
    """Rebuild the original from template + delta; raises on payload_hash mismatch."""
    st = _store()
    template = st["templates"].get(leaf["template_id"], {}).get("template", "")
    rebuilt = (template if leaf.get("template_applied") else "") + leaf["delta"]
    if _sha(rebuilt) != leaf["payload_hash"]:
        raise ValueError(f"payload_hash mismatch — engram leaf corrupt (template_id {leaf['template_id'][:12]})")
    return rebuilt


def selftest(file_path: str) -> int:
    text = Path(file_path).read_text(encoding="utf-8")
    marker = "## TARGET"
    head_end = text.find(marker)
    if head_end < 0:
        print("SELFTEST FAIL: no '## TARGET' sections in file (wave-pack shape required)")
        return 2
    template = text[:head_end]
    sections = []
    rest = text[head_end:]
    parts = rest.split(marker)
    for i in range(1, len(parts)):
        sections.append(marker + parts[i])
    if not sections:
        print("SELFTEST FAIL: zero leaves")
        return 2
    # a different template that does NOT match must degrade gracefully (delta = full text)
    leaves = [compress(s, template) for s in sections]
    mismatch = compress(sections[0], "definitely-not-the-template\n")
    ok = True
    total_orig = total_delta = 0
    for leaf, original in zip(leaves, sections):
        rebuilt = decompress(leaf)
        match = rebuilt == original
        ok &= match
        total_orig += len(original)
        total_delta += len(leaf["delta"])
    ro = decompress(mismatch)
    ok &= (ro == sections[0])
    ratio = round(1 - total_delta / max(total_orig, 1), 3)
    print(f"  leaves: {len(leaves)}  round-trip byte-exact: {ok}  (falsifier bar: >=95%)")
    print(f"  template: {len(template)} chars stored once; body deltas: {total_delta} chars")
    print(f"  compression ratio across leaves: {ratio} ({total_orig} -> {total_delta + 0} delta chars)")
    print(f"  mismatch-template leaf degrades to full delta and still round-trips: {ro == sections[0]}")
    print(f"SELFTEST {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="engram")
    ap.add_argument("action", choices=["compress", "decompress", "selftest"])
    ap.add_argument("--file", required=True)
    ap.add_argument("--template-head-to", default="## TARGET")
    args = ap.parse_args()
    if args.action == "selftest":
        return selftest(args.file)
    text = Path(args.file).read_text(encoding="utf-8")
    idx = text.find(args.template_head_to)
    leaf = compress(text, text[:idx] if idx > 0 else "")
    print(json.dumps({k: v for k, v in leaf.items() if k != "delta"}, indent=2))
    print(f"delta chars: {len(leaf['delta'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
