# Research note — flywheel-universe: budgeted Hebbian Kuramoto (thevelvetmonke, 2026-08-27)

Source: https://github.com/velvetmonkey/flywheel-universe (X: @thevelvetmonke).
Author: Ben Cassie. Runnable research code + Lean 4 formalization + Zenodo preprint.
Status: REAL AND CAREFUL, NOT IMMEDIATELY USABLE — steal the math shape, skip the domain.

## What it is
A control/calibration algorithm for oscillator-based Ising machines. Kuramoto
coupled-phase oscillators whose coupling weights W adapt Hebbian-style from
phases, under three disciplines: (1) **budgeted** — each node's total outgoing
coupling capped by a per-node budget, enforced by exact symmetric-Frobenius
projection onto the budget polytope EVERY step (dual root-finder satisfies KKT
to machine epsilon); (2) **fixed support** — weights only on an allowed edge
mask; (3) a hybrid freeze schedule splitting adaptive weight learning from
fixed-weight phase settling. Core theorem: joint (θ, Ẇ) dynamics descend a
constrained surrogate energy; limit points satisfy KKT stationarity. Companion
sorry-free Lean library proves the unprojected core.

## Honesty audit (why we take this author seriously)
- Explicit NOT-claimed section: no SOTA Max-Cut, no hardware primitive, no
  device-native learning law. Results section openly a placeholder.
- Self-quarantined earlier "cosmology" grandiosity into EXPLORATORY_NOTES.md.
- Formal verification with honest gap reporting (which Lean lemmas remain).
That is the tri-state doctrine + "claims must match the bytes" in academic dress,
from an independent lineage.

## Thesis resonance
Paper: "Robustness, Not Cut Quality, Is the Signal." Fleet: "receipts, not
benchmarks"; "cache discipline beats peak performance." Independent re-derivation
of the same value system — meld-pile evidence (our strongest validation class).

## STEAL #1 — budget-projection as R4's formal skeleton (actionable)
The rebuild spec's R4 (adaptive concurrency governor) currently means heuristic
throttles/cooldowns. This repo shows the upgrade: model every lane/seat/box as a
node with a **coupling budget** (tokens/hr, $/hr, concurrent calls), and make the
allocator step = exact projection onto the budget polytope. Consequences:
- allocation provably descends a Lyapunov function → no oscillation, no
  thrash, no "buyer loops spawning five boxes" (tonight's failure class);
- budgets are per-node and per-edge (lane-to-lane), matching fuel_feed's
  lane doctrine and the portfolio economics;
- convergence is a THEOREM, not a hope — the governor stops being vibes.
Implementation path: R4 spec gains a "budget polytope + projection step"
section citing this repo; buyer/governor code adopts it incrementally
(start with the exact-projection allocator over lane budgets, ignore oscillators).

## STEAL #2 — the honest-paper template (public arc)
Claims + explicit not-claims + formal checks + quarantined speculation = the
method post's structure when GLM-5.3/Qwen/council receipts go public.

## SKIP (for now)
The oscillators/Ising hardware themselves — no osc hardware in the fleet, no
Max-Cut workload. Revisit if coherent-Ising-machine rentals ever appear on
vast (the repo's amplitude-heterogeneity study targets Khan et al. arXiv:2510.24416).

## Reproduce (if ever needed)
git clone https://github.com/velvetmonkey/flywheel-universe
python validate_projection.py; python phase2_benchmark.py pilot
Related: [[project-token-render-manager]] (R4), [[project-rocinante-tripartite]].
