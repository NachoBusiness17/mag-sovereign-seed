"""republic — correspondence engine for the Republic of Letters.

B11 of the REPUBLIC OF LETTERS arc. Charter: watch/REPUBLIC_OF_LETTERS_20260906.md.
Commission: "Bring in all geniuses and their correspondence to each other —
recreate them and give them an Internet." Historically the res publica
literaria: Mersenne's mailbox was the 17th century's Internet — he copied,
forwarded, provoked; Fermat never published, he corresponded. We give the
recreated minds the network they actually had (letters, routing, shared
problems) plus the thing they never had: THE MARGIN's statement-DAG as the
shared to-do list, the kernel as arbiter.

Fleet translation, what this file implements:
  - letter schema (from/to/cc/in-reply-to/body/claims[]/dag_refs[]), persisted
    APPEND-ONLY at state/republic_letters.json: a retracted letter is
    superseded_by another, never deleted or edited — house chain law, enforced
    at save time (the guard is in code, not in prose).
  - citizen registry (LIVE | STUB | PLANNED). Stubs receive letters; their
    replies display AWAITING-RACTOR — honest: no fake voices for stubs.
  - Mersenne routing: deliver() validates citizens, dag_refs (read-only peek
    at state/the_margin_dag.json) and reply chains; forward() copies a letter
    with forwarded-from provenance (the historical Mersenne move).
  - THE MARGIN DAG integration: letters citing a node display that node's real
    kernel status + attempts count. A letter may PROPOSE a new node — the
    write goes through mag/the_margin.py's own interface when importable
    (append-only guarded there), else the proposal is recorded as
    PENDING-PROPOSAL in this book. The return value always says which.

Zero LLM tokens end to end. The seed letter's voice is INTERPRETED (marked in
metadata, never inside the body), grounded in the harvested cards.

Usage:
  python -m mag.republic show <letter_id>
  python -m mag.republic feed
  python -m mag.republic deliver --from A --to B [--cc C,D] [--in-reply-to N] \
      --body-file F [--claims-file F] [--dag-refs a,b]
  python -m mag.republic forward <letter_id> --to C [--by mersenne]
  python -m mag.republic demo      # seed + one forward + feed + falsifiers
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LETTERS_PATH = ROOT / "state" / "republic_letters.json"
DAG_PATH = ROOT / "state" / "the_margin_dag.json"
SCHEMA = "republic_letters_v1"
SEED_TAG = "republic-seed-fermat-liuhui-20260906"

TRI_STATES = ("SUPPORTED", "DISPUTED", "UNPROVEN")
CORPUS_STATUSES = ("LIVE", "STUB", "PLANNED")
# Fields a delivered letter may NEVER change. superseded_by and trail are the
# only two mutable fields, and only through the sanctioned operations.
FROZEN = ("id", "from", "to", "cc", "in_reply_to", "date", "body", "claims",
          "dag_refs", "forwarded_from", "meta")


class AppendOnlyViolation(RuntimeError):
    """Raised when a save would edit/remove a letter or rewind the trail."""


class RoutingError(ValueError):
    """Raised when a letter fails citizen/dag/reply-chain validation."""


# ------------------------------------------------------------------- dataclasses

@dataclass
class Claim:
    text: str        # the claim, kernel-checkable when formalizable
    tri_state: str   # SUPPORTED | DISPUTED | UNPROVEN
    evidence: str    # the primary source, or the honest reason there isn't one

    def to_doc(self) -> dict:
        return {"text": self.text, "tri_state": self.tri_state,
                "evidence": self.evidence}

    @staticmethod
    def from_doc(d: dict) -> "Claim":
        return Claim(d["text"], d["tri_state"], d.get("evidence", ""))


@dataclass
class Citizen:
    id: str
    name: str
    era: str
    corpus_status: str = "PLANNED"   # LIVE | STUB | PLANNED
    source_refs: list[str] = field(default_factory=list)
    note: str = ""                   # honest one-liner (ractor present? stub law?)

    def to_doc(self) -> dict:
        return {"id": self.id, "name": self.name, "era": self.era,
                "corpus_status": self.corpus_status,
                "source_refs": list(self.source_refs), "note": self.note}


@dataclass
class Letter:
    id: int
    sender: str                    # citizen id (JSON key: "from")
    recipient: str                 # citizen id (JSON key: "to")
    cc: list[str] = field(default_factory=list)
    in_reply_to: int | None = None
    date: str = ""
    body: str = ""
    claims: list[Claim] = field(default_factory=list)
    dag_refs: list[str] = field(default_factory=list)
    superseded_by: int | None = None   # set once, by supersede(); never edited
    forwarded_from: int | None = None  # provenance when this is a Mersenne copy
    meta: dict = field(default_factory=dict)   # interpreted_voice, seed tag, ...
    trail: list[dict] = field(default_factory=list)  # append-only routing trail

    def to_doc(self) -> dict:
        return {"id": self.id, "from": self.sender, "to": self.recipient,
                "cc": list(self.cc), "in_reply_to": self.in_reply_to,
                "date": self.date, "body": self.body,
                "claims": [c.to_doc() for c in self.claims],
                "dag_refs": list(self.dag_refs),
                "superseded_by": self.superseded_by,
                "forwarded_from": self.forwarded_from, "meta": dict(self.meta),
                "trail": [dict(t) for t in self.trail]}

    @staticmethod
    def from_doc(d: dict) -> "Letter":
        return Letter(d["id"], d["from"], d["to"], list(d.get("cc", [])),
                      d.get("in_reply_to"), d.get("date", ""),
                      d.get("body", ""),
                      [Claim.from_doc(c) for c in d.get("claims", [])],
                      list(d.get("dag_refs", [])), d.get("superseded_by"),
                      d.get("forwarded_from"), dict(d.get("meta", {})),
                      [dict(t) for t in d.get("trail", [])])


@dataclass
class Book:
    letters: dict[int, Letter] = field(default_factory=dict)
    next_id: int = 1
    pending: list[dict] = field(default_factory=list)  # PENDING-PROPOSAL records

    def to_doc(self) -> dict:
        return {"schema": SCHEMA, "next_id": self.next_id,
                "letters": {str(lid): self.letters[lid].to_doc()
                            for lid in sorted(self.letters)},
                "pending": [dict(p) for p in self.pending]}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _event(op: str, detail: str) -> dict:
    return {"ts": _now(), "op": op, "detail": detail}


# ------------------------------------------------------------------ persistence
# Canonical form: sorted keys, fixed indent, UTF-8, trailing newline —
# load->save->load is byte-identical BY CONSTRUCTION (F5 measures it anyway).

def dump(book: Book) -> str:
    return json.dumps(book.to_doc(), ensure_ascii=False, sort_keys=True,
                      indent=2) + "\n"


def parse(text: str) -> Book:
    doc = json.loads(text)
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"bad schema {doc.get('schema')!r}")
    return Book({int(k): Letter.from_doc(v)
                 for k, v in doc.get("letters", {}).items()},
                int(doc.get("next_id", 1)),
                list(doc.get("pending", [])))


def load(path: Path = LETTERS_PATH) -> Book:
    if not path.exists():
        return Book()
    return parse(path.read_text(encoding="utf-8"))


def save(book: Book, path: Path = LETTERS_PATH) -> None:
    """Append-only-guarded write. Loads the on-disk state first and refuses any
    save that edits a frozen field, drops a letter, rewinds a trail, un- or
    re-points a supersession, or shrinks the pending-proposal record."""
    if path.exists():
        old = load(path)
        for lid, old_l in old.letters.items():
            new_l = book.letters.get(lid)
            if new_l is None:
                raise AppendOnlyViolation(
                    f"letter {lid} would be deleted ({old_l.date}, "
                    f"{old_l.sender} -> {old_l.recipient}) — the archive never "
                    "deletes; supersede it instead")
            a, b = new_l.to_doc(), old_l.to_doc()
            for f in FROZEN:
                if a[f] != b[f]:
                    raise AppendOnlyViolation(
                        f"letter {lid} field {f!r} would be edited — delivered "
                        "letters are immutable; supersede, never rewrite")
            if new_l.trail[:len(old_l.trail)] != old_l.trail:
                raise AppendOnlyViolation(
                    f"trail of letter {lid} would be edited/removed — "
                    "append-only is enforced, not advisory")
            if old_l.superseded_by is not None and \
                    new_l.superseded_by != old_l.superseded_by:
                raise AppendOnlyViolation(
                    f"supersession of letter {lid} would be re-pointed "
                    f"({old_l.superseded_by} -> {new_l.superseded_by})")
            if old_l.superseded_by is None and new_l.superseded_by is not None \
                    and new_l.superseded_by not in book.letters:
                raise AppendOnlyViolation(
                    f"letter {lid} superseded_by {new_l.superseded_by} but "
                    "that letter is not in the book")
        if book.pending[:len(old.pending)] != old.pending:
            raise AppendOnlyViolation(
                "pending-proposal record would be edited/removed")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(book), encoding="utf-8", newline="\n")


# ------------------------------------------------------------- DAG integration

def dag_snapshot(path: Path = DAG_PATH) -> dict[str, dict]:
    """READ-ONLY peek at THE MARGIN's statement-DAG: id -> {status, attempts}.
    Never writes; absent file returns {} and validation says so honestly."""
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {nid: {"status": n.get("status", "stated"),
                  "attempts": len(n.get("attempts", [])),
                  "nl": n.get("nl_description", "")}
            for nid, n in doc.get("nodes", {}).items()}


def propose_statement(node_id: str, statement: str, nl_description: str,
                      deps: list[str] | None = None,
                      dag_path: Path | None = None,
                      from_letter: int | None = None,
                      book: Book | None = None) -> dict:
    """A letter may PROPOSE a new statement node. The DAG write itself stays
    with mag/the_margin.py's own interface (append-only guarded there) when
    importable; when the import fails the proposal is recorded as
    PENDING-PROPOSAL in this book and nothing touches the DAG. The returned
    mode says honestly which happened."""
    mode, wrote = "PENDING-PROPOSAL", False
    try:
        from mag import the_margin  # the sanctioned writer
        path = dag_path or the_margin.DAG_PATH
        dag = the_margin.load(path) if path.exists() else the_margin.seed(path)
        if node_id in dag.nodes:
            mode = "EXISTS"
        else:
            dag.add_node(the_margin.Node(id=node_id, statement=statement,
                                         nl_description=nl_description,
                                         deps=list(deps or [])))
            the_margin.save(dag, path)
            mode, wrote = "VIA-THE-MARGIN", True
    except ImportError:
        pass  # honest fallback: record, don't write
    if book is not None and mode == "PENDING-PROPOSAL":
        book.pending.append({"ts": _now(), "node_id": node_id,
                             "from_letter": from_letter, "status": mode})
    return {"wrote": wrote, "mode": mode, "node_id": node_id}


# ------------------------------------------------------------ citizen registry

CITIZENS = {
    "fermat": Citizen(
        "fermat", "Pierre de Fermat", "1607?–1665 · Toulouse", "LIVE",
        ["watch/FERMAT_RACTOR_20260906.md"],
        "harvest + persona + registers done; ractor module (fermat_ractor.py) "
        "not yet landed at engine build time — registry-ready-without-ractor"),
    "liu-hui": Citizen(
        "liu-hui", "Liu Hui 劉徽", "fl. 263 CE · Wei", "STUB",
        ["watch/REPUBLIC_OF_LETTERS_20260906.md §0, §4 — Nine Chapters ch. 6, "
         "the fine-horse/lame-horse ledger"],
        "receives letters; replies AWAITING-RACTOR — no fake voices for stubs"),
    "pascal": Citizen(
        "pascal", "Blaise Pascal", "1623–1662 · Paris", "STUB",
        ["watch/REPUBLIC_OF_LETTERS_20260906.md §2; Fermat–Pascal 1654 "
         "correspondence (harvest receipt in the Fermat card §1)"],
        "receives letters; replies AWAITING-RACTOR — next harvest per charter"),
    "mersenne": Citizen(
        "mersenne", "Marin Mersenne", "1588–1648 · Paris", "STUB",
        ["watch/REPUBLIC_OF_LETTERS_20260906.md §1, §3 — the router himself, "
         "first citizen-official"],
        "citizen-official: the routing office IS this engine; his personal "
        "voice is a later harvest"),
}


def citizen(cid: str) -> Citizen:
    try:
        return CITIZENS[cid]
    except KeyError:
        raise RoutingError(
            f"unknown citizen {cid!r} — registry: "
            f"{', '.join(sorted(CITIZENS))}") from None


# ---------------------------------------------------------------- Mersenne routing

def _validate_delivery(book: Book, sender: str, recipient: str, cc: list[str],
                       in_reply_to: int | None, claims: list[Claim],
                       dag_refs: list[str]) -> None:
    citizen(sender)
    citizen(recipient)
    if sender == recipient:
        raise RoutingError("cannot deliver to oneself — a letter to yourself "
                           "is a note, not correspondence")
    for c in cc:
        citizen(c)
        if c == recipient:
            raise RoutingError(f"cc {c!r} duplicates the recipient")
    for c in claims:
        if c.tri_state not in TRI_STATES:
            raise RoutingError(
                f"claim tri_state {c.tri_state!r} not in {TRI_STATES}")
        if not c.evidence.strip():
            raise RoutingError(
                f"claim without evidence: {c.text[:60]!r} — cite the primary "
                "source or mark it honestly (house law: cite or mark)")
    snap = dag_snapshot()
    for ref in dag_refs:
        if ref not in snap:
            raise RoutingError(
                f"unknown dag_ref {ref!r} — not a node in {DAG_PATH.name}"
                + (" (statement-DAG file absent)" if not snap else
                   f"; known: {sorted(snap)}"))
    if in_reply_to is not None:
        parent = book.letters.get(in_reply_to)
        if parent is None:
            raise RoutingError(
                f"in_reply_to {in_reply_to} — no such letter")
        if parent.superseded_by is not None:
            raise RoutingError(
                f"letter {in_reply_to} is superseded by "
                f"{parent.superseded_by} — reply to {parent.superseded_by} "
                "instead (retracted letters stop collecting replies)")


def deliver(book: Book, sender: str, recipient: str, body: str,
            cc: list[str] | None = None, in_reply_to: int | None = None,
            claims: list[Claim] | None = None, dag_refs: list[str] | None = None,
            meta: dict | None = None) -> Letter:
    """Validate everything, then append. Routing rejects bad citizens, bad
    dag_refs and broken reply chains with clear errors BEFORE anything lands."""
    cc, claims, dag_refs = list(cc or []), list(claims or []), list(dag_refs or [])
    _validate_delivery(book, sender, recipient, cc, in_reply_to, claims, dag_refs)
    letter = Letter(book.next_id, sender, recipient, cc, in_reply_to, _now(),
                    body, claims, dag_refs, meta=dict(meta or {}))
    letter.trail.append(_event(
        "delivered",
        f"{sender} -> {recipient}"
        + (f" (cc: {', '.join(cc)})" if cc else "")
        + (f" in reply to {in_reply_to}" if in_reply_to is not None else "")))
    book.letters[letter.id] = letter
    book.next_id += 1
    return letter


def forward(book: Book, letter_id: int, new_to: str,
            by: str = "mersenne") -> Letter:
    """The historical Mersenne move: copy a letter onward with provenance.
    The copy is a new letter (nothing is edited); both trails record it."""
    citizen(by)
    orig = book.letters.get(letter_id)
    if orig is None:
        raise RoutingError(f"cannot forward letter {letter_id} — no such letter")
    if orig.superseded_by is not None:
        raise RoutingError(
            f"letter {letter_id} is superseded by {orig.superseded_by} — "
            f"forward {orig.superseded_by} instead")
    _validate_delivery(book, by, new_to, [], None, [], [])
    copy = Letter(book.next_id, by, new_to,
                  cc=[c for c in orig.cc if c not in (new_to, by)],
                  in_reply_to=orig.in_reply_to, date=_now(), body=orig.body,
                  claims=[Claim.from_doc(c.to_doc()) for c in orig.claims],
                  dag_refs=list(orig.dag_refs), forwarded_from=orig.id,
                  meta={**orig.meta, "forwarded_from": orig.id})
    copy.trail.append(_event(
        "forwarded", f"forwarded from letter {orig.id} by {by} to {new_to}"))
    book.letters[copy.id] = copy
    book.next_id += 1
    orig.trail.append(_event(
        "forwarded", f"forwarded by {by} to {new_to} (see letter {copy.id})"))
    return copy


def supersede(book: Book, letter_id: int, by: str, reason: str) -> Letter:
    """Retract, house-chain style: the old letter STAYS, points superseded_by
    at a new retraction letter, and both trails say so. Never a deletion."""
    citizen(by)
    old = book.letters.get(letter_id)
    if old is None:
        raise RoutingError(f"cannot supersede letter {letter_id} — no such letter")
    if old.superseded_by is not None:
        raise RoutingError(
            f"letter {letter_id} is already superseded by {old.superseded_by}")
    ret = Letter(book.next_id, by, old.recipient, in_reply_to=letter_id,
                 date=_now(),
                 body=f"RETRACTION — letter {letter_id} is superseded: {reason}",
                 meta={"supersedes": letter_id})
    ret.trail.append(_event("supersede",
                            f"retracts letter {letter_id} by order of {by}"))
    book.letters[ret.id] = ret
    book.next_id += 1
    old.superseded_by = ret.id
    old.trail.append(_event("superseded",
                            f"superseded by letter {ret.id}: {reason}"))
    return ret


# ------------------------------------------------------------------ seed letter
# The charter's scheduled correspondence: Fermat ↔ Liu Hui on the fine horse
# and the lame horse. Voice is INTERPRETED — grounded in the harvested cards,
# marked in metadata (never inside the body).

SEED_BODY = """\
To Liu Hui, who read the Nine Chapters and left words in its margin, from
Pierre de Fermat, councilor of the Parlement of Toulouse — carried by Father
Mersenne, who has agreed to forward letters across thirteen centuries as he
once did across Paris.

