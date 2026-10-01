# ESTATE CATALOG DESIGN — one store, one catalog, groups as views
### 2026-09-16 · the operator's law: everything is one directory, split apart by cataloging, not by a million recreated folder schemes · no sacred cows · navigable or it doesn't count

## THE LAW

**Physical location is history. The catalog is the map. Groups are views over
the catalog, never folders you have to hike through.**

## THE ARCHITECTURE (three pieces)

### 1. THE STORE — where files physically live
New artifacts land in ONE forward store (date-sharded if needed). Existing
files DO NOT MOVE — the catalog indexes them in place. Migration happens
lazily, per-file, only when a file is next touched. The old tree atrophies
naturally instead of dying in a big-bang move.

### 2. THE CATALOG — the map (append-only, JSONL)
One row per known file:
```
{"id": "<sha256(path)[:12]>", "path": "watch/inbox/...", "bytes": N,
 "mtime": "2026-09-16T01:20:00Z", "zone": "intake", "ext": ".md",
 "title": "first heading or filename"}
```
Rows are append-only; the latest row per path wins. The catalog is the
authority on WHAT EXISTS and WHERE — not the folder tree.

Zones (the view keys): intake · astra · doctrine · runs · basecamp · campaigns ·
registry · games · code · research · dashboard · memory · vault · external.

### 3. RELATIONS — the graph layer (phase 2)
`relations.jsonl`: one row per relationship:
```
{"from": "<id>", "to": "<id>", "kind": "derived_from|supersedes|witnesses|contradicts|mined_into"}
```
This is where "how things relate to each other" lives — the navigation graph,
queryable, renderable by the deck. The mined-nuance edges (old file → basecamp
camp) become first-class relations: `mined_into`.

## THE TOOLING (exists now)

- `python -m mag.catalog scan [--roots ...] [--max N]` — index in place
- `python -m mag.catalog find [--q TERM] [--zone Z] [--since DATE]` — navigate
- `python -m mag.catalog stats` — the census by zone
- `python -m mag.git_divergence` — the worldline meter (branches)

## THE MIGRATION (phased, no big-bang)

- **Phase 0 (done tonight):** the catalog exists; 1,120 rows over
  intake/doctrine/campaigns/basecamp; find/stats queries live.
- **Phase 1:** expand scan to memory/ (recent), registry, research, games.
- **Phase 2:** the forward store opens (`store/2026-09/`); new artifacts land
  there + get catalog rows.
- **Phase 3:** dedup pass — byte-identical files collapse to one canonical row
  with `dup_of` relations; the copies are marked DUPLICATE in place (never
  deleted — the museum charter holds).
- **Phase 4:** sacred cows get their mined-nuance relations (`mined_into` the
  basecamp camps); the exhibit hall is the query "zone=basecamp OR
  relation=mined_into", not a folder.

## THE LAWS (derived from tonight's failures)

1. **No new organizational folder schemes.** A new grouping is a catalog view.
2. **No file moves without a catalog row.** The row is the truth; the path is
   just where the bytes currently sleep.
3. **A dated snapshot is not current health** (the brief's own law, §8.2) —
   statuses derive from the catalog's latest evidence, never from prose.
4. **Never delete.** The vaults are provenance. Duplicates are emphasis; the
   catalog marks them, the museum keeps them.
5. **If it isn't in the catalog, it doesn't exist** — the inverse is the gift:
   once it IS in the catalog, it can never be lost again.

## WHY THIS SHAPE

A directory tree answers "where is it?" — but the estate's real questions are
"what relates to what," "what's new since," "what did we already try," "which
camp owns this." Those are catalog queries. The folder hierarchy was solving a
problem (physical ordering) we no longer have; the catalog solves the problem
we actually have (navigation and relation). One store, one map, many views.
