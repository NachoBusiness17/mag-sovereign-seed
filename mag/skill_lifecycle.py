"""skill_lifecycle — EPHEMERAL one-turn skill flag prototype (adk-week steal).

Steal lineage (why this exists):
  1. ZCode skills-plugins injects SKILL.md instruction packs into sessions and
     they STAY loaded; the one flag that removes a skill removes its tool with
     it, so docs and tool switch as one unit
     (zcode-repo/apps/zcode-cli/packages/bootstrap/src/app/dynamic-workflow-gate.ts:21-27,
     create-app.ts:752-758; steal row "Tool gated by its own skill" in
     corpus/steal/ZCODE_REPO_STEAL_MAP_20260924.md, skills-plugins section).
  2. Google ADK gates behavior behind ADK_ENABLE_* env vars read AT CHECK TIME,
     enabled iff the value (case-insensitive) is '1' or 'true', default off
     (mine/raw/agent_platform/google/adk-python/src/google/adk/features/_feature_registry.py,
     utils/env_utils.is_env_enabled). Pattern imported from the adk-week lane.

Estate patch (the prototype): a skill can be LOADED into the seat tool registry
(tools.TOOL_MAP, the same registry backend/server.py and the executor serve) as
a real callable tool; it stays callable for EXACTLY ONE seat-turn, then
auto-unloads at the turn boundary. Gate:

    ADK_ENABLE_SKILL_LIFECYCLE=1   (or 'true', case-insensitive)

Default OFF: with the gate unset, load() refuses, the registry is never
mutated, and a seat's tool surface is identical to before this module existed.

Seat-turn semantics (meters, not prose):
  - turn counter starts at 0; begin_turn() is the seat's turn start (increments)
  - load() during seat-turn T registers the tool, stamped loaded_turn=T
  - end_turn() is the turn boundary: every ephemeral skill loaded at or before
    the current turn unloads and cannot dispatch again (unknown tool, exit 127)
  - load() also sweeps stale entries first, so a seat that never calls
    end_turn() still cannot accumulate loaded skills across turns

Safety: refuses to shadow a static registry tool, never unloads a static tool,
unload is idempotent, and every mutation returns a receipt (execution receipt
before fix).

Skill sources (read-only, on-disk estate packs):
  - mag/skill_seat.py SKILL_WEAVES (ponytail, caveman weave docs)
  - configs/skills.yaml rows carrying a resolvable `path`
    (resolution rules identical to mag/skills_pack.py: repo-relative or ~/)

Schema: mag_skill_lifecycle.v1 · deterministic · $0 (no LLM, no network)
CLI:    python -m mag.skill_lifecycle status
        python -m mag.skill_lifecycle load <skill_id>
        python -m mag.skill_lifecycle end-turn
        python -m mag.skill_lifecycle self-test
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # pragma: no cover - bare import outside the repo
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "mag_skill_lifecycle.v1"
ENV_GATE = "ADK_ENABLE_SKILL_LIFECYCLE"

# ---------------------------------------------------------------------------
# the gate (ADK pattern: is_env_enabled, default '0' = off)
# ---------------------------------------------------------------------------


def is_enabled() -> bool:
    """ADK_ENABLE_SKILL_LIFECYCLE gate. Default OFF. '1'/'true' enable."""
    return os.environ.get(ENV_GATE, "0").strip().lower() in ("1", "true")


# ---------------------------------------------------------------------------
# skill sources
# ---------------------------------------------------------------------------


def _resolve_path(rel: str) -> Path | None:
    """Same rules as mag/skills_pack.py: repo-relative, or ~-expanded."""
    if not rel:
        return None
    if rel.startswith("~/") or rel.startswith("~\\"):
        p = Path.home() / rel[2:]
    else:
        p = ROOT / rel
    return p if p.is_file() else None


def _skill_paths() -> dict[str, Path]:
    from mag.skill_seat import SKILL_WEAVES

    out: dict[str, Path] = {}
    for sid, rel in SKILL_WEAVES.items():
        p = _resolve_path(rel)
        if p is not None:
            out[sid] = p
    cfg = ROOT / "configs" / "skills.yaml"
    if cfg.is_file():
        try:
            import yaml

            data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        for row in data.get("skills") or []:
            if not isinstance(row, dict):
                continue
            sid = row.get("id")
            p = _resolve_path(row.get("path") or "")
            if sid and p is not None:
                out[str(sid)] = p
    return out


def available_skills() -> dict[str, str]:
    """skill_id -> absolute path, for every skill this module can load."""
    return {sid: str(p) for sid, p in sorted(_skill_paths().items())}


def skill_body(skill_id: str) -> str:
    p = _skill_paths().get(skill_id)
    if p is None:
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# seat-turn state (policy layer; registry mechanism lives in tools/__init__.py)
# ---------------------------------------------------------------------------

_turn = 0
# tool_name -> {"skill_id", "path", "loaded_turn"}
_loaded: dict[str, dict[str, Any]] = {}


def current_turn() -> int:
    return _turn


def reset_state() -> None:
    """Test/demo seam: clear the turn counter and the loaded table.

    Registry overlay is NOT touched here; call tools.unload_ephemeral_all()
    separately if the overlay must be cleared too.
    """
    global _turn
    _turn = 0
    _loaded.clear()


def begin_turn() -> int:
    """Seat-turn start: advance the counter. Returns the new turn number."""
    global _turn
    _turn += 1
    return _turn


def _tool_name(skill_id: str) -> str:
    return f"skill_{skill_id}"


def _sweep_stale() -> list[str]:
    """Unload any skill loaded on a turn older than the current one."""
    gone: list[str] = []
    for name in sorted(_loaded):
        if _loaded[name]["loaded_turn"] < _turn:
            res = unload(name)
            if res.get("ok"):
                gone.append(name)
    return gone


def load(skill_id: str) -> dict[str, Any]:
    """Load a skill into the seat tool registry for exactly one seat-turn.

    Gate OFF -> {"ok": False, "reason": "gate_off"}, registry untouched.
    Gate ON  -> tools.TOOL_MAP gains f"skill_<skill_id>" (callable this turn);
                end_turn() auto-unloads it.
    """
    import tools

    if not is_enabled():
        return {
            "ok": False,
            "reason": "gate_off",
            "gate": ENV_GATE,
            "hint": f"set {ENV_GATE}=1 to enable the one-turn skill lifecycle",
        }
    stale = _sweep_stale()
    body = skill_body(skill_id)
    if not body:
        return {
            "ok": False,
            "reason": "unknown_skill",
            "skill_id": skill_id,
            "available": sorted(available_skills()),
        }
    name = _tool_name(skill_id)
    rec = {
        "skill_id": skill_id,
        "path": available_skills().get(skill_id, ""),
        "loaded_turn": _turn,
    }
    reg = tools.register_ephemeral(name, _make_skill_tool(skill_id, name, rec), meta=dict(rec))
    if not reg.get("ok"):
        reg["skill_id"] = skill_id
        reg["swept_stale"] = stale
        return reg
    _loaded[name] = rec
    return {
        "ok": True,
        "tool": name,
        "skill_id": skill_id,
        "loaded_turn": _turn,
        "unloads_at_turn": _turn + 1,
        "swept_stale": stale,
    }


def _make_skill_tool(skill_id: str, name: str, rec: dict[str, Any]):
    def _run_skill_tool(**kw: Any) -> dict[str, Any]:
        body = skill_body(skill_id)
        return {
            "ok": bool(body),
            "tool": name,
            "skill_id": skill_id,
            "loaded_turn": rec["loaded_turn"],
            "unloads_at_turn": rec["loaded_turn"] + 1,
            "body_chars": len(body),
            "body": body,
        }

    return _run_skill_tool


def unload(tool_name: str) -> dict[str, Any]:
    """Explicit unload. Idempotent; never touches static registry tools."""
    import tools

    res = tools.unregister_ephemeral(tool_name)
    if res.get("ok") and not res.get("already_gone"):
        rec = _loaded.pop(tool_name, {})
        res["skill_id"] = rec.get("skill_id")
    return res


def end_turn() -> dict[str, Any]:
    """Seat-turn boundary: auto-unload every skill loaded this seat-turn."""
    import tools

    gone: list[dict[str, Any]] = []
    for name in sorted(_loaded):
        rec = _loaded[name]
        res = tools.unregister_ephemeral(name)
        if res.get("ok") and not res.get("already_gone"):
            _loaded.pop(name, None)
            gone.append(
                {
                    "tool": name,
                    "skill_id": rec["skill_id"],
                    "loaded_turn": rec["loaded_turn"],
                }
            )
    damaged = sorted(tools.STATIC_TOOLS - set(tools.TOOL_MAP))
    return {
        "ok": not damaged,
        "turn": _turn,
        "unloaded": [g["tool"] for g in gone],
        "receipts": gone,
        "damaged_static": damaged,
        "remaining_ephemeral": tools.ephemeral_tool_names(),
    }


def status() -> dict[str, Any]:
    import tools

    return {
        "schema": SCHEMA,
        "gate": ENV_GATE,
        "enabled": is_enabled(),
        "turn": _turn,
        "loaded": [
            {
                "tool": name,
                "skill_id": rec["skill_id"],
                "loaded_turn": rec["loaded_turn"],
                "unloads_at_turn": rec["loaded_turn"] + 1,
            }
            for name, rec in sorted(_loaded.items())
        ],
        "available_skills": sorted(available_skills()),
        "registry_size": len(tools.TOOL_MAP),
        "ephemeral": tools.ephemeral_tool_names(),
    }


# ---------------------------------------------------------------------------
# CLI (demo: status / load / end-turn, plus a dependency-free self-test)
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="mag.skill_lifecycle",
        description="EPHEMERAL one-turn skill flag behind ADK_ENABLE_SKILL_LIFECYCLE (default off)",
    )
    ap.add_argument("cmd", choices=["status", "load", "end-turn", "self-test"])
    ap.add_argument("skill_id", nargs="?", default="")
    args = ap.parse_args(argv)

    if args.cmd == "status":
        print(json.dumps(status(), indent=2))
        return 0
    if args.cmd == "load":
        if not args.skill_id:
            print("usage: python -m mag.skill_lifecycle load <skill_id>")
            return 2
        res = load(args.skill_id)
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1
    if args.cmd == "end-turn":
        print(json.dumps(end_turn(), indent=2))
        return 0
    if args.cmd == "self-test":
        return _self_test()
    return 2


def _self_test() -> int:
    """In-process self-test, no pytest required. Exit 0 = all checks passed."""
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    import tools

    # 1. default-off: a clean env must refuse to mutate the registry
    os.environ.pop(ENV_GATE, None)
    baseline = set(tools.TOOL_MAP)
    res_off = load("ponytail")
    check("gate_default_off", is_enabled() is False and res_off.get("reason") == "gate_off")
    check("registry_untouched_when_off", set(tools.TOOL_MAP) == baseline)

    # 2. gate values (ADK is_env_enabled semantics)
    for val, want in (
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("0", False),
        ("false", False),
        ("", False),
    ):
        os.environ[ENV_GATE] = val
        check(f"gate_value_{val or 'empty'}", is_enabled() is want)
    os.environ[ENV_GATE] = "1"

    # 3. one-turn lifecycle: load -> callable -> end_turn -> gone
    tools.unload_ephemeral_all()
    r = load("ponytail")
    check("load_ok", r.get("ok") is True, json.dumps(r)[:140])
    name = str(r.get("tool") or "")
    check("tool_in_registry", name in tools.TOOL_MAP)
    out = tools.dispatch(name, {})
    check(
        "dispatch_serves_skill",
        out.get("ok") is True and out.get("skill_id") == "ponytail",
    )
    check("body_nonempty", (out.get("body_chars") or 0) > 0)
    et = end_turn()
    check("end_turn_unloads", name in (et.get("unloaded") or []), json.dumps(et)[:140])
    check("tool_gone_after_turn", name not in tools.TOOL_MAP)
    out2 = tools.dispatch(name, {})
    check(
        "dispatch_unknown_after_unload",
        out2.get("ok") is False and out2.get("exit_code") == 127,
    )
    check("registry_back_to_baseline", set(tools.TOOL_MAP) == baseline)

    # 4. stale sweep: a seat that misses end_turn cannot accumulate skills
    load("ponytail")
    begin_turn()
    r2 = load("caveman")
    check(
        "stale_swept_on_next_load",
        r2.get("ok") is True and r2.get("swept_stale") == ["skill_ponytail"],
        json.dumps(r2)[:140],
    )
    end_turn()

    # 5. safety: static tools intact, unknown skills refused, baseline exact
    check("unknown_skill_refused", load("no-such-skill").get("reason") == "unknown_skill")
    check("static_tools_intact", tools.STATIC_TOOLS <= set(tools.TOOL_MAP))
    base_res = tools.dispatch("list_dir", {"path": "."})
    check("static_tool_still_dispatches", base_res.get("ok") is True)
    end_turn()
    check("final_registry_is_baseline", set(tools.TOOL_MAP) == baseline)
    os.environ.pop(ENV_GATE, None)

    failed = [c for c in checks if not c[1]]
    for cname, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {cname}  {detail}")
    print(f"{len(checks) - len(failed)}/{len(checks)} checks passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
