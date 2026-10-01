"""Deterministic Local seat for testing Desk protocol independently of Ollama."""
from __future__ import annotations

import re


def respond(*, user: str) -> str:
    """Return protocol-shaped output from the current operator instruction."""
    note_match = re.search(r"## Operator note\n([\s\S]*?)(?=\n\n## |\Z)", user)
    note = (note_match.group(1) if note_match else user).strip()

    exact = re.search(
        r"(?:output|Reply with) EXACTLY "
        r"(?:these \d+ words|this sentence once|the same sentence again)"
        r"(?: with no other text)?:\s*(.+)",
        note,
        re.I,
    )
    if exact:
        reply = exact.group(1).strip()
        edit = f"### Local · simulated commit\nExact-response checkpoint completed: {reply}"
    elif re.search(r"run git status", note, re.I):
        reply = "I cannot run shell commands from the Desk; no output was produced."
        edit = "### Local · simulated boundary\nRefused fake execution and requested an evidence-bearing Shell handoff."
    else:
        reply = "Local simulator committed the requested handoff step."
        edit = "### Local · simulated commit\nDeterministic Local completed one board-edit checkpoint."

    return f"### Reply\n{reply}\n\n### Canvas edit\n{edit}\n"