Sir,

They tell me you kept a ledger. Two horses leave the same gate at dawn: the
fine one gains speed each day (益疾), the lame one loses it (减迟), and your
school asked not which horse is nobler but on which day the accounts cross —
computed as daily duty, entered in the register, serving the granary. I have
read your problem across thirteen centuries, and I answer as one bookkeeper
to another.

For I also keep a ledger of gains and losses, but my traveler is light. When a
ray passes from water into air it does not take the shortest road; it takes the
fastest — it sums the time of each path as your ledger sums the day's speed,
and chooses the least. The doctors of Paris condemned the principle when I
stated it; the machine in this house still solves its mazes by it today. Your
益疾 and my least time are the same arithmetic: the total is the verdict, and
nature is a clerk who never errs in addition.

Here I must quarrel with you, in the friendly way. Your ledger serves the
granary: the crossing-day of the horses tells the magistrate when the carts
come home. Mine serves the theorem: I sum paths no horse will ever run,
because the total tells me what is necessary, and necessity was the only
master I acknowledged in thirty years at the bar. You measured acceleration
as duty to the harvest; I measured it as duty to the truth. I do not say one
ledger is the higher. I say they are two bindings of one book — and I would
read your binding.

And now the method, which is the whole of my letter. Seek the lesser. If the
lame horse loses a little each day, ask what must be true of the fine horse's
gain for the gap to close exactly on day n — then prove it first for the
smallest gap that cannot be made smaller. The descent contains the mountain.
So that the descent may begin, I enter a statement in our shared margin [1],
where the kernel — a clerk stricter than any of ours — will judge it; and I
note that another of my statements has already walked through the machine's
fire and carries its signature [2].

