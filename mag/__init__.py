"""Sovereign Mag \u2014 background companion loop.

Lazy package: importing ``mag`` or any ``mag.X`` submodule must NOT pull the
LangGraph daemon chain (mag.daemon \u2192 mag.act \u2192 graph \u2192 langgraph).
``run_cycle`` / ``run_loop`` are resolved on first attribute access so the rest
of the CLI (plan, dispatch, agent, improve, lab, ...) works without langgraph.
"""
from __future__ import annotations

__all__ = ["run_cycle", "run_loop"]


def __getattr__(name: str):
    if name in ("run_cycle", "run_loop"):
        from .daemon import run_cycle, run_loop
        return {"run_cycle": run_cycle, "run_loop": run_loop}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
