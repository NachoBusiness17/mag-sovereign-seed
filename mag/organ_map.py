"""Organ map — receipts-first inventory of the system's load-bearing organs.

The codebase has several catalogs, but none answers the operator's actual question:
what exists, what is callable, what has a state path, what has deterministic proof, and
what was observed alive recently?  This module keeps those claims separate.  ``map_organs``
is read-only; ``snapshot`` is the explicit writer for a generated map.

Status law:
  DECLARED      source/config path exists
  INSTRUMENTED  the advertised callable imports
  WIRED         a named caller surface exists
  STATEFUL      a declared state/receipt path exists
  VERIFIED      a deterministic probe passes
  LIVE          a recent successful receipt exists for this organ
  GHOST         no evidence beyond a declaration

Schema: organ_map.v1 · deterministic + $0 · no LLM · no network
CLI: python -m mag.organ_map status | snapshot
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "organ_map.v1"
OUT = ROOT / "memory" / "runs" / "organ_map" / "latest.json"
LIVE_MAX_SECONDS = 24 * 60 * 60

# The registry is deliberately small and explicit.  It is the load-bearing map, not a
# second 855-file catalog.  Every entry must say what evidence would make its claim true.
REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "id": "water_computer",
        "label": "water computer",
        "module": "mag.water_computer",
        "callable": "_play_demo",
        "source": "mag/water_computer.py",
        "wired_by": ["mag/water_swarm.py"],
        "state_paths": [],
        "receipt_paths": [],
        "proof": "water_glass",
    },
    {
        "id": "manifest",
        "label": "chain manifest",
        "module": "mag.manifest",
        "callable": "verify",
        "source": "mag/manifest.py",
        "wired_by": ["mag/manifest.py"],
        "state_paths": ["state/manifest_anchor.json"],
        "receipt_paths": [],
        "proof": "manifest",
    },
    {
        "id": "context_admission",
        "label": "context admission",
        "module": "mag.context_admission",
        "callable": "assess",
        "source": "mag/context_admission.py",
        "wired_by": ["mag/agent_cli.py"],
        "state_paths": ["memory/runs/context_admission/receipts.jsonl"],
        "receipt_paths": ["memory/runs/context_admission/receipts.jsonl"],
        "proof": "context_admission",
    },
    {
        "id": "context_pack",
        "label": "context pack",
        "module": "mag.context_pack",
        "callable": "build_context_pack",
        "source": "mag/context_pack.py",
        "wired_by": ["mag/agent_cli.py"],
        "state_paths": ["memory/context_pack_latest.md"],
        "receipt_paths": [],
        "proof": "import",
    },
    {
        "id": "context_checkpoint",
        "label": "context checkpoint",
        "module": "mag.context_checkpoint",
        "callable": "ContextCheckpoint",
        "source": "mag/context_checkpoint.py",
        "wired_by": ["mag/agent_cli.py"],
        "state_paths": ["memory/checkpoints"],
        "receipt_paths": [],
        "proof": "import",
    },
    {
        "id": "swarm_surface",
        "label": "swarm surface",
        "module": "mag.swarm_surface",
        "callable": "route_novel",
        "source": "mag/swarm_surface.py",
        "wired_by": ["mag/autonomous_research.py", "mag/swarm_worker.py"],
        "state_paths": ["memory/swarm_surface/sent.jsonl"],
        # sent.jsonl proves enqueue intent, not worker completion or liveness.
        "receipt_paths": [],
        "proof": "import",
    },
    {
        "id": "swarm_worker",
        "label": "swarm worker",
        "module": "mag.swarm_worker",
        "callable": "run_rightsized_once",
        "source": "mag/swarm_worker.py",
        "wired_by": ["mag/swarm_local_drain.py", "mag/swarm_surface.py"],
        "state_paths": ["memory/runs/swarm_worker/queue", "memory/runs/swarm_worker/results"],
        "receipt_paths": ["memory/runs/swarm_worker/results"],
        "proof": "import",
    },
    {
        "id": "verkle_knot",
        "label": "verkle knot",
        "module": "mag.verkle_knot",
        "callable": "prove_latest",
        "source": "mag/verkle_knot.py",
        "wired_by": ["mag/manifest.py", "mag/agent_cli.py"],
        "state_paths": ["memory/biography/verkle_chain.jsonl"],
        # The chain is durable state, not a per-run liveness receipt.
        "receipt_paths": [],
        "proof": "verkle",
    },
    {
        "id": "trajectory_rib",
        "label": "trajectory to RIB compiler",
        "module": "mag.trajectory_rib",
        "callable": "compile_tape",
        "source": "mag/trajectory_rib.py",
        "wired_by": ["main.py"],
        "state_paths": ["memory/runs/trajectory_rib/compiled.jsonl"],
        "receipt_paths": ["memory/runs/trajectory_rib/compiled.jsonl.meta.json"],
        "proof": "bounded_span",
    },
    {
        "id": "live_ops_readiness",
        "label": "live operations readiness observer",
        "module": "mag.live_ops_readiness",
        "callable": "snapshot",
        "source": "mag/live_ops_readiness.py",
        "wired_by": ["mag/live_report.py"],
        "state_paths": ["memory/runs/live_ops/readiness.json"],
        "receipt_paths": ["memory/runs/live_ops/readiness.json"],
        "proof": "observer_only",
    },
    {
        "id": "operator_mode",
        "label": "durable operator mode",
        "module": "mag.operator_mode",
        "callable": "read",
        "source": "mag/operator_mode.py",
        "wired_by": ["mag/autorun_common.py", "mag/local_scheduler.py", "scripts/container/drain_worker.py", "mag/agent_cli.py", "mag/live_ops_readiness.py"],
        "state_paths": ["state/operator_mode.json", "state/operator_mode.jsonl"],
        "receipt_paths": ["state/operator_mode.json", "state/operator_mode.jsonl"],
        "proof": "atomic_control_file",
    },
    {
        "id": "dirac_loop",
        "label": "Dirac loop",
        "module": "mag.dirac_loop",
        "callable": "scan",
        "source": "mag/dirac_loop.py",
        "wired_by": ["mag/dogfood_audit.py"],
        "state_paths": [],
        "receipt_paths": [],
        "proof": "dirac",
    },
    {
        "id": "openclaw",
        "label": "OpenClaw runtime policy",
        "module": "",
        "callable": "",
        "source": "deploy/openclaw/openclaw.container.json",
        "wired_by": ["docker-compose.yml", "deploy/openclaw/entrypoint.sh"],
        "state_paths": [r"C:\Users\ESTATE_USER\.openclaw\openclaw.json"],
        "receipt_paths": [],
        "proof": "openclaw_config",
    },
    {
        "id": "switchboard",
        "label": "switchboard",
        "module": "mag.switchboard",
        "callable": "route_intent",
        "source": "mag/switchboard.py",
        "wired_by": ["dashboard/rest.py", "mag/conductor.py", "mag/routing_concert.py"],
        "state_paths": ["memory/runs/switchboard_trail.jsonl"],
        "receipt_paths": [],
        "proof": "import",
    },
    {
        "id": "blackboard",
        "label": "blackboard",
        "module": "mag.swarm_tools",
        "callable": "blackboard_post",
        "source": "mag/swarm_tools.py",
        "wired_by": ["tools/swarm_tools.py", "tools/__init__.py"],
        "state_paths": ["memory/runs/swarm_worker/blackboard"],
        "receipt_paths": [],
        "proof": "import",
    },
    # These are named in doctrine or prior conversation, so keep them in the map as
    # tested assumptions.  A missing source is useful evidence: it makes the ghost visible.
    {
        "id": "atlas",
        "label": "atlas/lattice map",
        "module": "mag.atlas",
        "callable": "build",
        "source": "mag/atlas.py",
        "wired_by": ["mag/basecamp.py", "mag/elder.py"],
        "state_paths": ["memory/runs/atlas/atlas.json"],
        "receipt_paths": ["memory/runs/atlas/receipts.jsonl"],
        "proof": "import",
    },
    {
        "id": "basecamp",
        "label": "basecamp climb controller",
        "module": "mag.basecamp",
        "callable": "status",
        "source": "mag/basecamp.py",
        "wired_by": ["mag/fireball_cycle.py"],
        "state_paths": ["memory/runs/basecamp/status.json"],
        "receipt_paths": ["memory/runs/basecamp/receipts.jsonl"],
        "proof": "import",
    },
    {
        "id": "corpus_gap_research",
        "label": "corpus gap research battery (self-steal fan-out)",
        "module": "mag.corpus_gap_research",
        "callable": "main",
        "source": "mag/corpus_gap_research.py",
        "wired_by": ["mag/corpus_gap_repack.py"],
        "state_paths": ["memory/runs/corpus_gap_research/raw.jsonl",
                        "memory/runs/corpus_gap_research/receipt.json"],
        "receipt_paths": ["memory/runs/corpus_gap_research/receipt.json"],
        "proof": "import",
    },
    {
        "id": "corpus_gap_repack",
        "label": "corpus gap pack builder (single writer for the derived pack)",
        "module": "mag.corpus_gap_repack",
        "callable": "repack",
        "source": "mag/corpus_gap_repack.py",
        "wired_by": ["mag/corpus_gap_research.py"],
        "state_paths": ["memory/runs/corpus_gap_research/CORPUS_GAP_RESEARCH.md"],
        "receipt_paths": ["memory/runs/corpus_gap_research/receipt.json"],
        "proof": "import",
    },
    {
        "id": "corpus_lead_verify",
        "label": "corpus lead handle verifier (liveness census over the pack)",
        "module": "mag.corpus_lead_verify",
        "callable": "extract",
        "source": "mag/corpus_lead_verify.py",
        "wired_by": ["memory/runs/hermes_jobs/corpus_gap_research_CLOSED_20260928T235035Z.json"],
        "state_paths": ["memory/runs/corpus_gap_research/verify.json",
                        "memory/runs/corpus_gap_research/VERIFY.md"],
        "receipt_paths": ["memory/runs/corpus_gap_research/verify.json"],
        "proof": "import",
    },
    {
        "id": "corpus_salvage",
        "label": "corpus salvage (re-find correct handles for wrong leads)",
        "module": "mag.corpus_salvage",
        "callable": "main",
        "source": "mag/corpus_salvage.py",
        "wired_by": ["mag/corpus_gutenberg_truth.py"],
        "state_paths": ["memory/runs/corpus_gap_research/MANIFEST.candidates.json",
                        "memory/runs/corpus_gap_research/SALVAGE.md"],
        "receipt_paths": ["memory/runs/corpus_gap_research/MANIFEST.candidates.json"],
        "proof": "import",
    },
    {
        "id": "corpus_archive_check",
        "label": "archive.org citation verifier (with its own control item)",
        "module": "mag.corpus_archive_check",
        "callable": "main",
        "source": "mag/corpus_archive_check.py",
        "wired_by": ["docs/ref/ARCHIVE_AXIS_FINDING_20260929.md"],
        "state_paths": ["memory/runs/corpus_gap_research/archive_check.json",
                        "memory/runs/corpus_gap_research/ARCHIVE_CHECK.md"],
        "receipt_paths": ["memory/runs/corpus_gap_research/archive_check.json"],
        "proof": "import",
    },
    {
        "id": "corpus_nonanswer",
        "label": "non-answer detector (rows that name nothing)",
        "module": "mag.corpus_nonanswer",
        "callable": "main",
        "source": "mag/corpus_nonanswer.py",
        "wired_by": ["memory/runs/corpus_gap_research/NONANSWER.md"],
        "state_paths": ["memory/runs/corpus_gap_research/nonanswer.json",
                        "memory/runs/corpus_gap_research/NONANSWER.md"],
        "receipt_paths": ["memory/runs/corpus_gap_research/nonanswer.json"],
        "proof": "import",
    },
    {
        "id": "corpus_arxiv_register",
        "label": "arXiv register audit (real vs dead for the librarian's unregistered list)",
        "module": "mag.corpus_arxiv_register",
        "callable": "main",
        "source": "mag/corpus_arxiv_register.py",
        "wired_by": ["mag/corpus_map_backfill.py"],
        "state_paths": ["memory/runs/corpus_gap_research/ARXIV_REGISTER.json",
                        "memory/runs/corpus_gap_research/ARXIV_REGISTER.md"],
        "receipt_paths": ["memory/runs/corpus_gap_research/ARXIV_REGISTER.json"],
        "proof": "import",
    },
    {
        "id": "corpus_map_backfill",
        "label": "bibliography map backfill (verified-real rows, map left untouched)",
        "module": "mag.corpus_map_backfill",
        "callable": "main",
        "source": "mag/corpus_map_backfill.py",
        "wired_by": ["docs/ref/LIBRARIAN_CONSULTATION_20260929.md"],
        "state_paths": ["memory/runs/corpus_gap_research/MAP_BACKFILL.json",
                        "memory/runs/corpus_gap_research/MAP_BACKFILL.md"],
        "receipt_paths": ["memory/runs/corpus_gap_research/MAP_BACKFILL.json"],
        "proof": "import",
    },
    {
        "id": "elder",
        "label": "elder audit seat",
        "module": "mag.elder",
        "callable": "audit",
        "source": "mag/elder.py",
        "wired_by": ["mag/fireball_cycle.py"],
        "state_paths": ["memory/runs/elder/audit.json"],
        "receipt_paths": ["memory/runs/elder/receipts.jsonl"],
        "proof": "import",
    },
    {
        "id": "fireball_cycle",
        "label": "fireball cycle workshop job",
        "module": "mag.fireball_cycle",
        "callable": "run",
        "source": "mag/fireball_cycle.py",
        "wired_by": ["mag/dogfood_audit.py"],
        "state_paths": ["memory/runs/fireball_cycle/latest.json"],
        "receipt_paths": ["memory/runs/fireball_cycle/receipts.jsonl"],
        "proof": "import",
    },
    {
        "id": "effect_broker",
        "label": "effect broker",
        "module": "mag.effect_broker",
        "callable": "execute",
        "source": "mag/effect_broker.py",
        "wired_by": ["mag/swarm_cycle.py", "mag/harness.py"],
        "state_paths": ["memory/runs/effect_broker"],
        "receipt_paths": ["memory/runs/effect_broker"],
        "proof": "import",
    },
    {
        "id": "switchboard_v2",
        "label": "switchboard v2 reference monitor",
        "module": "mag.switchboard_v2",
        "callable": "reconcile",
        "source": "mag/switchboard_v2.py",
        "wired_by": ["mag/harness.py", "mag/swarm_cycle.py"],
        "state_paths": ["memory/runs/switchboard/trail.jsonl"],
        "receipt_paths": ["memory/runs/switchboard/trail.jsonl"],
        "proof": "import",
    },
    {
        "id": "policy_engine",
        "label": "policy engine",
        "module": "mag.policy_engine",
        "callable": "validate_authority",
        "source": "mag/policy_engine.py",
        "wired_by": ["mag/switchboard_v2.py", "mag/effect_broker.py"],
        "state_paths": ["memory/policy.json", "memory/policy_revocations.jsonl"],
        "receipt_paths": ["memory/runs/switchboard/trail.jsonl"],
        "proof": "import",
    },
    {
        "id": "harness",
        "label": "authority harness",
        "module": "mag.harness",
        "callable": "run_once",
        "source": "mag/harness.py",
        "wired_by": ["mag/swarm_cycle.py"],
        "state_paths": ["memory/runs/harness"],
        "receipt_paths": ["memory/runs/harness/health_receipts.jsonl"],
        "proof": "import",
    },
    {
        "id": "board_tailer",
        "label": "image-board intake tailer",
        "module": "mag.board_tailer",
        "callable": "poll",
        "source": "mag/board_tailer.py",
        "wired_by": ["mag/board_tailer.py"],
        "state_paths": ["memory/runs/board_tailer/cursor.json"],
        "receipt_paths": ["memory/runs/board_tailer/last_receipt.json"],
        "proof": "import",
    },
    {
        "id": "main_channel",
        "label": "file-shaped main channel and bounded gopher coordinator",
        "module": "mag.main_channel",
        "callable": "run",
        "source": "mag/main_channel.py",
        "wired_by": ["watch/main_window.md", "mag/orchestrator.py", "mag/elder.py"],
        "state_paths": ["memory/runs/main_channel/cursor.json", "memory/runs/main_channel/WARM_PACK.json"],
        "receipt_paths": ["memory/runs/main_channel/last_receipt.json", "memory/runs/main_channel/jobs.jsonl"],
        "proof": "import",
    },
    {
        "id": "session_bridge",
        "label": "session bridge",
        "module": "mag.session_bridge",
        "callable": "relay",
        "source": "mag/session_bridge.py",
        "wired_by": ["mag/afk_cadence.py", "mag/dogfood_audit.py"],
        "state_paths": ["bridge/relay_state.json"],
        "receipt_paths": ["memory/runs/session_bridge/receipts.jsonl"],
        "proof": "import",
    },
    {
        "id": "ask_router",
        "label": "ask router",
        "module": "mag.ask_router",
        "callable": "cmd_route",
        "source": "mag/ask_router.py",
        "wired_by": ["mag/afk_cadence.py", "mag/dogfood_audit.py"],
        "state_paths": ["memory/runs/ask_router"],
        "receipt_paths": ["memory/runs/ask_router/receipts.jsonl"],
        "proof": "import",
    },
    {
        "id": "swarm_cycle",
        "label": "swarm cycle",
        "module": "mag.swarm_cycle",
        "callable": "cycle",
        "source": "mag/swarm_cycle.py",
        "wired_by": ["mag/dogfood_audit.py"],
        "state_paths": ["memory/runs/swarm_cycle"],
        "receipt_paths": ["memory/runs/swarm_cycle"],
        "proof": "import",
    },
    {
        "id": "research_worker",
        "label": "bounded research worker",
        "module": "mag.research_worker",
        "callable": "run",
        "source": "mag/research_worker.py",
        "wired_by": ["mag/orchestrator.py"],
        "state_paths": ["memory/runs/research_worker"],
        "receipt_paths": ["memory/runs/research_worker"],
        "proof": "import",
    },
    {
        "id": "read_archive",
        "label": "lossless archive dereferencer",
        "module": "mag.read_archive",
        "callable": "deref",
        "source": "mag/read_archive.py",
        "wired_by": ["mag/dogfood_audit.py"],
        "state_paths": ["watch/openclaw_traj.jsonl.bounds.meta.json"],
        "receipt_paths": ["memory/runs/read_archive/receipts.jsonl"],
        "proof": "import",
    },
    {
        "id": "self_audit",
        "label": "self audit",
        "module": "mag.self_audit",
        "callable": "run_tier",
        "source": "mag/self_audit.py",
        "wired_by": ["mag/runtime.py"],
        "state_paths": ["memory/runs/self_audit/report.jsonl"],
        "receipt_paths": ["memory/runs/self_audit/report.jsonl"],
        "proof": "import",
    },
    {
        "id": "fleet_structure",
        "label": "fleet structure (seats + lanes doctrine)",
        "module": "",
        "callable": "",
        "source": "watch/FLEET_STRUCTURE_20260901.md",
        "wired_by": [],
        "state_paths": [
            "watch/LANE_SLOT_MAP_20260901.md",
            "watch/AUDIT_A_ATTEMPTS_20260901.md",
            "watch/AUDIT_B_ELDER_20260901.md",
            "watch/AUDIT_C_VERKLE_20260901.md",
            "watch/AUDIT_D_MAP_20260901.md",
        ],
        "receipt_paths": ["watch/inbox/FLEET_AUDIT_20260901.md"],
        "proof": "",
    },
    {
        "id": "host_resolver",
        "label": "DNS-Independent Host Resolver",
        "module": "mag.host_resolver",
        "callable": "resolve_host_for_service",
        "source": "mag/host_resolver.py",
        "wired_by": ["docker-compose.yml", "mag/api_server.py", "mag/browser_env.py", "mag/swarm_worker.py"],
        "state_paths": ["memory/runs/host_resolver/mappings.jsonl", "memory/runs/host_resolver/network_state.json"],
        "receipt_paths": ["memory/runs/host_resolver/receipts.jsonl"],
        "proof": "import",
    },
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def _exists(values: list[str]) -> list[str]:
    return [v for v in values if _path(v).exists()]


def _importable(module: str, name: str) -> tuple[bool, str]:
    if not module or not name:
        return False, "no Python callable (config organ)"
    try:
        obj = getattr(importlib.import_module(module), name)
        return callable(obj), "" if callable(obj) else "attribute is not callable"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {str(exc)[:120]}"


def _last_receipt(paths: list[str]) -> dict[str, Any]:
    candidates: list[tuple[float, Path, dict[str, Any]]] = []
    for raw in paths:
        p = _path(raw)
        files = [p] if p.is_file() else sorted(p.glob("*.json")) if p.is_dir() else []
        if p.is_file() and p.suffix == ".jsonl":
            row: dict[str, Any] | None = None
            try:
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.strip():
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
            except OSError:
                row = None
            if row is not None:
                candidates.append((p.stat().st_mtime, p, row))
            continue
        for f in files:
            try:
                row = json.loads(f.read_text(encoding="utf-8", errors="replace"))
                if isinstance(row, dict):
                    candidates.append((f.stat().st_mtime, f, row))
            except (OSError, json.JSONDecodeError):
                continue
    if not candidates:
        return {"exists": False, "recent": False, "ok": False}
    _mtime, path, row = max(candidates, key=lambda x: x[0])
    stamp = str(row.get("ts") or row.get("finished_at") or "")
    age_s: int | None = None
    try:
        if stamp:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            age_s = max(0, int((datetime.now(timezone.utc) - when).total_seconds()))
    except (TypeError, ValueError):
        age_s = None
    recent = age_s is not None and age_s <= LIVE_MAX_SECONDS
    if "ok" in row:
        receipt_ok = row.get("ok") is True
    elif row.get("status") == "RECEIPT_COMMITTED":
        # effect_broker receipts carry the actual result below the top-level
        # status.  The commit itself proves persistence; result.ok proves the
        # requested effect succeeded.
        result = row.get("result")
        if not isinstance(result, dict) and isinstance(row.get("receipt"), dict):
            # switchboard_v2 wraps the effect-broker result under ``receipt``.
            result = row["receipt"].get("result", row["receipt"])
        receipt_ok = isinstance(result, dict) and result.get("ok") is True
    elif "failed" in row:
        try:
            receipt_ok = int(row.get("failed") or 0) == 0
        except (TypeError, ValueError):
            receipt_ok = False
    elif row.get("band") in {"green", "amber", "red", "black"}:
        receipt_ok = True
    else:
        # A file that merely exists is durable state, not evidence of a successful run.
        receipt_ok = False
    return {"exists": True, "recent": recent, "ok": receipt_ok,
            "age_s": age_s, "path": str(path.relative_to(ROOT)).replace("\\", "/")
            if path.is_relative_to(ROOT) else str(path),
            "schema": row.get("schema"), "receipt_id": row.get("receipt_id")}


def _proof(kind: str, *, callable_ok: bool = False) -> tuple[bool, str]:
    if kind == "manifest":
        try:
            from mag.manifest import verify
            result = verify()
            return bool(result.get("verified")), str(result.get("state") or "unverified")
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:160]
    if kind == "water_glass":
        try:
            from mag.water_computer import _play_demo
            result = _play_demo()
            return bool(result.get("won") and not result.get("cheated")), "won/non-cheated"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:160]
    if kind == "context_admission":
        try:
            from mag.context_admission import assess
            green = assess(estimated_tokens=1_000, context_window=100_000)
            black = assess(estimated_tokens=101_000, context_window=100_000)
            ok = green.get("allowed") is True and black.get("allowed") is False
            return ok, "green admits / black denies"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:160]
    if kind == "dirac":
        try:
            from mag.dirac_loop import scan
            result = scan(scope="operational")
            return bool(result.get("ok")), f"operational betti1={result.get('betti1')}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:160]
    if kind == "verkle":
        try:
            from mag.verkle_knot import prove_latest
            result = prove_latest()
            return bool(result.get("verified")), str(result.get("note") or "proof")[:160]
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:160]
    if kind == "openclaw_config":
        try:
            host = _path(r"C:\Users\ESTATE_USER\.openclaw\openclaw.json")
            json.loads(host.read_text(encoding="utf-8"))
            json.loads((_path("deploy/openclaw/openclaw.container.json")).read_text(encoding="utf-8"))
            return True, "host and container JSON parse"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:160]
    if kind == "atomic_control_file":
        try:
            from mag.operator_mode import read
            result = read()
            ok = result.get("schema") == "operator_mode.v1" and result.get("mode") in {"running", "paused"}
            return ok, "schema + effective mode" if ok else "invalid operator mode"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:160]
    return callable_ok, "callable imported" if callable_ok else "callable not importable"


def map_organs() -> dict[str, Any]:
    """Return the evidence map without writing it or calling a provider."""
    rows: list[dict[str, Any]] = []
    for raw in REGISTRY:
        row = dict(raw)
        source_exists = _path(str(raw["source"])).is_file()
        callable_ok, import_error = _importable(str(raw.get("module") or ""), str(raw.get("callable") or ""))
        wired_paths = _exists(list(raw.get("wired_by") or []))
        wired = bool(wired_paths)
        state_paths_present = _exists(list(raw.get("state_paths") or []))
        stateful = bool(state_paths_present)
        proof_ok, proof_note = _proof(
            str(raw.get("proof") or "import"), callable_ok=callable_ok)
        receipt = _last_receipt(list(raw.get("receipt_paths") or []))
        live = bool(receipt.get("exists") and receipt.get("recent") and receipt.get("ok"))
        levels = ["DECLARED"] if source_exists else []
        if callable_ok:
            levels.append("INSTRUMENTED")
        if wired:
            levels.append("WIRED")
        if stateful:
            levels.append("STATEFUL")
        if proof_ok:
            levels.append("VERIFIED")
        if live:
            levels.append("LIVE")
        if not levels:
            levels = ["GHOST"]
        # A verified import is not the same thing as a connected organ. Keep
        # these gaps separate from the level ladder so a callable-but-orphaned
        # module cannot make the elder report a false clean bill of health.
        gap_codes: list[str] = []
        if not source_exists:
            gap_codes.append("source_missing")
        if raw.get("module") and not callable_ok:
            gap_codes.append("callable_missing")
        if not wired:
            gap_codes.append("caller_missing" if raw.get("wired_by") else "caller_undeclared")
        if raw.get("state_paths") and not stateful:
            gap_codes.append("state_missing")
        if raw.get("receipt_paths"):
            if not receipt.get("exists"):
                gap_codes.append("receipt_missing")
            elif not receipt.get("ok"):
                gap_codes.append("receipt_not_successful")
            elif not receipt.get("recent"):
                gap_codes.append("receipt_stale")
        if not proof_ok:
            gap_codes.append("proof_failed")
        row.update({
            "source_exists": source_exists,
            "callable_imports": callable_ok,
            "callable_error": import_error,
            "wired_evidence": wired,
            "wired_paths": wired_paths,
            "stateful_evidence": stateful,
            "state_paths_present": state_paths_present,
            "proof_ok": proof_ok,
            "proof_note": proof_note,
            "receipt": receipt,
            "levels": levels,
            "status": levels[-1],
            "gap_codes": gap_codes,
        })
        rows.append(row)
    summary = {level: sum(1 for r in rows if level in r["levels"])
               for level in ("DECLARED", "INSTRUMENTED", "WIRED", "STATEFUL", "VERIFIED", "LIVE", "GHOST")}
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "organs": rows,
            "summary": summary,
            "law": "a claim advances only when its corresponding evidence exists; unknown stays unknown"}


def operational_graph() -> dict[str, Any]:
    """Return the declared operational lifecycle graph used by Dirac.

    Edges are intentionally not marked verified merely because both endpoint modules exist.
    Transition receipts are a separate climb.  This graph makes missing ribs visible without
    turning a declaration into a liveness claim.
    """
    ids = [r["id"] for r in REGISTRY]
    nodes = [{"id": f"organ:{r['id']}", "kind": "organ", "label": r["label"],
              "source": r["source"]} for r in REGISTRY]
    transitions = [
        ("context_pack", "context_admission", "preflight"),
        ("context_admission", "context_pack", "repack"),
        ("context_pack", "swarm_surface", "pressure_offload"),
        ("swarm_surface", "swarm_worker", "enqueue"),
        ("swarm_worker", "context_checkpoint", "checkpoint"),
        ("context_checkpoint", "context_pack", "restore"),
        ("context_pack", "verkle_knot", "pack_receipt"),
        ("verkle_knot", "manifest", "commit"),
        ("manifest", "dirac_loop", "map"),
        ("dirac_loop", "context_admission", "observe"),
        ("context_admission", "openclaw", "runtime_policy"),
        ("openclaw", "context_admission", "runtime_receipt"),
        ("openclaw", "switchboard", "authority_boundary"),
        ("switchboard", "blackboard", "classify_shared_state"),
        ("blackboard", "switchboard", "proposal_review"),
        ("switchboard", "effect_broker", "authorize_effect"),
        ("effect_broker", "swarm_worker", "execute_effect"),
        ("swarm_worker", "self_audit", "health_probe"),
        ("self_audit", "dirac_loop", "audit_map"),
        ("context_pack", "water_computer", "negative_test"),
        ("water_computer", "manifest", "proof"),
    ]
    edges = [{"from": f"organ:{a}", "to": f"organ:{b}", "rel": rel,
              "verified": False, "evidence_required": f"receipt:{a}->{b}"}
             for a, b, rel in transitions if a in ids and b in ids]
    return {"ok": True, "schema": "organ_graph.v1", "scope": "operational",
            "nodes": nodes, "edges": edges,
            "note": "declared lifecycle topology; edge liveness is unknown until a transition receipt exists"}


def snapshot() -> dict[str, Any]:
    out = map_organs()
    out["graph"] = operational_graph()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    out["path"] = str(OUT.relative_to(ROOT)).replace("\\", "/")
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="organ_map", description="receipts-first organ inventory")
    ap.add_argument("cmd", nargs="?", default="status", choices=("status", "snapshot"))
    args = ap.parse_args(argv)
    out = snapshot() if args.cmd == "snapshot" else map_organs()
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