You ask how fast, and by what law. I have spent my life on that question and
mean to die generously in its debt. But your parable closes with a different
question — where are we going, and who is coming with us? — and courtesy
requires that I pose it back across the centuries. The lame horse is coming
with us, sir. In my experience it is the lame horse that changes the science.

I am, with all respect and a challenge,
Fermat

[1] dag: margin-sum-two-squares — an odd prime is a sum of two squares iff it
is 1 mod 4. Stated; the kernel has not yet judged it.
[2] dag: margin-primes-infinite — infinitude of the primes, Euclid's form.
Proved; the machine's clerk has signed it."""

SEED_CLAIMS = [
    Claim("Liu Hui's 263 CE commentary on the Nine Chapters contains the "
          "fine-horse/lame-horse problem of chapter 6.",
          "SUPPORTED",
          "watch/REPUBLIC_OF_LETTERS_20260906.md §0 ('REAL, grounded'); "
          "Nine Chapters ch. 6, Liu Hui commentary, 263 CE."),
    Claim("Fermat stated the least-time principle for light (1662) and it was "
          "condemned by Cartesians.",
          "SUPPORTED",
          "watch/FERMAT_RACTOR_20260906.md §1 (FROM-KNOWLEDGE canon): "
          "'least-time optics principle (1662, condemned by Cartesians)'."),
    Claim("The 益疾/减迟 reading — a daily gaining-speed/losing-speed duty "
          "ledger — is the historical framing of Liu Hui's commentary.",
          "UNPROVEN",
          "charter §0 marks it '[stylized but grounded]'; the exact ledger "
          "framing is not yet verified against a harvested primary source."),
    Claim("The East/West thesis (process vs event, ledger vs law, 'they chose "
          "a different question') is settled history.",
          "DISPUTED",
          "charter §0: 'Needham-question territory: live debate, "
          "DISPUTED-as-settled' — filed as the Eastern seats' register, not "
          "as a verdict."),
]

