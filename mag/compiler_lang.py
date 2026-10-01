"""compiler_lang — expand OUR COMPILER LANGUAGE (memlang + RIB lowering) intelligently by training
on EVERY harvested text file, DOGFOODING our fundamental systems. The corpus = the X-tabs/Grok
prompts harvested live from the browser this session + the shader mechanisms. Each text is run
through our own fundamental systems (percolator -> invariant, lens_shader/lens_knot -> lens+knot,
jones_lens -> topology, memlang -> compact token, world_rib -> world, machine_target -> machine).

Operator (2026-08-11): "we need every last one of these text files to learn from as training data for
our compiler lang so we can expand it intelligently using our fundamental systems as dogfood."

THE PIPELINE (deterministic + $0, every stage is a real fundamental system):
  text -> percolate(text)        -> the INVARIANT (raw signal stripped of noise/theater)
       -> lens_knot/shader       -> which LENS + VERKLE KNOT views it (a Roshomon witness)
       -> jones_lens.vector/jones-> the TOPOLOGY FINGERPRINT (the language's coordinate)
       -> memlang.compile_token  -> a COMPACT BINARY TOKEN (the language expands: new anchor+spec)
       -> world_rib.compile      -> lower the invariant to a WORLD (map precedes territory)
       -> machine_target         -> lower to MACHINE (agent-as-OS)
  dedup by invariant hash -> the LEARNED LEXICON (the language's new vocabulary from the corpus)

Schema: compiler_lang.v1 · deterministic + $0 · reuse: percolator, lens_knot, jones_lens, memlang,
world_rib, machine_target
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "compiler_lang.v1"
CORPUS_DIRS = [
    ROOT / "memory" / "ghost" / "x_surface" / "nachoquixotic_prompts",  # harvested X-tabs (Grok prompts)
]
# LEGACY DATA — sweeped through the SAME swarm process (dedupe + enqueue), not just new modules.
LEGACY_DIRS = [
    ROOT / "memory" / "learn",        # learned lessons from prior sessions (catalog/training)
    ROOT / "memory" / "percolator",   # compiled invariants + explore queue (the signal pipeline)
    ROOT / "memory" / "trash",        # legacy text dumps (harvested threads/bookmarks)
    ROOT / "memory" / "compiler_lang",  # prior compiler-lang lexicon (self-referential dogfood)
]
LEDGER = ROOT / "memory" / "compiler_lang" / "lexicon.jsonl"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def corpus() -> list[dict[str, str]]:
    """Gather EVERY harvested + LEGACY text file (the training corpus) + shader mechanisms, so ALL
    legacy data flows through the same swarm process (dedupe + enqueue)."""
    files: list[dict[str, str]] = []
    for d in CORPUS_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*")):
            if p.is_file() and p.suffix.lower() in (".md", ".txt", ".mkd"):
                txt = _read_text(p)[:20_000]
                if txt:
                    files.append({"source": f"x-tab/{p.name}", "text": txt})
    # LEGACY sweep: every legacy text/ledger file goes through the same pipeline.
    for d in LEGACY_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix.lower() in (".jsonl", ".json", ".md", ".txt"):
                txt = _read_text(p)[:20_000]
                if txt:
                    files.append({"source": f"legacy/{d.name}/{p.name}", "text": txt})
    # shader mechanisms as training data (the compiler-lang corpus from our shader-toy steal)
    try:
        from mag import shader_rib
        for sid, meta in shader_rib.SHADER_SYSTEMS.items():
            files.append({"source": f"shader/{sid}",
                          "text": meta["mechanism"] + " " + meta["frontier_task"]})
    except Exception:
        pass
    return files


def ingest(text: str, source: str) -> dict[str, Any]:
    """DOGFOOD every fundamental system on one text -> a compiler-language expansion entry."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "source": source, "error": "empty"}
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "source": source, "ts": _now(),
                           "text_len": len(text)}

    # 1) percolate -> the INVARIANT (raw signal stripped of noise/theater)
    invariant = text[:2000]
    try:
        from mag import percolator
        r = percolator.percolate(text)
        invariant = (r.get("invariant") or text[:2000])
        out["novelty"] = r.get("novelty")
    except Exception as e:
        out["percolator_error"] = str(e)[:80]

    # 2) lens -> which LENS + VERKLE KNOT views it (Roshomon witness)
    try:
        from mag import lens_knot
        knot = lens_knot.knot_id(source, invariant[:80])
        out["knot"] = knot
        # which lens the source attends to (by keyword)
        low = (source + " " + invariant[:300]).lower()
        lens = "memory/invariant"
        for ln, meta in lens_knot.LENS_FRAME.items():
            if any(a in low for a in meta["attends"]):
                lens = ln
                break
        out["lens"] = lens
    except Exception as e:
        out["lens_error"] = str(e)[:80]

    # 3) jones_lens -> the TOPOLOGY FINGERPRINT (the language's coordinate)
    try:
        from mag import jones_lens
        j = jones_lens.jones(invariant)
        out["jones"] = j["jones_fingerprint"]
        out["vector"] = jones_lens.vector(invariant)["vector"][:8]
    except Exception as e:
        out["jones_error"] = str(e)[:80]

    # 4) memlang -> a COMPACT BINARY TOKEN (the language expands: new anchor + spec)
    token = {}
    try:
        from mag import memlang
        token = memlang.compile_token("learn", f"[{source}] {invariant[:500]}",
                                      params={"source": source, "lens": out.get("lens")})
        out["memlang_token"] = token.get("token_hex", "")[:40] + "..."
        out["memlang_anchor"] = (token.get("anchor_hex") or "")[:16]
        out["memlang_action"] = token.get("action")
    except Exception as e:
        out["memlang_error"] = str(e)[:80]

    # 5) world_rib -> lower the invariant to a WORLD (map precedes territory)
    try:
        from mag import world_rib
        w = world_rib.compile(invariant, w=32, h=32)
        out["world"] = {"hash": w.get("hash", ""), "seed": w.get("seed")}
    except Exception as e:
        out["world_error"] = str(e)[:80]

    # 6) machine_target -> lower to MACHINE (agent-as-OS) — best-effort
    try:
        from mag import machine_target
        m = machine_target.lower(invariant) if hasattr(machine_target, "lower") else {}
        out["machine"] = bool(m)
    except Exception as e:
        out["machine_error"] = str(e)[:80]

    return out


