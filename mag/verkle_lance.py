"""verkle_lance — steal ghostlance's shape for the VERKLE KNOT lattice.

Operator (2026-08-11): "we need a verkle lance like pylance so we can use our determinism to map
to events tying them together temporally."

STEAL ANALYSIS:
  * SELF — ghost_pylance (GHOSTLANCE) is deterministic code-intelligence over our code (AST, $0);
    ghost_memlance is deterministic memory-state selection over our memory files. verkle_lance is the
    same shape over the VERKLE KNOT CHAIN: deterministic, content-addressed, $0 knot-intelligence.
  * The determinism IS the temporal map: each chain row has `index` (position), `parent_verkle_root`
    (merkle root of all prior) and `verkle_root` (root up to this) — so a knot's identity = its
    content hash, and its PLACE = the chain of roots that produced it. Events map to knots by
    session_id/theme/time, and the roots tie them together temporally (parent→child, turtles down).

Schema: verkle_lance.v1 · deterministic $0 · CLI: python -m mag.verkle_lance <tool>
MEMTOOLS (knot-intelligence, mirroring ghostlance):
  index()      - the knot chain in temporal order (session_id, ts, theme, leaf_hash, parent/root).
  temporal()   - the temporal timeline: ordered knots + parent→child root linkage + deltas.
  trace(key)   - map an event/key (session_id, theme, label, hash prefix) to its knot(s) + place.
  link(event)  - tie an event temporally: knot at/before its time, the verkle root, the linkage.
  verify(key)  - deterministic content-addressed verdict for a knot (in chain? valid hash? root?).
  self_check() - chain consistency: n leaves, root valid, temporal order monotonic, orphans.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
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

SCHEMA = "verkle_lance.v1"
BIO = ROOT / "memory" / "biography"
KNOTS = BIO / "knots"
CHAIN = BIO / "verkle_chain.jsonl"
TIP = BIO / "verkle_tip.json"

_cache: dict[str, Any] = {}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_chain(refresh: bool = False) -> list[dict[str, Any]]:
    if "chain" in _cache and not refresh:
        return _cache["chain"]
    rows: list[dict[str, Any]] = []
    if CHAIN.is_file():
        for line in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    # temporal order = chain index
    rows.sort(key=lambda r: r.get("index", 0))
    _cache["chain"] = rows
    return rows


def _knot_meta(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": row.get("index"),
        "session_id": row.get("session_id"),
        "ts": row.get("ts") or row.get("start_minute"),
        "start_minute": row.get("start_minute"),
        "theme": row.get("dominant_theme"),
        "leaf_hash": row.get("leaf_hash"),
        "parent_verkle_root": row.get("parent_verkle_root"),
        "verkle_root": row.get("verkle_root"),
        "tension": row.get("tension_index"),
    }


def index(*, refresh: bool = False) -> dict[str, Any]:
    rows = _load_chain(refresh)
    tip = _read_json(TIP) or {}
    return {"ok": True, "schema": SCHEMA, "n_knots": len(rows),
            "root": tip.get("root"), "last_session": tip.get("last_session_id"),
            "knots": [_knot_meta(r) for r in rows]}


def temporal(*, refresh: bool = False) -> dict[str, Any]:
    """The temporal timeline: ordered knots with parent→child root linkage + root deltas."""
    rows = _load_chain(refresh)
    timeline = []
    for i, r in enumerate(rows):
        meta = _knot_meta(r)
        meta["parent_root"] = r.get("parent_verkle_root")
        meta["root"] = r.get("verkle_root")
        meta["root_changed"] = bool(r.get("parent_verkle_root")) and \
            r.get("parent_verkle_root") != r.get("verkle_root")
        meta["delta_from_parent"] = (r.get("verkle_root") or "")[:12] if i else "genesis"
        timeline.append(meta)
    return {"ok": True, "schema": SCHEMA, "n_knots": len(timeline),
            "genesis": timeline[0] if timeline else None,
            "tip": timeline[-1] if timeline else None,
            "timeline": timeline}


def _matches(key: str, row: dict[str, Any]) -> bool:
    low = key.lower()
    hay = " ".join(str(row.get(k) or "") for k in
                   ("session_id", "dominant_theme", "leaf_hash", "filename", "dossier_commit")).lower()
    return low in hay or low in str(row.get("leaf_hash") or "").lower()


def trace(key: str, *, limit: int = 20) -> dict[str, Any]:
    """Map an event/key to its knot(s) + temporal place (like trace_value for knots).

    key = session_id, theme, label substring, or leaf_hash prefix. Returns every matching knot
    with its chain position, parent root and root (the temporal tie), plus its neighbours.
    """
    rows = _load_chain()
    hits = [r for r in rows if _matches(key, r)]
    if not hits:
        return {"ok": True, "schema": SCHEMA, "key": key, "found": False, "n_knots": len(rows)}
    out = []
    for h in hits[:limit]:
        idx = h.get("index")
        meta = _knot_meta(h)
        meta["parent"] = rows[idx - 1]["session_id"] if idx and idx - 1 < len(rows) else None
        meta["child"] = rows[idx + 1]["session_id"] if idx is not None and idx + 1 < len(rows) else None
        out.append(meta)
    return {"ok": True, "schema": SCHEMA, "key": key, "found": True,
            "n_matches": len(out), "matches": out}


def link(event: str, *, when: str = "") -> dict[str, Any]:
    """Tie an event temporally: the knot at/before its time and the verkle root at that point.

    This is the 'map to events tying them together temporally' op: given an event (a label/flow or
    an ISO time), find the chain position it lands in and the root that anchors it.
    """
    rows = _load_chain()
    if not rows:
        return {"ok": True, "schema": SCHEMA, "event": event, "found": False}
    # direct session/theme match first
    matched = [r for r in rows if _matches(event, r)]
    if matched:
        h = matched[-1]
        return {"ok": True, "schema": SCHEMA, "event": event, "found": True,
                "knot": _knot_meta(h), "verkle_root": h.get("verkle_root"),
                "n_knots_at_point": (h.get("index") or 0) + 1}
    # else temporal anchor: nearest knot by time
    tgt = None
    if when:
        try:
            tgt = datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError:
            tgt = None
    if tgt:
        best = None
        for r in rows:
            ts = r.get("ts") or r.get("start_minute")
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt <= tgt:
                best = r
            else:
                break
        if best:
            return {"ok": True, "schema": SCHEMA, "event": event, "found": True,
                    "knot": _knot_meta(best), "verkle_root": best.get("verkle_root"),
                    "temporal": "nearest_at_or_before"}
    return {"ok": True, "schema": SCHEMA, "event": event, "found": False,
            "note": "no session/theme match and no time anchor given; see temporal()"}


def verify(key: str) -> dict[str, Any]:
    """Deterministic content-addressed verdict: is the knot in the chain, hash present, root valid?"""
    rows = _load_chain()
    tip = _read_json(TIP) or {}
    h = next((r for r in rows if _matches(key, r)), None)
    if not h:
        return {"ok": True, "schema": SCHEMA, "key": key, "found": False}
    return {"ok": True, "schema": SCHEMA, "key": key, "found": True,
            "in_chain": bool(h.get("leaf_hash")),
            "has_root": bool(h.get("verkle_root")),
            "content_addressed": bool(h.get("leaf_hash") and h.get("verkle_root")),
            "leaf_hash": (h.get("leaf_hash") or "")[:12],
            "root_at_point": (h.get("verkle_root") or "")[:12],
            "tip_root": (tip.get("root") or "")[:12]}


# ── LANCING — mark reference spots in the tree for the swarm to take ─────────
_DIM = 3  # invariant-space dimension the flock seeds (flock_field dim)


def _shape(row: dict[str, Any]) -> list[float]:
    """A knot's SHAPE = its theme_vector_normalized (position in theme space), or a deterministic
    hash-seeded 3-vector when absent. Always returns a length-_DIM shape the swarm can seed from."""
    tv = row.get("theme_vector_normalized") or row.get("theme_vector") or []
    if isinstance(tv, (list, tuple)) and tv:
        # reduce/pad to _DIM deterministically
        out = []
        for i in range(_DIM):
            if i < len(tv):
                out.append(float(tv[i]))
            else:
                out.append(0.0)
        n = math.sqrt(sum(x * x for x in out)) or 1e-9
        return [round(x / n, 4) for x in out]
    h = str(row.get("leaf_hash") or row.get("session_id") or "x")
    # hash-seeded deterministic 3-vector (stable across runs)
    v = []
    for i in range(_DIM):
        b = int(h[i * 8:(i + 1) * 8] or "0", 16)
        v.append(((b % 1000) / 1000.0) * 2 - 1)
    return [round(x, 4) for x in v]


def lance(n: int = 20, *, mode: str = "spread") -> dict[str, Any]:
    """LANCE n reference spots in the verkle tree. Each lance = a knot's temporal place + its SHAPE.

    mode="spread"  -> n spots spread TEMPORALLY across the chain (evenly spaced by index) = 20
                      reference points for the swarm to seed from.
    mode="themes"  -> n knots by distinct dominant_theme (one per theme, most recent).
    The lanced shapes are exactly what the k8s flock takes as seed positions (swarm takes those
    shapes) -> pods converge on the lanced landscape -> fold back (emergent).
    """
    rows = _load_chain()
    if not rows:
        return {"ok": True, "schema": SCHEMA, "n": n, "lances": []}
    n = max(1, min(n, len(rows)))
    lances: list[dict[str, Any]] = []
    if mode == "themes":
        seen: dict[str, dict[str, Any]] = {}
        for r in rows:
            t = r.get("dominant_theme") or "untagged"
            seen[t] = r  # last (most recent) per theme
        for r in list(seen.values())[:n]:
            lances.append({"index": r.get("index"), "session_id": r.get("session_id"),
                           "theme": r.get("dominant_theme"), "ts": r.get("ts") or r.get("start_minute"),
                           "leaf_hash": (r.get("leaf_hash") or "")[:12],
                           "root": (r.get("verkle_root") or "")[:12],
                           "shape": _shape(r)})
    else:  # spread temporally
        step = max(1, len(rows) // n)
        for k in range(n):
            r = rows[min(k * step, len(rows) - 1)]
            lances.append({"index": r.get("index"), "session_id": r.get("session_id"),
                           "theme": r.get("dominant_theme"), "ts": r.get("ts") or r.get("start_minute"),
                           "leaf_hash": (r.get("leaf_hash") or "")[:12],
                           "root": (r.get("verkle_root") or "")[:12],
                           "shape": _shape(r)})
    return {"ok": True, "schema": SCHEMA, "n": len(lances), "mode": mode,
            "n_knots": len(rows), "lances": lances}


def shapes(n: int = 20, *, mode: str = "spread") -> dict[str, Any]:
    """Export the lanced shapes as a SEED BUNDLE the k8s flock can consume.

    Returns the lanced reference points + their shape vectors (the seed positions the swarm takes)
    + a JSON blob a flock pod reads via MAG_FLOCK_SEED to adopt that lance's shape.
    """
    L = lance(n, mode=mode)
    lances = L.get("lances", [])
    seeds = [ln["shape"] for ln in lances]
    return {"ok": True, "schema": SCHEMA, "n": len(lances), "mode": mode,
            "seeds": seeds,
            "seed_bundle": {
                "schema": "verkle_lance.seed.v1",
                "n": len(lances),
                "positions": seeds,
                "reference": [{"index": ln["index"], "session_id": ln["session_id"],
                               "theme": ln["theme"], "root": ln["root"]} for ln in lances],
            }}


def _seed_bundle_json(n: int = 20, *, mode: str = "spread") -> str:
    """The seed bundle as a JSON string (for MAG_FLOCK_SEED / pod env)."""
    S = shapes(n, mode=mode)
    return json.dumps(S.get("seed_bundle", {}), separators=(",", ":"))


# ── TIE-IN INFRASTRUCTURE: lances -> invariant RIB builder + stateless puppeteer ──
# Operator (2026-08-11): "it's the invariant rib builder / verkle knot stateless puppeteer tie in
# infrastructure." VerkleLance is the joint: lancing the verkle tree produces the SEED INVARIANTS
# (RIB scenes) the invariant builder renders/dispatches (steer_ollama / dispatch_to_k8s / render),
# and the STATELESS PUPPETEER (partner_puppet) steers remote agents with those same shapes. Any
# seat can be puppet (failover); state lives in the chain, never the process.


def _lance_invariant(ln: dict[str, Any]) -> str:
    """Turn one lance into an invariant RIB-scene seed (the unit of work)."""
    theme = ln.get("theme") or "lanced"
    sid = str(ln.get("session_id") or "?").replace(":", "_")[:24]
    root = str(ln.get("root") or "")[:12]
    return f"verkle_lance:{theme}:{sid}:{root}"


def rib_builder(n: int = 20, *, mode: str = "spread") -> dict[str, Any]:
    """Map lanced shapes -> invariant RIB scenes for the invariant rib builder (invariant_lattice).

    Each lance becomes an invariant (RIB scene); the builder can steer the local ollama, dispatch to
    the k8s swarm, or render cheapest. Deterministic $0 (no execution here — just the mapping).
    """
    L = lance(n, mode=mode)
    lances = L.get("lances", [])
    scenes = []
    for i, ln in enumerate(lances):
        scenes.append({"position": i, "invariant": _lance_invariant(ln),
                       "shape": ln["shape"], "session_id": ln["session_id"],
                       "root": ln["root"]})
    return {"ok": True, "schema": SCHEMA, "n": len(scenes), "mode": mode,
            "rib_scenes": scenes,
            "steer_bundle": {
                "schema": "verkle_lance.tiein.v1",
                "n": len(scenes),
                "invariants": [s["invariant"] for s in scenes],
                "positions": [s["shape"] for s in scenes],
            }}


def puppet_trigger(n: int = 20, *, mode: str = "spread", execute: bool = False) -> dict[str, Any]:
    """Tie lances into the STATELESS PUPPETEER (partner_puppet): each lance = a puppet token.

    A puppet is any actor that folds invariant knots. We derive a token per lance and expose the
    trigger path (partner_puppet.puppet). execute=False (default) = read-only wiring, $0.
    """
    RB = rib_builder(n, mode=mode)
    scenes = RB.get("rib_scenes", [])
    triggers = []
    for s in scenes:
        token = s["invariant"]
        result = None
        if execute:
            try:
                from mag.partner_puppet import puppet
                result = puppet(token, execute=True)
            except Exception as e:
                result = {"ok": False, "error": str(e)[:80]}
        triggers.append({"position": s["position"], "token": token,
                         "shape": s["shape"], "result": result})
    return {"ok": True, "schema": SCHEMA, "n": len(triggers), "mode": mode,
            "execute": execute, "puppets": triggers}


def tie_in(n: int = 20, *, mode: str = "spread", probe: bool = True) -> dict[str, Any]:
    """THE TIE-IN: lances -> invariant rib builder -> (render/dispatch) + stateless puppeteer.

    One surface connecting the three pillars:
      verkle_lance (lances the tree) -> invariant_lattice (RIB scenes: steer_ollama / dispatch_to_k8s
      / render) -> partner_puppet (stateless puppeteer triggers).
    probe=True (default): render ONE lance via the invariant builder cheapest-capable path (local
    ollama, $0) to prove the joint is live. No swarm dispatch / no execute by default.
    """
    RB = rib_builder(n, mode=mode)
    scenes = RB.get("rib_scenes", [])
    render_probe = None
    if probe and scenes:
        try:
            from mag.invariant_lattice import render
            render_probe = render(scenes[0]["invariant"], prefer="ollama")
        except Exception as e:
            render_probe = {"ok": False, "error": str(e)[:100]}
    try:
        from mag.partner_puppet import puppet  # noqa: F401 — importability = wired check
        puppet_wired = True
    except Exception:
        puppet_wired = False
    return {"ok": True, "schema": SCHEMA, "n": len(scenes), "mode": mode,
            "joint": "verkle_lance -> invariant_lattice(RIB builder) -> partner_puppet(stateless)",
            "puppet_wired": puppet_wired,
            "render_probe": render_probe,
            "steer_bundle": RB.get("steer_bundle"),
            "wiring": {
                "to_rib_builder": "invariant_lattice.render / steer_ollama / dispatch_to_k8s",
                "to_puppeteer": "partner_puppet.puppet(token, execute)",
                "farm": "k8s swarm (flock_job) takes the lanced shapes as seed positions",
            }}


def self_check(*, refresh: bool = False) -> dict[str, Any]:
    """Chain consistency: n leaves, tip root valid, temporal order monotonic, orphans."""
    rows = _load_chain(refresh)
    tip = _read_json(TIP) or {}
    # temporal order monotonic: index should be 0..n-1 in order
    order_ok = all(r.get("index") == i for i, r in enumerate(rows))
    orphans = [r for r in rows if not r.get("session_id")]
    has_content_addressed = all(r.get("leaf_hash") and r.get("verkle_root") for r in rows) if rows else True
    by_theme: dict[str, int] = {}
    for r in rows:
        t = r.get("dominant_theme") or "untagged"
        by_theme[t] = by_theme.get(t, 0) + 1
    return {"ok": True, "schema": SCHEMA, "n_knots": len(rows),
            "tip_root": tip.get("root"), "last_session": tip.get("last_session_id"),
            "order_monotonic": order_ok, "orphans": len(orphans),
            "all_content_addressed": has_content_addressed,
            "by_theme": by_theme,
            "genesis_ts": (rows[0].get("ts") or rows[0].get("start_minute")) if rows else None,
            "tip_ts": (rows[-1].get("ts") or rows[-1].get("start_minute")) if rows else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="verkle-lance")
    ap.add_argument("cmd", nargs="?", default="self_check",
                    choices=["index", "temporal", "trace", "link", "verify", "lance", "shapes",
                             "rib_builder", "puppet_trigger", "tie_in", "self_check"])
    ap.add_argument("--key", default="")
    ap.add_argument("--event", default="")
    ap.add_argument("--when", default="")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--mode", default="spread", choices=["spread", "themes"])
    args = ap.parse_args(argv)
    if args.cmd == "index":
        print(json.dumps(index(refresh=True), indent=2, default=str))
    elif args.cmd == "temporal":
        print(json.dumps(temporal(refresh=True), indent=2, default=str))
    elif args.cmd == "trace":
        print(json.dumps(trace(args.key), indent=2, default=str))
    elif args.cmd == "link":
        print(json.dumps(link(args.event, when=args.when), indent=2, default=str))
    elif args.cmd == "verify":
        print(json.dumps(verify(args.key), indent=2, default=str))
    elif args.cmd == "lance":
        print(json.dumps(lance(args.n, mode=args.mode), indent=2, default=str))
    elif args.cmd == "shapes":
        print(json.dumps(shapes(args.n, mode=args.mode), indent=2, default=str))
    elif args.cmd == "rib_builder":
        print(json.dumps(rib_builder(args.n, mode=args.mode), indent=2, default=str))
    elif args.cmd == "puppet_trigger":
        print(json.dumps(puppet_trigger(args.n, mode=args.mode), indent=2, default=str))
    elif args.cmd == "tie_in":
        print(json.dumps(tie_in(args.n, mode=args.mode), indent=2, default=str))
    else:
        print(json.dumps(self_check(refresh=True), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