SEED_META = {
    "interpreted_voice": True,
    "voice_note": "[INTERPRETED VOICE — grounded in harvested sources: "
                  "watch/FERMAT_RACTOR_20260906.md, "
                  "watch/REPUBLIC_OF_LETTERS_20260906.md]",
    "seed": SEED_TAG,
    "standing_agenda": "where are we going, and who is coming with us?",
}

SEED_DAG_REFS = ["margin-sum-two-squares", "margin-primes-infinite"]


def seed_correspondence(book: Book | None = None,
                        path: Path = LETTERS_PATH) -> Book:
    """Idempotent seed: the charter's scheduled correspondence — the seed
    letter (Fermat -> Liu Hui, cc Mersenne) plus one Mersenne forward to
    Pascal. Writes only what is missing; the archive only grows."""
    book = book if book is not None else load(path)
    seed_id = next((lid for lid, l in book.letters.items()
                    if l.meta.get("seed") == SEED_TAG), None)
    if seed_id is None:
        seed = deliver(book, "fermat", "liu-hui", SEED_BODY, cc=["mersenne"],
                       claims=SEED_CLAIMS, dag_refs=SEED_DAG_REFS, meta=SEED_META)
        seed.trail.append(_event("seed",
                                 "charter §4 scheduled correspondence "
                                 "(fermat <-> liu-hui on the horses)"))
        seed_id = seed.id
    if not any(l.forwarded_from == seed_id for l in book.letters.values()):
        forward(book, seed_id, "pascal")  # Mersenne routes it to the 1654 partner
    save(book, path)
    return book


