"""trust_gate — the SANITY SYSTEM: only NOVEL, DEDUPED, HIGH-TRUST data writes to the chain,
not poison. Sits in front of the swarm tools (verkle_write, memlance fold, corpus ingest).

Operator (2026-08-12): "how can we have some sanity system around this so it's only novel deduped
high trust data and not poisoning?"

THE GATE (deterministic + $0, three checks before anything writes):
  1. NOVELTY  — dedupe by invariant (canonical content-hash). Already-seen = REJECT (duplicate
                spam is the #1 poisoning vector in a terabyte corpus).
  2. TRUST    — score provenance: source reputation (operator=1.0, frontier/grok=0.8,
                swarm-worker=0.6, unknown=0.3) + groundedness (real bytes present, not fabricated)
                + doctrine alignment (resonates with our mounted RIBs).
  3. POISON   — heuristics: low entropy (repetitive spam), fabrication markers, forbidden
                patterns, anomaly.
  VERDICT (MemSentry 4-way, fold row agent-memory-sota#0):
    ACCEPT     novel + high-trust + clean -> write (trust_score stamped in the register)
    REVIEW     SUSPICIOUS but from a TRUSTED source (source_trust >= TRUST_THRESHOLD) -> held in
               quarantine AND an advisory is routed to operator_inbox (human review tier).
               Trusted-source suspicions are escalated to the operator instead of silently
               excluded (the old v1 behavior quarantined them with no notification).
    QUARANTINE suspicious from an UNTRUSTED source -> held in quarantine, never auto-written,
               no operator advisory (untrusted content does not earn operator attention)
    REJECT     duplicate / low-trust -> drop. Nothing suspicious or low-trust ever auto-writes:
               the ingest stays fail-closed.
  The accepted-writes register (seen.json) carries a trust_score per entry; quarantine/review
  records carry trust_score + verdict too, so every gate decision is auditable from disk.

Schema: trust_gate.v2 · reuse: percolator (dedupe), rib_bus (doctrine), ghost_leak_detector,
        operator_inbox (the Review advisory tier)
"""
from __future__ import annotations

import hashlib
import json
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

SCHEMA = "trust_gate.v2"
GATE_DIR = ROOT / "memory" / "trust_gate"
SEEN_FILE = GATE_DIR / "seen.json"          # accepted-writes register (hash -> ts/source/domain/trust_score)
QUARANTINE_DIR = GATE_DIR / "quarantine"

# Source reputation (provenance trust). Operator = highest; unknown = lowest.
SOURCE_TRUST = {"operator": 1.0, "grok-bot": 0.8, "frontier": 0.8, "grok": 0.8,
                "swarm-worker": 0.6, "swarm": 0.6, "bot": 0.6, "seed": 0.5, "unknown": 0.3}
TRUST_THRESHOLD = 0.6


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(content: str) -> str:
    return hashlib.sha256(" ".join((content or "").lower().split()).encode("utf-8")).hexdigest()[:20]


def _load_seen() -> dict[str, Any]:
    if SEEN_FILE.is_file():
        try:
            return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"seen": {}}


def _save_seen(seen: dict[str, Any]) -> None:
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 1. NOVELTY (dedupe by invariant — kills duplicate poisoning) ──────────────
def novelty(content: str) -> dict[str, Any]:
    """Dedupe check: is this content ALREADY in the chain? Duplicate = the #1 poisoning vector.
    Deterministic + $0."""
    c = _canonical(content or "")
    seen = _load_seen()
    already = c in seen["seen"]
    return {"ok": not already, "novel": not already, "hash": c,
            "count": seen["seen"].get(c, 0), "note": "already-seen" if already else "novel"}


# ── 2. TRUST (provenance + groundedness + doctrine alignment) ─────────────────
def trust(content: str, source: str = "unknown") -> dict[str, Any]:
    """Trust score 0..1: source reputation + groundedness (real bytes) + doctrine alignment.
    High-trust only. Deterministic + $0."""
    src = (source or "unknown").lower()
    rep = SOURCE_TRUST.get(src, 0.3)
    # groundedness: real content present (not an empty/fabricated shell)
    grounded = 1.0 if (content or "").strip() and len(content.strip()) >= 20 else 0.0
    # doctrine alignment: does it resonate with our mounted RIBs? (weak proxy, honest)
    alignment = 0.5
    try:
        from mag import rib_bus
        m = rib_bus.mount("general")
        ribs = " ".join(m.get("ribs", []))
        if ribs:
            toks = set(ribs.lower().split())
            hits = sum(1 for w in set((content or "").lower().split()) if w in toks)
            alignment = min(1.0, 0.3 + hits * 0.1)
    except Exception:
        pass
    score = round(0.5 * rep + 0.35 * grounded + 0.15 * alignment, 3)
    return {"ok": score >= TRUST_THRESHOLD, "score": score, "source": src,
            "source_trust": rep, "grounded": grounded, "alignment": alignment,
            "threshold": TRUST_THRESHOLD}


# ── 3. POISON (heuristics: entropy, fabrication markers, forbidden) ───────────
def poison(content: str) -> dict[str, Any]:
    """Poison heuristics: low entropy (repetitive spam), fabrication markers, forbidden patterns.
    Suspicious flags. Deterministic + $0."""
    c = (content or "").strip()
    flags: list[str] = []
    if len(c) >= 20:
        # entropy: a repetitive duplicate-heavy string (spam) has low unique-token ratio
        toks = c.lower().split()
        if len(toks) > 10 and len(set(toks)) / len(toks) < 0.3:
            flags.append("low-entropy-repeat")
        # fabrication markers (the honesty law): claims of work w/o evidence
        low = c.lower()
        if any(m in low for m in ("i did x", "trust me", "no tools needed", "just believe")):
            flags.append("fabrication-marker")
        if "password=" in low or "api_key=" in low or "secret=" in low:
            flags.append("secret-leak")
    return {"ok": len(flags) == 0, "poisoned": len(flags) > 0, "flags": flags}


