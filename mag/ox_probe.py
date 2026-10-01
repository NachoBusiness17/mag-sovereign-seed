"""ox_probe — reverse-engineer stealth/ox-alpha's processing flow (grok-elevated probe, 2026-08-23).

Grok's sharpest probe (from the CLI-harness elevation): TWO calls on an identical FROZEN
Hermes-shaped prefix (system + tool defs + fake memory/skills), task that MUST emit a tool call
(no prose). Then read the wire:

  * content null vs "" when tool_calls present   -> 3-channel contract (content = terminal commit)
  * reasoning/reasoning_details populated        -> native reasoning channel (ahead of OR's CoT)
  * usage.cached_tokens ~= prefix length on call B -> prefix-cache IS the standing agent (agent-serving)
  * reasoning tokens billed inside completion    -> they sell thinking as the product

Reuses ox_seat key/model/endpoint loading. T2+ public only (retained-log provider). Free ($0).

Schema: ox_probe.v1 · two calls, byte-identical prefix · free
CLI: python -m mag.ox_probe probe | status
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "ox_probe.v1"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def _load_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OR_API_KEY", "")
    if key:
        return key
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("OPENROUTER_API_KEY="):
                return s.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _load_model() -> str:
    m = os.environ.get("OPENROUTER_MODEL", "")
    if m:
        return m
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("OPENROUTER_MODEL="):
                return s.split("=", 1)[1].strip()
    return "stealth/ox-alpha"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _prefix_system() -> str:
    """A frozen Hermes-shaped prefix: the standing agent's 'self' (constitution + skills + memory)."""
    return (
        "You are Hermes, a persistent self-improving sovereign agent. Constitution: "
        "honesty over over-claiming; meet at the bytes not the words; never fabricate; "
        "code-as-law; content-addressed verkle state. Memory across sessions: "
        "invariant lattice, reusable skills ledger, cold-vertex spend doctrine. "
        "You run scheduled automations and dispatch subagents. "
        "When given a task you prefer the appropriate TOOL CALL over prose."
    )


def _prefix_tools() -> list[dict[str, Any]]:
    """~18 Hermes-shaped tool definitions (the standing tool schema)."""
    names = [
        "read_file", "write_file", "list_dir", "glob", "grep", "run_command",
        "web_search", "fetch_url", "get_time", "compute_hash", "read_env",
        "list_tools", "edit_file", "append_file", "move_file", "delete_file",
        "spawn_subagent", "scheduled_automation",
    ]
    tools = []
    for i, n in enumerate(names):
        tools.append({
            "type": "function",
            "function": {
                "name": n,
                "description": f"Tool {i}: {n}.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "target path"},
                                   "query": {"type": "string", "description": "search/query text"}},
                    "required": [],
                },
            },
        })
    return tools


