# Layman Office — customizable dashboard & Tesuji Grove

**Commitment:** `layman-office-vision-001`  
**As-of:** 2026-08-05  
**Status:** v3 design — research & UX spec (not v2 ship)  
**Parents:** `FRAMEWORK_LOAD.md` · `DASHBOARD_DESIGN.md` · `MAG_v3_BACKLOG.md`  
**Audience:** Nacho (operator) · designers · LLMs loading the framework

**One breath:** Your office should look like **your** office — plain words up front, your widgets, and a **poem tree** of what Mag has learned (skills, fixes, curious mistakes) that you can browse like a garden, not a settings maze.

---

## 1. Problem (why this doc exists)

Today the dashboard is **powerful but expert-shaped**: tabs, jargon, fixed layout. Mag already **learns** (improve, FKB, behavioral themes, model tesuji) but learning is buried in `memory/improve/` — not something a layman **sees and navigates**.

You want:

1. **Layman first** — grandma could open Office and know if Mag is OK  
2. **Customizable** — move panels, hide noise, pick a theme, save layout on disk  
3. **Tesuji Grove** — poem-style **skill tree** of Mag learnings, errors classified, skills unlocked  

All v3. Does not block v2 merge.

---

## 2. Layman layer (what everyone sees)

### 2.1 Plain-English home (fixed copy — not configurable)

Always visible at top of Office:

| Question | Answer on screen | Metaphor |
|----------|------------------|----------|
| Is Mag OK? | Green / yellow / red + one sentence | "Is the building open?" |
| What happened last? | Last bead title + 3 bullets | "Yesterday's filed folder" |
| What's next? | Top queue item or bond | "Top of the in-tray" |
| Am I pausing Mag? | "You're coding — night shift paused" | "Do not disturb sign" |

No Verkle, no lattice, no provider IDs in layman mode.

### 2.2 Layman mode toggle

```text
Settings → "Plain office" ON
  hides: Status instruments, Lattice, Blast, model quotas
  shows: Office · Days · Chat · Grove (skill tree)
  default: ON for new installs
```

Stored in: `state/mag_preferences.json` → `layman_mode: true`

---

## 3. Customizable dashboard (your layout on disk)

### 3.1 Metaphor

The dashboard is a **wall of cork boards**. You choose which boards hang, how big, and what color the room is. The **files in the filing cabinet** (residual) never change when you move a board.

### 3.2 Widget catalog (v3)

| Widget id | Layman name | What it shows |
|-----------|-------------|---------------|
| `office_now` | Right now | Queue + bonds + pause state |
| `last_bead` | Yesterday | Latest residual card |
| `pulse` | Heartbeat | Honest activity strip |
| `chat` | Talk to Mag | Ask + pack button |
| `grove` | **Tesuji Grove** | Poem skill tree (§4) |
| `in_tray` | To-do | `queue/todo.md` checked items |
| `night_shift` | Overnight | Autorun card summary |
| `curious_errors` | Oops garden | Classified failures (FKB) |
| `depth_status` | Expert vitals | Hidden unless layman off |

### 3.3 Layout file (operator-owned)

```json
{
  "schema": "mag_dashboard_layout.v1",
  "layman_mode": true,
  "theme": "terminal_green",
  "columns": 2,
  "widgets": [
    {"id": "office_now", "row": 0, "col": 0, "w": 2},
    {"id": "grove", "row": 1, "col": 0, "w": 1},
    {"id": "last_bead", "row": 1, "col": 1, "w": 1},
    {"id": "chat", "row": 2, "col": 0, "w": 2}
  ],
  "hidden": ["lattice", "blast", "models"]
}
```

Path: `memory/operator/dashboard_layout.json` (mounted in container)  
API (v3): `GET/PUT /api/v1/operator/layout`  
CLI (v3): `python main.py office-layout --export|--import`

### 3.4 Themes (cosmetic only)

| Theme | Vibe |
|-------|------|
| `terminal_green` | Default Mag — mono, dark |
| `plain_paper` | Light, high contrast, no glow |
| `night_desk` | Dim amber — second virtual desktop |
| `custom` | CSS vars in `memory/operator/theme.css` |

**Rule:** theme never changes data tiers or routing — cosmetics only.

---

## 4. Tesuji Grove — poem-style skill tree

### 4.1 Metaphor

A **bonsai grove** behind the office window. Each branch is something Mag **learned** — a skill, a fix, a classified mistake, a stolen tesuji from a model card. Each node has a **short poem** (layman) and **depth on click** (expert).

Not a game with XP. A **museum of competence** — honest, filed, forkable.

### 4.2 Node kinds (classification)

| Kind | Icon | Source on disk | Poem example |
|------|------|----------------|--------------|
| **skill** | leaf | `configs/skills.yaml` · promoted weave | *"Pack before speech — envelope, not scroll."* |
| **tesuji** | stone | `memory/improve/evals/models/*.md` Take rows | *"Cache the preamble; pay once per song."* |
| **remedy** | bandage | `memory/remedies/*.md` · FKB | *"Empty well? Janitor draws first."* |
| **curious_error** | firefly | FKB + behavioral leaf | *"Three echoes empty — guard stops the wheel."* |
| **chord_loop** | knot | `chord_lens` loop ids | *"Plans grew faster than soil — breathe, file."* |
| **practice** | path | `candidates.jsonl` promoted | *"Steer at the knot, not the waterfall."* |
| **locked** | seed | scout candidate not promoted | *"A seed in the tray — you have not planted."* |

