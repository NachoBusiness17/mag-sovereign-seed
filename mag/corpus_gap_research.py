"""corpus_gap_research -- the GAP half of the self-steal, fanned out across free channels.

WHY THIS EXISTS (operator, 2026-09-28): "look at all of my research and do a gap analysis and
launch a research project filling in the gaps around our gaming corpus our science, science
fiction and old books self steal and go wide and hard."

The measured gap (census 2026-09-28, `corpus_census_20260928.sh` + `prose_census2_20260928.sh`):

  * corpus/library is 5.4 GB / 55,915 files and it is ~90% CODE (ms-genai-beginners,
    openai-cookbook, zcode-zai-org, mod-playerbots, evennia, dfhack) -- not prose.
  * The entire readable-book corpus is 57 txt >100KB + 1 epub + 115 pdf. That is the corpus.
  * Science fiction / fiction prose: 1 epub (Tertium Organum 1922), 3 Ingersoll Lockwood
    (1900s lost-race), Wells' Star Maker, Stapleford's Last and First Men, Nag Hammadi.
    A scifi-author grep over corpus+steal returns 12 hits and every one is the WORD "wright".
    There is no Asimov, Clarke, Le Guin, Dick, Lem, Herbert, Gibson, Delany, Le Guin, Butler.
  * Science: docs/ref/BIBLIOGRAPHY_MAP.md is 357 lines and every row is LLM infrastructure
    (KV cache, mesh, eval). corpus/training_materials is 26 PDFs, all ML/math. There is no
    natural science, complexity theory, or history-of-science pull.
  * Old books: 20 authors, but concentrated in 1900-1928 political psychology (Lippmann, Le
    Bon, Jung, Freud, Bernays, Debord, Inniss, Wallas, Weil, Greer) plus Greek classics.
    No medieval/Renaissance, no East Asian, no South Asian, no African, no indigenous,
    no counter-Enlightenment, no military theory.
  * Gaming: deep on MECHANICS (Marathon terminal harvest, WoW/AzerothCore steal map, evennia,
    dfhack, playerbots) and empty on DESIGN THEORY and HISTORY (no MDA, no game studies).

The instrument is also blind where the corpus actually lives: `corpus_selfsteal.SURFACES` never
lists `corpus/**`, and its TEXT_EXT has no book containers. That half is fixed in
`corpus_selfsteal.prose()`; this module is the other half.

SELF-STEAL, NOT A NEW TOOL: the lane table, the request shape, the empty-content guard, the
lite-guard accounting, the append-only raw tape and the "leads not facts" pack header are all
IMPORTED from `mag/research_fanout.py`. This file contributes only the gap battery and its own
artifact root. Two lanes were dead at probe time (HTTP 404) and are reported, not hidden.

RUN:
  python -m mag.corpus_gap_research lanes
  python -m mag.corpus_gap_research battery
  python -m mag.corpus_gap_research run --workers 8
  python -m mag.corpus_gap_research retry
  python -m mag.corpus_gap_research status

Schema: corpus_gap_research.v1 . $0 (free tiers only; paid keys deliberately excluded).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

# ---- the borrowed half. Nothing below reimplements a lane call. ----------------------
from mag.research_fanout import (  # noqa: E402
    LANES, _env, call_lane, probe_lanes,
)

SCHEMA = "corpus_gap_research.v1"
OUT = ROOT / "memory" / "runs" / "corpus_gap_research"
RAW = OUT / "raw.jsonl"
PACK = OUT / "CORPUS_GAP_RESEARCH.md"
RECEIPT = OUT / "receipt.json"

SYSTEM = (
    "You are a research digger for a corpus project that already holds game MECHANICS and "
    "LLM infrastructure, and is missing the underlying IDEAS. Answer with CONCRETE, "
    "ACQUIRABLE material only: exact work titles, author, year, Project Gutenberg ebook "
    "numbers, Internet Archive identifiers, DOI or arXiv IDs, open-source repository URLs, "
    "publisher and year. Name what is legally downloadable and where from. Prefer specifics "
    "over framing. No preamble, no summary of the question, no moralising. If you are "
    "unsure of a number or an ID, say which part is uncertain instead of inventing one. "
    "Hard limit: 200 words. Compact bullets."
)

# ---------------------------------------------------------------------------
# THE GAP BATTERY -- 57 questions, scoped ONLY to measured gaps.
# id | theme | question
# ---------------------------------------------------------------------------
BATTERY: list[tuple[str, str, str]] = [
    # ================= G. GAMING -- design theory, history, criticism =================
    ("G01", "G-gaming", "Name the 10 canonical works of GAME DESIGN THEORY with author, year, "
     "publisher and whether the text is legally obtainable (PDF, book, or open access). "
     "Include MDA framework, Flow in games, the Bartle taxonomy,MDA, and Bogost's "
     "procedural rhetoric."),
    ("G02", "G-gaming", "Ernest Adams and the D&D lineage: which D&D books are public domain or "
     "legally free to download, with exact SRD/OGL version numbers, dates, and the exact "
     "current Open Gaming Licence or Creative Commons licence text? Give URLs."),
    ("G03", "G-gaming", "Richard Bartle's Designing Virtual Worlds (2004) and A Dark Room "
     "and an Empty Space: what is the full MUD taxonomy (Bartle axes, Rafstark, Apeland, "
     "Taylor), which MUD codebase implements each axis, and which open-source MUD codebase "
     "is the best legal donor today? Name repos and licences."),
    ("G04", "G-gaming", "Janet Murray's Hamlet on the Holodeck (1997) and Marie-Laure Ryan's "
     "Narrative as Virtual Reality (2001) and Avatars of Story (2006): give ISBNs, "
     "publishers, and which chapter or concept each contributes to procedural narrative "
     "design. Flag anything not legally free."),
    ("G05", "G-gaming", "Roguelike design literature: name the 10 most cited roguelike design "
     "essays and postmortems with author, year, publication and URL. Include Derek Yu's "
     "'How to Make a Roguelike', Chris Gregan's 'Five Things I Learned', and any "
     "Game Developer/Gamasutra/GameMaker postmortem with a named number (team size, budget, "
     "sales, development length)."),
    ("G06", "G-gaming", "The procedural generation bibliography: give 20 real citations with "
     "author, year, title and DOI/arXiv ID for PCG in games. Must include PCGML, "
     "WFC (Wave Function Collapse), Houdini, and at least 5 named commercial game postmortems "
     "that shipped procedural content."),
    ("G07", "G-gaming", "Dark Souls and the action-RPG lineage: which design GDC talks and "
     "postmortems exist for FromSoftware titles, Demon Souls, Bloodborne and Sekiro? Give "
     "speaker, conference, year, talk title and any public video or slides URL."),
    ("G08", "G-gaming", "Dwarf Fortress, roguelikes and simulation games as design sources: "
     "Bay 12 Games' Tarn Adams interviews, the DF '80+ things' threads, and the "
     "\"Faces of the deep\" writing on simulation-driven design. Give URLs and dates."),
    ("G09", "G-gaming", "Game studies as an academic field: list the 10 most cited GAME STUDIES "
     "books (not design books) with author, year, publisher and ISBN. Must include Bogost, "
     "Jenkins, Murray, Wardrip-Fruin, and at least one ludology-vs-narratology source."),
    ("G10", "G-gaming", "MUD and MMO history as a technical and design lineage: give 10 dated "
     "primary sources with URLs for the history of MUD1 through LambdaMOO, including Roy "
     "Trubshaw's original announcements, Pavel Curtis's LambdaMOO server, and the MUD "
     "development mailing list archives."),
    ("G11", "G-gaming", "TableTop RPG design lineage: name the 10 most influential tabletop RPG "
     "design books with author, year, publisher, ISBN and any open-access or legally free "
     "edition. Include Gygax, Arneson, Greg Costikyan, Ron Edwards, Fate, and Blades in the Dark."),
    ("G12", "G-gaming", "Game feel, juice and input latency as design science: cite the "
     "research literature (not blog posts) on game feel, controller latency, frame pacing "
     "and player-perceived responsiveness. Give authors, years, venues, DOIs. Include any "
     "work measuring the effect of latency on player performance."),
    ("G13", "G-gaming", "Serious games, training transfer and the evidence base: cite 10 real "
     "systematic reviews or meta-analyses on whether games transfer training to real-world "
     "performance. Give authors, year, journal, DOI. Include the S conjecture literature and "
     "any large negative-result review."),

    # ================= S. SCIENCE -- natural, complexity, history =====================
    ("S01", "S-science", "Complexity science primary sources: give 12 canonical citations with "
     "author, year, title, journal and DOI for complexity theory as applied to systems and "
     "agents. Must include Santa Fe Institute 1984 volume 1, Holland, Gell-Mann, "
     "Anderson's 'More is Different', and Chris Langton on artificial life."),
    ("S02", "S-science", "Information theory beyond the ML corpus: give 12 primary citations "
     "with author, year, title and DOI for Shannon 1948, Kolmogorov complexity, Chaitin "
     "incompleteness, algorithmic information theory, and the algorithmic priors literature "
     "(Hutter, Legg, Schmidhuber). Flag which are legally downloadable."),
    ("S03", "S-science", "Category theory and the mathematical foundations of composition: give "
     "the 10 primary references (Mac Lane, Lawvere, Fong & Spivak 'Seven Sketches in "
     "Compositionality', Spivak 'Categorical Foundations of the Sciences') with DOI and open "
     "access URLs."),
    ("S04", "S-science", "Nonstandard analysis, hyperreals and non-Newtonian modelling: give "
     "10 real primary citations with author, year, venue and DOI, including Robinson's "
     "Non-Standard Analysis and the modern reissues. Flag which are legally free."),
    ("S05", "S-science", "History and philosophy of science as a source of method: name 12 "
     "primary works with author, year, publisher and ISBN. Must include Kuhn, Popper, "
     "Lakatos, Duhem, Latour, and at least one book on scientific instrumentation or "
     "measurement."),
    ("S06", "S-science", "Cybernetics and second-order cybernetics: give 12 primary citations "
     "with author, year, title, publisher and DOI/ISBN. Must include Wiener, Ashby, "
     "Beer (Brain of the Firm), Varela, Maturana, and Stafford Beer's Designing Freedom. "
     "Flag which are legally free."),
    ("S07", "S-science", "Ecology, mycelial networks and the wood wide web claims: give 12 "
     "primary citations with author, year, journal and DOI covering mycorrhizal networks, "
     "carbon transfer, and the scientific disputes about the 'wood wide web' claim. Include "
     "the critical or replication-failure papers specifically."),
    ("S08", "S-science", "Statistical methodology the LLM corpus never cited: give 12 primary "
     "citations with author, year, journal and DOI. Must include bootstrap, permutation tests, "
     "multiple-comparison corrections, power analysis, and the replication crisis primary "
     "papers (Nature 2015, Science 2011)."),
    ("S09", "S-science", "Distributed systems primary literature outside the KV-cache "
     "corridor: give 15 primary citations with author, year, venue and DOI covering consensus, "
     "logical clocks, CRDTs, and Merkle/DAG history. Must include Lamport, Fischer Lynch "
     "Paterson, FLP impossibility, Bayou, and the 2020s CRDT survey."),
    ("S10", "S-science", "Game-theoretic and evolutionary modelling of multi-agent systems: "
     "give 12 primary citations with author, year, venue and DOI. Include Axelrod, Nowak, "
     "Ostrom's commons governance work, and any 2020s work on emergent conventions in LLM "
     "populations."),
    ("S11", "S-science", "Cognitive science of memory and narrative: give 12 primary "
     "citations with author, year, journal and DOI. Must include Bartlett, Schank, "
     "Kintsch constructivist theory, and the current schema-based narrative comprehension "
     "literature."),
    ("S12", "S-science", "Aesthetics and philosophy of art as design source: give 10 primary "
     "citations with author, year, publisher and ISBN. Include Kant's Critique of Judgment, "
     "Ranciere's distribution of the sensible, Adorno on commitment, and any 2020s work on "
     "computational aesthetics or procedural art value."),
    ("S13", "S-science", "Network science: give 12 primary citations with author, year, "
     "journal and DOI. Must include Barabasi & Albert, Watts & Strogatz, Newman "
     "(assortative mixing), the community detection null-model debate, and any 2020s "
     "work on network motifs in language or institutions."),

    # ================= F. SCIENCE FICTION -- the emptiest domain =====================
    ("F01", "F-scifi", "The pre-1940 science fiction canon as legally free full text: give 25 "
     "specific works with author, year, and the exact Project Gutenberg ebook number or "
     "Internet Archive identifier for a LEGAL full-text download. Prioritise Shelley, Verne, "
     "Wells, Burroughs, London, Zangwill."),
    ("F02", "F-scifi", "New Wave science fiction 1968-1980 as legally free text: give 20 "
     "specific works (novels and stories) with author, year, title, and the exact Project "
     "Gutenberg ID or Internet Archive identifier for a legal download. Prioritise Delany, "
     "Le Guin, Disch, Cherryh, Simmons, Aldiss."),
    ("F03", "F-scifi", "Philip K. Dick, Ursula K. Le Guin and Octavia Butler: which works are "
     "legally free, and what is the exact legal status of US copyright for works published "
     "in each year (95 years from publication)? Give the year-by-year boundary math for "
     "each author, plus any public-domain or open-license editions that exist."),
    ("F04", "F-scifi", "Asimov, Arthur C. Clarke and Robert A. Heinlein: give 12 specific "
     "works with publication year and the exact copyright-expiry year under US law, and name "
     "any edition that is already public domain or Creative Commons. Same for the short "
     "fiction."),
    ("F05", "F-scifi", "Science fiction as a design source for AI narratives: cite the 12 "
     "academic papers that use science fiction as a design or evaluation resource for AI "
     "systems, with author, year, venue and DOI/arXiv ID. Include any work on sci-fi "
     "scenario-based AI evaluation and SciFi4Latent or similar benchmark work."),
    ("F06", "F-scifi", "Frankenstein, Dr. Moreau and the SF origin: give exact publication "
     "years, first-edition publisher, and the Project Gutenberg or Internet Archive ID for "
     "each. Include the 1931 film public-domain status question and the 1823 edition scarcity."),
    ("F07", "F-scifi", "Weird fiction and horror as narrative systems: give 15 legally free "
     "works (Lovecraft where public domain, M.R. James, Blackwood, Machen, Ligotti-adjacent "
     "public domain sources) with Gutenberg/IA identifiers, plus the 8 academic works that "
     "formalize weird fiction as a category."),
    ("F08", "F-scifi", "Golden Age SF pulp: give 20 titles with author, year, magazine and "
     "the copyright status. Name which pulp magazines' contents are lawfully available as "
     "the magazine copyrights expire, with the actual publication years that put them into "
     "public domain."),
    ("F09", "F-scifi", "Modern and contemporary SF with permissive licences: find works "
     "published under Creative Commons or public domain by authors who allow it. Give "
     "author, year, licence, and URL. Also name any SF magazine (e.g. The Future Fire, "
     "Escape Pod, Strange Horizons) with an open-content or CC-ND policy."),
    ("F10", "F-scifi", "Narrative structure in long-form fiction as mechanical design: cite "
     "the 12 academic computational-literature papers that model plot, character or story "
     "structure, with author, year, venue and DOI/arXiv ID. Include any work on story "
     "generation evaluation and on narrative coherence metrics."),
    ("F11", "F-scifi", "Speculative fiction as policy and futures work: give 12 primary "
     "citations with author, year, publisher/venue and DOI/ISBN for science fiction in "
     "policy analysis. Include RAND, the Science Fiction and Policy Exchange, Miller's "
     "Futures Literacy, and any 2020s AI-futures anthology with permissive terms."),
    ("F12", "F-scifi", "Interactive fiction as literature: give 12 legally free works from "
     "the IF tradition with author, year and the exact source (IFDB ID, or a legal "
     "repository URL). Prioritise pre-1990 because that is where public domain sits. Include "
     "Zork, Adventure, Anchor Eclipse, and any Colossal Cave / Scott Adams work with clear "
     "rights."),
    ("F13", "F-scifi", "Children's and young-adult speculative fiction that is legally free: "
     "give 15 works with author, year, and the exact Project Gutenberg ID or Internet "
     "Archive ID. This is the most legally free SF-adjacent shelf in existence because of "
     "children's author copyright extensions expiring."),

    # ================= B. OLD BOOKS -- widening past 1900-1928 polit-psych =============
    ("B01", "B-oldbooks", "The medieval and Renaissance shelf as legally free full text: give "
     "25 specific works with author, death year, and the exact Project Gutenberg ID or "
     "Internet Archive ID. Prioritise Machiavelli, Castiglione, Cellini, Montaigne, "
     "Christine de Pizan, Christine of Pizan."),
    ("B02", "B-oldbooks", "The counter-Enlightenment shelf: give 20 works with author, year "
     "and exact Gutenberg/IA ID. Must include Burke, Tocqueville, Schmitt, de Maistre, "
     "Donoso Cortes, Carlyle, and any 18th-century work already in public domain."),
    ("B03", "B-oldbooks", "Military theory and strategy as design source: give 20 works with "
     "author, year and exact Gutenberg/IA ID. Must include Sun Tzu, Clausewitz's On War, "
     "Jomini, Liddell Hart's Strategy (the direct descendant), and Sun Tzu translations "
     "that are legally free."),
    ("B04", "B-oldbooks", "Economics before the econometrics: give 20 legally free works with "
     "author, year and Gutenberg/IA ID. Prioritise Smith, Ricardo, Marx's Capital vol 1, "
     "Keynes's General Theory status, Hayek, and the early institutional economics."),
    ("B05", "B-oldbooks", "The East Asian shelf: give 20 legally free or permissively licensed "
     "works with author, year and source URL. Prioritise Chinese classics (Sun Tzu, "
     "Mozi, Han Feizi, Xunzi), Japanese (Murasaki, Basho, Tokugawa-era), and any modern "
     "translations with explicit permissive licences."),
    ("B06", "B-oldbooks", "The South Asian shelf: give 15 legally free works with author, "
     "year and Gutenberg/IA ID. Prioritise the Upanishads, the Ramayana, Mahabharata "
     "translations that are free, Panini's grammar scholarship, and any classical "
     "Indian mathematics or logic (Nyaya, Panini)."),
    ("B07", "B-oldbooks", "The African and Caribbean shelf: give 15 legally free works with "
     "author, year and source. Prioritise oral-tradition collections published in public "
     "domain, early colonial ethnographic accounts now out of copyright, and any modern "
     "works with explicit CC licences."),
    ("B08", "B-oldbooks", "Indigenous and Pacific shelf: give 12 works with author or "
     "collective, year, and source. Prioritise public-domain ethnographies, early Pacific "
     "navigation records, and any community-published works under Creative Commons."),
    ("B09", "B-oldbooks", "Science history as narrative: give 15 legally free histories of "
     "science with author, year and Gutenberg/IA ID. Prioritise Whewell's History of the "
     "Inductive Sciences, Tyndall's Faraday, Mach's popular writings, and any history of "
     "mathematics or chemistry with a narrative spine."),
    ("B10", "B-oldbooks", "Mathematics history as narrative: give 15 legally free works with "
     "author, year and Gutenberg/IA ID. Prioritise Euler's Letters, Ball's History of "
     "Mathematics, Bell's Men of Mathematics, and any work on the history of non-Euclidean "
     "geometry or the foundations controversy."),
    ("B11", "B-oldbooks", "Medicine, public health and the body in the old books: give 15 "
     "legally free works with author, year and Gutenberg/IA ID. Prioritise Hippocratic "
     "writings, Galen, Harvey on circulation, Semmelweis, and any public-health or "
     "epidemiology history with a narrative structure."),
    ("B12", "B-oldbooks", "Psychology's pre-1900 shelf: give 15 legally free works with author, "
     "year and Gutenberg/IA ID. Prioritise Lotto's De Anima, Hume's Treatise, James's "
     "Principles, Ribot's Diseases of Personality, Janet, and any pre-Freud psychology."),
    ("B13", "B-oldbooks", "The legal shelf: give 15 legally free works with author, year and "
     "Gutenberg/IA ID. Prioritise Blackstone's Commentaries, Justinian, the Digest, "
     "Bentham, and any work on sovereign immunity or evidence law with a narrative spine."),
    ("B14", "B-oldbooks", "The adventure and exploration shelf as narrative source: give 15 "
     "legally free works with author, year and Gutenberg/IA ID. Prioritise Defoe, "
     "Crusoe-style survival accounts, Hakluyt, Hakluyt Society volumes, and any "
     "expedition narrative whose author died before 1930."),

    # ================= X. CROSS-DOMAIN -- the tools, not the content ==================
    ("X01", "X-cross", "Public-domain bulk corpora with permissive terms that are legally "
     "downloadable TODAY: name 10 specific datasets or libraries (name, owner, licence, URL, "
     "size) suitable for a local research corpus. Prioritise Project Gutenberg's own mirror, "
     "Standard Ebooks, Open Library, Wikisource, and any pre-1929 literary corpus."),
    ("X02", "X-cross", "The exact mechanics of a legal bulk book download: describe the "
     "current Project Gutenberg download URL pattern, the robots.txt or rate-limit "
     "position, the Standard Ebooks repository layout, and what 'public domain in the US' "
     "actually requires for a 1929 work versus a 1931 work. Cite the specific pages."),
    ("X03", "X-cross", "The legal basis for a local personal research corpus: explain the "
     "fair-use versus public-domain boundary for bulk text ingestion, with 5 real legal or "
     "library-science references (with DOI/ISBN) on personal research archiving, and the "
     "specific case law or statute names for US fair use."),
    ("X04", "X-cross", "Open-access text datasets from 2020s that are permissively licensed "
     "and useful for narrative and world-building: name 10 with owner, licence, size, URL, "
     "and one line on what each contains. Prioritise anything with CC-BY or CC0 terms."),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def battery_digest() -> str:
    blob = "|".join(f"{qid}:{q}" for qid, _t, q in BATTERY)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


_THINK_SCAFFOLD = re.compile(
    r"here'?s?\s+(?:a\s+)?thinking\s+process|^\s*#{0,4}\s*(?:\d+\.\s*)?analy[sz]e\s+user\s+request"
    r"|^\s*#{0,4}\s*(?:\d+\.\s*)?identify\s+(?:key|required|the\s+required)"
    r"|^\s*#{0,4}\s*(?:\d+\.\s*)?(?:constraints?|output\s+format|prioritise|prioritize)\s*:",
    re.IGNORECASE | re.MULTILINE,
)
_ANSWER_MARK = re.compile(r"^\s*(?:\*\*)?(?:final\s+)?(?:answer|response|result)s?\b\s*(?:\*\*)?\s*:?\s*$",
                          re.IGNORECASE | re.MULTILINE)
# "Let me list:" / "Here's the list:" / "Final list:" -- the point where this lane stops
# deliberating and starts emitting the actual citations.
_LIST_MARK = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?(?:ok(?:ay)?[,.!]?\s*)?(?:here(?:'s| is)\s+)?"
                        r"(?:the\s+)?(?:final\s+)?(?:list|answer|citations?|works?|references?)\b"
                        r"\s*(?:\*\*)?\s*:?\s*$", re.IGNORECASE)
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")


def _strip_reasoning(answer: str) -> tuple[str, bool]:
    """Cut a leaked reasoning scaffold off an answer, and say whether we cut one.

    MEASURED DEFECT (fan-out, 2026-09-28). `or-nemotron` returns its chain-of-thought as
    `message.content`: 13 of its answers opened with "Here's a thinking process:", and it
    spent the whole token budget DELIBERATING -- "Actually, GT 2304 is...", "I'll check" --
    before emitting a citation list that was itself truncated mid-line at the max_tokens
    boundary. Median length 1,489 words against a 200-word cap, where groq-oss / zai-lite /
    or-ling3 sat at 57-241. So the scaffold is a LANE property, and it inflated this pack's
    median answer length roughly sevenfold.

    The house `call_lane` already guards the same failure family via `empty_content`, but that
    guard only fires when content is EMPTY. Here content is full of reasoning and contains
    some answer, so it passes. Fix: locate the final list block and keep from there.

    Two implementation notes, both learned by looking at the real rows rather than by
    reasoning about them. First, an early version of this function reported stripped=True
    while removing 4 words out of 1,713 -- it flagged the header and then bailed, which is
    the worst possible outcome for a filter: a fix that is counted but does not work. Second,
    `max_tokens` truncation means the tail can be a partial line, so the cut must not assume
    the answer ends cleanly.
    """
    if not _THINK_SCAFFOLD.search(answer):
        return answer, False
    lines = answer.splitlines()
    # 1. explicit answer marker anywhere -> keep everything after the LAST one
    marks = [i for i, ln in enumerate(lines) if _ANSWER_MARK.match(ln)]
    if marks:
        tail = "\n".join(lines[marks[-1] + 1:]).strip()
        if tail:
            return tail, True
    # 2. otherwise: last "let me list:" style marker that is followed by real bullets
    for i in range(len(lines) - 1, -1, -1):
        if _LIST_MARK.match(lines[i]) and any(_BULLET.match(x) for x in lines[i + 1:i + 4]):
            tail = "\n".join(lines[i + 1:]).strip()
            if tail:
                return tail, True
    # 3. last resort: last run of consecutive bullet lines in the body
    best_start = None
    run: list[int] = []
    for i, ln in enumerate(lines):
        if _BULLET.match(ln):
            if run and i == run[-1] + 1:
                run.append(i)
            else:
                if len(run) > len(run) and best_start is None:
                    best_start = run[0]
                run = [i]
        elif ln.strip():
            if len(run) > 2:
                best_start = run[0]
            run = []
    if run and len(run) > 2 and best_start is None:
        best_start = run[0]
    if best_start is not None and best_start > 0:
        return "\n".join(lines[best_start:]).strip(), True
    return answer, False


def _live_lanes(env: dict[str, str]) -> list[dict[str, Any]]:
    """Lanes that have a key AND answer a live probe.

    FIXES A REAL DEFECT IN THE BORROWED MODULE, deliberately not patched at source.
    `mag/research_fanout.run()` does `live = [l for l in LANES if env.get(l["key"])]` -- it
    selects on KEY PRESENCE, not on a live probe, while its own module docstring claims
    "LANES are probed live before use (a stored key is not a live key)". Measured on
    2026-09-28: `or-union-alpha` and `or-glm52` both answer HTTP 404 on probe, yet still
    receive round-robin questions, so 1/6 of a 57-question battery was spent on two dead
    lanes (10 rows of `HTTP 404` on the raw tape in pass 1). Key presence is not liveness.

    We do not edit `mag/research_fanout.py` -- the standing law is read-only on house
    instruments without the operator naming that write. The fix lives in the copy that
    borrows it, and the failure rows stay on the tape as the evidence.

    Cost: one probe per lane, ~6 calls, on a free tier. Falls back to key-presence lanes if
    the probe itself fails for every lane, so this can never turn a working fan-out into a
    dead one.
    """
    keyed = [l for l in LANES if env.get(l["key"])]
    if not keyed:
        return []
    try:
        rows = []
        for lane in keyed:
            r = call_lane(lane, "Reply with exactly: READY", env[lane["key"]], timeout=45)
            rows.append((lane, bool(r.get("ok"))))
        ok_lanes = [l for l, good in rows if good]
        dead = [l["id"] for l, good in rows if not good]
        _LAST_DEAD.clear()
        _LAST_DEAD.update(dead)
        return ok_lanes or keyed
    except Exception:
        return keyed


_LAST_DEAD: dict[str, str] = {}


def battery() -> dict[str, Any]:
    by_theme: dict[str, list[str]] = {}
    for qid, theme, _q in BATTERY:
        by_theme.setdefault(theme, []).append(qid)
    return {"ok": True, "schema": SCHEMA, "battery_digest": battery_digest(),
            "questions": len(BATTERY), "themes": {k: len(v) for k, v in sorted(by_theme.items())},
            "ids_by_theme": by_theme, "cost": "$0 -- free tiers only"}


def _latest_by_qid() -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    if RAW.is_file():
        for ln in RAW.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            qid = r.get("qid")
            if not qid:
                continue
            if qid not in best or (r.get("ok") and not best[qid].get("ok")):
                best[qid] = r
    return best


def _record(rec: dict[str, Any], qid: str, theme: str, q: str, lock: threading.Lock) -> None:
    if rec.get("ok") and rec.get("answer"):
        clean, stripped = _strip_reasoning(rec["answer"])
        if stripped:
            rec["answer_words_before_strip"] = len(rec["answer"].split())
            rec["reasoning_scaffold_stripped"] = True
            rec["answer"] = clean
            rec["chars"] = len(clean)
    rec.update({"qid": qid, "theme": theme, "question": q})
    with lock:
        with RAW.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run(workers: int = 8, timeout: int = 150) -> dict[str, Any]:
    """Pass 1. Every question to a live lane, round-robin. Failures stay on the tape."""
    OUT.mkdir(parents=True, exist_ok=True)
    env = _env()
    live = _live_lanes(env)
    if not live:
        return {"ok": False, "schema": SCHEMA, "error": "no lanes with keys"}
    jobs = [(qid, theme, q, live[n % len(live)]) for n, (qid, theme, q) in enumerate(BATTERY)]
    results: list[dict[str, Any]] = []
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(call_lane, lane, q, env[lane["key"]], timeout): (qid, theme, q, lane)
                for (qid, theme, q, lane) in jobs}
        for f in futs:
            qid, theme, q, lane = futs[f]
            try:
                rec = f.result()
            except Exception as e:  # a child harness failure is not a finding about the corpus
                rec = {"ok": False, "error": f"worker:{type(e).__name__}: {str(e)[:120]}",
                       "lane": lane["id"], "model": lane["model"], "latency_ms": 0}
            _record(rec, qid, theme, q, lock)
            results.append(rec)
    return _summarise(results, pass_no=1)


def retry(workers: int = 4, attempts: int = 3, timeout: int = 200, backoff: float = 5.0) -> dict[str, Any]:
    """Pass 2. Only the unanswered. Appends -- pass 1 is never rewritten or deleted.

    The empty_content failure mode is the reason for max_tokens=3000 here: a reasoning
    model spends the budget inside a reasoning channel and returns message.content == ''.
    """
    env = _env()
    lane_by_id = {l["id"]: l for l in LANES}
    live_ids = [l["id"] for l in _live_lanes(env)]
    got = _latest_by_qid()
    todo = [(i, t, q) for (i, t, q) in BATTERY if not got.get(i, {}).get("ok")]
    if not todo:
        return {"ok": True, "schema": SCHEMA, "note": "nothing to retry", "answered": len(got)}
    winners = [ln for ln in live_ids
               if any(r.get("ok") and r.get("lane") == ln for r in got.values())] or live_ids
    plan = [(qid, theme, q, winners[n % len(winners)]) for n, (qid, theme, q) in enumerate(todo)]
    results: list[dict[str, Any]] = []
    lock = threading.Lock()

    def job(item: tuple[str, str, str, str]) -> dict[str, Any]:
        qid, theme, q, start = item
        order = [start] + [ln for ln in winners if ln != start]
        last: dict[str, Any] = {}
        for n, ln in enumerate(order[:max(1, attempts)]):
            lane = lane_by_id[ln]
            if n:
                time.sleep(backoff * n)
            r = call_lane(lane, q, env[lane["key"]], timeout=timeout, max_tokens=3000, attempt=2)
            r["pass"] = 2
            _record(r, qid, theme, q, lock)
            last = r
            if r.get("ok"):
                break
        return last

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        list(ex.map(job, plan))
    merged = _latest_by_qid()
    return _summarise(list(merged.values()), pass_no=2, retried=len(todo))


def _summarise(rows: list[dict[str, Any]], pass_no: int, retried: int = 0) -> dict[str, Any]:
    ok = [r for r in rows if r.get("ok")]
    lat = sorted(r.get("latency_ms", 0) for r in rows)
    per_theme: dict[str, dict[str, int]] = {}
    for r in rows:
        t = per_theme.setdefault(r.get("theme", "?"), {"answered": 0, "failed": 0})
        t["answered" if r.get("ok") else "failed"] += 1
    s = {
        "ok": True, "schema": SCHEMA, "ts": _now(), "pass": pass_no,
        "battery_digest": battery_digest(), "questions": len(BATTERY),
        "answered": len(ok), "failed": len(rows) - len(ok),
        "retried": retried, "chars": sum(r.get("chars", 0) or 0 for r in ok),
        "per_theme": dict(sorted(per_theme.items())),
        "lanes_used": sorted({r["lane"] for r in rows if r.get("lane")}),
        "per_lane": {ln: {"answered": sum(1 for r in rows if r.get("lane") == ln and r.get("ok")),
                          "failed": sum(1 for r in rows if r.get("lane") == ln and not r.get("ok"))}
                     for ln in sorted({r.get("lane") for r in rows if r.get("lane")})},
        "failures": [{"qid": r.get("qid"), "lane": r.get("lane"), "error": r.get("error")}
                     for r in rows if not r.get("ok")],
        "reasoning_scaffold_stripped": sum(1 for r in rows if r.get("reasoning_scaffold_stripped")),
        "scaffold_note": "answers whose leaked chain-of-thought was cut; see _strip_reasoning",
        "raw": str(RAW), "pack": str(PACK),
        "pack_is_stale": True,
        "pack_stale_note": (
            "This pass wrote a DERIVED pack without the reasoning-strip and without the "
            "hedge/lane-quality columns. Run `python -m mag.corpus_gap_repack` after the last "
            "retry to rebuild the human-facing pack from the append-only tape. Measured "
            "2026-09-28: three concurrent retries each overwrote a cleaned pack, dropping every "
            "HEDGED flag (216,536 B uncleaned vs 158,884 B cleaned). raw.jsonl is never "
            "affected -- it is append-only -- so the rebuild is lossless."
        ),
        "median_latency_ms": lat[len(lat) // 2] if lat else 0,
        "cost": "$0 -- free tiers only (groq, z.ai, OpenRouter :free); "
                "paid keys XAI/ANTHROPIC/OPENAI deliberately excluded",
    }
    _write_pack(rows, s)
    RECEIPT.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return s


def _write_pack(rows: list[dict[str, Any]], s: dict[str, Any]) -> None:
    by_theme: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_theme.setdefault(r.get("theme", "?"), []).append(r)
    L = [
        "# CORPUS GAP RESEARCH — science, science fiction, old books, game design theory",
        "",
        f"*battery_digest `{s['battery_digest']}` · **{s['answered']}/{s['questions']} answered** · "
        f"pass {s['pass']} · lanes {', '.join(s['lanes_used'])} · median latency "
        f"{s['median_latency_ms']} ms · {s['chars']} chars · generated {s['ts']}*",
        "",
        "> **These are LEADS, not facts.** Every answer below is free-tier model output.",
        "> A lead is promoted to a held item only by a byte check: a download that hashes, or a",
        "> path that exists. Free channels DO carry checkable errors — a lane asserting a",
        "> Gutenberg ID or a DOI is a claim until the URL is fetched and hashed.",
        "",
        "> ⚠ **DERIVED PACK — REBUILD BEFORE TRUSTING.** A fan-out pass wrote this file, so the",
        "> reasoning-strip and hedge columns are NOT applied here. Run",
        "> `python -m mag.corpus_gap_repack` to rebuild from the append-only tape. The tape is",
        "> the record; this file is derived from it. Measured 2026-09-28: three concurrent",
        "> retries each overwrote a cleaned pack, dropping every HEDGED flag.",
        "",
        "**Promotion rule for this pack:** fetch the URL → record the sha256 → land the file under",
        "`corpus/library/<theme>/` with a MANIFEST.sha256. Until then the row is a lead.",
        "",
    ]
    if s["failures"]:
        L += ["## Failures (preserved, never smoothed)", ""]
        for f in s["failures"]:
            L.append(f"- `{f['qid']}` on `{f['lane']}` — {f['error']}")
        L.append("")
    L += ["## Per-theme tally", "", "| theme | answered | failed |", "|---|---:|---:|"]
    for t, c in s["per_theme"].items():
        L.append(f"| {t} | {c['answered']} | {c['failed']} |")
    L.append("")
    for theme in sorted(by_theme):
        L += [f"## {theme}", ""]
        for r in sorted(by_theme[theme], key=lambda x: x.get("qid") or ""):
            L.append(f"### {r.get('qid')} — {r.get('question')}")
            L.append(f"*lane `{r.get('lane')}` · {r.get('model')} · {r.get('latency_ms')} ms*")
            L.append("")
            L.append(r.get("answer") or f"**FAILED:** {r.get('error')}")
            L.append("")
    PACK.write_text("\n".join(L), encoding="utf-8")


def status() -> dict[str, Any]:
    got = _latest_by_qid()
    return {
        "ok": True, "schema": SCHEMA, "battery_digest": battery_digest(),
        "questions": len(BATTERY), "answered": len([r for r in got.values() if r.get("ok")]),
        "unanswered": sorted(set(q for q, _t, _x in BATTERY) - set(got)),
        "out": str(OUT), "raw_exists": RAW.is_file(), "pack_exists": PACK.is_file(),
        "borrowed_from": "mag/research_fanout.py (LANES, call_lane, _env, probe_lanes)",
        "cost": "$0 -- free tiers only",
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="corpus-gap-research")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["lanes", "battery", "run", "retry", "status"])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=150)
    a = ap.parse_args(argv)
    out = {"lanes": probe_lanes, "battery": battery, "status": status,
           "run": lambda: run(workers=a.workers, timeout=a.timeout),
           "retry": lambda: retry(workers=max(1, a.workers // 2), timeout=max(200, a.timeout))}[a.cmd]()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str)[:4000])
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
