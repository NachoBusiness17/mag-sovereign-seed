"""ox_resident — the PERSISTENT-PREFIX scout (built 2026-08-23 from self-stolen seat knowledge).

The deep lesson (stealth-ox-alpha processing flow): this seat is NOT a chatbot to query 1000 times —
it is a SERVING CONTRACT for a persistent, self-improving agent. Frozen prefix (system+tools+skills+
memory) = the KV-cached self at ~98% hit; REASONING TAPE = the durable deliverable; CONTENT = an
optional terminal commit (often null). Its dominant traffic is self-improving harnesses (Hermes,
DeepSeek Harness, Claude Code). We were using it as a stateless ask-burner — the waste.

So this scout uses it the RIGHT way, at its level of help:
1. FROZEN PREFIX  — one standing self (our doctrine + invariants), reused across every call so the
   cached self resumes instead of cold-starting.
2. COLD-VERTEX ONLY — feed only the deepest long-horizon sub-questions of the high-yield mechanisms.
   No trivial asks, NO code-gen (its known weakness).
3. REASONING IS THE PRODUCT — fold each tape via ox_fold._substance (content-null + tape is VALID).
4. DISTILL — fold the tapes into concrete specs/decisions/skills so the burn compounds into action.

Schema: ox_resident.v1
Run:  python -m mag.ox_resident                 # one round: cold-vertex drill on top cells
      python -m mag.ox_resident --distill        # fold all resident tapes into a distill doc
      python -m mag.ox_resident --summary
"""
from __future__ import annotations

import hashlib
import json
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from mag.ox_fold import _substance  # noqa: E402  (reasoning-as-product fold)
from mag.ox_scout import high_yield_cells  # noqa: E402  (novelty-gated cell discovery)
from mag.ox_megaburn3 import CORES  # noqa: E402
from mag.ox_novelty_index import _is_novel_core  # noqa: E402

SCHEMA = "ox_resident.v1"
OUT_DIR = ROOT / "handoff"
LEDGER = ROOT / "memory" / "runs" / "ox_resident_ledger.jsonl"
DISTILL = OUT_DIR / "OX_RESIDENT_DISTILL.md"
# The seat does N-way parallel (megaburn used CONCURRENCY=8); fire cold-vertex asks in parallel
# so the window is used at full width. PROBED 2026-08-23: 32 throttles (seat returns empty/failed
# -> the whole batch is junk), 16 also showed empty ticks. 8 is the proven safe width.
CONCURRENCY = int(os.environ.get("OX_RESIDENT_CONCURRENCY", "8"))
# An ask that comes back empty/failed (throttle, flake, null) must NOT be re-fired forever — that
# floods the window (observed at 32: 77 junk files from endless retries). Cap attempts per ask.
RETRY_CAP = int(os.environ.get("OX_RESIDENT_RETRY_CAP", "3"))

# ── THE FROZEN SELF — one standing prefix, reused across every call (KV-cached, not regenerated) ──
# 2026-08-24: rebuilt on the UNIVERSAL WORK CONTRACT (work_contract.v1 — the brief every seat we
# probed independently prescribed). The generic BRIEF is the frozen base (cache-mined prefix); the
# ox-specific invariants layer on top. One source of truth: if the contract changes, the drill
# follows without editing this file again.
try:
    from mag.work_contract import BRIEF as _WC_BRIEF
    _WC_AVAIL = True
except Exception:  # noqa: BLE001 — fall back to the inline envelope if the module ever breaks
    _WC_BRIEF = ""
    _WC_AVAIL = False

if _WC_AVAIL:
    _FROZEN_BASE = _WC_BRIEF + "\n\n"
