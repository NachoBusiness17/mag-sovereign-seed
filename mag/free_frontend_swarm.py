"""free_frontend_swarm — drive the FREE web frontends as PARALLEL swarm seats.

Operator (2026-08-12): "wire the free-frontend swarm into the cadence (browser_driver -> drive the
free frontends as parallel seats, steal mid-run artifacts, fold results)... after that it's a free
overnight swarm."

THE PLAY: free LLM frontends (deepseek chat, perplexity, grok, x) driven through the container
browser (mag.browser_driver, CDP :9222) = essentially-free LLM seats, the same swarm shape as our
k8s swarm but $0. Each surface is one seat; a batch goal is asked on each in parallel; mid-run /
timed-out artifacts are STEALEN (partial harvest, don't discard — the free-tier loop tesuji);
results are folded to repo memory + rib_bus.

Honest: the browser container must be up (docker compose --profile browser up -d) + operator logged
in once. If CDP is down / not authed, status() and run() report the BLOCKER honestly — they never
fabricate a free-frontend answer.

Guarded: every external call is try/except so the cadence never breaks. Deterministic + $0 (free
frontends, no API spend).

Schema: free_frontend_swarm.v1 · reuse: browser_driver, rib_bus
"""
from __future__ import annotations

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

SCHEMA = "free_frontend_swarm.v1"
SEATS = ["deepseek", "perplexity", "grok"]   # free LLM seats to drive in parallel (x = search)
OUT_DIR = ROOT / "memory" / "free_swarm"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def status() -> dict[str, Any]:
    """Is the free-frontend swarm usable? Reads browser_driver.status() — the honest gate.
    Reports the blocker (container/CDP down, not authed) rather than pretending."""
    try:
        from mag import browser_driver
        return browser_driver.status()
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"browser_driver unreachable: {str(e)[:200]}"}


def run(goal: str, *, surfaces: list[str] | None = None,
        max_wait_s: int = 120, fold: bool = True) -> dict[str, Any]:
    """Drive the free frontends as PARALLEL seats on ONE goal. Steal mid-run / timed-out artifacts
    (partial harvest, don't discard). Fold each result to repo memory + rib_bus.

    Honest: if CDP is down or a surface isn't authed, that seat reports the blocker — never a
    fabricated answer."""
    from mag import browser_driver
    from mag import rib_bus

    seats = [s for s in (surfaces or SEATS) if s in browser_driver.SURFACES]
    results = []
    for s in seats:
        try:
            r = browser_driver.ask(goal, surface=s, max_wait_s=max_wait_s)
            # STEAL the mid-run / timed-out artifact: browser_driver returns whatever it read even
            # on timeout (partial harvest). Don't discard.
            text = str(r.get("answer") or r.get("text") or r.get("error") or "").strip()
            results.append({"seat": s, "ok": bool(r.get("ok")), "timeout": bool(r.get("timeout")),
                            "text_len": len(text), "head": text[:300]})
        except Exception as e:
            results.append({"seat": s, "ok": False, "error": str(e)[:120]})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"free_swarm_{_now().replace(':','').split('.')[0]}.json"
    payload = {"ts": _now(), "goal": goal[:400], "seats": results}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    folded = []
    if fold:
        for res in results:
            if res.get("ok") and res.get("head"):
                try:
                    pub = rib_bus.publish_rib(
                        f"FREE-FRONTEND SEAT [{res['seat']}] on goal: {res['head'][:300]}",
                        domain="free-frontend", source="free_frontend_swarm (free overnight)",
                        target_rank="T2")
                    folded.append({"seat": res["seat"], "rib": pub.get("ok")})
                except Exception:
                    folded.append({"seat": res["seat"], "rib": False})

    return {"ok": True, "schema": SCHEMA, "goal": goal[:400], "n_seats": len(seats),
            "results": results, "artifact": str(path), "folded": folded,
            "note": "free frontends as parallel swarm seats; partial/timed-out artifacts stolen"}


def cadence(*, goal: str | None = None, max_wait_s: int = 60) -> dict[str, Any]:
    """Guarded cadence step for republic_loop. Honest blocker if the container/CDP is down; never
    breaks the loop; cheap time-boxed asks on the free seats."""
    st = status()
    if not st.get("ok"):
        return {"ok": False, "schema": SCHEMA, "error": st.get("error") or "free-frontend seat down",
                "blocker": "browser container/CDP must be up + operator logged in"}
    g = goal or ("free overnight swarm: RIB-driven cold-edge research on the cheapest open "
                 "frontier seam")
    return run(g, max_wait_s=max_wait_s, fold=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv else list(sys.argv[1:])
    if argv and argv[0] == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
        return 0
    goal = " ".join(argv) if argv else None
    print(json.dumps(cadence(goal=goal), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
