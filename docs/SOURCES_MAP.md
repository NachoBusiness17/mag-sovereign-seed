# Sources Map — where each piece of the system comes from

*Each piece, sourced to its corpus: git repos, papers, and sites. Marked **verified** when
the arXiv ID was confirmed against the archive; **bib** = canonical bibliographic citation
(no fabricated IDs).*

---

## 1. The Memory (the chain) — content-addressed, append-only, tamper-evident log

- **Papers**
  - [verified] IPFS — Content Addressed, Versioned, P2P File System — J. Benet, 2014. arXiv:1407.3561 (the generalized Merkle DAG: content-addressed block store).
  - [bib] Merkle, R. (1980). "Protocols for Public Key Cryptosystems" — the Merkle tree, the hash-chain root.
  - [bib] RFC 6962, Certificate Transparency — the production append-only, tamper-evident log (rfc-editor.org/rfc/rfc6962).
- **Repos**
  - github.com/git/git — the original content-addressed object store.
  - github.com/ipfs/specs, github.com/protocol/ipfs — content addressing as a system.
  - github.com/gballet/verkle-trie — Verkle trees (Ethereum's chain-as-verkle research), the exact compact proof-tree we mirror.
- **Why:** the chain is a content-addressed log with a verifiable root — this is the entire established corpus for that.

## 2. The Routine (the loop) — event-driven sense → act → rest

- **Papers**
  - [bib] Kephart, J. & Chess, D. (2003). "The Vision of Autonomic Computing." IEEE Computer 36(1) — the MAPE-K loop (Monitor-Analyze-Plan-Execute + Knowledge), the canonical self-managing loop.
  - [bib] Jacobson, V. (1988). "Congestion Avoidance and Control." ACM SIGCOMM — the add-increase / back-off rhythm: work until the signal says back off, then wait.
- **Websites**
  - martinfowler.com/bliki/CircuitBreaker.html — the circuit-breaker pattern (try, fail, open, wait, retry).
- **Why:** the routine is a bounded sense-act loop that sleeps when idle and backs off under load — MAPE-K + circuit-breaker are the established shapes.

## 3. The Quality Check (the gate) — score before you save

- **Papers**
  - [verified] Deep Reinforcement Learning from Human Preferences — Christiano et al., 2017. arXiv:1706.03741 (learning what "good" means from judgments — reward-modeling, the ancestor of the gate).
  - [verified] Self-Consistency Improves Chain of Thought Reasoning — Wang et al., 2022. arXiv:2203.11171 (multiple answers, keep the consistent one — the "is this a real answer" signal).
  - [verified] On Calibration of Modern Neural Networks — Guo et al., 2017. arXiv:1706.04599 (a score that means what it says — the honesty of the number).
- **Why:** the gate scores output before it enters memory; reward modeling + consistency + calibration are the corpus for "know whether an answer is good."

## 4. The Machine Guard (the ceiling) — refuse work when the machine is hot

- **Papers**
  - [bib] Jacobson, V. (1988). "Congestion Avoidance and Control." ACM SIGCOMM — the AIMD law: full speed under the ceiling, halve/back off as you approach it.
- **Websites**
  - martinfowler.com/bliki/CircuitBreaker.html — refuse, open, wait, retry.
  - kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale — the production resource-scaler (limit → scale/refuse).
- **Repos**
  - github.com/kubernetes/autoscaler — the production autoscaling corpus.
- **Why:** the ceiling is load control; AIMD + circuit breakers + autoscaling are the established ways to hold a resource ceiling.

## 5. The Evolving Knowledge (the wave) — ideas breed

- **Papers**
  - [verified] Illuminating Search Spaces by Mapping Elites — Mouret & Clune, 2015. arXiv:1504.04909 (MAP-Elites: keep the best in every cell of the idea space — the "coldest vertices" made algorithmic).
  - [bib] Lehman, J. & Stanley, K. O. (2011). "Abandoning Objectives: Evolution through the Search for Novelty Alone." GECCO 2011, ACM — novelty search: explore what's different, not just what's fit (not on arXiv; cited by canonical reference).
  - [bib] Stanley, K. & Miikkulainen, R. (2002). "Evolving Neural Networks through Augmenting Topologies." Evolutionary Computation 10(2) — NEAT, complexify slowly (the gait applied to evolution).
- **Repos**
  - github.com/CodeReclaimers/neat-python — a maintained NEAT implementation.
- **Why:** the wave is evolutionary computation; MAP-Elites + novelty search + NEAT are the exact algorithm family.

## 6. The Seal (the backup) — verified, signed, rebuildable

- **Repos**
  - github.com/restic/restic — content-addressed, deduplicated, encrypted backups with snapshot verification.
  - github.com/borgbackup/borg — the same family (dedup + integrity-checked archives).
  - github.com/openzfs/zfs — snapshot + checksum-verified storage (the 3-2-1 discipline in filesystem form).
- **Websites**
  - The "3-2-1 backup rule" (three copies, two media, one off-site) — the industry standard, widely documented.
- **Why:** the seal is a verified snapshot; restic/Borg/ZFS are the production corpus for content-addressed, verified backup.

## 7. The Key (who are you?) — forced-choice value ranking

- **Papers / sites**
  - [bib] Stephenson, W. (1953). "The Study of Behavior" — the Q-methodology: forced-choice sorting of statements; the shape of the sort IS the profile. Community: qmethod.org.
  - [bib] Schwartz, S. H. (1992). "Universals in the Content and Structure of Values." Advances in Experimental Social Psychology 25 — the values taxonomy the statements are drawn from.
  - [bib] Greenwald, A., McGhee, D. & Schwartz, J. (1998). "Measuring Individual Differences in Implicit Cognition." JPSP 74 — implicit attitude measurement (the stance-over-knowledge signal).
  - Project Implicit: implicit.harvard.edu — the running implementation of stance measurement.
- **Why:** the key is a forced-choice value sort compared by rank correlation — Q-methodology + Schwartz + implicit measurement are the established corpus.

## 8. The Steering (plant a direction) — seed, not command

- **Papers / sites**
  - [bib] Thaler, R. & Sunstein, C. (2008). "Nudge" — planting a default/seed that steers without commanding.
  - [verified] Deep Reinforcement Learning from Human Preferences — Christiano et al., 2017. arXiv:1706.03741 (preference as the steering signal, not instruction).
  - [bib] Bargh, J., Chen, M. & Burrows, L. (1996). "Automaticity of Social Behavior." JPSP 71 — priming: a planted cue changes behavior without a command.
- **Why:** steering-by-seeding is nudge + preference signals + priming — the corpus for "change direction without ordering."

---

*Verified IDs confirmed against arXiv 2026-08-24. Everything marked bib is cited by canonical
reference; nothing unverified is passed off as a link.*
