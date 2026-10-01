#!/usr/bin/env python3
"""librarian.py — the dogfood-active bibliography auditor (v1)

The operator's law: records and bibliographies must not sit and collect dust —
they are part of the dogfooding process itself. This organ makes the
BIBLIOGRAPHY MAP load-bearing.

v1 (2026-09-11 — watch/LIBRARIAN_METHOD_20260911.md, the eight disciplines):
  PULLED/HASHED    per-row receipt state: a primary exists under
                   docs/report_v1/sources/ (receipts/<arxiv-id>.md, hashed
                   receipts carry a content hash; root PDFs match by name token)
  RETRIEVAL-PLAN   row names a source (arXiv id or URL) but no pulled receipt —
                   discipline 1: no live retrieval = every entry is a plan, not
                   a citation set, until pull + hash + excerpt
  TIER-3 FIRST     unnamed-debt rows GATE BUILDS — they sort first in the
                   report and in every section (disciplines 3 + 7)
  ADJACENT SWEEP   fields with ZERO coverage in the map, named on purpose
                   (discipline 5: correlated blind spots are structural)

v0 checks kept: UNREGISTERED, DUST, NO-STATUS, ARCHIVE.
Deterministic, stdlib-only, one pass. Writes watch/LIBRARIAN_REPORT.md.
Exit 0 = clean; exit 1 = unregistered citations exist (the map is behind the desk).
"""
import re, sys, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "docs" / "ref" / "BIBLIOGRAPHY_MAP.md"
OUT = ROOT / "watch" / "LIBRARIAN_REPORT.md"
SRC = ROOT / "docs" / "report_v1" / "sources"
RECEIPTS = SRC / "receipts"
WALK = ["watch", "docs", "mag"]
ARXIV = re.compile(r"\b(\d{4}\.\d{4,5})\b")
URL = re.compile(r"https?://|doi\.org|openreview|osf\.io|dl\.acm|ieeexplore", re.I)
STATUS_WORDS = ("PRIMARY-READ", "PRIMARY", "SECONDHAND", "CLASSICAL", "INTERNAL", "UNPROVEN", "UNVERIFIED", "row")
SELF_GUARD = {"librarian_report.md", "bibliography_map.md"}

# Discipline 5 — adjacent fields mined ON PURPOSE. Keywords matched against the
# map text (primary) and the scanned corpus (secondary).
FIELDS = {
    "ecology": ("ecology", "ecological", "pseudoreplication", "hurlbert"),
    "distributed systems": ("dynamo", "merkle", "anti-entropy", "distributed system", "byzantine", "consensus", "lamport"),
    "formal methods": ("formal method", "model checking", "tla+", "coq", "isabelle", "theorem prover", "smt solver"),
    "safety engineering": ("safety engineering", "stamp", "leveson", "fagan", "fmea", "hazard", "fault tree"),
    "economics": ("economics", "auction", "mechanism design", "market design", "game theor", "incentive compat"),
}


def md_files():
    out = []
    for d in WALK:
        base = ROOT / d
        if base.exists():
            out += [p for p in base.rglob("*.md") if p.name.lower() not in SELF_GUARD]
    return out


def map_rows():
    """Parse map rows -> list of dicts {rid, status, head, tier, raw}.

    Tier 3 = bullets under THE UNNAMED DEBT (should-have-cited-didn't; gates
    builds). Tier 1 = named table rows. Separator/prose lines are skipped.
    """
    rows = []
    section = ""
    if not MAP.exists():
        return rows
    for i, line in enumerate(MAP.read_text(encoding="utf-8", errors="replace").splitlines()):
        if line.startswith("#"):
            section = line.lstrip("# ").lower()
            continue
        stripped = line.strip()
        is_bullet = stripped.startswith("- ")
        is_table = stripped.startswith("|")
        if not (is_bullet or is_table):
            continue
        tier = 3 if "unnamed debt" in section else 1
        if is_table:
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) < 3 or set(cells[0]) <= set("- :"):
                continue
            head = cells[0][:80]
        else:
            head = stripped[2:82]
        raw = line
        m = ARXIV.search(raw)
        if m:
            rid = "arxiv:" + m.group(1)
        else:
            key = re.search(r"\b([A-Z][A-Za-z]+KV|[A-Z][A-Za-z]{3,})\b", head)
            rid = "key:" + (key.group(1) if key else f"row{i}")
        status = next((w for w in STATUS_WORDS if w.lower() in raw.lower()), None)
        rows.append({"rid": rid, "status": status, "head": head, "tier": tier, "raw": raw})
    return rows


