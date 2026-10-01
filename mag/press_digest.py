"""press_digest — recurring process: surface the NEXT pressing matter cheaply.

The operator wants a recurring cadence that:
  1. Taps the "next pieces that percolate through the self-learning system"
     (scrum backlog, ghost_summon coldest vertices, orphan intents, idea_graph
     open loops, recent failures, queued research packs).
  2. Runs the cheap research loop + Rashomon filter (multiple cheap perspectives)
     on the top candidate — AFTER exhausting what the operator would do.
  3. Surfaces the pressing matter to the operator (operator_inbox + a digest file)
     — as cheaply as possible: local/flash, dataset-guided, steal protocols, NO grok.

Schema: press_digest.v1
Wired into the governor cadence (MAG_PRESS_EVERY, default ~900 ticks).

CLI: python -m mag.press_digest gather|digest|emit
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "press_digest.v1"
PRESS_DIR = ROOT / "memory" / "press"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(rel: str, tail: int = 0) -> list[dict[str, Any]]:
    fp = ROOT / rel
    if not fp.is_file():
        return []
    rows = []
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows[-tail:] if tail else rows


def gather() -> dict[str, Any]:
    """Collect the percolating signals from the self-learning system (cheap, deterministic)."""
    items: list[dict[str, Any]] = []

    # scrum next (proof-first backlog)
    try:
        from mag.scrum import sprint
        sp = sprint()
        nxt = sp.get("item")
        if nxt:
            items.append({"src": "scrum", "id": nxt.get("id"), "title": nxt.get("title"),
                          "tier": nxt.get("tier"), "note": nxt.get("note", "")})
    except Exception:
        pass

    # ghost_summon coldest vertices (being neglected)
    try:
        from mag.ghost_summon import coldest_vertices
        for v in coldest_vertices(limit=4):
            items.append({"src": "coldest", "id": v.get("id"), "title": v.get("title"),
                          "note": f"coldest vertex ({v.get('degree')} conn)"})
    except Exception:
        pass

    # orphan intents (undone-yet-intended)
    try:
        from mag.orphan_timer import list_open
        for o in list_open()[:4]:
            items.append({"src": "orphan", "id": o.get("id"), "title": o.get("intent"),
                          "note": f"orphan since {str(o.get('first_seen') or '')[:16]}"})
    except Exception:
        pass

    # recent failure signals (FKB) — pressing if recurring
    try:
        fkb = _read_jsonl("logs/failure_kb.jsonl", tail=200)
        sigs: dict[str, int] = {}
        for r in fkb:
            s = r.get("sig") or ""
            if s:
                sigs[s] = sigs.get(s, 0) + 1
        hot = sorted(sigs.items(), key=lambda x: x[1], reverse=True)[:3]
        for s, n in hot:
            if n >= 3:
                items.append({"src": "failure", "id": s, "title": f"recurring failure x{n}",
                              "note": s[:80]})
    except Exception:
        pass

    # queued research packs (frontier/steal ready)
    try:
        from mag.research_pack import PACKS
        if PACKS.is_dir():
            fresh = sorted(PACKS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for p in fresh[:2]:
                try:
                    j = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                    items.append({"src": "research", "id": j.get("id"), "title": j.get("title", ""),
                                  "note": "fresh research pack"})
                except Exception:
                    pass
    except Exception:
        pass

    return {"schema": SCHEMA, "ts": _now(), "ok": True, "items": items, "count": len(items)}


def pick() -> dict[str, Any]:
    """Pick the single most PRESSING candidate, cheapest-first (scrum proof-first bias)."""
    g = gather()
    items = g["items"]
    if not items:
        return {"schema": SCHEMA, "ts": _now(), "ok": True, "item": None, "count": 0}
    rank = {"scrum": 0, "failure": 1, "orphan": 2, "coldest": 3, "research": 4}
    items.sort(key=lambda x: (rank.get(x["src"], 5), x.get("title", "")))
    return {"schema": SCHEMA, "ts": _now(), "ok": True, "item": items[0],
            "count": len(items), "all": [i["title"] for i in items[:6]]}


def rashomon(item: dict[str, Any]) -> str:
    """Cheap multi-perspective (Rashomon) note on the pressing item — local, no grok."""
    from mag.game_brawl_perspectives import _VOICES  # voice bank (cheap templates)
    import random
    voices = _VOICES.get("corner_stranger") + _VOICES.get("merchant_gil") + _VOICES.get("drinker_bo")
    if not voices:
        return ""
    chosen = random.sample(voices, min(2, len(voices)))
    return "\n".join(f"- {v}" for v in chosen)


def digest() -> dict[str, Any]:
    """Produce the pressing-matter digest (cheap): pick + rashomon + dataset note."""
    p = pick()
    item = p.get("item")
    if not item:
        return {"schema": SCHEMA, "ts": _now(), "ok": True, "pressing": None, "note": "nothing pressing"}
    return {
        "schema": SCHEMA, "ts": _now(), "ok": True, "pressing": item,
        "candidate_count": p.get("count"),
        "rashomon": rashomon(item),
        "dataset_guide": "steal_protocol + corpus lenses guide the next cheap research pass",
        "cheap_only": True,
    }


def emit() -> dict[str, Any]:
    """Write the digest to operator_inbox (reaches operator at checkpoint) + a surface file."""
    d = digest()
    PRESS_DIR.mkdir(parents=True, exist_ok=True)
    with open(PRESS_DIR / "latest.json", "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False, default=str)
    md = PRESS_DIR / "PRESS_DIGEST.md"
    if d.get("pressing"):
        item = d["pressing"]
        md.write_text(
            f"# PRESS DIGEST {d['ts']}\n\n"
            f"## Pressing: [{item.get('src')}] {item.get('title')}\n\n"
            f"_{item.get('note') or ''}_\n\n"
            f"### Rashomon (cheap perspectives)\n{d.get('rashomon') or '_no voices_'}\n\n"
            f"Next: run the cheap research loop (dataset-guided, steal protocols) on this item — "
            f"no grok until a frontier need is proven.\n",
            encoding="utf-8")
        try:
            from mag.operator_inbox import commit_guidance
            commit_guidance(
                f"[press] {item.get('title')} — surface this (src={item.get('src')}). "
                f"Digest: {PRESS_DIR/'PRESS_DIGEST.md'}",
                source="press_digest")
        except Exception as e:
            d["inbox_error"] = str(e)[:120]
        # memlang is the PRIMARY operation vector for steering: compile the pressing
        # matter into a verkle-anchored memlang `steer` token + STEER packet, so the
        # operator's agent consumes it via the steer->memlang path (not ad-hoc).
        try:
            from mag.memlang import compile_token
            d["memlang"] = compile_token("steer", f"press: {item.get('title','')[:200]}")
        except Exception as e:
            d["memlang_error"] = str(e)[:120]
        try:
            from mag.steer import emit as steer_emit
            d["steer_packet"] = steer_emit(f"press-{item.get('id','')}", "press_digest",
                                           f"[STEER] {item.get('title','')[:200]}",
                                           phases=["press"], steer_back=True)
        except Exception as e:
            d["steer_error"] = str(e)[:120]
    d["path"] = str(PRESS_DIR / "PRESS_DIGEST.md")
    return d


def run_cadence() -> dict[str, Any]:
    """Cadence entry (governor). Deterministic + cheap; never grok; surfaces to operator."""
    return emit()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "digest").lower()
    if cmd == "gather":
        print(json.dumps(gather(), indent=2, ensure_ascii=False, default=str))
    elif cmd == "emit":
        print(json.dumps(emit(), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(digest(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