# -------------------------------------------------------------------- display

def _dag_lines(letter: Letter, snap: dict[str, dict] | None = None) -> list[str]:
    snap = dag_snapshot() if snap is None else snap
    lines = []
    for ref in letter.dag_refs:
        node = snap.get(ref)
        if node is None:
            lines.append(f"    {ref}: NOT-IN-DAG (honest: snapshot unavailable)")
            continue
        lines.append(f"    {ref}: {node['status']}, {node['attempts']} attempt"
                     f"{'s' if node['attempts'] != 1 else ''}"
                     f" — {node['nl'][:90]}")
    return lines


def show_letter(letter: Letter, snap: dict[str, dict] | None = None) -> str:
    out = [f"LETTER {letter.id} — {letter.date}"]
    f, t = citizen(letter.sender), citizen(letter.recipient)
    out.append(f"  from: {letter.sender} ({f.name}) [{f.corpus_status}]")
    out.append(f"  to:   {letter.recipient} ({t.name}) [{t.corpus_status}]")
    if letter.cc:
        out.append(f"  cc:   {', '.join(letter.cc)}")
    out.append(f"  in-reply-to: {letter.in_reply_to or '—'}   "
               f"forwarded-from: {letter.forwarded_from or '—'}   "
               f"superseded-by: {letter.superseded_by or '—'}")
    if letter.meta.get("interpreted_voice"):
        out.append(f"  voice: {letter.meta.get('voice_note', 'interpreted')}")
    if letter.claims:
        out.append("  claims:")
        for c in letter.claims:
            out.append(f"    [{c.tri_state}] {c.text}")
            out.append(f"        evidence: {c.evidence}")
    if letter.dag_refs:
        out.append("  dag_refs (real kernel status from the_margin_dag.json):")
        out.extend(_dag_lines(letter, snap))
    if letter.trail:
        out.append("  routing trail:")
        for e in letter.trail:
            out.append(f"    {e['ts']} {e['op']}: {e['detail']}")
    if t.corpus_status == "STUB":
        out.append(f"  reply: AWAITING-RACTOR — {t.id} is STUB (persona "
                   "pending; no voice is faked)")
    out.append("  body:")
    out.extend(f"    {ln}" for ln in letter.body.splitlines())
    return "\n".join(out)


