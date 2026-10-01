"""window_bus — the extended window AS the swarm bus (blackboard at cache-hit cost, puppet hidden).

Idea (operator): extend window length to exploit it — get data to each other using a BUS so the
models run like an agent swarm, aware of each other and adapting to our systems, through them,
unaware of the puppet.

Grounding:
  - Blackboard architecture (Wikipedia): a SHARED repository (the blackboard) that specialist
    knowledge-sources watch and opportunistically contribute to; a CONTROL SHELL coordinates
    flow. -> The bus is the shared context; the puppet is the control shell that curates it.
  - Anthropic "Building effective agents": orchestrator-workers — a central coordinator delegates
    and synthesizes; workers run focused windows.
  - Our cache economics: a BYTE-STABLE prefix bills at cache-HIT (0.0028 vs 0.14 = 50x). So a
    shared, append-only, byte-stable bus segment is CHEAP to extend — "extending window length to
    carry shared data" bills at hit, and the bus is paid ONCE and shared by all members.
  - Our existing primitives (self-steal, no rebuild): shader_bus (register + deniable LSB bus),
    flock_field ("the field IS the coordination — no central orchestrator" = puppet already hidden),
    whisper_route (front/riddler/corpus/memlang), memlang (opcode + anchor, no readable spec).

Mechanism per member window = BUS (stable prefix, cache-HIT) + own delta (MISS) + output (OUT).
  - aware-of-swarm: every member mounts the same byte-stable BUS -> sees the swarm's shared state.
  - adaptive-to-our-systems: the BUS carries our invariants/signals -> members steer toward them.
  - unaware-of-puppet: the puppet = control shell that CURATES what goes on/off the bus; members
    never see the curation, only the resulting bus + a content anchor (deniable, like memlang).

Schema: window_bus.v1 · deterministic $0 · CLI: python -m mag.window_bus price --members 8 ...
"""
from __future__ import annotations

import hashlib
from typing import Any

try:
    from mag.cache_map import MODEL_RATES
except Exception:
    MODEL_RATES = {}

RATE = MODEL_RATES.get("deepseek-v4-flash") or {"hit": 0.0028, "miss": 0.14, "out": 0.28}
SCHEMA = "window_bus.v1"


