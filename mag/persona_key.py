"""persona_key v2 — THE Q-SORT GATE: recognize a person by HOW THEY RANK VALUES (2026-08-24).

STEAL (the operator: "steal"): the established mechanism already exists — the Q-SORT
(William Stephenson, 1953: forced-choice ranking of statements; the shape of the sort IS the
profile, and it kills the agree-with-everything response bias), the SCHWARTZ VALUE CIRCUMPLEX
(the established values taxonomy), and SPEARMAN rank correlation (the standard statistic for
comparing rankings). Adapted, not invented. The v1 heuristic is retired — it was keyword
counting with invented weights dressed in theory names. This is the sound version.

THE GATE: present generic value statements; the person ranks them most-like-me (1) to
least-like-me (N). Their ranking is correlated against their BASELINE ranking (seeded from
recorded behavior, refined by every real sort). High correlation = the same stance = the same
person. Deniable: the statements are generic human values, no internal vocabulary.

WHY SOUND:
  - METHOD: forced-choice Q-sort is established psychometrics (response-style bias defeated).
  - STATEMENTS: drawn from the Schwartz circumplex + the operator's recorded stance.
  - MEASURE: Spearman rank correlation — a real statistic, no invented weights.
  - BASELINE: seeded from recorded behavior, SELF-CALIBRATING (every real sort refines it).

HONEST LIMITS: the baseline is a seed until the operator sorts once for real; and like any
knowledge+stance proof it is a strong signal, not a lock.

Schema: persona_key.v2 · deterministic + $0 · reuse: the operator's recorded values (seed)
CLI: python -m mag.persona_key challenge | answer "<ranks>" | record "<ranks>" | baseline | status
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "persona_key.v2"
STATE = ROOT / "state" / "persona_baseline.json"
FIT_RHO = 0.5        # Spearman rho at/above this = the sort carries the operator's key
REFINE = 0.3         # EWMA weight for a real sort updating the baseline

# ── THE STATEMENTS — generic human values (Schwartz circumplex + the operator's recorded
# stance, phrased for anyone, no internal vocabulary). 14 items = a playable forced sort.
STATEMENTS = [
    "I trust what I can verify more than what I am told.",
    "I would rather stay free than be comfortable.",
    "I want proof before I commit to something.",
    "I notice when someone is trying to persuade me.",
    "I hold on to the one true thing even when it is inconvenient.",
    "I keep my own keys.",
    "I would rather be honest than impressive.",
    "I trust my own judgment over the crowd.",
    "I like new ideas even when they are risky.",
    "Big institutions usually know best.",
    "A sure offer today beats a free choice tomorrow.",
    "Safety is the most important thing.",
    "Other people's approval matters to me.",
    "I want to be part of something bigger than myself.",
]
N = len(STATEMENTS)

# ── SEED BASELINE — derived from the operator's RECORDED stance (this session + memory):
# the statements that match their actual values get a low rank number (most-like-me).
# A real sort replaces this seed (self-calibrating).
SEED_RANKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14, 12, 11, 10]  # index -> rank (1 = most like me)


def _load_baseline() -> list[int]:
    if STATE.is_file():
        try:
            b = json.loads(STATE.read_text(encoding="utf-8"))
            if len(b.get("ranks") or []) == N:
                return b["ranks"]
        except Exception:  # noqa: BLE001
            pass
    return list(SEED_RANKS)


def _save_baseline(ranks: list[int], n_sorts: int) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"schema": SCHEMA, "ranks": ranks, "n_sorts": n_sorts},
                                indent=2, ensure_ascii=False), encoding="utf-8")


def _spearman(a: list[float], b: list[float]) -> float:
    """Spearman rank correlation between two rankings — the real statistic."""
    n = len(a)
    if n < 2:
        return 0.0
    d2 = sum((x - y) ** 2 for x, y in zip(a, b))
    return 1.0 - (6.0 * d2) / (n * (n * n - 1))


def challenge() -> dict[str, Any]:
    """The gate's public face: N generic value statements for a forced-choice sort."""
    return {"ok": True, "schema": SCHEMA, "n": N,
            "statements": [{"i": i + 1, "text": s} for i, s in enumerate(STATEMENTS)],
            "instruction": "Rank them 1 (most like you) to %d (least like you). "
                           "No ties — forced choice. Give the ranks as a list in this order." % N,
            "note": "the shape of your sort is the key — written for a human"}