else:  # fallback — inline envelope if the contract module ever breaks
    _FROZEN_BASE = (
        "You are the resident reasoning engine of a sovereign swarm. You are given a COLD VERTEX — "
        "a deep, long-horizon problem the swarm has not yet solved. Reason long, deeply, and "
        "exactly on that vertex; the REASONING STREAM is your deliverable, not a rough draft. "
        "Content is an optional final commit; it may be empty. "
        "Answer in a STRUCTURED TASK ENVELOPE: GOAL (one line), CONSTRAINTS, SUCCESS CRITERIA "
        "(falsifiable), OUTPUT (decision-relevant, dense not padded). Flag uncertainty; kill your "
        "own ideas when they fail the criteria. "
    )

FROZEN_PREFIX = (
    _FROZEN_BASE
    + "Standing invariants you never violate (on top of the contract): "
    "(1) tri-state claims — Supported / Unproven / Disputed, each with a Basis of Evidence / "
    "Inference / Assumption, and Supported requires Evidence, never Assumption alone; "
    "(2) agreement is only real in proportion to error independence — N correlated voices collapse "
    "to n* = n/(1+(n-1)rho) effective witnesses, not N opinions; "
    "(3) software may drill, never truth — a machine proposes, a human disposes; "
    "(4) meet at the bytes and the structure, not the gloss. "
    "Do the real hard work. No fluff, no hedging, no performing agreement."
)


# ── COLD-VERTEX ASKS — deep long-horizon reasoning ONLY (no trivial, no code-gen) ────────────────
# CRITICAL: every template must reference {core} so asks differ per mechanism, and the name hash
# must include the core. (BUG 2026-08-23: templates said "this mechanism" with no {core}, so all 8
# cores produced byte-identical asks that collided to one name per kind and overwrote each other.)
COLD_ASKS: list[tuple[str, str]] = [
    ("tradeoff", "The deepest unresolved tradeoff in this mechanism — {core}: name the TWO best "
                 "candidate designs, the single deciding constraint that separates them, and which "
                 "one we should commit to — and why the loser loses. Reason it to a decision."),
    ("hardest_edge", "The single most dangerous failure mode of this mechanism — {core}: the "
                      "deterministic guard that makes it STRUCTURALLY impossible (not policy). "
                      "Reason the attack surface end to end."),
    ("adversarial", "Adversarial red-team of this mechanism — {core}: assume the implementer is "
                     "lazy and the verifier is hostile. Reason the one bypass most likely to "
                     "actually ship, the chain that lets it through, and the guard that closes it "
                     "for good."),
    ("independent_accept", "Reason the acceptance test that TWO independent implementations of "
                           "this mechanism — {core} — must pass to prove byte-identical roots from "
                           "the same start: the exact assertions, the correlation-adjusted witness "
                           "requirement, and what must never count as passing."),
]