### 4.3 Poem line rules (caveman + lyric)

- **One or two lines** max on the node face  
- Plain English; metaphor allowed; no jargon without tooltip  
- Must point to a **real file path** on expand  
- Optional: `attribution` (model card, session id, date)  
- Generated: local gemma:2b from remedy/leaf text — **human can edit** poem in `memory/grove/nodes/{id}.json`

### 4.4 Tree shape (not a RPG grid)

```text
                    [ ROOT: Mag office open ]
                           |
          +----------------+----------------+
          |                                 |
    [ Seats & tokens ]              [ Filing & memory ]
          |                                 |
    skill: pack-first                 skill: FILE block
    remedy: tier gate                 tesuji: verkle tip
          |                                 |
    curious_error: empty DS           chord_loop: plan_inflation
          |                                 |
    (branches grow as promote + FILE events append)
```

**Layout engine (v3):** force-directed or vertical "vine" — user picks in layout JSON: `grove_style: vine | radial | list_poem`

### 4.5 Node record (schema)

```json
{
  "schema": "grove_node.v1",
  "id": "grove-rem-empty-deepseek",
  "kind": "curious_error",
  "status": "learned",
  "poem": "The well echoed empty;\njanitor drew first.",
  "title": "DeepSeek empty reply guard",
  "source_path": "memory/remedies/rem-empty-deepseek.md",
  "parent_ids": ["grove-skill-pack-first"],
  "unlocked_at": "2026-08-03T14:06:00Z",
  "tags": ["seat", "deepseek", "guard"],
  "classifier": "fkb_auto",
  "steal_score": null
}
```

Index: `memory/grove/index.jsonl` (append-only, like candidates)  
Build: `python main.py grove-build` (scan remedies, skills, tesuji leaves, behavioral — idempotent)

### 4.6 Classifying curious errors

| Step | Who | Action |
|------|-----|--------|
| 1 | FKB | Failure signature → remedy card |
| 2 | grove-build | Propose kind + draft poem (local janitor) |
| 3 | Operator | Edit poem or reclassify in UI |
| 4 | promote | Optional: weave → skill branch |

**Layman view:** "Oops garden" widget — last 5 curious errors as poems, tap to see "what we do now."

---

## 5. Use cases (layman stories)

### Story A — "Is it working?"

Maria opens Office. Plain mode. Green: **"Mag is OK. Last night: 2 jobs filed."** She doesn't touch Settings. Done.

### Story B — "What did Mag learn?"

Nacho opens **Grove**. Sees a new firefly node: *"Three echoes empty — guard stops the wheel."* Taps → reads remedy + which autorun cycle triggered it. Edits poem to shorter line. Files to `memory/grove/nodes/…`.

### Story C — "My dashboard, my desk"

Moves Chat below Grove, enables `night_desk` theme for virtual desktop 2. Layout saves to disk. Container upgrade doesn't wipe it (mounted `memory/operator/`).

### Story D — "Classify this weird loop"

Improve scout surfaces harness pattern. Operator writes tesuji leaf. `grove-build` adds **stone** node under "Seats & tokens." Promote later → **path** node. Tree grows; chat doesn't.

---

## 6. v3 implementation phases

| Phase | Deliverable | Layman win |
|-------|-------------|------------|
| **A** | `layman_mode` toggle + copy pass on Office | Less jargon |
| **B** | `dashboard_layout.json` + 3 widgets | Custom cork board |
| **C** | `grove-build` + `memory/grove/` + list_poem UI | See learnings as poems |
| **D** | Interactive vine + edit poem + classify | Curious errors garden |
| **E** | Themes + import/export layout | Second desk aesthetic |

**v2 may ship:** plain copy on autorun card (Phase A partial). Full grove = v3.

---

## 7. Alignment (P1–P6)

| Purpose | How grove/layout serves it |
|---------|----------------------------|
| P1 sovereignty | Layout + grove on operator disk |
| P2 honest files | Every node cites `source_path` |
| P3 fork | Empty install = default layout + empty grove |
| P4 seat economics | Poems teach pack-first, not "use bigger model" |
| P5 human gate | promote still required for config changes |
| P6 emergent | Tree shape grows from real FILE events — unpredicted |

---

## 8. Anti-patterns

- Gamification scores / streaks / "level 47 mag"  
- Poems with no file backing (theater)  
- Auto-promote when node appears  
- Skill tree that hides failures (curious_errors required)  
- Custom theme that looks like ship is OK when phoenix failed  

---

## 9. For LLMs loading this doc

When operator asks for layman UI or skill tree:

1. Read this file + `DASHBOARD_DESIGN.md`  
2. Data lives in `memory/grove/`, `memory/operator/`, FKB, `configs/skills.yaml`  
3. v3 only — do not block v2 router merge  
4. Poems: short, honest, path-linked  

---

*End layman office vision — append to `MAG_v3_BACKLOG.md` as v3-011, v3-012.*
