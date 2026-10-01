"""campaign_runs — the swarm plays the campaign overnight and generates DATA on what a
successful campaign looks like. Records each session to memory/game/campaign_runs/<tag>-<date>-<id>.jsonl:
per turn: action, DM narration, saga, running gags, ok. By morning we have a corpus of what worked.

Reuse (nothing invented): game_campaign (engine), game_dm_llm (creative DM), game_saga (running gag).

Schema: campaign_runs.v1
"""
from __future__ import annotations

import difflib
import json
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCHEMA = "campaign_runs.v1"
RUNS_DIR = ROOT / "memory" / "game" / "campaign_runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# Fallback only. Targeted play uses legal actions in the current room.
_PLAYER_VERBS = [
    "look", "go north", "go down", "go deeper", "go right",
    "talk to mira", "talk to the merchant", "look at the crate", "take rope",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_session(*, n_turns: int = 8, tag: str = "auto", force_new: bool = True) -> dict[str, Any]:
    from mag import game_campaign as gc
    from mag import game_saga as saga

    start = gc.begin_play(module_id="classic", force_new=force_new)
    cid = str(start.get("campaign_id") or uuid.uuid4().hex[:8])
    out_path = RUNS_DIR / f"{tag}-{_now()[:10]}-{cid}.jsonl"
    rows: list[dict[str, Any]] = []

    # ITERATE-DON'T-REPEAT (operator law): seed + shuffle each session so no two nights are identical,
    # and catch near-duplicate narration so the loop self-heals instead of spinning the same beat.
    random.seed(cid)
    verbs = list(_PLAYER_VERBS)
    random.shuffle(verbs)

    try:
        gc.set_character(cid, gc.parse_character("a curious rogue named Bort, brave, cynical"))
    except Exception:
        pass

    iterated = 0
    prev_narration = ""
    for i in range(n_turns):
        camp = gc.load_campaign(cid) or {}
        legal = []
        try:
            legal = gc.list_legal_actions(camp) or []
        except Exception:
            legal = r.get("legal") if i and "r" in dir() else []
        picked = []
        for a in legal:
            if not isinstance(a, dict):
                continue
            t = str(a.get("type") or "")
            if t == "move" and a.get("direction"):
                picked.append("go " + str(a.get("direction")))
            elif t == "talk" and a.get("target"):
                picked.append("talk to " + str(a.get("target")))
            elif t == "look" and a.get("target"):
                picked.append("look at " + str(a.get("target")))
            elif t == "take" and (a.get("item") or a.get("target")):
                picked.append("take " + str(a.get("item") or a.get("target")))
            elif t == "look":
                picked.append("look")
            elif t in ("attack", "rest"):
                picked.append(t)
        verb = random.choice(picked) if picked else verbs[i % len(verbs)]
        try:
            r = gc.handle_game({
                "action": "act",
                "campaign_id": cid,
                "text": verb,
                "move": verb,
            })
            ok = bool(r.get("ok"))
            events = r.get("events") or []
            narration = "\n".join(str(e) for e in events) or str(
                r.get("narrate") or r.get("speak") or r.get("error") or ""
            )
        except Exception as e:
            ok = False
            narration = f"ERROR: {str(e)[:200]}"
        camp = gc.load_campaign(cid) or {}
        # self-heal: if this beat is a near-repeat of the last, flag it (the DM already varies; this
        # marks the loop saw it and moved on rather than silently repeating).
        repeated = bool(prev_narration) and difflib.SequenceMatcher(
            None, prev_narration[:300], narration[:300]).ratio() > 0.85
        if repeated:
            iterated += 1
        gags = [g["name"] for g in saga.running_gags(cid)]
        row = {"ts": _now(), "turn": i, "action": verb, "ok": ok, "iterated": repeated,
               "narration": narration[:900], "running_gags": gags,
               "room_id": camp.get("room_id"),
               "flags": list(camp.get("flags") or [])[:12],
               "legal": picked[:12]}
        rows.append(row)
        prev_narration = narration
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")

    return {"ok": True, "schema": SCHEMA, "campaign_id": cid, "file": str(out_path),
            "turns": len(rows), "iterated": iterated,
            "gags": sorted({g for r in rows for g in r.get("running_gags", [])})}


def status() -> dict[str, Any]:
    runs = sorted(RUNS_DIR.glob("*.jsonl"))
    total_turns = 0
    for p in runs:
        try:
            total_turns += sum(1 for _ in p.open(encoding="utf-8"))
        except Exception:
            pass
    return {"ok": True, "schema": SCHEMA, "dir": str(RUNS_DIR), "runs": len(runs),
            "total_turns": total_turns}


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(prog="campaign-runs")
    ap.add_argument("--turns", type=int, default=8)
    ap.add_argument("--tag", default="auto")
    a = ap.parse_args()
    print(json.dumps(run_session(n_turns=a.turns, tag=a.tag), indent=2, default=str))
