"""Multi-seat refine chain — Project Verkle recursive pattern on Mag.

Schema: mag_refine_chain.v1

Loop (default):
  deepseek refine → local critique → deepseek synthesize

Each round is a cold seat with envelope (purpose, tier, prior artifact).
Voice never blocks all rounds; speaks status; advances when prior ready.

Law: chat is heat; chain artifacts FILE; preference leaves are hypotheses.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_refine_chain.v1"
CHAIN_DIR = ROOT / "memory" / "working" / "refine_chains"
INDEX_PATH = CHAIN_DIR / "index.jsonl"
PREF_DIR = ROOT / "memory" / "improve" / "evals" / "models"

_START = re.compile(
    r"\b("
    r"start (a )?refine(ment)? chain|refine chain|"
    r"pass (this |that |it )?(to )?deepseek then local|"
    r"deepseek then local then (synthesize|synth)|"
    r"multi[- ]?seat refine|recursive refine|"
    r"project verkle (refine|experiment)"
    r")\b",
    re.I,
)
_STATUS = re.compile(
    r"\b(chain status|refine status|what round|next round status)\b",
    re.I,
)
_ADVANCE = re.compile(
    r"\b(next round|advance (the )?chain|continue (the )?chain|run next seat)\b",
    re.I,
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cid() -> str:
    return "rf-" + uuid.uuid4().hex[:10]


def _h(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:16]


def _default_plan() -> list[dict[str, str]]:
    return [
        {
            "seat": "deepseek",
            "role": "refine",
            "purpose": "Transform rough intent into a structured design + experiment brief",
            "expected_output": "Titled refinement; steps for local + ChatGPT; clear non-goals",
        },
        {
            "seat": "local",
            "role": "critique",
            "purpose": "Local-first critique: privacy, scope, provenance, revocation, hardware",
            "expected_output": "Critiques + constraints; do not restart design from scratch",
        },
        {
            "seat": "deepseek",
            "role": "synthesize",
            "purpose": "Reconcile refine + critique without erasing either character",
            "expected_output": "Synthesis; label yours vs local; next prompts; falsification notes",
        },
    ]


def structure_checkin_plan() -> list[dict[str, str]]:
    """Full structure orchestra: janitor → DS → OpenAI fable → Kimi → local seal.

    Used by mag.checkin_route after freeze + network probe. Prefer importing
    from mag.checkin_route when starting a full check-in ritual.
    """
    try:
        from mag.checkin_route import structure_checkin_plan as _plan

        return _plan()
    except Exception:
        return _default_plan()


def _seat_to_provider(seat: str, role: str = "") -> tuple[str, str | None]:
    """Map refine seat name → (provider_id, optional model override)."""
    import os

    s = (seat or "local").strip().lower()
    if s in ("local", "ollama", "janitor"):
        return "ollama", "gemma:2b"
    if s in ("deepseek",):
        return "deepseek", None
    if s in ("openai", "fable", "chatgpt"):
        model = os.environ.get("OPENAI_CHECKIN_MODEL") or os.environ.get("OPENAI_MODEL") or None
        return "openai", model
    if s in ("kimi", "kimi3", "kimi-k3", "moonshot"):
        # Prefer OpenRouter slug; override with KIMI_OPENROUTER_MODEL
        model = (
            os.environ.get("KIMI_OPENROUTER_MODEL")
            or os.environ.get("KIMI_MODEL")
            or "moonshotai/kimi-k2-0905-preview"
        )
        return "openrouter", model
    if s in ("openrouter",):
        return "openrouter", None
    if s in ("anthropic", "claude"):
        return "anthropic", None
    if s in ("xai", "grok_api"):
        return "xai", None
    # Unknown remote-ish seat → deepseek default for structure work
    if s not in ("",):
        return "deepseek", None
    return "ollama", "gemma:2b"


def _soft_skip_error(err: str) -> bool:
    """True if this round should soft-skip (carry prior) instead of fail the chain."""
    e = (err or "").lower()
    needles = (
        "missing api key",
        "missing key",
        "quota exhausted",
        "unknown provider",
        "refused: tier",
        "connection refused",
        "timed out",
        "timeout",
        "401",
        "403",
        "429",
        "not found",
        "model",
    )
    # Be careful: "model" alone is too broad — only with failure shapes
    if "model" in e and any(x in e for x in ("not found", "does not exist", "invalid", "unknown")):
        return True
    return any(n in e for n in needles if n != "model")


def _envelope(
    *,
    purpose: str,
    expected_output: str,
    prior_hash: str = "",
    data_tier: str = "T2",
) -> dict[str, Any]:
    return {
        "purpose": purpose,
        "data_tier": data_tier,
        "scope_hash": prior_hash or "genesis",
        "prohibitions": [
            "Do not claim personal secrets",
            "Do not invent implemented Mag features",
            "Historical figures = fiction if used",
            "Do not treat chat as DNA",
        ],
        "assumptions": ["Operator owns residual/tip on home disk"],
        "expected_output": expected_output,
        "prior_artifact_hash": prior_hash,
    }


def _pack_slice(n: int = 1000) -> str:
    try:
        from mag.context_pack import build_context_pack, format_context_pack_text

        return format_context_pack_text(build_context_pack(max_brief=500, max_live=250))[:n]
    except Exception:
        return ""


def _save(chain: dict[str, Any]) -> Path:
    CHAIN_DIR.mkdir(parents=True, exist_ok=True)
    path = CHAIN_DIR / f"{chain['chain_id']}.json"
    path.write_text(json.dumps(chain, indent=2, default=str), encoding="utf-8")
    with INDEX_PATH.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": _utc(),
                    "chain_id": chain["chain_id"],
                    "status": chain.get("status"),
                    "round_i": chain.get("round_i"),
                    "goal": str(chain.get("goal") or "")[:120],
                },
                default=str,
            )
            + "\n"
        )
    return path


def load_chain(chain_id: str) -> dict[str, Any] | None:
    path = CHAIN_DIR / f"{chain_id}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def latest_chain(session_id: str = "") -> dict[str, Any] | None:
    if not CHAIN_DIR.is_dir():
        return None
    files = sorted(CHAIN_DIR.glob("rf-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files:
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if session_id and str(c.get("session_id") or "") != session_id:
            continue
        return c
    return None


def start_chain(
    goal: str,
    *,
    session_id: str = "",
    plan: list[dict[str, str]] | None = None,
    auto_run: bool = True,
) -> dict[str, Any]:
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}
    cid = _cid()
    rounds_plan = plan or _default_plan()
    rounds: list[dict[str, Any]] = []
    for i, step in enumerate(rounds_plan):
        rounds.append(
            {
                "i": i,
                "seat": step.get("seat") or "local",
                "role": step.get("role") or "refine",
                "status": "pending",
                "envelope": _envelope(
                    purpose=str(step.get("purpose") or step.get("role") or "refine"),
                    expected_output=str(step.get("expected_output") or "structured artifact"),
                ),
                "artifact_path": "",
                "artifact_hash": "",
                "result_excerpt": "",
                "error": "",
            }
        )
    chain = {
        "schema": SCHEMA,
        "chain_id": cid,
        "ts": _utc(),
        "session_id": session_id or "",
        "goal": goal[:3000],
        "status": "running",
        "round_i": 0,
        "rounds": rounds,
        "pack_excerpt": _pack_slice(),
    }
    # freeze link
    try:
        from mag.diary_node import freeze_context

        fr = freeze_context(session_id=session_id, channel="voice", reason="refine_start")
        chain["frozen"] = {
            "day": fr.get("day"),
            "agent_commit": (fr.get("agent") or {}).get("content_commit"),
            "verkle_n": (fr.get("session_verkle") or {}).get("n_leaves"),
            "freeze_hash": fr.get("freeze_hash"),
        }
    except Exception:
        chain["frozen"] = {}

    _save(chain)
    if auto_run:
        threading.Thread(
            target=_run_round_worker,
            args=(cid, 0),
            daemon=True,
            name=f"refine-{cid}-0",
        ).start()

    try:
        from mag.training_events import emit

        emit(
            "refine_round",
            join={"chain_id": cid, "session_id": session_id or ""},
            input_data={"goal": goal[:400]},
            action={"kind": "start", "n_rounds": len(rounds)},
            outcome={"ok": True},
            pattern_tags=["refine", "multi_seat", "verkle_experiment"],
            tier_max="T2",
        )
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "chain_id": cid,
        "chain": chain,
        "speak_text": (
            f"Started refine chain {cid}: DeepSeek refine, then local critique, "
            f"then DeepSeek synthesize. Round 0 running in background — keep talking. "
            f"Say chain status or next round when ready."
        ),
        "answer": None,
        "route": "refine_start",
    }


def _artifact_path(cid: str, i: int, role: str) -> Path:
    d = CHAIN_DIR / cid
    d.mkdir(parents=True, exist_ok=True)
    return d / f"r{i}_{role}.md"


def _run_round_worker(chain_id: str, round_i: int) -> None:
    chain = load_chain(chain_id)
    if not chain:
        return
    rounds = list(chain.get("rounds") or [])
    if round_i < 0 or round_i >= len(rounds):
        return
    rnd = rounds[round_i]
    # need prior ready
    if round_i > 0:
        prev = rounds[round_i - 1]
        if prev.get("status") != "ready":
            rnd["status"] = "blocked"
            rnd["error"] = "prior round not ready"
            rounds[round_i] = rnd
            chain["rounds"] = rounds
            _save(chain)
            return

    rnd["status"] = "running"
    rnd["started"] = _utc()
    rounds[round_i] = rnd
    chain["rounds"] = rounds
    chain["round_i"] = round_i
    _save(chain)

    prior_text = ""
    prior_hash = ""
    if round_i > 0:
        prev = rounds[round_i - 1]
        prior_hash = str(prev.get("artifact_hash") or "")
        ap = prev.get("artifact_path") or ""
        if ap:
            p = ROOT / ap if not Path(ap).is_file() else Path(ap)
            if not p.is_file():
                p = CHAIN_DIR / chain_id / Path(ap).name
            if p.is_file():
                prior_text = p.read_text(encoding="utf-8", errors="replace")[:8000]
        rnd["envelope"] = _envelope(
            purpose=str((rnd.get("envelope") or {}).get("purpose") or rnd.get("role")),
            expected_output=str((rnd.get("envelope") or {}).get("expected_output") or ""),
            prior_hash=prior_hash,
        )

    seat = str(rnd.get("seat") or "local")
    role = str(rnd.get("role") or "refine")
    env = rnd.get("envelope") or {}
    user = (
        f"## Refine chain round {round_i} — role={role} seat={seat}\n"
        f"## Goal\n{chain.get('goal')}\n\n"
        f"## Envelope\n{json.dumps(env, indent=2)}\n\n"
        f"## Pack excerpt\n{chain.get('pack_excerpt') or ''}\n\n"
    )
    if prior_text:
        user += f"## Prior artifact (do not restart from scratch)\n{prior_text}\n\n"
    else:
        user += "## Prior artifact\n(none — you are first refine)\n\n"
    # MoA-style critical aggregation: give the synthesizer EVERY high-level seat's contribution,
    # numbered + attributed, and tell it to EVALUATE critically, not merge blindly.
    contribs = chain.get("role_outputs") or {}
    if role == "synthesize" and contribs:
        user += "## Contributions from all seats (each is a frontier model's output)\n"
        for i, (key, c) in enumerate(contribs.items(), 1):
            model = str(c.get("model") or c.get("seat") or key)
            user += f"{i}. [{key}] model={model}:\n{c.get('text', '')[:1500]}\n\n"
        user += (
            "Synthesize these contributions by CRITICALLY evaluating each — some may be biased or "
            "wrong. Do not merely concatenate or average; choose the strongest, reconcile "
            "conflicts, and label which contribution each part came from.\n"
        )
    user += (
        "Produce the expected_output as markdown. "
        "Label Mag capabilities vs proposed vs simulation. Be concrete."
    )

    system = (
        "You are a Mag refine-chain seat. Cold worker. "
        "No handoff theater. Honor envelope prohibitions. "
        "If role is critique or seal_critique: strengthen local-first boundaries. "
        "If synthesize: keep both characters; improve shared design. "
        "If janitor: organize only — short outline, no invention. "
        "If fable: clarity and scannable narrative of the work, not fiction-as-fact. "
        "If contract: pack-first, artifact > transcript, seat purity."
    )
    provider, model_override = _seat_to_provider(seat, role)

    try:
        from models.providers import chat_provider

        kwargs: dict[str, Any] = {
            "tier": "T1" if provider == "ollama" else "T2",
            "max_tokens": 900 if provider == "ollama" else 1400,
            "temperature": 0.35,
        }
        if model_override:
            kwargs["model"] = model_override
        elif provider == "ollama":
            kwargs["model"] = "gemma:2b" if role in ("janitor", "seal_critique", "critique") else "gemma:2b"
        res = chat_provider(provider, system, user, **kwargs)
        if not res.get("ok"):
            err = str(res.get("error") or "provider failed")
            # Soft-skip missing keys / quota so the orchestra can continue
            if _soft_skip_error(err):
                skip_text = (
                    f"_Seat {seat}/{role} soft-skipped: {err}_\n\n"
                    f"Prior artifact carried forward unchanged. Next seat should not invent "
                    f"what this seat would have added."
                )
                path = _artifact_path(chain_id, round_i, role)
                header = (
                    f"# Refine {chain_id} round {round_i} ({role} / {seat}) SKIPPED\n\n"
                    f"_ts: {_utc()}_\n\n"
                )
                path.write_text(header + skip_text, encoding="utf-8")
                rel = str(path.relative_to(ROOT)).replace("\\", "/")
                rnd["status"] = "ready"
                rnd["skipped"] = True
                rnd["artifact_path"] = rel
                rnd["artifact_hash"] = _h(skip_text)
                rnd["result_excerpt"] = skip_text[:500]
                rnd["error"] = err[:200]
                rnd["finished"] = _utc()
            else:
                raise RuntimeError(err)
        else:
            text = str(res.get("text") or res.get("content") or "").strip()
            path = _artifact_path(chain_id, round_i, role)
            header = (
                f"# Refine {chain_id} round {round_i} ({role} / {seat})\n\n"
                f"_ts: {_utc()}_\n\n"
            )
            path.write_text(header + text, encoding="utf-8")
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            ah = _h(text)
            rnd["status"] = "ready"
            rnd["artifact_path"] = rel
            rnd["artifact_hash"] = ah
            rnd["result_excerpt"] = text[:500]
            rnd["model"] = res.get("model")
            rnd["finished"] = _utc()
            rnd["error"] = ""
            # C3-style provenance: attribute this seat's contribution on the chain record so every
            # high-level model's output is attributable + can be credited/influenced later.
            chain.setdefault("role_outputs", {})
            try:
                from mag.model_classify import classify as _mc
                _cls = _mc(text, str(res.get("model") or seat))
                _cap = _cls.get("tier")
                _kind = _cls.get("kind")
            except Exception:
                _cap = _kind = None
            chain["role_outputs"][f"{role}:{seat}"] = {
                "role": role, "seat": seat, "model": res.get("model"),
                "model_capability": _cap, "content_kind": _kind,
                "artifact_hash": ah, "artifact_path": rel, "ts": _utc(),
                "text": text[:4000],
            }
            # swarm-surface law: route each high-level seat's output through the ONE primitive so
            # it enters the research loop + gets recorded (no dead-end artifacts).
            try:
                from mag import swarm_surface
                swarm_surface.route_novel(
                    f"Refine chain {chain_id} round {round_i} ({role}/{seat}):\n{text[:6000]}",
                    surface=f"refine:{role}",
                    lens=f"refine:{seat}",
                )
            except Exception:
                pass
    except Exception as exc:
        rnd["status"] = "failed"
        rnd["error"] = str(exc)[:300]
        rnd["finished"] = _utc()

    rounds[round_i] = rnd
    chain["rounds"] = rounds
    # auto-advance if success (including soft-skip ready) and more rounds
    if rnd.get("status") == "ready" and round_i + 1 < len(rounds):
        chain["status"] = "running"
        _save(chain)
        threading.Thread(
            target=_run_round_worker,
            args=(chain_id, round_i + 1),
            daemon=True,
            name=f"refine-{chain_id}-{round_i+1}",
        ).start()
    elif rnd.get("status") == "ready":
        chain["status"] = "complete"
        chain["finished"] = _utc()
        _save(chain)
        try:
            extract_preference_hypotheses(chain)
        except Exception:
            pass
    else:
        chain["status"] = "failed" if rnd.get("status") == "failed" else chain.get("status")
        _save(chain)

    try:
        from mag.training_events import emit

        emit(
            "refine_round",
            join={"chain_id": chain_id, "round": str(round_i)},
            input_data={"role": role, "seat": seat},
            action={"provider": provider},
            outcome={
                "status": rnd.get("status"),
                "artifact_hash": rnd.get("artifact_hash"),
                "error": rnd.get("error"),
            },
            pattern_tags=["refine", role, seat],
            tier_max="T2",
        )
    except Exception:
        pass


def advance_chain(chain_id: str) -> dict[str, Any]:
    chain = load_chain(chain_id)
    if not chain:
        return {"ok": False, "error": "missing chain"}
    rounds = list(chain.get("rounds") or [])
    # find first pending/blocked
    for i, rnd in enumerate(rounds):
        if rnd.get("status") in ("pending", "blocked", "failed"):
            if i > 0 and rounds[i - 1].get("status") != "ready":
                return {
                    "ok": False,
                    "error": f"round {i-1} not ready",
                    "chain_id": chain_id,
                }
            threading.Thread(
                target=_run_round_worker,
                args=(chain_id, i),
                daemon=True,
                name=f"refine-{chain_id}-{i}",
            ).start()
            return {
                "ok": True,
                "chain_id": chain_id,
                "started_round": i,
                "speak_text": f"Advancing chain {chain_id} round {i} ({rnd.get('role')}/{rnd.get('seat')}).",
                "route": "refine_advance",
            }
    return {
        "ok": True,
        "chain_id": chain_id,
        "status": chain.get("status"),
        "speak_text": f"Chain {chain_id} has no pending rounds — status {chain.get('status')}.",
        "route": "refine_advance",
    }


def chain_status_speak(chain: dict[str, Any]) -> str:
    cid = chain.get("chain_id")
    st = chain.get("status")
    bits = [f"Chain {cid} is {st}."]
    for rnd in chain.get("rounds") or []:
        bits.append(
            f"R{rnd.get('i')}:{rnd.get('role')}/{rnd.get('seat')}={rnd.get('status')}"
        )
    return " ".join(bits)


def extract_preference_hypotheses(chain: dict[str, Any]) -> dict[str, Any]:
    """Write model_preference hypotheses from completed rounds — not feelings."""
    PREF_DIR.mkdir(parents=True, exist_ok=True)
    cid = chain.get("chain_id") or "rf"
    leaves = []
    for rnd in chain.get("rounds") or []:
        if rnd.get("status") != "ready":
            continue
        seat = str(rnd.get("seat") or "unknown")
        excerpt = str(rnd.get("result_excerpt") or "")
        leaf = {
            "schema": "model_preference_leaf.v1",
            "status": "hypothesis",
            "seat": seat,
            "role": rnd.get("role"),
            "chain_id": cid,
            "round_i": rnd.get("i"),
            "artifact_hash": rnd.get("artifact_hash"),
            "artifact_path": rnd.get("artifact_path"),
            "indicators": {
                "verbosity": "high" if len(excerpt) > 400 else "mid",
                "local_first_language": bool(
                    re.search(r"local[- ]first|privacy|revoc|on[- ]device|ollama", excerpt, re.I)
                ),
                "falsification_language": bool(
                    re.search(r"falsif|hypothesis|control|replicate", excerpt, re.I)
                ),
                "implementation_detail": bool(
                    re.search(r"schema|endpoint|jsonl|adapter|test", excerpt, re.I)
                ),
            },
            "evidence_event_ids": [],
            "replicate_count": 1,
            "ts": _utc(),
            "note": "Hypothesis from one chain — not authoritative self-knowledge",
            "frozen": chain.get("frozen") or {},
        }
        fname = f"pref_{cid}_{seat}_r{rnd.get('i')}.json"
        path = PREF_DIR / fname
        path.write_text(json.dumps(leaf, indent=2, default=str), encoding="utf-8")
        leaves.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    chain["preference_leaves"] = leaves
    _save(chain)
    return {"ok": True, "leaves": leaves}


def try_refine_voice(
    text: str,
    *,
    session_id: str = "",
    brief: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Voice entry: start / status / advance refine chain."""
    t = text or ""
    if _STATUS.search(t):
        chain = latest_chain(session_id)
        if not chain:
            return {
                "ok": True,
                "answer": "No refine chain for this session yet.",
                "speak_text": "No refine chain for this session yet. Say start refine chain plus your goal.",
                "route": "refine_status",
            }
        speak = chain_status_speak(chain)
        return {
            "ok": True,
            "answer": speak,
            "speak_text": speak,
            "route": "refine_status",
            "chain_id": chain.get("chain_id"),
        }
    if _ADVANCE.search(t):
        chain = latest_chain(session_id)
        if not chain:
            return {
                "ok": True,
                "speak_text": "No chain to advance. Start a refine chain first.",
                "answer": "No chain",
                "route": "refine_advance",
            }
        out = advance_chain(str(chain["chain_id"]))
        out["answer"] = out.get("speak_text")
        return out
    if _START.search(t) or (
        re.search(r"\brefine\b", t, re.I)
        and re.search(r"\b(deepseek|local|chain|verkle|experiment)\b", t, re.I)
    ):
        # strip trigger words for goal
        goal = re.sub(
            r"\b(start (a )?refine(ment)? chain|refine chain|pass to deepseek then local|"
            r"deepseek then local then synthesize|multi[- ]?seat refine)\b[:\s]*",
            "",
            t,
            flags=re.I,
        ).strip()
        if not goal and brief:
            goal = str(brief.get("goal") or t)
        if not goal:
            goal = t
        out = start_chain(goal, session_id=session_id, auto_run=True)
        out["answer"] = out.get("speak_text")
        return out
    return None


