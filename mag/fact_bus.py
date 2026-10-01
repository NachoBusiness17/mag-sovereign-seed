"""fact_bus — fold FACTS into the verkle chain + bus, surfaced easily (like rib_bus for invariants).

Operator (2026-08-11): "how can we start logging these facts in the verkle chain so we can surface
them more easily. like the same mechanism to build invariants for code instruction."

Same mechanism as rib_bus (invariant -> verkle fold + store + bus), generalized to FACTS. Each fact
carries the 5 W's (who/what/when/where/why) so it surfaces readably:
  publish_fact(fact, who, what, when, where, why, domain) -> fold as verkle knot + append to
  memory/facts/<domain>.jsonl + publish to mag:fact (real-time sync).
  surface(domain, n) -> the easy retrieval of recent facts by domain.

Deterministic + $0 (fold/publish/store all local). Schema: fact_bus.v1
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

SCHEMA = "fact_bus.v1"
FACT_DIR = ROOT / "memory" / "facts"
CH_FACT = "mag:fact"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fact_file(domain: str) -> Path:
    d = (domain or "general").strip().lower().replace(" ", "-")[:60] or "general"
    return FACT_DIR / f"{d}.jsonl"


def _fact_key(domain: str, what: str) -> str:
    return hashlib.sha256(f"{domain}\x1f{what}".encode("utf-8")).hexdigest()[:16]


def _fold_verkle(domain: str, fact: dict[str, Any]) -> dict[str, Any]:
    try:
        from mag.verkle_knot import append_verkle_knot
        minute = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        dossier = {
            "session_id": f"fact_bus_{domain}",
            "time": {
                "created_at": {"iso_minute": minute, "unix_minute": None, "date": None},
                "updated_at": {"iso_minute": minute, "unix_minute": None, "date": None},
            },
            "scalar_knot": {
                "duration_minutes": 0.1,
                "tension_index": str(len(fact.get("what") or ""))[:8],
                "residual_weight": 1.0,
                "theme_vector": {
                    "dominant": f"fact_{domain}",
                    "basis": ["fact", "who", "when", "where", "why"],
                    "raw": [1.0, 0.0, 0.0, 0.0],
                    "normalized": [1.0, 0.0, 0.0, 0.0],
                },
            },
            "content_commit": {"hex": _fact_key(domain, fact.get("what") or "")},
            "fact": {k: str(v)[:400] for k, v in fact.items()},
        }
        return append_verkle_knot(dossier)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _publish(domain: str, fact: dict[str, Any]) -> bool:
    try:
        from mag import verkle_bus
        return bool(verkle_bus.publish_sync(
            CH_FACT, {"type": "fact", "domain": domain, "fact": fact}))
    except Exception:
        return False


def publish_fact(fact: str, *, who: str = "", what: str = "", when: str = "",
                 where: str = "", why: str = "", domain: str = "general",
                 fold: bool = True, publish: bool = True) -> dict[str, Any]:
    """Fold ONE fact (5 W's) into the verkle chain + store + bus. Deterministic + $0."""
    what = what or fact
    what = (what or "").strip()
    if not what:
        return {"ok": False, "error": "empty fact"}
    record = {"fact": fact[:400], "who": who[:120], "what": what[:400],
              "when": when or _now(), "where": where[:160], "why": why[:400], "ts": _now()}
    f = _fact_file(domain)
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    knot = _fold_verkle(domain, record) if fold else {}
    pub = _publish(domain, record) if publish else False
    return {"ok": True, "schema": SCHEMA, "domain": domain, "key": _fact_key(domain, what),
            "store_path": str(f), "verkle": knot, "published": pub, "fact": record}


def surface(domain: str = "general", n: int = 10) -> dict[str, Any]:
    """EASY surfacing: the recent facts for a domain, newest first (5 W's each). Deterministic."""
    f = _fact_file(domain)
    facts = []
    if f.is_file():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                facts.append(json.loads(line))
            except Exception:
                continue
    facts = facts[-max(1, int(n)):]
    facts.reverse()
    return {"ok": True, "schema": SCHEMA, "domain": domain, "n": len(facts), "facts": facts}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="fact-bus")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("publish")
    p.add_argument("fact")
    p.add_argument("--who", default="")
    p.add_argument("--what", default="")
    p.add_argument("--where", default="")
    p.add_argument("--why", default="")
    p.add_argument("--domain", default="general")
    sub.add_parser("surface").add_argument("--domain", default="general")
    a = ap.parse_args(argv)
    if a.cmd == "publish":
        print(json.dumps(publish_fact(a.fact, who=a.who, what=a.what, where=a.where,
                                      why=a.why, domain=a.domain), indent=2, default=str))
    else:
        print(json.dumps(surface(a.domain), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
