"""grok_route — the cash-routing guard for xAI/grok (operator law, 2026-09-05).

THE BLEED: salon_runner.py and grok_rightsize.py fired api.x.ai chat completions on the
PAYG cash key whenever XAI_API_KEY was set — ~$17 cash burned Aug 30–Sep 1 (billing CSV
2026-08-30..09-05: $4.72 + $6.23 + $5.74, ~500-840 calls/day), while TWO subscription
lanes sat idle: (1) the local Grok CLI (~/.grok/bin/grok — subscription-backed, the
sanctioned builder/gallery lane) and (2) the AOS lent Super-Grok surface (mag/aos_grok.py
— budgeted, specific-ask-only, partner courtesy contract).

LAW (operator 09-05: "route it through the two grok lanes we are granted with our
subscriptions"): grok work rides subscription lanes FIRST. api.x.ai cash is a
last-resort that must be EXPLICITLY armed per session by the operator:

    set XAI_CASH_ALLOWED=1   # only when he says so, for a named job

Default behavior of grok_cash_allowed(): False. Any lane that wants the cash endpoint
must call this guard; no guard call = no cash call. Salons lose the grok witness
honestly (down-lane semantics) instead of silently spending.

Usage in callers:
    from mag.grok_route import grok_cash_allowed, grok_cli_ok
    if grok_cash_allowed(): ...api.x.ai...          # explicit operator arm
    elif grok_cli_ok():  ...subprocess grok CLI...  # subscription lane
    else: report down, move on                       # honest witness loss

Schema: grok_route.v1
"""
from __future__ import annotations

import os
import shutil


def grok_cash_allowed() -> bool:
    """True ONLY if the operator explicitly armed cash spend this session."""
    return os.environ.get("XAI_CASH_ALLOWED", "").strip() == "1"


def grok_cli_ok() -> bool:
    """True if the subscription-backed grok CLI is installed and reachable."""
    return bool(shutil.which("grok") or os.path.exists(
        os.path.expanduser("~/.grok/bin/grok")))


def route_report() -> str:
    return (f"grok_route.v1 cash={'ARMED' if grok_cash_allowed() else 'blocked'} "
            f"cli={'ok' if grok_cli_ok() else 'missing'} "
            f"aos=lane(mag/aos_grok.py, budget-gated)")