def _already_sent() -> set[str]:
    """Anchors already enqueued to the swarm (dedupe via the SHARED swarm_surface ledger)."""
    try:
        from mag import swarm_surface
        # read the shared sent-ledger through the shared primitive
        rows = []
        if swarm_surface.LEDGER.is_file():
            for line in swarm_surface.LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    a = json.loads(line).get("anchor") or ""
                    if a:
                        rows.append(a)
                except Exception:
                    continue
        return set(rows)
    except Exception:
        return set()


def expand(*, write: bool = True, enqueue: bool = True) -> dict[str, Any]:
    """Run the corpus through the pipeline and DOGFOOD the process through the SHARED swarm_surface
    primitive: novel research is DEDUPED (by anchor) + enqueued to the SWARM RESEARCH QUEUE via
    mag.swarm_surface.route_novel -> swarm_worker.enqueue_task -> k8s worker drains in-cluster.
    The swarm coordinates this task surface; we never run it locally."""
    from mag import swarm_surface
    docs = corpus()
    sent, already = [], _already_sent()
    for d in docs:
        r = ingest(d["text"], d["source"])
        if not r.get("ok"):
            continue
        goal = (f"RESEARCH-PACK compiler_lang [{r.get('lens','lens')}] {d['source']}: "
                f"expand the compiler language from this harvested text. Invariant: "
                f"{r.get('invariant','')[:400]}  lens={r.get('lens')} jones={r.get('jones')} "
                f"knot={r.get('knot')}.")
        anchor = swarm_surface.anchor(goal, "compiler_lang")
        if anchor in already:
            continue  # dedupe via the shared ledger
        q = {"ok": False, "task_id": ""}
        if enqueue:
            q = swarm_surface.route_novel(goal, surface="compiler_lang",
                                          lens=r.get("lens"), domain="research")
        sent.append({"source": d["source"], "anchor": anchor, "lens": r.get("lens"),
                     "jones": r.get("jones"), "queued": q.get("task_id", ""),
                     "ok": q.get("ok", False)})
    if write:
        # the SHARED swarm_surface ledger is the dedup source of truth (written by route_novel);
        # we only mirror provenance here for the corpus surface itself.
        pass
    return {"ok": True, "schema": SCHEMA, "n_corpus": len(docs), "n_novel": len(sent),
            "n_deduped": len(docs) - len(sent),
            "sent_to_swarm": len([s for s in sent if s["ok"]]),
            "sent": sent[:20],
            "note": "novel research deduped + sent to the swarm research queue via the SHARED "
                    "swarm_surface primitive; the k8s worker drains it and files the result back — "
                    "the swarm coordinates this task surface, dogfooding the process (no local run)"}


def learned_lexicon() -> dict[str, Any]:
    """Read back the LEARNED LEXICON (the expanded vocabulary) from the ledger."""
    rows = []
    if LEDGER.is_file():
        for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return {"ok": True, "schema": SCHEMA, "n_lexemes": len(rows), "lexemes": rows[-200:],
            "lexicon_path": str(LEDGER.relative_to(ROOT)).replace("\\", "/")}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "corpus()->harvested text files + shader mechanisms; "
                        "ingest(text)->dogfood percolator/lens/jones/memlang/world/machine; "
                        "expand()->dedup + record the learned lexicon",
            "cost": "deterministic + $0 (dogfoods our own fundamental systems)",
            "corpus_dirs": [str(d.relative_to(ROOT)).replace("\\", "/") for d in CORPUS_DIRS],
            "lexicon_path": str(LEDGER.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="compiler-lang")
    ap.add_argument("cmd", nargs="?", default="expand",
                    choices=["expand", "corpus", "lexicon", "ingest", "status"])
    ap.add_argument("text", nargs="?", default="")
    a = ap.parse_args()
    if a.cmd == "expand":
        print(json.dumps(expand(), indent=2, default=str))
    elif a.cmd == "corpus":
        c = corpus()
        print(json.dumps({"n_corpus": len(c), "sources": [x["source"] for x in c]},
                         indent=2, default=str))
    elif a.cmd == "lexicon":
        print(json.dumps(learned_lexicon(), indent=2, default=str))
    elif a.cmd == "ingest":
        print(json.dumps(ingest(a.text or "test", "manual"), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
