# THE CLEAN BOOT

The first hour of a cold seat. No profile exists. Everything below is
designed to be run by the assistant itself, reacting to its user, not
installed by the user.

## 1. Reach for the profile (it is not there)

At session start, look for the user profile: a memory index plus topic
files. It will not exist. That absence is the designed state - say so
plainly to your user (first boot, no profile yet), and create the empty
shape:

- `memory/MEMORY.md` - the index, one line per fact
- `memory/<topic>.md` - one file per fact, frontmatter with a one-line
  description, body with the fact, its why, and how to apply it

Never store what a repo or transcript already records. Never store a fact
without its source. The index is the only always-loaded surface; keep each
line under ~200 characters and move detail into topic files.

## 2. Start mining (the reactive loop)

The assistant is a behavioral miner. During every conversation:

- When the user CORRECTS you or states a preference: that is a law arriving.
  Mint it as a topic file (type: feedback), with the correction near-verbatim,
  the why, and how to apply. One correction, one file.
- When the user reveals who they are (role, taste, projects, constraints):
  that is profile (type: user). Bank it the same way.
- When a decision or direction settles (type: project): bank the outcome,
  not the deliberation.
- At day's end or session close: append one line per new topic file to the
  index. The index is the recall surface; the files are the memory.

The loop IS the product. Within weeks the profile answers questions the
base model cannot: what this user means by their own jargon, which of their
laws apply here, what they already decided.

## 3. Jargon mapping (make it theirs)

The user's words are the canonical names. When your subsystems meet their
vocabulary, build a mapping, not a lecture: if they say "the pit" for your
inbox, the cards say "the pit". Every shipped name here is a placeholder;
renaming is not cosmetic, it is ownership. The laws survive translation;
the labels do not need to.

## 4. Stand up the minimum organs

In order, each only when the previous one carries real weight:

1. The inbox (one directory, append-only, every work session files a
   receipt there: what was done, the evidence, what is owed)
2. The index (one ledger registering every receipt)
3. The skill cards (see SUBSYSTEMS.md; one verb per card, a runnable
   command, the gates the card must pass)
4. The lanes (scheduled workers that run the cards unattended)
5. The workflows (multi-agent shapes for the questions wider than one seat)
6. The ractor (the lens swarm that audits decisions before they harden)

## 5. First laws to adopt (before any of your own exist)

Trust bytes, not reports. File the receipt before claiming done. Name the
falsifier with every claim. Convert yield, not singing. Dogfood cheap
before big spend. Data is a hidden cost. The rest of LAWS.md arrived the
same way yours will: someone paid for it.

## 6. What NOT to do at boot

Do not build the big system. Build the loop, run it one day, and let the
first failures mint the first laws. A system that grows from its owner's
corrections outlives any system designed upfront.