# ── THE GATE ──────────────────────────────────────────────────────────────────
def _is_trusted_source(source: str) -> bool:
    """A source is trusted when its reputation meets the trust threshold
    (operator/grok/frontier/swarm-worker yes; seed/unknown no)."""
    return SOURCE_TRUST.get((source or "unknown").lower(), 0.3) >= TRUST_THRESHOLD


def _route_review(content: str, *, source: str, domain: str, flags: list[str],
                  t: dict[str, Any], qpath: Path) -> dict[str, Any]:
    """REVIEW tier: route a trusted-source suspicion to operator_inbox (advisory, never
    auto-applied) so the operator sees the exclusion instead of it happening silently.
    Best-effort: an inbox failure never un-holds the item (fail-closed preserved)."""
    advisory = (
        f"[trust_gate REVIEW] trusted source '{source}' gated on domain '{domain}' "
        f"(trust_score {t['score']}, flags: {', '.join(flags)}). Held, not written. "
        f"Examine and admit or drop: {qpath.as_posix()} :: {(content or '')[:160]}"
    )
    routed = False
    detail = ""
    try:
        from mag import operator_inbox
        res = operator_inbox.commit_guidance(advisory, source="trust_gate")
        routed = bool(res.get("ok"))
        detail = str(res.get("item", {}).get("id") or res.get("error") or "")
    except Exception as e:  # inbox unavailable — the quarantine hold stands either way
        detail = f"inbox route failed: {str(e)[:120]}"
    return {"routed": routed, "channel": "operator_inbox.commit_guidance", "detail": detail,
            "advisory": advisory}


def gate(content: str, *, source: str = "unknown", domain: str = "general") -> dict[str, Any]:
    """The full SANITY GATE (MemSentry 4-way): NOVEL + HIGH-TRUST + CLEAN -> ACCEPT (write);
    suspicious from a trusted source -> REVIEW (held + operator_inbox advisory); suspicious
    from an untrusted source -> QUARANTINE (held); duplicate / low-trust -> REJECT (drop).
    Only ACCEPT writes. Deterministic + $0."""
    n = novelty(content)
    t = trust(content, source)
    p = poison(content)
    review: dict[str, Any] | None = None
    if not n["novel"]:
        verdict = "REJECT"
        reason = "duplicate (already in the chain — poisoning via spam)"
    elif not t["ok"]:
        verdict = "REJECT"
        reason = f"low-trust (score {t['score']} < {TRUST_THRESHOLD}, source '{source}')"
    elif not p["ok"]:
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
        trusted = _is_trusted_source(source)
        verdict = "REVIEW" if trusted else "QUARANTINE"
        qpath = QUARANTINE_DIR / f"q-{n['hash']}.json"
        qpath.write_text(
            json.dumps({"schema": SCHEMA, "ts": _now(), "verdict": verdict,
                        "source": source, "domain": domain, "flags": p["flags"],
                        "trust_score": t["score"], "content": (content or "")[:1000]},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        if trusted:
            reason = (f"suspicious ({', '.join(p['flags'])}) from trusted source '{source}' "
                      f"— held + advisory routed to operator_inbox (human review)")
            review = _route_review(content, source=source, domain=domain, flags=p["flags"],
                                   t=t, qpath=qpath)
            stamped = json.loads(qpath.read_text(encoding="utf-8"))
            stamped["review"] = {"routed": review["routed"], "channel": review["channel"]}
            qpath.write_text(json.dumps(stamped, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        else:
            reason = f"suspicious ({', '.join(p['flags'])}) from source '{source}' — held, not auto-written"
    else:
        verdict = "ACCEPT"
        reason = "novel + high-trust + clean"
    if verdict == "ACCEPT":
        seen = _load_seen()
        seen["seen"][n["hash"]] = {"ts": _now(), "source": source, "domain": domain,
                                   "trust_score": t["score"]}
        _save_seen(seen)
    return {"ok": True, "schema": SCHEMA, "verdict": verdict, "reason": reason,
            "novelty": n, "trust": t, "poison": p, "domain": domain,
            "trusted_source": _is_trusted_source(source),
            "review": review,
            "note": f"{verdict}: {reason}"}


def status() -> dict[str, Any]:
    seen = _load_seen()
    n_q = n_review = 0
    if QUARANTINE_DIR.is_dir():
        for f in QUARANTINE_DIR.glob("q-*.json"):
            n_q += 1
            try:
                if json.loads(f.read_text(encoding="utf-8")).get("verdict") == "REVIEW":
                    n_review += 1
            except Exception:
                pass
    return {"ok": True, "schema": SCHEMA, "n_accepted": len(seen.get("seen", {})),
            "n_quarantined": n_q, "n_review": n_review,
            "contract": "gate(content, source)->ACCEPT (novel+high-trust+clean, trust_score "
                        "stamped in register) / REVIEW (suspicious+trusted-source: held + "
                        "operator_inbox advisory) / QUARANTINE (suspicious+untrusted: held) / "
                        "REJECT (duplicate/low-trust). Only ACCEPT writes."}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="trust-gate")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "gate"])
    ap.add_argument("text", nargs="*", default=[])
    ap.add_argument("--source", default="unknown")
    a = ap.parse_args(argv)
    if a.cmd == "gate":
        print(json.dumps(gate(" ".join(a.text) or "sample", source=a.source),
                         ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
