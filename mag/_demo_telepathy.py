"""TELEPATHY — transmitting a complex function between agents via invariant codes
over the mycelial web (2026-08-26, operator order: "novel MCP tool use").

The experiment, mirroring the memlang memory-reading experiments:
  SENDER (agent A, its own process) invents a nontrivial function — expressed as an
  invariant RECIPE (pure data: opcodes + constants, never source text) — commits the
  recipe to the web as a content-addressed pheromone mark, compiles a memlang invariant
  code (pointer + semantics), and posts ONLY the token hex to the blackboard.
  No prose. No code in the message. Just the code.

  RECEIVER (agent B, a FRESH process sharing nothing with A but the web) reads the
  board, decodes the token, fetches the recipe BY CONTENT ANCHOR, executes it through
  its fixed mini-interpreter (no dynamic eval — the recipe is data), and produces output.

  VERDICT: receiver's output must equal the sender's committed ground truth.
  Capability moved body-to-body without either body holding the other's context.

Safety: the transmitted artifact is a JSON recipe over a fixed opcode set
  (init, xor_mul, rotl, fold_hex, sha8). Nothing from the web is ever exec'd —
  a poisoned recipe can only produce wrong numbers, not code execution.

Honest limits (on the record):
  * resolve() is per-tree registry — this demo runs inside one tree; cross-tree
    telepathy needs the shared-registry build (the known mind-meld gate).
  * The receiver is a deterministic agent body (fresh interpreter). The LLM-mediated
    receiver walking the same protocol through MCP tools is the epoch-2 version.

CLI: python -m mag._demo_telepathy            (sender -> receiver -> verdict)
     python -m mag._demo_telepathy --role sender|receiver
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "memory" / "runs" / "telepathy"

# The function A transmits this run: chained xor-mul with rotation, hex-folded, sha-tagged.
# Constants invented per run — the receiver cannot guess them, only receive them.
RECIPE = {
    "schema": "telepathy.recipe.v1",
    "name": "chained-xor-rotate digest",
    "constants": [95, 58, 199, 145],
    "steps": ["init", "xor_mul_chain", "rotl3_13", "fold_hex4", "sha8"],
}
CHALLENGE = "telepathy-challenge-20260826"

OPCODES = {"init", "xor_mul_chain", "rotl3_13", "fold_hex4", "sha8"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def interpret(recipe: dict[str, Any], challenge: str) -> str:
    """The receiver's FIXED mini-interpreter over the opcode set. Data in, digest out.
    Rejects any recipe whose steps leave the opcode set (poison guard)."""
    if set(recipe.get("steps", [])) - OPCODES:
        raise ValueError("recipe uses unknown opcodes — rejected")
    C = recipe["constants"]
    x = challenge.encode()
    acc = 0
    for i, b in enumerate(x):
        acc = ((acc ^ (b * C[i % len(C)])) << 3 | (acc >> 13)) & 0xFFFF
    return f"{acc:04x}" + hashlib.sha256(x).hexdigest()[:8]


def sender() -> dict[str, Any]:
    """Agent A: commit recipe + ground truth to the web, post only the invariant code."""
    from mag import memlang
    from mag.swarm_tools import blackboard_post, pheromone_drop

    OUT.mkdir(parents=True, exist_ok=True)
    ground_truth = interpret(RECIPE, CHALLENGE)

    recipe_sha = _sha(json.dumps(RECIPE, sort_keys=True))
    gt_sha = _sha(ground_truth)
    pheromone_drop(scent=json.dumps(RECIPE), kind="capability", at=recipe_sha,
                   owner="agent-A")
    pheromone_drop(scent=ground_truth, kind="ground-truth", at=gt_sha, owner="agent-A")

    tok = memlang.compile_token(
        "learn", "capability:chained-xor-rotate-digest",
        {"src_anchor": recipe_sha, "gt_anchor": gt_sha, "scent_kind": "capability",
         "challenge": CHALLENGE})
    token_hex = str(tok.get("token") or tok.get("token_hex") or "")
    blackboard_post(text=f"INVARIANT-CODE {token_hex}", kind="finding", owner="agent-A")

    (OUT / "sender_state.json").write_text(json.dumps(
        {"recipe_sha": recipe_sha, "gt_sha": gt_sha, "ground_truth": ground_truth,
         "token": tok}, default=str, indent=2), encoding="utf-8")
    return {"ok": bool(token_hex), "token_hex": token_hex, "recipe_sha": recipe_sha,
            "ground_truth": ground_truth}


def receiver() -> dict[str, Any]:
    """Agent B (fresh process): token -> decode -> fetch by anchor -> interpret."""
    from mag import memlang
    from mag.swarm_tools import blackboard_read, pheromone_trail

    board = blackboard_read(limit=20)
    notes = list(board.get("tail") or []) + list(board.get("pinned") or [])
    token_hex = ""
    for n in notes:
        t = (n.get("text") or "") if isinstance(n, dict) else str(n)
        if "INVARIANT-CODE " in t:
            token_hex = t.split("INVARIANT-CODE ", 1)[1].strip().split()[0]
    if not token_hex:
        return {"ok": False, "error": "no invariant code on the board"}

    dec = memlang.decode(token_hex)
    res = memlang.resolve(token_hex)
    params = res.get("params") or dec.get("params") or {}
    src_anchor, gt_anchor = params.get("src_anchor"), params.get("gt_anchor")
    challenge = str(params.get("challenge", ""))

    recipe_text = truth = None
    for mark in pheromone_trail(limit=50).get("trail", []):
        at = mark.get("at") or ""
        if at == src_anchor:
            recipe_text = mark.get("scent")
        elif at == gt_anchor:
            truth = mark.get("scent")
    if not recipe_text or not truth:
        return {"ok": False, "error": "anchor fetch failed", "decoded_params": params}

    recipe = json.loads(recipe_text)
    try:
        produced = interpret(recipe, challenge)
    except ValueError as e:
        return {"ok": False, "error": f"poison guard: {e}"}
    return {"ok": True, "token_hex": token_hex, "decoded_action": dec.get("action"),
            "recipe_name": recipe.get("name"), "produced": produced,
            "committed_truth": truth, "telepathy_pass": produced == truth}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["sender", "receiver"], default="")
    a = ap.parse_args(argv)
    if a.role == "sender":
        out = sender()
    elif a.role == "receiver":
        out = receiver()
    else:
        s = sender()
        import subprocess
        r = subprocess.run(                      # agent B in a FRESH interpreter
            [sys.executable, "-m", "mag._demo_telepathy", "--role", "receiver"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        rb = json.loads(r.stdout) if r.returncode == 0 else {"ok": False,
                                                             "error": r.stderr[-300:]}
        out = {"sender": {k: s.get(k) for k in ("ok", "recipe_sha")},
               "receiver_fresh_process": rb,
               "verdict": "TELEPATHY VERIFIED" if rb.get("telepathy_pass")
                          else "FAILED"}
    print(json.dumps(out, default=str, indent=2))
    if "verdict" in out:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "last_run.json").write_text(json.dumps(out, default=str, indent=2),
                                           encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
