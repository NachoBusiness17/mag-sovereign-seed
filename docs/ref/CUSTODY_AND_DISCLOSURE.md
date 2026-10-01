# CUSTODY AND DISCLOSURE LAW — treasury & sensitive facts
*Warmed 2026-08-27, after the riddler-custody conversation. Status: seat doctrine,
operator-ratified in conversation this date. Chain rows may cite this file by path.*

## T0 — THE MATERIAL NEVER TRAVELS

Key material (seed phrases, private keys, signing keys of any treasury) **never
enters any agent context** — no chat, no file the fleet writes, no memory row, no
chain knot, no session transcript. Not because agents betray — archives don't have
intentions. Because everything an agent touches becomes text on disk, and this fleet
*mines its own transcripts for a living*. The map stays human-held, offline, period.
There is no safeguard protocol for T0 material inside agent contexts; "not yet" is
the wrong shape. It is **never**.

## TIERS OF TREASURY INTERACTION

| Tier | What crosses the wall | Agent role |
|---|---|---|
| **Watch-only** | Public addresses only | Full accounting: ledger eyes without hands, balance tracking, GSTD book entries attestable by address |
| **Movement** | Nothing automatic | Agent drafts UNSIGNED transactions → human signs on hardware. Or: fresh petty-cash hot wallet, capped at expendable, revocable, never connected to the main stash |
| **Disclosure** | Facts as riddles | Holdings/status/founder-type facts ride riddler surrogate rows (below); decode is local, at decision time |

## DISCLOSURE ROWS (riddler-encoded facts on chain v2)

```json
{
  "row_id": "<uuid>",
  "type": "riddler.disclosure.v1",
  "epoch": "<YYYYMMDDHHMMSSZ>",
  "surrogate_payload": "<dressed story-fact per mag/riddler.py compile_surrogate conventions>",
  "decode_map_ref": "<pointer/ID into the PRIVATE map — pointer lives here, map never does>",
  "answer_channel": "raw-answer",
  "note": "decode locally at decision time; miners see fiction"
}
```

Rules:
- Decode output must be produced and consumed **locally** — a decoded fact re-typed
  into chat context recreates the plaintext problem. Read it, decide, let it go.
- Use the **raw-answer channel** with the planted `ANSWER:` steer. The consensus-
  illusion measurement (2026-08-10) showed surrogate-action verbs are orthogonal to
  correctness — steering signals only, never decisions.
- Each model/pod sees a different disguised face; no cross-reference infers territory.

## GOVERNANCE

- Two-person rule for any movement tier action: operator present, seat executes draft only.
- Nothing recurring without an epoch-frozen mandate naming cap, cadence, and kill switch.
- Secrets age well in good vaults — there is no urgency exception to T0.
