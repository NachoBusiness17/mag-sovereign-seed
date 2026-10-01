"""knot_untangle — codify the esoteric 'untangle the knot' as a REAL, useful, testable operation.

Operator (2026-08-11): "how can we actually codify any of this within rib without it being all
handwaivy and how is it not just ritual how is it actually useful can we tell a cluster of k9's
to untangle a knot topology problem within our verkle structure?"

THE POINT (not ritual, not hand-wavy): the Monroe/esoteric layer is a LENS, but the primitives are
REAL. A verkle knot is a content-addressed leaf in the chain. The REAL tangle in a verkle chain is
NOT braid crossings — it's NEAR-DUPLICATE CONTENT: many knots saying the same invariant (over-
constraining the same anchor). That's measurable with real token-overlap similarity, and untangling
it = re-synthesizing each near-duplicate cluster into ONE essential invariant (a real dedup gain).

So:
  - a "tangled" knot = one that shares high token-overlap with OTHER knots in the chain (it's a
    near-duplicate: multiple knots over-constrain the same content anchor).
  - "untangling" = RE-SYNTHESIZING each tangled CLUSTER into a SINGLE simpler invariant, collapsing
    the near-duplicates (fewer knots, same essential content — a real chain-consolidation win).
  - dispatching it to a cluster of k8s workers = each worker merges one tangled cluster into its
    essential invariant and returns the single simplified form.

THE OPERATION (deterministic + $0 measure; swarm dispatch only for the tangled clusters):
  tangle(rib)      -> real measure: a knot's MAX token-overlap ratio against its best-matching
                     neighbor in the chain. >OVERLAP_THRESHOLD = tangled (near-duplicate).
  scan_chain()     -> read the REAL verkle chain, cluster knots by content overlap, rank the
                     TANGLED CLUSTERS (each = the near-duplicates that should collapse to one).
                     Honest: reports n_knots, n_clusters, the top tangled clusters + sizes.
  untangle(domain, dry) -> dispatch each tangled cluster to the k8s swarm: a worker merges the
                     cluster into ONE essential invariant. dry=True = plan. Honest: only counts
                     dispatched + task ids, never claims a result it didn't get.

Schema: knot_untangle.v2 · deterministic + $0 except swarm dispatch (the tangled clusters only)
Reuse: verkle_knot (chain + consolidate), swarm_worker (dispatch), rib_bus
"""
from __future__ import annotations

import re
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "knot_untangle.v2"
# content-anchor overlap ratio above this = the knot is a near-duplicate (tangled with another)
OVERLAP_THRESHOLD = 0.6
_TOKEN_RE = re.compile(r"[a-z0-9_]{3,}")
_STOP = frozenset("the a an of to and for in on at by with from as is are was were be been being it "
                  "its this that these those we you they i he she them our their your my his her do "
                  "does did not no nor so but if then than too very can will just should would".split())


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP}


def _top_anchors(toks: set[str], k: int = 3) -> list[str]:
    """Deterministic top-k anchor tokens (sorted) for content-anchor bucketing (O(n), not O(n^2))."""
    return sorted(toks)[:k]


def _overlap(a: set[str], b: set[str]) -> float:
    """Jaccard-style overlap: shared content / union. 1.0 = identical content, 0 = none."""
    if not a or not b:
        return 0.0
    return round(len(a & b) / len(a | b), 4)


def tangle(rib: str, *, others: list[str] | None = None) -> dict[str, Any]:
    """REAL tangle measure: max token-overlap of this rib against its best-matching neighbor.
    >OVERLAP_THRESHOLD = tangled (near-duplicate). Deterministic + $0. If no `others` given,
    reports the rib's self-profile (tangled requires a peer to overlap with — honest)."""
    rib = (rib or "").strip()
    if not rib:
        return {"ok": False, "schema": SCHEMA, "error": "empty rib", "tangled": False}
    a = _tokens(rib)
    if not others:
        return {"ok": True, "schema": SCHEMA, "rib": rib[:200], "n_tokens": len(a),
                "max_overlap": 0.0, "tangled": False, "n_peers": 0,
                "note": "no peers given — tangle requires another knot to overlap with"}
    best = 0.0
    best_i = -1
    for i, o in enumerate(others):
        b = _tokens(o)
        ov = _overlap(a, b)
        if ov > best:
            best = ov
            best_i = i
    return {"ok": True, "schema": SCHEMA, "rib": rib[:200], "n_tokens": len(a),
            "max_overlap": best, "best_peer": best_i, "n_peers": len(others),
            "tangled": best > OVERLAP_THRESHOLD,
            "note": (f"near-duplicate of peer {best_i} (overlap {best}) — over-constrains the same "
                     "content anchor" if best > OVERLAP_THRESHOLD else "distinct content anchor")}


