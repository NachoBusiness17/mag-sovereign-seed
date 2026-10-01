"""invariant — make the session prefix STABLE RELIABLY.

The operator's ask: "how do we make them stable reliably?" — referring to the
frozen-prefix / session-invariant that must stay byte-identical so the prompt
cache HITS on every reply (50x: $0.0028/M hit vs $0.14/M miss).

WHY the current preamble is NOT stable: `session_route.preamble()` mixes the
STABLE parts (SESSION_SEED.md + the agent-state formatting block, both
byte-deterministic per state) with VOLATILE parts (the `learned` block — live
failure-KB remedies + growing skill-ledger case law, plus the model hint). As the
ledger grows, `learned` re-renders differently every session → the prefix bytes
change → cache miss → the 50x evaporates.

THE FIX (this module): SEPARATE, PIN, VERIFY.
  1. STABLE prefix  = seed + formatting. Deterministic per state. Never volatile.
  2. VOLATILE tail  = learned + model_hint + the ask. Goes AFTER a delimiter so
     the cache still hits on the prefix; only the tail is a fresh miss.
  3. PIN:  spec_gate.freeze(SEED)  +  verkle-anchor the prefix sha (provable).
  4. VERIFY: before every session, check() that the prefix bytes match the pinned
     sha AND the seed file hasn't drifted → stable:true. If drifted, DON'T ship
     drifted bytes — re-freeze or escalate (spec_gate's "trust bytes" law).

Composes EXISTING primitives (spec_gate freeze/check + verkle_knot.append_verkle_knot
+ session_route.read_seed/formatting_block/learned_block). Deterministic, $0, no LLM.

CLI:  python -m mag.invariant freeze [--state X] [--label L]
      python -m mag.invariant check  [--state X]
      python -m mag.invariant stable [--state X]        (print only the stable prefix)
      python -m mag.invariant preamble "<goal>" [--state X] [--with-model]
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

# The marker that separates the byte-stable invariant from the volatile tail.
# Fixed bytes — never changes — so the stable prefix is cache-shareable as-is.
DELIM = "<<<STABLE-INVARIANT-END>>>"

STATE_DIR = ROOT / "memory" / "runs" / "invariant"
STATE_FILE = STATE_DIR / "state.json"
SCHEMA = "invariant.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.is_file():
        return {"schema": SCHEMA, "pins": {}}
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {"schema": SCHEMA, "pins": {}}
    except Exception:
        return {"schema": SCHEMA, "pins": {}}


def _save_state(d: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def _seed_path() -> Path:
    return ROOT / "state" / "SESSION_SEED.md"


def stable_prefix(agent_state: str = "coding-agent") -> str:
    """The byte-stable invariant prefix for a state: seed + formatting block.

    Deliberately EXCLUDES the volatile `learned` block and any model hint — those
    live in the tail. Deterministic per state: same state → same bytes every time.
    """
    from mag import session_route

    seed = session_route.read_seed()
    fmt = session_route.formatting_block((agent_state or "").strip().lower() or "coding-agent")
    blocks: list[str] = []
    if fmt:
        blocks.append(fmt)
    if seed:
        blocks.append(f"## Session seed (read before acting — the routing invariant)\n{seed}")
    return "\n\n".join(blocks).strip()


def _prefix_sha(agent_state: str) -> str:
    return hashlib.sha256(stable_prefix(agent_state).encode("utf-8")).hexdigest()


def freeze(agent_state: str = "coding-agent", *, label: str = "") -> dict[str, Any]:
    """Pin the stable prefix: spec_gate the seed + verkle-anchor the prefix sha."""
    st = (agent_state or "").strip().lower() or "coding-agent"
    prefix = stable_prefix(st)
    if not prefix:
        return {"schema": SCHEMA, "ok": False, "error": "empty stable prefix (seed missing?)"}

    sha = _prefix_sha(st)

    # 1) byte-pin the seed file so drift is caught before we ever ship it.
    sg = {}
    try:
        from mag import spec_gate
        sg = spec_gate.freeze(_seed_path(), label=f"invariant:{st}")
    except Exception as e:
        sg = {"ok": False, "error": str(e)[:120]}

    # 2) verkle-anchor the prefix sha so stability is provable on the chain.
    vk = {}
    try:
        from mag import verkle_knot
        vk = verkle_knot.append_verkle_knot({
            "session_id": f"invariant:{st}",
            "dominant_theme": f"invariant-{st}",
            "chord_commitment": sha,
            "dossier_commit": sha,
            "summary": f"frozen session invariant prefix for {st} (sha {sha[:12]})",
            "purpose": "session_invariant_pin",
        })
    except Exception as e:
        vk = {"ok": False, "error": str(e)[:120]}

    state = _load_state()
    state.setdefault("pins", {})[st] = {
        "sha": sha,
        "prefix_len": len(prefix),
        "label": label or f"invariant:{st}",
        "seed_spec_ok": bool(sg.get("ok")),
        "seed_sha": sg.get("sha"),
        "verkle_ok": bool(vk.get("ok")),
        "verkle_root": vk.get("verkle_root"),
        "ts": _now(),
    }
    _save_state(state)

    return {
        "schema": SCHEMA, "ok": True, "state": st, "sha": sha,
        "prefix_len": len(prefix), "seed_spec_ok": bool(sg.get("ok")),
        "verkle_ok": bool(vk.get("ok")), "verkle_root": vk.get("verkle_root"),
        "note": "stable prefix pinned (spec_gate + verkle). Any byte drift now trips check().",
    }


def check(agent_state: str = "coding-agent") -> dict[str, Any]:
    """Is the current prefix byte-identical to the pinned invariant? stable:true = cache-safe."""
    st = (agent_state or "").strip().lower() or "coding-agent"
    pins = _load_state().get("pins") or {}
    pin = pins.get(st)
    if not pin:
        return {"schema": SCHEMA, "ok": False, "stable": False, "state": st,
                "error": f"no invariant pinned for '{st}' — run freeze first"}

    cur_sha = _prefix_sha(st)
    stable = cur_sha == pin.get("sha")

    # seed-file drift (independent of assembled prefix, catches source edits)
    sg = {}
    try:
        from mag import spec_gate
        sg = spec_gate.check(_seed_path())
    except Exception as e:
        sg = {"error": str(e)[:120]}
    seed_ok = bool(sg.get("ok"))

    return {
        "schema": SCHEMA, "ok": True, "state": st,
        "stable": stable and seed_ok,
        "prefix_stable": stable,
        "seed_stable": seed_ok,
        "pinned_sha": pin.get("sha"),
        "current_sha": cur_sha,
        "seed_drift": (not seed_ok) and (sg.get("expected_sha") is not None),
        "prefix_len": pin.get("prefix_len"),
        "pinned_ts": pin.get("ts"),
        "verkle_root": pin.get("verkle_root"),
        "action": "ship" if (stable and seed_ok) else "RE-FREEZE before shipping (drifted bytes break the cache)",
    }


# ── INSTRUCTION-LAYER EPOCH PIN (2026-08-26) ───────────────────────────────────────────────
# The session-invariant pins above cover SESSION_SEED + formatting — the SESSION prefix.
# The INSTRUCTION layer (work_contract.BRIEF + rib_cache.FROZEN_RIB + the corrections skill)
# is the other cache-mined prefix every seat folds in, and it was UNPINNED — a silent edit
# changed the fleet-wide prefix with no gate and no alarm. Pin it: any change now must be a
# deliberate, visible epoch event (freeze_instructions with a label), and check_instructions
# flags drift. (Found by the verification seat 2026-08-26: "the guard doesn't guard the thing
# that just changed.")
INSTRUCTION_SOURCES: list[tuple[str, object]] = [
    ("work_contract.BRIEF",
     lambda: __import__("mag.work_contract", fromlist=["BRIEF"]).BRIEF),
    ("rib_cache.FROZEN_RIB",
     lambda: __import__("mag.rib_cache", fromlist=["FROZEN_RIB"]).FROZEN_RIB),
    ("operator-corrections.SKILL",
     lambda: (ROOT / ".agents" / "skills" / "operator-corrections" / "SKILL.md")
     .read_text(encoding="utf-8", errors="replace")),
]


def instruction_sha() -> str:
    """Content hash of the instruction layer — BRIEF + FROZEN_RIB + corrections skill."""
    h = hashlib.sha256()
    for name, src in INSTRUCTION_SOURCES:
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        try:
            h.update(str(src()).encode("utf-8"))
        except Exception as e:  # noqa: BLE001
            h.update(f"<unread:{e}>".encode("utf-8"))
    return h.hexdigest()


def freeze_instructions(*, label: str = "") -> dict[str, Any]:
    """Pin the instruction layer as a deliberate epoch. Any future byte drift trips check()."""
    st = "instructions"
    cur = instruction_sha()
    state = _load_state()
    state.setdefault("pins", {})[st] = {
        "sha": cur, "ts": _now(), "label": label or "instruction-layer epoch",
        "sources": [n for n, _ in INSTRUCTION_SOURCES],
    }
    _save_state(state)
    return {"ok": True, "schema": SCHEMA, "pinned": st, "sha": cur[:16],
            "ts": state["pins"][st]["ts"], "label": state["pins"][st]["label"]}


def check_instructions() -> dict[str, Any]:
    """Is the instruction layer byte-identical to its pinned epoch? stable:true = cache-safe."""
    st = "instructions"
    pins = _load_state().get("pins") or {}
    pin = pins.get(st)
    if not pin:
        return {"ok": True, "schema": SCHEMA, "stable": None,
                "error": "no instruction-layer pin — run freeze_instructions",
                "action": "PIN (deliberate epoch required)"}
    cur = instruction_sha()
    stable = cur == pin.get("sha")
    return {"ok": True, "schema": SCHEMA, "stable": stable,
            "epoch": pin.get("ts"), "label": pin.get("label"),
            "pinned_sha": pin.get("sha")[:16], "cur_sha": cur[:16],
            "sources": pin.get("sources"),
            "action": "ship" if stable else
                      "DRIFT — instruction layer changed; deliberate epoch required "
                      "(freeze_instructions --label '...')"}


def tail(goal: str = "", agent_state: str = "coding-agent", *, with_model: bool = False) -> str:
    """The volatile part — learned case law + model hint. Goes AFTER the delimiter."""
    from mag import session_route

    st = (agent_state or "").strip().lower() or "coding-agent"
    parts: list[str] = []
    learned = session_route.learned_block(goal)
    if learned:
        parts.append(learned)
    if with_model and (goal or "").strip():
        try:
            from mag.self_drive import plan
            p = plan(goal, agent_state=st)
            if p.get("ok"):
                parts.append(f"## Routing hint\nmodel={p.get('model')} shape={p.get('model_shape')}")
        except Exception:
            pass
    return "\n\n".join(parts).strip()


def preamble(goal: str = "", agent_state: str = "coding-agent", *, with_model: bool = False) -> dict[str, Any]:
    """The stable invariant + volatile tail, clearly separated.

    Returns stable_prefix + DELIM + tail. Only the tail varies per ask — the
    prefix stays byte-identical so the cache hits on it every reply.
    """
    st = (agent_state or "").strip().lower() or "coding-agent"
    prefix = stable_prefix(st)
    body = tail(goal, st, with_model=with_model)
    full = prefix + ("\n\n" + DELIM + "\n\n" + body if body else "")
    return {
        "schema": SCHEMA, "state": st, "prefix": prefix, "tail": body,
        "delim": DELIM, "text": full, "prefix_len": len(prefix), "tail_len": len(body),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "check"
    rest = argv[1:]
    state = "coding-agent"
    label = ""
    with_model = False
    goal = ""
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--state" and i + 1 < len(rest):
            state = rest[i + 1]; i += 2; continue
        if a == "--label" and i + 1 < len(rest):
            label = rest[i + 1]; i += 2; continue
        if a == "--with-model":
            with_model = True; i += 1; continue
        goal = " ".join(rest[i:]); break
    if cmd == "freeze":
        print(json.dumps(freeze(state, label=label), indent=2, ensure_ascii=False))
    elif cmd == "freeze-instructions":
        print(json.dumps(freeze_instructions(label=label), indent=2, ensure_ascii=False))
    elif cmd == "check-instructions":
        print(json.dumps(check_instructions(), indent=2, ensure_ascii=False))
    elif cmd == "stable":
        print(stable_prefix(state))
    elif cmd == "preamble":
        print(json.dumps(preamble(goal, state, with_model=with_model), indent=2, ensure_ascii=False))
    else:  # check
        print(json.dumps(check(state), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
