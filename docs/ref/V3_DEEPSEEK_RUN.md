# v3 DeepSeek code run

**Commitment:** `v3-deepseek-run-001`  
**As-of:** 2026-08-05  
**BUILD:** `docs/ref/BUILD-v3-deepseek-run.md` (frozen)

**One job:** After v2 merge, run **one command** that boots Mag, queues a DeepSeek build goal, drains once, and feeds improve + spider + training events.

---

## 1. Gate (do first on home PC)

```text
Merge PR #8 → #9 → #10 → #11
Pull / merge PR #13 (v3 swarm)
Copy .env.example → .env · set DEEPSEEK_API_KEY
scripts\v3_home_smoke.cmd  → PASS
```

Post-merge ritual:

```powershell
mag.cmd doctor
.\.venv\Scripts\python.exe scripts\routing_smoke.py
python main.py verkle-audit --dry
python main.py v3-status
python main.py switchboard self-test
```

---

## 2. DeepSeek run (one command)

**Windows:**

```cmd
scripts\v3_deepseek_run.cmd "[build] implement pack mode janitor default for ask"
```

**Linux / cloud:**

```bash
chmod +x scripts/v3_deepseek_run.sh
./scripts/v3_deepseek_run.sh "[build] your goal here"
```

**Default goal** (if none passed): wiring smoke — summarize `queue/todo.md` to `memory/working.md`.

### What it does

| Step | Subsystem |
|------|-----------|
| doctor + routing_smoke + v3-status | v2 lattice |
| power start | kill switch / supervisor |
| seats register | Cursor peer |
| orchestrator queue add + drain --once | DeepSeek agent spawn |
| improve-loop cycle | behavioral + nervous + spider |
| training-events --stats | task_lifecycle labels |

---

## 3. Seat law (do not break)

| Seat | When |
|------|------|
| **Ollama** | ask, brief, scut, classify |
| **DeepSeek** | `[build]`, autorun drain, orchestrator queue |
| **Grok** | `[priority]` plan only — frozen BUILD |
| **Cursor** | audit, multi-file hands |

Set `MAG_DRAINER=1` before `power start` for continuous queue drain while AFK.

---

## 4. Manual equivalents

```cmd
mag.cmd power start
queue_deepseek.cmd "your goal"
mag.cmd orchestrator drain --once
mag.cmd improve-loop cycle
mag.cmd spider --once
mag.cmd training-events --stats
```

Or dashboard Chat → **Agent** mode → DeepSeek seat → Send.

---

## 5. Verify wiring (this run shipped)

| Check | Command |
|-------|---------|
| task_lifecycle events | `python main.py training-events --stats` |
| Grove REST | `curl http://127.0.0.1:8765/api/v1/grove?limit=5` |
| Switchboard status | `switchboard_status.cmd` |
| Spider tier steer | `python main.py spider --once --inject` (stall only) |

---

## 6. Chat preflight (CHAT-1–4) — verify before deepseek run

| ID | Check | Pass when |
|----|-------|-----------|
| CHAT-1 | Seat visible | `#chatProvider` shows selected seat |
| CHAT-2 | Cost visible | `#chatPreflight` + `#chatQuota` show deepseek tok/calls |
| CHAT-3 | Mode honest | Default **Ask**; Agent warns → Shell for tools |
| CHAT-4 | No stuck pending | Chip "What was I doing?" returns in Ask mode; no infinite `pending …` |

**Smoke (dashboard open):**

1. Hard refresh (`Ctrl+Shift+R`) — cache bust `app.js?v=v3-chat-ready-1`
2. Chat tab → preflight strip shows `mode=ask · seat=local · deepseek …`
3. Click **What was I doing?** → Ask answer (not Agent tool loop)
4. Switch Agent → send → status shows `tool N…` or times out with error (not forever pending)
5. **Open Shell** for `[build]` goals

Record gate: `python main.py release record --version v3 --gate chat_preflight --ok`

---

## 7. Next waves (after this run passes)

| Wave | BUILD | Seat |
|------|-------|------|
| 1 | `BUILD-pack-modes-janitor.md` | DeepSeek build |
| 2 | Factory pilot `factory-audit-json` | DeepSeek + Cursor audit |
| 3 | Chat Cursor-like (C1–C8) | Cursor |

See `docs/ref/MAG_V3_DISPATCH_PLAN.md` · `docs/ref/MAG_NEXT_CODING_RUN.md`.

---

## 8. If it fails

| Symptom | Fix |
|---------|-----|
| Hang on send | Set `DEEPSEEK_API_KEY` in `.env` |
| routing_smoke fail | Merge v2 PR #8 first |
| v3-status unknown cmd | Pull PR #13 |
| drain busy forever | `mag_kill.cmd` · clear stale `[test]` queue rows |
| Hermes python | Use `mag.cmd` or `.venv\Scripts\python.exe` |

---

*Parent checklist: `docs/ref/V3_HOME_SHIP_CHECKLIST.md`*