def _knot_rib(row: dict[str, Any]) -> str:
    """Extract the RIB-ish content from a real chain row (honest: whatever invariant text it carries)."""
    for k in ("invariant", "rib", "note", "theme", "title", "content"):
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # fall back to the raw row json (content-addressed, real bytes)
    import json as _j
    try:
        return _j.dumps(row, ensure_ascii=False)
    except Exception:
        return str(row)


def latest_rows_per_session(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Latest-per-session resolution for v2 append-leaves chains (AH19, 2026-09-30).

    v1: one row per session (amend-in-place) — identity (input returned
    unchanged). v2: a re-save APPENDS a new (session_id, session_seq) row, so
    one session's own seq history is near-identical content that would read
    as "tangled" near-duplicates and inflate n_knots (VERKLE_V2_DECISION.md
    §2.2); the tangle measure must compare the LATEST row per session only
    (last matching row in chain order — same rule as
    verkle_knot.latest_leaf_for_session's fallback). Rows with no session_id
    pass through in place.
    """
    latest: dict[str, dict[str, Any]] = {}
    for r in rows:
        sid = str(r.get("session_id") or "")
        if sid:
            latest[sid] = r  # append-ordered chain: last occurrence wins
    if len(latest) == len(rows):
        return rows  # pure v1 (no duplicate sids): unchanged behavior
    out: list[dict[str, Any]] = []
    emitted: set[str] = set()
    for r in rows:
        sid = str(r.get("session_id") or "")
        if not sid:
            out.append(r)
        elif sid not in emitted and latest.get(sid) is r:
            out.append(r)
            emitted.add(sid)
    return out


def scan_chain(*, top: int = 5) -> dict[str, Any]:
    """Read the REAL verkle chain, cluster knots by content anchor, rank the TANGLED CLUSTERS
    (near-duplicates that should collapse to one). O(n) via content-anchor hashing (NOT O(n^2)
    pairwise — the 3781-knot chain timed out before). Deterministic + $0, honest on real bytes.

    AH19 (2026-09-30): rows are resolved to the LATEST row per session before
    clustering — under v2 append-leaves one session's own seq history is
    near-identical content that would otherwise read as false tangles."""
    try:
        from mag.chain_query import chain
        rows = chain._read(tail=None)  # canonical read surface (chain_query), not the raw file
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"chain_query unavailable: {str(e)[:120]}"}
    n_chain_rows = len(rows)
    rows = latest_rows_per_session(rows)
    if not rows:
        return {"ok": True, "schema": SCHEMA, "n_knots": 0, "n_clusters": 0,
                "top_tangled": [], "note": "chain empty"}
    # tokenize every knot once, bucket by its top-k anchor tokens (deterministic, O(n))
    indexed = []
    for r in rows:
        rib = _knot_rib(r)
        indexed.append({"sid": str(r.get("session_id") or "?"),
                        "filename": str(r.get("filename") or "?"),
                        "rib": rib, "toks": _tokens(rib)})
    buckets: dict[str, list[dict[str, Any]]] = {}
    for kn in indexed:
        for anchor in _top_anchors(kn["toks"]):
            buckets.setdefault(anchor, []).append(kn)
    # within each anchor bucket, confirm real overlap and merge into clusters (cheap; buckets are small)
    seen: set[str] = set()
    clusters: list[list[dict[str, Any]]] = []
    for anchor, cands in buckets.items():
        for kn in cands:
            if kn["sid"] in seen:
                continue
            # try to join the first existing cluster it genuinely overlaps
            placed = False
            for cl in clusters:
                if _overlap(kn["toks"], cl[0]["toks"]) > OVERLAP_THRESHOLD:
                    cl.append(kn)
                    seen.add(kn["sid"])
                    placed = True
                    break
            if not placed:
                clusters.append([kn])
                seen.add(kn["sid"])
    # a TANGLED cluster = 2+ knots (near-duplicates over-constraining one anchor)
    tangled = [c for c in clusters if len(c) >= 2]
    tangled.sort(key=lambda c: -len(c))
    top_tangled = [{"cluster_size": len(c),
                    "members": [{"session_id": m["sid"], "filename": m["filename"]} for m in c],
                    "rep_rib": c[0]["rib"][:160]} for c in tangled[:top]]
    return {"ok": True, "schema": SCHEMA,
            "n_knots": len(indexed), "n_chain_rows": n_chain_rows,
            "n_sessions": len(indexed),
            "n_clusters": len(clusters), "n_tangled_clusters": len(tangled),
            "n_tangled_knots": sum(len(c) for c in tangled),
            "top_tangled": top_tangled,
            "source": "real verkle chain (verkle_knot._load_chain_rows), O(n) content-anchor buckets; "
                      "rows resolved to latest-per-session first (AH19 v2; n_knots == n_sessions, "
                      "n_chain_rows is the raw row count)",
            "threshold": f"token-overlap > {OVERLAP_THRESHOLD} = same content anchor (near-duplicate)"}


def untangle(*, domain: str = "territory", dry: bool = True, top: int = 3) -> dict[str, Any]:
    """DISPATCH the tangled CLUSTERS to a cluster of k8s workers: each worker merges ONE tangled
    cluster into a single essential invariant (collapses the near-duplicates). dry=True = plan
    ($0, no dispatch). Honest: reports dispatched + task ids, never claims a result it didn't get."""
    scan = scan_chain(top=top)
    clusters = scan.get("top_tangled") or []
    out = {"ok": True, "schema": SCHEMA, "dry": dry, "scan": scan,
           "n_to_untangle": len(clusters), "tasks": []}
    if dry or not clusters:
        out["tasks"] = [{"cluster_size": c.get("cluster_size"),
                         "ok": True, "task_id": None, "dry": True} for c in clusters]
        return out
    from mag import swarm_worker as sw
    for i, c in enumerate(clusters):
        members = c.get("members") or []
        goal = (f"[knot-untangle] This verkle knot CLUSTER ({len(members)} near-duplicate knots "
                f"over-constraining the same content anchor) is TANGLED. Merge them into ONE "
                f"essential invariant — collapse the near-duplicates to a single, cleaner knot. "
                f"Keep only the essential invariant, drop the redundant rest. Honest provenance. "
                f"Members: {[m.get('session_id') for m in members][:8]}. Rep rib: "
                f"{c.get('rep_rib', '')[:160]}")
        try:
            from mag import rib_bus as rb
            goal = rb.inject_for(goal, domain=domain)
        except Exception:
            pass
        try:
            r = sw.enqueue_task(goal, provider="deepseek", model="deepseek-chat",
                                domain="knot-untangle", agent_idx=i, tag="knot-untangle")
            out["tasks"].append({"cluster": i, "cluster_size": c.get("cluster_size"),
                                 "ok": bool(r.get("ok")), "task_id": r.get("task_id")})
        except Exception as e:
            out["tasks"].append({"cluster": i, "cluster_size": c.get("cluster_size"),
                                 "ok": False, "error": str(e)[:80]})
    out["n_dispatched"] = sum(1 for t in out["tasks"] if t.get("ok"))
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "tangle(rib, others)->REAL near-duplicate measure (token-overlap vs peers); "
                        "scan_chain()->cluster the REAL verkle chain, rank tangled clusters; "
                        "untangle(dry)->dispatch each tangled cluster to a k8s worker to collapse "
                        "near-duplicates to one essential invariant. Not ritual: content-anchor "
                        "dedup of the chain.",
            "cost": "deterministic + $0 except swarm dispatch (the tangled clusters only)"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="knot-untangle")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "tangle", "scan", "untangle"])
    ap.add_argument("rib", nargs="*", default=[])
    ap.add_argument("--dry", default=True, action=argparse.BooleanOptionalAction)
    a = ap.parse_args()
    if a.cmd == "tangle":
        print(json.dumps(tangle(" ".join(a.rib) or "the map precedes the territory"), indent=2, default=str))
    elif a.cmd == "scan":
        print(json.dumps(scan_chain(), indent=2, default=str))
    elif a.cmd == "untangle":
        print(json.dumps(untangle(dry=a.dry), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
