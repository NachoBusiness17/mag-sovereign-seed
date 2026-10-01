"""Session dossier: structured pack + human PDF for scanning.

Outputs per session:
  memory/biography/<id>.md          (existing narrative)
  memory/biography/<id>.dossier.json  (machine-readable)
  memory/biography/<id>.pdf           (human scan pack)
  memory/biography/<id>/assets/       (charts / figures)
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT
from mag.chord_lens import STRIKE_ROOT, build_chord_strike
from mag.ingest_registry import resolve_and_ingest
from mag.knot_math import (
    content_commit,
    duration_minutes,
    load_session_meta,
    scalar_knot_proxy,
)
from mag.steiniger_lens import (
    build_laymen_operations,
    laymen_attribution_block,
)

BIO_DIR = ROOT / "memory" / "biography"
DOSSIER_SCHEMA = "session_dossier.v4_chord_knot"


def _upsert_jsonl(
    path: Path, key: str, value: str, row: dict[str, Any], *, keep: int = 400
) -> None:
    """One row per key value — amend original, avoid append bloat."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(r.get(key) or "") == str(value):
                continue
            rows.append(r)
    rows.append(row)
    path.write_text(
        "\n".join(json.dumps(r, default=str) for r in rows[-keep:]) + "\n",
        encoding="utf-8",
    )

# Theme / metaphor / concept lexicons (heuristic seed; LLM can enrich)
THEME_KEYS = {
    "mirror_meta": ["mirror", "chord", "locus", "meta layer", "sovereign"],
    "mag_hands": ["mag", "ollama", "langgraph", "todo", "agent"],
    "scrum_plan": ["scrum", "backlog", "sprint", "ticket", "w0."],
    "constitution": ["constitution", "lessig", "tier", "capture", "fork"],
    "dashboard": ["dashboard", "scaffold", "instrument", "zeitgeist"],
    "harness": ["harness", "handoff", "grok -p", "headless"],
    "biography": ["biograph", "session", "summar", "watch", "live_from"],
    "data_r0": ["data/raw", "archive", "train", "r0", "annotate"],
}

METAPHOR_PATTERNS = [
    (r"\bmag\b", "Mag (PSO companion) — bonded helper, not the hero"),
    (r"\bwindmill", "Quixote windmills — capture systems that look like landscape"),
    (r"\bmyceli", "Mycelium — forkable network without a single core"),
    (r"\bthrone", "Throne — capture center to refuse"),
    (r"\brope\b|\bknot\b", "Rope/knot — tension to make visible, not polish away"),
    (r"\bchord\b", "Strike the chord — multi-frame truth + personal impact + moves"),
    (r"\btoy\b", "Toy vs instrument — scaffold real, product not yet"),
    (r"\bsancho\b", "Sancho — spine without flattery"),
    (r"\bclerk\b", "Clerk Mag — hands without mirror soul"),
    (r"\bbiograph", "Biographer — chronicle of intent for future-you"),
]

IDEA_PATTERNS = [
    (r"data.?tier|T0|T1|T2|T3", "Data tiers as architecture-as-law (what may leave the machine)"),
    (r"code is law|lessig", "Lessig: architecture regulates more than content"),
    (r"multi-?frame|observer chart", "Multi-frame agency without single-cause collapse"),
    (r"handoff\.v1|service contract", "Agent handoffs as versioned contracts"),
    (r"fork equal|no rank|no token", "Fork equality / anti-rank capture"),
    (r"open.?router|multi.?model", "Model lanes: local vs specialist cloud"),
    (r"R0|seed mirror", "R0 seed mirror gated on operator archive"),
    (r"session.?end|summar", "Session-end biography as persistent meta"),
]


