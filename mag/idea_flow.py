"""Idea flow ledger — where work went, by model/API, time, quota, artifacts.

Powers Mag dashboard tab "Flow". Aggregates logs + memory dirs only.
No network. Grok TUI tokens are never claimed here.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

USAGE = ROOT / "logs" / "usage.jsonl"
PROV = ROOT / "logs" / "provider_usage.jsonl"
RESEARCH = ROOT / "memory" / "research_packs"
BIO = ROOT / "memory" / "biography"
BRIEFS = ROOT / "memory" / "briefs"
INGEST = ROOT / "memory" / "ingest"
CONTEXT = ROOT / "memory" / "context_pack_latest.json"


def _read_jsonl(path: Path, limit: int = 5000) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _est_tokens(chars: int) -> int:
    return max(0, int(chars or 0) // 4)


def _bucket_model(meta: dict, detail: str = "") -> str:
    m = str((meta or {}).get("model") or "").strip()
    if m:
        return m
    # parse "role=clerk model=gemma:2b ms=…"
    if "model=" in detail:
        try:
            part = detail.split("model=", 1)[1].split()[0]
            return part
        except IndexError:
            pass
    return ""


def _chat_rollups(rows: list[dict]) -> dict[str, Any]:
    by_model: dict[str, dict] = defaultdict(
        lambda: {
            "calls": 0,
            "ok": 0,
            "fail": 0,
            "ms": 0,
            "out_chars": 0,
            "est_out_tokens": 0,
            "roles": defaultdict(int),
        }
    )
    by_role: dict[str, dict] = defaultdict(
        lambda: {
            "calls": 0,
            "ms": 0,
            "out_chars": 0,
            "est_out_tokens": 0,
            "models": defaultdict(int),
        }
    )
    by_day: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    by_action: dict[str, int] = defaultdict(int)
    timeline: list[dict] = []

    for r in rows:
        action = str(r.get("action") or "?")
        by_action[action] += 1
        meta = r.get("meta") or {}
        ts = str(r.get("ts") or "")
        day = ts[:10] if ts else "?"
        model = _bucket_model(meta, str(r.get("detail") or ""))
        role = str(meta.get("role") or "")
        ms = int(meta.get("ms") or 0)
        chars = int(meta.get("chars") or 0)
        ok = bool(r.get("ok", True))
        lane = str(r.get("lane") or "")

        is_chat = action in ("chat", "provider_chat") or bool(model)
        if action == "chat" or (action == "provider_chat" and model):
            key = model or ("remote?" if action == "provider_chat" else "unknown")
            by_model[key]["calls"] += 1
            by_model[key]["ms"] += ms
            by_model[key]["out_chars"] += chars
            by_model[key]["est_out_tokens"] += _est_tokens(chars)
            if ok:
                by_model[key]["ok"] += 1
            else:
                by_model[key]["fail"] += 1
            if role:
                by_model[key]["roles"][role] += 1
            rk = role or ("provider" if action == "provider_chat" else "?")
            by_role[rk]["calls"] += 1
            by_role[rk]["ms"] += ms
            by_role[rk]["out_chars"] += chars
            by_role[rk]["est_out_tokens"] += _est_tokens(chars)
            by_role[rk]["models"][key] += 1
            if day and day != "?":
                by_day[day][key] += 1

        # idea-ish events for timeline (not every visual_pack heartbeat)
        if action in (
            "chat",
            "provider_chat",
            "ask",
            "multi_smoke",
            "dispatch",
            "research_pack",
            "escalate",
            "brief",
        ) or (action == "visual_pack" and meta.get("n_nodes")):
            if action == "brief" and not meta.get("used_llm"):
                # still note as artifact write, lighter
                pass
            timeline.append(
                {
                    "ts": ts,
                    "lane": lane,
                    "action": action,
                    "ok": ok,
                    "model": model or None,
                    "role": role or None,
                    "ms": ms or None,
                    "est_out_tokens": _est_tokens(chars) if chars else None,
                    "detail": (str(r.get("detail") or ""))[:120],
                    "artifact": _artifact_hint(meta),
                }
            )

    # serialize defaultdicts
    models_out = []
    for m, s in sorted(by_model.items(), key=lambda x: -x[1]["calls"]):
        models_out.append(
            {
                "model": m,
                "calls": s["calls"],
                "ok": s["ok"],
                "fail": s["fail"],
                "wall_s": round(s["ms"] / 1000.0, 2),
                "est_out_tokens": s["est_out_tokens"],
                "out_chars": s["out_chars"],
                "roles": dict(s["roles"]),
                "local": _is_local_model(m),
            }
        )
    roles_out = []
    for role, s in sorted(by_role.items(), key=lambda x: -x[1]["calls"]):
        roles_out.append(
            {
                "role": role,
                "calls": s["calls"],
                "wall_s": round(s["ms"] / 1000.0, 2),
                "est_out_tokens": s["est_out_tokens"],
                "models": dict(s["models"]),
            }
        )
    days_out = []
    for day in sorted(by_day.keys()):
        days_out.append({"day": day, "by_model": dict(by_day[day])})

    total_calls = sum(m["calls"] for m in models_out)
    total_wall = sum(m["wall_s"] for m in models_out)
    total_est = sum(m["est_out_tokens"] for m in models_out)

    return {
        "by_model": models_out,
        "by_role": roles_out,
        "by_day": days_out,
        "by_action": dict(sorted(by_action.items(), key=lambda x: -x[1])),
        "totals": {
            "chat_calls": total_calls,
            "wall_s": round(total_wall, 2),
            "est_out_tokens": total_est,
        },
        "timeline": timeline[-80:],  # last 80 idea-ish events
    }


def _is_local_model(model: str) -> bool:
    m = (model or "").lower()
    if not m or m in ("remote?", "unknown"):
        return False
    if any(x in m for x in ("gemma", "llama", "mistral", "phi", "qwen", "nomic")):
        if "/" in m and not m.startswith("ollama"):
            # openrouter/meta-llama etc → remote
            return "ollama" in m
        return True
    return False


def _artifact_hint(meta: dict) -> str | None:
    if not meta:
        return None
    for k in ("path", "latest", "pdf", "prompt"):
        p = meta.get(k)
        if p:
            try:
                return Path(str(p)).name
            except Exception:
                return str(p)[-60:]
    if meta.get("commit"):
        return f"commit={str(meta['commit'])[:12]}"
    if meta.get("n_nodes") is not None:
        return f"nodes={meta['n_nodes']}"
    return None


def _provider_rollups(rows: list[dict]) -> dict[str, Any]:
    by_p: dict[str, dict] = defaultdict(
        lambda: {
            "calls": 0,
            "ok": 0,
            "fail": 0,
            "tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "models": defaultdict(int),
        }
    )
    edges: list[dict] = []  # idea edges: provider → model
    for r in rows:
        p = str(r.get("provider") or "?")
        model = str(r.get("model") or "?")
        tok = int(r.get("tokens") or 0)
        pt = int(r.get("prompt_tokens") or 0)
        ct = int(r.get("completion_tokens") or 0)
        calls = int(r.get("calls") or 1)
        ok = bool(r.get("ok", True))
        by_p[p]["calls"] += calls
        by_p[p]["tokens"] += tok
        by_p[p]["prompt_tokens"] += pt
        by_p[p]["completion_tokens"] += ct
        if ok:
            by_p[p]["ok"] += calls
        else:
            by_p[p]["fail"] += calls
        by_p[p]["models"][model] += calls
        edges.append(
            {
                "ts": r.get("ts"),
                "provider": p,
                "model": model,
                "tokens": tok,
                "ok": ok,
            }
        )

    providers = []
    local_tok = remote_tok = local_c = remote_c = 0
    for p, s in sorted(by_p.items(), key=lambda x: -x[1]["calls"]):
        entry = {
            "provider": p,
            "calls": s["calls"],
            "ok": s["ok"],
            "fail": s["fail"],
            "tokens": s["tokens"],
            "prompt_tokens": s["prompt_tokens"],
            "completion_tokens": s["completion_tokens"],
            "models": dict(s["models"]),
            "local": p == "ollama",
        }
        providers.append(entry)
        if p == "ollama":
            local_tok += s["tokens"]
            local_c += s["calls"]
        else:
            remote_tok += s["tokens"]
            remote_c += s["calls"]

    return {
        "by_provider": providers,
        "totals": {
            "local_calls": local_c,
            "local_tokens": local_tok,
            "remote_calls": remote_c,
            "remote_tokens": remote_tok,
        },
        "recent": edges[-40:],
    }


def _research_ideas() -> list[dict]:
    if not RESEARCH.is_dir():
        return []
    ideas = []
    for p in sorted(RESEARCH.glob("*.json"), reverse=True):
        if p.name.startswith("latest"):
            continue
        d = _read_json(p)
        if not d:
            continue
        base = p.stem
        answers = []
        for ap in RESEARCH.glob(f"{base}.answer.*.md"):
            seat = ap.name.replace(f"{base}.answer.", "").replace(".md", "")
            text = ap.read_text(encoding="utf-8", errors="replace")
            answers.append(
                {
                    "seat": seat,
                    "chars": len(text),
                    "est_tokens": _est_tokens(len(text)),
                    "preview": text.strip()[:280],
                    "file": ap.name,
                }
            )
        sources = []
        for s in d.get("sources") or []:
            sources.append(
                {
                    "url": s.get("url") or s.get("final_url"),
                    "ok": s.get("ok"),
                    "chars": s.get("chars"),
                    "local_text": (s.get("local") or {}).get("text"),
                }
            )
        ideas.append(
            {
                "id": d.get("id") or base,
                "ask": d.get("ask") or d.get("title") or base,
                "created_at": d.get("created_at"),
                "elevate_to": d.get("elevate_to"),
                "criteria": d.get("success_criteria") or [],
                "sources": sources,
                "answers": answers,
                "has_pdf": (RESEARCH / f"{base}.pdf").is_file(),
                "has_prompt": (RESEARCH / f"{base}.prompt.txt").is_file(),
                "routing": d.get("routing") or {},
                "files": {
                    "json": f"/files/research_packs/{p.name}",
                    "pdf": f"/files/research_packs/{base}.pdf"
                    if (RESEARCH / f"{base}.pdf").is_file()
                    else None,
                    "prompt": f"/files/research_packs/{base}.prompt.txt"
                    if (RESEARCH / f"{base}.prompt.txt").is_file()
                    else None,
                },
                "reconciliation": _reconcile_pack(d, answers),
            }
        )
    return ideas[:30]


def _reconcile_pack(pack: dict, answers: list[dict]) -> dict:
    """Where the idea went and what closed."""
    src_ok = sum(1 for s in (pack.get("sources") or []) if s.get("ok"))
    src_n = len(pack.get("sources") or [])
    seats = [a["seat"] for a in answers]
    status = "open"
    if answers:
        status = "answered_local" if any(s == "local" for s in seats) else "answered"
    if pack.get("elevate_to") == "grok_tui" and "grok" not in " ".join(seats):
        status = "awaiting_elevate" if answers else "pack_ready"
    elif pack.get("elevate_to") == "local" and answers:
        status = "reconciled_local"
    return {
        "status": status,
        "sources_ok": f"{src_ok}/{src_n}",
        "answer_seats": seats,
        "elevate_to": pack.get("elevate_to"),
        "note": (
            "Lesser models ran on pack only; elevate Grok only if fidelity fails."
            if pack.get("routing", {}).get("local_first")
            else "See pack.routing"
        ),
    }


def _artifacts() -> dict[str, Any]:
    packs = []
    if RESEARCH.is_dir():
        for p in RESEARCH.glob("*.pdf"):
            if p.name.startswith("latest"):
                continue
            packs.append(
                {
                    "kind": "research_pdf",
                    "name": p.name,
                    "bytes": p.stat().st_size,
                    "href": f"/files/research_packs/{p.name}",
                    "mtime": datetime.fromtimestamp(
                        p.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )
    dossiers = []
    if BIO.is_dir():
        for p in BIO.glob("*.dossier.json"):
            if p.name.startswith("latest"):
                continue
            dossiers.append(
                {
                    "kind": "dossier",
                    "name": p.name,
                    "href": f"/files/biography/{p.name}",
                }
            )
    briefs = []
    if BRIEFS.is_dir():
        for p in BRIEFS.glob("*.md"):
            briefs.append(
                {
                    "kind": "brief",
                    "name": p.name,
                    "chars": p.stat().st_size,
                    "href": f"/files/briefs/{p.name}"
                    if p.parent.name == "briefs"
                    else None,
                }
            )
    # briefs live under memory/briefs — safe_file maps files/ → memory/
    for b in briefs:
        b["href"] = f"/files/briefs/{b['name']}"

    visual = []
    if BIO.is_dir():
        for p in BIO.glob("*.visual_pack.json"):
            visual.append(
                {
                    "kind": "visual_pack",
                    "name": p.name,
                    "href": f"/files/biography/{p.name}",
                }
            )

    catalog = _read_json(INGEST / "catalog.json") or {}
    ingest_n = int(catalog.get("count") or len(catalog.get("items") or {}) or 0)

    context = _read_json(CONTEXT)
    verkle_tip = _read_json(BIO / "verkle_tip.json") or {}

    return {
        "research_pdfs": packs,
        "dossiers": dossiers[:20],
        "briefs": briefs[:20],
        "visual_packs": visual[:10],
        "ingest_count": ingest_n,
        "context_pack": bool(context),
        "verkle_tip": {
            "root": verkle_tip.get("verkle_root") or verkle_tip.get("root"),
            "session_id": verkle_tip.get("session_id"),
        },
        "counts": {
            "research_pdfs": len(packs),
            "dossiers": len(dossiers),
            "briefs": len(briefs),
            "visual_packs": len(visual),
            "ingest": ingest_n,
        },
    }


def _flow_edges(chat: dict, prov: dict, ideas: list[dict]) -> list[dict]:
    """Sankey-ish edges: seat/role → model → provider family."""
    edges: list[dict] = []
    for r in chat.get("by_role") or []:
        for model, n in (r.get("models") or {}).items():
            edges.append(
                {
                    "from": f"role:{r['role']}",
                    "to": f"model:{model}",
                    "weight": n,
                    "kind": "role_model",
                }
            )
            dest = "provider:ollama" if _is_local_model(model) else "provider:remote"
            edges.append(
                {
                    "from": f"model:{model}",
                    "to": dest,
                    "weight": n,
                    "kind": "model_provider",
                }
            )
    for p in prov.get("by_provider") or []:
        for model, n in (p.get("models") or {}).items():
            edges.append(
                {
                    "from": f"api:{p['provider']}",
                    "to": f"model:{model}",
                    "weight": n,
                    "kind": "api_model",
                }
            )
    for idea in ideas:
        for ans in idea.get("answers") or []:
            edges.append(
                {
                    "from": f"idea:{(idea.get('ask') or '')[:40]}",
                    "to": f"seat:{ans.get('seat')}",
                    "weight": max(1, (ans.get("est_tokens") or 1) // 50),
                    "kind": "idea_seat",
                }
            )
    return edges


def build_idea_flow() -> dict[str, Any]:
    usage_rows = _read_jsonl(USAGE)
    prov_rows = _read_jsonl(PROV)
    chat = _chat_rollups(usage_rows)
    providers = _provider_rollups(prov_rows)
    ideas = _research_ideas()
    artifacts = _artifacts()

    budgets = None
    try:
        from models.quota import all_budgets

        budgets = all_budgets()
    except Exception as e:
        budgets = {"ok": False, "error": str(e)}

    remaining = []
    for p in (budgets or {}).get("providers") or []:
        remaining.append(
            {
                "provider": p.get("provider"),
                "name": p.get("name"),
                "unlimited": p.get("unlimited"),
                "used_calls": p.get("used_calls"),
                "used_tokens": p.get("used_tokens"),
                "remaining_calls": p.get("remaining_calls"),
                "remaining_tokens": p.get("remaining_tokens"),
                "budget_ok": p.get("budget_ok"),
                "reset_in_hours": p.get("reset_in_hours"),
                "configured": p.get("configured"),
                "period": p.get("period"),
            }
        )

    # reconciliation summary
    open_ideas = sum(
        1
        for i in ideas
        if (i.get("reconciliation") or {}).get("status")
        in ("open", "pack_ready", "awaiting_elevate")
    )
    closed_ideas = len(ideas) - open_ideas

    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "note": (
            "This tab is activity telemetry: local output tokens are estimated from chars/4 and provider "
            "rows show reported volume. See Cost truth above for receipt-priced dollars. "
            "Grok TUI and subscription usage are not metered here."
        ),
        "spend": {
            "local_chat": chat["totals"],
            "providers": providers["totals"],
            "combined_picture": {
                "local_est_out_tokens": chat["totals"]["est_out_tokens"],
                "local_api_tokens": providers["totals"]["local_tokens"],
                "remote_api_tokens": providers["totals"]["remote_tokens"],
                "wall_s": chat["totals"]["wall_s"],
                "chat_calls": chat["totals"]["chat_calls"],
            },
        },
        "models": chat["by_model"],
        "roles": chat["by_role"],
        "days": chat["by_day"],
        "actions": chat["by_action"],
        "providers": providers["by_provider"],
        "provider_recent": providers["recent"],
        "remaining": remaining,
        "ideas": ideas,
        "ideas_summary": {
            "n": len(ideas),
            "open": open_ideas,
            "reconciled": closed_ideas,
        },
        "artifacts": artifacts,
        "edges": _flow_edges(chat, providers, ideas),
        "timeline": list(reversed(chat["timeline"][-60:])),  # newest first
    }
