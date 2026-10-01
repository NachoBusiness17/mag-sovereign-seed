"""Diary nodes on Verkle tip — seal walk/talk into DNA-adjacent leaves + train labels.

Schema: mag_diary_node.v1
Tesuji: docs/ref/tesuji/diary-verkle-train-2026-08-07.md

Law:
  - Chat/voice trail = heat until seal
  - One seal → one diary_node_leaf on the same Verkle chain/tip as session knots
  - High-fidelity train = brief + turns + seat + artifacts, not bubble scrape
  - Audio opt-in only (speak-as-me later)
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import ROOT

SCHEMA = "mag_diary_node.v1"
FREEZE_SCHEMA = "mag_state_freeze.v1"
DIARY_DIR = ROOT / "memory" / "biography" / "diary_nodes"
AUTO_DIR = DIARY_DIR / "auto"
INDEX_PATH = DIARY_DIR / "index.jsonl"
AUTO_INDEX = AUTO_DIR / "index.jsonl"
# Cheap auto-freeze throttle (seconds between auto snaps per session)
_AUTO_MIN_GAP_S = float(__import__("os").environ.get("MAG_DIARY_AUTO_GAP_S") or "90")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _leaf_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return _h(b"diary-leaf:" + raw)


def _safe_id(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "", (s or "").strip())[:64] or "anon"


def _gather_session(session_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {"turns": [], "last_brief": {}, "session_id": session_id}
    try:
        from mag.voice_turn import load_session

        sess = load_session(session_id)
        out["turns"] = list(sess.get("turns") or [])
        lb = sess.get("last_brief")
        if isinstance(lb, dict):
            out["last_brief"] = lb
    except Exception:
        pass
    return out


def _gather_trail(session_id: str, *, limit: int = 40) -> list[dict[str, Any]]:
    path = ROOT / "memory" / "runs" / "voice_trail.jsonl"
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    sid = _safe_id(session_id)
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if sid and str(o.get("session_id") or "") != sid:
                continue
            rows.append(o)
    except OSError:
        return []
    return rows[-limit:]


def _gather_dig(session_id: str) -> list[dict[str, Any]]:
    try:
        from mag.voice_dig_board import _load_state

        state = _load_state()
        eps = list(state.get("episodes") or [])
        sid = _safe_id(session_id)
        if sid:
            mine = [e for e in eps if _safe_id(str(e.get("session_id") or "")) == sid]
            if mine:
                return mine[-8:]
        return eps[-6:]
    except Exception:
        return []


def _intention_goals(sess: dict[str, Any], trail: list[dict[str, Any]]) -> list[str]:
    goals: list[str] = []
    lb = sess.get("last_brief") or {}
    if lb.get("goal"):
        goals.append(str(lb["goal"])[:220])
    for t in sess.get("turns") or []:
        if t.get("role") == "user":
            u = str(t.get("text") or "").strip()
            if u and u not in goals:
                goals.append(u[:220])
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for g in goals:
        k = g.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(g)
    return out[:12]


def _auto_summary(goals: list[str], turns: list[dict[str, Any]]) -> str:
    """Cheap local summary — no frontier. Fallback extractive if Ollama down."""
    user_bits = [str(t.get("text") or "") for t in turns if t.get("role") == "user"][-6:]
    mag_bits = [str(t.get("text") or "") for t in turns if t.get("role") == "assistant"][-4:]
    blob_goals = "; ".join(goals[:5]) or "(no goals)"
    prompt_user = (
        f"Summarize this operator diary seal in 2-4 short sentences for a personal biographer.\n"
        f"Goals/topics: {blob_goals}\n"
        f"Operator said: {' | '.join(user_bits)[:600]}\n"
        f"Mag said (snip): {' | '.join(m[:80] for m in mag_bits)[:400]}\n"
        f"No RAM/BIOS unless they asked. Name people/ideas if present."
    )
    try:
        from models.providers import chat_provider

        res = chat_provider(
            "ollama",
            "You write short diary summaries. Factual, warm, no markdown.",
            prompt_user,
            model="gemma:2b",
            tier="T1",
            max_tokens=120,
            temperature=0.3,
        )
        if res.get("ok"):
            text = str(res.get("text") or res.get("content") or "").strip()
            if text:
                return text[:600]
    except Exception:
        pass
    # extractive fallback
    parts = []
    if goals:
        parts.append("Topics: " + "; ".join(goals[:4]))
    if user_bits:
        parts.append("You: " + user_bits[-1][:160])
    if mag_bits:
        parts.append("Mag: " + mag_bits[-1][:120])
    return " ".join(parts)[:500] or "Empty seal — no turns yet."


def freeze_context(
    *,
    session_id: str = "",
    channel: str = "voice",
    reason: str = "seal",
) -> dict[str, Any]:
    """Cheap snapshot of agent + day bead + tips at this instant.

    Frozen for fidelity and undefined future use — not a second DNA store.
    Links: agent_state tip, session verkle tip, residual day, working head.
    """
    ts = _utc()
    day = ts[:10] if len(ts) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    freeze: dict[str, Any] = {
        "schema": FREEZE_SCHEMA,
        "ts": ts,
        "day": day,
        "channel": channel or "voice",
        "reason": reason,
        "voice_session_id": _safe_id(session_id) if session_id else "",
        "agent": {},
        "session_verkle": {},
        "day_bead": {},
        "working": {},
        "nervous": {},
    }

    # Agent state tip (who Mag thought it was — frozen)
    try:
        from mag.agent_state import load_latest

        st = load_latest() or {}
        tip = st.get("tip") or {}
        freeze["agent"] = {
            "commitment": st.get("commitment") or "",
            "content_commit": (st.get("content_commit") or {}).get("hex") or "",
            "one_line": str(st.get("one_line") or "")[:300],
            "label": st.get("label") or "",
            "agent_tip_root": (tip.get("root") or "")[:64],
            "n_versions": tip.get("n_versions"),
            "path": "memory/agent_state/LATEST.json",
            "ts": st.get("ts") or "",
        }
    except Exception as exc:
        freeze["agent"] = {"error": str(exc)[:120]}

    # Session Verkle tip (bead chain at seal time)
    tip_path = ROOT / "memory" / "biography" / "verkle_tip.json"
    if tip_path.is_file():
        try:
            tip = json.loads(tip_path.read_text(encoding="utf-8"))
            freeze["session_verkle"] = {
                "root": tip.get("root") or "",
                "n_leaves": tip.get("n_leaves"),
                "last_filename": tip.get("last_filename"),
                "last_leaf_hash": tip.get("last_leaf_hash"),
                "last_session_id": tip.get("last_session_id"),
                "last_leaf_kind": tip.get("last_leaf_kind"),
                "path": "memory/biography/verkle_tip.json",
            }
        except Exception:
            pass

    # Day bead / residual for this calendar day or last session
    freeze["day_bead"] = {
        "day": day,
        "residual_glob": f"memory/biography/residual/*{day}*",
        "knots_day_prefix": day,
    }
    try:
        from mag.registry import get_latest_session_id, residual_path

        sid = get_latest_session_id() or ""
        if sid:
            rp = residual_path(sid)
            freeze["day_bead"]["latest_session_id"] = sid
            freeze["day_bead"]["residual_path"] = (
                str(rp.relative_to(ROOT)).replace("\\", "/") if rp and rp.is_file() else None
            )
            if rp and rp.is_file():
                try:
                    res = json.loads(rp.read_text(encoding="utf-8"))
                    card = res.get("session_card") if isinstance(res.get("session_card"), dict) else {}
                    freeze["day_bead"]["residual_tldr"] = str(res.get("tldr") or card.get("blurb") or "")[:240]
                    freeze["day_bead"]["residual_title"] = str(card.get("title") or "")[:120]
                except Exception:
                    pass
    except Exception:
        pass

    # Working head (cheap open loops glance)
    working = ROOT / "memory" / "working.md"
    if working.is_file():
        try:
            freeze["working"] = {
                "path": "memory/working.md",
                "head": working.read_text(encoding="utf-8", errors="replace")[:500],
            }
        except Exception:
            pass

    # Nervous system path only (don't re-probe whole body every freeze if heavy)
    ns = ROOT / "memory" / "nervous_system.md"
    if ns.is_file():
        try:
            freeze["nervous"] = {
                "path": "memory/nervous_system.md",
                "head": ns.read_text(encoding="utf-8", errors="replace")[:400],
            }
        except Exception:
            pass

    freeze["freeze_hash"] = _h(
        json.dumps(
            {
                "day": freeze["day"],
                "agent": freeze.get("agent"),
                "session_verkle": {
                    "root": (freeze.get("session_verkle") or {}).get("root"),
                    "n_leaves": (freeze.get("session_verkle") or {}).get("n_leaves"),
                },
                "ts": freeze["ts"],
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    )
    return freeze


def save_auto_freeze(
    *,
    session_id: str = "",
    channel: str = "voice",
    brief: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Cheap automatic freeze — append-only, no Verkle tip advance.

    For future undefined purposes: reconstruct 'what Mag/agent believed that day'.
    Throttled per session unless force=True.
    """
    AUTO_DIR.mkdir(parents=True, exist_ok=True)
    sid = _safe_id(session_id) if session_id else "anon"
    # throttle
    if not force and AUTO_INDEX.is_file():
        try:
            lines = [ln for ln in AUTO_INDEX.read_text(encoding="utf-8").splitlines() if ln.strip()]
            for line in reversed(lines[-30:]):
                row = json.loads(line)
                if str(row.get("voice_session_id") or "") != sid:
                    continue
                prev_ts = str(row.get("ts") or "")
                if prev_ts:
                    try:
                        prev = datetime.fromisoformat(prev_ts.replace("Z", "+00:00"))
                        now = datetime.now(timezone.utc)
                        if (now - prev).total_seconds() < _AUTO_MIN_GAP_S:
                            return {
                                "ok": True,
                                "skipped": True,
                                "reason": "throttled",
                                "gap_s": _AUTO_MIN_GAP_S,
                            }
                    except Exception:
                        pass
                break
        except Exception:
            pass

    freeze = freeze_context(session_id=sid, channel=channel, reason="auto")
    if brief:
        freeze["last_brief"] = {
            "goal": brief.get("goal"),
            "depth": brief.get("depth"),
            "why": brief.get("why"),
            "seat_recommend": brief.get("seat_recommend"),
        }
    freeze_id = f"auto-{freeze['day']}-{uuid4().hex[:8]}"
    freeze["freeze_id"] = freeze_id
    freeze["promoted_to_verkle"] = False

    fpath = AUTO_DIR / f"{freeze_id}.json"
    fpath.write_text(json.dumps(freeze, indent=2, default=str), encoding="utf-8")
    rel = str(fpath.relative_to(ROOT)).replace("\\", "/")
    try:
        with AUTO_INDEX.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "freeze_id": freeze_id,
                        "ts": freeze["ts"],
                        "day": freeze["day"],
                        "voice_session_id": sid,
                        "path": rel,
                        "agent_commit": (freeze.get("agent") or {}).get("content_commit") or "",
                        "verkle_n_leaves": (freeze.get("session_verkle") or {}).get("n_leaves"),
                        "verkle_root8": str((freeze.get("session_verkle") or {}).get("root") or "")[:8],
                    },
                    default=str,
                )
                + "\n"
            )
    except OSError:
        pass

    return {
        "ok": True,
        "skipped": False,
        "freeze_id": freeze_id,
        "path": rel,
        "day": freeze["day"],
        "freeze_hash": freeze.get("freeze_hash"),
        "schema": FREEZE_SCHEMA,
    }