def receipt_state():
    """Scan docs/report_v1/sources/ -> (pulled_ids, hashed_ids, pdf_tokens).

    A receipt in receipts/<arxiv-id>.md = PULLED; if its content carries a
    content hash (>=16 hex chars, per the extraction protocol) = HASHED too.
    Root PDFs contribute name tokens (deepseek, gva, ...) matched against rows.
    """
    pulled, hashed, pdf_tokens = set(), set(), {}
    if RECEIPTS.exists():
        for p in RECEIPTS.glob("*.md"):
            m = ARXIV.search(p.stem)
            if not m:
                continue
            pulled.add(m.group(1))
            try:
                head_txt = p.read_text(encoding="utf-8", errors="replace")[:2048]
            except OSError:
                continue
            if re.search(r"\b[0-9a-f]{16,}\b", head_txt, re.I):
                hashed.add(m.group(1))
    if SRC.exists():
        for p in SRC.glob("*.pdf"):
            token = re.split(r"[_\-.]", p.stem)[0].lower()
            if len(token) >= 4:
                pdf_tokens[token] = p.name
    return pulled, hashed, pdf_tokens


def extraction_aliases(map_text):
    """Name -> arxiv id pairs from the map's EXTRACTION PROTOCOL line, e.g.
    'CoT 2201.11903' — lets id-less rows (CoT/ReAct/SWE-bench) reach receipts."""
    aliases = {}
    for line in map_text.splitlines():
        if "extraction protocol" in line.lower():
            for m in re.finditer(r"\b([A-Za-z][\w+\-/]*?)\s+(\d{4}\.\d{4,5})\b", line):
                aliases[m.group(1).lower()] = m.group(2)
    return aliases


def row_state(row, pulled, hashed, pdf_tokens, aliases):
    """v1 status vocabulary: PULLED+HASHED > PULLED > RETRIEVAL-PLAN > stamped > None."""
    ids = ARXIV.findall(row["raw"])
    low = row["raw"].lower()
    if any(a in hashed for a in ids):
        return "PULLED+HASHED"
    if any(a in pulled for a in ids):
        return "PULLED"
    if any(tok in low for tok in pdf_tokens):
        return "PULLED"
    alias_ids = [aid for name, aid in aliases.items()
                 if re.search(r"\b" + re.escape(name) + r"\b", row["raw"], re.I)]
    if any(a in hashed for a in alias_ids):
        return "PULLED+HASHED"
    if any(a in pulled for a in alias_ids):
        return "PULLED"
    if ids or alias_ids or URL.search(row["raw"]):
        return "RETRIEVAL-PLAN"
    if row["tier"] == 3:
        return "RETRIEVAL-PLAN"  # unnamed-debt header: ALL rows are plans until pulled
    return row["status"]  # stamped rows keep their v0 stamp; None = NO-STATUS


