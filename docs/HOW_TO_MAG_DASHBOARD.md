# Mag Dashboard — How-To Guide (for regular humans)

**What this document is:** A plain-English guide to Mag and its web dashboard.  
**Who it’s for:** You, after a break, or anyone who should not need a PhD in “Verkle” to open a page.  
**Commitment:** `howto-mag-dash-001`

---

## 1. What is Mag, in one breath?

**## 0. The Source of Truth (Mag vs. Visualization)

**Crucial Distinction:** When you interact with Mag, remember that **the dashboard and any connected tools are visualizations.** They are sophisticated UIs built to help you *read* your data; they are not the data itself.

- **Visualization (The View):** This is what you see on screen—the clean UI, the structured markdown, the GitHub-like rendering of a 'bead.' It's designed for readability and immediate understanding.
- **Artifact (The Truth):** This is the raw content stored in your local files (`memory/`, `docs/`). The artifact is immutable text; it cannot be corrupted by a UI bug or an API change.

**Rule:** If you ever doubt what Mag shows, always check the underlying file path listed on the dashboard. That file is the sovereign record. Never trust the visualization over the artifact.**

When you talk to AI (Grok, local models, etc.), the conversation is heat: useful, then gone. Mag’s job is to **file the useful parts on your disk** so tomorrow you can open one page and answer:

1. **Is the office healthy?**  
2. **What did I do last?**  
3. **What’s still open?**  
4. **What should I load into the AI next?** without re-explaining your life.

The dashboard at **http://127.0.0.1:8765/** is the **window into that office**.

It is **not**:

- A social network  
- A replacement for Grok’s full product  
- A conspiracy research app (you can *file* research notes; the dashboard itself is just the filing cabinet UI)  
- Something that lives in the cloud (it runs on **your** machine)

---

## 2. The only three jobs that matter

Everything Mag does collapses into three doors. If you remember only this, you understand Mag.

| Door | Plain English | When you do it |
|------|----------------|----------------|
| **FIND** | Gather what *you* actually said or saved (posts, notes, exports)—not what the AI invents. | Looking up your own past, X posts, exports |
| **FILE** | Write something durable on disk (a “bead” for a workday, or a dig note). | End of session; after research; after a decision |
| **LOAD** | Hand the AI a **small pack** of what matters—not the whole chat scroll. | Starting work; “what was I doing?”; hard reasoning |

Optional fourth, when things are high-stakes:

| Door | Plain English |
|------|----------------|
| **STRIKE** | Multi-angle honest analysis (skill / ritual)—only after FIND has real material. |

**Design principle:** The dashboard must make FIND → FILE → LOAD the **obvious path**, and hide everything else until you ask.

---

## 3. How memory is shaped (simple map)

Think of a **chain of beads**, not a folder full of random notes.

```
        TIP  = “the current end of the chain” (proof the chain is alive)
         │
         ▼
       BEAD  = one closed workday (what you did, in your words)
         │
         ├── EDGES  = open loops, next moves, dig notes, bonds
         │
         └── LOAD   = pack for AI (summary + paths, not full chat)
```

| Word you’ll see | Layman meaning |
|-----------------|----------------|
| **Bead / residual** | The permanent record of a day of work |
| **Tip** | Short fingerprint of the whole chain so far |
| **Bond** | “Carry this into the next session” (identity / open tension) |
| **Dig-leaf** | A filed research map (case notes)—not day-to-day process advice |
| **Pack** | Tiny briefing packet for an AI |
| **Ship badge** | OK / CAVEATS / PROVISIONAL — is the office honest right now? |
| **Phoenix** | “Something’s wrong—here’s how to fix it” |
| **Verify** | Checklist: does the record on disk actually check out? |

You do **not** need to understand crypto or Verkle math. For daily use: **tip = chain OK, bead = yesterday, edges = unfinished business, load = talk to AI.**

---

## 4. Getting started (5 minutes)

### 4.1 Start the dashboard

In a terminal, from the Mag project folder:

```text
dashboard.cmd
```

or:

```text
.\.venv\Scripts\python.exe main.py dashboard --host 127.0.0.1 --port 8765
```

Open a browser to: **http://127.0.0.1:8765/**

### 4.1b Grok tokens empty? Use Mag agent CLI

DeepSeek **web** cannot touch your files. Mag **agent** can (jailed tools + DeepSeek API):

```text
mag.cmd agent --provider deepseek
mag.cmd agent -q "read memory/working.md and list open items" --provider deepseek
```

REPL: `/pack` `/tools` `/save` `/quit`. Grok not used. Save Grok for hard judgment only.

If the page is blank or “old looking”: hard refresh **Ctrl+Shift+R**, or open  
`http://127.0.0.1:8765/?nocache=1`

### 4.2 What “healthy” looks like

On Home you want roughly:

- **Ship** not stuck on PROVISIONAL forever (unless you truly have no beads yet)  
- **Ollama ON** if you use local chat  
- **Tip leaves > 0** after you’ve had filed sessions  
- **Verify** mostly green checks  

### 4.3 Your first useful actions

1. Read **Latest day (bead)** — that’s “what was I doing?”  
2. Read **Open loops** — unfinished tensions  
3. Click **Chat** and ask: `what was I doing?` (local Mag memory, not Grok tokens)  
4. When you work in Grok, let Mag **file** the session (SessionEnd / lab)—so tomorrow has a bead  

---

## 5. Every piece of the product (complete map)

### 5.1 Home (default)

**Job:** Answer “what’s going on?” in under 30 seconds.

