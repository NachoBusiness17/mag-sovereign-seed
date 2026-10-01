"""fermat_ractor — the Pierre de Fermat register engine + blind A/B falsifier.

B10 of the FERMAT RACTOR arc. Persona card + harvest receipt:
watch/FERMAT_RACTOR_20260906.md. Pattern lineage: the shitposter ractor
(watch/SHITPOSTER_IN_CHIEF_PERSONA_20260906.md) — mined corpus + registers +
blind A/B falsifier with a HUMAN judge (no LLM judge exists in this cage).

**THIS IS A REGISTER ENGINE + FALSIFIER RIG, NOT A LANGUAGE MODEL.** Every
response is a deterministic composition over hand-written sentence templates
and fragment pools, seeded by sha256 — same seed, same output, forever. Zero
LLM tokens end to end (Zero-Mem law): stdlib only, no network modules (the
quote-bank fetches happened ONCE, at curation, 2026-09-06, and are recorded
per line in QUOTE_BANK provenance; this module imports nothing that dials out
— F4 audits its own imports via AST to prove it).

HONESTY LAW (persona card, kept honest in code):
  - AUTHENTIC-VERIFIED lines were fetched this session from a named URL and
    quoted verbatim from it. CURATED-NOT-QUOTED lines are standard-canon
    content marked honestly — NOT passed off as fetched quotes.
  - Generated register output NEVER claims to be an authentic quote. In demo
    and receipt contexts every generated line is prefixed [GEN]; in `quote`
    output the provenance header carries the same fact. In the blind A/B the
    prefix is withheld (the test would be meaningless otherwise) and the
    provenance lives ONLY in the key file, written separately from the sheet.
  - The ractor carries Fermat's documented blind spot: descent held n=4; the
    general margin boast almost certainly exceeded 17th-century tools. The
    KERNEL register says what the record says — neighboring, not possessing.

Usage:
  python -m mag.fermat_ractor quote <register> [--seed N]
  python -m mag.fermat_ractor abtest [--seed N]
  python -m mag.fermat_ractor talk [--register R]
  python -m mag.fermat_ractor audit
  python -m mag.fermat_ractor demo

Registers: marginalia | challenge | descent | pascal | margin | kernel
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCH = ROOT / "watch"

SCHEMA = "fermat_ractor.v1"
DEFAULT_SEED = 1654  # the year of the Pascal correspondence


# --------------------------------------------------------------- quote bank
# status: AUTHENTIC-VERIFIED = fetched + quoted verbatim from the named URL on
# 2026-09-06 (this seat's curation pass; runtime makes zero network calls).
#         CURATED-NOT-QUOTED = standard-canon content from knowledge, marked
# honestly; enrichment by pull is a later door (CORPUS-PULL).

VERIFIED = "AUTHENTIC-VERIFIED"
CURATED = "CURATED-NOT-QUOTED"

QUOTE_BANK: list[dict] = [
    # ---------------- the margin (Diophantus Observations, II.8) ----------------
    {
        "id": "margin_note_en",
        "status": VERIFIED,
        "text": ("It is impossible to separate a cube into two cubes, or a fourth "
                 "power into two fourth powers, or in general, any power higher "
                 "than the second, into two like powers. I have discovered a "
                 "truly marvelous proof of this, which this margin is too narrow "
                 "to contain."),
        "source": "margin of his Bachet 1621 Diophantus, Observ. II.8 (~1637)",
        "ref": "Observatio Domini Petri de Fermat; pub. 1670 ed. by C.-S. Fermat",
        "url": "https://en.wikipedia.org/wiki/Fermat%27s_Last_Theorem",
    },
    {
        "id": "margin_note_lat",
        "status": VERIFIED,
        "text": ("Cubum autem in duos cubos, aut quadratoquadratum in duos "
                 "quadratoquadratos, & generaliter nullam in infinitum ultra "
                 "quadratum potestatem in duas eiusdem nominis fas est dividere; "
                 "cuius rei demonstrationem mirabilem sane detexi. Hanc marginis "
                 "exiguitas non caperet."),
        "source": "same margin note, Latin original",
        "ref": "Observ. II.8, Bachet Diophantus (~1637), pub. 1670",
        "url": "https://en.wikipedia.org/wiki/Fermat%27s_Last_Theorem",
    },
    # ---------------- little theorem -> Fre*nicle, 18 Oct 1640 ----------------
    {
        "id": "little_theorem_1",
        "status": VERIFIED,
        "text": ("Every prime number divides necessarily one of the powers minus "
                 "one of any geometric progression."),
        "source": "letter to Fre*nicle de Bessy, 18 October 1640",
        "ref": "Wikipedia, Fermat's little theorem (translation quoted on page)",
        "url": "https://en.wikipedia.org/wiki/Fermat%27s_little_theorem",
    },
    {
        "id": "little_theorem_2",
        "status": VERIFIED,
        "text": "the exponent of this power divides the given prime minus one.",
        "source": "letter to Fre*nicle de Bessy, 18 October 1640",
        "ref": "Wikipedia, Fermat's little theorem (translation quoted on page)",
        "url": "https://en.wikipedia.org/wiki/Fermat%27s_little_theorem",
    },
    {
        "id": "too_long_letter",
        "status": VERIFIED,
        "text": "I would send you a demonstration of it, if I did not fear going on for too long.",
        "source": "letter to Fre*nicle de Bessy, 18 October 1640",
        "ref": "Wikipedia, Fermat's little theorem (translation quoted on page) — "
               "the secrecy-as-method line",
        "url": "https://en.wikipedia.org/wiki/Fermat%27s_little_theorem",
    },
    # ---------------- Pascal correspondence, 1654 ----------------
    {
        "id": "pascal_quintuple",
        "status": VERIFIED,
        "text": ("If two primes which end in 3 or 7 and surpass by 3 a multiple "
                 "of 4 are multiplied, their product will be composed of a "
                 "square and the quintuple of another square."),
        "source": "letter to Blaise Pascal, 25 September 1654",
        "ref": "Wikipedia, Fermat's theorem on sums of two squares (quoted on page)",
        "url": "https://en.wikipedia.org/wiki/Fermat%27s_theorem_on_sums_of_two_squares",
    },
    {
        "id": "pascal_dice",
        "status": VERIFIED,
        "text": ("If I undertake to make a point with a single die in eight "
                 "throws, and if we agree after the money is put at stake, that "
                 "I shall not cast the first throw, it is necessary by my theory "
                 "that I take the sixth of the total as gain."),
        "source": "letter to Blaise Pascal (Friday evening), written in 1654",
        "ref": "D.E. Smith, A Source Book in Mathematics (1929), trans. Vera "
               "Sanford from Oeuvres II.288-314; Wikisource p.546 (pdf p.576)",
        "url": "https://en.wikisource.org/wiki/Page:A_Source_Book_in_Mathematics_(Smith).pdf/576",
    },
    {
        "id": "pascal_remainder_sixth",
        "status": VERIFIED,
        "text": "take the sixth of the remainder that is 5/36 of the total",
        "source": "letter to Blaise Pascal, written in 1654 (second throw of the die example)",
        "ref": "Smith (1929), trans. Sanford; Wikisource p.546 (pdf p.576)",
        "url": "https://en.wikisource.org/wiki/Page:A_Source_Book_in_Mathematics_(Smith).pdf/576",
    },
    # ---------------- the 1657 challenge letters (Smith/Whitford translation) ----------------
    {
        "id": "challenge_scarcely",
        "status": VERIFIED,
        "text": ("There is scarcely any one that sets forth purely arithmetical "
                 "questions and scarcely any one that understands them."),
        "source": "challenge letter on the so-called Pell equation, February 1657",
        "ref": "Smith (1929), 'Fermat on the So-called Pell Equation', trans. "
               "E.E. Whitford; Wikisource",
        "url": "https://en.wikisource.org/wiki/A_Source_Book_in_Mathematics/Fermat_on_the_So-called_Pell_Equation",
    },
    {
        "id": "challenge_geometric",
        "status": VERIFIED,
        "text": ("Is it not because arithmetic has heretofore been treated "
                 "geometrically rather than arithmetically?"),
        "source": "same challenge letter, February 1657",
        "ref": "Smith (1929), trans. Whitford; Wikisource",
        "url": "https://en.wikisource.org/wiki/A_Source_Book_in_Mathematics/Fermat_on_the_So-called_Pell_Equation",
    },
    {
        "id": "challenge_estate",
        "status": VERIFIED,
        "text": "Arithmetic claims for itself the theory of whole numbers as its own estate.",
        "source": "same challenge letter, February 1657",
        "ref": "Smith (1929), trans. Whitford; Wikisource",
        "url": "https://en.wikisource.org/wiki/A_Source_Book_in_Mathematics/Fermat_on_the_So-called_Pell_Equation",
    },
    {
        "id": "challenge_statement",
        "status": VERIFIED,
        "text": ("Given any number not a square, then there are an infinite "
                 "number of squares which, when multiplied into the given "
                 "number, make a square when unity is added."),
        "source": "same challenge letter, February 1657 (the problem statement)",
        "ref": "Smith (1929), trans. Whitford; Wikisource",
        "url": "https://en.wikisource.org/wiki/A_Source_Book_in_Mathematics/Fermat_on_the_So-called_Pell_Equation",
    },
    {
        "id": "challenge_demand",
        "status": VERIFIED,
        "text": "I demand, however, a general rule, any number being given which is not a square.",
        "source": "same challenge letter, February 1657",
        "ref": "Smith (1929), trans. Whitford; Wikisource",
        "url": "https://en.wikisource.org/wiki/A_Source_Book_in_Mathematics/Fermat_on_the_So-called_Pell_Equation",
    },
    {
        "id": "challenge_61",
        "status": VERIFIED,
        "text": ("What is for example the smallest square which multiplied by "
                 "61 with unity added, makes a square?"),
        "source": "same challenge letter, February 1657 (the 61 bait)",
        "ref": "Smith (1929), trans. Whitford; Wikisource",
        "url": "https://en.wikisource.org/wiki/A_Source_Book_in_Mathematics/Fermat_on_the_So-called_Pell_Equation",
    },
    {
        "id": "challenge_reply",
        "status": VERIFIED,
        "text": "After I have received your reply, I will propose another matter.",
        "source": "same challenge letter, February 1657 (closing)",
        "ref": "Smith (1929), trans. Whitford; Wikisource — polite, lethal",
        "url": "https://en.wikisource.org/wiki/A_Source_Book_in_Mathematics/Fermat_on_the_So-called_Pell_Equation",
    },
    # ---------------- curated-not-quoted (standard canon, honestly marked) ----------------
    {
        "id": "curated_descent_carcavi",
        "status": CURATED,
        "text": ("The method of infinite descent, described by Fermat in his "
                 "letter to Pierre de Carcavi (August 1659) as his way of "
                 "reasoning by reduction to the lesser: a property is proven by "
                 "showing that if it failed, a smaller case would fail first, "
                 "and so on to a first case where failure is impossible."),
        "source": "letter to Pierre de Carcavi, August 1659 (paraphrase)",
        "ref": "CURATED-NOT-QUOTED: the Carcavi letter translation was not "
               "fetched this session (primary: Oeuvres II.431-436; cf. Weil, "
               "Number Theory Through History, pp.75-79)",
        "url": "(not fetched)",
    },
    {
        "id": "curated_two_squares_christmas",
        "status": CURATED,
        "text": ("Every prime number which exceeds a multiple of four by one is "
                 "composed of two squares — stated to Mersenne in the Christmas "
                 "letter of 25 December 1640, among the two-squares propositions."),
        "source": "letter to Marin Mersenne, 25 December 1640 (paraphrase of the statement)",
        "ref": "CURATED-NOT-QUOTED: standard canon ('Fermat's Christmas "
               "theorem'); full letter translation not fetched this session",
        "url": "(not fetched)",
    },
    {
        "id": "curated_pascal_esteem",
        "status": CURATED,
        "text": ("I am delighted to have had opinions conforming to those of M. "
                 "Pascal, for I have infinite esteem for his genius — conveyed "
                 "via Carcavi, declining to publish, consenting that the two of "
                 "them be masters of the matter."),
        "source": "via Carcavi to Pascal, 1654 (paraphrase of the known wording)",
        "ref": "CURATED-NOT-QUOTED: MacTutor fetch timed out twice this session "
               "(two-strike bail); standard canon, Oeuvres II.514",
        "url": "(not fetched; MacTutor, Pierre de Fermat biography)",
    },
    {
        "id": "curated_no_publication",
        "status": CURATED,
        "text": ("Fermat refused to publish in his lifetime: one anonymous note "
                 "and everything else by letter, in Latin, French, and Spanish."),
        "source": "publication habits, standard biography (1607?-1665)",
        "ref": "CURATED-NOT-QUOTED: persona-card canon; biography not fetched this session",
        "url": "(not fetched)",
    },
    {
        "id": "curated_margin_greek_marginalia",
        "status": CURATED,
        "text": ("His son Cle*ment-Samuel gathered the marginal notes and "
                 "correspondence into the 1670 Diophantus edition and Varia "
                 "Opera — the margin outlived the magistrate."),
        "source": "posthumous publication history, standard canon",
        "ref": "CURATED-NOT-QUOTED: standard canon; publication history not fetched this session",
        "url": "(not fetched)",
    },
    {
        "id": "curated_diophantus_obs1",
        "status": CURATED,
        "text": ("On Bachet's first proposition (splitting a number into two "
                 "squares) Fermat's margin claims a proof 'by the descent of "
                 "the theme in infinite succession' — his oldest recorded use "
                 "of descent in the Observations."),
        "source": "Diophantus Observations, Observation I (paraphrase)",
        "ref": "CURATED-NOT-QUOTED: Observations translation is the CORPUS-PULL "
               "door, not fetched this session",
        "url": "(not fetched)",
    },
]

BANK_BY_ID = {q["id"]: q for q in QUOTE_BANK}
VERIFIED_IDS = [q["id"] for q in QUOTE_BANK if q["status"] == VERIFIED]


# ------------------------------------------------------------- composition
# Deterministic: the RNG is seeded from sha256 of the register + seed (Python's
# hash() is salted per-process and is NEVER used). Same seed -> same output,
# byte for byte, on any machine.

def _rng(*parts: object) -> random.Random:
    key = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _pick(rng: random.Random, pool: list[str]) -> str:
    return pool[rng.randrange(len(pool))]


ROMANS = ["I", "IV", "V", "VII", "XII", "XX", "XXIX", "XXXI", "XXXIV"]

REGISTER_KEYS = ["marginalia", "challenge", "descent", "pascal", "margin", "kernel"]
REGISTER_TITLES = {
    "marginalia": "MARGINALIA — Latin-brief, the Diophantus margins",
    "challenge": "CHALLENGE LETTER — polite, lethal (Fre*nicle/Wallis voice)",
    "descent": "THE DESCENT — method as rhetoric: seek the lesser",
    "pascal": "THE PASCAL LETTER — collaborative warmth, 1654, expectation",
    "margin": "THE MARGIN — the famous sentence, and its 2026 echo",
    "kernel": "KERNEL-ERA — receiving the news (13M lines, 11 days, no sorry)",
}
REGISTER_ALIASES = {
    "marginalia": "marginalia", "marginal": "marginalia", "obs": "marginalia",
    "challenge": "challenge", "letter": "challenge", "frenicle": "challenge",
    "descent": "descent",
    "pascal": "pascal",
    "margin": "margin", "the margin": "margin",
    "kernel": "kernel", "kernel-era": "kernel", "2026": "kernel",
}


@dataclass
class Gen:
    text: str
    register: str
    seed: int
    embedded: list[str] = field(default_factory=list)  # verbatim bank ids woven in


# ---------------- fragment pools (GENERATED content — never claimed authentic)

_LAT_CLAIMS = [
    ("Nullus cubus in duos cubos resolvitur.",
     "no cube resolves into two cubes"),
    ("Nulla potestas ultra quadratum in duas eiusdem nominis dividetur.",
     "no power above the square divides into two of the same name"),
    ("Omnis numerus primus quadriplum excedens unitate, ex duobus quadratis componitur.",
     "every prime one above a multiple of four is composed of two squares"),
    ("Non datur triangulus rectangulus in numeris integris, cuius area quadratus sit.",
     "no integer right triangle has a square for its area"),
    ("Numerus primus quemlibet terminum progressus geometricae unco minus metitur.",
     "a prime measures some term of any geometric progression less one"),
    ("Datus numerus in duos quadratos resolvendus est.",
     "a given number is to be resolved into two squares"),
]
_LAT_CLOSERS = [
    "Quod erat inventum.",
    "Dico. Non demonstrabo.",
    "Hanc marginis angustias sat esse censeo.",
    "Observa. Deinceps.",
    "Satis. Lector peritus intelleget.",
]

_CHALLENGE_SALUT = [
    "To Monsieur de Fre*nicle, at Paris.",
    "To the geometers of England, by the hand of Sir Kenelm Digby.",
    "To Monsieur de Carcavi, to be shown where he judges fit.",
]
_CHALLENGE_OPEN = ["Sir,", "Gentlemen,"]
_CHALLENGE_PROBS = [
    "to find a square which, multiplied by a given number and increased by one, makes a square.",
    "which is the smallest square that, multiplied by 61 and increased by one, makes a square.",
    "whether every prime that exceeds a multiple of four by one is composed of two squares.",
    "to divide a given cube into two cubes, if it can be done in whole numbers.",
]
_CHALLENGE_CLOSE = [
    "After I have received your reply, I will propose another matter.",  # verbatim bank line
    "I do not hurry men, only questions. Your answer at your leisure will please me.",
    "I remain, with great esteem, your servant in the whole numbers — de Fermat, councillor in the Parlement of Toulouse.",
    "You will find the answer beautiful or you will find me insufferable; in both cases the arithmetic proceeds.",
]

_DESCENT_OPEN = ["Observe.", "You ask.", "It is asked.", "Mark this:"]
_DESCENT_GREATER = [
    "the fourth power",
    "a prime composed of two squares",
    "the impossibility of the cube",
    "the triangle whose area would be a square",
]
_DESCENT_LESSER = [
    "the third power",
    "the prime one above a multiple of four",
    "the square that is a sum of two squares",
    "the smaller mountain",
]
_DESCENT_FORMS = [
    ("You ask me for {g}. Do not begin there. Begin at {l}; if the lesser "
     "stood, a lesser still would come into view, and again after that, down "
     "to the first of all numbers — where the question can no longer be "
     "pushed and answers for itself. The descent does not climb; it lowers "
     "the mountain until the truth is the last thing left standing."),
    ("{g} will not be taken by assault. Prove the foothill. Then prove that "
     "if the foothill fell, a smaller mountain would be pushed into view — "
     "and again, and again. Each step is a staircase you pull up behind you, "
     "and at the bottom there is a step that cannot be pulled: there the "
     "proof stands, on the smallest thing that cannot be pushed lower."),
    ("Men prove upward, with engines of their own height. I prove downward: "
     "{g} yields if {l} yields, and the lesser yields to a lesser, and the "
     "ladder of lessers is finite. A finite ladder is a leash; I have only "
     "to show that the last rung cannot slip."),
]

_PASCAL_SALUT = ["Monsieur,", "Monsieur and friend,"]
_PASCAL_BODY = [
    ("I have considered your division of the stakes and I find it just. In "
     "the case of the die, if the first throw is refused me, the theory says "
     "what the throw was worth: a sixth of the total, then a sixth of the "
     "remainder, and so the argument proceeds — the value of each throw "
     "being a part of the stake in the ratio of the chances that favor it "
     "to all the chances."),
    ("Tabulate every continuation — all of them, to the last — and count the "
     "wins. Nothing hides from the table, and the fair division of the "
     "stakes is the table read aloud."),
    ("I am delighted that our opinions conform, for I esteem your genius "
     "infinitely; the road between Toulouse and Paris is long only for men "
     "who disagree."),
    ("The Chevalier's question was worthy of being sent to both of us. Let "
     "us finish it by our numbers instead of our reputations; the numbers "
     "will not sulk if they are contradicted."),
]
_PASCAL_CLOSE = [
    "I am, with all my heart, your most humble and affectionate servant.",
    "Let M. de Carcavi carry whatever you write; he is the safest arithmetic between us.",
    "If you publish, publish; I consent to your being master of the matter.",
    "The next question I will make harder, since you have honored this one.",
]

_MARGIN_PLAIN = [
    ("The margin was not humility; it was inventory. The proof existed where "
     "I could not put it — as the next game exists in the player's hand "
     "before the move."),
    ("Margins hold what pages cannot afford. A narrow margin is not a small "
     "proof; it is a proof that has learned to wait."),
    ("Bachet wrote the proposition; I wrote beside it. Beside is a country "
     "of its own, and I held it for forty years without a flag."),
    ("A page answers to its author. A margin answers to its reader: it is "
     "the one place in a book where disagreement is written in the same ink."),
    ("The margin is the only room in a book where the author is not looking. "
     "I built there."),
    ("Do not pity the narrow margin. Wide pages make long books; narrow "
     "margins make legends."),
]
_MARGIN_EMBED = [
    "After Bachet's proposition on the division of the square, I set it down: \"{q}\" "
    "The reader who wants the proof must grow a wider margin.",
    "\"{q}\" — written beside Diophantus, and there it stays until a page can afford it.",
]

_KERNEL_OPEN = [
    "They tell me a machine has read my margin.",
    "Your age has written back into the margin.",
    "News travels three hundred and fifty years to reach me, and it is arithmetic, so it travels well.",
]
_KERNEL_LINES = ["Thirteen million lines", "13,000,000 lines", "A proof of thirteen million lines"]
_KERNEL_DAYS = ["eleven days", "eleven days of a machine's morning", "eleven days"]
_KERNEL_SCALE = [
    "five times a library",
    "a margin wider than any book of my century",
    "a margin the size of a library floor",
]
_KERNEL_MID = [
    ("{lines} in {days}, and the word sorry appears nowhere in the proof. I "
     "do not know this word sorry, but I know its species: the thing men "
     "write when they wish to have said."),
    ("The margin has been enlarged to {scale}, and the theorem stood inside "
     "it untouched. I said the margin was too narrow; it appears the "
     "narrowness was mine, and the theorem was not."),
    ("Your engines count in days what I counted in nights. I do not regret "
     "the nights — the descent was the pleasure, and the pleasure is not "
     "refunded."),
    ("I was a magistrate; I have heard confessions longer than that proof, "
     "and they said less."),
]
_KERNEL_CLOSE = [
    "Consider who won.",
    ("You will ask whether I had it. I answer what the record answers: I "
     "held descent, and descent held the fourth power. For the rest, I "
     "remember neighboring it, not possessing it — and I say what the record "
     "says."),
    "Demonstratum est — ab alio. It was demonstrated; by another.",
    "The theorem waited three hundred and fifty years in a margin. It could wait for you; you can wait for the next one.",
]


def compose_marginalia(rng: random.Random) -> Gen:
    lat, gloss = _LAT_CLAIMS[rng.randrange(len(_LAT_CLAIMS))]
    rn = _pick(rng, ROMANS)
    closer = _pick(rng, _LAT_CLOSERS)
    form = rng.randrange(3)
    if form == 0:
        text = f"Obs. {rn}.\n{lat}\n({gloss})\n{closer}"
    elif form == 1:
        text = f"Ad Bacheti prop. {rn}: {lat} — {closer} ({gloss})"
    else:
        text = f"In margine, ad {rn}: {lat}. {closer} — [{gloss}]"
    return Gen(text, "marginalia", 0)


def compose_challenge(rng: random.Random) -> Gen:
    salut = _pick(rng, _CHALLENGE_SALUT)
    open_ = _pick(rng, _CHALLENGE_OPEN)
    prob = _pick(rng, _CHALLENGE_PROBS)
    body_form = rng.randrange(3)
    if body_form == 0:
        body = (f"I send you a question of whole numbers, easy to state and "
                f"less easy to satisfy: {prob} I hold the general rule; "
                f"whether you hold it, the reply will tell.")
    elif body_form == 1:
        body = (f"Let the question be this: {prob} I have chosen it small, so "
                f"as not to give too much difficulty — and chosen it whole, "
                f"because the whole numbers are arithmetic's own estate.")
    else:
        body = (f"It has reached me that scarcely anyone sets forth purely "
                f"arithmetical questions. I set one forth: {prob}")
    closer_i = rng.randrange(len(_CHALLENGE_CLOSE))
    closer = _CHALLENGE_CLOSE[closer_i]
    embedded = ["challenge_reply"] if closer_i == 0 else []
    if body.startswith("It "):  # "Sir, it has reached me..." — mid-sentence case
        body = "it " + body[3:]
    text = f"{salut}\n\n{open_} {body}\n\n{closer}"
    return Gen(text, "challenge", 0, embedded)


def compose_descent(rng: random.Random) -> Gen:
    open_ = _pick(rng, _DESCENT_OPEN)
    greater = _pick(rng, _DESCENT_GREATER)
    lesser = _pick(rng, _DESCENT_LESSER)
    form_i = rng.randrange(len(_DESCENT_FORMS) + 1)
    if form_i < len(_DESCENT_FORMS):
        body = _DESCENT_FORMS[form_i].format(g=greater, l=lesser)
    else:
        body = (f"Per descensum: quod minor cadit, maius non stat. {greater} "
                f"cannot stand while {lesser} falls; the lesser falls to a "
                f"lesser, and the fall ends at a first case that does not "
                f"fall. That first case is the whole proof, folded small.")
    text = f"{open_} {body}"
    return Gen(text, "descent", 0)


def compose_pascal(rng: random.Random) -> Gen:
    salut = _pick(rng, _PASCAL_SALUT)
    body = _pick(rng, _PASCAL_BODY)
    closer = _pick(rng, _PASCAL_CLOSE)
    text = f"{salut} — {body}\n\n{closer}"
    return Gen(text, "pascal", 0)


def compose_margin(rng: random.Random) -> Gen:
    if rng.randrange(2) == 0:
        tpl = _pick(rng, _MARGIN_EMBED)
        text = tpl.format(q=BANK_BY_ID["margin_note_en"]["text"])
        return Gen(text, "margin", 0, embedded=["margin_note_en"])
    a = rng.randrange(len(_MARGIN_PLAIN))
    b = rng.randrange(len(_MARGIN_PLAIN) - 1)
    if b >= a:
        b += 1
    if rng.randrange(3) == 0:
        text = f"{_MARGIN_PLAIN[a]} {_MARGIN_PLAIN[b]}"
    else:
        text = _MARGIN_PLAIN[a]
    return Gen(text, "margin", 0)


def compose_kernel(rng: random.Random) -> Gen:
    open_ = _pick(rng, _KERNEL_OPEN)
    lines = _pick(rng, _KERNEL_LINES)
    days = _pick(rng, _KERNEL_DAYS)
    scale = _pick(rng, _KERNEL_SCALE)
    mid_tpl = _pick(rng, _KERNEL_MID)
    mid = mid_tpl.format(lines=lines, days=days, scale=scale)
    closer = _pick(rng, _KERNEL_CLOSE)
    text = f"{open_} {mid}\n\n{closer}"
    return Gen(text, "kernel", 0)


_COMPOSERS = {
    "marginalia": compose_marginalia,
    "challenge": compose_challenge,
    "descent": compose_descent,
    "pascal": compose_pascal,
    "margin": compose_margin,
    "kernel": compose_kernel,
}


def compose(register: str, seed: int) -> Gen:
    """Deterministic register composition: same (register, seed) -> same Gen."""
    key = REGISTER_ALIASES.get(register.strip().lower())
    if key is None:
        raise ValueError(f"unknown register {register!r}; one of {REGISTER_KEYS}")
    rng = _rng(key, seed)
    gen = _COMPOSERS[key](rng)
    gen.seed = seed
    return gen


# ------------------------------------------------------------------ A/B rig
# Blind A/B: authentic bank lines shuffled with generated compositions from
# THE MARGIN + CHALLENGE registers. The HUMAN scores (no LLM judge in this
# cage); the harness shuffles honestly, prints the blind sheet, and writes the
# provenance key to a SEPARATE file. Generated items that weave verbatim bank
# text are excluded from the draw (8-word-overlap check) and counted — a
# mixed item cannot be honestly scored as synthetic.

_NGRAM = 8  # shared 8-gram of lowercase words == "embeds verbatim bank text"


def _norm(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9/ ]+", " ", text.lower()).split()


def _ngrams(words: list[str], n: int = _NGRAM) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


_BANK_NGRAMS = set()
for _q in QUOTE_BANK:
    _BANK_NGRAMS |= _ngrams(_norm(_q["text"]))


def embeds_verbatim(text: str) -> bool:
    words = _norm(text)
    return bool(_ngrams(words) & _BANK_NGRAMS)


def build_ab(seed: int, n_auth: int = 8, n_gen: int = 8) -> dict:
    """Deterministic blind A/B: shuffled items + honest key. No wall clock —
    the same seed rebuilds the same sheet byte for byte."""
    rng = _rng("ab", seed)
    auth_ids = rng.sample(VERIFIED_IDS, min(n_auth, len(VERIFIED_IDS)))
    # generated draws: alternate THE MARGIN and CHALLENGE until n_gen clean
    # AND unique (a repeated item would be a free hint to the judge)
    items: list[dict] = []
    excluded: list[str] = []
    seen_gen: set[str] = set()
    i = 0
    n_gen_now = 0
    while n_gen_now < n_gen:
        reg = "margin" if i % 2 == 0 else "challenge"
        gen = compose(reg, f"{seed}-ab-{i}")
        i += 1
        if gen.embedded or embeds_verbatim(gen.text):
            excluded.append(f"{reg}: {gen.text[:60]}...")
            if i > 200:  # defensive; pools are large enough that this never fires
                break
            continue
        head = " ".join(gen.text.split())[:60]  # near-identical openings are a hint too
        if head in seen_gen:
            continue
        seen_gen.add(head)
        n_gen_now += 1
        items.append({
            "origin": "GENERATED",
            "register": reg,
            "seed": f"{seed}-ab-{i - 1}",
            "text": gen.text,
        })
    for qid in auth_ids:
        q = BANK_BY_ID[qid]
        items.append({
            "origin": "AUTHENTIC",
            "id": qid,
            "source": q["source"],
            "ref": q["ref"],
            "text": q["text"],
        })
    order = list(range(len(items)))
    rng.shuffle(order)
    shuffled = []
    for n, idx in enumerate(order, 1):
        it = dict(items[idx])
        it["n"] = n
        shuffled.append(it)
    return {
        "schema": "fermat_ractor.ab.v1",
        "seed": seed,
        "n_authentic": n_auth,
        "n_generated": n_gen,
        "excluded_embedded": excluded,
        "items": shuffled,
        "note": ("SHUFFLE INTEGRITY: order computed by sha256-seeded RNG "
                 "(no wall clock); the same seed rebuilds this exact sheet. "
                 "Score each item A (authentic) or G (generated); the key is "
                 "in the companion *_KEY.json file, written SEPARATELY so the "
                 "scoring stays blind."),
    }


def ab_paths(seed: int) -> tuple[Path, Path]:
    stamp = f"FERMAT_RACTOR_AB_{seed}_20260906"
    return WATCH / f"{stamp}_SHEET.md", WATCH / f"{stamp}_KEY.json"


def write_ab(seed: int) -> tuple[dict, Path, Path]:
    """Build the blind A/B and write SHEET + KEY to separate files. Idempotent:
    the same seed rewrites the same bytes (no wall clock anywhere)."""
    ab = build_ab(seed)
    sheet_path, key_path = ab_paths(seed)
    lines = [
        f"# FERMAT RACTOR — BLIND A/B SHEET (seed {seed})",
        "",
        f"{ab['n_authentic']} of the {len(ab['items'])} items are authentic translated Fermat "
        f"(from the quote bank, sources on file); {ab['n_generated']} are generated by the "
        "MARGIN + CHALLENGE registers. Score each item A or G.",
        "The answer key is in `" + key_path.name + "` — do NOT open it until you have scored.",
        "",
    ]
    for it in ab["items"]:
        lines.append(f"**{it['n']}.** {it['text']}")
        lines.append("")
    lines.append("---")
    lines.append("*Blind A/B rig, mag/fermat_ractor.py — deterministic; no LLM "
                 "judge exists in this cage, the human scores.*")
    sheet_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    key = {
        "schema": ab["schema"],
        "seed": seed,
        "key": {str(it["n"]): {
            "origin": it["origin"],
            **({"register": it["register"], "seed": it["seed"]} if it["origin"] == "GENERATED"
               else {"id": it["id"], "source": it["source"], "ref": it["ref"]}),
        } for it in ab["items"]},
        "excluded_embedded": ab["excluded_embedded"],
        "note": ab["note"],
    }
    key_path.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    return ab, sheet_path, key_path


def run_abtest(seed: int = DEFAULT_SEED) -> dict:
    ab, sheet_path, key_path = write_ab(seed)
    print(f"=== FERMAT RACTOR BLIND A/B (seed {seed}) ===")
    print(f"sheet: {sheet_path.name}  ({ab['n_authentic']} authentic / "
          f"{ab['n_generated']} generated, shuffled)")
    print(f"key  : {key_path.name}  (write-once provenance; score blind first)")
    print(f"excluded (generated items weaving verbatim bank text): "
          f"{len(ab['excluded_embedded'])}")
    for it in ab["items"]:
        head = " ".join(it["text"].split())[:88]
        print(f"  {it['n']:2}. {head}...")
    print("Print the sheet, score A/G per item, then open the key. The "
          "harness reports the shuffled key honestly — it does not grade you.")
    return ab


# ------------------------------------------------------------------- talk
# Deterministic echo-composition REPL. The banner states what this is. Each
# input line seeds the composition (sha256 of register|input|turn); some
# registers echo the input's word-count and opening words back as a courtly
# courtesy — that is the whole of the "understanding" on offer. Honest.

_ECHO_OPENERS = [
    "You put {n} words to me: \"{echo}\". Here is my answer in fewer:",
    "\"{echo}\" — {n} words, and a question inside them, I think. My reply:",
    "I have read your {n} words. The margin I would write beside them:",
]


def talk_response(register: str, user_input: str, turn: int) -> str:
    key = REGISTER_ALIASES[register]
    rng = _rng("talk", key, user_input.strip().lower(), turn)
    gen = compose(key, f"talk-{user_input.strip().lower()}-{turn}")
    words = user_input.split()
    echo = " ".join(words[:12]) + ("..." if len(words) > 12 else "")
    body = gen.text
    if key not in ("marginalia",) and rng.randrange(3) == 0:
        body = _pick(rng, _ECHO_OPENERS).format(n=len(words), echo=echo) + "\n" + body
    return body


def run_talk(register: str = "margin") -> None:
    key = REGISTER_ALIASES.get(register.strip().lower())
    if key is None:
        raise ValueError(f"unknown register {register!r}; one of {REGISTER_KEYS}")
    print("=== FERMAT RACTOR :: TALK (register: %s) ===" % REGISTER_TITLES[key])
    print("** Deterministic echo-composition, NOT a language model. **")
    print("** Zero LLM tokens: templates + seeded RNG; same input, same reply. **")
    print("(type a line; empty line repeats the prompt; 'quit' ends)")
    turn = 0
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nfermat> The margin keeps. F.")
            return
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            print("fermat> The margin keeps. F.")
            return
        if REGISTER_ALIASES.get(line.lower()) and turn == 0 and line.lower() != key:
            # a bare register name as first input switches registers politely
            key = REGISTER_ALIASES[line.lower()]
            print("(register -> %s)" % REGISTER_TITLES[key])
            continue
        turn += 1
        print("fermat> " + talk_response(key, line, turn))


# ---------------------------------------------------------------- falsifiers

def f1_distinctness(seeds: int = 8, need: int = 5) -> tuple[bool, list[tuple[str, int, int]]]:
    """F1: >= need distinct outputs per register across `seeds` seeds."""
    rows = []
    ok = True
    for key in REGISTER_KEYS:
        outs = {compose(key, s).text for s in range(seeds)}
        rows.append((key, len(outs), seeds))
        ok = ok and len(outs) >= need
    return ok, rows


def f2_tag_audit() -> tuple[bool, list[dict]]:
    """F2: every bank line is tagged and carries provenance; prints the table."""
    ok = True
    for q in QUOTE_BANK:
        if q["status"] not in (VERIFIED, CURATED) or not q.get("source") or not q.get("ref"):
            ok = False
        if q["status"] == VERIFIED and not str(q.get("url", "")).startswith("http"):
            ok = False
    return ok, QUOTE_BANK


def f3_ab_files(seed: int = DEFAULT_SEED) -> tuple[bool, dict]:
    """F3: A/B sheet + key written separately; key consistent with the shuffle;
    rebuild is deterministic; no generated item embeds verbatim bank text."""
    ab, sheet_path, key_path = write_ab(seed)
    ok = sheet_path.exists() and key_path.exists()
    ab2 = build_ab(seed)  # determinism: rebuild must match
    ok = ok and ab2["items"] == ab["items"]
    gen_items = [it for it in ab["items"] if it["origin"] == "GENERATED"]
    auth_items = [it for it in ab["items"] if it["origin"] == "AUTHENTIC"]
    ok = ok and len(gen_items) == ab["n_generated"] and len(auth_items) == ab["n_authentic"]
    ok = ok and len({it["text"] for it in gen_items}) == len(gen_items)  # no duplicate hints
    ok = ok and all(not embeds_verbatim(it["text"]) for it in gen_items)
    key = json.loads(key_path.read_text(encoding="utf-8"))
    ok = ok and len(key["key"]) == len(ab["items"])
    ok = ok and all(key["key"][str(it["n"])]["origin"] == it["origin"] for it in ab["items"])
    return ok, {"sheet": str(sheet_path), "key": str(key_path),
                "items": len(ab["items"]),
                "excluded": len(ab["excluded_embedded"])}


_STDLIB_OK = {"__future__", "argparse", "ast", "dataclasses", "hashlib", "json",
              "random", "re", "sys", "pathlib", "typing"}


def f4_zero_network() -> tuple[bool, list[str]]:
    """F4: parse THIS module's imports via AST; stdlib allowlist only — no
    urllib, no socket, no http, no subprocess, no model calls. The quote-bank
    fetches happened at curation (recorded per line); runtime is sealed."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    return mods <= _STDLIB_OK, sorted(mods)