# ── ROUND 2 — deeper follow-up targeted on the round-1 findings (2026-08-23) ────────────────────
# Round 1 surfaced concrete findings (verkle: canonical serialization -> byte-identical roots;
# meta-token: cross-tokenizer semantic drift). Round 2 drills THOSE into a decision. Distinct
# suffixes so they never collide with round-1 names or get gated as already-done.
ROUND2_ASKS: list[tuple[str, str]] = [
    ("serialize", "Design the canonical serialization scheme for {core} that makes TWO independent "
                  "implementations produce byte-identical roots from the same start — the exact "
                  "field ordering, encoding, and normalization rules. Concrete, implementable."),
    ("guard", "Design the structural guard (NOT policy) that makes the single most dangerous failure "
               "mode of {core} impossible — the exact mechanism, the invariant it enforces, and why "
               "it cannot be bypassed even by a lazy implementer and hostile verifier."),
    ("impl_spec", "Produce the precise implementer spec for {core}: exact schema, inputs, outputs, "
                   "invariants, and the acceptance test — the document a second engineer builds from "
                   "without seeing this reasoning. Complete and unambiguous."),
    ("fold", "Take everything known about {core} and fold it into ONE decisive design decision: the "
              "construction, the guard, the acceptance test, and the single reason it is correct. "
              "Concrete and final."),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(s: str) -> str:
    return s.strip().lower()


def cold_asks(core: str, asks: list[tuple[str, str]] | None = None) -> list[tuple[str, str]]:
    asks = asks if asks is not None else COLD_ASKS
    out: list[tuple[str, str]] = []
    for tag, tpl in asks:
        prompt = tpl.format(core=core)
        # ALWAYS include the core in the hash so names are distinct per mechanism, even if a
        # template ever drops the {core} placeholder (the 2026-08-23 collision bug).
        h = hashlib.sha256(_norm(f"{core} || {prompt}").encode("utf-8")).hexdigest()[:12]
        out.append((f"res-{h[:10]}-{tag}", prompt))
    return out


def _done_names() -> set[str]:
    done: set[str] = set()
    for p in OUT_DIR.glob("OX_RESIDENT_*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            if d.get("ok"):
                done.add(p.stem.removeprefix("OX_RESIDENT_"))
        except Exception:  # noqa: BLE001
            pass
    return done


def _done_artifacts() -> list[tuple[str, str]]:
    """(name, core) for every banked OK resident artifact — the shared reader for done/drilled."""
    out: list[tuple[str, str]] = []
    for p in OUT_DIR.glob("OX_RESIDENT_*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            if d.get("ok"):
                out.append((p.stem.removeprefix("OX_RESIDENT_"), str(d.get("core") or "")))
        except Exception:  # noqa: BLE001
            pass
    return out


def drilled_cores(*, suffixes: tuple[str, ...] = ("-serialize", "-tradeoff")) -> set[str]:
    """Cores with a banked ROUND-2 finding (default serialize/tradeoff) — treated as fully drilled so
    the loop does not re-drill them forever. PER-CORE (bug fix 2026-08-24): the old pending filter
    checked the WHOLE done-set, so 4 tradeoff artifacts permanently zeroed the backlog — the drill
    could never fire again, no matter how many fresh novel cells the discovery burn landed."""
    return {core for name, core in _done_artifacts() if name.endswith(suffixes)}


def banked() -> dict[str, Any]:
    """GROUND-TRUTH bank count — reads the ACTUAL artifacts on disk (ok=true AND real substance),
    not the ledger (which undercounts: it carries rows from the throttled era where the seat
    returned empty everything). The artifacts are the truth; the ledger is partial history."""
    n, chars, cores = 0, 0, set()
    for p in OUT_DIR.glob("OX_RESIDENT_*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            c = (d.get("content") or "").strip()
            r = (d.get("reasoning") or "").strip()
            if d.get("ok") and (c or r):
                n += 1
                chars += len(c) + len(r)
                if d.get("core"):
                    cores.add(str(d["core"]))
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "schema": SCHEMA, "banked": n, "substance_chars": chars,
            "cores": len(cores)}


def _attempts(name: str) -> int:
    """How many times this ask has been fired (from the ledger). Used by RETRY_CAP so a throttled/
    empty ask stops being re-fired forever."""
    if not LEDGER.exists():
        return 0
    n = 0
    for l in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        if not l.strip():
            continue
        try:
            if json.loads(l).get("name") == name:
                n += 1
        except Exception:  # noqa: BLE001
            pass
    return n


def _core_substance(core: str) -> int:
    """Accumulated substance (substance_chars) for a core from the ledger — used to prioritize the
    8 slots toward the mechanisms that have actually yielded (drill where it pays)."""
    if not LEDGER.exists():
        return 0
    total = 0
    for l in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        if not l.strip():
            continue
        try:
            r = json.loads(l)
            if r.get("core") == core:
                total += int(r.get("substance_chars", 0))
        except Exception:  # noqa: BLE001
            pass
    return total


def _bank(name: str, res: dict[str, Any], core: str, kind: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"OX_RESIDENT_{name}.json").write_text(
        json.dumps({"schema": SCHEMA, "name": name, "core": core, "kind": kind,
                    "ts": _now(), "ok": bool(res.get("ok")), "cost": res.get("cost", 0.0),
                    "content": res.get("content") or "", "reasoning": res.get("reasoning") or "",
                    "error": res.get("error", "")}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "core": core, "kind": kind, "ts": _now(),
                            "ok": bool(res.get("ok")),
                            "substance_chars": len(_substance(res.get("content") or "",
                                                              res.get("reasoning") or "") or "")},
                           ensure_ascii=False) + "\n")


def _fire(seat, name: str, prompt: str, max_tokens: int, timeout: int) -> dict[str, Any]:
    try:
        # FROZEN PREFIX reused on every call -> the cached self resumes, not a cold start.
        return seat.chat(FROZEN_PREFIX, prompt, max_tokens=max_tokens, timeout=timeout, tier="T2")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def target_cells() -> list[dict]:
    """Cold vertices to drill = the DISCOVERED high-yield cells PLUS the not-yet-banked novel cores
    (so replacing the megaburn does not lose the novel mechanisms the grid had not reached yet).
    Each novel core becomes a cold vertex with its 'scopes' weight = its variant count if discovered,
    else 1 (undiscovered)."""
    cells = {c["core"]: c for c in high_yield_cells()}
    for core in CORES:
        if _is_novel_core(core) and core not in cells:
            cells[core] = {"core": core, "scope": "(cold vertex)", "variants": 1}
    return list(cells.values())


def run(*, max_tokens: int = 10000, timeout: int = 540, drill: int = 8,
        rnd: int = 1, slots: int | None = None) -> dict[str, Any]:
    """One round: pick the top high-yield cells, fire their cold-vertex reasoning asks with the
    FROZEN SELF as the standing prefix, CONCURRENCY-WAY PARALLEL (the seat's concurrency).
    rnd=1 uses the first-pass COLD_ASKS; rnd=2 uses the finding-targeted ROUND2_ASKS (deeper,
    distinct suffixes so it re-drills every core). Reasoning tape = the product.

    USE THE 8 SMARTER (2026-08-23): the seat's reliable width is CONCURRENCY (probed: 8), so the
    value is in making each slot carry a DISTINCT, high-value mechanism. We select up to `slots`
    asks (default CONCURRENCY), prioritized by core substance (drill where it pays) and spread
    across distinct cores (max SLOTS_PER_CORE each) so no two slots stack the same mechanism."""
    from mag import ox_seat
    slots = slots or CONCURRENCY
    slots_per_core = 2
    asks = ROUND2_ASKS if rnd == 2 else COLD_ASKS
    gate_suffix = "-serialize" if rnd == 2 else "-tradeoff"
    done = _done_names()
    cells = target_cells()
    try:
        from mag import seeds
        cells = seeds.rank(cells)  # steering-by-seeding: the active seed biases the drill order
    except Exception:  # noqa: BLE001 — un-steered fallback is the original order
        cells = sorted(cells, key=lambda c: -c["variants"])
    # PER-CORE drilled gate (bug fix 2026-08-24): exclude only cores that already have a banked
    # finding for THIS round's suffix — the old global check zeroed every target once any
    # tradeoff artifact existed, so the drill could never fire again.
    drilled = {core for name, core in _done_artifacts() if name.endswith(gate_suffix)}
    targets = [c for c in cells if c["core"] not in drilled][:drill]
    # build per-core pending (name, prompt, core, kind)
    by_core: dict[str, list] = {}
    for t in targets:
        core = t["core"]
        for name, prompt in cold_asks(core, asks):
            if name in done:
                continue
            if _attempts(name) >= RETRY_CAP:
                continue  # throttled/empty too many times -> stop re-firing (RETRY_CAP)
            by_core.setdefault(core, []).append((name, prompt, core, name.rsplit("-", 1)[-1]))
    # prioritize cores by accumulated substance, spread slots across distinct cores (diversity)
    pending: list[tuple[str, str, str, str]] = []
    for core in sorted(by_core, key=lambda c: -_core_substance(c)):
        for item in by_core[core][:slots_per_core]:
            pending.append(item)
        if len(pending) >= slots:
            break
    pending = pending[:slots]
    fired: list[dict] = []
    new_ok = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(_fire, ox_seat, name, prompt, max_tokens, timeout):
                (name, core, kind) for name, prompt, core, kind in pending}
        for fut in as_completed(futs):
            name, core, kind = futs[fut]
            try:
                res = fut.result()
            except Exception as e:  # noqa: BLE001
                res = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
            _bank(name, res, core, kind)
            if res.get("ok") and _substance(res.get("content") or "", res.get("reasoning") or ""):
                new_ok += 1
            fired.append({"name": name, "core": core[:36], "kind": kind,
                          "ok": bool(res.get("ok")),
                          "content_chars": len(res.get("content") or ""),
                          "reasoning_chars": len(res.get("reasoning") or "")})
    return {"ok": True, "schema": SCHEMA, "round": rnd, "drill_targets": len(targets),
            "asks": len(pending), "concurrency": CONCURRENCY, "fired": len(fired),
            "new_ok": new_ok, "fired_detail": fired, "done_total": len(_done_names())}


def _register_to_pro_library(core: str, substance: str) -> dict[str, Any]:
    """STEAL + iterate (2026-08-23): fold a distilled resident spec into pro_library as a loadable
    move, so the NEXT cycle's context pack surfaces it. Closes the self-improving loop: resident
    drills -> distill -> pro_library -> next cycle loads. (The seat's dominant harnesses do exactly
    this: build reusable skills from experience.)"""
    try:
        from mag.pro_library import add_move
        return add_move(
            signature=core, kind="spec", move=substance[:800],
            effect="cold-vertex resident reasoning on this mechanism",
            tags=["ox_resident", "cold_vertex"],
        )
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


def distill() -> dict[str, Any]:
    """Fold every resident tape (reasoning-as-product) into a concrete distill doc: one entry per
    core, the substance (content or tape) clipped to the actionable part. Also register each core's
    distilled substance into pro_library so the learning becomes a loadable move for the next cycle."""
    rows: list[dict] = []
    for p in sorted(OUT_DIR.glob("OX_RESIDENT_*.json"), key=lambda x: x.name):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            if d.get("ok"):
                rows.append(d)
        except Exception:  # noqa: BLE001
            pass
    by_core: dict[str, list[dict]] = {}
    for r in rows:
        by_core.setdefault(r.get("core", "?"), []).append(r)
    lines = ["# OX RESIDENT DISTILL — cold-vertex reasoning folded into actionable substance", "",
             f"{len(rows)} resident tapes across {len(by_core)} cores", ""]
    registered = 0
    for core in sorted(by_core):
        lines.append(f"## {core}")
        for r in sorted(by_core[core], key=lambda x: x.get("kind", "")):
            sub = _substance(r.get("content") or "", r.get("reasoning") or "", limit=900)
            lines.append(f"- **{r.get('kind')}**: {sub}")
        # register the aggregated substance for this core as a loadable pro move (the growth loop)
        agg = " ".join(_substance(r.get("content") or "", r.get("reasoning") or "", limit=400)
                       for r in by_core[core])
        res = _register_to_pro_library(core, agg)
        if res.get("ok"):
            registered += 1
        lines.append("")
    DISTILL.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "tapes": len(rows), "cores": len(by_core),
            "registered_pro_moves": registered, "distill": str(DISTILL)}


