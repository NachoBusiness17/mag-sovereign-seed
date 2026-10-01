# Data layers — USER / TRAIN / FRAMEWORK

**Commitment:** `data-layers-001`  
**As-of:** 2026-08-07  
**Parents:** `memory/README.md` · `MAG_TRAINING_DATA_SPEC.md` · `CROSS_AGENT_VERKLE_HANDOFF.md` · `memory/boot/REPUBLIC_LAUNCH.md`  
**Job:** Separate private soil from train export from committable law so forks converge without stealing identity.

---

## One rule

| Layer | Leaves the machine? | Git? | Purpose |
|-------|---------------------|------|---------|
| **USER** | Only by explicit share with terms | **Never** | Your residual, day, machine |
| **TRAIN** | Only redacted export, promote-gated | Never raw; export artifacts optional | How the *harness* learned to route |
| **FRAMEWORK** | Always (public / clone) | **Always** | Direction, spores, code — anyone’s Mag |

**Git thumb:** names *you* or *this machine’s day* → USER. Teaches *anyone’s Mag* → FRAMEWORK. Labels *harness behavior without identity* → TRAIN export.

---

## USER (private soil)

Never commit. Never default-share. Live under `memory/` (see `.gitignore`).

| Path / class | Notes |
|--------------|--------|
| `memory/biography/` | Day beads, residual, Verkle tip chain live |
| `memory/working/`, `working_*.md` | Scratch, not law |
| `memory/agent_sessions/`, `interaction_logs/` | Transcripts |
| `.env`, keys, tokens | Secrets |
| `memory/mail/`, `plans/`, `agent_uploads/` | Operator-private |
| `memory/game_benchmarks/` | Run dumps (this machine) |
| Full Verkle chain + private leaves | Canonical local; share only via `verkle_share` |

Consent: `MAG_BEHAVIOR_LOG=0` can disable behavioral catch. Portable bags are cold copies of *your* tip — still USER until redacted into a share bag.

---

## TRAIN (redacted learning)

Not diary mimicry. Spec: `docs/ref/MAG_TRAINING_DATA_SPEC.md`.

| Path / class | Notes |
|--------------|--------|
| `memory/training/events.jsonl` | `mag_training_event.v1` — gitignored |
| Pattern labels / FKB signatures | Closed vocabulary, no PII |
| `training-export` CLI output | T2-redacted JSONL for republic train dir |
| Eval freezes (orchestration prompts) | Expected seat/phase — may ship as FRAMEWORK fixtures when scrubbed |

**Anti-pattern:** train LoRA on residual prose; second DNA store in a vector cloud.

---

## FRAMEWORK (commit always)

Ships on clone. Empty biography is correct.

| Path / class | Notes |
|--------------|--------|
| `mag/`, `tests/`, `configs/`, `dashboard/`, `main.py` | Product code |
| `docs/ref/*` vision, specs, steals, tesuji | Direction + craft |
| `docs/ref/SPORES.md` | Direction → inspiration → beyond (index) |
| `docs/ref/DATA_LAYERS.md` | This file |
| `memory/boot/REPUBLIC_LAUNCH.md` | Fresh-clone entry |
| `memory/handoff/ACTIVATION.md`, `DEEPSEEK_START.md` | Seat grammar |
| `memory/improve/GOAL.md`, `HABIT.md`, `SEATS.md`, `MIRROR.md` | Improve framework (not personal pins dumps) |
| `memory/operator_directives.md` | Autonomy contract |
| Knowledge pack *stubs*, game module stubs, narrative corpus seeds | Shape, not your play history |
| Force-added improve pins only when product (e.g. public rank recipe) | Prefer redacted |

---

## Spore vs residual (republic convergence)

```text
SPORES (FRAMEWORK)     →  what to look for; what lies beyond
USER residual          →  what I saw on my machine
TRAIN events           →  how seats routed and failed/succeeded
```

Another person builds their mirror, populates **their** USER soil, and re-derives the same insights because spores point at the same windmills — not because they ingested your diary.

---

## Verkle share (bridge, not a fourth DNA)

Share is **not** committing USER to git. It is an operator-sealed bag:

- Graph + summaries + leaf hashes (consultable knowledge graph)
- **Consent block travels with the bag** (`allowed_uses`, `forbid`, tier, attribution, expire)
- Tier T0/T1/T2 redaction; receipt of what was stripped
- Import into another Mag is human-gated

Law sketch: `verkle_share.v1` (implement in Cursor). Parents: `CROSS_AGENT_VERKLE_HANDOFF.md`, portable bag Lessig-6.

---

## Commit checklist

**OK:** code, docs/ref, configs, tests, boot/handoff seeds, scrubbed stubs.  
**Never:** `.env`, biography, working, sessions, uploads, live tip, raw training events with identity.  
**Ask:** force-add under `memory/improve/pins/` — only if non-personal product signal.

---

## One line

Private soil stays home; train is redacted pattern; framework spores let strangers meet at the same republic without wearing your face.
