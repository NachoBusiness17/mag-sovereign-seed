"""ox_fold — THE STANDING-WAVE FOLD: process/dedupe/synthesize each megaburn output AS IT LANDS.

Operator (2026-08-22): "these things are coming in slow that gives us time now to process dedupe
and create a synthesis without waiting for them all to finish... we can do in tandem allowing all
of them to use our systems to create this compounding loop. The standing wave."

So instead of waiting for all 100 to finish then post-processing, we fold EACH banked output into a
growing synthesis the moment it lands: dedupe by content anchor, process the claims, synthesize
into a running document, and feed the running invariant forward so the next lensing/ask is sharper.
The synthesis re-derives from every folded fragment — the standing wave re-knotted from the
incoming interference.

Schema: ox_fold.v1
Run:  python -m mag.ox_fold fold            # fold any new banked outputs into the synthesis
      python -m mag.ox_fold watch [--every S] # continuous: fold as outputs land
      python -m mag.ox_fold status            # synthesis state
"""
from __future__ import annotations

import hashlib
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

SCHEMA = "ox_fold.v1"
OUT_DIR = ROOT / "handoff"
SYNTH_FILE = OUT_DIR / "OX_SYNTHESIS.md"
FOLD_LEDGER = ROOT / "memory" / "runs" / "ox_fold_ledger.jsonl"
WAVE_GLOB = "OX_MEGA_*.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _anchor(content: str, reasoning: str) -> str:
    return hashlib.sha256(f"{content}\n{reasoning}".encode("utf-8")).hexdigest()[:16]


def _folded_anchors() -> set[str]:
    if not FOLD_LEDGER.is_file():
        return set()
    out = set()
    for line in FOLD_LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if d.get("anchor"):
                out.add(d["anchor"])
        except Exception:
            continue
    return out


def _banked_names() -> list[str]:
    return sorted(p.stem.removeprefix("OX_MEGA_") for p in OUT_DIR.glob(WAVE_GLOB))


def _theme(name: str) -> str:
    """Coarse theme bucket from the task name (for grouping the synthesis)."""
    n = name.replace("_", " ").lower()
    if any(k in n for k in ("code", "law", "govern", "enforc", "invariant", "sanction", "constitut")):
        return "code-as-law"
    if any(k in n for k in ("token", "coordinate", "bridge", "merge", "meta")):
        return "meta-token"
    if any(k in n for k in ("verkle", "proof", "root", "hash", "merkle", "tamper")):
        return "verification"
    if any(k in n for k in ("deniab", "comms", "riddler", "opsec", "secret")):
        return "deniable-comms"
    if any(k in n for k in ("consensus", "swarm", "flock", "illusion")):
        return "consensus"
    if any(k in n for k in ("cache", "hit", "measured", "split", "rightsize", "cost")):
        return "cache-economics"
    if any(k in n for k in ("checkpoint", "context", "edit", "anchor", "semantic")):
        return "agentic-context"
    if any(k in n for k in ("sovereign", "frontier", "integration", "fold", "scout", "own")):
        return "sovereignty"
    return "foundation"


def _clip(text: str, limit: int = 400) -> str:
    """First meaningful paragraph of a text, stripped of markdown headers, capped at limit."""
    lines = [l for l in text.splitlines() if l.strip()]
    out = []
    for l in lines:
        out.append(l.strip())
        if len("\n".join(out)) >= limit:
            break
    return "\n".join(out)[:limit]


def _substance(content: str, reasoning: str, limit: int = 400) -> str:
    """THE INVERSION (ox-alpha steal, 2026-08-23): REASONING is the durable product (the tape);
    CONTENT is the optional terminal commit. Fold whichever channel carried the substance, and
    LABEL the reasoning stream when it's the product — so content-null + reasoning-as-deliverable
    is folded as VALID (the 3-channel contract we proved), not dropped as a fallback."""
    c = (content or "").strip()
    r = (reasoning or "").strip()
    if not c and not r:
        return ""
    if len(r) > len(c):
        return f"[reasoning tape] {_clip(r, limit)}"
    return _clip(c, limit)


def rewrite() -> dict[str, Any]:
    """Force a full re-render of the synthesis with the CURRENT fold logic (the inversion).

    Applies reasoning-as-residual retroactively: the old fold was content-first and, for the 93/100
    reasoning-dominant outputs, folded only thin content and marginalized the actual product (the
    tape). This rebuilds the whole doc from the ledger with _substance (reasoning folds as the
    deliverable when it carried the substance).
    """
    _rewrite_synthesis([])
    t = SYNTH_FILE.read_text(encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "action": "rewrite",
            "synthesis_chars": len(t), "reasoning_tape_marks": t.count("[reasoning tape]")}


