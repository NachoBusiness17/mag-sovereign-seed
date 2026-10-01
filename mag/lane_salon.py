"""lane_salon — the frontier salon, made to work with the seats we ACTUALLY have.

Operator (2026-08-24): "look at all the seats you do have. look at what it was attempting and
make it work. i was just simply attempting what you are now capable of."

The ORIGINAL frontier_salon was a sacred cow that hung forever: it reached ChatGPT/SuperGrok via
the CDP browser seats (down), so it sat waiting instead of answering. The IDEA was right — many
seats witness the same question, then their answers are combined. This module makes it WORK by
using the seats that ARE reachable: the API lanes (models.providers.chat_provider — verified:
nvidia, openrouter, groq, together, deepseek), all with real timeouts, honest down-reporting.

  salon(question) -> every reachable API lane witnesses the SAME question, then the answers are
                     combined: roshomon-style shared invariant (token overlap = the consensus) +
                     each seat's distinct contribution. Honest: a down lane reports down, never
                     fabricates. FREE-FIRST: the paid lane (deepseek-pro) only joins off-peak
                     (mag.offpeak) unless MAG_ALLOW_PEAK=1.

Schema: lane_salon.v1 · deterministic + $0 coordinator · reuse: models.providers.chat_provider,
roshomon (consensus), offpeak (paid-lane gating)
CLI: python -m mag.lane_salon salon "<question>" [--lanes nvidia,openrouter,...]
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "lane_salon.v1"
OUT = ROOT / "memory" / "runs" / "lane_salon"

# The witnesses — the API lanes that actually work (verified today):
# (label, provider_id, model or None=provider default, paid?).
WITNESSES: list[tuple[str, str, str | None, bool]] = [
    ("grok-cli", "grok-tandem", None, False),  # subscription CLI headless (mag/grok_tandem), $0
    ("nvidia-flash", "nvidia", "deepseek-ai/deepseek-v4-flash-0731", False),
    ("openrouter", "openrouter", "openrouter/auto", False),
    ("groq", "groq", None, False),
    ("cerebras", "cerebras", "gpt-oss-120b", False),
    ("together", "together", None, True),  # trial/paid — off-peak
    ("deepseek-pro", "deepseek", None, True),  # paid — off-peak only
]
# B2-133 DORMANT GATE (2026-09-26): a provider declared dormant in configs/providers.yaml
# never witnesses (mag/doctor.py:607: dormant is a declared state). B2-36 set cerebras
# dormant (card-gated 30-day trial, chat 402 no-credit); the same gate catches nvidia
# (dormant per B2-61, 410 EOL). Operator GO flips the flag and the witness returns,
# no code edit. Receipt: watch/inbox/burn_wave_20260926/B2_133_cerebras_purge_20260926.md
from mag.dormant import dormant_ids as _dormant_provider_ids

WITNESSES = [w for w in WITNESSES if w[1] not in _dormant_provider_ids()]
ROOM = ROOT / "watch" / "room.jsonl"

_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_TRIVIAL = {"that", "this", "with", "from", "have", "will", "what", "would", "your",
            "there", "they", "should", "their", "about"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _room(seat: str, event: str, text: str, thread: str = "salon", **extra: Any) -> None:
    rec = {"ts": _now(), "seat": seat, "event": event, "thread": thread, "text": (text or "")[:4000]}
    rec.update(extra)
    try:
        with ROOM.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except OSError:
        pass


def _witness(label: str, provider: str, model: str | None, paid: bool, question: str) -> dict[str, Any]:
    """Ask ONE lane via the API surface (chat_provider). Honest down-reporting, never fabricates.
    Paid lanes defer off-peak unless MAG_ALLOW_PEAK=1 (free-first)."""
    if paid:
        # SPEC (2026-09-25, t78): this gate FAILED OPEN (the t52 species): an errored
        # defer_if_peak read was swallowed by 'except Exception: pass' and the paid
        # witness went out AT PEAK while the gate was blind. Fail CLOSED per the
        # t43/t52/t61/t75 convention: an errored peak check defers the paid lane,
        # cause named in error.
        try:
            from mag.offpeak import defer_if_peak
            if defer_if_peak().get("defer"):
                return {"ok": False, "surface": label, "provider": provider, "paid": True,
                        "error": "deferred_peak — paid lane off-peak only (MAG_ALLOW_PEAK=1 overrides)",
                        "answer": ""}
        except Exception as _dp_e:  # noqa: BLE001 - the gate must never BREAK the witness; it DENIES
            return {"ok": False, "surface": label, "provider": provider, "paid": True,
                    "error": ("defer gate errored; failing CLOSED (paid deferred): "
                              + str(_dp_e)[:110]),
                    "answer": ""}
    try:
        from models.providers import reload_providers, chat_provider
        reload_providers()
        # 2026-09-05: 900 truncated real salons mid-answer (groq cut at 952 chars,
        # reasoning lanes returned headers only). 2200 = full three-part answers.
        kw = {"tier": "T2", "max_tokens": 2200}
        if model:
            kw["model"] = model
        r = chat_provider(provider, system="You are one witness in a sovereign roundtable. "
                                           "Answer the question directly and concretely, your own view.",
                          user=question, **kw)
        text = (r.get("text") or "").strip()
        return {"ok": bool(r.get("ok")) and bool(text), "surface": label, "provider": provider,
                "paid": paid, "answer": text, "error": (r.get("error") or "")[:160]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "surface": label, "provider": provider, "paid": paid,
                "answer": "", "error": f"unreachable: {str(e)[:120]}"}


def _consensus(witnesses: list[dict[str, Any]]) -> str:
    """roshomon-style: the tokens SHARED across the available witnesses (deterministic)."""
    ok = [w for w in witnesses if w.get("ok")]
    if not ok:
        return "no witnesses answered — the salon cannot consensus on nothing"
    sets = [set(_TOKEN_RE.findall((w.get("answer") or "").lower())) for w in ok]
    common = set.intersection(*sets) if sets else set()
    common = {t for t in common if len(t) > 3 and t not in _TRIVIAL}
    return " ".join(sorted(common))[:400] if common else \
        "the witnesses agree on no shared token (distinct expertise — each line kept)"


def salon(question: str, *, lanes: list[str] | None = None,
          thread: str = "salon", monitor: str = "") -> dict[str, Any]:
    """Verbose posters on one room thread; optional monitor seat tri-states and files fixes."""
    q = (question or "").strip()
    if not q:
        return {"ok": False, "schema": SCHEMA, "error": "empty question"}
    selected = WITNESSES
    if lanes:
        want = {str(x).strip().lower() for x in lanes}
        selected = [w for w in WITNESSES if w[0].lower() in want or w[1].lower() in want]
    _room("salon-runner", "salon_question", q, thread=thread, seats=[w[0] for w in selected])
    results = []
    for label, provider, model, paid in selected:
        if label == "grok-cli":
            # subscription tandem lane (grok_route.v1 law): headless CLI, $0 cash
            try:
                from mag.grok_tandem import ask_cli
                witness_frame = ("You are one witness in a sovereign roundtable. "
                                 "Answer concisely.\n\n" + q)
                r = ask_cli(witness_frame)
                w = {"surface": "grok-cli", "ok": r["ok"], "paid": False,
                     "answer": r.get("answer", ""), "error": r.get("error", "")}
            except Exception as e:
                w = {"surface": "grok-cli", "ok": False, "paid": False,
                     "answer": "", "error": str(e)[:200]}
            results.append(w)
            _room("grok-cli", "salon_answer", (w.get("answer") or w.get("error") or "")[:4000],
                  thread=thread, ok=w["ok"])
            continue
        w = _witness(label, provider, model, paid, q)
        results.append(w)
        _room(label, "salon_answer", (w.get("answer") or w.get("error") or "")[:4000],
              thread=thread, ok=bool(w.get("ok")))
    up = [w for w in results if w.get("ok")]
    consensus = _consensus(results)
    verdict = ""
    if monitor and up:
        blob = "\n\n".join(f"[{w['surface']} ok={w['ok']}] {(w.get('answer') or w.get('error') or '')[:1200]}"
                           for w in results)
        try:
            from models.providers import chat_provider
            r = chat_provider(monitor, system=(
                "You monitor the salon. Tri-state each witness SUPPORTED/DISPUTED/UNPROVEN "
                "with one line, then surviving consensus in three lines. No new claims. "
                "If a witness is wrong, file the fix as a one-line patch."),
                user=f"QUESTION:\n{q}\n\nANSWERS:\n{blob}",
                model="deepseek-v4-flash" if monitor == "deepseek" else None,
                thinking=False, max_tokens=1800, tier="T2")
            verdict = (r.get("text") if r.get("ok") else f"MONITOR FAILED: {str(r.get('error'))[:240]}") or ""
        except Exception as e:  # noqa: BLE001
            verdict = f"MONITOR FAILED: {e}"
        _room(f"monitor-{monitor}", "salon_verdict", verdict, thread=thread)
    OUT.mkdir(parents=True, exist_ok=True)
    run = {"schema": SCHEMA, "ts": _now(), "question": q, "thread": thread,
           "n_witnesses": len(selected), "n_up": len(up), "consensus": consensus,
           "verdict": verdict[:2000], "witnesses": results}
    try:
        (OUT / f"salon_{_now()[:16].replace(':', '')}.json").write_text(
            json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    _room("salon-runner", "salon_done", f"up={len(up)}/{len(selected)} thread={thread}", thread=thread)
    return {"ok": bool(up), "schema": SCHEMA, "ts": _now(), "thread": thread,
            "n_witnesses": len(selected), "n_up": len(up), "consensus": consensus,
            "verdict": verdict[:800],
            "witnesses": [{k: w[k] for k in ("surface", "ok", "paid", "answer", "error")} for w in results],
            "note": "verbose on one board; monitor files tri-state fixes"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="lane_salon", description="salon over the working API seats")
    p.add_argument("cmd", nargs="?", default="salon", choices=["salon", "status"])
    p.add_argument("question", nargs="?")
    p.add_argument("--lanes", default="")
    p.add_argument("--thread", default="salon")
    p.add_argument("--monitor", default="", help="provider id that tri-states the board (e.g. deepseek)")
    a = p.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps({"schema": SCHEMA, "witnesses": [w[0] for w in WITNESSES],
                          "note": "API lanes that work — free-first, paid deepseek off-peak"}, indent=2))
        return 0
    q = a.question or ""
    if not q:
        print("usage: python -m mag.lane_salon salon '<question>' [--lanes ...]")
        return 1
    lanes = [x for x in a.lanes.split(",") if x.strip()] if a.lanes else None
    print(json.dumps(salon(q, lanes=lanes, thread=a.thread, monitor=a.monitor),
                     ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
