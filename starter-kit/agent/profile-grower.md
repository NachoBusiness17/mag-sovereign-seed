---
name: profile-grower
version: 0.1.0
description: >
  Grow the profile from its files: cull phantoms, supersede stale facts
  with lineage, keep the index lean enough to load whole. The maintenance
  half of the recreate-you loop. Trigger: "grow the profile", weekly.
---

# Profile Grower

The profile rots without tending. Three operations, in order:

## 1. Census (phantom hunt)

Every index row must point at a live file. A phantom row is silent
corruption - the system believes a fact it cannot produce.

```bash
python tools/profile_boot.py --memory memory   # exit 2 = phantoms listed
```

For each phantom: find the file (moved? renamed?) and fix the link, or
strike the row. Never delete silently - strike with a date.

## 2. Supersession (append-only aging)

When a fact changes, do not edit it: write the new file, link the old one
(supersedes: <old-file>), and update the index line. The lineage is the
history; the chain is the memory. A profile with no lineage has been
edited, and edited profiles lie about their past.

## 3. Lean (the index diet)

The index is the only always-loaded surface. If it cannot be read in one
sitting, move hooks to coarser topic files. Under ~200 characters a line,
one line per fact - a fat index is a forgetting you have not noticed yet.

## Gates

- Census exit 0 before any batch dispatch that reads the profile.
- No file edited in place after 24 hours of age - supersession only.
- The index loads whole or the diet runs.
