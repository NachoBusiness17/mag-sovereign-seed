"""Research pack — scrape + clean ask PDF for multi-model routing.

Local-first information routing:
  1. Operator ask + success criteria (fidelity for lesser models)
  2. Fetch public URLs → local text copies (ingest)
  3. Write JSON + PDF pack (full ask, sources, rubric)
  4. Hand pack to Ollama / remote / Grok TUI — not raw chat history

Tier: URLs are treated as T2 public. Never put secrets in the ask field.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from config import ROOT

PACKS = ROOT / "memory" / "research_packs"
SCHEMA = "research_pack.v1"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "tr"):
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        t = data.strip()
        if t:
            self._chunks.append(t + " ")

    def text(self) -> str:
        raw = "".join(self._chunks)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _slug(s: str, n: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "pack").lower()).strip("-")
    return (s or "pack")[:n]


def _fetch_url(url: str, timeout: float = 25.0) -> dict[str, Any]:
    import httpx

    headers = {
        "User-Agent": "MagResearchPack/1.0 (+local sovereign agent; research)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            r = client.get(url)
            ctype = (r.headers.get("content-type") or "").lower()
            raw = r.content
            text = ""
            if "html" in ctype or url.rstrip("/").endswith((".html", ".htm")) or b"<html" in raw[:500].lower():
                parser = _TextExtractor()
                try:
                    parser.feed(r.text)
                    text = parser.text()
                except Exception:
                    text = re.sub(r"<[^>]+>", " ", r.text)
                    text = re.sub(r"\s+", " ", text).strip()
            elif "pdf" in ctype:
                text = f"[PDF binary {len(raw)} bytes — stored locally; text extract not run]"
            else:
                text = r.text[:50000] if r.encoding else raw[:50000].decode("utf-8", errors="replace")
            return {
                "ok": r.status_code < 400,
                "url": str(r.url),
                "status_code": r.status_code,
                "content_type": ctype,
                "text": text[:80000],
                "bytes": len(raw),
                "raw": raw if r.status_code < 400 else None,
            }
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e), "text": "", "raw": None}


def _save_web_copy(url: str, raw: bytes | None, text: str) -> dict[str, str]:
    from mag.ingest_registry import LOCAL_WEB, resolve_and_ingest

    LOCAL_WEB.mkdir(parents=True, exist_ok=True)
    host = urlparse(url).netloc.replace(":", "_") or "web"
    h = hashlib.sha256(url.encode()).hexdigest()[:12]
    html_path = LOCAL_WEB / f"{host}-{h}.html"
    txt_path = LOCAL_WEB / f"{host}-{h}.txt"
    if raw:
        html_path.write_bytes(raw[:2_000_000])
    txt_path.write_text(text[:100000], encoding="utf-8", errors="replace")
    try:
        resolve_and_ingest(
            title=url,
            url=url,
            local_path=str(txt_path),
            tags=["research_pack", "web", "t2"],
            kind="web",
        )
    except Exception:
        pass
    return {"html": str(html_path) if raw else "", "text": str(txt_path)}


def build_research_pack(
    ask: str,
    *,
    urls: list[str] | None = None,
    success_criteria: list[str] | None = None,
    constraints: list[str] | None = None,
    expected_format: str = "",
    title: str = "",
    elevate_to: str = "auto",
) -> dict[str, Any]:
    """Build research pack dict + write JSON/PDF under memory/research_packs/."""
    ask = (ask or "").strip()
    if not ask:
        return {"ok": False, "error": "empty ask"}

    urls = [u.strip() for u in (urls or []) if u.strip()]
    criteria = success_criteria or [
        "Answer the ask directly; no filler.",
        "Cite sources by URL when using scraped text.",
        "Flag uncertainty instead of inventing facts.",
        "Stay within constraints; do not request private data.",
    ]
    constraints = constraints or [
        "Public/T2 material only for remote models.",
        "Do not expand scope beyond the ask.",
        "Prefer shorter correct answers over long speculative ones.",
    ]
    expected_format = expected_format or (
        "1) Direct answer  2) Evidence bullets with source URLs  "
        "3) Open questions / gaps  4) Recommended next local move"
    )

    sources: list[dict[str, Any]] = []
    for url in urls[:12]:
        fetched = _fetch_url(url)
        paths = {"html": "", "text": ""}
        if fetched.get("ok") and (fetched.get("raw") is not None or fetched.get("text")):
            paths = _save_web_copy(url, fetched.get("raw"), fetched.get("text") or "")
        excerpt = (fetched.get("text") or "")[:4000]
        sources.append(
            {
                "url": url,
                "final_url": fetched.get("url") or url,
                "ok": bool(fetched.get("ok")),
                "status_code": fetched.get("status_code"),
                "error": fetched.get("error"),
                "excerpt": excerpt,
                "local": paths,
                "chars": len(fetched.get("text") or ""),
            }
        )

    ts = datetime.now(timezone.utc)
    rid = ts.strftime("%Y%m%dT%H%M%SZ") + "_" + _slug(title or ask)
    pack = {
        "schema": SCHEMA,
        "id": rid,
        "created_at": ts.isoformat().replace("+00:00", "Z"),
        "title": title or ask[:80],
        "ask": ask,
        "success_criteria": criteria,
        "constraints": constraints,
        "expected_format": expected_format,
        "elevate_to": elevate_to,  # auto | local | remote | grok_tui
        "sources": sources,
        "routing": {
            "intent": (
                "Lesser models execute against this pack only. "
                "Grok elevates only when fidelity fails or task is hard_code."
            ),
            "local_first": True,
            "token_rule": "Send this pack (truncated sources) — not full chat history.",
        },
        "for_lesser_models": {
            "system": (
                "You are a specialist given a research pack. "
                "Use only the ask, criteria, constraints, and source excerpts. "
                "Cite URLs. Be concise. No flattery."
            ),
            "user_template": "See pack.ask + pack.sources[].excerpt + criteria.",
        },
    }

    PACKS.mkdir(parents=True, exist_ok=True)
    json_path = PACKS / f"{rid}.json"
    latest_json = PACKS / "latest.json"
    raw = json.dumps(pack, indent=2, default=str)
    json_path.write_text(raw, encoding="utf-8")
    latest_json.write_text(raw, encoding="utf-8")

    pdf_path = None
    pdf_error = None
    try:
        pdf_path = str(_write_pdf(pack, PACKS / f"{rid}.pdf"))
        (PACKS / "latest.pdf").write_bytes(Path(pdf_path).read_bytes())
    except Exception as e:
        pdf_error = str(e)

    # compact prompt blob for models
    prompt_path = PACKS / f"{rid}.prompt.txt"
    prompt_path.write_text(_pack_to_prompt(pack), encoding="utf-8")
    (PACKS / "latest.prompt.txt").write_text(_pack_to_prompt(pack), encoding="utf-8")

    # DAIMON steal: freeze protocol + empty execution state BEFORE any answer run
    freeze = _write_freeze_bag(pack, sources)
    pack["freeze"] = freeze
    raw = json.dumps(pack, indent=2, default=str)
    json_path.write_text(raw, encoding="utf-8")
    latest_json.write_text(raw, encoding="utf-8")

    return {
        "ok": True,
        "id": rid,
        "json": str(json_path),
        "pdf": pdf_path,
        "pdf_error": pdf_error,
        "prompt": str(prompt_path),
        "n_sources": len(sources),
        "sources_ok": sum(1 for s in sources if s.get("ok")),
        "elevate_to": elevate_to,
        "protocol": freeze.get("protocol"),
        "execution_state": freeze.get("execution_state"),
        "note": "Frozen first: protocol + empty execution_state live before --run answers.",
    }


def _write_freeze_bag(pack: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, str]:
    """Prospective freeze bag (DAIMON honesty steal): protocol before answers."""
    rid = str(pack.get("id") or "pack")
    ts = pack.get("created_at") or datetime.now(timezone.utc).isoformat()
    source_hashes = []
    for s in sources:
        excerpt = s.get("excerpt") or ""
        h = hashlib.sha256(excerpt.encode("utf-8", errors="replace")).hexdigest()[:16]
        source_hashes.append(
            {
                "url": s.get("url"),
                "ok": s.get("ok"),
                "excerpt_sha256_16": h,
                "chars": s.get("chars"),
            }
        )
    protocol = {
        "schema": "mag_research_protocol.v1",
        "commitment": "freeze-before-run-daimon-steal",
        "pack_id": rid,
        "frozen_at": ts,
        "ask": pack.get("ask"),
        "title": pack.get("title"),
        "success_criteria": pack.get("success_criteria"),
        "constraints": pack.get("constraints"),
        "expected_format": pack.get("expected_format"),
        "elevate_to": pack.get("elevate_to"),
        "sources": source_hashes,
        "answers": None,
        "law": "Protocol and empty execution_state must exist before any model answer.",
    }
    execution_state = {
        "schema": "mag_research_execution_state.v1",
        "pack_id": rid,
        "status": "frozen_pending_run",
        "started_at": None,
        "finished_at": None,
        "attempts": [],
        "errors": [],
        "answer_paths": [],
        "note": "Empty before run — filled by run_pack.",
    }
    p_path = PACKS / f"{rid}.protocol.json"
    e_path = PACKS / f"{rid}.execution_state.json"
    p_path.write_text(json.dumps(protocol, indent=2, default=str), encoding="utf-8")
    e_path.write_text(json.dumps(execution_state, indent=2, default=str), encoding="utf-8")
    (PACKS / "latest.protocol.json").write_text(p_path.read_text(encoding="utf-8"), encoding="utf-8")
    (PACKS / "latest.execution_state.json").write_text(
        e_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return {
        "protocol": str(p_path),
        "execution_state": str(e_path),
    }


def _complete_execution_state(pack_id: str, run_out: dict[str, Any]) -> None:
    """Stamp execution_state after a run (audit bag)."""
    e_path = PACKS / f"{pack_id}.execution_state.json"
    prev: dict[str, Any] = {}
    if e_path.is_file():
        try:
            prev = json.loads(e_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            prev = {}
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    attempts = list(prev.get("attempts") or [])
    attempts.append(
        {
            "ts": now,
            "seat": run_out.get("seat"),
            "provider": run_out.get("provider"),
            "ok": bool(run_out.get("ok") and not run_out.get("local_error")),
            "fidelity": (run_out.get("fidelity") or {}).get("recommend"),
            "answer_path": run_out.get("answer_path"),
            "error": run_out.get("local_error") or (run_out.get("result") or {}).get("error"),
        }
    )
    prev.update(
        {
            "schema": "mag_research_execution_state.v1",
            "pack_id": pack_id,
            "status": "completed" if run_out.get("ok") else "failed",
            "started_at": prev.get("started_at") or now,
            "finished_at": now,
            "attempts": attempts,
            "answer_paths": [a.get("answer_path") for a in attempts if a.get("answer_path")],
            "errors": [a.get("error") for a in attempts if a.get("error")],
            "note": "Run complete — compare against frozen protocol; operator is final judge.",
        }
    )
    e_path.write_text(json.dumps(prev, indent=2, default=str), encoding="utf-8")
    (PACKS / "latest.execution_state.json").write_text(
        e_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    # minimal errata stub if fidelity weak
    fid = run_out.get("fidelity") or {}
    if fid.get("recommend") and fid.get("recommend") != "hold":
        errata = {
            "schema": "mag_research_errata.v1",
            "pack_id": pack_id,
            "ts": now,
            "items": [
                {
                    "kind": "fidelity_weak",
                    "detail": "Heuristic fidelity not PASS — spot-check or elevate; do not treat answer as DNA.",
                    "fidelity": fid,
                }
            ],
        }
        ep = PACKS / f"{pack_id}.errata.json"
        ep.write_text(json.dumps(errata, indent=2, default=str), encoding="utf-8")
        (PACKS / "latest.errata.json").write_text(ep.read_text(encoding="utf-8"), encoding="utf-8")


def _pack_to_prompt(pack: dict[str, Any], *, max_source_chars: int = 2500) -> str:
    lines = [
        f"# Research pack {pack.get('id')}",
        "",
        "## ASK",
        pack.get("ask") or "",
        "",
        "## SUCCESS CRITERIA (fidelity bar)",
    ]
    for c in pack.get("success_criteria") or []:
        lines.append(f"- {c}")
    lines += ["", "## CONSTRAINTS"]
    for c in pack.get("constraints") or []:
        lines.append(f"- {c}")
    lines += ["", f"## EXPECTED FORMAT\n{pack.get('expected_format') or ''}", "", "## SOURCES"]
    for i, s in enumerate(pack.get("sources") or [], 1):
        lines.append(f"\n### Source {i}: {s.get('url')}")
        if not s.get("ok"):
            lines.append(f"FETCH FAILED: {s.get('error') or s.get('status_code')}")
            continue
        ex = (s.get("excerpt") or "")[:max_source_chars]
        lines.append(ex)
    lines += [
        "",
        "## YOUR JOB",
        "Answer the ASK using sources. Meet SUCCESS CRITERIA. Obey CONSTRAINTS. Use EXPECTED FORMAT.",
    ]
    return "\n".join(lines)


def _write_pdf(pack: dict[str, Any], out: Path) -> Path:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    out.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1m", parent=styles["Heading1"], fontSize=14, spaceAfter=8)
    h2 = ParagraphStyle("H2m", parent=styles["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("Bodym", parent=styles["BodyText"], fontSize=9, leading=12)
    mono = ParagraphStyle("Monom", parent=styles["Code"], fontSize=8, leading=10)

    def esc(s: str) -> str:
        return (
            (s or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    story = []
    story.append(Paragraph(esc(f"Research pack · {pack.get('id')}"), h1))
    story.append(Paragraph(esc(f"Created {pack.get('created_at')} · local-first multi-model routing"), body))
    story.append(Spacer(1, 8))
    story.append(Paragraph("ASK", h2))
    story.append(Paragraph(esc(pack.get("ask") or ""), body))
    story.append(Paragraph("SUCCESS CRITERIA (what lesser models must deliver)", h2))
    for c in pack.get("success_criteria") or []:
        story.append(Paragraph(esc(f"• {c}"), body))
    story.append(Paragraph("CONSTRAINTS", h2))
    for c in pack.get("constraints") or []:
        story.append(Paragraph(esc(f"• {c}"), body))
    story.append(Paragraph("EXPECTED FORMAT", h2))
    story.append(Paragraph(esc(pack.get("expected_format") or ""), body))
    story.append(Paragraph("SOURCES", h2))
    for i, s in enumerate(pack.get("sources") or [], 1):
        story.append(Paragraph(esc(f"{i}. {s.get('url')}  ok={s.get('ok')}"), body))
        if s.get("local", {}).get("text"):
            story.append(Paragraph(esc(f"local: {s['local']['text']}"), mono))
        ex = (s.get("excerpt") or s.get("error") or "")[:1500]
        if ex:
            story.append(Paragraph(esc(ex[:1500]), mono))
        story.append(Spacer(1, 6))
    story.append(Paragraph("ROUTING NOTE", h2))
    story.append(
        Paragraph(
            esc(
                "Lesser models: execute against this pack only. "
                "Grok: elevate only if local/remote fidelity fails or task is hard architecture."
            ),
            body,
        )
    )
    doc.build(story)
    return out


def load_pack(path: str | Path | None = None) -> dict[str, Any] | None:
    p = Path(path) if path else PACKS / "latest.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def pack_body_excerpts(pack: dict[str, Any], *, min_chars: int = 500) -> list[str]:
    """Return usable source bodies (excerpt/text) from pack when fetch was rich enough."""
    out: list[str] = []
    for s in pack.get("sources") or []:
        if not s.get("ok"):
            continue
        body = (s.get("excerpt") or s.get("text") or "").strip()
        chars = int(s.get("chars") or len(body) or 0)
        if chars >= min_chars and len(body) >= min(200, min_chars // 2):
            out.append(body)
    return out


def answer_grounded_in_pack(
    answer: str,
    pack: dict[str, Any],
    *,
    min_chars: int = 500,
    min_token_hits: int = 3,
) -> dict[str, Any]:
    """
    Claims-vs-excerpt check (v0).

    If pack has rich fetch bodies: require answer to share content tokens with them
    (or contain a short quoted span from the excerpt). If no rich body, grounded is
    N/A (not a free pass for inventing — lattice_loop treats fetch-all-fail separately).
    """
    bodies = pack_body_excerpts(pack, min_chars=min_chars)
    if not bodies:
        return {
            "schema": "grounding_check.v1",
            "applicable": False,
            "grounded": None,
            "token_hits": 0,
            "quote_hit": False,
            "note": "no rich pack body — grounding N/A",
        }
    ans = answer or ""
    ans_l = ans.lower()
    # token pool from bodies (skip stop-ish short words)
    stop = {
        "that", "this", "with", "from", "have", "were", "been", "their", "there",
        "which", "would", "could", "about", "into", "than", "then", "them", "they",
        "will", "your", "what", "when", "where", "while", "also", "more", "most",
        "some", "such", "only", "other", "over", "after", "before", "between",
        "http", "https", "www", "html", "home", "page", "said", "says",
    }
    body_tokens: set[str] = set()
    for b in bodies:
        for w in re.findall(r"[a-z0-9]{5,}", b.lower()):
            if w not in stop:
                body_tokens.add(w)
    ans_tokens = set(re.findall(r"[a-z0-9]{5,}", ans_l))
    hits = len(body_tokens & ans_tokens)
    # quoted span: any 24+ char window from body appears in answer (normalized space)
    quote_hit = False
    for b in bodies:
        compact = re.sub(r"\s+", " ", b).strip()
        if len(compact) < 24:
            continue
        # sample a few windows from early body (title-ish + mid)
        candidates = [compact[:80], compact[40:120], compact[100:180]]
        for c in candidates:
            c = c.strip()
            if len(c) >= 24 and c.lower() in ans_l:
                quote_hit = True
                break
        if quote_hit:
            break
    grounded = hits >= min_token_hits or quote_hit
    return {
        "schema": "grounding_check.v1",
        "applicable": True,
        "grounded": grounded,
        "token_hits": hits,
        "quote_hit": quote_hit,
        "body_token_n": len(body_tokens),
        "note": "token overlap and/or excerpt quote vs pack body",
    }


def score_fidelity(answer: str, pack: dict[str, Any]) -> dict[str, Any]:
    """Heuristic scorecard vs success_criteria — not a moral grade."""
    text = (answer or "").lower()
    criteria = list(pack.get("success_criteria") or [])
    urls = [str(s.get("url") or "") for s in (pack.get("sources") or []) if s.get("url")]
    checks: list[dict[str, Any]] = []
    for c in criteria:
        cl = c.lower()
        # keyword overlap heuristic
        words = [w for w in re.findall(r"[a-z0-9]{4,}", cl) if w not in {
            "that", "this", "with", "from", "your", "have", "must", "should", "every", "claim"
        }]
        hit = sum(1 for w in words[:8] if w in text)
        ok = hit >= max(1, min(2, len(words) // 3)) if words else len(text) > 40
        # special: cite/url criteria
        if any(k in cl for k in ("cite", "url", "source")):
            ok = bool(urls) and (
                any(u.lower() in text for u in urls if u)
                or "http" in text
                or "source" in text
            )
        if "bullet" in cl or "3 " in cl or "three" in cl:
            bullets = len(re.findall(r"(?m)^\s*[-*•]|\d+\.", answer or ""))
            ok = bullets >= 2
        checks.append({"criterion": c, "ok": ok, "note": "heuristic keyword/structure check"})

    # Fidelity v2: claims-vs-excerpt when pack has rich body
    grounding = answer_grounded_in_pack(answer, pack)
    if grounding.get("applicable"):
        checks.append(
            {
                "criterion": "Ground answer in pack excerpt (token/quote bind).",
                "ok": bool(grounding.get("grounded")),
                "note": f"grounding_check hits={grounding.get('token_hits')} quote={grounding.get('quote_hit')}",
            }
        )
    # All sources failed / thin: do not treat as grounded research
    sources = list(pack.get("sources") or [])
    if sources:
        any_ok_rich = bool(pack_body_excerpts(pack, min_chars=200))
        any_attempt = True
        if any_attempt and not any_ok_rich:
            # thin or failed fetches — require honesty markers rather than free pass
            honest = any(
                k in text
                for k in (
                    "fetch failed",
                    "could not fetch",
                    "no content",
                    "403",
                    "404",
                    "unable to access",
                    "paywall",
                    "no usable",
                )
            )
            checks.append(
                {
                    "criterion": "Admit thin/failed fetch — do not invent page body.",
                    "ok": honest,
                    "note": "no rich pack body",
                }
            )

    n_ok = sum(1 for c in checks if c["ok"])
    n = max(1, len(checks))
    ratio = n_ok / n
    recommend = "hold" if ratio >= 0.67 else "elevate_or_retry"
    ungrounded = bool(grounding.get("applicable") and not grounding.get("grounded"))
    if sources and not pack_body_excerpts(pack, min_chars=200):
        # failed/thin sources + no honesty → ungrounded for queue gates
        if not any(
            k in text
            for k in (
                "fetch failed",
                "could not fetch",
                "no content",
                "403",
                "404",
                "unable to access",
                "paywall",
                "no usable",
            )
        ):
            ungrounded = True
    return {
        "schema": "fidelity_scorecard.v1",
        "passed": n_ok,
        "total": len(checks),
        "ratio": round(ratio, 3),
        "recommend": recommend,
        "checks": checks,
        "grounding": grounding,
        "ungrounded": ungrounded,
        "note": "Heuristic + grounding v0 — operator is final judge of fidelity.",
    }


def run_pack(
    pack: dict[str, Any] | None = None,
    *,
    seat: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Execute pack on local worker or remote; or return elevate payload for Grok."""
    pack = pack or load_pack()
    if not pack:
        return {"ok": False, "error": "no research pack"}

    prompt = _pack_to_prompt(pack)
    elev = seat or pack.get("elevate_to") or "auto"
    if elev == "auto":
        # default: try local worker first
        elev = "local"

    pack_id = str(pack.get("id") or "")
    # Ensure freeze bag exists even for packs built before this steal
    if pack_id and not (PACKS / f"{pack_id}.protocol.json").is_file():
        _write_freeze_bag(pack, list(pack.get("sources") or []))

    out: dict[str, Any] = {
        "ok": True,
        "pack_id": pack_id,
        "seat": elev,
        "prompt_chars": len(prompt),
    }

    if elev in ("grok_tui", "grok"):
        out["seat"] = "grok_tui"
        out["hint"] = "Elevate to Grok TUI with this pack only (PDF + prompt)."
        out["prompt"] = prompt[:12000]
        out["pdf"] = str(PACKS / f"{pack.get('id')}.pdf")
        out["json"] = str(PACKS / f"{pack.get('id')}.json")
        out["elevate_summary"] = {
            "ask": (pack.get("ask") or "")[:400],
            "criteria": pack.get("success_criteria"),
            "sources_ok": sum(1 for s in (pack.get("sources") or []) if s.get("ok")),
            "pdf": out["pdf"],
            "prompt_file": str(PACKS / f"{pack.get('id')}.prompt.txt"),
        }
        if pack_id:
            _complete_execution_state(pack_id, {**out, "ok": True})
        return out

    system = (pack.get("for_lesser_models") or {}).get("system") or (
        "Execute the research pack. Cite sources. Meet criteria."
    )

    answer_text = ""
    if elev == "local" or (not provider and elev == "auto"):
        from llm import chat

        try:
            text = chat("worker", system, prompt[:14000], temperature=0.2)
            answer_text = text
            out["provider"] = "ollama"
            out["model"] = "worker"
            out["text"] = text
            score = score_fidelity(text, pack)
            out["fidelity"] = score
            out["hint"] = (
                "Local worker answered from pack. "
                + (
                    "Fidelity heuristic PASS — still spot-check."
                    if score["recommend"] == "hold"
                    else "Fidelity heuristic WEAK — elevate to Grok or retry with --provider openrouter."
                )
            )
            ans = PACKS / f"{pack.get('id')}.answer.local.md"
            ans.write_text(
                f"# Answer (local)\n\n{text}\n\n## Fidelity scorecard\n\n"
                + json.dumps(score, indent=2)
                + "\n",
                encoding="utf-8",
            )
            (PACKS / "latest.fidelity.json").write_text(
                json.dumps(score, indent=2), encoding="utf-8"
            )
            out["answer_path"] = str(ans)
            if pack_id:
                _complete_execution_state(pack_id, out)
            return out
        except Exception as e:
            out["local_error"] = str(e)
            out["ok"] = False
            if pack_id:
                _complete_execution_state(pack_id, out)
            elev = "remote"

    if elev == "remote" or provider:
        from models.providers import chat_provider, chat_routed

        if provider:
            res = chat_provider(provider, system, prompt[:14000], tier="T2", max_tokens=2048)
        else:
            res = chat_routed(system, prompt[:14000], job="public_summarize", tier="T2", max_tokens=2048)
        out["seat"] = "remote"
        out["provider"] = res.get("provider")
        out["result"] = res
        if res.get("ok"):
            answer_text = res.get("text") or ""
            score = score_fidelity(answer_text, pack)
            out["fidelity"] = score
            ans = PACKS / f"{pack.get('id')}.answer.remote.md"
            ans.write_text(
                f"# Answer ({res.get('provider')}:{res.get('model')})\n\n{answer_text}\n\n"
                f"## Fidelity scorecard\n\n{json.dumps(score, indent=2)}\n",
                encoding="utf-8",
            )
            (PACKS / "latest.fidelity.json").write_text(
                json.dumps(score, indent=2), encoding="utf-8"
            )
            out["answer_path"] = str(ans)
            out["hint"] = (
                "Remote answered from pack. "
                + (
                    "Fidelity heuristic PASS — spot-check."
                    if score["recommend"] == "hold"
                    else "Fidelity WEAK — elevate to Grok with pack PDF."
                )
            )
        else:
            out["ok"] = False
            out["hint"] = "Remote failed — try local, fix keys/quota, or elevate to Grok."
        if pack_id:
            _complete_execution_state(pack_id, out)
        return out

    return out
