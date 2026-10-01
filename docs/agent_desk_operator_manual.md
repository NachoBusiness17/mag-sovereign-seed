# Agent Desk — Operator Manual

Turn-based **Local (gemma4 · desk_orchestrator)** ↔ **DeepSeek (chat-only)** on one shared canvas.  
This desk is for **proving the L0→specialist handoff** — not execution. Run tools in **Shell** or **Workers**.

**Trust model:** if slow→fast (desk, you watching) fails, fast→fast (repack/orchestrator→DeepSeek unmanned) must not be trusted. See `docs/agent_desk_trust_ladder.md`.

---

**Local selector:** choose **Workflow test** to debug the Desk process quickly with a deterministic simulated Local seat. Choose **Real Local** to put Ollama and local hardware back in the loop. Workflow-test passes are process evidence only and never certify the real Local model.

## What this room is for

| Use the desk for | Do *not* use the desk for |
|------------------|---------------------------|
| Agreeing on a goal before work | Running shell commands |
| Two models reasoning together | Deep tool loops / file scans |
| Writing a shared contract on canvas | Long autonomous agent runs |
| Operator steering with short notes | Replacing Workers tab |

The canvas (`memory/working/agent_desk.md`) is the **contract**. Lane chat is **transcript**. Files on disk win over what either model says.

### Middle column: one file, two views

| Pane | What it is |
|------|------------|
| **Preview** (left) | Rendered markdown — how the board *looks* |
| **Edit** (right) | Raw source — what you and agents actually write |

Both panes mirror the same file. Edit on the right → preview updates on save/reload. Agents append to `## Dialogue` in the file; preview shows headings and formatting.

---

## How turns work

1. **Operator** sets `## Goal` (and optionally a kickoff note).
2. **Local** speaks → appends under `## Dialogue` as `### Local · …`
3. **DeepSeek** speaks → appends as `### DeepSeek · …`
4. Cursor badge shows who held the pen last.
5. **Ping-pong ×2** = four turns (local → remote → local → remote).

Operator typing in the canvas = **operator cursor** (you are editing the contract directly).

---

## Etiquette — for operators