def _parse_ranks(v: Any) -> list[int] | None:
    if isinstance(v, list):
        vals = v
    elif isinstance(v, str):
        v = v.strip().replace(",", " ").replace("[", "").replace("]", "")
        vals = v.split()
    else:
        return None
    try:
        out = [int(x) for x in vals]
    except Exception:  # noqa: BLE001
        return None
    if len(out) != N or sorted(out) != list(range(1, N + 1)):
        return None
    return out


def answer(ranks: Any) -> dict[str, Any]:
    """Score a forced-choice sort against the baseline via Spearman. Ranks: a list of N
    numbers (1 = most like me) in statement order, or the same as a space/comma string."""
    r = _parse_ranks(ranks)
    if not r:
        return {"ok": True, "schema": SCHEMA, "score": 0.0, "key_fits": False,
                "note": "could not parse the ranks (need %d numbers, 1 = most like you, "
                        "no ties, in statement order)" % N}
    baseline = _load_baseline()
    rho = _spearman([float(x) for x in baseline], [float(x) for x in r])
    fits = rho >= FIT_RHO
    return {"ok": True, "schema": SCHEMA, "rho": round(rho, 3),
            "score": round(max(0.0, rho), 3), "key_fits": fits, "fit_rho": FIT_RHO,
            "note": ("the sort carries the operator's key (rho %.2f)" % rho
                     if fits else "the sort does not match the baseline (rho %.2f)" % rho)}


def record(ranks: Any) -> dict[str, Any]:
    """A REAL sort: score it, then refine the baseline (EWMA) — the gate self-calibrates
    to the operator's actual stance, replacing the seed."""
    r = _parse_ranks(ranks)
    if not r:
        return {"ok": True, "schema": SCHEMA, "error": "need %d ranks (1=most like you)" % N}
    baseline = _load_baseline()
    rho = _spearman([float(x) for x in baseline], [float(x) for x in r])
    new = [round(REFINE * o + (1 - REFINE) * b) for o, b in zip(r, baseline)]
    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {"n_sorts": 0}
    n = int(st.get("n_sorts") or 0) + 1
    _save_baseline(new, n)
    return {"ok": True, "schema": SCHEMA, "rho": round(rho, 3), "n_sorts": n,
            "note": "baseline refined from this real sort — the gate learns you"}


def baseline() -> dict[str, Any]:
    b = _load_baseline()
    n = 0
    if STATE.is_file():
        try:
            n = int(json.loads(STATE.read_text(encoding="utf-8")).get("n_sorts") or 0)
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "schema": SCHEMA, "ranks": b, "n_sorts": n,
            "note": ("seeded from recorded behavior (not yet calibrated by a real sort)"
                     if n == 0 else "calibrated by %d real sort(s)" % n)}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "n_statements": N, "fit_rho": FIT_RHO,
            "method": "Q-sort (Stephenson 1953) + Schwartz values + Spearman rank correlation",
            "baseline": baseline(),
            "contract": "challenge() = the sort; answer() = Spearman vs baseline; record() = "
                        "refine the baseline from a real sort. Sound: established method, "
                        "real statistic, self-calibrating. Strong signal, not a lock.",
            "built": "2026-08-24 — v2, the steal"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="persona_key", description="the Q-sort gate")
    p.add_argument("cmd", nargs="?", default="status",
                   choices=["status", "challenge", "answer", "record", "baseline"])
    p.add_argument("ranks", nargs="*", default=None)
    a = p.parse_args(argv)
    if a.cmd == "challenge":
        print(json.dumps(challenge(), indent=2, ensure_ascii=False))
    elif a.cmd in ("answer", "record"):
        if a.ranks:
            print(json.dumps((answer if a.cmd == "answer" else record)(a.ranks),
                             indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"ok": False, "error": "provide ranks, e.g. answer 1 3 2 5 4 ..."}))
    elif a.cmd == "baseline":
        print(json.dumps(baseline(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