def main():
    t0 = time.time()
    files = md_files()
    texts = {}
    for p in files:
        try:
            texts[p] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass

    rows = map_rows()
    pulled, hashed, pdf_tokens = receipt_state()
    aliases = extraction_aliases(MAP.read_text(encoding="utf-8", errors="replace") if MAP.exists() else "")
    for r in rows:
        r["state"] = row_state(r, pulled, hashed, pdf_tokens, aliases)

    row_ids = {r["rid"] for r in rows}
    cited = defaultdict(list)      # arxiv id -> files citing it
    for p, txt in texts.items():
        for m in ARXIV.finditer(txt):
            cited["arxiv:" + m.group(1)].append(str(p.relative_to(ROOT)))

    mapped_arxiv = {r["rid"][6:] for r in rows if r["rid"].startswith("arxiv:")}
    unregistered = {aid: fs for aid, fs in cited.items()
                    if aid not in row_ids and aid[6:] not in mapped_arxiv}

    all_text = "\n".join(t for t in texts.values())
    dust, nostatus, retrieval_plan, tier3 = [], [], [], []
    for r in sorted(rows, key=lambda r: (-r["tier"], r["rid"])):   # Tier 3 first
        needle = r["rid"].split(":", 1)[1]
        used = needle.lower() in all_text.lower()
        if not used:
            dust.append(r)
        if r["state"] is None:
            nostatus.append(r)
        if r["state"] == "RETRIEVAL-PLAN":
            retrieval_plan.append(r)
        if r["tier"] == 3:
            tier3.append(r)

    # Discipline 5 — adjacent-field sweep: which fields does the map never touch?
    map_text = MAP.read_text(encoding="utf-8", errors="replace").lower() if MAP.exists() else ""
    sweep = []
    for field, kws in FIELDS.items():
        map_hits = sum(map_text.count(k) for k in kws)
        corpus_hits = sum(all_text.lower().count(k) for k in kws)
        sweep.append((field, map_hits, corpus_hits))
    sweep.sort(key=lambda t: (t[1], t[2], t[0]))

    archived = sorted(p.name for p in SRC.glob("*")) if SRC.exists() else []

    rep = ["# LIBRARIAN REPORT — bibliography dogfood audit (v1)", "",
           f"_generated {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())} · "
           f"{len(texts)} docs scanned · {len(rows)} map rows · {time.time()-t0:.1f}s · "
           f"method: watch/LIBRARIAN_METHOD_20260911.md_", "",
           f"## TIER-3 GATE ROWS ({len(tier3)}) — unnamed debt, processed first", ""]
    for r in tier3:
        rep.append(f"- [{r['state'] or 'NO-STATUS'}] {r['rid']} — {r['head']}")
    rep += ["", f"## RETRIEVAL-PLAN ({len(retrieval_plan)}) — source named, primary not pulled+hashed", ""]
    for r in retrieval_plan:
        rep.append(f"- {r['rid']} — {r['head']}")
    rep += ["", f"## UNREGISTERED ({len(unregistered)}) — cited in cards, missing from the map", ""]
    for aid, fs in sorted(unregistered.items()):
        rep.append(f"- {aid} ← {fs[0]}" + (f" +{len(fs)-1}" if len(fs) > 1 else ""))
    rep += ["", f"## DUST ({len(dust)}) — map rows never consulted by any doc (tier-3 first)", ""]
    for r in dust:
        rep.append(f"- {r['rid']} — {r['head']}")
    rep += ["", f"## NO-STATUS ({len(nostatus)}) — rows without any status stamp", ""]
    for r in nostatus:
        rep.append(f"- {r['rid']} — {r['head']}")
    rep += ["", "## ADJACENT-FIELD SWEEP — discipline 5: mine the fields the thread never named", "",
            "_hits = keyword occurrences; 0 map hits = uncovered field_", ""]
    for field, mh, ch in sweep:
        rep.append(f"- {field}: map hits {mh} · corpus hits {ch}" + ("  ** ZERO MAP COVERAGE **" if mh == 0 else ""))
    rep += ["", f"## ARCHIVE ({len(archived)}) — primary sources retained in-repo", ""]
    for a in archived:
        rep.append(f"- docs/report_v1/sources/{a}")
    OUT.write_text("\n".join(rep) + "\n", encoding="utf-8")

    gaps = [f for f, mh, _ in sweep if mh == 0]
    states = defaultdict(int)
    for r in rows:
        states[r["state"] or "NO-STATUS"] += 1
    print(f"LIBRARIAN v1 -> {OUT.relative_to(ROOT)}")
    print(f"  docs scanned:     {len(texts)}")
    print(f"  map rows:         {len(rows)}  (tier-3: {len(tier3)})")
    print(f"  PULLED+HASHED:    {states['PULLED+HASHED']}")
    print(f"  PULLED:           {states['PULLED']}")
    print(f"  RETRIEVAL-PLAN:   {states['RETRIEVAL-PLAN']}")
    print(f"  UNREGISTERED:     {len(unregistered)}  (map behind the desk)")
    print(f"  DUST:             {len(dust)}  (rows never consulted)")
    print(f"  NO-STATUS:        {len(nostatus)}")
    print(f"  ZERO-Map-FIELDS:  {', '.join(gaps) if gaps else 'none'}")
    print(f"  ARCHIVE:          {len(archived)} primary sources retained")
    return 1 if unregistered else 0


if __name__ == "__main__":
    sys.exit(main())