### Before you start
- Write **one** clear `## Goal` — a sentence the agents can test against.
- Clear or archive old `## Dialogue` when the topic changes (don't pile unrelated threads).
- Put binding decisions in `## Operator notes`, not buried in chat.

### While they talk
- **Kick off** once with a short operator note; don't spam notes every turn.
- Let ping-pong finish before injecting another steer unless they're off-rails.
- If they agree on a next step, **you** copy it to `## Operator notes` and execute elsewhere.
- Don't ask them to "run" things here — say "propose the command; operator runs it in Shell."

### When to interrupt
- Same point repeated twice → stop ping-pong, edit canvas, restate Goal.
- Format slop (`### Unknown ·`) → edit canvas by hand, tighten Goal.
- DeepSeek API error → single lane retry or check Body → Routes.
- Local nonsense → treat as weak summarizer; lean on DeepSeek for structure, Local for quick takes.

### Tone you should model
- Concrete > visionary.
- "What's the one next step?" > open-ended brainstorming.
- Disagreement is fine; stalemate → operator decides in `## Operator notes`.

---

## Etiquette — for agents (Local & DeepSeek)

These rules are injected into both models every turn.

1. **Respond to the last peer message**, not a full canvas recitation.
2. **One new idea per turn** — don't repeat what's already under `## Dialogue`.
3. **Canvas edit = one paragraph** under `### Local ·` or `### DeepSeek ·`.
4. **No tools, no file claims** unless the text is on the canvas.
5. **No fake execution** ("I ran…", "I scanned…") — propose; operator executes.
6. **Format strictly:**
   ```
   ### Reply
   (2–6 sentences to peer + operator)

   ### Canvas edit
   ### Local · short title
   One paragraph.
   ```
7. If the Goal is done, say so in Reply and append a `### … · Done` line with the agreed next step for the operator.

---

## Known limitations

### Local = Mag L0 (same software, not a separate chatbot)

**Local on the desk is not a different product.** It is the same seat Mag uses everywhere for L0 scut work:

| Where | Same stack |
|-------|------------|
| Desk **Local** lane | `desk_orchestrator` → **gemma4:latest** (handoff voice) |
| Desk orchestrator (legacy API) | `orchestrator` → **gemma:2b** (one-shot scut) |
| `configs/lanes.yaml` | `desk_orchestrator: gemma4:latest` · `orchestrator: gemma:2b` |
| Auto-repack residual | **gemma:2b** compresses tool chains → goal + crumbs |
| Biographer / clerk hot path | Same Ollama pool, sequential load policy |

**Doctrine (lanes.yaml):** *gemma:2b = scut* for repack/router; *gemma4 = desk handoff* for slow→fast calibration on this board.

When Local truncates, echoes, or ignores format **on the desk**, expect the **same class of failure** when Mag uses that model for repack summaries, steer text, or orchestrator glances. The desk is a **visible calibration surface** for local Mag — not a sandbox with different rules.

**Shared L0 limits (desk + repack + orchestrator):**
- **Weak format adherence** — repack residuals and desk replies may omit structure; parser falls back to `### Unknown ·`.
- **Truncation under pressure** — short outputs cut mid-thought (same as baseline `Sure, here's the`).
- **Echo / residual bleed** — after repack or long dialogue log, repeats prior blocks instead of new content.
- **Small context effective window** — canvas ~8k chars to desk; repack drops tool chains to crumbs for the same reason.
- **No tools on L0 orchestrator** — cannot verify repo; proposes only (operator / DeepSeek / Shell executes).
- **No cross-session memory** — canvas + dialogue log (desk) or repack residual (agent turns) is the whole story.

**Implication for operators:** trust Local on the desk the same way you trust local Mag elsewhere — **scut signals only**. DeepSeek (specialist / remote) carries structure; you carry decisions.

### DeepSeek (dialogue mode)
- **Chat only** — `tools=None`; old `desk-deepseek` tool session is ignored here.
- **API latency & cost** — each turn is a paid call; ping-pong ×2 = 4 calls.
- **Fails closed** — if the API errors, the turn stops (partial ping-pong possible).

### System
- **Canvas context cap** — ~8k chars sent to models per turn; very long canvases truncate.
- **Ping-pong cap** — max 4 rounds (8 turns) per request.
- **Append-only dialogue** — agents append blocks; they don't rewrite earlier sections.
- **Lane logs** — stored in browser localStorage; clearing browser clears lane UI (canvas file remains).
- **Cursor file** — `memory/working/agent_desk_cursor.json` (who spoke last).
- **Dialogue log** — `memory/working/agent_desk_dialogue.jsonl` (machine-readable turns).

### What this desk cannot do
- Merge with Workers orchestrator automatically.
- Guarantee both models stay on-topic without a tight Goal.
- Replace operator judgment on when to stop.

---

## Controls (quick reference)

| Control | Action |
|---------|--------|
| **Send** (Local / DeepSeek lane) | That agent's single turn |
| **Ping-pong ×2** | Four automated turns from current canvas |
| **Kick off** | Operator note → Local turn → DeepSeek turn |
| **Save / Reload** | Write / read `agent_desk.md` |
| **Clear** | Browser lane logs only |
| Typing in canvas | Operator edit + auto-save |

---

## Suggested canvas shape

```markdown
# Agent desk

## Goal
(one sentence)

## Dialogue
(agents append here — turn-based)

## Operator notes
(your decisions — source of truth for "what we actually do")

## Open questions
(optional — park unresolved items)
```

---

## Recovery checklist

1. **Messy canvas** → copy Goal, wipe Dialogue, paste Goal back, ping-pong again.
2. **Stuck agents** → add `## Operator notes` with "Decision: …" and stop ping-pong.
3. **Old tool session poison** → irrelevant in dialogue mode; ignore `desk-deepseek.json` for this tab.
4. **UI stale** → hard refresh (`Ctrl+Shift+R`).

---

## Files

| Path | Purpose |
|------|---------|
| `memory/working/agent_desk.md` | Shared canvas |
| `memory/working/agent_desk_cursor.json` | Turn cursor |
| `memory/working/agent_desk_dialogue.jsonl` | Turn log |
| `prompts/desk_dialogue_local.txt` | Local system prompt |
| `prompts/desk_dialogue_remote.txt` | DeepSeek system prompt |
| `docs/agent_desk_operator_manual.md` | This manual |

---

_Last updated: dialogue-only desk (v11). Execution lives in Shell / Workers._