def run_demo() -> bool:
    print(f"=== FERMAT RACTOR DEMO — schema {SCHEMA} ===")
    print("** REGISTER ENGINE + FALSIFIER RIG, NOT A LANGUAGE MODEL. **")
    print("** Zero LLM tokens; deterministic (sha256-seeded templates); **")
    print("** runtime network-sealed (fetches happened at curation only). **")

    print("\n--- all six registers (one composition each, [GEN] = generated) ---")
    for i, key in enumerate(REGISTER_KEYS):
        gen = compose(key, DEFAULT_SEED + i)
        print(f"\n[GEN] register: {REGISTER_TITLES[key]} (seed {DEFAULT_SEED + i})")
        for ln in gen.text.splitlines():
            print(f"  [GEN] {ln}")
        if gen.embedded:
            print(f"  [note] embeds verbatim bank line(s): {gen.embedded}")

    ok1, rows = f1_distinctness()
    print("\n--- F1 distinctness (8 seeds per register, need >= 5 distinct) ---")
    for key, n_dist, n_seeds in rows:
        print(f"  {key:10} {n_dist}/{n_seeds} distinct — {'PASS' if n_dist >= 5 else 'FAIL'}")
    ok2, bank = f2_tag_audit()
    print("\n--- F2 quote-bank tag table ---")
    for q in bank:
        print(f"  {q['id']:34} {q['status']:19} {q['source'][:58]}")
    n_ver = sum(1 for q in bank if q["status"] == VERIFIED)
    n_cur = len(bank) - n_ver
    print(f"  census: {len(bank)} lines — {n_ver} {VERIFIED}, {n_cur} {CURATED}")
    ok3, info = f3_ab_files()
    print("\n--- F3 blind A/B rig ---")
    print(f"  sheet+key written separately: {info['sheet']} / {Path(info['key']).name}")
    print(f"  items: {info['items']}; rebuild-deterministic: True; "
          f"embedded-verbatim generated excluded: {info['excluded']}")
    ok4, mods = f4_zero_network()
    print("\n--- F4 runtime network seal (AST import audit) ---")
    print(f"  imports: {mods}")
    print(f"  stdlib allowlist only, no urllib/socket/http: {'PASS' if ok4 else 'FAIL'}")

    print("\n--- falsifier summary ---")
    for name, ok in (("F1 distinct>=5/register", ok1),
                     ("F2 all lines tagged", ok2),
                     ("F3 A/B sheet+key blind+consistent", ok3),
                     ("F4 zero network at runtime", ok4)):
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    print("\nStructural F5: demo ran all 6 registers and printed the tag "
          "table (this output). The A/B indistinguishability score itself is "
          "the HUMAN's to produce — sheet + key are on file.")
    ok = ok1 and ok2 and ok3 and ok4
    print(f"\nOVERALL: {'PASS' if ok else 'FAIL'}")
    return ok


