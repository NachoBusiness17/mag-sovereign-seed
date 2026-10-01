# witness_sampling — statistical honesty at scale

## The claim
Statistical honesty is not achieved by isolated sampling artifacts, but by **convergent multi-witness comparison** (roshomon) anchored deterministically via **verkle knots** (lens_chain).

## What enforces it (three organs)
- **roshomon.py**: multi-witness invariant comparison across N models; convergent statements become the ROSHOMON CORE (higher-confidence truth), divergent statements preserved as perspective. Dispatched via k8s swarm_worker queue, compared through invariants with $0 analysis cost.
- **lens_chain.py**: content-addressed verkle knots with O(log n) inclusion proofs; anchors each resolution deterministically.
- **swarm_worker.py**: dedicated k8s queue drained by CronJob; ensures no double-drain, no local spawns, enforces the discipline at scale.

## The one trap
Treating witness_sampling as a standalone **module** rather than a **cross-cutting discipline** will cause the audit to miss how statistical honesty is actually enforced across the fleet.

## Falsifier
Show a file named `witness_sampling.py` or `witness.py` that implements a sampling-specific module with its own tests and schema. Absence of such a file falsifies the claim that it is a discipline, not a module.
