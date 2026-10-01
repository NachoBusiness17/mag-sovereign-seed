"""grok_free — the FREE grok surfaces: grok CLI harness + grok.com private idea space.

DOCTRINE (operator): grok.com and the grok CLI are directly available at a mem-edit level
(browser or docker), act as a private space to save ideas coherently, and are freely
EDITABLE. IMPORTANT (operator correction): the grok CLI and the API share the SAME key /
team (715bf1ab) — there is NO separate free pool. The genuinely free editable surface is
the grok DESKTOP (grok.com), driven by the GHOST PROTOCOL via the browser. So grok_free's
'free' surface = the grok desktop (grok.com browser); the CLI/API both bill the working team.

This module is the "bones" (skeleton) our agents build out:
  1. `capture(goal)`     — run a grok call (API on the working team for elevation, or the
                          CLI which uses the same key).
  2. `save_idea(...)`    — save an idea coherently + privately. Writes a local private idea
                          (memory/ideas/grok_free/ — never public), and can hand it to
                          grok.com (the private save space) for the operator to confirm.
  3. `status()`          — which free grok surfaces are reachable (CLI binary, browser).
  4. Ghost integration   — surfaces status under sense_surfaces; cadence-capable.

Schema: grok_free.v1
CLI:  python -m mag.grok_free capture "<goal>" | save-idea "<title>" "<body>" | status
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "grok_free.v1"
IDEAS_DIR = ROOT / "memory" / "ideas" / "grok_free"
GROK_COM_URL = "https://grok.com"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cli_available() -> dict[str, Any]:
    """Is the free grok CLI harness binary present? (names/paths only, no secrets.)"""
    try:
        from harness.grok_cli import find_grok, harness_available
        return {"ok": harness_available(), "bin": find_grok(), "note": "free subscription seat"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def route_surface(goal: str = "") -> dict[str, Any]:
    """Deterministic, $0 surface selector: which grok surface serves this goal.
    CLI (free) -> grok.com (free/private, operator browser) -> API (paid fallback).
    This is the 'orchestrator model' — a cheap deterministic probe, not a frontier debate.
    """
    cli = _cli_available()
    if cli.get("ok"):
        pick = "cli"
    else:
        pick = "api"  # browser (grok.com) is an operator-surface; headless automation is fragile
    return {
        "ok": True, "schema": SCHEMA, "goal": (goal or "")[:120],
        "surface": pick, "cli": cli.get("ok"),
        "note": "cli=free seat, com=grok.com private space, api=paid fallback",
        "grok_com": GROK_COM_URL,
    }


def _prior_block(goal: str) -> tuple[str, list[str]]:
    """Self-referencing PRIOR GROK-FREE IDEAS block (steal: agentswarm memoryBlock)."""
    try:
        from mag.research_lens import retrieve_prior
        pr = retrieve_prior(goal, lens_id="grok_free", limit=3)
        refs = pr.get("prior_refs") or []
        if refs:
            return ("PRIOR GROK-FREE IDEAS (build on them; don't redo settled ones):\n"
                    + pr.get("prior_block", "")[:2000]), refs
    except Exception:
        pass
    return "", []


def status() -> dict[str, Any]:
    """Which free grok surfaces are reachable."""
    cli = _cli_available()
    return {
        "schema": SCHEMA,
        "ok": bool(cli.get("ok")),
        "cli_harness": cli,
        "grok_com": {"url": GROK_COM_URL, "note": "private idea space (browser surface)"},
        "ideas_dir": str(IDEAS_DIR),
        "transport_doctrine": "default to free grok CLI + grok.com; paid API only as fallback",
        "ts": _now(),
    }


def capture(goal: str, *, context: str = "") -> dict[str, Any]:
    """Run a FREE grok call via the CLI harness (subscription seat, $0). API fallback.
    Compounding: auto-injects a PRIOR GROK-FREE IDEAS block from the research-lens corpus."""
    if not (goal or "").strip():
        return {"ok": False, "error": "empty goal"}
    prior, refs = _prior_block(goal)
    ctx = prior + ("\n\n" + context if context else "") if prior else context
    try:
        from mag.grok_rightsize import call_grok_free
        r = call_grok_free(goal, context=ctx)
        _log_usage(surface=r.get("surface") or "cli", ok=bool(r.get("ok")),
                   cost=r.get("cost_est_usd", 0.0),
                   fallback=not bool(r.get("harness")))
        # fold the free capture's answer back into the grok_free lens corpus (compounding)
        folded = {}
        if r.get("ok") and (r.get("content") or "").strip():
            try:
                from mag.research_lens import fold_back
                folded = fold_back(
                    _write_answer(goal, r.get("content", "")), lens_id="grok_free")
            except Exception:
                folded = {"ok": False}
        return {
            "ok": bool(r.get("ok")),
            "content": r.get("content", ""),
            "model": r.get("model", ""), "tier": r.get("tier", ""),
            "cost_est_usd": r.get("cost_est_usd", 0.0),
            "key_env": r.get("key_env", ""), "harness": bool(r.get("harness")),
            "error": r.get("error", ""), "schema": SCHEMA,
            "prior_refs": refs, "folded": folded.get("ok", False),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "schema": SCHEMA}


def _write_answer(goal: str, content: str) -> Path:
    """Persist a free capture as a research-lens foldable answer file."""
    d = IDEAS_DIR / "answers"
    d.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in goal.lower())[:50]
    p = d / f"{_now()[:16].replace(':', '')}-{slug}.answer.grokfree.md"
    p.write_text(f"# {goal}\n\n{content}\n", encoding="utf-8")
    return p


def save_idea(title: str, body: str = "", *, private: bool = True) -> dict[str, Any]:
    """Save an idea coherently + privately. Writes a local private idea file (never public);
    grok.com is the browser-side private space the operator can use to keep it too."""
    title = (title or "untitled").strip()[:200]
    body = (body or "").strip()
    ts = _now()
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in title.lower())[:60]
    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    path = IDEAS_DIR / f"{ts[:16].replace(':', '')}-{slug}.md"
    text = f"# {title}\n\n- Saved: `{ts}` · private: {private}\n- Space: grok_free (local + grok.com)\n\n{body}\n"
    path.write_text(text, encoding="utf-8")
    # also record as an idea_graph node so ideas become recallable topology (steal: concept-cells)
    graph = {}
    try:
        from mag import idea_graph as ig
        node = ig.add_node(title=title, ntype="open_loop", status="open", body=body[:4000],
                           tags=["grok_free", "private_idea"], source="grok_free",
                           node_id=None)
        graph = {"ok": True, "node_id": node.get("id")}
    except Exception as e:
        graph = {"ok": False, "error": str(e)[:120]}
    return {
        "ok": True, "schema": SCHEMA, "title": title, "path": str(path),
        "private": private, "ts": ts, "idea_graph": graph,
        "grok_com": {"url": GROK_COM_URL, "note": "browser surface — operator can confirm/keep the idea there"},
    }


def handoff(goal: str, *, context: str = "") -> dict[str, Any]:
    """FREE project handoff (steal: blackboard artifact-subscription + MAG_BUILD_PIPELINE):
    the free grok surface writes a frozen BUILD contract, then the cheap executor (DeepSeek)
    builds from it. This is the free plan-leg of the build pipeline."""
    if not (goal or "").strip():
        return {"ok": False, "error": "empty goal"}
    # 1) free grok produces the spec
    cap = capture(goal, context=context)
    spec = cap.get("content") or ""
    # 2) write a frozen BUILD contract
    from datetime import datetime as _dt
    hd = ROOT / "queue" / "handoff"
    hd.mkdir(parents=True, exist_ok=True)
    stem = "BUILD-grokfree-" + _dt.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    cpath = hd / f"{stem}.md"
    body = (
        f"# {stem}\n\n- Source: grok_free (free grok CLI harness, $0)\n"
        f"- Goal: {goal[:300]}\n- Status: frozen — cheap executor builds from this spec.\n\n"
        f"## Spec (from free grok)\n{spec[:8000]}\n\n"
        "## Contract\nOutput: code/configs under the repo. Acceptance: unit tests / physics checks. "
        "No secrets. Fold result back to the corpus.\n"
    )
    cpath.write_text(body, encoding="utf-8")
    # 3) enqueue the cheap executor
    spawn = {}
    try:
        from mag.orchestrator import spawn_task
        spawn = spawn_task(f"Execute build package {stem}: expand the frozen spec and implement it.",
                           provider="deepseek", model="deepseek-v4-flash", tag="grok-free-handoff")
    except Exception as e:
        spawn = {"ok": False, "error": str(e)[:120]}
    return {"ok": bool(spawn.get("ok")), "schema": SCHEMA, "stem": stem,
            "contract": str(cpath), "spawn": spawn, "capture": cap.get("ok"),
            "cost_est_usd": cap.get("cost_est_usd", 0.0)}


# ------------------------------------------------------------------ control ----
RUNS_DIR = ROOT / "memory" / "runs" / "grok_free"
CONTROL = RUNS_DIR / "control.jsonl"
USAGE = RUNS_DIR / "usage.jsonl"
STATE = RUNS_DIR / "cadence_state.json"
SKILL_PATH = ROOT / "memory" / "skills" / "grok-free.md"
CONTROL_TTL_S = 3600  # a control signal times out -> proceed autonomously (steal: timeout->autonomous)


def _log_usage(surface: str, ok: bool, cost: float, *, fallback: bool = False) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with USAGE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), "surface": surface, "ok": bool(ok),
                            "cost_est_usd": cost, "fallback": bool(fallback)}) + "\n")


def control_signal(action: str, note: str = "") -> dict[str, Any]:
    """Append a control signal to the free-surface control channel (steal: ControlMsg)."""
    action = (action or "status").lower()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "action": action, "note": (note or "")[:200]}
    with CONTROL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return {"ok": True, "control": row}


def control_status() -> dict[str, Any]:
    """Read the control channel: latest signal + whether it's still in force."""
    if not CONTROL.is_file():
        return {"ok": True, "latest": None, "blocked": False, "ttl_s": CONTROL_TTL_S}
    rows = []
    for line in CONTROL.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    latest = rows[-1] if rows else None
    blocked = False
    if latest:
        import time
        try:
            age = time.time() - datetime.fromisoformat(latest.get("ts", "")).timestamp()
            if latest.get("action") in ("stop", "pause", "kill") and age < CONTROL_TTL_S:
                blocked = True
        except Exception:
            pass
    return {"ok": True, "latest": latest, "blocked": blocked, "ttl_s": CONTROL_TTL_S,
            "note": "blocked control times out -> proceeds autonomously"}


