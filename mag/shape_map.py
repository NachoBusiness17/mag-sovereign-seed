"""shape_map — make EVERY subsystem a portable verkle-backed shape.

The operator's vision (2026-08-09): "build the shapes that map to memory and transmit them,
get data anywhere" — applied to the ENTIRE series of subsystems. The generic primitive:

  For any subsystem, content-address its STRUCTURAL elements (invariants / artifacts / state),
  fold them into a Merkle root, and emit a COMPACT PORTABLE SPEC (hashes + root, no content).
  Transmit the spec (kilobytes) -> any node with the content (CAS) re-derives the root and
  VERIFIES it matches -> the shape validates reconstruction. Stateless: you own the shape,
  not the state.

This is the castle-in-the-sky made generic: each subsystem declares its shape source; a single
registry maps the whole portfolio; one command exports every subsystem as a portable root.

Deterministic, $0, no LLM. Schema: shape_map.v1
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "shape_map.v1"
OUT = ROOT / "queue" / "handoff" / "shapes"
from mag.steal_steer import _embed


def _h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _merkle_root(hashes: list[str]) -> str:
    if not hashes:
        return _h(b"empty")
    layer = hashes[:]
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i + 1] if i + 1 < len(layer) else left
            nxt.append(_h(("node:" + left + ":" + right).encode()))
        layer = nxt
    return layer[0]


def shape_for(name: str, elements: list[Any], *, text_fn: Callable[[Any], str] | None = None) -> dict[str, Any]:
    """Content-address structural elements -> portable spec {name, root, n, leaf_hashes, coords}."""
    text_fn = text_fn or (lambda e: str(e))
    leaves = []
    for e in elements:
        t = text_fn(e)
        leaves.append({"hash": _h(t.encode("utf-8")), "embed": list(_embed(t)), "text_len": len(t)})
    root = _merkle_root([l["hash"] for l in leaves])
    return {"schema": SCHEMA, "name": name, "root": root, "n": len(leaves),
            "leaf_hashes": [l["hash"] for l in leaves], "leaves": leaves}


def verify(spec: dict[str, Any], elements: list[Any], *, text_fn: Callable[[Any], str] | None = None) -> dict[str, Any]:
    """Re-derive the root from (possibly remote) elements; confirm it matches the transmitted spec."""
    text_fn = text_fn or (lambda e: str(e))
    hashes = [_h(text_fn(e).encode("utf-8")) for e in elements]
    root = _merkle_root(hashes)
    ok = (root == spec.get("root")) and (len(hashes) == spec.get("n"))
    return {"ok": ok, "name": spec.get("name"), "root_matches": root == spec.get("root"),
            "n_matches": len(hashes) == spec.get("n"), "expected_root": spec.get("root"),
            "derived_root": root}


def reconstruct(spec: dict[str, Any], elements: list[Any], *, text_fn: Callable[[Any], str] | None = None) -> dict[str, Any]:
    """Simulate 'get data anywhere': given the shape + CAS content, confirm the full structure
    reconstructs to the transmitted root (inclusion of every leaf)."""
    text_fn = text_fn or (lambda e: str(e))
    v = verify(spec, elements, text_fn=text_fn)
    return {"ok": v["ok"], "reconstructed": bool(v["ok"]), "n": len(elements),
            "note": "shape validated content-addressed reconstruction" if v["ok"]
            else "shape MISMATCH — structure drifted or content missing"}


# ---------------------------------------------------------------------------
# Registry: subsystem -> (element extractor, text_fn). Add a line per subsystem.
# ---------------------------------------------------------------------------
def _rib_elements() -> list[Any]:
    from mag.emergent_harvest import _load_invariants
    return _load_invariants()


def _corpus_elements() -> list[Any]:
    d = ROOT / "memory" / "research_packs"
    return [p.stem for p in d.glob("*.answer.*.md")] if d.is_dir() else []


def _ledger_elements() -> list[Any]:
    p = ROOT / "memory" / "improve" / "skill_ledger.jsonl"
    out = []
    if p.is_file():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _sizer_elements() -> list[Any]:
    p = ROOT / "memory" / "learn" / "sizing.jsonl"
    out = []
    if p.is_file():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _chain_elements() -> list[Any]:
    p = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
    out = []
    if p.is_file():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _jsonl_path(rel: str) -> list[Any]:
    p = ROOT / rel
    out = []
    if p.is_file():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _steal_pack_elements() -> list[Any]:
    return _jsonl_path("memory/runs/steal_pack/filed.jsonl")


def _pro_library_elements() -> list[Any]:
    return _jsonl_path("memory/pro/pro_library.jsonl")


def _mycelium_elements() -> list[Any]:
    return _jsonl_path("memory/mycelium/nodes.jsonl") + _jsonl_path("memory/mycelium/edges.jsonl")


def _lens_elements() -> list[Any]:
    p = ROOT / "memory" / "lenses" / "corpus_index.json"
    if not p.is_file():
        return []
    try:
        idx = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    items = idx.get("items") if isinstance(idx, dict) else idx
    return items if isinstance(items, list) else [idx]


def _txt(e: Any) -> str:
    if isinstance(e, dict):
        return json.dumps(e, sort_keys=True, default=str)
    return str(e)


REGISTRY: dict[str, tuple[Callable[[], list[Any]], Callable[[Any], str]]] = {
    "rib": (_rib_elements, lambda e: f"[{e.get('domain')}] {e.get('text')}"),
    "corpus": (_corpus_elements, str),
    "skill_ledger": (_ledger_elements, _txt),
    "one_sizer": (_sizer_elements, _txt),
    "verkle_chain": (_chain_elements, _txt),
    "steal_pack": (_steal_pack_elements, _txt),
    "pro_library": (_pro_library_elements, _txt),
    "mycelium": (_mycelium_elements, _txt),
    "research_lens": (_lens_elements, _txt),
}

# FAMILY CLAIMS (2026-09-27, operator grant "Family extension" after the
# attic orphan census — watch/inbox/lens_20260927/ATTIC_ORPHAN_CENSUS.md):
# archived snapshots that BELONG to a registered subsystem even though the
# backup relocated/flattened their roots (the census's "backup costume").
# An archive member matching a family rule is HELD by that subsystem, not
# a structural orphan. The Mimosa hook-state blob and the ghost leak-report
# stream were deliberately left UNCLAIMED (operator fork: only the verkle
# family extension was granted).
FAMILY_CLAIMS: dict[str, list[dict[str, str]]] = {
    "verkle_chain": [
        {
            "rule": "attic/**/biography_backup_*/knots/**/*.knot.json",
            "why": "the chain's own backing store snapshotted at a relocated root (167k+ files)",
        },
        {
            "rule": "attic/**/biography_backup_*/knots/by-session_*.json",
            "why": "session pointer files riding the same snapshot",
        },
        {
            "rule": "attic/**/biography_backup_*/verkle_chain.jsonl",
            "why": "chain index snapshot",
        },
        {
            "rule": "attic/**/biography_backup_*/verkle_tip.json",
            "why": "tip snapshot",
        },
    ],
}


def family_claims() -> dict[str, list[dict[str, str]]]:
    """The archive-family extension table (policy, not a matcher)."""
    return FAMILY_CLAIMS


def shape(subsystem: str) -> dict[str, Any]:
    if subsystem not in REGISTRY:
        return {"ok": False, "error": f"unknown subsystem '{subsystem}'; known: {list(REGISTRY)}"}
    get, tf = REGISTRY[subsystem]
    return shape_for(subsystem, get(), text_fn=tf)


def portfolio() -> dict[str, Any]:
    """Export a portable shape for EVERY registered subsystem -> one index of the whole system."""
    shapes = {}
    for name in REGISTRY:
        s = shape(name)
        # portable spec: root + hashes only (no content bytes) so it transmits tiny
        shapes[name] = {"name": name, "root": s["root"], "n": s["n"],
                        "leaf_hashes": s["leaf_hashes"]}
    root = _merkle_root([shapes[n]["root"] for n in shapes])
    return {"ok": True, "schema": SCHEMA, "n_subsystems": len(shapes), "portfolio_root": root,
            "shapes": shapes}


def export(subsystem: str | None = None) -> dict[str, Any]:
    """Write portable spec file(s) to queue/handoff/shapes/ so they can be transmitted."""
    OUT.mkdir(parents=True, exist_ok=True)
    if subsystem:
        s = shape(subsystem)
        p = OUT / f"shape_{subsystem}.json"
        p.write_text(json.dumps(s, indent=2, default=str), encoding="utf-8")
        return {"ok": True, "path": str(p), "name": subsystem, "root": s["root"], "n": s["n"]}
    pf = portfolio()
    p = OUT / "portfolio.json"
    p.write_text(json.dumps(pf, indent=2, default=str), encoding="utf-8")
    return {"ok": True, "path": str(p), **pf}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="shape-map")
    ap.add_argument("cmd", nargs="?", default="portfolio", choices=["portfolio", "shape", "export"])
    ap.add_argument("--sub", default="")
    ap.add_argument("--verify", default="")
    args = ap.parse_args(argv)
    if args.cmd == "portfolio":
        print(json.dumps(portfolio(), indent=2, default=str))
    elif args.cmd == "shape":
        print(json.dumps(shape(args.sub), indent=2, default=str))
    elif args.cmd == "export":
        print(json.dumps(export(args.sub or None), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
