"""Token-chain: DeepSeek writes a tiny work order; local Ollama executes it.

Purpose
-------
Prove Grok (or operator) can *direct* DeepSeek as a planner seat that emits a
frozen local_work_order.v1, then a dumb local seat executes without burning
frontier tokens on tool thrash.

Dashboard: POST /api/v1/token-chain
CLI:       python main.py token-chain [--goal ...] [--dry] [--live]
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT


def _rel_posix(path) -> str:
    """Repo-relative posix path, absolute when outside ROOT.

    Cause (ball3 follow-up sweep 2026-09-29): display/receipt derivations
    raised ValueError whenever the path lived outside the repo (the suite
    runs use an out-of-repo pytest basetemp). Same fix as the driver-meter
    lane's _rel_posix in tools/stealth_driver.py.
    """
    try:
        return Path(path).relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()



SCHEMA = "local_work_order.v1"
RUN_DIR = ROOT / "memory" / "runs" / "token_chain"
ALLOWED_OPS = frozenset({"read_file", "list_dir", "count_lines", "write_run_note"})
MAX_STEPS = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)


def _safe_under_root(rel: str) -> Path:
    """Resolve path under ROOT; reject escapes and secret files."""
    raw = (rel or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or ".." in raw.split("/"):
        raise ValueError(f"unsafe path: {rel!r}")
    low = raw.lower()
    for ban in (".env", "credentials", "secret", "id_rsa", "auth.json"):
        if ban in low:
            raise ValueError(f"prohibited path: {rel!r}")
    p = (ROOT / raw).resolve()
    root = ROOT.resolve()
    if not str(p).startswith(str(root)):
        raise ValueError(f"path escapes root: {rel!r}")
    return p


def parse_work_order(text: str) -> dict[str, Any]:
    """Extract local_work_order.v1 JSON from model text."""
    s = (text or "").strip()
    if not s:
        raise ValueError("empty plan text")
    # fenced json
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL | re.IGNORECASE)
    if m:
        s = m.group(1)
    else:
        start, end = s.find("{"), s.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("no JSON object in plan")
        s = s[start : end + 1]
    data = json.loads(s)
    if not isinstance(data, dict):
        raise ValueError("plan must be object")
    data["schema"] = SCHEMA
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps required")
    if len(steps) > MAX_STEPS:
        data["steps"] = steps[:MAX_STEPS]
        data["truncated_steps"] = True
    clean: list[dict[str, Any]] = []
    for i, step in enumerate(data["steps"]):
        if not isinstance(step, dict):
            continue
        op = str(step.get("op") or step.get("action") or "").strip()
        if op not in ALLOWED_OPS:
            raise ValueError(f"step {i}: op {op!r} not in {sorted(ALLOWED_OPS)}")
        path = str(step.get("path") or "").strip()
        if op != "write_run_note" and not path:
            raise ValueError(f"step {i}: path required")
        if path:
            # validate early so bad plans never reach exec
            _safe_under_root(path)
        clean.append(
            {
                "op": op,
                "path": path,
                "note": str(step.get("note") or step.get("content") or "")[:2000],
            }
        )
    if not clean:
        raise ValueError("no valid steps")
    data["steps"] = clean
    data["goal"] = str(data.get("goal") or "token-chain")[:500]
    data["success_criteria"] = str(data.get("success_criteria") or "all steps ok")[:500]
    return data


def execute_work_order(order: dict[str, Any]) -> dict[str, Any]:
    """Deterministic local executor — no LLM. Safe ops only under ROOT."""
    results: list[dict[str, Any]] = []
    ok_all = True
    for i, step in enumerate(order.get("steps") or []):
        op = step["op"]
        t0 = time.perf_counter()
        try:
            if op == "read_file":
                p = _safe_under_root(step["path"])
                if not p.is_file():
                    raise FileNotFoundError(str(p))
                text = p.read_text(encoding="utf-8", errors="replace")
                results.append(
                    {
                        "i": i,
                        "op": op,
                        "path": step["path"],
                        "ok": True,
                        "chars": len(text),
                        "preview": text[:240],
                        "ms": int((time.perf_counter() - t0) * 1000),
                    }
                )
            elif op == "list_dir":
                p = _safe_under_root(step["path"] or ".")
                if not p.is_dir():
                    raise NotADirectoryError(str(p))
                names = sorted(x.name for x in p.iterdir())[:50]
                results.append(
                    {
                        "i": i,
                        "op": op,
                        "path": step["path"],
                        "ok": True,
                        "n": len(names),
                        "names": names,
                        "ms": int((time.perf_counter() - t0) * 1000),
                    }
                )
            elif op == "count_lines":
                p = _safe_under_root(step["path"])
                n = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
                results.append(
                    {
                        "i": i,
                        "op": op,
                        "path": step["path"],
                        "ok": True,
                        "lines": n,
                        "ms": int((time.perf_counter() - t0) * 1000),
                    }
                )
            elif op == "write_run_note":
                _ensure()
                note_path = RUN_DIR / "local_note.md"
                body = (
                    f"# token-chain local note\n\n"
                    f"- ts: {_now()}\n"
                    f"- goal: {order.get('goal')}\n\n"
                    f"{step.get('note') or '(empty)'}\n"
                )
                note_path.write_text(body, encoding="utf-8")
                results.append(
                    {
                        "i": i,
                        "op": op,
                        "path": "memory/runs/token_chain/local_note.md",
                        "ok": True,
                        "ms": int((time.perf_counter() - t0) * 1000),
                    }
                )
            else:
                raise ValueError(f"unknown op {op}")
        except Exception as exc:
            ok_all = False
            results.append(
                {
                    "i": i,
                    "op": op,
                    "path": step.get("path"),
                    "ok": False,
                    "error": str(exc)[:400],
                    "ms": int((time.perf_counter() - t0) * 1000),
                }
            )
    return {"ok": ok_all, "results": results, "n_ok": sum(1 for r in results if r.get("ok"))}


def _plan_prompt(goal: str) -> tuple[str, str]:
    system = (
        "You are Mag's PLANNER seat (DeepSeek). Output ONLY one JSON object, no prose.\n"
        f"Schema {SCHEMA}. Allowed ops: {sorted(ALLOWED_OPS)}.\n"
        f"Max {MAX_STEPS} steps. Paths relative to Mag root only.\n"
        "Never request .env, secrets, or paths outside the repo.\n"
        "Prefer read_file / count_lines / list_dir on memory/improve or docs — cheap scut for local.\n"
        "Include write_run_note once with a 1-line summary of what local will report."
    )
    user = (
        f"Goal (T2 public): {goal}\n\n"
        "Emit JSON:\n"
        "{\n"
        f'  "schema": "{SCHEMA}",\n'
        '  "goal": "...",\n'
        '  "success_criteria": "...",\n'
        '  "steps": [\n'
        '    {"op": "read_file", "path": "memory/improve/field_brief.md"},\n'
        '    {"op": "count_lines", "path": "memory/improve/candidates.jsonl"},\n'
        '    {"op": "write_run_note", "note": "..."}\n'
        "  ]\n"
        "}\n"
    )
    return system, user


def _usage_tokens(resp: dict[str, Any]) -> dict[str, int]:
    u = resp.get("usage") or resp.get("meta") or {}
    if not isinstance(u, dict):
        u = {}
    return {
        "prompt_tokens": int(u.get("prompt_tokens") or u.get("input_tokens") or 0),
        "completion_tokens": int(u.get("completion_tokens") or u.get("output_tokens") or 0),
        "total_tokens": int(
            u.get("total_tokens")
            or (
                int(u.get("prompt_tokens") or 0)
                + int(u.get("completion_tokens") or 0)
            )
            or 0
        ),
    }


def run_token_chain(
    *,
    goal: str | None = None,
    dry: bool = False,
    live: bool = True,
    planner: str = "deepseek",
    fixture_plan: str | None = None,
) -> dict[str, Any]:
    """
    Run one chain tick.

    dry=True  → no model calls; use canned plan if no fixture
    live=True → call DeepSeek for plan, execute locally (no local LLM needed)
    """
    _ensure()
    goal = (goal or "Inspect improve field_brief and candidates; note top ticket ids").strip()
    out: dict[str, Any] = {
        "schema": "token_chain_run.v1",
        "ts": _now(),
        "goal": goal,
        "dry": dry,
        "live": live and not dry,
        "planner": planner,
        "ok": False,
    }

    plan_text = fixture_plan
    planner_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    planner_error: str | None = None

    if plan_text is None and dry:
        plan_text = json.dumps(
            {
                "schema": SCHEMA,
                "goal": goal,
                "success_criteria": "read brief + count candidates + note",
                "steps": [
                    {"op": "read_file", "path": "memory/improve/field_brief.md"},
                    {"op": "count_lines", "path": "memory/improve/candidates.jsonl"},
                    {
                        "op": "write_run_note",
                        "note": "dry fixture: local executed work order without DeepSeek",
                    },
                ],
            }
        )
    elif plan_text is None and live:
        try:
            from models.providers import chat_provider

            system, user = _plan_prompt(goal)
            resp = chat_provider(
                planner,
                system,
                user,
                tier="T2",
                max_tokens=800,
                temperature=0.1,
            )
            if not isinstance(resp, dict):
                raise RuntimeError(f"bad provider response type: {type(resp)}")
            if resp.get("ok") is False:
                raise RuntimeError(str(resp.get("error") or resp)[:400])
            plan_text = str(
                resp.get("text")
                or resp.get("content")
                or resp.get("message")
                or ""
            )
            if not plan_text and isinstance(resp.get("result"), str):
                plan_text = resp["result"]
            # some adapters nest choices
            if not plan_text and resp.get("choices"):
                try:
                    plan_text = resp["choices"][0]["message"]["content"]
                except Exception:
                    pass
            planner_usage = _usage_tokens(resp)
            out["planner_raw_ok"] = True
            out["planner_model"] = resp.get("model") or planner
        except Exception as exc:
            planner_error = str(exc)[:500]
            out["planner_raw_ok"] = False
            # fallback canned plan so local half still proves
            plan_text = json.dumps(
                {
                    "schema": SCHEMA,
                    "goal": goal,
                    "success_criteria": "fallback local after planner error",
                    "steps": [
                        {"op": "read_file", "path": "memory/improve/field_brief.md"},
                        {
                            "op": "write_run_note",
                            "note": f"planner failed: {planner_error[:200]}",
                        },
                    ],
                    "planner_fallback": True,
                }
            )

    try:
        order = parse_work_order(plan_text or "")
    except Exception as exc:
        out["error"] = f"parse: {exc}"
        out["planner_error"] = planner_error
        out["plan_text_preview"] = (plan_text or "")[:400]
        _write_run(out)
        return out

    out["work_order"] = order
    out["planner_usage"] = planner_usage
    out["planner_error"] = planner_error

    exec_res = execute_work_order(order)
    out["execution"] = exec_res
    out["ok"] = bool(exec_res.get("ok")) and not planner_error

    # Token thesis: planner should stay small; local exec uses 0 frontier tokens
    out["token_thesis"] = {
        "frontier_tokens": planner_usage.get("total_tokens") or 0,
        "local_llm_tokens": 0,
        "local_exec_steps": len(exec_res.get("results") or []),
        "claim": (
            "DeepSeek plans only (short completion); deterministic local executor "
            "does file scut — 0 frontier tool-loop tokens."
        ),
    }
    out["observe"] = {
        "run_dir": _rel_posix(RUN_DIR),
        "cli": "python main.py token-chain --goal \"...\"",
        "dashboard": "POST /api/v1/token-chain",
        "latest": "memory/runs/token_chain/latest.json",
    }
    _write_run(out)
    return out


def _write_run(out: dict[str, Any]) -> None:
    _ensure()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RUN_DIR / f"run-{stamp}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "latest.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    out["artifact"] = _rel_posix(path)


def cmd_token_chain(args: Any) -> int:
    goal = " ".join(getattr(args, "goal", None) or []) or None
    if getattr(args, "goal_text", None):
        goal = str(args.goal_text)
    res = run_token_chain(
        goal=goal,
        dry=bool(getattr(args, "dry", False)),
        live=not bool(getattr(args, "dry", False)),
        planner=str(getattr(args, "planner", None) or "deepseek"),
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") or res.get("execution", {}).get("ok") else 1