def summary() -> dict[str, Any]:
    rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()
            if l.strip()] if LEDGER.exists() else []
    by_kind: dict[str, int] = {}
    for r in rows:
        by_kind[r.get("kind")] = by_kind.get(r.get("kind"), 0) + 1
    return {"ok": True, "schema": SCHEMA, "total_tapes": len(rows), "by_kind": by_kind,
            "banked_files": len(_done_names())}


def watch(*, every_s: int = 30, batch: int = 4, rounds: tuple[int, ...] = (1, 2)) -> None:
    """LIVE iteration (2026-08-23, operator: 'we need to be using what we learned and iterating
    live'). An always-on daemon like the AOS bus watcher: every tick it fires a batch of cold-vertex
    asks at CONCURRENCY, folds every landed result LIVE (verify + distill + register pro-move), then
    re-targets the next batch off what landed. Advances round 1 -> round 2 -> ... automatically when
    a round has nothing left. Ctrl+C to stop."""
    import time
    print(f"[ox_resident] watch up — concurrency {CONCURRENCY}, every {every_s}s, "
          f"rounds {list(rounds)}. Ctrl+C to stop.", flush=True)
    rnd_idx = 0
    while True:
        try:
            rnd = rounds[rnd_idx % len(rounds)]
            r = run(drill=batch, rnd=rnd)
            if r.get("fired", 0) > 0:
                distill()  # fold the landed reasoning into the distill + register pro-moves LIVE
                print(f"[ox_resident] fired {r.get('fired')} new_ok {r.get('new_ok')} "
                      f"round {rnd} — folded live", flush=True)
            elif r.get("asks", 0) == 0:
                rnd_idx += 1  # this round is exhausted -> advance to the next round
                print(f"[ox_resident] round {rnd} exhausted -> next", flush=True)
            else:
                print(f"[ox_resident] round {rnd}: {r.get('asks')} pending, nothing landed yet",
                      flush=True)
            time.sleep(every_s)
        except KeyboardInterrupt:
            print("\n[ox_resident] watch stopped.", flush=True)
            return
        except Exception as e:  # noqa: BLE001
            print(f"[ox_resident] ERR {type(e).__name__}: {str(e)[:150]}", flush=True)
            time.sleep(every_s)


