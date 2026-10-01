# WHAT THE SYSTEMS ARE AND WHY — in normal words

The system has a habit of naming things poetically (knots, organs, ractors,
waltzes). This page drops the poetry and answers the two questions that matter:
what is in there, and why does it exist.

## Where it lives: containers

**What:** The whole system runs inside Docker containers. Think of these as
sealed shipping containers inside the computer. The agents work inside them and
cannot casually rummage through the rest of the machine.

**Why:** An AI with file access on a family computer is a bull in a house. The
containers are the fencing. It also means if something breaks, you restart one
container instead of reinstalling your computer.

## How it remembers: files, a chained diary, and a notary

**What:** Memory is ordinary files on disk, plus one special file: a diary where
every ten minutes or so a small program (the janitor) appends a short page
describing what just happened. Each new page contains a cryptographic fingerprint
of the previous page, like gluing each page to the one before it. The live
system's diary is about 8,700 pages long.

**Why:** Two reasons. First, chat windows forget; files do not. Anything not
written to disk did not happen. Second, the gluing means yesterday cannot be
quietly rewritten. If someone edits an old page, the fingerprints stop matching
and the tampering is visible. The system's name for this is a hash chain; you
can just think "diary with glued pages."

**The notary:** Every so often the whole state gets snapshotted and stamped (a
seal). Seals answer the question "but what did the system actually believe on
Tuesday?" without trusting anyone's memory.

## How it works: organs, a work board, and workers

**What:** The program parts are called organs (there are about 190 of them in
`mag/`), each with one job: watch the news, grade a claim, summarize, file a
receipt, spend money carefully. Work arrives as written tasks on a to-do board.
Different AI models act as workers that pick tasks up. Cheap or free models do
the bulk; expensive models are summoned only for the hard ones, like calling a
specialist instead of your family doctor for everything.

**Why the free-first routing:** the system's founding economics. Its operator
decided early that the system must live on nearly-free compute (see
`FREE_COMPUTE.md`), which forced the good habit of never burning paid capacity
on work a free lane can do.

## How it stays honest: receipts, grades, and a hostile inspector

This is the part worth copying, so it gets three entries.

**The receipt drawer.** Anything that finishes gets a dated receipt in a folder:
what was done, where the evidence lives. The house law is "residual on disk is
truth; chat is heat." If it did not get a receipt, it did not happen.

**Tri-state grading.** Every claim gets exactly one of three grades: Supported
(checked, evidence cited), Disputed (checked, evidence against), or Unproven
(cannot be checked). Not "true/false/maybe" as vibes; as verdicts with named
evidence. This kills the most common AI failure, confident invention, because
"I cannot verify this" is always an available answer.

**The hostile inspector.** Finished work gets re-checked by a second pass whose
explicit job is to break it: re-verify quotes against the original sources,
recount the numbers, hunt for anything fabricated. The inspector's reports are
kept, including when it finds problems. (It found a leaked-config risk in this
very package's export process; the risk was cut. That is the system working.)

## How you watch it: a dashboard

**What:** A small website that runs on the same machine (not the public
internet) showing what the system is doing: current goal, work lanes, history,
live activity.

**Why:** A system you cannot see is a system you cannot trust or enjoy. The
operator wanted a window, not a black box.

## How it talks to other machines: the bridge

**What:** A one-way, verified mail slot. One machine packages its work, the
other machine recomputes the package's fingerprints and only accepts it if they
match, and every accepted delivery is logged in a permanent ledger.

**Why:** Backups that silently fail are worse than no backups. The bridge makes
"did the copy arrive intact?" a checkable fact instead of a hope.

## The index of its own mistakes

**What:** The system's memory index includes a section listing 441 entries that
point at files that never existed: plans that were indexed but never built, or
moved without updating the pointer.

**Why keep that?** Because deleting the evidence of your errors guarantees you
repeat them. The phantom ledger is kept on display on purpose. Any system that
cannot show you its mistakes is hiding them.

## What the whole thing adds up to

Sovereignty, used precisely: the system is yours because it runs on your
machine, its memory is files you can copy, its honesty rules are checks you can
rerun, and you can unplug it. It is not a product, has no subscription, phones
home to nobody, and gets no say in whether it keeps existing.

## What it is not

- Not an app you install and forget; it is closer to a workshop you tend.
- Not magic; every "smart" behavior above is a written rule plus a check.
- Not finished; the live version changes daily, and its own audit grades its
  weakest claims honestly (see `story/` for it doing exactly that in public).
