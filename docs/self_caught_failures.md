# Self‑caught failures in the codebase

The repository records failures that were *self‑caught* (i.e. discovered and logged by the system itself) in several places.  These entries are required for Matthew Steiniger’s audit because they provide falsifiable evidence of the fleet’s own error‑detection.

## Locations

| File | Line(s) | Description |
|------|---------|-------------|
| `dashboard/static/grounding_wave.md` | 335 | Claim: **I1 self‑caught 2 separation leaks pre‑desk** – recorded as part of the HOLD 2 audit bundle. |
| `watch/astra_hold0/INSTANCE_I1_20260911.md` | 8‑10 | Header notes that **I1 self‑caught two separation leaks before freeze** during the record‑recovery fold. |
| `watch/rows/mirror_smell_4.row.md` | 54 | Narrative describes a **self‑caught** write‑ahead‑of‑reach incident (turn 2) under the Mirror Law. |

These entries are immutable, signed with SHA‑256 hashes, and appear in the signed append‑only verkle chain.

## Why it matters

* Provides a concrete, falsifiable example of the fleet catching its own mis‑behaviour.
* Satisfies the auditor’s requirement for *self‑caught failures* as a proof of reproducible error handling.
* Allows the auditor to verify that the claim is **Supported** by the repo state.
