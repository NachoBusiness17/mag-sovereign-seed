# Home hardware envelope — skills & local models

**As-of:** 2026-08-06  
**Machine:** DESKTOP · 64 GB RAM · AMD RX 5600 XT (~6 GB VRAM) · no CUDA  
**Job:** Run Mag skills and Ollama **inside** this box’s limits. Escalate hard work.

---

## Law

```text
Skill / seat picks model by job size, not ego.
6 GB VRAM → one resident model.
65k context on 8B is a self-own.
Voice stays small. Desk stays qwen-desk. Worker bursts only.
DeepSeek / Grok = judgment + multi-file — not “hello”.
```

## Role → model (home)

| Role | Model | Why |
|------|--------|-----|
| clerk / router / orchestrator scut | `gemma:2b` | Fast, tiny |
| **Voice conversation** | `gemma:2b` (`MAG_VOICE_LOCAL_MODEL`) | ~1–3 s replies |
| desk orchestrator / conductor | `qwen-desk:latest` | Best measured t/s on this GPU |
| biographer / critic (default) | `qwen-desk:latest` | Avoid dual 8B |
| worker short burst | `gemma4:latest` | Heavier; sequential only |
| embed | `nomic-embed-text` | Embeddings only |
| free remote | OpenRouter (if key) | L1 public |
| specialist | DeepSeek / Grok TUI | Scarce |

Config truth: `configs/lanes.yaml` · `configs/providers.yaml`.

## Ollama process env (User)

Set once (restart Ollama app after):

| Var | Home value | Was / avoid |
|-----|------------|-------------|
| `OLLAMA_CONTEXT_LENGTH` | **8192** | 65536 (KV cache explosion) |
| `OLLAMA_MAX_LOADED_MODELS` | **1** | stacking 2b+8B thrash |
| `OLLAMA_NUM_PARALLEL` | **1** | queue, don’t parallel 8B |
| `OLLAMA_KEEP_ALIVE` | **10m** | cold-load every turn |

## Skills operating rules

1. **LOAD** pack + this envelope before inventing Vast/70B paths.  
2. **Scut / smoke / status / voice** → local 2b or qwen-desk only.  
3. **Multi-file implement** → freeze BUILD → DeepSeek/Cursor, not gemma4 looping.  
4. **Never** pull models > home VRAM without operator + `max_auto_pull_gb` (stay 0).  
5. **SAM / ReBAR** optional; does not replace model sizing.  
6. If latency > 15 s local → wrong model or cold 8B; unload and use desk/2b.

## Anti-patterns on this box

- Default chat_provider → gemma4 for “hi”  
- Biographer + worker both loaded  
- `OLLAMA_CONTEXT_LENGTH=65536` with gemma4  
- Voice on gemma4  
- Treating 64 GB system RAM as “more VRAM”  

## Restart after change

```powershell
# Quit Ollama tray app, then reopen — or:
Get-Process ollama* | Stop-Process -Force
# Start Ollama from Start Menu
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent
.\.venv\Scripts\python.exe main.py cast   # voice
# Dashboard if needed: python main.py lab
```

## Probe

```powershell
curl.exe -s http://127.0.0.1:11434/api/ps
.\mag.cmd doctor
# Voice turn should answer in a few seconds on gemma:2b
```

## Voice steal (VAD → pad → pipeline)

- **UI:** `http://127.0.0.1:8766/voice` — energy **VAD** (browser AnalyserNode) owns end-of-turn.
- **Contract:** speech → scratch pad; keep talking → append; VAD quiet + hangover → commit → agent.
- **Pipeline mode:** local format → DeepSeek swarm plan/answer → local humanize ≤90s (`mag/voice_pipeline.py`).
- **Pad API:** `POST /api/v1/voice/scratch` · files under `memory/working/voice_scratch/`.
- **STT steal (shipped):** `faster-whisper` CPU int8 + browser isolation (`echoCancellation`/`noiseSuppression`) via `mag/voice_stt.py` + `POST /api/v1/voice/stt`. No speaker enrollment. Model env: `MAG_VOICE_WHISPER_MODEL` (default `base`).
