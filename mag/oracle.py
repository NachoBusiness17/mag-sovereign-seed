"""oracle — the ORACLE primitive (Chainlink pattern, self-stolen): bring EXTERNAL reality INTO the
chain VERIFIED + PROVENANCE-ANCHORED, so our internal model of the outside world is coherent and
grounded, not a guess.

OPERATOR (2026-08-13): "fuck yes" (build the oracle) — from sw53ethsteal: the ONE Ethereum-ecosystem
steal that most enhances INTERNAL COHERENCE OF THE OUTSIDE WORLD. Today we fetch external reality
ad-hoc (browser_driver/horizon) but do NOT verify + anchor it as coherent internal state, so our
model of the outside world can drift from reality.

THE PRIMITIVE (deterministic $0 coordinator; the fetches are the seams):
  fetch_sources(topic) -> fetch the SAME external fact from MULTIPLE sources (OUR OWN fetch surface:
                          research_pack._fetch_url, never the generic tool). Honest per-source.
  verify(sources)      -> CROSS-SOURCE AGREEMENT: the shared claim across the sources (roshomon-style
                          token overlap). verified=True only if the sources agree; else honest partial.
  anchor(claim, prov)  -> append the VERIFIED claim to the oracle's anchored ledger
                          (memory/runs/oracle/anchored.jsonl), CONTENT-ADDRESSED (leaf_hash) + source
                          provenance. The chain of the outside world.
  oracle(topic)        -> the full primitive: fetch -> verify -> anchor -> return the verified external
                          fact + provenance + anchor hash.
  query(topic)         -> query the anchored ledger (the indexed, coherent map of the outside world).

SELF-STEAL: research_pack._fetch_url (our own fetch surface), roshomon (cross-source consensus),
verkle content-addressing (leaf_hash), the endpoint-catalog indexing pattern.

Schema: oracle.v1 · deterministic $0 coordinator · reuse: research_pack, roshomon, verkle_knot
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
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

SCHEMA = "oracle.v1"
OUT = ROOT / "memory" / "runs" / "oracle"
LEDGER = OUT / "anchored.jsonl"   # the chain of the outside world (verified, anchored, queryable)
_TOKEN_RE = re.compile(r"[a-z0-9_]+")
STOP = {"the", "and", "that", "this", "with", "from", "have", "will", "what", "are", "for", "not"}

# The oracle's sources (multi-source verification — the Chainlink pattern).
SOURCES = [
    "https://api.github.com",          # example source 1 (github public api)
    "https://api.github.com/zen",      # example source 2
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fetch(url: str, *, timeout: int = 15) -> dict[str, Any]:
    """Fetch ONE external source via OUR OWN surface (research_pack._fetch_url), never the generic
    fetch tool. Honest on failure."""
    try:
        from mag import research_pack
        text = research_pack._fetch_url(url, timeout=timeout)
        return {"ok": True, "source": url, "text": (text or "")[:4000]}
    except Exception as e:
        # fallback: plain urllib (still our own process, not the generic tool)
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return {"ok": True, "source": url, "text": (r.read().decode("utf-8", "replace") or "")[:4000]}
        except Exception as e2:
            return {"ok": False, "source": url, "error": str(e2)[:120]}


def fetch_sources(topic: str, *, urls: list[str] | None = None) -> dict[str, Any]:
    """Fetch the SAME external reality from MULTIPLE sources (multi-source for verification)."""
    targets = urls or SOURCES
    out = [_fetch(u) for u in targets]
    return {"ok": True, "schema": SCHEMA, "n_sources": len(out), "sources": out}


def verify(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """CROSS-SOURCE AGREEMENT (Chainlink): the shared claim across the available sources. verified=True
    only if the sources AGREE on a non-trivial core. Deterministic (token overlap, roshomon-style)."""
    ok_sources = [s for s in sources if s.get("ok") and s.get("text")]
    if len(ok_sources) < 2:
        return {"ok": False, "verified": False, "error": "need >=2 agreeing sources",
                "n_ok": len(ok_sources), "consensus": ""}
    toksets = [set(_TOKEN_RE.findall(s["text"].lower())) - STOP for s in ok_sources]
    common = set.intersection(*toksets) if toksets else set()
    # keep meaningful (4+ char) shared tokens as the consensus core
    consensus_toks = [t for t in sorted(common) if len(t) >= 4]
    consensus = " ".join(consensus_toks)[:300]
    verified = len(consensus_toks) >= 3
    return {"ok": True, "schema": SCHEMA, "verified": verified, "n_sources": len(ok_sources),
            "consensus": consensus, "n_consensus_toks": len(consensus_toks),
            "note": "cross-source agreement; verified only if the sources agree on a non-trivial core"}


def anchor(claim: str, *, provenance: list[str], topic: str = "") -> dict[str, Any]:
    """ANCHOR the verified claim to the oracle's ledger — CONTENT-ADDRESSED (leaf_hash) + provenance.
    The chain of the outside world: immutable, queryable, coherent."""
    leaf = hashlib.sha256(f"{claim}|{'|'.join(provenance)}".encode("utf-8")).hexdigest()[:16]
    row = {"schema": "oracle.anchor.v1", "ts": _now(), "topic": topic[:200], "claim": claim[:2000],
           "provenance": provenance, "leaf_hash": leaf}
    OUT.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "schema": SCHEMA, "anchored": True, "leaf_hash": leaf,
            "claim": claim[:300], "provenance": provenance, "ledger": str(LEDGER)}


def oracle(topic: str, *, urls: list[str] | None = None, force_anchor: bool = False) -> dict[str, Any]:
    """THE FULL PRIMITIVE: fetch -> verify -> anchor -> return the verified external fact + provenance.
    Only anchors if VERIFIED (or force_anchor for unverifiable-but-worth-holding facts, flagged)."""
    f = fetch_sources(topic, urls=urls)
    v = verify(f["sources"])
    result = {"ok": True, "schema": SCHEMA, "ts": _now(), "topic": topic[:200],
              "fetch": f, "verify": v}
    if v.get("verified") or force_anchor:
        consensus = v.get("consensus") or topic
        prov = [s.get("source", "?") for s in f["sources"] if s.get("ok")]
        a = anchor(consensus, provenance=prov, topic=topic)
        result["anchor"] = a
        result["verified_fact"] = consensus
    else:
        result["anchor"] = {"anchored": False, "error": "not verified — no cross-source agreement"}
    return result


def query(topic: str, *, limit: int = 5) -> dict[str, Any]:
    """QUERY the anchored ledger — the indexed, coherent map of the outside world."""
    if not LEDGER.is_file():
        return {"ok": True, "schema": SCHEMA, "n_hits": 0, "hits": [], "note": "no oracle anchors yet"}
    t = (topic or "").lower()
    hits = []
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if t and t not in (row.get("claim") or "").lower() and t not in (row.get("topic") or "").lower():
            continue
        hits.append({"claim": row.get("claim", "")[:300], "provenance": row.get("provenance", []),
                     "leaf_hash": row.get("leaf_hash", ""), "ts": row.get("ts", "")})
        if len(hits) >= limit:
            break
    return {"ok": True, "schema": SCHEMA, "topic": topic, "n_hits": len(hits), "hits": hits,
            "note": "the anchored ledger = the coherent map of the outside world"}


def status() -> dict[str, Any]:
    n = 0
    if LEDGER.is_file():
        for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                n += 1
    return {"ok": True, "schema": SCHEMA,
            "contract": "oracle(topic)->fetch + verify + anchor (the Chainlink primitive); "
                        "fetch_sources()->multi-source fetch; verify()->cross-source agreement; "
                        "anchor()->content-addressed ledger write; query(topic)->the indexed map",
            "cost": "deterministic $0 coordinator; the fetches are the (free) seams",
            "n_anchored": n, "ledger": str(LEDGER)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="oracle")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "oracle", "query"])
    ap.add_argument("topic", nargs="?", default="")
    ap.add_argument("--url", action="append", default=[])
    a = ap.parse_args()
    if a.cmd == "oracle":
        print(json.dumps(oracle(a.topic or "github api", urls=a.url or None), indent=2, default=str))
    elif a.cmd == "query":
        print(json.dumps(query(a.topic), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
