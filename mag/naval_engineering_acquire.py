"""Naval engineering reference data -- US Government Printing Office 1957.

OPERATOR ADDITION, 2026-09-29:
  "except they have engineering data for stuff i like it keep it. could be useful for
   electronics and design i'm trying to build an intelligence i want to use instead of one
   people want to neuter and feed me"

WHY THIS IS A SEPARATE MODULE
  I first declined these two volumes on the grounds that they score ZERO for "differential
  analyzer": naval ordnance, not analog computing, and landing them would pad the
  physical-compute lineage shelf with off-topic bytes. The operator overruled that, and the
  correction matters more than the two files.

  I judged relevance by whether a document served the shelf's NARROW topic. The actual
  question is whether it serves the operator's BUILD. A corpus scoped to my guess of the topic
  is smaller than one scoped to the operator's intent -- and "an intelligence I want to use
  instead of one people want to neuter" is the clearest statement of intent in this whole
  tranche. Ballistics tables, metallurgy and thermodynamics are what an engineer building
  hardware reaches for.

WHY BOTH .txt AND .pdf ARE LANDED
  Measured in the text layer of the .txt:

      table 251   plate 149   figure 367   curves 16   characteristics 25
      chart 0     graph 10

  A djvu.txt carries CAPTIONS, not images. Every one of those 718 figures and plates is reduced
  to a line of alt text. The 44 MB and 37.6 MB Text PDFs carry the actual rendered plates.

  So the .txt is searchable and citable, and the .pdf is the only form from which the
  engineering data can actually be READ. Landing only the .txt would have delivered 718
  references to figures nobody can see -- which is exactly the failure mode the whole lineage
  of identity gates in this session exists to catch: a file whose presence implies a content
  the file does not contain.

RIGHTS
  Both volumes: 'UNITED STATES GOVERNMENT PRINTING OFFICE WASHINGTON: 1957', 'For sale by the
  Superintendent of Documents, U.S. Government Printing Office'. US Government works carry no
  US copyright (17 USC 105). Evidence is in the documents' own title pages, not in an
  archive.org metadata field -- archive.org's rights field is silent for this item.

  Verified present in collection 'mechanical-computer-technical-manuals':
      Naval_Ordnance_V1_Part1.pdf         44,077,626 B   Text PDF
      Naval_Ordnance_V1_Part1_djvu.txt     578,671 B   DjVuTXT
      Naval_Ordnance_V1_Part2.pdf         37,607,388 B   Text PDF
      Naval_Ordnance_V1_Part2_djvu.txt     498,909 B   DjVuTXT
"""

from __future__ import annotations

IDENT = "mechanical-computer-technical-manuals"

# shelf: NOT pd_physical_compute. These are engineering reference volumes that happen to live in
# the same archive.org collection as the Bush material. Filing them under the physical-compute
# shelf would assert a subject relationship that does not exist -- 0 hits for "differential
# analyzer" in either volume -- and the operator asked for them as electronics/design data.
SHELF = "naval_engineering"

ROWS: list[dict] = [
    {
        "slug": "naval-ordnance-and-gunnery-v1-part1-1957-txt",
        "file": "Naval_Ordnance_V1_Part1_djvu.txt",
        "row": "6",
        "why": ("Naval Ordnance and Gunnery, Vol 1 (1957), US Naval Academy, Part 1. Text layer. "
                "251 tables, 149 plates, 367 figures of ballistics, metallurgy, thermodynamics "
                "and fire control. SEARCHABLE FORM -- the plates themselves are images and live "
                "only in the PDF sibling."),
    },
    {
        "slug": "naval-ordnance-and-gunnery-v1-part1-1957-pdf",
        "file": "Naval_Ordnance_V1_Part1.pdf",
        "row": "6",
        "why": ("the 44 MB Text PDF of the same volume: the only form in which the 149 plates and "
                "367 figures are actually VISIBLE. The .txt is the index to these; this is the "
                "data."),
    },
    {
        "slug": "naval-ordnance-and-gunnery-v1-part2-1957-txt",
        "file": "Naval_Ordnance_V1_Part2_djvu.txt",
        "row": "6",
        "why": "Part 2 of the same 1957 volume: 216 tables and 351 figures. SEARCHABLE FORM.",
    },
    {
        "slug": "naval-ordnance-and-gunnery-v1-part2-1957-pdf",
        "file": "Naval_Ordnance_V1_Part2.pdf",
        "row": "6",
        "why": "the 37.6 MB Text PDF of Part 2: the rendered plates. SEARCHABLE and READABLE.",
    },
]

PDF_ROWS = [r for r in ROWS if r["file"].endswith(".pdf")]