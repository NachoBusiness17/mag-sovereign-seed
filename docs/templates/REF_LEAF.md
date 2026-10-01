# Ref leaf template (`ref_leaf.v1`)

**Commitment:** `ref-leaf-template-001`  
**Job:** One reusable shape so every Mag object files the useful stuff only.  
**Parents:** `docs/DNA.md` · `docs/FRACTAL_BEADS.md` · `docs/ZEITGEIST.md`  
**Honesty:** Card is for lists. Payload is for truth. Derived is optional. Never require PDF to be done.

Copy this skeleton. Keep section order. Prefer tables. Cut costume.

---

## Skeleton (paste and fill)

```markdown
# {Title} — {kind} ref

**Commitment:** `{slug}-00N`  
**Job:** one sentence — what this object is *for*  
**Object:** kind · id · parent_id · ts  
**Honesty:** what this is *not* (1–2 lines)

---

## 1. Card (list face)

**Title:**  
**Blurb:** (≤2 sentences)  
**Bullets:**
- (3–7 max)

## 2. Anchors (reconstruct)

| Field | Value |
|-------|-------|
| id | |
| kind | |
| parent_id | |
| ts_start / ts_end | |
| path / post_id / session_id | |
| content_commit / tip | |

## 3. Payload core (truth)

Tables > prose. What it contains or what happened. No costume.

## 4. Use / jobs (why keep it)

- job tags:
- how used / will be used:

## 5. Edges (where it sits)

| Edge | Target |
|------|--------|
| parent | |
| children | |
| related docs | |
| related sessions | |
| tapestry tags | |

## 6. Claims vs evidence

| Claim | Evidence | Status |
|-------|----------|--------|
| | | shipped / story / quarantine |

## 7. Forward

| Next | Why | Done when |
|------|-----|-----------|
| | | |

## 8. One line

Single verdict sentence.
```

---

## Length budget

| Part | Default max |
|------|-------------|
| Card (title+blurb+bullets) | ~120 words |
| Full leaf | ~800–1200 words (~2 pages) |
| Bullets | 3–7 |
| Deep cut | Only if operator asks |

No subsystem encyclopedia unless `kind=framework` and Job says so.

---

## Display contract

1. **List** = card only  
2. **Open** = full leaf  
3. **Zoom out** = parent card  
4. **Zoom in** = children cards  
5. **Cite** = `kind:id@commit`

---

## Machine twin

Optional JSON beside the markdown: same fields as `ref_leaf.v1.schema.json`.  
Derived PDF/visual: regenerable sticker, never required for lean complete.

---

## Fill rules

See `FILL_RULES.md` for kind → section content.  
Examples: `examples/session_ref_leaf.example.md`, `examples/framework_ref_leaf.example.md`.

---

## One line

**Same eight sections for every object; kind only changes what you put in the boxes.**