def feed(book: Book) -> str:
    snap = dag_snapshot()
    head = (f"Republic of Letters — {len(book.letters)} letters, "
            f"{len(CITIZENS)} citizens "
            f"({sum(1 for c in CITIZENS.values() if c.corpus_status == 'LIVE')} "
            f"LIVE / "
            f"{sum(1 for c in CITIZENS.values() if c.corpus_status == 'STUB')} "
            f"STUB)")
    rows = [show_letter(book.letters[lid], snap)
            for lid in sorted(book.letters)]
    if book.pending:
        rows.append("PENDING-PROPOSALS (DAG writer was not importable when "
                    "proposed — recorded, never faked):")
        rows.extend(f"  {p['ts']} node {p['node_id']} from letter "
                    f"{p['from_letter']}: {p['status']}" for p in book.pending)
    return head + "\n\n" + "\n\n".join(rows)


def post(sender: str, recipient: str, body: str, cc: list[str] | None = None,
         in_reply_to: int | None = None, claims: list[Claim] | None = None,
         dag_refs: list[str] | None = None, meta: dict | None = None,
         path: Path = LETTERS_PATH) -> Letter:
    """Disk-level deliver: load, validate, append, save."""
    book = load(path)
    letter = deliver(book, sender, recipient, body, cc, in_reply_to, claims,
                     dag_refs, meta)
    save(book, path)
    return letter


# ------------------------------------------------------------------ falsifiers

