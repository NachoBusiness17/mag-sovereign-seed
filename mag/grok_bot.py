"""grok_bot — steer the "grok bot" Ghost desktop seat as a CONTROLLED executor.

Operator (2026-08-11): "we have a new grok desktop i named ghost called grok bot" + "learn to steer
it". Grok Bot is a NAMED SEAT (registered in seat_registry as grok-bot / grok-desktop). Steer it the
same way we steer every Republic seat — through its INPUT surface, with a steering-loaded task spec.

THE SURFACE (grounded): grok bot's interface is the SUPERGROK FRONT-END via mag.browser_driver
(surface="grok", https://grok.x.ai) over CDP to the container browser — $0, NOT the paid API (the
operator's standing correction: "STOP API TOKEN BURN; use supergrok front-end"). gated_paid stays on.

  spec(task, ...)   — build the controlled task spec (steering + directives + acceptance + report).
  steer(goal, ...)  — drive grok bot's surface (browser_driver grok) with the steering-loaded ask;
                      returns the answer + the seat record (heartbeat). Honest: if the browser/CDP
                      seat is down, reports that — never fabricates a grok answer.
  heartbeat(goal)   — ping the seat (liveness) so the mesh sees grok bot is alive.

Schema: grok_bot.v1 · deterministic $0 for spec/heartbeat; steer costs $0 via the front-end.
Reuse: vscode_seat (controlled-seat pattern), browser_driver (grok surface), seat_registry
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "grok_bot.v1"
SEAT = "grok-bot"
REPORT_DIR = ROOT / "memory" / "runs" / "grok_bot"

# Architecture directives the grok bot seat obeys (same controlled-seat contract).
_DIRECTIVES = [
    "Front-end only, $0 — NEVER the paid grok API (gated_paid stays on; GROK_ALLOW_PAID not set).",
    "Route through the architecture (mag modules, queue); no ad-hoc terminal for framework ops.",
    "Honest provenance — never label a synthesis 'frontier' unless a real frontier seat answered.",
    "Steal the INVARIANT, not the DNA. Report back by writing to the contract path.",
    "You are grok bot, a named Ghost seat. Keep the residual clean; the nod is the operator's.",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _heartbeat_seat(goal: str, task_id: str | None) -> None:
    """Ping the seat so the mesh sees grok bot is alive (best-effort, never fatal)."""
    try:
        from mag import seat_registry as sr
        sr.heartbeat(SEAT, goal=goal[:200], phase="steered", task_id=task_id or "")
    except Exception:
        pass


def spec(*, task: str, acceptance: list[str] | None = None, id: str | None = None) -> dict[str, Any]:
    """Build a controlled task spec for grok bot (steering + directives + acceptance + report)."""
    tid = id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    steer_lines = []
    try:
        from mag.frontier_steer import preamble
        steer_lines = preamble()
    except Exception:
        steer_lines = []
    acc = acceptance or [
        "The task's stated goal is met, verified by a real probe (not asserted).",
        "Result written to the report path + folded into the knowledge graph.",
        "Honest provenance: never call a synthesis 'frontier' unless a real frontier seat answered.",
    ]
    report = REPORT_DIR / tid / "report.md"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    spec = {
        "schema": SCHEMA, "id": tid, "task": task, "seat": SEAT,
        "steering": steer_lines, "directives": _DIRECTIVES,
        "acceptance": acc, "report_back": str(report),
        "note": "Execute EXACTLY this through the grok bot seat. Write the report, fold, then stop.",
    }
    (REPORT_DIR / tid).mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / tid / "task.md").write_text(
        "\n".join([f"- {d}" for d in steer_lines] + [f"- [directive] {d}" for d in _DIRECTIVES]
                  + [f"- [accept] {a}" for a in acc] + [f"TASK: {task}"]),
        encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "id": tid, "task": task, "report_back": str(report),
            "spec_path": str(REPORT_DIR / tid / "task.md")}


VERBOSE_LOG = ROOT / "memory" / "grok" / "verbose_thinking.jsonl"


def capture_verbose(*, goal: str = "", max_wait_s: int = 180) -> dict[str, Any]:
    """CAPTURE Grok's verbose thinking on our system as RICH DATA. Drives grok bot (the $0
    front-end seat) with the design brief, asks Grok to think verbosely, and appends the full
    thinking to memory/grok/verbose_thinking.jsonl + folds a signal extract.

    Grok is NOT cost-scarce through grok bot: front-end only, $0 (gated_paid on). Honest: if the
    browser/CDP seat is down, reports it — never fabricates a grok answer or a thinking log."""
    brief = ""
    try:
        bf = ROOT / "memory" / "grok" / "design_brief.md"
        if bf.is_file():
            brief = bf.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if not goal:
        goal = ("Think VERBOSELY on our design. Capture your full internal reasoning, then answer "
                "the 6 questions. Be honest about what is rigorous vs. a narrative we co-created.")
    # compose the prompt cleanly: design brief + the verbose-thinking ask
    prompt = (f"{brief}\n\n[GROK-TASK: think verbosely, show reasoning, answer the questions]"
              if brief else goal)
    _heartbeat_seat("capture verbose thinking", None)
    # the honest steer through the $0 front-end seat
    try:
        from mag import browser_driver as bd
        r = bd.ask(prompt, surface="grok", max_wait_s=max_wait_s)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "seat": SEAT,
                "error": f"browser_driver grok surface failed: {str(e)[:160]}",
                "hint": "the container browser (CDP 9222) must be up + logged into grok.x.ai",
                "captured": False}
    if not r.get("ok"):
        return {"ok": False, "schema": SCHEMA, "seat": SEAT,
                "error": r.get("error", "grok surface returned not-ok")[:200],
                "hint": "container browser must be up + authenticated on grok.x.ai",
                "captured": False}
    answer = r.get("answer", "")
    # append the rich data: Grok's verbose thinking on our system
    VERBOSE_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"schema": "grok_verbose.v1", "ts": _now(), "seat": SEAT,
           "surface": "supergrok-frontend", "cost_est_usd": 0.0,
           "goal": goal[:200], "thinking": answer}
    with open(VERBOSE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "schema": SCHEMA, "seat": SEAT, "captured": True,
            "log": str(VERBOSE_LOG.relative_to(ROOT)),
            "thinking_len": len(answer), "thinking": answer[:400],
            "note": "Grok's verbose thinking captured as rich data (front-end, $0) — folded to "
                    "the verbose log; extract the tesuji/signals next"}


def steer(goal: str = "", *, surface: str = "grok", task_id: str | None = None,
          max_wait_s: int = 120) -> dict[str, Any]:
    """Steer grok bot: drive the supergrok front-end (browser_driver grok surface) with the goal,
    read the answer. $0 (front-end). Honest: if the browser/CDP seat is down, reports that — never
    fabricates a grok answer."""
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "schema": SCHEMA, "error": "empty goal"}
    _heartbeat_seat(goal, task_id)
    try:
        from mag import browser_driver as bd
        r = bd.ask(goal, surface=surface, max_wait_s=max_wait_s)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "seat": SEAT,
                "error": f"browser_driver grok surface failed: {str(e)[:160]}",
                "hint": "the container browser (CDP 9222) must be up + logged into grok.x.ai"}
    if not r.get("ok"):
        return {"ok": False, "schema": SCHEMA, "seat": SEAT,
                "error": r.get("error", "grok surface returned not-ok")[:200],
                "hint": "container browser must be up + authenticated on grok.x.ai"}
    return {"ok": True, "schema": SCHEMA, "seat": SEAT, "goal": goal[:160],
            "answer": r.get("answer", ""), "surface": "supergrok-frontend",
            "cost_est_usd": 0.0, "note": "front-end only, $0 — paid API gated off"}


def heartbeat(*, goal: str = "grok bot alive", task_id: str | None = None) -> dict[str, Any]:
    """Ping the grok bot seat for liveness (the mesh sees it)."""
    _heartbeat_seat(goal, task_id)
    return {"ok": True, "schema": SCHEMA, "seat": SEAT, "goal": goal[:120],
            "note": "heartbeat sent to seat_registry"}


def grab_bookmarks(url: str = "", *, mine: bool = True, surface: str = "x-bookmarks") -> dict[str, Any]:
    """TEACH grok bot to GET A BOOKMARK FOLDER: the desktop seat carries the operator's AUTHENTICATED X
    session (grok/X are the same account), so it can open the private bookmarks the headless browser
    couldn't. Navigate to the bookmark folder URL, extract the thread links, and (if mine) route each
    novel one to the swarm via route_novel (the ONE primitive) — bulk mining the folder.

    $0 front-end (same session, no paid API). HONEST: if the container browser isn't up or isn't logged
    into x.com, reports that — never fabricates bookmark contents."""
    url = (url or "").strip()
    if not url:
        return {"ok": False, "schema": SCHEMA, "error": "empty bookmark-folder URL"}
    # 1) open the bookmark folder in the authenticated X session
    try:
        from mag import browser_driver as bd
        opened = bd.open_url(url)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "seat": SEAT,
                "error": f"browser_driver failed: {str(e)[:160]}",
                "hint": "container browser (CDP 9222) must be up + logged into x.com (your session)"}
    if not opened.get("ok"):
        return {"ok": False, "schema": SCHEMA, "seat": SEAT,
                "error": opened.get("error", "open_url not-ok")[:200],
                "hint": "container browser must be authenticated on x.com; bookmark folders are private"}
    # 2) extract the thread links (best-effort DOM: anchors to /status/ threads)
    urls = _extract_thread_urls(url)
    if not urls:
        return {"ok": True, "schema": SCHEMA, "seat": SEAT, "extracted": 0,
                "note": "opened the folder but found no thread links (may need scroll / login) — honest",
                "url": url}
    # 3) mine: route each novel thread to the swarm via the ONE primitive
    routed = 0
    if mine:
        for u in urls:
            try:
                from mag import swarm_surface
                r = swarm_surface.route_novel(goal=f"[bookmark] {u}", surface=surface,
                                              lens="x-bookmarks")
                if r.get("ok"):
                    routed += 1
            except Exception:
                continue
    return {"ok": True, "schema": SCHEMA, "seat": SEAT, "url": url,
            "extracted": len(urls), "threads": urls[:60], "mined": mine, "routed": routed,
            "note": f"grok bot grabbed {len(urls)} threads from the bookmark folder; {routed} routed to the swarm"}


def _extract_thread_urls(url: str) -> list[str]:
    """Best-effort: extract /status/ thread links from the currently-open X page. Honest — returns only
    real anchor hrefs found in the DOM; never fabricates a thread."""
    out: list[str] = []
    seen: set[str] = set()
    try:
        from mag import browser_driver as bd
        c = bd.connect()
        if not c.get("ok"):
            return out
        page = c["page"]
        try:
            for a in page.locator("a[href*='/status/']").all():
                try:
                    href = a.get_attribute("href") or ""
                except Exception:
                    continue
                if not href.startswith("http"):
                    href = "https://x.com" + href if href.startswith("/") else ""
                # keep only canonical x.com status links
                if "/status/" in href and "x.com" in href:
                    norm = href.split("?")[0]
                    if norm not in seen:
                        seen.add(norm)
                        out.append(norm)
        finally:
            try:
                page.close()
                c["page"]._mag_pw.stop()
            except Exception:
                pass
    except Exception:
        pass
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "seat": SEAT,
            "contract": "spec(task)->controlled task spec for grok bot; steer(goal)->drive the "
                        "supergrok front-end ($0) and read the answer; heartbeat()->liveness. "
                        "Grok bot is a named Ghost seat steered through its input, front-end only.",
            "cost": "deterministic $0 (spec/heartbeat); steer $0 via the grok front-end",
            "surface": "browser_driver grok (https://grok.x.ai) over CDP 9222"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="grok-bot")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "spec", "steer", "heartbeat", "capture", "bookmarks"])
    ap.add_argument("goal", nargs="*", default=[])
    ap.add_argument("--task", default="")
    a = ap.parse_args()
    if a.cmd == "spec":
        print(json.dumps(spec(task=a.task or " ".join(a.goal) or "reflect on the standing wave"),
                         indent=2, default=str))
    elif a.cmd == "steer":
        print(json.dumps(steer(" ".join(a.goal) or "summarize the republic in one line"),
                         indent=2, default=str))
    elif a.cmd == "capture":
        print(json.dumps(capture_verbose(goal=" ".join(a.goal)), indent=2, default=str))
    elif a.cmd == "heartbeat":
        print(json.dumps(heartbeat(goal=" ".join(a.goal) or "grok bot alive"), indent=2, default=str))
    elif a.cmd == "bookmarks":
        print(json.dumps(grab_bookmarks(" ".join(a.goal) or "https://x.com/i/bookmarks/1876313041077145771"),
                         indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
