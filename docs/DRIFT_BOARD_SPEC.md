# DRIFT_BOARD_SPEC.md - teleo drift verdict history panel

Status: spec v1, filed 2026-09-26 (burn wave B2-64), BEFORE the code that
serves it (build discipline: spec before behavior change). Owner of the
`/static/drift_board.html` surface on the lab UI (`mag.cmd lab`, :8765).

## 1. What it is

A static, build-time-rendered panel that surfaces the weekly teleological
drift verdict history from `memory/runs/adv_arc_50/teleo_drift_stamps.jsonl`
(the T1-T6 ledger written by `tools/drift_pairs_stamp.py`, instrument
`tools/drift.py`). One row per pair:

| column | definition |
|---|---|
| pair | pair_id + pair name + teleo (from the stamp bytes) |
| verdict history | one cell per v2 stamp week, oldest first: `W38=DRIFTING`, `W39=ALIGNED`, ... |
| current corr | `corr_dm_dr` of the latest v2 stamp (by stamped_at) |
| referent age | UTC-today minus the newest referent data date, recomputed live from the referent source with the same filters as `tools/drift_pairs_stamp.py` (see table in section 2). The stamp's `window.end` is shown beside it as provenance |
| DRIFTING-days | if the current verdict is DRIFTING: UTC-today minus the `stamped_at` date where the current unbroken trailing run of DRIFTING v2 stamps began; else 0. Streak start date shown beside the count |

Headline counters: pairs currently DRIFTING (n/6), longest DRIFTING streak,
stalest referent.

## 2. Referent sources (must match the generator's filters)

| pair | referent source | filter |
|---|---|---|
| T1 | memory/corpus/LINKS.jsonl | key `ts` |
| T2 | watch/inbox/mrpool_export/ledger.jsonl | key `date` |
| T3 | queue/lanes/*/trail.jsonl | key `ts` |
| T4 | memory/improve/releases/gates.jsonl | key `ts` |
| T5 | memory/training/events.jsonl | `pattern == "release_milestone"`, regex date pass (241 MB file, do not json.loads every row) |
| T6 | memory/burns/LEDGER.jsonl | key `ts` |

## 3. Honesty laws

1. v1 rows (no `schema` field, undated: ledger lines 1-3) appear in the
   verdict history as `v1(undated)` only. They are EXCLUDED from all
   day-count math: their stamp dates are receipt-attested, not row-attested
   (THE50_W6_T26_DRIFT_STAMP.receipt.json, corrected 2026-09-26). Counting
   them would fabricate dates.
2. The page is a visualization, never the artifact (HOW_TO_MAG_DASHBOARD.md
   rule): every number links its source file path, the page carries its
   generated-at timestamp and the ledger path, so a stale build is visible.
3. Verdict colors come from tools/drift.py thresholds: ALIGNED >= +0.5,
   INVERTED <= -0.5, DRIFTING between, VACUOUS = referent never moved.
   FRAGILE-ALIGNED (tools/drift_pairs_stamp.py _apply_aging_guard, landed
   2026-09-26 after this spec's first filing) renders as ALIGNED's
   provisional form: amber-green, never the unknown-gray fallback, and it
   counts as ALIGNED for DRIFTING-day streak semantics (it breaks a
   DRIFTING streak, it never extends one).
4. A missing or unreadable referent source renders `n/a`, never a guess.
5. No em-dash anywhere in the generated output.
6. The fleetbar (LAW-060) is injected server-side by dashboard/server.py;
   the page must not embed its own copy.

## 4. Build and serve

```
.venv\Scripts\python.exe tools\drift_dashboard.py          # build panel + print md table
.venv\Scripts\python.exe tools\drift_dashboard.py --check  # exit 0 if outputs fresh vs ledger mtime
```

Writes `dashboard/static/drift_board.html`. Served by the existing
`/static/` handler (dashboard/server.py:633); zero server.py changes. The
markdown table is printed to stdout for receipt embedding.

## 4b. Alarm tripwire (B2-225, filed 2026-09-26 before the code)

`--alarm` reuses the same table computation and fires when either threshold
is crossed, per pair:

- DRIFTING streak at or above 14 days (`drifting_days >= 14`), or
- live referent age at or above 30 days (parsed from `ref_age`; an `n/a`
  referent never fires).

On any breach it writes ONE dated inbox row,
`watch/inbox/DRIFT_ALARM_<YYYY-MM-DD>.md` (same-day rerun overwrites, never
duplicate-spam), naming every breaching pair with verdict, streak, streak
start and referent age, prints the same lines to stdout, and exits 2
(house fresh/exit-2 convention). Quiet exits 0 and writes nothing. The
alarm row is a proposal surface only: model text proposes, the
switchboard/effect broker authorizes effects; the ledger and the panel are
never mutated by the alarm.

## 5. Falsifier (pre-registered)

- If the panel's current corr or verdict for any pair disagrees with a
  hand-read of the ledger rows, the renderer is wrong: fix, do not ship.
- If referent age for T4 shows < 30d while gates.jsonl still ends
  2026-08-06, the live recomputation is lying and the build is void.
- If a W40 stamp lands and the panel does not pick it up on rebuild, the
  ledger-read path is stale-cached and fails the `--check` contract.