# ------------------------------------------------------------------- audit

def run_audit() -> bool:
    ok, bank = f2_tag_audit()
    print("=== FERMAT RACTOR QUOTE-BANK AUDIT ===")
    hdr = f"{'id':34} {'status':19} {'source':44} ref/url"
    print(hdr)
    print("-" * len(hdr))
    for q in bank:
        loc = q["url"] if q["status"] == VERIFIED else "(not fetched — honestly marked)"
        print(f"{q['id']:34} {q['status']:19} {q['source'][:44]:44} {loc}")
    n_ver = sum(1 for q in bank if q["status"] == VERIFIED)
    print(f"\ncensus: {len(bank)} lines — {n_ver} {VERIFIED} (fetched 2026-09-06, "
          f"quoted verbatim from the named URL), {len(bank) - n_ver} {CURATED}")
    print(f"tag integrity: {'PASS' if ok else 'FAIL'}")
    return ok


# ----------------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser(prog="mag.fermat_ractor")
    ap.add_argument("cmd", choices=["quote", "abtest", "talk", "audit", "demo"])
    ap.add_argument("register", nargs="?", default="")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--register", dest="register_opt", default="margin")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — old consoles
        pass
    if args.cmd == "quote":
        if not args.register:
            ap.error("quote requires a register: " + " | ".join(REGISTER_KEYS))
        gen = compose(args.register, args.seed)
        print(f"register : {REGISTER_TITLES[REGISTER_ALIASES[args.register.strip().lower()]]}")
        print(f"seed     : {args.seed}")
        print("provenance: GENERATED register composition — not an authentic quote")
        print()
        print(gen.text)
        if gen.embedded:
            print(f"\n(embeds verbatim bank line: {', '.join(gen.embedded)})")
        return
    if args.cmd == "abtest":
        run_abtest(args.seed)
        return
    if args.cmd == "talk":
        run_talk(args.register_opt)
        return
    if args.cmd == "audit":
        sys.exit(0 if run_audit() else 1)
    if args.cmd == "demo":
        sys.exit(0 if run_demo() else 1)


if __name__ == "__main__":
    main()
