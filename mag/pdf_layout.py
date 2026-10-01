"""Clean technical PDF layout for session dossiers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.units import inch as _inch  # noqa: F401 — used below
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

try:
    from mag.ingest_registry import file_url
except Exception:  # pragma: no cover

    def file_url(path):  # type: ignore
        return None

# Monochrome-leaning technical palette
INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#555555")
RULE = colors.HexColor("#CCCCCC")
ACCENT = colors.HexColor("#1a365d")  # deep blue, not neon
BG_SOFT = colors.HexColor("#F7F7F5")
WHITE = colors.white


def _esc(s: Any) -> str:
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="DocTitle",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=INK,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="DocSub",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=MUTED,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=ACCENT,
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MagBullet",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=INK,
            leftIndent=8,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Meta",
            fontName="Courier",
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Footer",
            fontName="Helvetica",
            fontSize=7,
            textColor=MUTED,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeBlock",
            fontName="Courier",
            fontSize=6.5,
            leading=8.5,
            textColor=INK,
            backColor=BG_SOFT,
            leftIndent=4,
            rightIndent=4,
            spaceBefore=4,
            spaceAfter=6,
        )
    )
    return styles


def _rule():
    return HRFlowable(width="100%", thickness=0.5, color=RULE, spaceBefore=4, spaceAfter=8)


def _bullets(items: list[str], style) -> list:
    out = []
    for it in items:
        if not it:
            continue
        out.append(Paragraph(f"• {_esc(it)}", style))
    return out


def _meta_table(rows: list[list[str]], styles) -> Table:
    data = [[Paragraph(f"<b>{_esc(a)}</b>", styles["Meta"]), Paragraph(_esc(b), styles["Meta"])] for a, b in rows]
    t = Table(data, colWidths=[1.45 * inch, 5.35 * inch])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("BACKGROUND", (0, 0), (-1, -1), BG_SOFT),
                ("BOX", (0, 0), (-1, -1), 0.4, RULE),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def _math_table(knot: dict[str, Any], styles) -> Table:
    tv = knot.get("theme_vector") or {}
    rows = [
        ["S_core (convention)", f"{knot.get('S_core_proxy')}"],
        ["β target", f"{knot.get('beta_target')}"],
        ["tension_index", f"{knot.get('tension_index')}"],
        ["residual_weight", f"{knot.get('residual_weight')}"],
        ["frame_occupancy", f"{knot.get('frame_occupancy')}"],
        ["Q_proxy", f"{knot.get('Q_proxy')}"],
        ["gap_proxy", f"{knot.get('gap_proxy')}"],
        ["λ₂_proxy", f"{knot.get('lambda2_proxy')}"],
        ["E_dirichlet_proxy", f"{knot.get('dirichlet_energy_proxy')}"],
        ["theme L1 / L2", f"{tv.get('L1')} / {round(tv.get('L2') or 0, 4)}"],
        ["theme entropy (nats)", f"{tv.get('entropy_nats')}"],
        ["theme concentration", f"{tv.get('concentration')}"],
        ["dominant theme", f"{tv.get('dominant')}"],
        ["duration (min)", f"{knot.get('duration_minutes')}"],
    ]
    data = [
        [Paragraph(f"<b>{_esc(a)}</b>", styles["Meta"]), Paragraph(_esc(b), styles["Meta"])]
        for a, b in rows
    ]
    t = Table(data, colWidths=[2.1 * inch, 4.7 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.6, ACCENT),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def render_clean_pdf(session_id: str, dossier: dict[str, Any], assets: dict[str, str], out_path: Path) -> Path:
    styles = _styles()
    time = dossier.get("time") or {}
    knot = dossier.get("scalar_knot") or {}
    sl = dossier.get("steiniger_laymen") or {}
    commit = dossier.get("content_commit") or {}

    created = (time.get("created_at") or {})
    updated = (time.get("updated_at") or time.get("last_active_at") or {})
    generated = (time.get("dossier_generated_at") or {})

    footer_left = session_id[:13]
    footer_mid = generated.get("iso_minute") or ""

    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        y = 0.5 * inch
        canvas.line(0.7 * inch, y + 10, letter[0] - 0.7 * inch, y + 10)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(0.7 * inch, y, footer_left)
        canvas.drawCentredString(letter[0] / 2, y, footer_mid)
        canvas.drawRightString(letter[0] - 0.7 * inch, y, f"{doc.page}")
        # top rule
        canvas.line(0.7 * inch, letter[1] - 0.45 * inch, letter[0] - 0.7 * inch, letter[1] - 0.45 * inch)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(0.7 * inch, letter[1] - 0.38 * inch, "SESSION DOSSIER · SCALAR-KNOT ANCHOR")
        canvas.drawRightString(
            letter[0] - 0.7 * inch,
            letter[1] - 0.38 * inch,
            "Steiniger-inspired · laymen ops",
        )
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=f"Session dossier {session_id}",
        author="Sovereign Mag",
    )

    story: list[Any] = []

    # Header block
    story.append(Paragraph("Session dossier", styles["DocTitle"]))
    story.append(
        Paragraph(
            "Untangling engine record · timestamps to the minute · math anchors for scalar-knot analysis",
            styles["DocSub"],
        )
    )
    story.append(_rule())

    story.append(
        _meta_table(
            [
                ["Session ID", session_id],
                ["Title", time.get("title") or "—"],
                ["Start (UTC)", f"{created.get('iso_minute', '—')}  ·  unix {created.get('unix_minute', '—')}"],
                ["End (UTC)", f"{updated.get('iso_minute', '—')}  ·  unix {updated.get('unix_minute', '—')}"],
                ["Date", f"{created.get('date', '—')} → {updated.get('date', created.get('date', '—'))}"],
                ["Duration", f"{knot.get('duration_minutes', '—')} minutes"],
                ["Dossier written", f"{generated.get('iso_full', generated.get('iso_minute', '—'))}"],
                ["Commit", f"{commit.get('algo', 'sha256')} {str(commit.get('hex', ''))[:16]}…"],
                ["Schema", dossier.get("schema") or ""],
                [
                    "Chord commitment",
                    (dossier.get("chord") or {}).get("commitment_hash") or "—",
                ],
            ],
            styles,
        )
    )

    chord = dossier.get("chord") or {}
    story.append(Paragraph("Chord struck", styles["H1"]))
    story.append(
        Paragraph(
            _esc(
                f"Commitment: {chord.get('commitment_hash', '—')}  ·  "
                f"Framework root: {str(chord.get('framework_root') or '')[:20]}…"
            ),
            styles["Meta"],
        )
    )
    story.append(Paragraph("1 · Plain English", styles["H2"]))
    story.append(Paragraph(_esc(chord.get("plain_english") or dossier.get("tldr")), styles["Body"]))
    story.append(Paragraph("2 · Personal impact", styles["H2"]))
    story.append(Paragraph(_esc(chord.get("personal_impact") or "—"), styles["Body"]))
    story.append(Paragraph("3 · Rope", styles["H2"]))
    story.append(Paragraph(_esc(chord.get("rope") or "—"), styles["Body"]))
    story.append(Paragraph("4 · Loops audited", styles["H2"]))
    loops = [
        f"{L.get('id')}: {L.get('plain')}" for L in (chord.get("loops_audited") or [])
    ]
    story.extend(_bullets(loops or ["None flagged in extract."], styles["MagBullet"]))
    story.append(Paragraph("5 · Disentangled moves", styles["H2"]))
    moves = chord.get("disentangled_moves") or []
    story.extend(
        _bullets(
            [f"{i+1}. {m}" for i, m in enumerate(moves)],
            styles["MagBullet"],
        )
        if moves
        else _bullets(["—"], styles["MagBullet"])
    )
    story.append(Paragraph("6 · Self-audit", styles["H2"]))
    story.append(Paragraph(_esc(chord.get("self_audit") or "—"), styles["Body"]))

    story.append(Paragraph("Observer charts (interference is signal)", styles["H2"]))
    for c in chord.get("observer_charts") or []:
        mark = "●" if c.get("active") else "○"
        story.append(
            Paragraph(
                f"{mark} <b>{_esc(c.get('label'))}</b> (score {c.get('score')}) — {_esc(c.get('plain'))}",
                styles["MagBullet"],
            )
        )

    # Math anchors — primary for future analysis
    story.append(Paragraph("A · Scalar-knot anchors (analysis)", styles["H1"]))
    story.append(
        Paragraph(
            "Proxies for later untangling (Steiniger-inspired). Not a full EUT solve. "
            "Use with minute timestamps for time-series comparison across sessions.",
            styles["Body"],
        )
    )
    story.append(_math_table(knot, styles))
    story.append(Spacer(1, 6))
    basis = (knot.get("theme_vector") or {}).get("basis") or []
    raw = (knot.get("theme_vector") or {}).get("raw") or []
    if basis and raw:
        story.append(Paragraph("Theme weight vector (fixed basis)", styles["H2"]))
        story.append(
            Paragraph(
                _esc("  ".join(f"{b}={v:g}" for b, v in zip(basis, raw))),
                styles["Meta"],
            )
        )

    # One clean chart only
    if assets.get("themes_chart"):
        story.append(Spacer(1, 8))
        story.append(Image(assets["themes_chart"], width=6.0 * inch, height=2.5 * inch))

    # Laymen ops — compact
    story.append(Paragraph("B · Untangling read (plain language)", styles["H1"]))
    story.append(Paragraph("What was under pressure", styles["H2"]))
    story.extend(_bullets(sl.get("tension") or [], styles["MagBullet"]))
    story.append(Paragraph("Frames held", styles["H2"]))
    for f in sl.get("frames") or []:
        mark = "●" if f.get("active") else "○"
        story.append(
            Paragraph(
                f"{mark} <b>{_esc(f.get('label'))}</b> — {_esc(f.get('note'))}",
                styles["MagBullet"],
            )
        )
    story.append(Paragraph("Protected core", styles["H2"]))
    story.extend(_bullets(sl.get("protected_core") or [], styles["MagBullet"]))
    story.append(Paragraph("Residual bonds (keep)", styles["H2"]))
    story.extend(_bullets((sl.get("residual_bonds") or [])[:8], styles["MagBullet"]))
    story.append(Paragraph("Collapse risks", styles["H2"]))
    story.extend(_bullets(sl.get("collapse_risks") or [], styles["MagBullet"]))
    story.append(Paragraph("Good moves", styles["H2"]))
    story.extend(_bullets((sl.get("good_moves") or [])[:8], styles["MagBullet"]))

    # Salient — limited
    story.append(Paragraph("C · Salient operator asks", styles["H1"]))
    asks = [
        sp.get("text")
        for sp in (dossier.get("salient_points") or [])
        if sp.get("type") == "operator_ask"
    ][-8:]
    story.extend(_bullets(asks, styles["MagBullet"]))

    story.append(Paragraph("D · Metaphors & ideas", styles["H1"]))
    mets = [m.get("meaning") for m in (dossier.get("metaphors") or [])][:8]
    ideas = [i.get("idea") for i in (dossier.get("complex_ideas") or [])][:8]
    story.append(Paragraph("Metaphors", styles["H2"]))
    story.extend(_bullets(mets or ["—"], styles["MagBullet"]))
    story.append(Paragraph("Ideas", styles["H2"]))
    story.extend(_bullets(ideas or ["—"], styles["MagBullet"]))

    # Bibliography — filename + where + clickable remote/local
    story.append(Paragraph("E · Bibliography (filename · where · links)", styles["H1"]))
    story.append(
        Paragraph(
            "Each item lists <b>filename</b>, <b>local path</b>, and <b>remote/HTML</b> when known. "
            "Local copies live under memory/ingest/local/. Blue text is clickable.",
            styles["Body"],
        )
    )
    final_bib = [["Kind / tags", "Title · filename · where · link"]]
    for b in (dossier.get("bibliography") or [])[:22]:
        kind = b.get("kind") or ""
        tags = ", ".join(b.get("tags") or [])[:40]
        title = b.get("title") or b.get("ref") or ""
        fname = b.get("filename") or "—"
        where = b.get("where_to_find") or b.get("note") or ""
        url = b.get("url") or ""
        local = b.get("local_copy") or b.get("local_path") or ""
        html_stub = b.get("html_stub") or ""
        # Prefer remote URL for click; else file URL for local html/pdf
        href = url
        if not href and html_stub:
            href = file_url(html_stub) or ""
        if not href and local:
            href = file_url(local) or ""
        if href:
            title_bit = f'<link href="{_esc(href)}" color="blue"><u>{_esc(title)[:90]}</u></link>'
        else:
            title_bit = _esc(title)[:90]
        body = (
            f"{title_bit}<br/>"
            f"<b>file:</b> {_esc(fname)}<br/>"
            f"<b>where:</b> {_esc(where)[:160]}"
        )
        if local:
            body += f"<br/><b>local:</b> {_esc(local)[:120]}"
        final_bib.append(
            [
                f"{kind}\n{tags}",
                Paragraph(body, styles["Meta"]),
            ]
        )
    bt = Table(final_bib, colWidths=[1.25 * inch, 5.55 * inch])
    bt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("BOX", (0, 0), (-1, -1), 0.4, RULE),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(bt)
    ingest = dossier.get("ingest") or {}
    if ingest:
        story.append(Spacer(1, 6))
        story.append(
            Paragraph(
                _esc(
                    f"Ingest DB: catalog={ingest.get('catalog')} · "
                    f"docs={ingest.get('local_docs')} · papers={ingest.get('local_papers')}"
                ),
                styles["Meta"],
            )
        )

    story.append(Paragraph("F · Open loops", styles["H1"]))
    story.extend(_bullets(dossier.get("open_loops") or [], styles["MagBullet"]))

    # Machine appendix
    story.append(PageBreak())
    story.append(Paragraph("Appendix · Machine index", styles["H1"]))
    story.append(
        Paragraph(
            "Prefer sibling .dossier.json for computers. PDF is human scan. "
            "Time fields: time.*.iso_minute, time.*.unix_minute. Math: scalar_knot.*",
            styles["Body"],
        )
    )
    index = {
        "schema": dossier.get("schema"),
        "session_id": session_id,
        "time": {
            "start_minute": created.get("iso_minute"),
            "end_minute": updated.get("iso_minute"),
            "start_unix_minute": created.get("unix_minute"),
            "end_unix_minute": updated.get("unix_minute"),
            "generated_minute": generated.get("iso_minute"),
        },
        "scalar_knot": {
            k: knot.get(k)
            for k in (
                "tension_index",
                "residual_weight",
                "Q_proxy",
                "gap_proxy",
                "lambda2_proxy",
                "dirichlet_energy_proxy",
                "duration_minutes",
            )
        },
        "theme_vector": knot.get("theme_vector"),
        "content_commit": commit,
    }
    story.append(Paragraph(_esc(json.dumps(index, indent=2)), styles["CodeBlock"]))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "Steiniger methods attributed (Academia / slashreboot / ORCID). "
            "CC-BY-4.0. Not settled-physics claims. Local private pack.",
            styles["DocSub"],
        )
    )

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return out_path