def _artifacts(
    *,
    session_id: str,
    include_audio: bool,
    dig_eps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    arts: list[dict[str, Any]] = []
    arts.append(
        {
            "kind": "trail",
            "path": "memory/runs/voice_trail.jsonl",
            "session_id": session_id,
        }
    )
    arts.append(
        {
            "kind": "dig",
            "path": "memory/working/voice_dig_board.json",
            "episodes_n": len(dig_eps),
        }
    )
    sess_path = ROOT / "memory" / "working" / "voice_sessions" / f"{_safe_id(session_id)}.json"
    if sess_path.is_file():
        arts.append(
            {
                "kind": "session",
                "path": str(sess_path.relative_to(ROOT)).replace("\\", "/"),
            }
        )
    if include_audio:
        stt_dir = ROOT / "memory" / "agent_uploads" / "voice_stt"
        if stt_dir.is_dir():
            clips = sorted(stt_dir.glob("stt-*"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]
            for c in clips:
                arts.append(
                    {
                        "kind": "audio",
                        "path": str(c.relative_to(ROOT)).replace("\\", "/"),
                        "voice_train_ok": False,  # consent default off
                    }
                )
    return arts


def append_diary_to_verkle(leaf: dict[str, Any]) -> dict[str, Any]:
    """Append a diary leaf through the same single-writer boundary as session knots."""
    # This path historically copied the chain rewrite logic instead of calling
    # verkle_knot.append_verkle_knot because diary leaves carry extra fields.
    # Keep that shape, but make the mutation participate in the canonical lock;
    # otherwise a diary seal can race a normal append and publish a stale root.
    from mag.verkle_knot import verkle_lock

    with verkle_lock():
        return _append_diary_to_verkle_unlocked(leaf)


def _append_diary_to_verkle_unlocked(leaf: dict[str, Any]) -> dict[str, Any]:
    """Locked implementation for :func:`append_diary_to_verkle`."""
    from mag.verkle_knot import (
        BIO,
        CHAIN,
        KNOTS,
        TIP,
        _load_chain_rows,
        _merkle_root,
        _rewrite_chain,
    )

    KNOTS.mkdir(parents=True, exist_ok=True)
    DIARY_DIR.mkdir(parents=True, exist_ok=True)

    seal_id = str(leaf.get("seal_id") or "")
    ts = leaf.get("ts") or _utc()
    minute = ""
    m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})", ts.replace("+00:00", "Z"))
    if m:
        minute = f"{m.group(1)}_{m.group(2)}{m.group(3)}"
    else:
        minute = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    theme = "diary"
    goals = leaf.get("intention_goals") or []
    if goals:
        g0 = re.sub(r"[^a-z0-9]+", "-", str(goals[0]).lower())[:24].strip("-") or "diary"
        theme = g0
    sid8 = seal_id.replace("diary-", "")[:8]
    commit8 = str(leaf.get("leaf_hash") or "0")[:8]
    fname = f"{minute}_{theme}_{sid8}_{commit8}.diary.knot.json"
    leaf = dict(leaf)
    leaf["filename"] = fname
    leaf["type"] = "diary_node_leaf"
    leaf["schema"] = "verkle_knot_leaf.v1"
    leaf["leaf_kind"] = "diary_node"

    path = KNOTS / fname
    path.write_text(json.dumps(leaf, indent=2, default=str), encoding="utf-8")
    # durable copy under diary_nodes
    dpath = DIARY_DIR / fname
    dpath.write_text(json.dumps(leaf, indent=2, default=str), encoding="utf-8")

    frozen = leaf.get("frozen") or {}
    chain_row = {
        "ts": ts if ts.endswith("Z") else ts.replace("+00:00", "Z"),
        "filename": fname,
        "leaf_hash": leaf["leaf_hash"],
        "session_id": seal_id,  # unique per seal — always append
        "leaf_kind": "diary_node",
        "channel": leaf.get("channel"),
        "title": leaf.get("title"),
        "start_minute": leaf.get("ts"),
        "end_minute": leaf.get("ts"),
        "dominant_theme": theme,
        "amended": False,
        "voice_session_id": leaf.get("voice_session_id"),
        # Fidelity joins — reconstruct agent + day bead later
        "day": frozen.get("day") or (leaf.get("ts") or "")[:10],
        "agent_commit": (frozen.get("agent") or {}).get("content_commit") or "",
        "agent_tip_root8": str((frozen.get("agent") or {}).get("agent_tip_root") or "")[:8],
        "verkle_root_at_seal8": str((frozen.get("session_verkle") or {}).get("root") or "")[:8],
        "verkle_n_at_seal": (frozen.get("session_verkle") or {}).get("n_leaves"),
        "freeze_hash": frozen.get("freeze_hash") or "",
    }
    rows = _load_chain_rows()
    rows.append(chain_row)
    all_hashes = _rewrite_chain(rows)
    root = _merkle_root(all_hashes) if all_hashes else _h(b"empty")
    parent_root = _merkle_root(all_hashes[:-1]) if len(all_hashes) > 1 else _h(b"empty")

    tip = {
        "schema": "verkle_tip.v1",
        "root": root,
        "n_leaves": len(all_hashes),
        "last_filename": fname,
        "last_leaf_hash": leaf["leaf_hash"],
        "last_session_id": seal_id,
        "last_leaf_kind": "diary_node",
        "updated_minute": minute.replace("_", "T")[:16] if minute else None,
        "note": "Session knots + diary seals. Merkle–Verkle hybrid tip.",
    }
    TIP.write_text(json.dumps(tip, indent=2), encoding="utf-8")
    (BIO / "latest.diary.knot.json").write_text(
        json.dumps(leaf, indent=2, default=str), encoding="utf-8"
    )

    # index
    try:
        with INDEX_PATH.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "seal_id": seal_id,
                        "filename": fname,
                        "leaf_hash": leaf["leaf_hash"],
                        "title": leaf.get("title"),
                        "ts": ts,
                        "day": chain_row.get("day"),
                        "n_leaves": len(all_hashes),
                        "path": str(dpath.relative_to(ROOT)).replace("\\", "/"),
                        "agent_commit": chain_row.get("agent_commit"),
                        "verkle_n_at_seal": chain_row.get("verkle_n_at_seal"),
                        "freeze_hash": chain_row.get("freeze_hash"),
                    },
                    default=str,
                )
                + "\n"
            )
    except OSError:
        pass

    return {
        "ok": True,
        "filename": fname,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "diary_path": str(dpath.relative_to(ROOT)).replace("\\", "/"),
        "leaf_hash": leaf["leaf_hash"],
        "verkle_root": root,
        "parent_verkle_root": parent_root,
        "n_leaves": len(all_hashes),
        "tip": str(TIP.relative_to(ROOT)).replace("\\", "/"),
    }


