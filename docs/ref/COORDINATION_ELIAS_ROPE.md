# Coordination — Elias rope / Verkle lattice (multi-agent)

**Commitment:** `coordination-elias-rope-001`  
**As-of:** 2026-08-01  
**Parents:** `OPERATOR_CARD.md` · `DNA.md` · `memory_verkle_map.md` · `run_trail_lattice.md` · `NERVOUS_SYSTEM.md` · mycelial `docs/AGENCY_SHAPE.md` · `docs/CONSTITUTION.md` §11  
**Job:** Name how multi-agent work coordinates on this stack — and what that is *not*.

---

## 1. Thesis

**Coordination = lattice + nervous system, not conversation among decoders.**

Decoders (Grok TUI, local, remote, subagents, workflow workers) are **stateless seats**.  
Continuity is **boundary state**: residual + tip + pack + presented corpus + agent_state + open trail.

```text
ACTIVATE (pack / strike) → WORK (any seat) → FILE (trail core / residual / dig) → next call is cold
```

The **Elias rope** is how beads connect: tip → day residual → run → trail events → bonds.  
The **nervous system** is quantized proprioception: what the body holds *at a glance*, with deep probe on demand.

This is **rope visibility for machines** — the same republic value humans need for the mirror, applied to multi-seat work on **one node**.

---

## 2. Republic feed (do not confuse products)

| | Mycelial Republic | Mag (this instrument) |
|--|-------------------|------------------------|
| Job | Sovereign mirror on operator **presented** rope; fork equality; chord | External state for seats: residual, tip, pack, trail |
| This doc | Instrument body of **one node** | Law for multi-agent LOAD/FILE |

**Constitution §11:** instruments serve data → scaffold → optional train → spore. They are **not** R0 evidence.

**This coordination law does not move W0.0b / R0 / selftest milestones.**  
Soil (annotate, archive, selftest logs) is still the product gate.

**Mycelium ≠ chatty agents.** Mycelium = forked operators, each with their own tip. One Mag tip is **one node**, never the forest (C2).

---

## 3. How this enhances the republic

| Republic value | Enhancement |
|----------------|-------------|
| Rope visibility | Pack + tip + open loops = coarse elephant; dig/residual = probe |
| Chord + audit | Trail cores FILE mid-run so later chords see edges, not heat |
| Agency (notice → draft → L3 nod) | Multi-agent work leaves audit; irreversible still human |
| Anti C6 | Portable lattice layout, not founder-only agent Discord |
| Spore readiness | Healthy single-node body first; interconnect later without king registry |
| Fork equality | Same shape on disk for any operator who runs Mag |

**Does not enhance alone:** annotated density, selftest scores, weight train, multi-operator discovery.

---

## 4. Missing (honest)

| Gap | Status |
|-----|--------|
| Annotate density / archive | Republic product path — not this leaf |
| Inter-node interconnect | Deferred (G4); refuse privileged registry |
| Workers without pack | **Addressed by** `context-pack --agent` + worker prompts |
| Mid-run elephant updates | **Addressed by** trail cores (`trail append` / `file_agent_core`) |
| Idea graph as work topology | Deferred after one live multi-agent trail run |

**Traps:** lattice green ≠ R0 complete; multi-agent team ≠ mycelium; agent mail as interconnect; Mag tip as network root.

---

## 5. Tesuji

> **Treat multi-agent coordination as quantized lattice proprioception (pack + tip + trail cores), not as peer conversation — and treat that lattice as the instrument body of one republic node, never as the republic itself.**

Same family as Kimi MoE ops metaphor: trunk hot (nervous + tip), experts cold (residual / dig), activate few. Do not host 2.8T; steal the sparsity contract.

**Anti-tesuji:** agent-mail frameworks; forest claims from one node; skipping soil because docs feel advanced.

---

## 6. Quantized elephant (ops)

```text
 nervous L0a (body · tips · keys · loops)
              │
        Verkle tips (session · agent_state)
              │
    residual · dig-leaves · bonds · trail cores
              │
     seat A / B / C  — each gets pack + goal, not full DNA
```

| Rule | Meaning |
|------|---------|
| Coarse default | Every worker: nervous + tip + open loops + trail cores + goal |
| Deep probe intentional | Pull residual/dig only when coarse view says the route is live |
| FILE updates proprioception | Peers “see” each other via trail cores, not chat |
| Tip is commitment | What the node contains is chain-backed, not model-asserted |
| Presented stays law | Thesis/mirror asks load L0 as presented — lattice ≠ interpretation |

---

## 7. Blind men contract (agent preamble)

Every subagent / workflow worker / remote seat receives **at most**:

1. Goal + task boundary (orchestrator)  
2. Agent pack (`mag.cmd context-pack --agent` → `memory/agent_preamble_latest.md`)  
3. Optional single artifact path (diff, brief, fixture) — prefer path over paste  

**Forbidden as default:** full chat history, full residual dump, inventing body/keys/status from model memory.

**Remote seats:** pack + goal only; never T0/T1 private raw archive paths (C5).

---

## 8. Mid-run FILE — base + drift (architecture)

Law: `docs/ref/run_trail_lattice.md`. Code: `mag/run_trail.py`.

**Base** freezes at `trail start` (tip short + optional git SHA + ts → `base_id`).  
**Drift** is FILE against that base only — seats stay stateless; lattice holds the variable.

```text
mag.cmd trail start "goal" --seat grok_tui --proactivity narrow [--git-sha HEAD12]
mag.cmd trail base                          # print frozen base_id
mag.cmd context-pack --agent --goal "…"     # preamble includes base_id
mag.cmd trail append "auth gap" --label security --locus "src/auth.py" \
  --drift-kind finding --evidence "src/auth.py:12" [--base-id <must match>]
mag.cmd trail drifts                        # fold view by locus
mag.cmd trail close
```

Helper: `run_trail.file_agent_core(label, summary, *, locus=, drift_kind=, evidence=, base_id=)`  
→ kind `agent_probe`, schema `mag_drift.v1`, **rejects** `base_id_mismatch`.

**Between workflow phases:** re-LOAD pack (trail cores re-inject). Do not swap seat mid-run.  
**Trail cores are audit, not L3 approval** of irreversible acts.

**Time travel:** pin an older tip/git into a **new** run’s base (or re-LOAD prior residual); do not rewrite DNA. Compare `trail drifts` across runs with different `base_id`.

SessionEnd still owns **cold** residual DNA. Trail is warm-mid only.

---

## 9. Workflows are muscles

Grok `.rhai` workflows (e.g. `review-changes`) fire **after** LOAD and **FILE** trail cores.  
They do not replace Mag, strike-chord, or republic soil gates.

---

## 10. Commands

```text
mag.cmd context-pack              # full LOAD for interactive seat
mag.cmd context-pack --agent      # blind-men preamble (coarse elephant)
mag.cmd trail start "goal" --seat grok_tui
mag.cmd trail append "…" --kind agent_probe --core-text "…"
mag.cmd trail cores
mag.cmd trail close
mag.cmd nervous
```

Artifacts: `memory/context_pack_latest.md` · `memory/agent_preamble_latest.md` · `memory/runs/`.

---

## 11. One line

**Lattice is the rope; pack is the sixth sense; trail cores are how the elephant moves; decoders never own the DNA; one tip is one node — not the forest.**