def _autonomy_gate() -> dict[str, Any]:
    """The free surface proceeds autonomously unless an unexpired stop/pause/kill is in force."""
    cs = control_status()
    if cs.get("blocked"):
        return {"ok": False, "action": "blocked", "control": cs.get("latest")}
    return {"ok": True, "action": "autonomous"}


# ---------------------------------------------------------------- cadence ----
def write_skill() -> dict[str, Any]:
    """Write the grok-free SKILL.md (steal: conductor skills/ + SKILL.md+references layout)."""
    SKILL_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# grok-free — free grok surfaces (CLI harness + grok.com private idea space)\n\n"
        "- Default to the FREE grok CLI harness (`grok -p`, subscription seat, $0) and grok.com\n"
        "- (private idea space) over the paid API. Paid API only as fallback when CLI is absent.\n"
        "- `capture(goal)` — free grok call, compounds via research_lens (injects PRIOR GROK-FREE\n"
        "- IDEAS, folds answer back). `save_idea(title, body)` — private idea + idea_graph node.\n"
        "- `handoff(goal)` — writes a frozen `queue/handoff/BUILD-grokfree-*.md` and spawns the\n"
        "- cheap DeepSeek executor. `route_surface(goal)` — deterministic cli|com|api pick.\n"
        "- Autonomy: proceeds unless an unexpired stop/pause/kill control is in force.\n"
    )
    SKILL_PATH.write_text(body, encoding="utf-8")
    return {"ok": True, "skill": str(SKILL_PATH)}


