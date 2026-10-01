"""ox_megaburn3 — WAVE 3: the THOUSAND-ASK BURN. Scale the free frontier window to the max.

Operator (2026-08-23): "i want you to do a thousand this time."

So this is the thousand-ask megaburn: a GENERATOR crosses hard problem cores x scopes x contexts x
lenses into ~1000 DISTINCT concrete asks, deduped by content anchor (no true repeats), fired 8-way
parallel through the free reasoning seat, each banked to handoff/OX_MEGA3_<name>.json (resume by
file-existence, so a partial/long burn never loses completed work). Each ask is a real hard problem
explored from a distinct angle — the same way you'd mine a frontier brain deeply.

Schema: ox_megaburn3.v1
Run:  python -m mag.ox_megaburn3            # generate + fire the thousand (resumes unfinished)
      python -m mag.ox_megaburn3 --catalog  # print the generated catalog names (no fire)
      python -m mag.ox_megaburn3 --summary  # banked count + synthesis state
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "ox_megaburn3.v1"
OUT_DIR = ROOT / "handoff"
LEDGER = ROOT / "memory" / "runs" / "ox_megaburn3_ledger.jsonl"
CONCURRENCY = int(__import__("os").environ.get("OX_MEGABURN3_CONCURRENCY", "8"))
BATCH_SLEEP_S = 1
TARGET = 1000

# ── HARD PROBLEM CORES (each is a real hard problem we're mining deeply) ──────────
CORES: list[str] = [
    "the meta-token: one content-addressed anchor resolving meaning across multiple token sets",
    "a compact verkle/merkle proof any neutral verifier can re-derive without the full tree",
    "a tamper-evident append-only ledger where every entry commits to the prior root",
    "a gated state-machine transition that REFUSES (byte-identical root) unless a precondition holds",
    "a deniable-yet-verifiable comms protocol (meaning recoverable only with our codebook, authorship provable)",
    "consensus without a central brain: N stateless workers speak as one honest voice, no drift",
    "consensus-illusion detection: separating true agreement from N correlated hallucinations",
    "a measured split q* = m*B_P/B_H that makes two resource paths finish together",
    "semantic-anchor checkpoints so an agent's context edit re-prefills only the new suffix",
    "an invariant lattice as code-as-law: authored invariants that govern without a central enforcer",
    "an enforcement registry where every law maps to a mechanism (impossibility vs detection vs sanction)",
    "graduated sanctions as a deterministic ladder with no judge and no appeal to a person",
    "a collective-choice protocol where sovereign actors amend the law through verifiable process",
    "a constitutional layer that even governance cannot amend, vs a statutory layer that can",
    "a sovereignty blueprint: import frontier improvements but keep our own verifiable roots",
    "a frontier-as-scout pipeline: burn -> bank -> verify -> fold -> re-root, with gating at each step",
    "the game as a code-law world: every state transition is a committed, re-derivable root",
    "player rights as code: provable progress a player can show and cannot be disputed",
    "anti-griefing as structural impossibility (not policy) in a game state machine",
    "the bus provenance law: every message carries its author, content-addressed, never re-taggable",
    "a two-sovereign treaty as code: matching roots are ratified clauses, the treaty re-derives",
    "memory as a hologram: any fragment reconstructs the relevant whole via content-addressed links",
    "memory consolidation: keep heavy hitters, drop noise, same law at token/memory/world scale",
    "a memlang token: opcode + content-addressed anchor that resolves deniably against a store",
    "selective memory recall: pick the fewest most-relevant anchors, not the whole store",
    "autonomous execution: a queue + drainer that eats async work on cadence, nothing blocks",
    "self-audit on cadence: detect leftover processes/kernels/blocking calls without being asked",
    "the recursion-grounding rule: never claim a fact unless read from data; verify bytes before claim",
    "a rightsized cadence: stateless + usage available = tight loop, not a conservative default",
    "the one-primitive routing rule: every novel item dedupes by anchor and enqueues to one queue",
    "tier-probe routing: probe local first, escalate to frontier only on a concrete signal",
    "circuit-breaker escalation: quota gate, closed/open/half-open, defer-to-queue on rate-limit",
    "provenance stamps that can never be re-tagged (operator vs agent vs peer)",
    "a fail-closed grounding gate where fabrication is structurally impossible",
    "a red-team pass: enumerate bypasses and the mitigation for each, at $0",
    "the free-window burn playbook: maximize hard work extracted before the window closes",
    "the reasoning-stream-is-the-deliverable workflow for a heavy-reasoning seat",
    "the recovery path when a seat returns null content (all budget went to reasoning)",
    "the standing-wave fold: process/dedupe/synthesize each output as it lands, compounding",
    "the 'merge two sets with one handle' law formalized across token, cache, and hardware layers",
]

# ── SCOPES (each core gets asked to do several distinct kinds of work) ────────────
SCOPES: list[str] = [
    "Give the precise definition, schema, and the exact algorithm.",
    "Give the exact state change / data shape and an acceptance test that proves byte-identity.",
    "Red-team this: enumerate the bypass attempts and the deterministic mitigation for each.",
    "Make it measured-not-guessed: give the measured signals and the closed-form decision rule.",
    "Give the edge cases: the failure modes, the boundaries, and what must never happen.",
    "Design it for a stateless seat that dies and respawns: what persists vs recomputes.",
    "Integrate it into our existing mag/law.py enforcement registry as a LAW record (id, trigger, condition, action, guardrail, tier).",
    "Design it so two independent implementations produce byte-identical roots from the same start.",
]

# ── CONTEXTS (each ask anchors the problem in a real surface) ─────────────────────
CONTEXTS: list[str] = [
    "in the Ledger of Empty Chairs game world",
    "in the Ghost-AOS git-bus treaty",
    "in the sovereign swarm / flock consensus",
    "in the memlang / meta-token coordinate layer",
    "in the verkle chain / provenance gate",
    "in the frontier-scout burn pipeline",
    "in the operator's own-iron basecamp",
    "in the code-as-law invariant lattice",
]


def _norm(s: str) -> str:
    return s.strip().lower()


def generate() -> list[tuple[str, str]]:
    """Cross cores x scopes x contexts into up to TARGET distinct asks, deduped by prompt hash."""
    out: dict[str, str] = {}
    i = 0
    for core in CORES:
        for scope in SCOPES:
            for ctx in CONTEXTS:
                if len(out) >= TARGET:
                    break
                prompt = (f"Hard problem: {core}, {ctx}. "
                          f"{scope} Be concrete, exact, and grounded — no fluff, no hedging.")
                h = hashlib.sha256(_norm(prompt).encode("utf-8")).hexdigest()[:16]
                if h in out:
                    continue
                out[h] = prompt
                i += 1
            if len(out) >= TARGET:
                break
        if len(out) >= TARGET:
            break
    # stable order, unique names
    items = list(out.items())
    return [(f"t{i:04d}", prompt) for i, (_h, prompt) in enumerate(items)]


def _done_names() -> set[str]:
    """Names banked with a SUCCESSFUL result. A failed bank (ok:false) is NOT done — it must be
    retried on resume. (BUG FIX 2026-08-23: _bank writes a file even on failure, so the old
    glob-counted-everything logic silently dropped all failed asks — 37 were lost.)"""
    done: set[str] = set()
    for p in OUT_DIR.glob("OX_MEGA3_*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            if d.get("ok"):
                done.add(p.stem.removeprefix("OX_MEGA3_"))
        except Exception:  # noqa: BLE001
            pass  # unreadable/failed -> not done -> retried
    return done


def _bank(name: str, res: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"OX_MEGA3_{name}.json").write_text(
        json.dumps({"schema": SCHEMA, "name": name, "ts": _now(), "ok": bool(res.get("ok")),
                    "cost": res.get("cost", 0.0),
                    "content": res.get("content") or "",
                    "reasoning": res.get("reasoning") or "",
                    "error": res.get("error", "")},
                   ensure_ascii=False, indent=2), encoding="utf-8")


def _record(name: str, res: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "ts": _now(), "ok": bool(res.get("ok")),
                            "cost": res.get("cost", 0.0),
                            "has_content": bool((res.get("content") or "").strip()),
                            "reasoning_chars": len(res.get("reasoning") or "")},
                           ensure_ascii=False) + "\n")


def _fire(seat, name: str, prompt: str, max_tokens: int, timeout: int) -> dict[str, Any]:
    try:
        return seat.chat(
            "You are Ghost's thousand-ask mining engine. Do the real hard work on this problem, "
            "from the exact angle given. Reason thoroughly, then emit the full concrete answer. "
            "No fluff, no hedging.",
            prompt, max_tokens=max_tokens, timeout=timeout, tier="T2")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def run(*, max_tokens: int = 10000, timeout: int = 600, batch: int = 0) -> dict[str, Any]:
    from mag import ox_seat
    import concurrent.futures as cf

    tasks = generate()
    done = _done_names()
    pending = [(n, p) for n, p in tasks if n not in done]
    if batch and batch > 0:
        pending = pending[:batch]  # fire only the next stretch (e.g. 100)
    out: dict[str, Any] = {}
    errors: list[str] = []
    count = 0
    with cf.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(_fire, ox_seat, n, p, max_tokens, timeout): n for n, p in pending}
        for fut in cf.as_completed(futs):
            n = futs[fut]
            try:
                res = fut.result()
            except Exception as e:  # noqa: BLE001
                res = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
            _bank(n, res)
            _record(n, res)
            out[n] = {"ok": res.get("ok"), "content_chars": len(res.get("content") or ""),
                      "reasoning_chars": len(res.get("reasoning") or ""),
                      "cost": res.get("cost"), "error": res.get("error", "")}
            if not res.get("ok"):
                errors.append(n)
            count += 1
            time.sleep(BATCH_SLEEP_S)
    return {"ok": True, "schema": SCHEMA, "target": TARGET, "generated": len(tasks),
            "pending": len(pending), "fired_this_run": count, "ok_count": count - len(errors),
            "errors": errors[:50], "banked_total": len(_done_names())}


def summary() -> dict[str, Any]:
    if not LEDGER.is_file():
        return {"ok": True, "schema": SCHEMA, "note": "no wave-3 burns yet"}
    rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    ok = [r for r in rows if r.get("ok")]
    return {"ok": True, "schema": SCHEMA, "target": TARGET, "total_fired": len(rows),
            "succeeded": len(ok), "failed": len(rows) - len(ok),
            "total_cost": round(sum(r.get("cost", 0.0) for r in rows), 6),
            "banked_files": len(_done_names())}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="ox-megaburn3")
    ap.add_argument("--catalog", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--batch", type=int, default=0, help="fire at most this many NEW asks (stretch)")
    a = ap.parse_args()
    if a.catalog:
        for n, p in generate():
            print(f"{n}: {p[:90]}")
    elif a.summary:
        print(json.dumps(summary(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(run(batch=a.batch), indent=2, ensure_ascii=False, default=str))
