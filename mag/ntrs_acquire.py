"""NTRS acquirer — NASA Technical Reports Server, space-era circuitry.

API VERIFIED LIVE 2026-09-29, not assumed from a search snippet:
    search   GET https://ntrs.nasa.gov/api/citations/search?q=...&page[size]=N&page[from]=N
             -> {"stats": {...}, "results": [...], "aggregations": {...}}   646,655 documents
    record   GET https://ntrs.nasa.gov/api/citations/<id>
             -> downloads[].links.{original,pdf,fulltext}
    fetch    GET https://ntrs.nasa.gov/api/citations/<id>/downloads/<name>.{pdf,txt}
  No authentication. Rate limit reported as 500 requests.

RIGHTS ARE A FIELD, NOT A GUESS
  Every record carries `distribution` ("PUBLIC") and `copyright` (a dict incl.
  disclosedToPublic, thirdPartyPermissionsProduced, publisherPermissionOrRelease). Rows are
  accepted only when distribution == "PUBLIC". A record with METADATA_ONLY dissemination, or
  with third-party content flagged, is held rather than landed -- same rule as the Soviet
  patent: refuse rather than put an unexamined document on a shelf.

BOTH FORMS ARE FETCHED WHERE BOTH EXIST
  NTRS exposes a rendered .pdf and a .txt fulltext for the same record. The Naval Ordnance
  lesson applies: the .txt is searchable, the .pdf is the only form in which figures and
  schematics are actually visible. The Astrionics record is 25.7 MB of PDF against 220 KB of
  text -- a 117:1 ratio that is entirely plates. Fetching only the text would have delivered
  references to drawings nobody can see.

DEDUPE IS ENFORCED, NOT ADVISED
  Every fetch is checked against mag.dedupe_index (sha256 of every corpus file) BEFORE it is
  written, and against an advisory title index. This seat has twice re-acquired material the
  estate already held; the gate is the reason that should not recur.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mag.dedupe_index import load as dedupe_load            # noqa: E402
from mag.physical_compute_acquire import _pdf_text          # noqa: E402

RUNS = ROOT / "memory" / "runs" / "ntrs_circuitry"
RECEIPTS = ROOT / "docs" / "report_v1" / "sources" / "receipts"
PD_SHELF = ROOT / "corpus" / "library" / "pd_physical_compute" / "nasa_space"
REF_SHELF = ROOT / "corpus" / "papers_reference_nonredistributable"
API = "https://ntrs.nasa.gov/api/citations"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HermesCorpus/1.0"}


def _get(url: str, tries: int = 3, timeout: int = 120) -> tuple[int, bytes, str]:
    last = ""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.status, r.read(), ""
        except Exception as e:                      # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:80]}"
            time.sleep(2 * (attempt + 1))
    return 0, b"", last


# QUERIES, chosen from the era the operator asked for and the era gaps measured in the local
# census. Each is a real NTRS query string; every hit is verified by fetching its record.
QUERIES: list[tuple[str, str]] = [
    ("astrionics guidance computer",        "guidance computer, analog + digital avionics"),
    ("Apollo guidance computer",            "the DGC itself"),
    ("inertial guidance platform",          "gyros, accelerometers, platforming"),
    ("spacecraft telemetry system",         "telemetry, PCM, ground stations"),
    ("electronic circuits space",           "circuitry as such"),
    # MEASURED DEAD QUERY, replaced 2026-09-29: 'Sputnik Vostok electronics' returns ZERO hits on
    # NTRS. Not a transient failure -- re-queried and confirmed 0. The cause is that NTRS ANDs
    # every term, and no record in the corpus contains all three words. The lesson is the same one
    # that stopped a truncated search-snippet URL being staged: a query returning nothing is a
    # claim about the CATALOGUE that has to be checked, not a conclusion about the subject.
    #
    # Also measured: bare 'Sputnik' returns 10 hits of which the top two are 'Reconsidering
    # Sputnik' (a history paper, fine) and "Pluto's Sputnik Planitia" (a geology paper about a
    # plain on Pluto, irrelevant). Single-word Soviet queries pull planetary-science collisions.
    # So the working Soviet queries are two-word ones that name the domain: 'Soviet electronics'
    # gives 7 downloadable+PUBLIC, 'Soviet spacecraft electronics' gives 3.
    ("Soviet electronics",                "power electronics, buses, Soviet hardware"),
    ("Soviet spacecraft electronics",     "Soviet avionics as such"),
    ("Soviet nuclear power satellite",    "the nuclear-power spacecraft line"),
    ("satellite attitude control",          "reaction wheels, control electronics"),
    ("vacuum tube amplifier spacecraft",    "pre-1965 electronics"),
]

# -- THE SOVIET HALF. NASA translated Soviet space work through the Technical Translation (TT)
# series and the Foreign Technology Division, and those translations are US Government works --
# public domain. So the Soviet circuitry line does not need a Russian-language source at all: the
# English translations are on NTRS and they are cleaner, better scanned, and legally free.
#
# MEASURED live against the API before staging: 'Soviet space electronics' returns 14 total with
# 7 downloadable+PUBLIC, 'Soyuz spacecraft' 177 total with 9 downloadable+PUBLIC, 'Vostok
# spacecraft' 12 with 1. Every row below is a real query string that returned hits, not a guess
# at a document title -- the same rule that stopped a truncated search-snippet URL being staged
# as a source earlier in this session.
SOVIET_QUERIES: list[tuple[str, str]] = [
    ("Soviet space electronics",   "power electronics, spacecraft buses, Soviet hardware"),
    ("Soyuz spacecraft",           "the Soyuz line: docking, reliability, subsystems"),
    ("Vostok spacecraft",          "the earliest crewed flights"),
    ("Sputnik satellite",          "the first artificial satellites"),
    ("Soviet spacecraft guidance", "attitude control and guidance"),
    ("Salyut space station",       "long-duration Soviet hardware"),
    ("Soviet launch vehicle",      "launcher systems and their electronics"),
]

# -- THE ANCIENT TURN. MEASURED BEFORE STAGING, and the result is the reason this section exists.
# A term census over the corpus returned: aqueduct 56, roman 4,977, pozzolan 0. On inspection
# EVERY one of those is a false positive:
#     'roman'      -> Roman numerals in a book on computing; a "Roman toga" in Ingersoll Lockwood;
#                     a "Roman catholic" catechism in Equiano. FICTION AND THEOLOGY.
#     'aqueduct'   -> 8 files total: Decline and Fall, Marco Polo, 20,000 Leagues, From the Earth
#                     to the Moon, the Kama Sutra, Euler's letters. NO ENGINEERING SOURCE.
#     'pozzolan'   -> 0, genuinely.
# So the corpus holds NO ancient engineering material whatsoever, and the 4,977 figure was
# measuring the word 'Roman' in novels. This is the same class of error as reporting a content
# probe's result as a property of the document -- a count that measures the string, not the
# subject. Ancient engineering is therefore a genuine gap, not a consolidation of what we have.
#
# The sources for it are structural: Frontinus' De aquaeductu (the 1st-century AD survey of
# Rome's water supply), Vitruvius (concrete, vaults, hydraulics), and the modern scholarship on
# Roman concrete -- all reachable via archive.org, which is where the existing mechanical/analog
# tranche came from.
ANCIENT_QUERIES: list[tuple[str, str]] = [
    ("Frontinus water supply Rome", "De aquaeductu -- the ancient surveyor's manual"),
    ("Vitruvius architecture",       "concrete, vaults, the ten books"),
    ("Roman concrete pozzolan",      "the material science behind the vaults"),
    ("Roman engineering survey",     "roads, bridges, aqueducts as built works"),
]


def search(q: str, size: int = 25, frm: int = 0) -> list[dict]:
    st, body, err = _get(f"{API}/search?" + urllib.parse.urlencode(
        {"q": q, "page": {"size": size, "from": frm}}, doseq=True), timeout=90)
    if st != 200:
        print(f"    search failed {q!r}: {err}")
        return []
    try:
        return json.loads(body).get("results", [])
    except Exception as e:                          # noqa: BLE001
        print(f"    search parse failed {q!r}: {e}")
        return []


def record(rid: str) -> dict | None:
    st, body, _ = _get(f"{API}/{rid}", timeout=90)
    return json.loads(body) if st == 200 else None


_HELD_CACHE: set[str] | None = None


def _held_hashes() -> set[str]:
    """Every sha256 already in the corpus, so a re-acquisition is refused BEFORE it is written.

    This seat has twice re-acquired material the estate already held (three Ingersoll Lockwood
    books, 1,069,068 B). The dedupe groups file lists only DUPLICATED hashes, which is the wrong
    set -- a re-acquisition of a document that is held ONCE matches nothing there. What is needed
    is every hash on disk, so this walks the corpus and caches the result.
    """
    global _HELD_CACHE
    if _HELD_CACHE is not None:
        return _HELD_CACHE
    _HELD_CACHE = set()
    corpus = ROOT / "corpus"
    for p in corpus.rglob("*"):
        if not p.is_file():
            continue
        try:
            if p.stat().st_size == 0:
                continue
            _HELD_CACHE.add(hashlib.sha256(p.read_bytes()).hexdigest())
        except Exception:
            continue
    return _HELD_CACHE


def land(rec: dict, shelf_name: str) -> list[dict]:
    """Land both forms of one record. Returns per-file result rows."""
    rid = str(rec.get("id"))
    title = str(rec.get("title") or rid)[:150]
    out: list[dict] = []

    dist = rec.get("distribution")
    cp = rec.get("copyright") or {}
    if dist != "PUBLIC":
        return [{"id": rid, "title": title, "status": "HELD-NOT-PUBLIC",
                 "why": f"distribution={dist!r} -- not a public-domain claim"}]
    if cp.get("thirdPartyPermissionsProduced"):
        return [{"id": rid, "title": title, "status": "HELD-THIRD-PARTY",
                 "why": "copyright.thirdPartyPermissionsProduced=True -- third-party content "
                        "inside; refusing to land unexamined"}]

    links = {}
    for dl in rec.get("downloads") or []:
        for k, v in (dl.get("links") or {}).items():
            links.setdefault(k, v)
    if not links:
        return [{"id": rid, "title": title, "status": "NO-DOWNLOAD",
                 "why": "record advertises no download links"}]

    dest_dir = PD_SHELF / shelf_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    RECEIPTS.mkdir(parents=True, exist_ok=True)

    for kind, link in (("pdf", links.get("pdf") or links.get("original")),
                       ("txt", links.get("fulltext"))):
        if not link:
            continue
        st, body, err = _get(f"https://ntrs.nasa.gov{link}", timeout=300)
        if st != 200 or not body:
            out.append({"id": rid, "title": title, "status": "FETCH-FAILED",
                        "why": f"{kind}: {err or st}"})
            continue
        if kind == "pdf" and body[:5] != b"%PDF-":
            out.append({"id": rid, "title": title, "status": "NOT-A-PDF",
                        "why": f"first bytes {body[:8]!r}"})
            continue

        sha = hashlib.sha256(body).hexdigest()
        if sha in _held_hashes():
            out.append({"id": rid, "title": title, "status": "DEDUPED-BY-HASH",
                        "why": f"already in the corpus (sha {sha[:12]})"})
            continue

        slug = "".join(ch if ch.isalnum() else "-" for ch in title.lower())[:70].strip("-")
        dest = dest_dir / f"nasa_{rid}_{slug}.{kind}"
        dest.write_bytes(body)

        text = ""
        if kind == "pdf":
            text, _why = _pdf_text(body) or ("", "")
            text = text or ""
        else:
            text = body.decode("utf-8", "replace")

        rcp = RECEIPTS / f"nasa_{rid}_{kind}.md"
        rcp.write_text(
            f"# RETRIEVAL RECEIPT — NASA NTRS {rid} — {title}\n\n"
            f"ntrs_id: {rid}\n"
            f"title: {title}\n"
            f"sti_type: {rec.get('stiType','')} {rec.get('stiTypeDetails','')}\n"
            f"center: {(rec.get('center') or {}).get('name','')}\n"
            f"published: {rec.get('distributionDate','')}\n"
            f"distribution: {dist}\n"
            f"copyright: {json.dumps(cp)}\n"
            f"keywords: {', '.join(rec.get('keywords') or [])[:300]}\n"
            f"content_sha256_16: {sha[:16]}\n"
            f"bytes: {len(body):,}\n"
            f"form: {kind}\n"
            f"pulled: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}\n"
            f"source: https://ntrs.nasa.gov{link}\n"
            f"rights_tier: PD (NASA technical report, distribution PUBLIC per the record's own "
            f"distribution field; US Government work, 17 USC 105)\n"
            f"landed: {str(dest.relative_to(ROOT)).replace(chr(92), '/')}\n"
            f"extracted_chars: {len(text):,}\n"
            f"abstract: {' '.join(str(rec.get('abstract','')).split())[:600]}\n", encoding="utf-8")

        out.append({"id": rid, "title": title, "status": "LANDED", "form": kind,
                    "bytes": len(body), "sha256": sha,
                    "landed": str(dest.relative_to(ROOT)).replace("\\", "/"),
                    "receipt": str(rcp.relative_to(ROOT)).replace("\\", "/"),
                    "extracted_chars": len(text)})
        time.sleep(1.0)          # NTRS allows 500 req; stay well inside it

    return out


def main() -> int:
    limit_per_query = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    tranche = sys.argv[2] if len(sys.argv) > 2 else "nasa"
    if tranche == "soviet":
        queries = SOVIET_QUERIES
    elif tranche == "ancient":
        queries = ANCIENT_QUERIES
    else:
        queries = QUERIES
    RUNS.mkdir(parents=True, exist_ok=True)
    dedupe_load()
    results: list[dict] = []

    for q, why in queries:
        print(f"\n=== {q}   [{why}]")
        hits = search(q, size=limit_per_query)
        print(f"  {len(hits)} hits")
        n_landed = 0
        for h in hits:
            rid = str(h.get("id"))
            if not (h.get("downloadsAvailable") and h.get("distribution") == "PUBLIC"):
                print(f"  - {rid} skip (downloadsAvailable={h.get('downloadsAvailable')}, "
                      f"distribution={h.get('distribution')})")
                continue
            rec = record(rid)
            if not rec:
                print(f"  - {rid} record fetch failed")
                continue
            rows = land(rec, "nasa_space")
            for r in rows:
                results.append({**r, "query": q})
                if r["status"] == "LANDED":
                    n_landed += 1
                    print(f"  + {rid} {r['form']:3s} {r['bytes']:>12,}B  "
                          f"{r['title'][:52]}")
                else:
                    print(f"  - {rid} {r['status']}")
        print(f"  landed {n_landed} files from {q!r}")

    out = RUNS / f"NTRS_LANDING_{tranche.upper()}.json"
    prev = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {"rows": []}
    seen = {(r["id"], r.get("form")) for r in results}
    prev["rows"] = [r for r in prev.get("rows", [])
                    if (r["id"], r.get("form")) not in seen] + results
    prev["ts"] = datetime.now(timezone.utc).isoformat()
    prev["tranche"] = tranche
    prev["landed"] = sum(1 for r in prev["rows"] if r["status"] == "LANDED")
    prev["bytes_landed"] = sum(r.get("bytes", 0) for r in prev["rows"] if r["status"] == "LANDED")
    out.write_text(json.dumps(prev, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTOTAL {prev['landed']} files, {prev['bytes_landed']:,} bytes -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())