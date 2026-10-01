"""Sovereign dispatch — local context + auto model pick + min tokens.

Goal for the operator:
  Context stays on disk (Mag living record).
  A router chooses ollama / Claude / DeepSeek / Llama / Grok-API / Hermes / …
  Only a short pack + goal leave the machine for remotes.
  Grok TUI remains the interactive sovereign seat for hard work.
  Hermes is an optional external agent seat (skills loop / long autonomous).
"""
from __future__ import annotations

from typing import Any

from mag.context_pack import build_context_pack, format_context_pack_text
from models.quota import pick_provider
from models.registry import model_for

# Named remotes — force_provider of these must not fall into local exec
REMOTE_PROVIDERS = frozenset(
    {
        "deepseek",
        "openrouter",
        "openai",
        "anthropic",
        "groq",
        "gemini",
        "xai",
        "together",
    }
)


def _classify_job(goal: str) -> tuple[str, str, str]:
    """Returns (job, tier, seat) via unified router."""
    from mag.router import route

    r = route(goal)
    return (
        str(r.get("job") or "default"),
        str(r.get("tier") or "T2"),
        str(r.get("seat") or "local"),
    )


def dispatch(
    goal: str,
    *,
    execute: bool = True,
    force_provider: str | None = None,
    force_seat: str | None = None,
    max_context_chars: int = 1800,
) -> dict[str, Any]:
    """
    Full sovereign hop:
      1) load local context-pack (min tokens)
      2) classify job/seat
      3) if local → ollama/ask
      4) if remote → pick provider by quota → chat with pack+goal only
      5) if grok_tui → return pack for Grok (no auto spend)
    """
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    # Planning gate: big/ambiguous/expensive goals get clarified before commit.
    if execute and not force_provider and not force_seat:
        try:
            from mag.plan import plan_gate

            gated = plan_gate(goal)
            if gated.get("gate") == "plan":
                return gated
        except Exception:
            pass  # gate is advisory; never block dispatch on a plan bug

    pack = build_context_pack(max_brief=900, max_live=500)
    pack_text = format_context_pack_text(pack)

    # Attach latest research pack when goal is research-ish or pack is fresh
    research_attached = False
    research_prompt = ""
    try:
        from mag.research_pack import PACKS, load_pack, _pack_to_prompt, run_pack

        rp = load_pack()
        job_probe, _, _ = _classify_job(goal)
        if rp and (
            job_probe == "research"
            or any(k in goal.lower() for k in ("pack", "source", "http", "research", "scrape"))
            or (PACKS / "latest.json").is_file()
            and job_probe in ("public_summarize", "default", "research")
        ):
            # prefer running the research pack path for research jobs
            if job_probe == "research" and execute and not force_provider:
                ran = run_pack(rp, seat=force_seat or "local", provider=None)
                return {
                    "ok": True,
                    "goal": goal[:400],
                    "job": "research",
                    "tier": "T2",
                    "seat": ran.get("seat") or "local",
                    "research_pack_id": rp.get("id"),
                    "result": ran,
                    "fidelity": ran.get("fidelity"),
                    "hint": ran.get("hint")
                    or "Used latest research pack. Check fidelity; elevate if weak.",
                    "health": pack.get("health"),
                    "models_local": pack.get("models"),
                }
            research_prompt = _pack_to_prompt(rp)[:3500]
            research_attached = True
            pack_text = (
                pack_text
                + "\n\n## Latest research pack (attached)\n"
                + research_prompt
            )
    except Exception:
        pass

    if len(pack_text) > max_context_chars + (2000 if research_attached else 0):
        lim = max_context_chars + (2000 if research_attached else 0)
        pack_text = pack_text[: lim - 20] + "\n…[truncated]"

    job, tier, seat = _classify_job(goal)
    if force_seat:
        seat = force_seat

    # Explicit remote provider (dashboard seat=DeepSeek etc.) wins over local classify.
    # Without this, "what was I doing" / coding → local and force_provider is ignored.
    fp = (force_provider or "").strip().lower() or None
    if fp in REMOTE_PROVIDERS:
        if not force_seat:
            seat = "remote"
        # Explicit provider selection chooses a worker, not a privacy waiver.
        # Classified T0/T1 work remains private and is refused by chat_provider.

    # Compose: seat purity when a run is open (no mid-run thrash)
    run_gate: dict[str, Any] | None = None
    try:
        from mag.run_trail import check_seat, load_run, normalize_seat

        active = load_run()
        if active and active.get("status") == "open":
            locked = normalize_seat(str(active.get("seat") or "local"))
            attempted = normalize_seat(seat)
            # privacy.never_remote blocks remote while run active
            priv = active.get("privacy") or {}
            if priv.get("never_remote") and attempted == "remote":
                return {
                    "ok": False,
                    "goal": goal[:400],
                    "job": job,
                    "tier": tier,
                    "seat": seat,
                    "error": "run_never_remote",
                    "hint": (
                        f"Active run {active.get('run_id')} forbids remote. "
                        "trail close or keep seat local."
                    ),
                    "run_id": active.get("run_id"),
                }
            chk = check_seat(attempted)
            if not chk.get("ok"):
                return {
                    "ok": False,
                    "goal": goal[:400],
                    "job": job,
                    "tier": tier,
                    "seat": seat,
                    "error": "seat_purity_violation",
                    "locked_seat": locked,
                    "attempted_seat": attempted,
                    "run_id": active.get("run_id"),
                    "hint": (
                        f"Active run locked to seat={locked}. "
                        "trail close then restart with new seat — no mid-run swap."
                    ),
                }
            # classify may say remote while run is local — pin to locked seat
            if attempted != locked:
                seat = locked
            else:
                seat = locked
            run_gate = {
                "run_id": active.get("run_id"),
                "locked_seat": locked,
                "proactivity": active.get("proactivity"),
            }
            # Visible cost of hop on trail (audit / commitment device)
            if execute:
                try:
                    from mag.run_trail import append_event

                    append_event(
                        "dispatch",
                        f"job={job} seat={locked} goal={goal[:120]}",
                        run_id=str(active.get("run_id")),
                        core={
                            "type": "tool_digest",
                            "tool": "dispatch",
                            "result": f"{job}/{locked}",
                        },
                    )
                except Exception:
                    pass
    except Exception as e:
        run_gate = {"warn": str(e)}

    out: dict[str, Any] = {
        "ok": True,
        "goal": goal[:400],
        "job": job,
        "tier": tier,
        "seat": seat,
        "context_chars": len(pack_text),
        "research_attached": research_attached,
        "health": pack.get("health"),
        "models_local": pack.get("models"),
        "result": None,
        "provider": None,
        "hint": "",
        "run_gate": run_gate,
    }

    if seat == "wait":
        out["hint"] = "Human required."
        return out

    if seat == "grok_tui":
        out["hint"] = (
            "Hard work — stay in Grok TUI (sovereign seat). "
            "Use this context_pack only; do not reload full chat."
        )
        out["context_pack_excerpt"] = pack_text[:1200]
        out["result"] = {
            "action": "defer_to_grok_tui",
            "open_loops": pack.get("open_loops"),
        }
        return out

    if seat == "cursor":
        preamble_path = str(
            (__import__("config").ROOT / "memory" / "cursor_preamble_latest.md")
        )
        out["hint"] = (
            "Hard code — use Cursor IDE (composer seat). "
            "Run launch_cursor_seat.cmd or context-pack --agent. "
            f"Preamble: {preamble_path}"
        )
        out["context_pack_excerpt"] = pack_text[:1200]
        out["result"] = {
            "action": "defer_to_cursor",
            "preamble": preamble_path,
            "open_loops": pack.get("open_loops"),
        }
        return out

    if seat == "hermes":
        from harness.hermes_cli import escalate_via_hermes, hermes_status

        st = hermes_status()
        out["provider"] = "hermes"
        out["hermes"] = st
        if not execute:
            out["hint"] = (
                "Dry run — hermes seat. Install if missing, then re-run without --dry."
                if not st.get("available")
                else "Dry run — would call Hermes with context-pack + goal only."
            )
            out["result"] = {"action": "defer_to_hermes", "available": st.get("available")}
            return out
        if not st.get("available"):
            out["ok"] = False
            out["hint"] = st.get("hint") or "Hermes not installed"
            out["result"] = st
            return out
        res = escalate_via_hermes(
            goal=goal,
            context=pack_text,
            mode="chat",
        )
        out["result"] = res
        out["ok"] = bool(res.get("ok"))
        out["hint"] = (
            "Hermes seat — pack+goal only; skills/memory stay in Hermes home."
            if res.get("ok")
            else f"Hermes failed: {res.get('error') or res.get('stderr') or res.get('exit_code')}"
        )
        return out

    if not execute:
        pick = pick_provider(job, tier=tier) if seat == "remote" else {
            "ok": True,
            "provider": "ollama",
            "model": model_for("worker"),
        }
        out["provider"] = pick
        out["hint"] = "Dry run — pass execute=True / --go to call models"
        return out

    # Local only when seat is local AND no remote force_provider
    if (seat == "local" or fp == "ollama") and fp not in REMOTE_PROVIDERS:
        out["provider"] = "ollama"
        out["result"] = _local_exec(goal, pack)
        out["hint"] = "Answered from local context/models. Grok: summarize only if needed."
        return out

    # remote: min-token user message = pack + goal
    system = (
        "You are a specialist called by Mag for one job. "
        "Use only the context block. Be concise. No flattery. "
        "Do not request private data."
    )
    user = f"## Local context (authoritative)\n{pack_text}\n\n## Job\n{goal}\n"
    if fp and fp in REMOTE_PROVIDERS:
        from models.providers import chat_provider

        res = chat_provider(
            fp,
            system,
            user,
            tier=tier,
            max_tokens=1024,
        )
        out["seat"] = "remote"
        out["provider"] = fp
        out["result"] = res
        out["ok"] = bool(res.get("ok"))
        out["answer"] = (res.get("text") or res.get("answer") or "") if res.get("ok") else ""
        out["hint"] = (
            f"Remote {fp} — tokens spent on pack+goal only."
            if res.get("ok")
            else f"Remote {fp} failed: {res.get('error') or 'unknown'}"
        )
        return out
    if force_provider and fp not in REMOTE_PROVIDERS and fp != "ollama":
        # unknown force id — try chat_provider anyway
        from models.providers import chat_provider

        res = chat_provider(
            force_provider,
            system,
            user,
            tier=tier,
            max_tokens=1024,
        )
        out["provider"] = force_provider
        out["result"] = res
        out["ok"] = bool(res.get("ok"))
        out["answer"] = (res.get("text") or "") if res.get("ok") else ""
        out["hint"] = f"Remote {force_provider} — tokens spent on pack+goal only."
        return out

    from models.providers import chat_routed

    res = chat_routed(system, user, job=job, tier=tier, max_tokens=1024)
    out["provider"] = res.get("provider")
    out["result"] = res
    if res.get("ok"):
        out["hint"] = f"Routed to {res.get('provider')}:{res.get('model')} with min context."
    else:
        # fallback local
        out["seat"] = "local_fallback"
        out["result"] = {
            "remote_error": res,
            "local": _local_exec(goal, pack),
        }
        out["hint"] = "Remote failed/empty budget — fell back to local."
    return out


def _local_exec(goal: str, pack: dict[str, Any]) -> dict[str, Any]:
    g = goal.lower()
    try:
        if "smoke" in g:
            from models.multi_smoke import run_multi_smoke

            return {"action": "multi_smoke", **{k: run_multi_smoke().get(k) for k in ("ok", "verdict", "models_seen")}}
        if "doctor" in g or "health" in g or "quota" in g and "chat" not in g:
            from mag.health import sanity
            from models.quota import all_budgets

            if "quota" in g or "provider" in g:
                return {"action": "quota", "budgets": all_budgets()}
            s = sanity()
            return {"action": "doctor", "status": s.get("status"), "live_stale": (s.get("recording") or {}).get("live_stale")}
        from mag.ask import ask

        r = ask(goal, use_llm=True)
        return {
            "action": "ask",
            "ok": r.get("ok"),
            "answer": (r.get("answer") or "")[:2000],
        }
    except Exception as e:
        return {"action": "error", "ok": False, "error": str(e)}