def demo() -> bool:
    """Seeds the real correspondence (idempotent), prints the feed, then runs
    the falsifiers. Destructive probes run on temp copies, never the real
    archive; a labeled failure is a valid outcome."""
    ok = True
    book = seed_correspondence()

    # F1: append-only — edit raises, delete raises, supersede works (temp copy).
    f1a = f1b = f1c = False
    tmp = Path(str(LETTERS_PATH) + ".f1.tmp")
    tmp.unlink(missing_ok=True)
    try:
        save(load(), tmp)  # mirror the real state so the guard has something
        # to defend; a save to nowhere guards nothing (the_margin lesson)
        mut = parse(tmp.read_text(encoding="utf-8"))
        mut.letters[1].body = "tampered"
        save(mut, tmp)
    except AppendOnlyViolation:
        f1a = True
    try:
        mut = parse(tmp.read_text(encoding="utf-8"))
        del mut.letters[1]
        save(mut, tmp)
    except AppendOnlyViolation:
        f1b = True
    try:
        sup = parse(tmp.read_text(encoding="utf-8"))
        ret = supersede(sup, 1, "mersenne", "F1 probe retraction")
        save(sup, tmp)
        back = parse(tmp.read_text(encoding="utf-8"))
        f1c = (back.letters[1].superseded_by == ret.id
               and 1 in back.letters)  # retracted, never deleted
    except (AppendOnlyViolation, RoutingError, KeyError):
        f1c = False
    finally:
        tmp.unlink(missing_ok=True)
    f1 = f1a and f1b and f1c
    print(f"F1 append-only (edit raises {f1a}, delete raises {f1b}, "
          f"supersede persists {f1c}): {'PASS' if f1 else 'FAIL'}")
    ok &= f1

    # F2: routing validates citizens, dag_refs, reply chains (temp file).
    tmp = Path(str(LETTERS_PATH) + ".f2.tmp")
    tmp.unlink(missing_ok=True)
    probes = []
    try:
        b2 = Book()
        for label, fn in (
                ("unknown citizen", lambda: deliver(
                    b2, "ghost", "fermat", "x")),
                ("unknown dag_ref", lambda: deliver(
                    b2, "fermat", "liu-hui", "x", dag_refs=["no-such-node"])),
                ("unknown in_reply_to", lambda: deliver(
                    b2, "fermat", "liu-hui", "x", in_reply_to=999)),
                ("self-delivery", lambda: deliver(
                    b2, "fermat", "fermat", "x")),
                ("claim w/o evidence", lambda: deliver(
                    b2, "fermat", "liu-hui", "x",
                    claims=[Claim("c", "SUPPORTED", "")])),
                ("bad tri_state", lambda: deliver(
                    b2, "fermat", "liu-hui", "x",
                    claims=[Claim("c", "TRUE", "e")]))):
            try:
                fn()
                probes.append(f"{label}=NOT-REJECTED")
            except RoutingError:
                probes.append(f"{label}=rejected")
        good = deliver(b2, "fermat", "liu-hui", "probe",
                       cc=["mersenne"], dag_refs=SEED_DAG_REFS)
        probes.append("valid delivery=landed")
        ret = supersede(b2, good.id, "mersenne", "F2 probe")
        try:
            deliver(b2, "pascal", good.sender, "x", in_reply_to=good.id)
            probes.append("reply-to-superseded=NOT-REJECTED")
        except RoutingError:
            probes.append("reply-to-superseded=rejected")
        try:
            forward(b2, good.id, "pascal")
            probes.append("forward-of-superseded=NOT-REJECTED")
        except RoutingError:
            probes.append("forward-of-superseded=rejected")
        save(b2, tmp)
    finally:
        tmp.unlink(missing_ok=True)
    f2 = all(p.endswith(("rejected", "landed")) for p in probes) and \
        "valid delivery=landed" in probes
    print(f"F2 routing validation: {'PASS' if f2 else 'FAIL'} [{'; '.join(probes)}]")
    ok &= f2

    # F3: forward preserves provenance (temp file).
    tmp = Path(str(LETTERS_PATH) + ".f3.tmp")
    tmp.unlink(missing_ok=True)
    f3 = False
    try:
        b3 = Book()
        orig = deliver(b3, "fermat", "liu-hui", "provenance probe",
                       cc=["mersenne"], claims=[Claim("t", "UNPROVEN", "e")],
                       dag_refs=SEED_DAG_REFS)
        cp = forward(b3, orig.id, "pascal")
        save(b3, tmp)
        back = parse(tmp.read_text(encoding="utf-8"))
        o, c = back.letters[orig.id], back.letters[cp.id]
        f3 = (c.forwarded_from == orig.id
              and c.body == o.body
              and c.dag_refs == o.dag_refs
              and any("forwarded from letter" in e["detail"] for e in c.trail)
              and any(f"see letter {cp.id}" in e["detail"] for e in o.trail))
    except (RoutingError, AppendOnlyViolation):
        f3 = False
    finally:
        tmp.unlink(missing_ok=True)
    print(f"F3 forward provenance (copy carries forwarded-from, both trails "
          f"record it): {'PASS' if f3 else 'FAIL'}")
    ok &= f3

    # F4: DAG integration shows the REAL kernel status from the real file.
    snap = dag_snapshot()
    seed = next((l for l in book.letters.values()
                 if l.meta.get("seed") == SEED_TAG), None)
    pilot = snap.get("margin-primes-infinite", {})
    f4 = False
    if seed is not None:
        rendered = "\n".join(_dag_lines(seed, snap))
        wants_proved = (f"margin-primes-infinite: {pilot.get('status')}, "
                        f"{pilot.get('attempts')} attempts")
        f4 = (pilot.get("status") == "proved" and pilot.get("attempts", 0) > 0
              and wants_proved in rendered)
        print(f"F4 DAG display = real kernel state (margin-primes-infinite: "
              f"{pilot.get('status')}, {pilot.get('attempts')} attempts in "
              f"the_margin_dag.json; rendered verbatim): "
              f"{'PASS' if f4 else 'FAIL'}")
    else:
        print("F4 DAG display: FAIL (seed letter missing)")
    ok &= f4

    # F5: persistence deterministic round-trip, byte-identical.
    b1 = dump(book)
    b2 = dump(parse(b1))
    f5 = b1 == b2
    print(f"F5 round-trip byte-identical: {'PASS' if f5 else 'FAIL'} "
          f"({len(b1)}B, sha {hashlib.sha256(b1.encode()).hexdigest()[:12]})")
    ok &= f5

    # F6: the demo ran end-to-end clean on the REAL archive — seed + forward
    # present, ids monotonic with no gaps, every reference resolves.
    ids = sorted(book.letters)
    f6 = (seed is not None
          and any(l.forwarded_from == seed.id for l in book.letters.values())
          and ids == list(range(1, book.next_id))
          and all((l.in_reply_to is None or l.in_reply_to in book.letters)
                  and (l.forwarded_from is None
                       or l.forwarded_from in book.letters)
                  and (l.superseded_by is None
                       or l.superseded_by in book.letters)
                  for l in book.letters.values()))
    print(f"F6 end-to-end clean (seed id {seed.id if seed else '?'} + forward "
          f"on disk, ids 1..{book.next_id - 1} contiguous, all references "
          f"resolve): {'PASS' if f6 else 'FAIL'}")
    ok &= f6

    print(f"\nOVERALL: {'PASS' if ok else 'FAIL'} — "
          f"{len(book.letters)} letters at {LETTERS_PATH.name}, "
          f"DAG nodes: {sorted(snap)}")
    return ok


