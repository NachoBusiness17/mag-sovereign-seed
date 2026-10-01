"""Mag check-in route — freeze → network probe → multi-seat structure pass → Grok LOAD.

Schema: mag_checkin.v1

Operator intent (Grok TUI skill /mag-checkin):
  After freezing state, do not burn Grok on re-organizing the mess.
  Probe the Mag router body (nervous / doctor-ish / spider / ollama).
  FILE a structure chain through local janitor → DeepSeek → OpenAI structure
  pass → Kimi (via OpenRouter when keyed) → local seal critique.
  Grok only re-LOADs pack + final artifact and judges.

Law: chat is heat; freeze + chain artifacts FILE; missing remote keys soft-skip.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_checkin.v1"
CHECKIN_DIR = ROOT / "memory" / "working" / "checkins"
INDEX_PATH = CHECKIN_DIR / "index.jsonl"

# OpenAI "fable" structure pass — clarity / narrative coherence of the plan.
# Model comes from providers.yaml (default gpt-4o-mini) unless OPENAI_CHECKIN_MODEL set.
# Kimi K3 via OpenRouter when key present; soft-skip otherwise.
KIMI_OPENROUTER_MODEL = "moonshotai/kimi-k2-0905-preview"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def structure_checkin_plan() -> list[dict[str, str]]:
    """Multi-seat structure orchestra → local_usable.v1 when goal is pack/module."""
    return [
        {
            "seat": "local",
            "role": "janitor",
            "purpose": (
                "Local janitor / rules_clerk face: reorganize frozen mess into outline — "
                "goals, open loops, tags, non-goals. No remote claims. Hardware-honest. "
                "If goal is a game/world: list rooms/roles needed, not freestyle lore."
            ),
            "expected_output": (
                "Markdown: ## Outline ## Open loops ## Tags ## Non-goals ## "
                "World roles needed (if any) ## What needs a smarter seat (1-3 bullets)"
            ),
        },
        {
            "seat": "deepseek",
            "role": "structure",
            "purpose": (
                "Module author face: produce a local_usable.v1 design Mag can FILE — "
                "datasheet rows (layer-tagged), misconceptions, retrieval obligations, "
                "world_roles. Prefer artifact shape over essay. Honor local-first."
            ),
            "expected_output": (
                "Markdown + JSON blocks: ## Goal ## local_usable pack sketch "
                "(slug, kind: structure|game_module|entity_ref) ## datasheet rows "
                "## misconceptions ## obligations ## acceptance ## do-not-list. "
                "Never collapse interpretation into fact."
            ),
        },
        {
            "seat": "openai",
            "role": "fable",
            "purpose": (
                "Scene/designer clarity on master notes only: scannable story of the work. "
                "Must not promote interpretation→fact. Public face may be play/riddle; "
                "soil stays disk."
            ),
            "expected_output": (
                "Markdown master.md candidate only; keep technical datasheet rows unchanged; "
                "label fiction as fiction"
            ),
        },
        {
            "seat": "kimi",
            "role": "contract",
            "purpose": (
                "Contract_trail face: layer purity, pack-first, artifact > transcript, "
                "seat purity, world_role may/must_not. Soft-skip if unkeyed."
            ),
            "expected_output": (
                "Markdown: ## Contracts ## Layer risks ## World role purity ## "
                "Artifact paths ## What Grok judges ## What stays local"
            ),
        },
        {
            "seat": "local",
            "role": "seal_critique",
            "purpose": (
                "Local seal: hardware envelope, local_prompt must exclude master essay, "
                "obligations before generation. If pack fields are complete enough, "
                "note path memory/knowledge_packs/<slug>/."
            ),
            "expected_output": (
                "Markdown: ## Local constraints ## Cut list ## Safe next FILE "
                "(local_usable write) ## Grok re-LOAD (3 bullets)"
            ),
        },
    ]


def probe_router_network() -> dict[str, Any]:
    """Cheap check-in on Mag body — no secrets, no warehouse inventory."""
    out: dict[str, Any] = {
        "ts": _utc(),
        "dash": {},
        "ollama": {},
        "nervous_head": "",
        "spider": {},
        "providers": {},
        "tips": [],
    }

    # Dashboard / doctor-ish
    try:
        import urllib.request

        req = urllib.request.Request(
            "http://127.0.0.1:8765/api/v1/nervous",
            method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=4) as r:
            body = r.read().decode("utf-8", errors="replace")
            out["dash"] = {"ok": True, "port": 8765, "nervous_live": True}
            try:
                out["dash"]["glance"] = json.loads(body)
            except json.JSONDecodeError:
                out["dash"]["raw_len"] = len(body)
    except Exception as exc:
        out["dash"] = {
            "ok": False,
            "error": str(exc)[:160],
            "tip": "mag.cmd doctor  # venv read, no spawn; do not host python main.py lab",
        }

    # Ollama
    try:
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
            models = [m.get("name") for m in (data.get("models") or []) if m.get("name")]
            out["ollama"] = {"ok": True, "n_models": len(models), "models_head": models[:8]}
    except Exception as exc:
        out["ollama"] = {"ok": False, "error": str(exc)[:120]}

    # Nervous file (pack-first path)
    ns = ROOT / "memory" / "nervous_system.md"
    if ns.is_file():
        try:
            out["nervous_head"] = ns.read_text(encoding="utf-8", errors="replace")[:500]
        except Exception:
            pass

    # Spider signals (read-only)
    try:
        from mag.spider import scan as spider_scan  # type: ignore

        out["spider"] = spider_scan() if callable(spider_scan) else {"note": "no scan"}
    except Exception:
        try:
            from mag import spider as sp

            trail = getattr(sp, "SPIDER_TRAIL", None)
            if trail and Path(trail).is_file():
                lines = Path(trail).read_text(encoding="utf-8", errors="replace").splitlines()[-5:]
                out["spider"] = {"trail_tail_n": len(lines), "ok": True}
            else:
                out["spider"] = {"ok": True, "note": "spider present, no trail"}
        except Exception as exc:
            out["spider"] = {"ok": False, "error": str(exc)[:100]}

    # Provider key presence only (no secret values)
    try:
        from models.providers import get_provider, provider_keys, load_providers

        cfg = load_providers() or {}
        for pid in ("deepseek", "openai", "openrouter", "ollama", "anthropic", "xai"):
            pcfg = get_provider(pid) or (cfg.get("providers") or {}).get(pid) or {}
            if not pcfg and pid != "ollama":
                out["providers"][pid] = {"configured": False}
                continue
            if pid == "ollama" or pcfg.get("free_local"):
                out["providers"][pid] = {"configured": True, "local": True}
                continue
            keys = provider_keys(pcfg) if pcfg else []
            out["providers"][pid] = {
                "configured": bool(keys),
                "name_in_env": bool(pcfg.get("api_key_env")),
            }
    except Exception as exc:
        out["providers"] = {"error": str(exc)[:120]}

    # Tips for operator / Grok
    if not out.get("dash", {}).get("ok"):
        out["tips"].append(
            "Dash down — mag.cmd doctor first (no spawn). "
            "If still dead AND docker works: docker compose restart mag. Not host python main.py lab."
        )
    if not out.get("ollama", {}).get("ok"):
        out["tips"].append("Ollama down — local janitor seats will fail.")
    prov = out.get("providers") or {}
    if isinstance(prov, dict):
        if not (prov.get("deepseek") or {}).get("configured"):
            out["tips"].append("DeepSeek key missing — structure seat soft-skips.")
        if not (prov.get("openai") or {}).get("configured"):
            out["tips"].append("OpenAI key missing — fable pass soft-skips.")
        if not (prov.get("openrouter") or {}).get("configured"):
            out["tips"].append("OpenRouter key missing — Kimi pass soft-skips.")

    return out


def start_checkin(
    goal: str,
    *,
    session_id: str = "tui-checkin",
    auto_run: bool = True,
    skip_network: bool = False,
) -> dict[str, Any]:
    """Freeze → probe Mag network → FILE structure refine chain → return Grok card.

    Grok TUI should: report checkin_id + chain_id, then STOP implementing.
    On return: LOAD context-pack + final artifact only (not the novel).
    """
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal — what should the structure pass organize?"}

    CHECKIN_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Freeze state
    freeze: dict[str, Any] = {}
    try:
        from mag.diary_node import freeze_context, save_auto_freeze

        freeze = freeze_context(
            session_id=session_id,
            channel="tui",
            reason="mag_checkin",
        )
        try:
            save_auto_freeze(
                session_id=session_id,
                channel="tui",
                brief={"goal": goal[:400], "kind": "checkin"},
                force=True,
            )
        except Exception:
            pass
    except Exception as exc:
        freeze = {"error": str(exc)[:160]}

    # 2) Router network check-in
    network = {} if skip_network else probe_router_network()

    # 3) Multi-seat structure chain (uses Mag refine_chain methods)
    from mag.refine_chain import start_chain

    chain_out = start_chain(
        goal,
        session_id=session_id,
        plan=structure_checkin_plan(),
        auto_run=auto_run,
    )
    chain_id = str(chain_out.get("chain_id") or "")
    # Tag chain as checkin
    try:
        from mag.refine_chain import load_chain, _save  # type: ignore

        ch = load_chain(chain_id) if chain_id else None
        if ch:
            ch["kind"] = "structure_checkin"
            ch["checkin_network"] = {
                "dash_ok": (network.get("dash") or {}).get("ok"),
                "ollama_ok": (network.get("ollama") or {}).get("ok"),
                "provider_flags": {
                    k: bool((v or {}).get("configured"))
                    for k, v in (network.get("providers") or {}).items()
                    if isinstance(v, dict)
                },
                "tips": network.get("tips") or [],
            }
            _save(ch)
    except Exception:
        pass

    checkin_id = "ck-" + (chain_id.replace("rf-", "") if chain_id else _utc()[-8:])
    card = {
        "schema": SCHEMA,
        "checkin_id": checkin_id,
        "ts": _utc(),
        "session_id": session_id,
        "goal": goal[:3000],
        "freeze": {
            "day": freeze.get("day"),
            "freeze_hash": freeze.get("freeze_hash"),
            "agent_commit": (freeze.get("agent") or {}).get("content_commit"),
            "verkle_n": (freeze.get("session_verkle") or {}).get("n_leaves"),
        },
        "network": network,
        "chain_id": chain_id,
        "chain_ok": bool(chain_out.get("ok")),
        "plan_seats": [s.get("seat") + "/" + s.get("role", "") for s in structure_checkin_plan()],
        "local_usable_hint": (
            "When chain complete, FILE with mag.local_usable.write_pack "
            "or export_game_module_to_pack(); play smoke: python -m mag.play_benchmark --level B0"
        ),
        "dual_reading": {
            "public_face": "structure_or_play_activation",
            "soil": "disk packs + engine",
            "roles": "world_roles host multi-seat self-talk without persona theater",
        },
        "grok_return": {
            "do": [
                "mag.cmd context-pack  # or python main.py context-pack",
                f"read chain final artifact under memory/working/refine_chains/{chain_id}/",
                "optional: mag.local_usable.write_pack from chain outputs",
                "judge only: acceptance, steal, unstick — do not re-implement scut",
            ],
            "stop": "Do not re-paste the novel; pack + final artifact only",
        },
    }
    path = CHECKIN_DIR / f"{checkin_id}.json"
    path.write_text(json.dumps(card, indent=2, default=str), encoding="utf-8")
    with INDEX_PATH.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": card["ts"],
                    "checkin_id": checkin_id,
                    "chain_id": chain_id,
                    "goal": goal[:120],
                    "dash_ok": (network.get("dash") or {}).get("ok"),
                },
                default=str,
            )
            + "\n"
        )

    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    tips = network.get("tips") or []
    speak = (
        f"Check-in {checkin_id}: frozen, network probed, structure chain {chain_id} filed. "
        f"Seats: janitor→deepseek→openai-fable→kimi→local seal. "
        f"Grok re-LOADs pack + final artifact only."
    )
    if tips:
        speak += " Tips: " + "; ".join(tips[:3])

    return {
        "ok": True,
        "schema": SCHEMA,
        "checkin_id": checkin_id,
        "chain_id": chain_id,
        "card_path": rel,
        "card": card,
        "chain": chain_out,
        "speak_text": speak,
        "route": "mag_checkin",
    }


def checkin_status(checkin_id: str = "", chain_id: str = "") -> dict[str, Any]:
    """Status for a check-in card + refine chain."""
    from mag.refine_chain import chain_status_speak, latest_chain, load_chain

    card = None
    if checkin_id:
        p = CHECKIN_DIR / f"{checkin_id}.json"
        if p.is_file():
            try:
                card = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                card = None
            chain_id = chain_id or str((card or {}).get("chain_id") or "")
    chain = load_chain(chain_id) if chain_id else latest_chain()
    return {
        "ok": True,
        "checkin": card,
        "chain": chain,
        "speak": chain_status_speak(chain) if chain else "No chain yet.",
    }
