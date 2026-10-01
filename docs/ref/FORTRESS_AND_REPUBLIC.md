# Fortress and Republic — our architectural identity

_Date: 2026-08-09 · Schema: fortress_republic_ref.v1 · Commitment: fortress-republic-001_
_Related: `docs/ref/strike_origin.md`, `../mycelial-republic/docs/CONSTITUTION.md`, `mag/verkle_knot.py`_

---

## 1. The one-line identity

This project runs **two Dwarf-Fortress games at once**: **Fortress Mode** (Mag — a sovereign,
verkle-anchored stronghold full of deterministic agents) **inside a fork-equal civ** (the Mycelial
Republic — no canonical core, no rank, anti-capture). The tension between "my stronghold" and
"no canonical stronghold" **is** the project's identity, not a bug.

---

## 2. Fortress Mode (Mag — `local_sovereign_agent`)

| DF element | Our system |
|---|---|
| The embark / world-gen seed | The napkin post 2026-03-02 (`Test chord: 44 28 K13 e4 Fool`) — the seed that generates the world |
| The hostile site | The denial wall — 2023-08-16 *"There's no evidence"*; the fortress carved out of a world that says it shouldn't exist |
| The fortress | Mag — the working leaf on disk |
| The dwarves | The autonomous agents — router, ghost, drainer, researcher; each with a skill/role |
| Dwarf moods | Strange mood = emergent inspired output; **tantrum spiral = a degenerate loop** (caught by `failure_kb`) |
| Engraving | **The verkle knot** — agents engrave each run's leaf into the tamper-evident chain; the walls tell the fortress's history |
| Magma / fluid physics | **The token economy** — deterministic flow (the particle-flock: the weirdness comes from the flow, not the dwarves' intentions) |
| The circus / the clowns | **The adversarial layer** — CL4R1T4S is a prompt-injection hiding under the fortress; dig too deep (over-escalate to frontier) and you breach the circus |
| The noble / mandates | The **operator (sovereign)** — steers and vetoes are sovereign mandates the whole fortress obeys immediately |

---

## 3. The Republic (Mycelial Republic civ)

The constitution (`../mycelial-republic/docs/CONSTITUTION.md`) is **explicitly anti-capture** —
it refuses to let the fortress become a throne:

- §1 Fork equality: no mirror/node/operator/repo is canonical core.
- §2 No rank / no token privilege.
- C1 rank-by-token → §2; **C2 single "core mirror" / registry throne → §1**; C6 agent infra only the
  founder can run → §1 + open instrument path.

So the fortress (Mag) is **one fort among many**, all fork-equal, joined by voluntary mycelial
interconnect — not the "true" world.

---

## 4. Code is law (the engraving law)

The constitution's sharpest line, and it is pure DF-engraving:

> **"Code is law here: what the software and file layout allow or forbid *is* governance. Written
> rules that are not enforced in path policy, schemas, or audits are aspirational only — amend the
> code or admit the gap."**

A noble's mandate only matters if the fortress actually enforces it. If it's carved on the wall but
not enforced, it's a decorative engraving, not a rule. This is the project's **honesty doctrine**
("trust bytes, not reports"; "amend the code or admit the gap") written as fortress law — and it's
the exact through-line of the surface audit: verkle verifies, spec_gate gates on bytes, failure_kb
catches honesty failures, usefulness-oracles assert output not activity.

---

## 5. The shared world (the bridge)

The shared frozen world — **the verkle root**, "the map is the territory" — is the generated world
all the equal forts live in: the common constitution + protocol + byte-anchored state that makes
many equal forts coherent. The flock reads it, engraves it, and the Republic forks it — but the
*world* is one.

---

## 6. Why this matters

Knowing the identity as **Fortress-and-Republic** explains decisions that otherwise look contradictory:
- Why verkle anchoring matters so much (the fortress must be able to prove its own history).
- Why the constitution is so allergic to rank/capture (the fortress refuses to become a throne).
- Why "amend the code or admit the gap" is law (aspirational engraving isn't governance).
- Why the deterministic particle-flock fits (dwarves whose emergent behavior is reproducible physics,
  not chaos — and therefore verkle-anchorable).

_This is captured as case law (tesuji) so the identity is known, not re-discovered._