def handle_refine(body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    action = str(body.get("action") or "list").strip().lower()
    if action in ("checkin", "structure_checkin", "mag_checkin"):
        from mag.checkin_route import start_checkin

        return start_checkin(
            str(body.get("goal") or body.get("text") or ""),
            session_id=str(body.get("session_id") or "tui-checkin"),
            auto_run=body.get("auto_run", True) is not False,
            skip_network=body.get("skip_network") is True,
        )
    if action in ("start", "create"):
        plan = None
        if body.get("plan") == "checkin" or body.get("kind") == "structure_checkin":
            plan = structure_checkin_plan()
        return start_chain(
            str(body.get("goal") or body.get("text") or ""),
            session_id=str(body.get("session_id") or ""),
            plan=plan,
            auto_run=body.get("auto_run", True) is not False,
        )
    if action in ("status", "get"):
        cid = str(body.get("chain_id") or "")
        chain = load_chain(cid) if cid else latest_chain(str(body.get("session_id") or ""))
        if not chain:
            return {"ok": False, "error": "no chain"}
        return {"ok": True, "chain": chain, "speak": chain_status_speak(chain)}
    if action in ("advance", "next"):
        cid = str(body.get("chain_id") or "")
        if not cid:
            c = latest_chain(str(body.get("session_id") or ""))
            cid = str((c or {}).get("chain_id") or "")
        return advance_chain(cid)
    if action in ("list",):
        rows = []
        if INDEX_PATH.is_file():
            for line in INDEX_PATH.read_text(encoding="utf-8").splitlines()[-30:]:
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return {"ok": True, "n": len(rows), "chains": list(reversed(rows))}
    return {"ok": False, "error": f"unknown action: {action}"}