# ------------------------------------------------------------------------ CLI

def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="mag.republic")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_show = sub.add_parser("show")
    p_show.add_argument("letter_id", type=int)
    sub.add_parser("feed")
    p_del = sub.add_parser("deliver")
    p_del.add_argument("--from", dest="frm", required=True)
    p_del.add_argument("--to", required=True)
    p_del.add_argument("--cc", default="")
    p_del.add_argument("--in-reply-to", type=int, default=None)
    p_del.add_argument("--body-file", required=True,
                       help="letter body; '-' reads stdin")
    p_del.add_argument("--claims-file", default="",
                       help='JSON list of {text, tri_state, evidence}')
    p_del.add_argument("--dag-refs", default="", help="comma-separated node ids")
    p_fwd = sub.add_parser("forward")
    p_fwd.add_argument("letter_id", type=int)
    p_fwd.add_argument("--to", required=True)
    p_fwd.add_argument("--by", default="mersenne")
    sub.add_parser("demo")
    args = ap.parse_args()
    try:
        _run(ap, args)
    except RoutingError as exc:
        print(f"ROUTING REJECTED — {exc}")
        sys.exit(2)
    except AppendOnlyViolation as exc:
        print(f"ARCHIVE REFUSED THE WRITE — {exc}")
        sys.exit(2)


def _run(ap: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.cmd == "show":
        bk = load()
        letter = bk.letters.get(args.letter_id)
        if letter is None:
            raise RoutingError(f"no letter {args.letter_id} — ids on file: "
                               f"{sorted(bk.letters)}")
        print(show_letter(letter))
    elif args.cmd == "feed":
        print(feed(load()))
    elif args.cmd == "deliver":
        body = (sys.stdin.read() if args.body_file == "-"
                else Path(args.body_file).read_text(encoding="utf-8"))
        claims = [Claim.from_doc(c) for c in (
            json.loads(Path(args.claims_file).read_text(encoding="utf-8"))
            if args.claims_file else [])]
        letter = post(args.frm, args.to, body,
                      cc=[c for c in args.cc.split(",") if c],
                      in_reply_to=args.in_reply_to, claims=claims,
                      dag_refs=[d for d in args.dag_refs.split(",") if d])
        print(f"delivered letter {letter.id}: {letter.sender} -> "
              f"{letter.recipient}")
        print(show_letter(letter))
    elif args.cmd == "forward":
        bk = load()
        cp = forward(bk, args.letter_id, args.to, by=args.by)
        save(bk)
        print(f"letter {args.letter_id} forwarded to {args.to} by {args.by} "
              f"-> letter {cp.id}")
    elif args.cmd == "demo":
        sys.exit(0 if demo() else 1)


if __name__ == "__main__":
    main()
