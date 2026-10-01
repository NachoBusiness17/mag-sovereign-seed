# Token-chain test (shipped)

**DeepSeek plans → deterministic local executes.**  
Frontier tokens only on a short plan completion. File scut costs **0** frontier tool-loop tokens.

## Run

```powershell
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent
.\.venv\Scripts\python.exe main.py token-chain --dry
.\.venv\Scripts\python.exe main.py token-chain "Inspect improve field_brief; note top tickets"
```

Dashboard (after lab restart so routes load):

```http
POST http://127.0.0.1:8765/api/v1/token-chain
{"goal": "Inspect improve field_brief", "dry": false}

GET  http://127.0.0.1:8765/api/v1/token-chain
```

## Observe

- `memory/runs/token_chain/latest.json`
- `memory/runs/token_chain/local_note.md`
- `python main.py improve --status` (unchanged; this is separate from improve scout)

## Architecture (Grok prompt role)

1. **Grok (scarce)** — define goal + success criteria only (or skip; default goal is fine).
2. **DeepSeek (T2 planner)** — emit `local_work_order.v1` JSON only.
3. **Local executor** — `read_file` / `list_dir` / `count_lines` / `write_run_note` under Mag root. No LLM required for exec half.

## Live proof (2026-08-06)

- DeepSeek: **386** total tokens (245 prompt + 141 completion)
- Local: 3 steps OK, **0** local LLM tokens
- Artifact: `memory/runs/token_chain/run-20260806T212222Z.json`

## Dashboard vs CLI

Use **CLI** for reliable tests today. Dashboard POST is wired; restart `main.py lab` to pick up the route if 404.
