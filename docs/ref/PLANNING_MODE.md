# Planning mode — clarify & workshop before committing to big tasks

**Commitment:** `planning-mode-mag-001`
**Status:** IMPLEMENTED (2026-08-02)
**Code:** `mag/plan.py` · gate wired into `mag/dispatch.py` · CLI `python main.py plan ...`
**Parents:** `docs/ref/MAG_OS_v2.md` · `docs/ref/OPERATOR_CARD.md` · `mag/dispatch.py`

---

## What it is

A cheap, local-first clarification pass that runs **before** dispatch commits to a
big/ambiguous/expensive task. It produces a short plan object (goal → scope →
success checks → seat → token budget) the operator can approve, edit, or reject.

Small tasks (list, show, read, brief, recall, status) **skip** the gate entirely.

## When the gate fires

`mag/plan.py::should_plan(goal)` returns True when the goal matches ANY of:

| Signal | Example |
|--------|---------|
| **Length** | goal > ~400 chars |
| **Ambiguity** | "improve", "fix", "make better", "smarter", "know what i mean" |
| **Scope** | "all", "everything", "system", "by default", "incorporate", "refactor", "architecture" |
| **Expense** | "research", "scrape", "analyze deeply", "train", "build", "implement" |
| **Irreversible** | "delete", "archive", "move", "rename", "migrate", "reset" |
| **Explicit** | `plan:` prefix or `--plan` flag |

Small tasks (`list`, `show`, `read`, `brief`, `recall`, `status`, `health`, `doctor`, `quota`) always skip.

## The plan object

Written to `memory/plans/{plan_id}.json` (append-only). Fields: plan_id, goal,
clarified_goal, scope (in/out), success_checks, seat, provider, est_tokens,
steps, open_questions, signals, status (draft|approved|rejected), created.

## CLI

```
python main.py plan list                      # list all plans
python main.py plan show <id>                 # show one plan (JSON)
python main.py plan approve <id>              # mark approved -> dispatch may run
python main.py plan reject <id>               # mark rejected
python main.py plan edit <id>                 # print plan for manual edit
python main.py plan --goal '<goal>'           # fire the gate on a goal (draft plan)
```

## How it works in practice

```
operator: "improve the token efficiency of everything"
  -> PLAN GATE fires (ambiguity + scope + expense)
  -> Mag returns a draft plan + clarifying questions (no tokens burned on exec)
  -> operator answers / edits / says "just do it" to skip
  -> approve -> dispatch runs with clarified goal + success checks
```

The gate is **advisory**: if `mag.plan` raises, dispatch proceeds normally. It
never blocks a small task and never blocks on a plan bug.

## Anti-patterns (guarded)

- **Planning theater** — gate only fires on trigger signals; "just do it" skips.
- **Blocking small work** — list/read/brief/recall/status never gate.
- **Second constitution** — one module, one doc, no dashboard tab.
- **Glory before soil** — the gate is the operational form of "presented-not-interpreted": confirm the target before burning tokens.
