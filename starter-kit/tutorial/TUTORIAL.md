# TUTORIAL MODE - the first day, hands on

Three lessons, one day. Each is 15-30 minutes and ends with a real organ
running. Do them in order; each builds on the last. If you get stuck,
`python tools/kit_doctor.py` names what is missing.

## Lesson 1: first boot + first memory (15 min)

1. Run the doctor: `python tools/kit_doctor.py` - everything "ok"?
   (If git is missing, setup/install.sh or setup/install.ps1 fetches the
   free stuff, including where to sign up for GitHub.)
2. First boot: `python tools/profile_boot.py --memory memory`
   - It says FIRST BOOT and creates the empty shape. That absence is the
     designed state - the kit ships with no profile on purpose.
3. Now mine yourself: open a chat with your assistant (any harness) and
   tell it one true correction and one fact about how you work. Then, by
   hand the first time, write two files with the agent/conversation-miner
   card's shape:
   - `memory/likes-direct-answers.md` (or whatever YOU would call it)
   - append one line per file to `memory/MEMORY.md`
4. Re-run profile_boot - exit 0 now, with your two rows in the boot brief.

You now have the loop's shape. Everything after this is automation.

## Lesson 2: the receipt + the first law (20 min)

1. Do one small real task with your assistant (a script, a summary,
   anything with evidence).
2. File the receipt: `inbox/2026-MM-DD-whatwasdone.md` containing what was
   done, the evidence (path, command, output), and what is owed. File it
   BEFORE either of you claims done.
3. When the assistant gets something wrong during the task, mint the law:
   write `memory/<law>.md` with the law-minter card's shape - the
   correction near-verbatim, the why, and "paid for by" pointing at the
   receipt you just filed.

You now have evidence-linked memory: laws that can name their failures.

## Lesson 3: go reactive + pick your plugs (30 min)

1. Load the three agent/ cards into your harness's instruction surface
   (system prompt, skills dir, CLAUDE.md/AGENTS.md-style file - whatever
   yours is called). Tell the assistant: "mine this session with the
   conversation-miner card."
2. Talk normally for twenty minutes. Count what it banked unprompted.
   That count is the kit working.
3. Pick your plugs:
   - Hermes-class agents: integrations/hermes/README.md
   - Android (phone as the body): integrations/android/README.md
   - Anything else: SUBSYSTEMS.md, organs 1-4, run as cards.

## After the first day

- SUBSYSTEMS.md organ 4 (lanes) when a week of receipts exists.
- workflows/ shapes when a question outgrows one seat.
- The ractor (SUBSYSTEMS.md organ 6) before any decision that hardens.
- Regenerate your own BOOT.md when your boot stops matching this one.
