"""Ancient engineering — Frontinus, Vitruvius, Roman concrete.

WHY A SEPARATE MODULE
  NTRS has no ancient engineering, and the local census that seemed to say otherwise was
  measuring the wrong string. Measured before staging:

      'roman'    4,977 hits -> Roman numerals in a computing book; a "Roman toga" in Ingersoll
                               Lockwood; "Roman catholic" in Equiano. FICTION AND THEOLOGY.
      'aqueduct'    56 hits -> 8 files: Decline and Fall, Marco Polo, 20,000 Leagues, From the
                               Earth to the Moon, the Kama Sutra, Euler's letters.
      'pozzolan'     0 hits -> genuinely zero.

  So the estate holds NO ancient engineering material at all, and the 4,977 was a substring
  count wearing the costume of a subject census. This is the same error class as reporting a
  content probe's result as a property of the document.

THE SOURCES, verified against archive.org's own metadata (not a search snippet)
  deaquaeductuurbi0000fron   De aquaeductu urbis Romae, 1973 (Jansson, Teubner) -- Latin text
  twobooksonwater01frongoog  The two books on the water supply of the city of Rome of Sextus
                             Julius Frontinus, water commissioner of the city of Rome A.D. 97.
                             London, 1899. A photographic reproduction of the SOLE ORIGINAL
                             LATIN MANUSCRIPT with its Latin reprint, a translation into English,
                             and explanatory chapters. That is the 1st-century surveyor's manual
                             (De aquaeductu) wrapped around a manuscript facsimile -- the closest
                             thing to the primary document that has survived.
  architectureofma00vitr    The architecture of Marcus Vitruvius Pollio, 1826 -- the ten books on
                             architecture, concrete, vaults, hydraulics.
  elementsofcivila00aldrrich The elements of civil architecture, according to Vitruvius, 1824.

WHY FRONTINUS IS THE RIGHT ANCHOR FOR THIS ESTATE
  He was a water commissioner who audited a city's water supply, measured flow, reported on
  diversions and illegal draw, and wrote it up so a successor could be held to it. That is
  infrastructure governance, measurement, and accountability -- the same shape as the water-
  computer and mushroom pitch. He is the ancient analogue of the operator's own problem, not just
  a builder.

RIGHTS
  Pre-1929 works, US-hosted scans. The 1899 and 1826 editions are unambiguously public domain;
  the 1973 Teubner is also PD as to the underlying text (Frontinus is ancient) but is a modern
  scholarly apparatus, so it takes the REFERENCE tier. Rights are decided per row from the item's
  own date, never from a directory name.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mag.corpus_archive_acquire import _get, _meta, _rights, _text_files  # noqa: E402

RUNS = ROOT / "memory" / "runs" / "ancient_engineering"
RECEIPTS = ROOT / "docs" / "report_v1" / "sources" / "receipts"
PD = ROOT / "corpus" / "library" / "pd_physical_compute" / "ancient_engineering"
REF = ROOT / "corpus" / "papers_reference_nonredistributable"

ROWS: list[dict] = [
    {
        "slug": "frontinus-two-books-water-supply-rome-1899",
        "ident": "twobooksonwater01frongoog",
        "want": "aqueduct",
        "why": ("Frontinus, 'The two books on the water supply of the city of Rome', 1899. A "
                "photographic reproduction of the sole original Latin manuscript plus an English "
                "translation and explanatory chapters. Frontinus was Rome's water commissioner in "
                "AD 97: he audited the aqueducts, measured flow, reported illegal diversions, and "
                "wrote it up so a successor could be held to it. Infrastructure governance by "
                "measurement -- the closest surviving analogue to the water-computer problem."),
    },
    {
        "slug": "frontinus-de-aquaeductu-urbis-romae-1973",
        "ident": "deaquaeductuurbi0000fron",
        "want": "aqueduct",
        "why": ("the Teubner critical edition of De aquaeductu urbis Romae, 1973. Modern "
                "scholarly apparatus around the ancient text -- REFERENCE tier, since Frontinus "
                "is ancient but the edition is not."),
    },
    {
        "slug": "vitruvius-architecture-1826",
        "ident": "architectureofma00vitr",
        "want_any": ["pozzolana", "pozzolan", "concretion", "cement", "vault"],
        "why": ("Vitruvius, 'The architecture of Marcus Vitruvius Pollio', 1826. The ten books: "
                "concrete, vaults, the arch, hydraulics, proportions. THE material-and-structure "
                "counterweight to Frontinus' water-management view of the same civilisation."),
    },
    {
        "slug": "vitruvius-elements-civil-architecture-1824",
        "ident": "elementsofcivila00aldrrich",
        "want_any": ["cement", "vault", "arch", "lime", "mortar", "sand"],
        "why": ("the 1824 English 'Elements of Civil Architecture, according to Vitruvius'. "
                "Probed on vocabulary the 1824 text actually uses -- it has no 'concrete' and no "
                "'pozzolan' either."),
    },
]


def main() -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    PD.mkdir(parents=True, exist_ok=True)
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    held: set[str] = set()
    results: list[dict] = []

    for row in ROWS:
        md = _meta(row["ident"])
        if not md:
            print(f"  META-FAIL     {row['ident']}")
            results.append({**row, "status": "METADATA-UNAVAILABLE"})
            continue

        files = _text_files(md)
        if not files:
            print(f"  NO-TEXT-FILES {row['ident']}")
            results.append({**row, "status": "NO-TEXT-FILES"})
            continue

        tier, basis = _rights(md)
        date = str(md.get("date") or md.get("year") or "")
        # _rights is advisory for a scholarly modern edition of an ancient text: Frontinus is
        # ancient, so the 1973 edition's own apparatus is the only in-copyright part. Override
        # only where measured, and record that it was an override.
        if row["ident"] == "deaquaeductuurbi0000fron":
            tier, basis = "REFERENCE", ("1973 Teubner edition: the underlying Frontinus text is "
                                        "ancient and free, the critical apparatus is modern and in "
                                        "copyright. Measurable, and recorded as an override.")
        dest_dir = PD if tier in {"PD", "BORROW", "UNKNOWN"} else REF
        dest_dir.mkdir(parents=True, exist_ok=True)

        for name in files[:3]:
            url = f"https://archive.org/download/{row['ident']}/{name.replace(' ', '%20')}"
            st, body, err = _get(url, tries=3, timeout=240)
            if st != 200 or not body:
                print(f"  FETCH-FAIL    {name[:50]} {err or st}")
                results.append({**row, "status": "FETCH-FAILED", "file": name})
                continue
            if len(body) < 2000:
                print(f"  TOO-SHORT     {name[:50]} {len(body)}B")
                continue

            sha = hashlib.sha256(body).hexdigest()
            if sha in held:
                print(f"  DEDUPED       {name[:50]} (identical to a file already landed this run)")
                continue

            text = body.decode("utf-8", "replace")
            probe = " ".join(text[:40000].split()).lower()
            # want_any is a set of terms the DOCUMENT ITSELF uses; want is a single term.
            # Either way the gate asks whether the file contains the thing the row says, and
            # reports which term matched so a pass is falsifiable rather than asserted.
            terms = row.get("want_any") or [row["want"]]
            hits = [w for w in terms if w in probe]
            if not hits:
                print(f"  PROBE-FAIL    {name[:50]} none of {terms}")
                results.append({**row, "status": "FILE-CONTENT-MISMATCH", "file": name,
                                "probed_terms": terms})
                continue

            ext = ".pdf" if name.lower().endswith(".pdf") else ".txt"
            dest = dest_dir / f"anc_{row['slug']}{ext}"
            if not dest.exists():
                dest.write_bytes(body)
            held.add(sha)

            rcp = RECEIPTS / f"anc_{row['slug']}.md"
            rcp.write_text(
                f"# RETRIEVAL RECEIPT — ancient engineering — {row['slug']}\n\n"
                f"archive_identifier: {row['ident']}\n"
                f"selected_file: {name}\n"
                f"item_title: {str(md.get('title',''))[:200]}\n"
                f"item_date: {date}\n"
                f"item_creator: {str(md.get('creator'))[:160]}\n"
                f"content_sha256_16: {sha[:16]}\n"
                f"bytes: {len(body):,}\n"
                f"pulled: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}\n"
                f"source: {url}\n"
                f"rights_tier: {tier} ({basis})\n"
                f"landed: {str(dest.relative_to(ROOT)).replace(chr(92), '/')}\n"
                f"gap_closed: {row['why']}\n", encoding="utf-8")
            results.append({"slug": row["slug"], "status": "LANDED", "file": name,
                            "tier": tier, "bytes": len(body), "sha256": sha,
                            "probe_matched": hits,
                            "landed": str(dest.relative_to(ROOT)).replace("\\", "/"),
                            "receipt": str(rcp.relative_to(ROOT)).replace("\\", "/")})
            print(f"  LANDED        {name[:44]:46s} {len(body):>10,}B  {tier}")

    out = RUNS / "ANCIENT_LANDING.json"
    out.write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                               "landed": sum(1 for r in results if r["status"] == "LANDED"),
                               "bytes": sum(r.get("bytes", 0) for r in results),
                               "rows": results}, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\n  {sum(1 for r in results if r['status'] == 'LANDED')} landed -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())