def build_dossier(
    session_id: str,
    turns: dict[str, Any],
    narrative_md: str,
    *,
    mode: str = "heuristic",
    chat_path: Path | None = None,
) -> dict[str, Any]:
    users = turns.get("user") or []
    assts = turns.get("assistant") or []
    tools = turns.get("tools") or []
    reasons = turns.get("reasoning") or []
    blob = " ".join(users + assts + tools + reasons).lower()
    time_meta = load_session_meta(session_id, chat_path)

    themes = []
    theme_scores: dict[str, int] = {}
    for name, keys in THEME_KEYS.items():
        score = sum(blob.count(k) for k in keys)
        if score > 0:
            theme_scores[name] = score
            themes.append({"id": name, "score": score, "keys_hit": [k for k in keys if k in blob]})

    themes.sort(key=lambda x: -x["score"])

    metaphors = []
    for pat, meaning in METAPHOR_PATTERNS:
        if re.search(pat, blob, re.I):
            metaphors.append({"trigger": pat, "meaning": meaning})

    ideas = []
    for pat, meaning in IDEA_PATTERNS:
        if re.search(pat, blob, re.I):
            ideas.append({"trigger": pat, "idea": meaning})

    # Salient points: last user prompts + theme list
    salient = []
    for u in users[-12:]:
        u_clean = re.sub(r"</?user_query>", "", u).strip()
        if len(u_clean) > 20:
            salient.append({"type": "operator_ask", "text": u_clean[:500]})
    for t in themes[:6]:
        salient.append({"type": "theme", "text": f"{t['id']} (score {t['score']})"})

    files = sorted(
        set(re.findall(r"(?:[A-Za-z]:)?[^\s\"']+\.(?:md|py|json|yaml|yml|txt|pdf)", blob))
    )[:40]
    # normalize noise
    files = [f for f in files if "http" not in f and len(f) < 180][:25]

    src = str(turns.get("source") or "")
    if src == "mag_agent":
        transcript_hint = (
            "Full transcript: memory/agent_sessions/<seat>.json (Mag agent seat)."
        )
    else:
        transcript_hint = (
            "Full transcript remains in ~/.grok/sessions/.../chat_history.jsonl"
        )
    open_loops = [
        "Re-read this dossier before inventing new epics next session.",
        "Check scrum board if republic tickets were in flight.",
        transcript_hint,
        "Keep Steiniger as method inspiration — not a required AI persona to ship.",
    ]
    # Growing ingest DB: local copies + paths + tags + registry
    extra_refs = _build_bibliography(blob, files, narrative_md)
    bibliography = resolve_and_ingest(
        session_id=session_id,
        extra_refs=extra_refs,
        copy_local=True,
    )

    laymen = build_laymen_operations(themes, users, assts, metaphors, ideas, open_loops)
    frames = laymen.get("frames") or []
    frames_active = sum(1 for f in frames if f.get("active"))
    dur = duration_minutes(time_meta)
    knot = scalar_knot_proxy(
        themes=themes,
        tension_n=len(laymen.get("tension") or []),
        frames_active=frames_active,
        frames_total=max(len(frames), 1),
        residual_n=len(laymen.get("residual_bonds") or []),
        collapse_n=len(laymen.get("collapse_risks") or []),
        metaphor_n=len(metaphors),
        idea_n=len(ideas),
        user_n=len(users),
        tool_n=len(tools),
        duration_minutes=dur,
    )

    # provisional commit for chord ref
    provisional = content_commit(
        {
            "session_id": session_id,
            "time": time_meta,
            "scalar_knot": knot,
            "themes": themes,
        }
    )
    chord = build_chord_strike(
        session_id=session_id,
        users=users,
        assts=assts,
        tools=tools,
        themes=themes,
        tension=list(laymen.get("tension") or []),
        good_moves=list(laymen.get("good_moves") or []),
        open_loops=open_loops,
        dossier_commit=provisional.get("hex"),
    )

    dossier_core = {
        "schema": DOSSIER_SCHEMA,
        "session_id": session_id,
        # Seat that produced this workday (source-agnostic FILE). engine string stays legacy.
        "seat": {
            "source": turns.get("source") or "unknown",
            "provider": turns.get("provider"),
            "model": turns.get("model"),
            "local_session_id": turns.get("local_session_id"),
            "agnostic": True,
        },
        "time": time_meta,
        "scalar_knot": knot,
        "chord": chord,
        "tldr": chord.get("plain_english") or _tldr(themes, users, assts),
        "steiniger_laymen": laymen,
        "themes": themes,
        "salient_points": salient[:24],
        "metaphors": metaphors,
        "complex_ideas": ideas,
        "open_loops": open_loops,
        "stats": {
            "lines_scanned": turns.get("line_count"),
            "user_turns": len(users),
            "assistant_turns": len(assts),
            "tool_previews": len(tools),
        },
    }
    commit = content_commit(dossier_core)

    # session-specific chord markers (not external docs)
    bibliography = [
        {
            "id": "chord-commitment-this-session",
            "ref": chord.get("commitment_hash"),
            "title": chord.get("commitment_hash"),
            "note": "This session chord commitment (moves substance)",
            "kind": "chord_commitment",
            "tags": ["chord", "session", "commitment"],
            "url": None,
            "filename": None,
            "local_path": None,
            "where_to_find": f"session {session_id} · chord.commitment_hash in dossier JSON",
        },
        {
            "id": "strike-root-hash",
            "ref": f"Strike root {STRIKE_ROOT[:16]}…",
            "title": f"Strike framework root {STRIKE_ROOT[:16]}…",
            "note": "Public strike / marble-OS seed",
            "kind": "framework_seed",
            "tags": ["strike", "root"],
            "url": "https://x.com/NachoQuixotic/status/2071204776293908905",
            "filename": None,
            "local_path": None,
            "where_to_find": f"hash={STRIKE_ROOT} · see skill-strike-chord local copy under memory/ingest",
        },
    ] + bibliography

    dossier = {
        **dossier_core,
        "content_commit": commit,
        "generated_at": (time_meta.get("dossier_generated_at") or {}).get("iso_full")
        or datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "inspiration": {
            "author": "Matthew P. Steiniger",
            "academia": "https://independent.academia.edu/MatthewSteiniger",
            "site": "https://slashreboot.com",
            "orcid": "0009-0000-6069-4989",
            "license": "CC-BY-4.0 attribute when reusing methods",
            "use": "operational lens + math proxies for untangling engine; not physics dogma",
            "attribution_blurb": laymen_attribution_block(),
            "strike_chord": {
                "skill": "~/.grok/skills/strike-chord/SKILL.md",
                "root": STRIKE_ROOT,
                "structure": "plain→impact→rope→loops→moves→commitment→self-audit",
                "charts": "money|secrets|fracture|personal_rope",
            },
        },
        "scan": {
            "human": (
                "PDF: Chord struck → personal impact → rope → loops → moves → "
                "math anchors → charts → biblio"
            ),
            "machine": (
                f"schema={DOSSIER_SCHEMA}; chord.*; time.*.iso_minute; "
                "scalar_knot.*; content_commit.hex; verkle_knot"
            ),
        },
        "operator_prompts": [{"text": u[:600]} for u in users[-20:]],
        "assistant_outcomes": [{"text": a[:600]} for a in assts[-15:]],
        "reasoning_snippets": [{"text": r[:400]} for r in reasons[-12:]],
        "paths_touched": files,
        "bibliography": bibliography,
        "ingest": {
            "registry": str(ROOT / "memory" / "ingest" / "registry.jsonl"),
            "catalog": str(ROOT / "memory" / "ingest" / "catalog.json"),
            "local_docs": str(ROOT / "memory" / "ingest" / "local" / "docs"),
            "local_papers": str(ROOT / "memory" / "ingest" / "local" / "papers"),
            "local_web": str(ROOT / "memory" / "ingest" / "local" / "web"),
        },
        "narrative_md_path": str(BIO_DIR / f"{session_id}.md"),
        "engine": "untangling+strike_chord",
    }
    return dossier