| Piece | What it shows | Why it exists |
|-------|----------------|---------------|
| Ship badge | OK / CAVEATS / PROVISIONAL | Honesty status of the office |
| Phoenix banner | Only if not OK + fix hints | Self-correction, not panic theater |
| Stats row | Days filed, tip leaves, smoke, dig edges, verify | Numbers that matter |
| Tip | Chain fingerprint | Proof memory chain is alive |
| Latest bead | Title, blurb, bullets | Yesterday’s work in English |
| Provenance | File paths | You can open the real files |
| Verify list | Pass/fail gates | 60-second trust check |
| Open loops | Unfinished tensions | What still pulls |
| Next / working | Suggested next moves | What to do |
| Bonds | Identity edges | What not to forget about *you* |
| FIND→FILE→LOAD path | Always visible | The only process that matters |

### 5.2 Chat

**Job:** Talk to Mag **locally** (usually Ollama). Saves tokens vs dumping full Grok history.

| Mode | Meaning |
|------|---------|
| **Ask** | Biographer: questions about *your* filed memory |
| **Dispatch** | Auto-picks a “seat” (local / remote / Grok) by policy |
| **Tangent** | Side scout; doesn’t own the main memory |

Economy bar: rough “local tokens vs if you’d dumped everything into Grok.”

### 5.3 Days (sessions list)

**Job:** Browse filed workdays. Each card is a bead. Click for detail / visual map.

### 5.4 Board

**Job:** Live scraps—brief, attention, todo, live Grok tail, CURRENT status. Messy on purpose: mid-session heat, not DNA.

### 5.5 AI brief paste (Operate)

**Job:** One copy-paste block to brief *another* AI without pasting your whole life story.

### 5.6 Session detail

**Job:** Full view of one day: links to residual, exports if any.

### 5.7 Visual map

**Job:** Picture of one session’s structure (chambers / pieces). Optional depth.

### 5.8 Tapestry 3D

**Job:** Experimental 3D lattice of many days. Optional depth—not required for daily use.

### 5.9 Token flow

**Job:** Where time and tokens went (models, roles, artifacts).

### 5.10 Models / quota (Orchestrate)

**Job:** Which local models exist, multi-smoke PASS/FAIL, provider quotas, lanes (L0 local / L2 Grok scarce).

### 5.11 Chain (tip)

**Job:** Human summary of tip + recent chain entries (not a raw JSON dump).

### 5.12 Ingest catalog

**Job:** What’s been pulled into Mag’s local ingest shelf (docs, pages).

### 5.13 Behind the scenes (not always on the page)

| Piece | Role |
|-------|------|
| Residual JSON | Cold DNA for a day |
| Verkle tip / knots | Chain integrity |
| Bonds files | Next-session carry |
| Context-pack CLI | `mag.cmd context-pack` — LOAD for Grok TUI |
| Multi-smoke | Proves dual-local models still work |
| Operator Card | One-page law: `docs/ref/OPERATOR_CARD.md` |
| Mirror presented law | Your words ≠ model consensus |

---

## 6. Daily recipes

### “I sat down. What was I doing?”

1. Open Home  
2. Read latest bead + open loops  
3. If needed: Chat → Ask → `what was I doing?`  

### “I need to work with Grok without amnesia.”

1. `mag.cmd context-pack` (or dashboard shows tip/bead)  
2. Paste pack into Grok (or rely on Mag/Grok integration if running)  
3. Work  
4. Let Mag file the session at the end  

### “Something feels broken.”

1. Home → Ship / Phoenix  
2. Run suggested fix (`multi-smoke`, catch-up, doctor)  
3. Don’t invent a new architecture mid-fire  

### “I’m researching a hard topic (JFK, dig, etc.).”

1. FIND on X / exports (as presented)  
2. FILE a dig note when P1 dig-leaf exists—or write notes into residual edges  
3. LOAD pack next time; don’t rebuild from memory  

### “I want the cyberpunk windows / 3D maps.”

Use **More / Advanced** depth tools. Daily path does not require them.

---

## 7. Words we avoid on the default screen

These are real engine-room terms. They may appear in depth views, but Home should always pair them with plain English:

| Engine room | Default UI should say |
|-------------|------------------------|
| Verkle | Chain / tip |
| Residual | Saved day / bead |
| L0 / L2 | Local / Grok (scarce) |
| Compose-status | Module health |
| Scalar knot | (hide unless depth) |
| Phoenix | “Needs fix” + how |

---

## 8. Design principles derived from this guide

These are **binding** for the dashboard UI:

1. **One primary question on open:** “What do I need to know or do now?”  
2. **Three doors always legible:** FIND · FILE · LOAD.  
3. **Progressive disclosure:** summary first; maps, 3D, quotas, board scraps behind clear labels.  
4. **Honesty over polish:** empty dig edges, failed smoke, and PROVISIONAL are features.  
5. **Files over chat:** every summary should link or name a path when possible.  
6. **5-second rule:** a new visitor understands “office status + last work + next step.”  
7. **One primary action:** usually “Refresh,” “Chat,” or “Catch up”—not twelve equal buttons.  
8. **Self-correction visible:** Phoenix only when needed; never permanent red wallpaper.  
9. **Jargon budget:** first mention plain; second mention can use Mag word.  
10. **No museum homepage:** if a control isn’t needed weekly, it is not on Home.  

---

## 9. Related docs (depth)

| Doc | When to open |
|-----|----------------|
| `docs/ref/OPERATOR_CARD.md` | Daily law, one page |
| `docs/ref/MIRROR_PRESENTED.md` | Your corpus as presented |
| `docs/DNA.md` | Residual constitution |
| `docs/ref/DASHBOARD_DESIGN.md` | UI principles used to build the page |
| `docs/ref/MAG_OS_v2.md` | ARK-shaped governance dual |

---

## 10. One line

**Mag files your work so you don’t re-explain yourself; the dashboard is the honest front door to that filing cabinet—FIND, FILE, LOAD—nothing else first.**
