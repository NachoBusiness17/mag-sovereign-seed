"""subscriptions — the ledger that manages what we pay for (2026-08-25).

Operator: "we have a lot of subscriptions now i need you to manage and make sure we are
using or canceling appropriately."

Every subscription/surface: type (sub/usage/prepaid/free), estimated monthly cost, key env,
ACTUAL usage from the provider ledger, and a verdict (USE / CANCEL / WATCH). The ledger reads
real bytes (provider_usage.jsonl + .env key presence); it never guesses usage.

Schema: subscriptions.v1
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
USAGE = ROOT / "logs" / "provider_usage.jsonl"


def _env() -> None:
    try:
        from models.env_load import load_dotenv
        load_dotenv()
    except Exception:  # noqa: BLE001
        pass


def _usage() -> dict[str, dict[str, Any]]:
    """Per-provider aggregates from the real ledger."""
    by = defaultdict(lambda: {"calls": 0, "pt": 0, "ct": 0})
    if USAGE.is_file():
        for line in USAGE.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            prov = str(r.get("provider") or r.get("provider_id") or "?")
            by[prov]["calls"] += 1
            by[prov]["pt"] += int(r.get("prompt_tokens") or 0)
            by[prov]["ct"] += int(r.get("completion_tokens") or 0)
    return dict(by)


# ── THE LEDGER ──────────────────────────────────────────────────────────────────────────
# B2-521 DORMANT GATE (2026-09-26): the free_lanes row still claimed "cerebras 85%" and
# "nvidia credits" after B2-36/B2-61 declared both dormant (card-gated 30-day trial, chat
# 402 no-credit; NVIDIA 410 EOL; mag/doctor.py:607: dormant is a declared state). The row
# is now built from the live roster: dormant ids drop out of name, note, and keys; operator
# GO flips the flag and the claims return with no code edit. Receipt:
# watch/inbox/burn_wave_20260926/B2_521_cerebras_stragglers_20260926.md
from mag.dormant import dormant_ids as _dormant_provider_ids  # noqa: E402

_BACKBONE_CLAIMS: list[tuple[str, str, str]] = [
    # (provider id, key env exactly as the row carried it, the measured claim in the note)
    ("groq", "GROQ_API_KEY", "groq 91% ok"),
    ("cerebras", "CEREBAS_API_KEY", "cerebras 85%"),
    ("z_ai", "", "z_ai 81%"),
    ("nvidia", "", "nvidia credits"),
    ("ollama", "", "ollama local"),
]
_LIVE_BACKBONE = [c for c in _BACKBONE_CLAIMS if c[0] not in _dormant_provider_ids()]

SUBSCRIPTIONS: list[dict[str, Any]] = [
    {"id": "deepseek", "name": "DeepSeek API (pay-as-you-go)", "type": "usage",
     "cost_mo": "~$30-90 (was $3/day heavy windows)", "keys": ["DEEPSEEK_API_KEY"],
     "verdict": "USE-AS-BRAKE",
     "note": "THE big line: 21k+ calls / 1.16B prompt tokens on v4-flash in the ledger. Default "
             "swap to z_ai + coder on GLM plan should drop this hard. Brake only now."},
    {"id": "glm_coding_lite", "name": "GLM Coding Lite (z.ai)", "type": "sub", "cost_mo": "~$18",
     "recurring": True, "quantity": 1, "monthly_usd": 18.0, "price_status": "operator_declared",
     "billing_period": "monthly", "source_url": "https://docs.z.ai/guides/overview/pricing",
     "keys": ["ZAI_API_KEY"], "verdict": "USE",
     "note": "Frontier coder, dedicated quota, cache-hit-scaled. Active: coder harness + "
             "Cursor/ZCode. This replaces DeepSeek for coding."},
    {"id": "together", "name": "Together AI", "type": "sub", "cost_mo": "$5",
     "recurring": True, "quantity": 1, "monthly_usd": 5.0, "price_status": "operator_declared",
     "billing_period": "monthly",
     "keys": ["TOGETHER_API_KEY"], "verdict": "USE",
     "note": "Independent witness + nvidia-model fallback. Verified working (deepseek-v4-flash "
             "serverless, 1M ctx). Cheap independence."},
    {"id": "cursor", "name": "Cursor (desktop)", "type": "sub", "cost_mo": "unknown — verify plan",
     "recurring": True, "quantity": 1, "monthly_usd": None, "published_floor_usd": 20.0,
     "price_status": "needs_confirmation", "billing_period": "monthly",
     "plan_options": {"Hobby": 0.0, "Pro": 20.0, "Teams Standard": 40.0},
     "source_url": "https://cursor.com/pricing",
     "keys": ["CURSOR_API_KEY"], "verdict": "WATCH",
     "note": "Just installed desktop. Worth keeping ONLY if wired to the GLM coding plan "
             "(supported tool, rides Lite quota). Otherwise it's its own meter."},
    {"id": "autoclaw", "name": "AutoClaw (z.ai desktop)", "type": "free", "cost_mo": "$0",
     "keys": [], "verdict": "USE",
     "note": "Free credits (26k) + GLM plan boost (150%). Busywork/IM/browser surface."},
    {"id": "zcode", "name": "ZCode (GLM desktop)", "type": "free", "cost_mo": "$0 (plan)",
     "keys": [], "verdict": "USE",
     "note": "First-party GLM editor on the plan. The interactive coding window."},
    {"id": "openclaw", "name": "OpenClaw (open source)", "type": "free", "cost_mo": "$0",
     "keys": [], "verdict": "USE",
     "note": "Agent kernel, CLI installed, automations/plugins/MCP. Headless agentic path."},
    {"id": "grok", "name": "Grok / SuperGrok (2 seats)", "type": "sub", "cost_mo": "unknown — verify SuperGrok vs Plus",
     "recurring": True, "quantity": 2, "monthly_usd": None, "published_floor_usd": 30.0,
     "price_status": "needs_confirmation", "billing_period": "monthly",
     "plan_options": {"SuperGrok": 30.0, "SuperGrok Plus": 100.0},
     "source_url": "https://x.ai/pricing",
     "keys": ["XAI_API_KEY", "XAI_API_KEY_2", "GROK_API_KEY", "GROK_API_KEY_2"],
     "verdict": "WATCH",
     "note": "Used for escalation/frontier (grok-4.5/4-latest/mini in ledger, $0 recorded = "
             "subscription seat). Worth it while used for escalation; check vs plan."},
    {"id": "chatgpt", "name": "ChatGPT (1 seat)", "type": "sub", "cost_mo": "unknown — verify Go, Plus, or Pro",
     "recurring": True, "quantity": 1, "monthly_usd": None, "published_floor_usd": 8.0,
     "price_status": "needs_confirmation", "billing_period": "monthly",
     "plan_options": {"Go": 8.0, "Plus": 20.0, "Pro": 200.0},
     "source_url": "https://openai.com/chatgpt/pricing",
     "keys": ["OPENAI_API_KEY"], "verdict": "WATCH",
     "note": "Interactive ChatGPT subscription is separate from OpenAI API receipts and Codex usage. Confirm the plan and billing account."},
    {"id": "github_copilot", "name": "GitHub Copilot (1 seat)", "type": "sub", "cost_mo": "unknown — verify Pro, Pro+, Max, or Business",
     "recurring": True, "quantity": 1, "monthly_usd": None, "published_floor_usd": 10.0,
     "price_status": "needs_confirmation", "billing_period": "monthly",
     "plan_options": {"Pro": 10.0, "Pro+": 39.0, "Max": 100.0, "Business": 19.0},
     "source_url": "https://github.com/features/copilot",
     "keys": [], "verdict": "WATCH",
     "note": "Copilot subscription is fixed seat spend; its included model credits are not joined to Mag token receipts."},
    {"id": "openrouter", "name": "OpenRouter (2 accounts)", "type": "prepaid",
     "cost_mo": "prepaid credits (a1 funded)", "keys": ["OPENROUTER_API_KEY", "OPENROUTER_API_KEY_2"],
     "verdict": "USE-THEN-REVIEW",
     "note": "Free lanes (many :free models) + funded account 1. Use the free lanes; don't "
             "refill the funded account unless free tiers can't carry."},
    {"id": "anthropic", "name": "Anthropic / Claude", "type": "sub", "cost_mo": "check",
     "keys": ["ANTHROPIC_API_KEY"], "verdict": "CHECK",
     "note": "Key exists but NO usage in our ledger (claude CLI now points at GLM coding "
             "endpoint). If a paid Claude sub is idle, cancel."},
    {"id": "openai", "name": "OpenAI API", "type": "usage", "cost_mo": "low",
     "keys": ["OPENAI_API_KEY"], "verdict": "WATCH",
     "note": "20 calls (gpt-4o-mini) in ledger. Mostly covered by OpenRouter/plan. Check if "
             "the key funds anything we actually need."},
    {"id": "gemini", "name": "Google Gemini", "type": "usage", "cost_mo": "low",
     "keys": ["GEMINI_API_KEY", "GOOGLE_API_KEY"], "verdict": "WATCH",
     "note": "5 calls (gemini-2.0-flash) in ledger. Near-idle; only keep if needed for "
             "multimodal/vision work."},
    {"id": "vast", "name": "Vast.ai (GPU rental)", "type": "usage", "cost_mo": "check",
     "keys": ["VASTAI_API_KEY"], "verdict": "CHECK",
     "note": "GPU rental (saelis). If the instance is idle/not used, that's recurring cost "
             "with no benefit — terminate it."},
    {"id": "free_lanes",
     "name": "Free lanes (" + "/".join(c[0] for c in _LIVE_BACKBONE) + " free)",
     "type": "free", "cost_mo": "$0",
     "keys": [c[1] for c in _LIVE_BACKBONE if c[1]],
     "verdict": "USE",
     "note": "The backbone: " + ", ".join(c[2] for c in _LIVE_BACKBONE)
             + ". No cost. Cadence learned for their calm hours."},
]


def status() -> dict[str, Any]:
    _env()
    usage = _usage()
    rows = {}
    for s in SUBSCRIPTIONS:
        keys_ok = any(os.environ.get(k, "").strip() for k in s.get("keys", []))
        u = usage.get(s["id"], {})
        rows[s["id"]] = {
            "name": s["name"], "type": s["type"], "cost_mo": s["cost_mo"],
            "verdict": s["verdict"], "note": s["note"],
            "key_present": keys_ok,
            "ledger_calls": u.get("calls", 0),
            "ledger_prompt_tokens": u.get("pt", 0),
        }
    return {"ok": True, "schema": "subscriptions.v1", "n": len(SUBSCRIPTIONS),
            "note": "verdicts: USE=keep active; USE-AS-BRAKE=only when free fails; "
                    "CANCEL/CHECK=idle or unverified cost; WATCH=keep but review; "
                    "USE-THEN-REVIEW=use existing credits, don't refill",
            "subscriptions": rows}


if __name__ == "__main__":
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else "status"
    if arg == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
