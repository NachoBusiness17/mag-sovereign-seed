# One-pager: Wiring gaps (use what you have)

**Commitment:** `mag-wiring-gaps-001`

## Thesis

**More doctrine than wiring.** Connect shipped modules before adding new ones.

## Hot-path pipeline (target)

```text
route(goal) → job + skill_seat + task_estimate
  → build_context_pack(mode, job, goal)
  → spawn + skill preamble
  → terminal → training_event + cost_ledger
  → improve reads events + loop-audit
```

## Top gaps

| Gap | Fix | Uses |
|-----|-----|------|
| Pack always `skills_for_job("default")` | Pass `job` from route | skills.yaml, context_pack |
| No `pack mode` | `janitor\|route\|build\|audit\|plan` | cost_rates pack_modes |
| skill_seat not on spawn | `build_preamble` in agent CLI | skill_seat.py |
| W7 patch-verify **missing file** | Add weave under docs/ref/weaves/ | skills.yaml |
| sovereign-mag path `~/.grok/` | Repo-local fallback | prompts/skills/ |
| loop-audit not in improve intake | Scout reads `--json` snapshot | improve.py |
| Research loops in pack only | resonance goal-scoped; spider scheduled | resonance, spider |

## Shipped but cold

| Module | Wire to |
|--------|---------|
| loop-audit | improve, spider, Office |
| cost-simulator | pre-blast + task_estimate prior |
| training_events | queue terminal, route, skill_gate |
| conductor | pack mode + phase overlay |
| modules.yaml | v3-status / Office health |

## Priority (min bloat)

1. Pack mode + job skills  
2. skill_seat on spawn  
3. Fix W7 + skill paths  
4. Improve ← loop-audit + events  
5. `[steward]` jobs  

## Registry

`configs/modules.yaml` · `mag/loops_registry.py`