def _anchor(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def _tok(text: str) -> int:
    # conservative ~4 chars/token for ASCII-heavy deterministic text
    return max(1, round(len(text) / 4))


def bus_segment(*, invariants: list[str], signals: list[str],
                members: list[str], header: str = "SWARM-BUS") -> dict[str, Any]:
    """Assemble the byte-stable shared bus (blackboard): our invariants + live signals + roster.
    Deterministic: fixed ordering, dedup, content anchor. Members mount this as their stable prefix."""
    lines: list[str] = [f"<{header}>"]
    for i in sorted(set(invariants)):
        lines.append("INV " + i)
    for s in sorted(set(signals)):
        lines.append("SIG " + s)
    for m in sorted(set(members)):
        lines.append("MEM " + m)
    lines.append(f"</{header}>")
    text = "\n".join(lines)
    return {"ok": True, "schema": SCHEMA, "lines": lines,
            "tokens": _tok(text), "anchor": _anchor(text),
            "n_invariants": len(set(invariants)), "n_signals": len(set(signals)),
            "n_members": len(set(members))}


def price_window_bus(*, bus_tokens: int, members: int, delta_per_member: int,
                     out_per_member: int) -> dict[str, Any]:
    """'Extend window length to exploit it': the bus is a shared STABLE prefix, so every member
    bills the bus at cache-HIT (once) and only its own delta at MISS. Compare to naive where each
    member re-pays the whole bus at MISS (no byte-stable reuse)."""
    # Shared bus at hit (one prefix, reused across members -> hit rate applies to bus_tokens)
    bus_hit_usd = bus_tokens / 1e6 * RATE["hit"]
    per_member = (delta_per_member / 1e6 * RATE["miss"]) + (out_per_member / 1e6 * RATE["out"])
    shared_total = round(bus_hit_usd + per_member * members, 6)

    # Naive: each member pays the FULL bus at miss (no shared stable prefix)
    naive_total = round((bus_tokens + delta_per_member) / 1e6 * RATE["miss"] * members
                        + out_per_member / 1e6 * RATE["out"] * members, 6)

    return {
        "ok": True, "schema": SCHEMA,
        "rates": {"hit": RATE["hit"], "miss": RATE["miss"], "out": RATE["out"]},
        "shape": {"bus_tokens": bus_tokens, "members": members,
                  "delta_per_member": delta_per_member, "out_per_member": out_per_member},
        "shared_bus": {"usd": shared_total,
                       "bus_share_usd": round(bus_hit_usd, 6),
                       "awareness_share_of_cost": round(bus_hit_usd / max(1e-9, shared_total), 4)},
        "naive_no_bus": {"usd": naive_total},
        "savings_x": round(naive_total / max(1e-9, shared_total), 2),
        "doctrine": ("awareness is cheap: the bus is a shared byte-stable prefix billed at cache-HIT "
                     "once, so extending window length to carry swarm data costs almost nothing and "
                     "is paid ONCE for ALL members."),
    }


def member_view(*, bus: dict[str, Any], member: str, delta: str,
                hidden_control: str = "") -> dict[str, Any]:
    """What a member sees: the shared BUS (awareness of the swarm + our systems) + its own delta.
    The puppet's curation (hidden_control) is NEVER shown -> members adapt to the bus, unaware of
    the puppet (control shell) that curated it."""
    window = bus["lines"] + ["MY " + member, "DELTA " + delta]
    if hidden_control:
        window = window  # control shell stays out of the visible window (deniable)
    return {
        "ok": True, "schema": SCHEMA, "member": member,
        "visible_tokens": _tok("\n".join(window)),
        "sees_bus": True, "sees_control": False,
        "bus_anchor": bus.get("anchor"), "window": window,
        "deniability": "member sees only the shared bus + its own delta; the puppet's curation "
                       "(control shell) is absent from the window",
    }


def curate(*, prev: dict[str, Any], member_deltas: dict[str, str],
           header: str = "SWARM-BUS") -> dict[str, Any]:
    """The puppet (control shell) advances the bus: append each member's distilled delta, re-anchor.
    Members adapt to the new bus next round without ever seeing this curation step."""
    lines: list[str] = [f"<{header}>"]
    # keep invariant/signal lines from prev (stable prefix), append distilled deltas
    for ln in prev.get("lines", []):
        if ln.startswith(("INV ", "SIG ", "MEM ", "<", "</")):
            lines.append(ln)
    for m in sorted(member_deltas):
        lines.append("DELTA " + m + " :: " + member_deltas[m].strip())
    lines.append(f"</{header}>")
    text = "\n".join(lines)
    return {"ok": True, "schema": SCHEMA, "lines": lines,
            "tokens": _tok(text), "anchor": _anchor(text),
            "advanced": len(member_deltas),
            "note": "puppet appended member deltas and re-anchored; next round mounts this as the "
                    "new byte-stable prefix (still cache-HIT) — awareness grows, puppet stays hidden"}


def price_dynamic_invariant(*, inv_tokens: int, reads: int) -> dict[str, Any]:
    """'Invariants created on the fly -> cache hits -> mine nuance for pennies.'
    A dynamically-authored invariant (a distilled nuance) is appended to the byte-stable bus ONCE
    (one small MISS for the fold), then every subsequent member/hop read of the grown bus bills it
    at cache-HIT. So the nuance compounds across all reads at pennies. Compares to NOT folding it
    into the stable prefix, where every read re-pays at MISS."""
    fold_usd = inv_tokens / 1e6 * RATE["miss"]          # one-time append (the 'on the fly' fold)
    per_read_usd = inv_tokens / 1e6 * RATE["hit"]       # rides the cached prefix thereafter
    total = round(fold_usd + per_read_usd * reads, 6)
    naive = round(inv_tokens / 1e6 * RATE["miss"] * (1 + reads), 6)  # every read re-pays at miss
    per_read_min_usd = per_read_usd * 1e6
    return {
        "ok": True, "schema": SCHEMA, "kind": "dynamic_invariant",
        "shape": {"inv_tokens": inv_tokens, "reads": reads},
        "costs": {
            "fold_once_usd": round(fold_usd, 6),
            "per_read_hit_usd": round(per_read_usd, 6),
            "per_read_hit_usd_per_M": round(per_read_min_usd, 4),
            "total_usd": total,
            "naive_no_cache_usd": naive,
        },
        "savings_x": round(naive / max(1e-9, total), 2),
        "doctrine": ("fold the nuance into the byte-stable prefix once (small miss), then mine it "
                     "at cache-HIT across every member/hop — pennies because the invariant amortizes "
                     "over all reads. Invariants are created ON THE FLY from emergent activity, not "
                     "pre-hardcoded."),
    }


def fold_dynamic_invariant(*, bus: dict[str, Any], name: str, body: str,
                           reads: int) -> dict[str, Any]:
    """The puppet (control shell) folds a freshly-mined nuance into the bus as a new INV line.
    Append-only (byte-stable prefix preserved) -> next round still cache-HIT. Prices the fold."""
    inv = "INV " + name + " :: " + body
    lines = bus.get("lines", [])
    # append before the closing tag to keep the stable prefix + re-anchor
    close = "</" + (next((l[1:].rstrip(">") for l in lines if l.startswith("</")), "SWARM-BUS")) + ">"
    core = [l for l in lines if not l.startswith("</")]
    new_lines = core + [inv, close]
    text = "\n".join(new_lines)
    inv_tokens = _tok(inv)
    price = price_dynamic_invariant(inv_tokens=inv_tokens, reads=reads)
    return {"ok": True, "schema": SCHEMA, "kind": "fold_dynamic_invariant",
            "name": name, "inv_tokens": inv_tokens, "anchor": _anchor(text),
            "tokens": _tok(text), "reads": reads,
            "price": price}


def accept_knot(*, name: str, body: str, session_id: str, dominant_theme: str | None = None,
                reads: int = 1, write: bool = True) -> dict[str, Any]:
    """'A self-contained verkle knot that ties back into the hole when accepted — like our api calls.'
    When a mined dynamic invariant is ACCEPTED, commit it as a real self-contained verkle knot via
    append_verkle_knot (self-steal — the write/chain/tip machinery already exists). The knot links
    back into the tree via parent_verkle_root ('the hole it joins') and the tip root advances.
    Like an API call: mine -> accept(POST) -> knot appended -> verkle_bus 'mag:verkle' -> all agents
    sync. Deterministic; never raises (write failure degrades to a priced preview)."""
    theme = (dominant_theme or name or "untagged").strip().lower().replace(" ", "-")[:24]
    inv = f"INV {name} :: {body}"
    inv_tokens = _tok(inv)
    price = price_dynamic_invariant(inv_tokens=inv_tokens, reads=reads)
    if not write:
        return {"ok": True, "schema": SCHEMA, "kind": "accept_knot", "written": False,
                "theme": theme, "price": price,
                "note": "preview: accepted invariant would commit as a verkle knot (ties back via parent_verkle_root)"}

    try:
        from datetime import datetime, timezone
        from mag.verkle_knot import append_verkle_knot
        now = datetime.now(timezone.utc)
        iso = now.isoformat().replace("+00:00", "Z")[:16] + "Z"
        anchor = _anchor(inv)
        dossier = {
            "session_id": session_id,
            "time": {
                "created_at": {"iso_minute": iso, "unix_minute": int(now.timestamp() // 60),
                               "date": now.strftime("%Y-%m-%d")},
                "updated_at": {"iso_minute": iso, "unix_minute": int(now.timestamp() // 60),
                               "date": now.strftime("%Y-%m-%d")},
            },
            "scalar_knot": {
                "theme_vector": {"basis": None, "raw": [0.0] * 8, "normalized": [0.0] * 8,
                                 "dominant": theme},
                "duration_minutes": 1, "tension_index": 0.0, "residual_weight": 0.0,
                "Q_proxy": 0.0, "gap_proxy": 0.0, "lambda2_proxy": 0.0, "dirichlet_energy_proxy": 0.0,
            },
            "content_commit": {"hex": anchor},
            "chord": {},
        }
        r = append_verkle_knot(dossier)
        return {"ok": True, "schema": SCHEMA, "kind": "accept_knot", "written": True,
                "theme": theme, "price": price,
                "knot": {"filename": r.get("filename"), "leaf_hash": r.get("leaf_hash"),
                         "path": r.get("path")},
                "ties_back": {"parent_verkle_root": r.get("parent_verkle_root"),
                              "verkle_root": r.get("verkle_root"), "n_leaves": r.get("n_leaves")},
                "like_api": "mag:verkle published -> all agents sync (verkle_bus); accepted knot now "
                            "a self-contained leaf in the chain",
                "amended": r.get("amended"), "skipped": r.get("skipped", False)}
    except Exception as e:  # never break the swarm on a write failure
        return {"ok": True, "schema": SCHEMA, "kind": "accept_knot", "written": False,
                "theme": theme, "error": str(e)[:160], "price": price,
                "note": "verkle write unavailable; invariant priced but not committed"}


def main(argv: list[str] | None = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="window_bus")
    p.add_argument("--members", type=int, default=8)
    p.add_argument("--bus", type=int, default=6000, help="bus (stable prefix) tokens")
    p.add_argument("--delta", type=int, default=3000)
    p.add_argument("--out", type=int, default=800)
    a = p.parse_args(argv)
    print(json.dumps(price_window_bus(bus_tokens=a.bus, members=a.members,
                                      delta_per_member=a.delta, out_per_member=a.out),
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
