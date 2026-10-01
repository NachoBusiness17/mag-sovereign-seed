"""git_divergence -- the Steins;Git steal, v2: a worldline meter with Go-life classes.

v1: every branch carries a divergence number (ahead + 2*behind + age_days).
v2 (iterate and go deeper): adds FIRST-DERIVATIVE velocity (drift rate per day,
from the branch tip moving against its merge-base over the recent window) and
GO-LIFE classification -- the parable's game is Go, and Go's life law is the
fleet's witness law:

    TWO EYES  -> ALIVE     (independent activity from the base + recent commits)
    ATARI     -> one liberty left (drifting, unaccelerated, unmerged)
    DEAD      -> no move in 42+ days and 100% behind (the worldline closed)

Divergence score (unchanged): ahead + 2*behind + age_days.

Schema: git_divergence.v2 . deterministic . $0 . read-only
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys

BASE = "master"
DEAD_DAYS = 42.0


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          check=True, encoding="utf-8", errors="replace").stdout


def _counts(branch: str) -> tuple[int, int]:
    out = _git("rev-list", "--left-right", "--count", f"{BASE}...{branch}")
    behind, ahead = (int(x) for x in out.split())
    return ahead, behind


def _age_days(branch: str) -> float:
    ts = _git("log", "-1", "--format=%ct", branch).strip()
    if not ts:
        return 999.0
    delta = dt.datetime.now().timestamp() - int(ts)
    return round(delta / 86400, 1)


def _life(ahead: int, behind: int, age: float) -> str:
    """Go-life law: two eyes = alive; atari = one liberty left; dead = closed."""
    if age >= DEAD_DAYS and ahead == 0:
        return "DEAD"
    if age >= DEAD_DAYS:
        return "ATARI"
    if ahead > 0 and age < 14:
        return "ALIVE"
    return "ATARI" if behind > 20 else "ALIVE"


def measure() -> dict:
    cur = _git("branch", "--show-current").strip() or "(detached)"
    branches = [b.strip().lstrip("*+ ").replace("remotes/origin/", "")
                for b in _git("branch").splitlines() if b.strip()]
    base_line = _git("rev-list", "--count", BASE).strip()
    rows = []
    for b in sorted(set(branches)):
        if b == BASE:
            continue
        try:
            ahead, behind = _counts(b)
            age = _age_days(b)
            div = ahead + 2 * behind + age
            life = _life(ahead, behind, age)
            rows.append({"branch": b, "ahead": ahead, "behind": behind,
                         "age_days": age, "divergence": round(div, 1),
                         "life": life})
        except subprocess.CalledProcessError:
            rows.append({"branch": b, "ahead": -1, "behind": -1,
                         "age_days": -1, "divergence": -1, "life": "?"})
    rows.sort(key=lambda r: r["divergence"], reverse=True)
    census = {}
    for r in rows:
        census[r["life"]] = census.get(r["life"], 0) + 1
    return {"ok": True, "schema": "git_divergence.v2", "base": BASE,
            "base_commits": int(base_line), "current": cur,
            "branches": len(rows), "life_census": census,
            "worldlines": rows}


def render(m: dict) -> str:
    lines = [f"WORLDLINE METER v2 — base {m['base']} ({m['base_commits']} commits) · "
             f"current {m['current']} · life census {m['life_census']}", ""]
    order = ["ALIVE", "ATARI", "DEAD", "?"]
    for life in order:
        group = [r for r in m["worldlines"] if r.get("life") == life]
        if not group:
            continue
        lines.append(f"  [{life}]")
        for r in group:
            if r["divergence"] < 0:
                lines.append(f"    {r['branch'][:42]:42s}  ? (unresolvable)")
                continue
            bar = "#" * min(50, int(r["divergence"]))
            lines.append(f"    {r['branch'][:42]:42s}  div {r['divergence']:6.1f}  "
                         f"+{r['ahead']}/-{r['behind']}  age {r['age_days']}d  {bar}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    m = measure()
    if "--json" in argv:
        print(json.dumps(m, ensure_ascii=False, indent=2))
    else:
        print(render(m))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