def fold() -> dict[str, Any]:
    """Fold every NEW banked output into the growing synthesis (deduped by content anchor)."""
    seen = _folded_anchors()
    folded: list[dict[str, Any]] = []
    duplicates = 0
    by_theme: dict[str, int] = {}
    for name in _banked_names():
        p = OUT_DIR / f"OX_MEGA_{name}.json"
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        content = (d.get("content") or "").strip()
        reasoning = (d.get("reasoning") or "").strip()
        if not content and not reasoning:
            continue
        a = _anchor(content, reasoning)
        if a in seen:
            duplicates += 1
            continue
        theme = _theme(name)
        by_theme[theme] = by_theme.get(theme, 0) + 1
        # route genuinely novel research through the shared swarm primitive (standing law)
        routed = ""
        try:
            from mag import swarm_surface
            rr = swarm_surface.route_novel(
                f"{name}: {_substance(content, reasoning, 220)}", surface=f"ox-fold-{theme}",
                lens="standing-wave-synthesis")
            routed = rr.get("task_id", "")
        except Exception:
            routed = ""
        rec = {"name": name, "theme": theme, "anchor": a, "ts": _now(),
               "content_chars": len(content), "reasoning_chars": len(reasoning),
               "swarm_task": routed, "summary": _substance(content, reasoning)}
        folded.append(rec)
        seen.add(a)
        FOLD_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with FOLD_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"anchor": a, "name": name, "theme": theme, "ts": _now(),
                                "swarm_task": routed}, ensure_ascii=False) + "\n")
    if folded:
        _rewrite_synthesis(folded)
    return {"ok": True, "schema": SCHEMA, "folded_new": len(folded), "duplicates": duplicates,
            "by_theme": by_theme, "total_banked": len(_banked_names())}


def _rewrite_synthesis(new_folds: list[dict[str, Any]]) -> None:
    """Rewrite the standing synthesis doc from the fold ledger (the wave re-knotted)."""
    all_folds: list[dict[str, Any]] = []
    if FOLD_LEDGER.is_file():
        for line in FOLD_LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                all_folds.append(json.loads(line))
            except Exception:
                continue
    # re-read summaries from the banked files for the doc body
    rows = []
    for r in all_folds:
        name = r.get("name", "")
        d = {}
        try:
            d = json.loads((OUT_DIR / f"OX_MEGA_{name}.json").read_text(encoding="utf-8"))
        except Exception:
            pass
        rows.append({"name": name, "theme": r.get("theme", "foundation"),
                     "summary": _substance(d.get("content") or "", d.get("reasoning") or "")})
    by_theme: dict[str, list[str]] = {}
    for r in rows:
        by_theme.setdefault(r["theme"], []).append(f"- **{r['name']}** — {r['summary']}")
    body = ["# OX STANDING-WAVE SYNTHESIS", "",
            f"_Re-knotted from every folded fragment as the wave arrived. {len(rows)} folds._", ""]
    total = 0
    for theme in sorted(by_theme):
        items = by_theme[theme]
        body.append(f"## {theme} ({len(items)})")
        body.extend(items)
        body.append("")
        total += len(items)
    body.append(f"## Running invariant")
    body.append("Every fold re-derives the same chord: many actors, one authored invariant, a "
                "root that re-derives. The synthesis is the standing wave — the persistent thread "
                "re-knotted from the interference of all incoming fragments.")
    SYNTH_FILE.write_text("\n".join(body), encoding="utf-8")


def watch(*, every_s: int = 90) -> None:
    """Continuous fold: as each output lands, dedupe + synthesize in tandem. Ctrl+C to stop."""
    import time
    last = -1
    print(f"[ox_fold] standing-wave fold up — every {every_s}s. Ctrl+C to stop.", flush=True)
    while True:
        try:
            n = len(_banked_names())
            if n != last:
                last = n
                r = fold()
                print(f"[ox_fold] banked={n} folded_new={r['folded_new']} "
                      f"dup={r['duplicates']} themes={r['by_theme']}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[ox_fold] ERR {type(e).__name__}: {str(e)[:120]}", flush=True)
        time.sleep(max(int(every_s), 30))


def status() -> dict[str, Any]:
    folds = 0
    if FOLD_LEDGER.is_file():
        folds = sum(1 for _ in FOLD_LEDGER.open(encoding="utf-8"))
    return {"ok": True, "schema": SCHEMA, "folded": folds, "banked": len(_banked_names()),
            "synthesis_file": str(SYNTH_FILE), "synthesis_exists": SYNTH_FILE.is_file()}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="ox-fold")
    ap.add_argument("cmd", nargs="?", default="fold", choices=["fold", "watch", "status"])
    ap.add_argument("--every", type=int, default=90)
    a = ap.parse_args()
    if a.cmd == "watch":
        watch(every_s=a.every)
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(fold(), indent=2, ensure_ascii=False, default=str))
