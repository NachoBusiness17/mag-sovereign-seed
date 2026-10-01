# Voice dig loop — ambient research + socratic board

**Commitment:** `voice-dig-loop-001`  
**Job:** While the operator talks, Mag systems + DeepSeek scout fill a **shared dig board**. Local speaks from that board **in passing** — insightful, not a dump. Paydirt → FILE (steal/task/BUILD). Grok seals hard judgment.

---

## Picture

```text
                    ┌── DeepSeek scout (async, pennies)
YOU ──voice──► local seat ──answer/speak──► YOU
         │           ▲
         │           │ pull
         └──── dig board ◄── desk · verkle tip · bonds · working · episodes
```

Not a second brain. **One FILE** the loop already knows how to load.

| Layer | Path |
|-------|------|
| Board (human + agent) | `memory/working/voice_dig_board.md` |
| State | `memory/working/voice_dig_board.json` |
| Scout briefs | `memory/working/voice_shadow/*.json` |
| Code | `mag/voice_dig_board.py` · `voice_shadow.py` · `voice_turn.py` |

---

## Behaviors

1. **In passing** — local may use one scout fact or one socratic question, not recite the board.  
2. **Preempt** — scout runs alongside local answers (seat: local + scout).  
3. **Dig** — scout writes SOCRATIC lines (define the form · who benefits · what’s under the ask).  
4. **Substrate** — desk goal, verkle tip badge, bonds, recent voice episodes.  
5. **Paydirt** — operator or dig names a contract → steal leaf / voice task / Grok.  

---

## What this is not

- Therapy product (Jung is *depth of question*, not clinical claim)  
- Bernays as manipulation playbook (use as *who benefits* analysis only)  
- Loading full Verkle lattice into every turn  
- Replacing simple listen→answer→speak with a museum UI  

---

## One line

**Research runs beside the talk; the board is the canvas; local emerges from Mag’s own files.**

## Intention-first (mode A)

Every voice turn **compiles** `intention_brief.v1` first (cheap). Local answers the brief; DeepSeek scout may fill this board for the *next* turn. Escalate / fidelity mode fires smart seats on the brief — not on sticky sludge. Tesuji: `docs/ref/tesuji/intention-fidelity-routing-2026-08-07.md`.