def _processed_ids() -> set[str]:
    if STATE.is_file():
        try:
            return set((json.loads(STATE.read_text(encoding="utf-8")) or {}).get("done") or [])
        except Exception:
            return set()
    return set()


def cadence(*, max_new: int = 2) -> dict[str, Any]:
    """Autonomous loop: work the private idea backlog with the FREE grok surface.
    Scans idea_graph open_loop nodes tagged grok_free/private_idea, captures free on the
    top unprocessed one (compounding), folds back, marks done. Idempotent + budgeted."""
    gate = _autonomy_gate()
    if not gate.get("ok"):
        return {"ok": True, "action": "blocked", "control": gate.get("control")}
    done = _processed_ids()
    processed, skipped = [], []
    try:
        from mag import idea_graph as ig
        nodes = ig.list_nodes(status="open", ntype="open_loop", limit=30)
    except Exception as e:
        nodes, skipped = [], [{"error": str(e)[:120]}]
    picked = 0
    for n in nodes:
        if picked >= max_new:
            break
        nid = str(n.get("id") or "")
        tags = [str(t).lower() for t in (n.get("tags") or [])]
        if "grok_free" not in tags and "private_idea" not in tags:
            continue
        if nid in done:
            continue
        goal = str(n.get("title") or "")[:400]
        cap = capture(goal)
        ok = bool(cap.get("ok"))
        (processed if ok else skipped).append(
            {"node": nid, "title": goal[:60], "cost": cap.get("cost_est_usd", 0.0), "ok": ok})
        if ok:
            done.add(nid)
            picked += 1
    if processed:
        STATE.write_text(json.dumps({"done": sorted(done), "ts": _now()}, indent=2), encoding="utf-8")
    return {"ok": True, "action": "cadence", "processed": processed, "skipped": skipped,
            "done_count": len(done), "max_new": max_new}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="grok-free", description="Free grok surfaces: CLI harness + grok.com private idea space")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_cap = sub.add_parser("capture", help="free grok CLI call (subscription seat, $0)")
    p_cap.add_argument("goal", nargs="+")
    p_cap.add_argument("--context", default="")
    p_save = sub.add_parser("save-idea", help="save an idea privately")
    p_save.add_argument("title", nargs="+")
    p_save.add_argument("--body", default="")
    p_h = sub.add_parser("handoff", help="free grok spec -> frozen BUILD contract -> cheap executor")
    p_h.add_argument("goal", nargs="+")
    sub.add_parser("status", help="which free grok surfaces are reachable")
    p_ctl = sub.add_parser("control", help="control channel (stop|pause|kill|resume)")
    p_ctl.add_argument("action", nargs="?", default="status")
    sub.add_parser("cadence", help="autonomous loop over the private idea backlog")
    sub.add_parser("skill", help="write the grok-free SKILL.md")
    args = ap.parse_args(argv)
    if args.cmd == "capture":
        print(json.dumps(capture(" ".join(args.goal), context=args.context), indent=2, default=str)[:8000])
    elif args.cmd == "save-idea":
        print(json.dumps(save_idea(" ".join(args.title), body=args.body), indent=2, default=str)[:4000])
    elif args.cmd == "handoff":
        print(json.dumps(handoff(" ".join(args.goal)), indent=2, default=str)[:6000])
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif args.cmd == "control":
        if args.action == "status":
            print(json.dumps(control_status(), indent=2, default=str))
        else:
            print(json.dumps(control_signal(args.action), indent=2, default=str))
    elif args.cmd == "cadence":
        print(json.dumps(cadence(), indent=2, default=str)[:8000])
    elif args.cmd == "skill":
        print(json.dumps(write_skill(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["capture", "save_idea", "handoff", "status", "route_surface",
           "control_signal", "control_status", "cadence", "write_skill", "main"]
