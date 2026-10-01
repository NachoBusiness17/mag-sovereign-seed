"""game_piece_tandem — one seat MINES the spec, the other WRITES the code, I fold it (2026-08-17).

THE TANDEM (operator): "drive them to code out what remains in tandem helping each other work on
pieces while you do research on best practices and rightsizing solutions and pausing them or
redirecting them while you gather the right resources for tasks they're to take."

THE HONEST DIVISION (grounded in the burner's real shape):
  - Seats produce TEXT. They can't write files to our repo through the burner. So:
      seat A (MINE)  -> takes a steal-table item, produces a grounded SPEC (text, on-contract)
      seat B (WRITE) -> takes that SPEC, produces the CODE MODULE (text, on-contract)
      me (coordinator) -> verify each accepted output + FOLD the accepted code into an actual file
                          under mag/ (deterministic). Pause/redirect if either drifts.
  - Steal corpus is the target list (docs/ref/GAME_THEORY_PLAY_MAP.md Tier B: Nomic rules_patch,
    Diplomacy multi-party, Pandemic common-pool threat, etc.).

Schema: game_piece_tandem.v1 · deterministic coordinator + watched seats · reuse: grok_seat_burner
(run_watched/record_spend), swarm_surface (novel routing), verkle/memory (fold).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "game_piece_tandem.v1"

# The steal-table items that are genuine remaining pieces (Tier B, not yet built).
STEAL_ITEMS: list[dict[str, str]] = [
    {"name": "nomic_rules_patch", "source": "Nomic",
     "what": "a rules_patch mechanic where players propose a rule change that must pass before it mutates the world",
     "landing": "mag/game_mud.py or a new mag/game_rules.py — add a 'propose'/'vote' action"},
    {"name": "diplomacy_multi_party", "source": "Diplomacy",
     "what": "a multi-party FILE-then-act mechanic: parties write a shared file, then act on the committed state",
     "landing": "new mag/game_diplomacy.py — shared-file turn resolution"},
    {"name": "pandemic_common_pool", "source": "Pandemic",
     "what": "a common-pool threat mechanic: players share a dwindling resource and must coordinate or the pool collapses",
     "landing": "new mag/game_threat.py — shared-threat budget"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _card_txt() -> str:
    p = ROOT / "memory" / "runs" / "SEAT_CARD.md"
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _pick_item(name: str | None = None) -> dict[str, str]:
    if name:
        for it in STEAL_ITEMS:
            if it["name"] == name:
                return it
    return STEAL_ITEMS[0]


def mine_spec(item: dict[str, str], seat: str = "nacho") -> dict[str, Any]:
    """Seat A (MINE): turn a steal-table item into a grounded, concrete build SPEC."""
    from mag.grok_seat_burner import run_watched
    spec = {
        "deliverable": (
            f"Write a concrete BUILD SPEC for adding a {item['name']} mechanic to the game, "
            f"stolen from {item['source']}: {item['what']}. Include: (1) the exact actions/verbs "
            f"to add, (2) the data shape, (3) which existing module it lands in ({item['landing']}), "
            f"(4) the invariants it must respect. 3-5 concise paragraphs."
        ),
        "scene": "the game build", "word_limit": 600, "context": _card_txt(),
        "max_turns": 8, "timeout": 400,
    }
    r = run_watched(seat, spec)
    return {"ok": bool(r.get("ok")), "seat": seat, "phase": "mine",
            "accepted": r.get("accepted"), "spec": (r.get("accepted") or {}).get("output", "")}


def write_code(spec_text: str, item: dict[str, str], seat: str = "sd") -> dict[str, Any]:
    """Seat B (WRITE): turn the mined SPEC into an actual Python CODE MODULE.

    BEST-PRACTICE (2026-08-17): use JSON-SCHEMA structured output so the seat returns the code in
    a parseable field instead of prose that fails to parse. This fixes the 'write produced no code'
    failure — the schema constrains the output to a reliable shape."""
    from mag.grok_seat_burner import run_watched
    code_spec = {
        "deliverable": (
            f"Write a COMPLETE, working Python module that implements the {item['name']} mechanic "
            f"stolen from {item['source']}. The spec:\n{spec_text[:3000]}\n\n"
            f"Land it at {item['landing']}. The module must be importable, deterministic, $0, and "
            f"match our style (a SCHEMA constant, a status() function, reuse not invent). "
            f"Return ONLY a JSON object with one key 'code' whose value is the full module text. "
            f"No markdown fences around the JSON. The code will be saved to a file verbatim."
        ),
        "scene": "the game build", "word_limit": 1500, "context": _card_txt(),
        "max_turns": 8, "timeout": 500,
        "json_schema": json.dumps({
            "type": "object", "properties": {"code": {"type": "string"}},
            "required": ["code"],
        }),
    }
    r = run_watched(seat, code_spec)
    out = (r.get("accepted") or {}).get("output") or ""
    code = _unwrap_code(out)
    return {"ok": bool(code.strip()), "seat": seat, "phase": "write",
            "accepted": r.get("accepted"), "code": code, "raw": out[:200]}


def _unwrap_code(raw: str) -> str:
    """PURE + DETERMINISTIC: extract the code text from grok's json_schema output (no monkeypatch,
    re-derivable — same raw -> same code). Handles the shapes observed from grok (2026-08-17):
      1. {"structuredOutput": {"code": "..."}}   <- the clean shape
      2. {"text": "<json-string of {code:...}>"}  <- text-wrapped double-encoded
      3. {"text": "..."}                          <- plain
    structuredOutput.code is itself a JSON-encoded string, so decode it fully to clean source."""
    out = (raw or "").strip()
    if not out:
        return ""
    try:
        val = json.loads(out)
        for _ in range(6):
            if isinstance(val, dict) and "structuredOutput" in val:
                val = val["structuredOutput"]
            elif isinstance(val, dict) and "text" in val:
                v = val["text"]
                try:
                    val = json.loads(v) if isinstance(v, str) else v
                except Exception:
                    val = v
                    break
            elif isinstance(val, dict) and "code" in val:
                val = val["code"]
                break
            else:
                break
        code = str(val) if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
    except Exception:
        return out
    # if code is still a JSON object string, try one more unwrap
    if code.strip().startswith("{"):
        try:
            p2 = json.loads(code)
            if isinstance(p2, dict):
                code = str(p2.get("code") or p2.get("text") or p2.get("structuredOutput") or code)
        except Exception:
            pass
    # structuredOutput.code is often itself a JSON-encoded string (escaped). Decode once more so
    # we get clean source text, not a repr with \\\" escapes.
    if code.strip().startswith("\\") or code.strip().startswith('"') or "\\n" in code:
        try:
            decoded = json.loads(code)
            if isinstance(decoded, str):
                code = decoded
        except Exception:
            pass
    return code


def _fold_code(item: dict[str, str], code: str) -> dict[str, Any]:
    """Fold the accepted code into an actual file under mag/. Deterministic, honest — only writes
    if the code is non-trivial and we have a safe landing path."""
    code = (code or "").strip()
    if len(code) < 100:
        return {"ok": False, "error": "code too short to fold", "n_chars": len(code)}
    # landing: strip 'mag/' prefix if present; default safe path
    rel = str(item.get("landing") or "").split("|")[0].strip()
    rel = rel.replace("mag/", "").replace("mag\\", "")
    if not rel.endswith(".py"):
        rel = f"game_{item['name']}.py"
    dest = ROOT / "mag" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    # never clobber an existing non-empty file without a marker
    if dest.is_file() and dest.stat().st_size > 200:
        return {"ok": False, "error": f"target exists (won't clobber): {rel}", "path": str(dest)}
    try:
        dest.write_text(code + "\n", encoding="utf-8")
        return {"ok": True, "path": str(dest.relative_to(ROOT)).replace("\\", "/"),
                "n_chars": len(code)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def run_tandem(item_name: str | None = None, *,
               mine_seat: str = "nacho", write_seat: str = "sd") -> dict[str, Any]:
    """THE TANDEM LOOP for one piece: A mines spec -> B writes code -> I fold + record."""
    item = _pick_item(item_name)
    print(f"[tandem] {item['name']} ({item['source']}) — {mine_seat} mines, {write_seat} writes", flush=True)
    m = mine_spec(item, seat=mine_seat)
    if not m.get("spec"):
        return {"ok": False, "schema": SCHEMA, "phase": "mine", "mine": m,
                "error": "mine produced no spec"}
    w = write_code(m["spec"], item, seat=write_seat)
    if not w.get("code"):
        return {"ok": False, "schema": SCHEMA, "phase": "write", "mine": m, "write": w,
                "error": "write produced no code"}
    fold = _fold_code(item, w["code"])
    # record spend for both phases
    try:
        from mag.grok_seat_burner import record_spend
        record_spend(mine_seat, m.get("accepted") and {"accepted": m.get("accepted")}, {"deliverable": f"mine {item['name']}"})
        record_spend(write_seat, w.get("accepted") and {"accepted": w.get("accepted")}, {"deliverable": f"write {item['name']}"})
    except Exception:
        pass
    return {"ok": fold.get("ok"), "schema": SCHEMA, "item": item["name"],
            "fold": fold, "mine_seat": mine_seat, "write_seat": write_seat,
            "mine_words": len(m.get("spec", "").split()), "write_chars": len(w.get("code", "")),
            "note": "seat A mined the spec, seat B wrote the code, I folded it to disk"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "run_tandem(item)->A mines spec, B writes code, fold to disk; "
                        "STEAL_ITEMS = the Tier B pieces not yet built; status()->this",
            "items": [it["name"] for it in STEAL_ITEMS],
            "cost": "deterministic coordinator; the two seat calls are the scarce cost",
            "reuse": "grok_seat_burner.run_watched/record_spend, SEAT_CARD, steal corpus"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "status").lower()
    if cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
        return 0
    if cmd == "run":
        item = argv[1] if len(argv) > 1 else None
        print(json.dumps(run_tandem(item), indent=2, ensure_ascii=False, default=str))
        return 0
    print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
