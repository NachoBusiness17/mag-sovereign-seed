"""one_sizer — shared store: domain × skill × shape → cheapest-capable tier.

Weaves the right-sizer's joined knowledge ACROSS domains so whisper/memlang can
resolve "what is the cheapest capable tier for this (skill, domain, shape)?" from
learned rows instead of recomputing the stateless right-sizer every time. Learning
layers (skill_pipeline._fold) WRITE here; the store is READ by whisper/memlang
(deniable: memlang carries only opcode + anchor hash; the tier never rides the wire).

Schema: one_sizer.v1
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "one_sizer.v1"
STORE = ROOT / "memory" / "learn" / "sizing.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rows() -> list[dict[str, Any]]:
    if not STORE.is_file():
        return []
    out = []
    for line in STORE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def record_sizing(*, skill: str, domain: str = "general", shape: str = "balanced",
                  effective_tier: str, model: str = "", ok: bool = True) -> dict[str, Any]:
    """Append a sizing observation: a (skill, domain, shape) landed on a tier/model.
    Called by skill_pipeline.run's fold hook — this is what joins knowledge across domains."""
    STORE.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": SCHEMA, "ts": _now(), "skill": (skill or "?"), "domain": (domain or "general"),
        "shape": (shape or "balanced"), "effective_tier": (effective_tier or "flash"),
        "model": model or "", "ok": bool(ok),
    }
    with STORE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "row": row}


def resolve_sizing(*, shape: str | None = None, domain: str | None = None,
                   skill: str | None = None) -> dict[str, Any]:
    """Cheapest-capable (tier, model) for a (domain, shape[, skill]) from learned rows.
    Most-specific match first: (domain,shape) -> (domain) -> (shape) -> any. Mode vote over
    ok rows. Returns found=False (never errors) when there is no learned data yet."""
    rows = _rows()
    shape = (shape or "balanced").lower()
    domain = (domain or "general").lower()
    if not rows:
        return {"ok": True, "found": False, "effective_tier": None, "model": None,
                "shape": shape, "domain": domain, "skill": skill,
                "note": "no learned sizing rows yet"}

    def pick(cands: list[dict[str, Any]]) -> tuple[str, str] | None:
        ok_rows = [r for r in cands if r.get("ok")]
        if not ok_rows:
            return None
        c = Counter((str(r.get("effective_tier") or "flash"), str(r.get("model") or ""))
                    for r in ok_rows)
        return c.most_common(1)[0][0]

    cands = [
        [r for r in rows if str(r.get("shape")) == shape and str(r.get("domain")) == domain],
        [r for r in rows if str(r.get("domain")) == domain],
        [r for r in rows if str(r.get("shape")) == shape],
        rows,
    ]
    for group in cands:
        m = pick(group)
        if m:
            return {"ok": True, "found": True, "effective_tier": m[0], "model": m[1],
                    "shape": shape, "domain": domain, "skill": skill,
                    "note": "resolved from joined one-sizer store (cross-domain)"}
    return {"ok": True, "found": False, "effective_tier": None, "model": None,
            "shape": shape, "domain": domain, "skill": skill,
            "note": "no matching learned row"}


def stats() -> dict[str, Any]:
    rows = _rows()
    if not rows:
        return {"ok": True, "rows": 0, "domains": [], "note": "empty store"}
    from collections import defaultdict
    by_domain: dict[str, int] = defaultdict(int)
    for r in rows:
        by_domain[str(r.get("domain") or "general")] += 1
    return {"ok": True, "rows": len(rows),
            "domains": dict(sorted(by_domain.items(), key=lambda kv: -kv[1]))}


def main(argv: list[str] | None = None) -> int:
    import sys as _sys
    argv = list(_sys.argv[1:] if argv is None else argv)
    import json as _json
    if argv and argv[0] == "resolve":
        shape = argv[1] if len(argv) > 1 else None
        domain = argv[2] if len(argv) > 2 else None
        print(_json.dumps(resolve_sizing(shape=shape, domain=domain), indent=2, default=str))
    elif argv and argv[0] == "stats":
        print(_json.dumps(stats(), indent=2, default=str))
    else:
        print(_json.dumps(stats(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