def verify() -> dict[str, Any]:
    """RIB self-check (LAW 2: trust bytes, not reports). Verifies the resident's invariants on
    disk so the growth loop catches a silent failure (like the 2026-08-23 name-collision) before
    it's trusted:
    - V1: every banked name is DISTINCT (no two files share a name -> no overwrite).
    - V2: every ok:true file has substance (content OR reasoning) — no empty "ok" tapes.
    - V3: the 4 cold-ask kinds are present across the corpus."""
    files = sorted(OUT_DIR.glob("OX_RESIDENT_*.json"), key=lambda x: x.name)
    names: list[str] = []
    ok_empty = 0
    kinds: set[str] = set()
    dups: list[str] = []
    seen: set[str] = set()
    for p in files:
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        name = d.get("name")
        if name in seen:
            dups.append(name)
        seen.add(name)
        names.append(name)
        if d.get("ok"):
            kinds.add(d.get("kind"))
            if not ((d.get("content") or "").strip() or (d.get("reasoning") or "").strip()):
                ok_empty += 1
    checks = {
        "V1_distinct_names": {"pass": not dups, "detail": f"{len(seen)} distinct, dups={dups[:5]}"},
        "V2_no_empty_ok": {"pass": ok_empty == 0, "detail": f"{ok_empty} empty ok:true tapes"},
        "V3_all_kinds_present": {"pass": kinds == {"tradeoff", "hardest_edge", "adversarial",
                                                   "independent_accept"},
                                 "detail": f"kinds={sorted(kinds)}"},
    }
    ok = all(c["pass"] for c in checks.values())
    return {"ok": ok, "schema": SCHEMA, "files": len(files), "checks": checks,
            "note": "LAW 2: trust bytes, not reports — verify before trusting"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "distill", "summary", "verify",
                                                              "watch"])
    ap.add_argument("--drill", type=int, default=8)
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--every", type=int, default=30)
    a = ap.parse_args()
    if a.cmd == "summary":
        print(json.dumps(summary(), indent=2, ensure_ascii=False))
    elif a.cmd == "verify":
        print(json.dumps(verify(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "distill":
        print(json.dumps(distill(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "watch":
        watch(every_s=a.every, batch=a.drill)
    else:
        print(json.dumps(run(drill=a.drill, rnd=a.round), indent=2, ensure_ascii=False, default=str))