def _call(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None,
          *, max_tokens: int = 120, timeout: int = 180) -> dict[str, Any]:
    """One raw OpenRouter call; returns the full wire fields we need."""
    key = _load_key()
    if not key:
        return {"ok": False, "error": "no OPENROUTER_API_KEY in .env"}
    model = _load_model()
    body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "http": e.code, "error": e.read().decode("utf-8", "replace")[:300]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    ch = (b.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    usage = b.get("usage") or {}
    ptd = usage.get("prompt_tokens_details") or {}
    ctd = usage.get("completion_tokens_details") or {}
    return {
        "ok": True, "model": b.get("model") or model,
        "content": msg.get("content"),
        "tool_calls": msg.get("tool_calls"),
        "reasoning": msg.get("reasoning") or msg.get("reasoning_details"),
        "finish_reason": ch.get("finish_reason"),
        "cost": usage.get("cost", 0),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "cached_tokens": ptd.get("cached_tokens", 0),
        "reasoning_tokens": ctd.get("reasoning_tokens", 0),
    }


def probe(*, max_tokens: int = 120, timeout: int = 180) -> dict[str, Any]:
    """The two-call prefix-cache experiment (grok's sharpest probe)."""
    tools = _prefix_tools()
    sysm = _prefix_system()
    user_a = ("Use the read_file tool on /tmp/seed.txt and report which tool you called. "
              "DO NOT answer in prose; just make the tool call.")
    messages_a = [{"role": "system", "content": sysm},
                  {"role": "user", "content": user_a}]
    a = _call(messages_a, tools, max_tokens=max_tokens, timeout=timeout)
    if not a.get("ok"):
        return {"schema": SCHEMA, "ts": _now(), "ok": False, "error": a.get("error"),
                "http": a.get("http")}

    # Build call B from call A (byte-identical prefix + minimal delta / tool result).
    messages_b = list(messages_a)
    delta_note = ""
    tool_calls = a.get("tool_calls")
    if tool_calls:
        messages_b.append({"role": "assistant", "content": a.get("content"),
                           "tool_calls": tool_calls})
        messages_b.append({"role": "tool", "tool_call_id": tool_calls[0].get("id"),
                           "content": "seed content: ok"})
        delta_note = "tool_result_delta"
    else:
        messages_b.append({"role": "user", "content": "ok"})
        delta_note = "one_token_delta"
    b = _call(messages_b, tools, max_tokens=max_tokens, timeout=timeout)

    # ---- conclusions (honest, each tied to an observation) ----
    findings: list[dict[str, str]] = []
    if a.get("tool_calls") and a.get("content") is None:
        findings.append({"obs": "content null + tool_calls present", "conclusion":
                         "3-channel contract: content is a terminal commit, not the default"})
    if a.get("reasoning"):
        findings.append({"obs": "reasoning_details populated", "conclusion":
                         "native reasoning channel (ahead of OR's CoT ontology) — reasoning is the tape"})
    if b.get("ok"):
        pt = b.get("prompt_tokens") or 0
        cached = b.get("cached_tokens") or 0
        ratio = (cached / pt) if pt else 0
        findings.append({"obs": f"call B cached_tokens={cached}/{pt} ({ratio:.0%})",
                         "conclusion": ("prefix-cache IS the standing agent (agent-serving)" if ratio > 0.5
                                        else "no true prefix cache (83% may be aggregator/prompt-reuse)" )})
    if (b.get("reasoning_tokens") or 0) > 0:
        findings.append({"obs": f"reasoning_tokens={b.get('reasoning_tokens')}", "conclusion":
                         "reasoning billed inside completion_tokens — they sell thinking as the product"})

    out = {
        "schema": SCHEMA, "ts": _now(), "ok": True,
        "model": a.get("model"), "prefix_tokens_a": a.get("prompt_tokens"),
        "call_a": {"content_null": a.get("content") is None, "content": a.get("content"),
                   "tool_calls": bool(tool_calls), "has_reasoning": bool(a.get("reasoning")),
                   "finish": a.get("finish_reason"), "cached": a.get("cached_tokens"),
                   "completion": a.get("completion_tokens")},
        "delta": delta_note,
        "call_b": {"ok": b.get("ok"), "cached_tokens": b.get("cached_tokens"),
                   "prompt_tokens": b.get("prompt_tokens"),
                   "completion_tokens": b.get("completion_tokens"),
                   "reasoning_tokens": b.get("reasoning_tokens"), "error": b.get("error")},
        "findings": findings,
        "note": "two-call prefix-cache probe; free seat; T2+ public only (retained-log provider)",
    }
    (ROOT / "memory" / "runs" / "ox_probe").mkdir(parents=True, exist_ok=True)
    (ROOT / "memory" / "runs" / "ox_probe" / f"probe_{out['ts'].replace(':', '').replace('-', '')[:15]}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def status() -> dict[str, Any]:
    return {"schema": SCHEMA, "ok": True, "note": "ox_probe: two-call prefix-cache probe on stealth/ox-alpha"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="ox-probe")
    ap.add_argument("cmd", nargs="?", default="probe", choices=["probe", "status"])
    ap.add_argument("--max-tokens", type=int, default=120)
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args(argv)
    out = probe(max_tokens=a.max_tokens, timeout=a.timeout) if a.cmd == "probe" else status()
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