def seal_diary(
    *,
    session_id: str = "",
    title: str = "",
    channel: str = "voice",
    include_audio: bool = False,
    summary: str = "",
) -> dict[str, Any]:
    """Seal voice/talk window into a diary node + Verkle leaf + train event."""
    sid = _safe_id(session_id) if session_id else ""
    if not sid:
        sid = f"voice-{uuid4().hex[:10]}"

    sess = _gather_session(sid)
    turns = list(sess.get("turns") or [])
    trail = _gather_trail(sid)
    dig_eps = _gather_dig(sid)
    goals = _intention_goals(sess, trail)
    if not turns and not goals and not trail:
        return {
            "ok": False,
            "schema": SCHEMA,
            "error": "nothing to seal — talk first, then Seal diary",
            "session_id": sid,
        }

    seal_id = f"diary-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}-{uuid4().hex[:6]}"
    auto_title = title.strip() if title else ""
    if not auto_title:
        if goals:
            auto_title = str(goals[0])[:80]
        elif turns:
            auto_title = str(turns[-1].get("text") or "voice seal")[:80]
        else:
            auto_title = f"Diary seal {seal_id[-6:]}"

    summ = (summary or "").strip() or _auto_summary(goals, turns)
    arts = _artifacts(session_id=sid, include_audio=include_audio, dig_eps=dig_eps)
    # Freeze agent + day bead + tips *before* tip advances (fidelity: state as recorded)
    frozen = freeze_context(session_id=sid, channel=channel or "voice", reason="seal")
    arts.append(
        {
            "kind": "freeze",
            "day": frozen.get("day"),
            "freeze_hash": frozen.get("freeze_hash"),
            "agent_commit": (frozen.get("agent") or {}).get("content_commit"),
            "agent_path": (frozen.get("agent") or {}).get("path"),
            "verkle_n_at_seal": (frozen.get("session_verkle") or {}).get("n_leaves"),
            "residual_path": (frozen.get("day_bead") or {}).get("residual_path"),
        }
    )

    # Body without leaf_hash for hashing
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "kind": "diary_node_leaf",
        "seal_id": seal_id,
        "ts": _utc(),
        "day": frozen.get("day"),
        "channel": channel or "voice",
        "voice_session_id": sid,
        "title": auto_title,
        "summary": summ,
        "intention_goals": goals,
        "turns_n": len(turns),
        "turns_excerpt": [
            {"role": t.get("role"), "text": str(t.get("text") or "")[:300], "seat": t.get("seat")}
            for t in turns[-16:]
        ],
        "last_brief": sess.get("last_brief") or {},
        "dig_episodes": [
            {"you": e.get("you"), "mag": e.get("mag"), "seat": e.get("seat")} for e in dig_eps[-6:]
        ],
        "frozen": frozen,  # agent tip + day bead + verkle tip at seal time
        "artifacts": arts,
        "training": {
            "exportable": True,
            "tier_max": "T2",
            "tags": ["diary", "voice", channel or "voice", "freeze"],
            "voice_train_ok": False,
        },
    }
    body["leaf_hash"] = _leaf_hash(
        {k: v for k, v in body.items() if k != "leaf_hash"}
    )

    verkle = append_diary_to_verkle(body)

    # Also park a full freeze file under auto/ for easy LOAD later
    try:
        AUTO_DIR.mkdir(parents=True, exist_ok=True)
        freeze_path = AUTO_DIR / f"seal-{seal_id}.json"
        frozen_seal = dict(frozen)
        frozen_seal["seal_id"] = seal_id
        frozen_seal["promoted_to_verkle"] = True
        frozen_seal["leaf_hash"] = body["leaf_hash"]
        freeze_path.write_text(json.dumps(frozen_seal, indent=2, default=str), encoding="utf-8")
    except Exception:
        freeze_path = None

    # High-fidelity training event
    try:
        from mag.training_events import emit

        emit(
            "diary_seal",
            join={
                "seal_id": seal_id,
                "session_id": sid,
                "leaf_hash": str(body["leaf_hash"])[:16],
                "day": str(frozen.get("day") or ""),
                "agent_commit": str((frozen.get("agent") or {}).get("content_commit") or "")[:16],
            },
            input_data={
                "title": auto_title,
                "goals": goals[:8],
                "brief": sess.get("last_brief") or {},
                "turns_n": len(turns),
                "frozen": {
                    "day": frozen.get("day"),
                    "agent_one_line": (frozen.get("agent") or {}).get("one_line"),
                    "verkle_n": (frozen.get("session_verkle") or {}).get("n_leaves"),
                },
            },
            action={
                "channel": channel,
                "include_audio": include_audio,
                "n_leaves": verkle.get("n_leaves"),
            },
            outcome={
                "ok": True,
                "summary": summ[:400],
                "filename": verkle.get("filename"),
                "verkle_root": str(verkle.get("verkle_root") or "")[:16],
                "artifacts_n": len(arts),
                "freeze_hash": frozen.get("freeze_hash"),
            },
            pattern_tags=["diary", "verkle", "voice", "train", "freeze"],
            tier_max="T2",
            exportable=True,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "schema": SCHEMA,
        "seal_id": seal_id,
        "day": frozen.get("day"),
        "title": auto_title,
        "summary": summ,
        "intention_goals": goals,
        "artifacts": arts,
        "frozen": {
            "day": frozen.get("day"),
            "agent_commit": (frozen.get("agent") or {}).get("content_commit"),
            "agent_one_line": (frozen.get("agent") or {}).get("one_line"),
            "verkle_n_at_seal": (frozen.get("session_verkle") or {}).get("n_leaves"),
            "freeze_hash": frozen.get("freeze_hash"),
            "path": str(freeze_path.relative_to(ROOT)).replace("\\", "/") if freeze_path else None,
        },
        "voice_session_id": sid,
        "leaf_hash": body["leaf_hash"],
        "verkle": verkle,
        "n_leaves": verkle.get("n_leaves"),
        "training": body["training"],
        "note": "Sealed to tip with frozen agent+day bead. Auto freezes also land under diary_nodes/auto/.",
    }


