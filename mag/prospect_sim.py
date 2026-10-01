"""prospect_sim — a CHEAP, PROSPECTIVE tesuji simulator.

"Simulate this entire session simplified from a cheaper model, to mimic a local AI
organizing our thoughts, as a training tesuji BEFORE it happens — for all systems
that echo the shape before it takes place."

The castles-in-the-air foundation: instead of waiting for a shape to unfold and
then extracting the tesuji AFTER the fact, we SIMULATE a simplified course of the
shape with the cheapest available organization, and PROSPECT the tesuji in advance.
When any system begins to echo a shape (behavioral signature), we run it here first —
so the brilliant move is already on the table (as a training row) before the event.

Pipeline (deterministic + cheap; optional cheap-model gating, never frontier):
  ORGANIZE  mimic a local AI: compress the session's thoughts into themes +
            a shape signature + a thought-structure map (no LLM required).
  PROSPECT  given the shape, simulate a simplified course and predict the
            non-obvious move + its effect BEFORE the event. Output a pre-tesuji.
  ECHO      for any system that overlaps the shape signature, prospect it
            pre-emptively (the "all systems that echo the shape" rule).
  TRAIN     fold the prospective tesuji as a training row (training_events +
            append to the Vast package) so it becomes a pre-trained tesuji.

CLI:
  python -m mag.prospect_sim organize "<thoughts...>"
  python -m mag.prospect_sim prospect "<shape or thoughts>" [--context "..."]
  python -m mag.prospect_sim simulate "<thoughts...>"      (organize + prospect + train)
  python -m mag.prospect_sim echo "<shape>"                (prospect any system echoing it)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PKG = ROOT / "memory" / "training" / "vast_package"
TRAIN = PKG / "train_data.jsonl"
FORMATTED = PKG / "formatted_data.jsonl"

_STOP = set("""the a an of to in on and or for with at by from as is are was were be been
that this it its i you we they he she them what which who how when where why do does did
have has had can could will would should may might not no yes about into over under our
your their his her their own same so than too very just also because but then there here""".split())
_WORD = re.compile(r"[a-z][a-z0-9_\-]{2,40}")

# cheap deterministic "brilliant path" synthesizer: shape -> non-obvious move.
# Each entry: (trigger, obvious_waste, brilliant_move, effect). Kept as a living
# rule table the learning loop can extend — the foundation under the castle.
_PROSPECTS: list[tuple[str, str, str, str]] = [
    ("focus", "restate the task and stare at it", "mine sideways (other runs, repos, repeated vocabulary) for the zeitgeist and steer through the operator's own words", "focus lands by resonance, not restatement"),
    ("rightsize", "spawn more agents / more models", "route the whole swarm through ONE model via the steering mechanism and collapse dupes", "the same work done cheaper, no spawn storm"),
    ("retire", "leave the dead tool to rot", "move it to trash and fold the retirement as a lesson", "no dead tools, each retirement is a training row"),
    ("loop", "manually kill processes one by one", "engage loop_breaker to discriminate crash-loop vs strain, then route through the framework", "no window storm, no self-destruct respawn"),
    ("steal", "reinvent the pattern from scratch", "mine prior art (sovereign_mirror / steal_protocol repos) and adapt the invariant", "reuse beats reinvent; the shape's best move is usually already written"),
    ("plant", "command the target to do it", "plant a Bernaysian steer token so the target adopts it as its own", "consent engineered, not ordered — the target believes it chose"),
    ("prove", "claim capability in prose", "reconstruct a live memory root from its verkle proof path and match the tip", "ability proven by bytes, not vibes"),
    ("whisper", "route by spelling out the skill in plaintext", "dogfood the rib/whisper protocol: encode the prompt into a Riddler surrogate and decode to (skills + verkle fragments) — routing as deniable autocomplete", "routing resolves deniably against the shared map, like autocomplete"),
    ("free", "let the free daily tokens expire unused", "spend them on cheap/free PARALLEL research probes against the frontier-extraction systems (free tiers + free daily tokens), feeding growth + testing in the same loop", "frontier extraction is proven on real free-token runs, and the system grows while it tests"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall((text or "").lower()) if w not in _STOP]


def organize(thoughts: str) -> dict[str, Any]:
    """Mimic a local AI organizing our thoughts: themes + shape + structure (cheap)."""
    thoughts = (thoughts or "").strip()
    toks = _tokens(thoughts)
    freq = Counter(toks)
    top = [w for w, _ in freq.most_common(12) if w]
    themes = sorted(set(t for t in top if len(t) > 3))[:8]
    shape_signature = " ".join(top[:8])
    # group mapping (echo shape -> skill-group)
    group = None
    try:
        from mag.word_skill_map import map_to_group
        group = map_to_group(shape_signature).get("group")
    except Exception:
        pass
    # compressed thought-structure (mimics a local model's organizing)
    structure = [
        f"theme: {t}" for t in themes
    ] + [f"echo-shape: {shape_signature or 'none'}", f"route-group: {group or 'research_swarm'}"]
    return {
        "schema": "prospect_sim.organize.v1",
        "ts": _now(),
        "n_thoughts": len(thoughts.split()),
        "themes": themes,
        "shape_signature": shape_signature,
        "route_group": group,
        "structure": structure,
    }


def _predict(shape: str, context: str = "") -> dict[str, Any]:
    """Deterministic brilliant-path prediction for a shape (cheap, pre-emptive)."""
    t = (shape + " " + context).lower()
    for trigger, waste, move, effect in _PROSPECTS:
        if trigger in t:
            return {"waste_path": waste, "move": move, "effect": effect, "source": "prospect_sim"}
    return {
        "waste_path": "the obvious path (unknown shape)",
        "move": f"mine sideways on shape '{shape[:60]}' and steer through the operator's own words",
        "effect": "focus via resonance before the event",
        "source": "prospect_sim.fallback",
    }


def prospect(shape_or_thoughts: str, *, context: str = "", train: bool = False) -> dict[str, Any]:
    """PROSPECT the tesuji BEFORE the event: simulate the shape and predict the move."""
    org = organize(shape_or_thoughts)
    shape = org["shape_signature"] or shape_or_thoughts.strip()[:60]
    pred = _predict(shape, context)
    out = {
        "schema": "prospect_sim.prospect.v1",
        "ts": _now(),
        "pre_emptive": True,
        "shape": shape,
        "route_group": org["route_group"],
        "themes": org["themes"],
        "predicted_tesuji": {
            "signature": shape,
            "waste_path": pred["waste_path"],
            "move": pred["move"],
            "effect": pred["effect"],
        },
        "trained": False,
    }
    if train:
        out["trained"] = bool(_train_row(shape, pred, org))
    return out


def simulate_session(thoughts: str) -> dict[str, Any]:
    """Simulate this session cheaply: organize -> prospect -> train the pre-tesuji."""
    org = organize(thoughts)
    shape = org["shape_signature"] or "session"
    pred = _predict(shape, "")
    trained = _train_row(shape, pred, org)
    return {
        "schema": "prospect_sim.simulate.v1",
        "ts": _now(),
        "organized": org,
        "prospective_tesuji": {
            "signature": shape,
            "waste_path": pred["waste_path"],
            "move": pred["move"],
            "effect": pred["effect"],
        },
        "trained": bool(trained),
        "training_row": trained,
    }


def echo(shape: str, *, systems: list[str] | None = None) -> dict[str, Any]:
    """For ALL systems that echo the shape: prospect each pre-emptively."""
    systems = systems or ["ghost", "drainer", "governor", "orchestrator", "swarm"]
    org = organize(shape)
    sig_terms = set(org["shape_signature"].split()) if org["shape_signature"] else set()
    results = {}
    for sysname in systems:
        sys_sig = set(_tokens(sysname))
        echo_hit = bool(sys_sig & sig_terms) or not sig_terms
        if echo_hit:
            results[sysname] = prospect(shape, context=f"echoed by {sysname}")["predicted_tesuji"]
        else:
            results[sysname] = {"echo": False}
    return {
        "schema": "prospect_sim.echo.v1",
        "ts": _now(),
        "shape": org["shape_signature"] or shape,
        "systems_scanned": systems,
        "results": results,
    }


def _train_row(shape: str, pred: dict[str, Any], org: dict[str, Any]) -> dict[str, Any] | None:
    """Fold the prospective tesuji as a training row (training_events + Vast append)."""
    row = {
        "instruction": "When a system echoes the shape '" + (shape or "unknown")[:80] + "', what is the non-obvious move to take BEFORE the event?",
        "input": "",
        "output": f"Prospective tesuji (pre-emptive): the waste path is '{pred['waste_path']}'. The brilliant move is to {pred['move']}. Effect: {pred['effect']}.",
    }
    try:
        TRAIN.parent.mkdir(parents=True, exist_ok=True)
        with TRAIN.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        with FORMATTED.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        from mag import training_events
        training_events.emit(
            "tesuji_shell",
            input_data={"shape": shape[:200]},
            action={"kind": "prospect_sim", "pre_emptive": True,
                    "move": pred["move"][:200], "route_group": org.get("route_group")},
            outcome={"trained": True},
            pattern_tags=["prospect_sim", "pre_emptive", "training_tesuji", "before_it_happens"],
            tier_max="T2",
        )
        return row
    except Exception as e:
        return {"error": str(e)[:120]}


# ───────────────────────────────────────────────────────────────────────────
# SHARED STATELESS MEMORY (HF-style) + VERKLE KNOT — the "ya dig" layer.
# A hash-keyed store, queried statelessly by shape-hash (like a HF dataset /
# repo id). Every prospective tesuji is ALSO verkle-knotted so the shared,
# content-addressed chain is the source of truth — no per-agent session state.
# ───────────────────────────────────────────────────────────────────────────
import hashlib as _hashlib  # noqa: E402

SHARED_MEM = ROOT / "memory" / "prospect" / "map.jsonl"


def _shape_key(shape: str) -> str:
    return _hashlib.sha256((shape or "").strip().lower().encode()).hexdigest()[:16]


def shared_mem_get(shape: str) -> dict[str, Any] | None:
    """Stateless read: look up a prospective tesuji by shape-hash (HF-style)."""
    key = _shape_key(shape)
    if not SHARED_MEM.is_file():
        return None
    for line in SHARED_MEM.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            if r.get("shape_key") == key:
                return r
        except json.JSONDecodeError:
            continue
    return None


def shared_mem_put(shape: str, pred: dict[str, Any], org: dict[str, Any]) -> dict[str, Any]:
    """Stateless write: append a prospective tesuji keyed by shape-hash, then
    verkle-knot it so it lives on the shared content-addressed chain."""
    key = _shape_key(shape)
    row = {
        "schema": "prospect_sim.mem.v1",
        "ts": _now(),
        "shape_key": key,
        "shape": shape[:200],
        "route_group": org.get("route_group"),
        "themes": org.get("themes"),
        "waste_path": pred["waste_path"],
        "move": pred["move"][:400],
        "effect": pred["effect"][:200],
    }
    SHARED_MEM.parent.mkdir(parents=True, exist_ok=True)
    with SHARED_MEM.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # verkle-knot the tesuji (shared stateless memory on the chain)
    knot = {}
    try:
        from mag.verkle_knot import append_verkle_knot
        k = append_verkle_knot({
            "session_id": f"prospect-{key}",
            "theme": "prospect_tesuji",
            "summary": f"[prospect] {shape[:120]} -> {pred['move'][:120]}",
        })
        row["knot"] = {"leaf_hash": k.get("leaf_hash"), "verkle_root": k.get("verkle_root")}
        knot = row["knot"]
    except Exception as e:
        row["knot_error"] = str(e)[:120]
    return row


def categorize(text: str) -> dict[str, Any]:
    """AUTOMATED at initial categorization: organize -> shape -> shared stateless
    memory (hit = steal, no recompute) -> else compute + store + verkle-knot + train."""
    org = organize(text)
    shape = org["shape_signature"] or text.strip()[:60] or "unknown"
    existing = shared_mem_get(shape)
    if existing:
        return {
            "schema": "prospect_sim.categorize.v1",
            "ts": _now(),
            "category": shape,
            "route_group": org["route_group"],
            "memory": "hit",
            "source": "shared_stateless_memory",
            "prospective_tesuji": {
                "waste_path": existing.get("waste_path"),
                "move": existing.get("move"),
                "effect": existing.get("effect"),
            },
            "knot": existing.get("knot"),
        }
    pred = _predict(shape, "auto-categorized")
    stored = shared_mem_put(shape, pred, org)
    _train_row(shape, pred, org)
    return {
        "schema": "prospect_sim.categorize.v1",
        "ts": _now(),
        "category": shape,
        "route_group": org["route_group"],
        "memory": "miss",
        "source": "computed",
        "prospective_tesuji": {
            "waste_path": pred["waste_path"],
            "move": pred["move"],
            "effect": pred["effect"],
        },
        "knot": stored.get("knot"),
    }


def memory_search(text: str, *, limit: int = 5) -> dict[str, Any]:
    """RESTful memory search: exact hash hit, else nearest by token overlap."""
    exact = shared_mem_get(text)
    if exact:
        return {"ok": True, "hit": True, "item": exact, "near": []}
    toks = set(_tokens(text))
    near: list[dict[str, Any]] = []
    if SHARED_MEM.is_file():
        for line in SHARED_MEM.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                overlap = toks & set(_tokens(r.get("shape") or ""))
                if overlap:
                    near.append({**r, "_overlap": len(overlap)})
            except json.JSONDecodeError:
                continue
    near.sort(key=lambda x: -x.get("_overlap", 0))
    return {"ok": True, "hit": False, "item": None, "near": near[:limit]}


def memory_recent(limit: int = 20) -> list[dict[str, Any]]:
    """RESTful memory listing: most recent prospective tesujis stored."""
    rows: list[dict[str, Any]] = []
    if SHARED_MEM.is_file():
        for line in SHARED_MEM.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "organize"
    rest = " ".join(argv[1:]) if len(argv) > 1 else ""
    if cmd == "organize":
        print(json.dumps(organize(rest), indent=2, ensure_ascii=False))
    elif cmd == "prospect":
        print(json.dumps(prospect(rest, train=True), indent=2, ensure_ascii=False))
    elif cmd == "simulate":
        print(json.dumps(simulate_session(rest), indent=2, ensure_ascii=False))
    elif cmd == "echo":
        print(json.dumps(echo(rest), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(organize(rest), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