def _tldr(themes: list[dict], users: list[str], assts: list[str]) -> str:
    top = ", ".join(t["id"] for t in themes[:4]) or "general session"
    last = ""
    if users:
        last = re.sub(r"</?user_query>", "", users[-1]).strip()[:180]
    return f"Session focused on: {top}. Latest operator push: {last or '—'}"


def _build_bibliography(blob: str, files: list[str], narrative: str) -> list[dict[str, str]]:
    bib: list[dict[str, str]] = []
    anchors = [
        ("mycelial-republic/docs/CONSTITUTION.md", "Lessig-style constitution (fork equality, tiers)"),
        ("mycelial-republic/docs/SCRUM.md", "Agent/PO scrum process"),
        ("mycelial-republic/docs/AGENT_ROADMAP.md", "R0–R4 DAG and agent roles"),
        ("mycelial-republic/docs/STEINIGER_INGEST_LOG.md", "Local Steiniger scaffold ingest log"),
        ("local_sovereign_agent/README.md", "Mag + watch + harness instrument"),
        (
            "sovereign-mirror-scaffold/docs/STEINIGER_PAPERS.md",
            "Paper→code map for Steiniger stack (instrument)",
        ),
        (
            "sovereign-mirror-scaffold/docs/DIAGNOSTIC_ZEITGEIST.md",
            "Zeitgeist diagnostic (Lessig × Steiniger × Strike)",
        ),
        ("sovereign-mirror-scaffold/docs/MANIFESTO.md", "Multi-frame agency manifesto"),
        ("~/.grok/skills/strike-chord/SKILL.md", "Strike-the-chord output contract"),
        ("~/.grok/skills/operator-quixote/SKILL.md", "Default operator rules"),
    ]
    for path, note in anchors:
        key = path.split("/")[-1].lower().replace(".md", "")
        if (
            key[:6] in blob
            or "steiniger" in blob
            or path.split("/")[0].replace("~.", "") in blob
            or any(path.split("/")[-1].lower() in f.lower() for f in files)
            or True  # always list local anchors for computer scan completeness
        ):
            bib.append({"ref": path, "note": note, "kind": "local_doc", "url": ""})

    if "mirror" in blob or "chord" in blob or True:
        bib.append(
            {
                "ref": "strike-the-chord / sovereign mirror protocol (operator)",
                "note": "Truth-only multi-frame analysis; personal impact; no throne",
                "kind": "framework",
                "url": "",
            }
        )

    for url in re.findall(r"https?://[^\s\)\"']+", narrative + " " + blob)[:12]:
        bib.append(
            {"ref": url, "note": "Mentioned in session extract", "kind": "url", "url": url}
        )

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for b in bib:
        if b["ref"] in seen:
            continue
        seen.add(b["ref"])
        out.append(b)
    return out[:40]