def list_diary(*, limit: int = 20) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if INDEX_PATH.is_file():
        try:
            for line in INDEX_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
    rows = rows[-max(1, min(limit, 100)) :]
    rows.reverse()
    tip = {}
    tip_path = ROOT / "memory" / "biography" / "verkle_tip.json"
    if tip_path.is_file():
        try:
            tip = json.loads(tip_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "ok": True,
        "schema": SCHEMA,
        "n": len(rows),
        "seals": rows,
        "verkle_tip": {
            "n_leaves": tip.get("n_leaves"),
            "root": str(tip.get("root") or "")[:16],
            "last_leaf_kind": tip.get("last_leaf_kind"),
            "last_filename": tip.get("last_filename"),
        },
    }


def handle_diary(body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    action = str(body.get("action") or "list").strip().lower()
    if action in ("seal", "commit", "file"):
        return seal_diary(
            session_id=str(body.get("session_id") or ""),
            title=str(body.get("title") or ""),
            channel=str(body.get("channel") or "voice"),
            include_audio=bool(body.get("include_audio")),
            summary=str(body.get("summary") or ""),
        )
    if action in ("freeze", "auto_freeze", "snapshot"):
        return save_auto_freeze(
            session_id=str(body.get("session_id") or ""),
            channel=str(body.get("channel") or "voice"),
            brief=body.get("brief") if isinstance(body.get("brief"), dict) else None,
            force=bool(body.get("force")),
        )
    if action in ("list", "status", ""):
        return list_diary(limit=int(body.get("limit") or 20))
    return {"ok": False, "error": f"unknown action: {action}"}
