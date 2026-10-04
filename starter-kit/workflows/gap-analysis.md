# THE GAP ANALYSIS - a standing workflow composition (v0.1)

One auditor per surface of a work burst, each verifying claims against
bytes, merging into one ranked register. Run after any burst, before the
findings go stale. The register a gap analysis emits IS the next job's
lane table.

## The auditors

One auditor per surface (for a software+docs project: code claims, doc
claims, test claims, number claims, schedule claims, security claims).
Each auditor:

1. Reads the burst's receipts/promises.
2. Verifies each promise against bytes: numbers reproduced, citations
   byte-checked, finish-lines re-verified by running the check.
3. Names gaps: severity x fill-ease (S1-S4 x one-sitting / one-wave /
   owner-only).

## The register

| gap | severity | fill-ease | owner | the one-sitting fix |
|---|---|---|---|---|

Ranked by severity, cut by fill-ease; one-sitting fills go first.

## The laws

- An unattributable drift is a fabrication smell: investigate before
  refreshing any count.
- A count is stamped with instrument, moment, and denominator (the
  census law).
- Every "done" claim is re-verified by RUNNING its check, not by reading
  its receipt.
- Salvage: auditors report as they land; the register merges what
  landed, names what failed.

## The falsifier

A gap analysis that finds zero gaps in a real burst was not looking -
audit the auditors before trusting the clean bill.