def write_dossier_assets(session_id: str, dossier: dict[str, Any]) -> dict[str, str]:
    """Theme chart for human export (PDF/visual). Not part of lean DNA."""
    assets_dir = BIO_DIR / session_id / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return paths

    themes = dossier.get("themes") or []
    if not themes:
        return paths

    fig, ax = plt.subplots(figsize=(6.5, 2.8), dpi=150)
    labels = [t["id"] for t in themes[:8]]
    scores = [t["score"] for t in themes[:8]]
    ax.barh(labels[::-1], scores[::-1], color="#1a365d", height=0.65)
    ax.set_xlabel("weight", fontsize=8, color="#555555")
    ax.tick_params(axis="both", labelsize=8, colors="#333333")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    p = assets_dir / "themes.png"
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    paths["themes_chart"] = str(p)
    return paths


def render_pdf(session_id: str, dossier: dict[str, Any], assets: dict[str, str]) -> Path:
    """Render PDF into derived/ only (on-demand export layer)."""
    from mag.pdf_layout import render_clean_pdf  # optional dep: reportlab (lazy)
    from mag.registry import DERIVED_DIR, derived_path

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = derived_path(session_id, "pdf")
    return render_clean_pdf(session_id, dossier, assets, pdf_path)


def write_session_pack(
    session_id: str,
    turns: dict[str, Any],
    narrative_md: str,
    *,
    mode: str = "heuristic",
    use_llm: bool = True,
    chat_path: Path | None = None,
    amend: bool = False,
    write_pdf: bool = False,
    write_assets: bool | None = None,
) -> dict[str, Any]:
    """Build residual DNA + chain leaf. PDF/assets only when requested (export layer)."""
    BIO_DIR.mkdir(parents=True, exist_ok=True)
    dossier = build_dossier(
        session_id, turns, narrative_md, mode=mode, chat_path=chat_path
    )
    if amend:
        dossier["amended_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if use_llm and mode != "heuristic_only":
        dossier = _maybe_llm_enrich(dossier, narrative_md, turns)
    sl = dossier.get("steiniger_laymen") or {}
    for key in ("tension", "good_moves", "residual_bonds", "collapse_risks"):
        if key in sl and isinstance(sl[key], list):
            cleaned = []
            for x in sl[key]:
                if isinstance(x, str) and x.strip() and not x.strip().startswith("{"):
                    cleaned.append(x.strip())
                elif isinstance(x, dict):
                    cleaned.append(str(next(iter(x.values()), x))[:400])
            sl[key] = cleaned
    dossier["steiniger_laymen"] = sl

    # recompute commit over stable analysis fields
    from mag.knot_math import content_commit

    dossier["content_commit"] = content_commit(
        {
            "session_id": session_id,
            "time": dossier.get("time"),
            "scalar_knot": dossier.get("scalar_knot"),
            "tldr": dossier.get("tldr"),
            "steiniger_laymen": dossier.get("steiniger_laymen"),
            "themes": dossier.get("themes"),
        }
    )

    # timeline ledger — one row per session (upsert)
    ledger = BIO_DIR / "knot_timeline.jsonl"
    t = dossier.get("time") or {}
    sk = dossier.get("scalar_knot") or {}
    tl_row = {
        "session_id": session_id,
        "start_minute": (t.get("created_at") or {}).get("iso_minute"),
        "end_minute": (t.get("updated_at") or {}).get("iso_minute"),
        "start_unix_minute": (t.get("created_at") or {}).get("unix_minute"),
        "end_unix_minute": (t.get("updated_at") or {}).get("unix_minute"),
        "generated_minute": (t.get("dossier_generated_at") or {}).get("iso_minute"),
        "tension_index": sk.get("tension_index"),
        "residual_weight": sk.get("residual_weight"),
        "Q_proxy": sk.get("Q_proxy"),
        "gap_proxy": sk.get("gap_proxy"),
        "lambda2_proxy": sk.get("lambda2_proxy"),
        "dirichlet_energy_proxy": sk.get("dirichlet_energy_proxy"),
        "duration_minutes": sk.get("duration_minutes"),
        "theme_vector": (sk.get("theme_vector") or {}).get("normalized"),
        "commit": (dossier.get("content_commit") or {}).get("hex"),
        "amended": amend,
    }
    _upsert_jsonl(ledger, "session_id", session_id, tl_row)

    try:
        from mag.session_card import attach_card_to_dossier

        attach_card_to_dossier(dossier, narrative_md)
    except Exception:
        pass

    # Assets (charts) are interpretation — only when exporting PDF/visual
    do_assets = write_assets if write_assets is not None else bool(write_pdf)
    assets: dict[str, str] = {}
    if do_assets:
        assets = write_dossier_assets(session_id, dossier)
    dossier["assets"] = assets

    pdf_path = None
    pdf_error = None
    if write_pdf:
        try:
            if not assets:
                assets = write_dossier_assets(session_id, dossier)
                dossier["assets"] = assets
            pdf_path = render_pdf(session_id, dossier, assets)
            try:
                from mag.registry import write_derived_pdf_bytes

                # derived already written by render_pdf; refresh latest pointer only
                write_derived_pdf_bytes(
                    session_id, pdf_path.read_bytes(), also_flat=False
                )
            except Exception:
                pass
        except Exception as e:
            pdf_error = str(e)
    else:
        from mag.registry import find_derived

        prior = find_derived(session_id, "pdf")
        if prior is not None:
            pdf_path = prior

    # Living Verkle-knot record (filename-addressed topic evolution)
    verkle: dict[str, Any] = {}
    try:
        from mag.verkle_knot import append_verkle_knot

        verkle = append_verkle_knot(
            dossier, pdf_path=str(pdf_path) if pdf_path else None
        )
        dossier["verkle_knot"] = {
            "filename": verkle.get("filename"),
            "leaf_hash": verkle.get("leaf_hash"),
            "verkle_root": verkle.get("verkle_root"),
            "n_leaves": verkle.get("n_leaves"),
            "path": verkle.get("path"),
        }
    except Exception as e:
        verkle = {"ok": False, "error": str(e)}

    # Lean residual + hot registry (canonical)
    residual_meta: dict[str, Any] = {}
    try:
        from mag.registry import publish_residual

        residual_meta = publish_residual(
            session_id,
            dossier,
            narrative_md=narrative_md,
            write_md=True,
        )
        from mag.registry import residual_path as _rp

        json_path = str(_rp(session_id))
    except Exception as e:
        # fallback flat write
        json_path = BIO_DIR / f"{session_id}.dossier.json"
        json_path.write_text(json.dumps(dossier, indent=2, default=str), encoding="utf-8")
        (BIO_DIR / "latest.dossier.json").write_text(
            json.dumps(dossier, indent=2, default=str), encoding="utf-8"
        )
        json_path = str(json_path)
        residual_meta = {"error": str(e)[:200]}

    return {
        "dossier_json": json_path,
        "residual": residual_meta,
        "pdf": str(pdf_path) if pdf_path else None,
        "pdf_error": pdf_error,
        "assets": assets,
        "theme_count": len(dossier.get("themes") or []),
        "start_minute": (dossier.get("time") or {}).get("created_at", {}).get(
            "iso_minute"
        ),
        "end_minute": (dossier.get("time") or {}).get("updated_at", {}).get(
            "iso_minute"
        ),
        "commit": (dossier.get("content_commit") or {}).get("hex"),
        "knot_timeline": str(ledger),
        "verkle": verkle,
    }


def _maybe_llm_enrich(dossier: dict[str, Any], narrative: str, turns: dict[str, Any]) -> dict[str, Any]:
    """Ask local model for extra metaphors/ideas when available."""
    try:
        from llm import chat, extract_json
    except Exception:
        return dossier
    if len(narrative) < 200:
        return dossier
    try:
        raw = chat(
            "worker",
            "Extract structured session insights as JSON only. Laymen English. "
            "Steiniger-inspired ops OK as plain tools (tension, frames, core, residual bonds) "
            "— never claim physics truth or Saelis identity.",
            f"""From this session narrative and prompts, extract JSON:
{{"extra_metaphors":[{{"meaning":"plain language metaphor"}}],
 "extra_ideas":[{{"idea":"complex idea in plain English"}}],
 "extra_salient":[{{"text":"..."}}],
 "extra_tension":["what was under pressure"],
 "extra_good_moves":["lower stress + raise clarity"],
 "bibliography_notes":[{{"ref":"...","note":"..."}}]}}

Narrative:
{narrative[:5000]}

User asks:
{chr(10).join((turns.get('user') or [])[-8:])}
""",
            temperature=0.2,
        )
        data = extract_json(raw) or {}
        for m in data.get("extra_metaphors") or []:
            if m.get("meaning"):
                dossier.setdefault("metaphors", []).append(
                    {"trigger": "llm", "meaning": str(m["meaning"])[:300]}
                )
        for i in data.get("extra_ideas") or []:
            if i.get("idea"):
                dossier.setdefault("complex_ideas", []).append(
                    {"trigger": "llm", "idea": str(i["idea"])[:400]}
                )
        for s in data.get("extra_salient") or []:
            if s.get("text"):
                dossier.setdefault("salient_points", []).append(
                    {"type": "llm_salient", "text": str(s["text"])[:500]}
                )
        for b in data.get("bibliography_notes") or []:
            if b.get("ref"):
                dossier.setdefault("bibliography", []).append(
                    {
                        "ref": str(b["ref"])[:200],
                        "note": str(b.get("note") or "")[:300],
                        "kind": "llm",
                        "url": "",
                    }
                )
        sl = dossier.setdefault("steiniger_laymen", {})
        for t in data.get("extra_tension") or []:
            if t:
                sl.setdefault("tension", []).append(str(t)[:400])
        for m in data.get("extra_good_moves") or []:
            if m:
                sl.setdefault("good_moves", []).append(str(m)[:400])
    except Exception:
        pass
    return dossier
