# Mag release notes — template (v3+)

**Commitment:** `mag-release-template-001`  
**Job:** Copy for each major version; FILE gate events via `python main.py release record`  
**Schema:** `mag_release_notes.v1`

---

## Copy block

```markdown
# Mag v{N} — Release notes

**Commitment:** `mag-release-v{N}-001`
**Version:** {semver or plan id}
**As-of:** {YYYY-MM-DD}
**Status:** {planned | in_progress | partial | shipped}
**Registry:** `configs/releases.yaml` → `id: v{N}`

---

## Card

**Title:**
**Blurb:** (≤2 sentences)
**Shipped:** (bullets)
**Not shipped / deferred:** (bullets)

---

## Gates (behavioral memory)

| gate_id | Description | Record when |
|---------|-------------|-------------|
| run_a | v2 merge ritual | routing_smoke green |
| factory_pilot | First audit JSON | RUN B |
| chat_preflight | CHAT-1–4 | dashboard strip live |
| v4_mold | Conductor eval green | eval cases pass |
| v5_probe | External seat read-only | route map filed |

```powershell
python main.py release record --version v{N} --gate {gate_id} --ok --note "evidence path"
```

---

## Behavioral lessons (v{N} → v{N+1})

| Episode | Lesson | Carried to |
|---------|--------|------------|

---

## Verify

```powershell
# commands
```

---

## Artifacts children must load

| Doc | Role |
|-----|------|
```

---

## Version-specific placeholders

| Version | Focus | Key artifacts |
|---------|-------|---------------|
| **v3** | Substrate — orchestrator, switchboard, pack, Chat | `MAG_NEXT_CODING_RUN.md`, BUILD specs |
| **v4** | Mold — conductor, steward, eval, cost ledger | `MAG_V4_CONDUCTOR_LOOP_DRAFT.md` |
| **v5** | Forest seats — GSTD, Vast train, XRPL | `MAG_v5_PIPE.md` |

Create `RELEASE_NOTES_v3.md` when RUN A green; do not pre-write shipped bullets until artifacts exist on disk.

---

*Registry index: `VERSION_REGISTRY.md`*
