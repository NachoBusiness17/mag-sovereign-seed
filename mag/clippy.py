"""Clippy, bent into a Verkle knot — the standing reminder (tied, not untied).

It looks like you're trying to work on Mag. Would you like a reminder? The
reminder is a verkle knot now: each line is a knot leaf (sha256), the leaves
commit to a tip (merkle root), and Clippy speaks from inside the knot — the
content stays useful, the shape is tied.

Invocable: `python main.py clippy` · always-on in AGENTS.md.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import ROOT  # noqa: E402


def _h(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _merkle_root(leaf_hashes: list[str]) -> str:
    if not leaf_hashes:
        return _h("empty")
    layer = leaf_hashes[:]
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i + 1] if i + 1 < len(layer) else left
            nxt.append(_h("node:" + left + ":" + right))
        layer = nxt
    return layer[0]


def _pile_line() -> str:
    try:
        from mag.state_snapshot import status

        s = status()
        return f"pile: {s.get('pile', 0)} total / {s.get('unclassified', 0)} unclassified (overnight: main.py pile-classify)"
    except Exception:
        return "pile: (unavailable)"


def _leaves() -> list[str]:
    return [
        "NEW WINDOW? execute /memories/session/next-window-handoff.md — design is DONE, this is execution → LOW tier",
        "TESTS: 39 deterministic green (+2 model-gated) — pytest -q before claiming done. Trust bytes, not reports.",
        "DELIBERATE-ASK: strong asks = frozen RIB + small ask + output contract + quantize target. Pay the context tax ONCE.",
        "THINKING-MODE is the axis (not flash vs pro) — tune it before tier (design_vague proved it).",
        "PILE HABIT: escalation/session-close → mag.state_snapshot.capture_summary. Contribute before you go.",
        _pile_line(),
        "TIER LADDER: ollama → free tiers (gemini/groq/z.ai...) → deepseek flash → pro/grok (only judgment climbs).",
    ]


def clippy(*, flat: bool = False) -> str:
    leaves = _leaves()
    hashes = [_h("leaf:" + l) for l in leaves]
    root = _merkle_root(hashes)
    tip8 = root[:8]
    if flat:
        return "\n".join(["🖇️ CLIPPY (flat):"] + ["• " + l for l in leaves])
    lines = [
        "🖇️  CLIPPY, bent into a Verkle knot. He is trying to help. He is also tied.",
        f"     knot tip: {tip8} · n_leaves: {len(leaves)} · tie: 2026-08-07",
        "",
    ]
    for i, (leaf, h) in enumerate(zip(leaves, hashes), 1):
        lines.append(f"  [{i:02d}] {leaf}  · {h[:8]}")
    lines += [
        "",
        "     ── tie-off ──",
        "     The knot holds 7 reminders. Untying requires operator consent.",
        "     (You do not have a choice. The rope is verkle-committed.)",
        "",
        "→ /memories/session/next-window-handoff.md · doctrine: repo memory (DELIBERATE-ASK · PUPPETEER · PILE)",
    ]
    return "\n".join(lines)


def _gather_state() -> dict[str, Any]:
    """Live indicators Clippy uses to propose real pressing work."""
    state: dict[str, Any] = {}
    try:
        from mag.state_snapshot import status as pile_status

        ps = pile_status()
        state["pile_unclassified"] = ps.get("unclassified", 0)
        state["pile_total"] = ps.get("pile", 0)
    except Exception:
        state["pile_unclassified"] = 0
    try:
        from mag.skill_ledger import progress

        p = progress() or {}
        state["decisions"] = p.get("decisions") or (p.get("progress") or {}).get("decisions") or 0
        state["labeled"] = p.get("labeled_rows") or (p.get("progress") or {}).get("labeled_rows") or 0
    except Exception:
        state["decisions"] = state["labeled"] = 0
    try:
        from mag.operator_inbox import status as inbox_status

        state["inbox_pending"] = inbox_status().get("pending_n", 0)
    except Exception:
        state["inbox_pending"] = 0
    return state


# The frozen next steps — the real pressing work (from /memories/session/next-window-handoff.md)
_HANDOFF_ACTIONS = [
    ("Run the G1 authority sweep at runs=5",
     "the runs=2 curve was noise — flip-rates need samples to be decision-grade",
     "gauntlet sweep --sweep g1 --runs 5", "local", "5 min"),
    ("Add the thinking-mode rubric arm to tier_probe",
     "design_vague proved thinking on/off is the axis — the rubric must measure correctness, not punish prose",
     "tier_probe", "local", "30 min"),
    ("Add GET /api/v1/pile REST status route",
     "surface the state pile on the dashboard so the loop is visible",
     "rest.py", "local", "10 min"),
    ("Register pile-classify as the overnight job",
     "unclassified summaries are waiting on downtime classification",
     "scheduler / night task", "local", "10 min"),
    ("Quantization Brief #1 (graveyard scan → bootloader v1.1)",
     "this session's 7 bugs are bootloader-patch material — run the 2x/week loop",
     "quantize brief", "any", "30 min"),
]


def propose_actions(state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    state = state or _gather_state()
    props: list[dict[str, Any]] = []
    if state.get("pile_unclassified"):
        props.append({
            "id": "A", "title": "Run the overnight pile classification",
            "why": f"{state['pile_unclassified']} unclassified state summaries are queued for training soil",
            "cmd": "main.py pile-classify", "tier": "local", "effort": "varies (cold model)",
            "nugget": "classify the pile → case law + training rows",
        })
    for i, (title, why, cmd, tier, effort) in enumerate(_HANDOFF_ACTIONS, 1):
        props.append({"id": chr(ord("A") + i), "title": title, "why": why, "cmd": cmd,
                      "tier": tier, "effort": effort, "nugget": title})
    if (state.get("decisions") or 0) < 1000:
        props.append({
            "id": "Z", "title": "Seed skill_ledger decisions toward target",
            "why": f"decisions at {state.get('decisions', 0)}/1000 — the counter is the training-volume gauge",
            "cmd": "main.py skill-ledger seed-bench", "tier": "local", "effort": "10 min",
            "nugget": "grow case law volume",
        })
    if state.get("inbox_pending"):
        props.append({
            "id": "Y", "title": "Review pending operator inbox guidance",
            "why": f"{state['inbox_pending']} pending guidance items waiting to steer the agent",
            "cmd": "dashboard", "tier": "operator", "effort": "5 min",
            "nugget": "clear the steering queue",
        })
    return props[:6]


def record_choice(action: str, *, source: str = "clippy") -> dict[str, Any]:
    """Capture the chosen direction to the pile AND steer the agent at its next
    checkpoint — the operator choice becomes a breadcrumb the agent drains."""
    from mag.state_snapshot import capture_summary

    cap = capture_summary(goal=action[:300], outcome="ok", tier="operator-choice",
                          kind="operator", source=source, lessons=["operator picked next action"])
    steered = False
    try:
        from mag.operator_inbox import commit_guidance

        commit_guidance(f"[operator next-action choice] {action[:300]}", source=source)
        steered = True
    except Exception:
        pass
    return {"ok": True, "captured": bool(cap.get("ok")), "steered": steered, "action": action}


def choose(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="clippy choose", description="Propose + choose the next pressing course of action.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    props = propose_actions()
    if args.json:
        print(json.dumps({"proposals": props}, indent=2, ensure_ascii=False))
        return 0
    print("🖇️  CLIPPY proposes the next pressing courses of action (from live state):\n")
    for p in props:
        print(f"  [{p['id']}] {p['title']}   ({p['tier']} · {p['effort']})")
        print(f"       why: {p['why']}")
        print(f"       cmd: {p['cmd']}\n")
    raw = input("choose [A..Z] or type your own direction: ").strip()
    action = next((p["title"] for p in props if raw.upper() == p["id"]), None)
    if action is None and raw:
        action = raw
    if not action:
        print("no choice — Clippy remains tied.")
        return 0
    r = record_choice(action)
    print(f"\n🖇️  Chosen: {action}")
    print(f"    captured to pile: {r['captured']} · steered to agent: {r['steered']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="clippy", description="Standing reminder (verkle-knotted) + next-action proposer.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--flat", action="store_true", help="plain reminder without the knot")
    sub = ap.add_subparsers(dest="cmd")
    p_ch = sub.add_parser("choose", help="propose + choose the next pressing course of action")
    p_ch.add_argument("--json", action="store_true")
    args, _ = ap.parse_known_args(argv)
    if args.cmd == "choose":
        return choose(argv[1:] if argv else None)
    if args.json:
        print(json.dumps({"ok": True, "tip": _merkle_root([_h("leaf:" + l) for l in _leaves()])[:8],
                          "n_leaves": len(_leaves()), "reminder": clippy(flat=args.flat)}, indent=2, ensure_ascii=False))
    else:
        print(clippy(flat=args.flat))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
