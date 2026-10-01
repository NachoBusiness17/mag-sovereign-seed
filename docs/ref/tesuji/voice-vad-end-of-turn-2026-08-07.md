# voice-vad-end-of-turn — steal tesuji

**schema:** `steal_tesuji.v1`  
**date:** 2026-08-07  
**commitment:** `steal-voice-vad-eot-001`  
**status:** **taken**  
**in Mag:** `dashboard/static/cast-voice.html` (EnergyVAD) · `mag/voice_scratch.py` · `mag/voice_pipeline.py`

---

## 1. Origin (as presented)

| Field | Value |
|-------|--------|
| Names | **Silero VAD**; **Pipecat** (frame pipeline + interrupt); **LiveKit Agents** (session + turn-detection) |
| Host environments | Pipecat Cloud / Daily; LiveKit Cloud; OpenAI Realtime-style “always their stack” |
| Primary refs | github.com/pipecat-ai/pipecat · github.com/livekit/agents · Silero VAD family · 2025–26 voice-agent writeups (turn-taking / barge-in) |
| Host wants | You build *inside* their transport + STT + TTS + orchestration; agent is a tenant of their room |

## 2. Contract we stole (invariant)

`IF end-of-turn is decided by a fixed silence timer alone (not speech activity), THEN the pad commits mid-thought or waits awkwardly after real stops — turn quality collapses.`

**Mechanism:** Voice activity (energy / VAD) marks *speech vs quiet*; hangover after quiet + non-empty scratch pad → **commit** wakes Mag. More speech → **append**, cancel stale wake. Barge-in if speech while Mag speaks.

## 3. Same as our world

- Mag already wanted **scratch pad** of transcript, not one-shot STT→LLM  
- **Generation cancel** = interrupt without host session object  
- **Local-first pipeline** (format → DeepSeek swarm → humanize) matches “cheap workers + scarce frontier”  
- FILE residual / pad on disk = memory outside vendor chat  

## 4. Differs (why not just use the host)

- We refuse WebRTC room as DNA  
- We refuse cloud STT/TTS as the only path  
- Hardware envelope (RX 5600 XT, Ollama) is *ours*, not their GPU SKU menu  
- Grok stays scarce judgment; host would make every turn “frontier-shaped”  

## 5. What we like

- **End-of-turn as a first-class event**, not a UX timeout  
- **Interrupt / barge-in** as normal conversation, not error  
- Frame idea: pad = buffer, commit = frame boundary  
- Separating **STT (words)** from **VAD (activity)** — they solve different failures  
- Multi-step swarm *after* pad is honest, not while mouth is still open  

## 6. What we love

The tesuji is tiny: **who owns “you’re done talking?”**  
When Mag owned it with a fixed 1400 ms, the dream felt broken.  
When **VAD owns it**, the dream matches the body — keep talking, correct yourself, then Mag thinks.

That is the Go-shaped move: local efficiency, fewer moving parts (no second product), higher fidelity to human turn-taking.

## 7. Why grateful we don’t live in the host environment

| Host path | What we’d lose |
|-----------|----------------|
| LiveKit/Pipecat Cloud as brain | Residual DNA on *their* disk story |
| OpenAI Realtime as default voice | Token rent + closed loop; Grok-style scarcity inverted |
| “Just use their agent” | Dashboard museum + no FIND/FILE/LOAD |
| Their STT+TTS only | No offline desk path; no gemma:2b envelope |

**Grateful:** we can steal Silero’s *job* with a browser energy VAD and keep **cast :8766**, **pad files**, **DeepSeek only when committed**, **Unsloth parked until dialogue is real**.  
The host would be fine software. It would not be **sovereign mirror hands**.

## 8. Where it lives inside us

| Layer | Path |
|-------|------|
| VAD + UI | `dashboard/static/cast-voice.html` (`EnergyVAD`) |
| Pad / wake | `mag/voice_scratch.py` · `POST /api/v1/voice/scratch` |
| Pipeline | `mag/voice_pipeline.py` (local→swarm→humanize ≤90s) |
| Law | `docs/ref/HOME_HARDWARE_ENVELOPE.md` · this leaf |
| Trail | `memory/working/voice_scratch/*.json` · `voice_sessions/` |

## 9. Compose (greater than sum)

| Prior Mag piece | Failure | VAD + pad cancel |
|-----------------|---------|------------------|
| Fixed silence timer | Mid-sentence commit | Activity-based hangover |
| One-shot voice/turn | No corrections | Append until EOT |
| gemma4 default chat | 60s timeout / crash feel | Pipeline + 2b + budget |
| PowerShell TTS | Host-ish ghost audio | Browser player only |
| Dashboard fat | Confuses core purpose | Voice page is the dogfood surface |

Together: **dream of conversation** without renting the host’s conversation product.

## 10. Adjacent quarries (wordsearch map)

| Semantic topic | Quarry phrases |
|----------------|----------------|
| Turn-taking | `voice activity detection turn detection barge-in` |
| Pipelines | `pipecat sentence aggregator interrupt frame` |
| Sessions | `livekit agents turn_detector silero` |
| Local STT | `faster-whisper streaming interim transcript` |
| Human TTS | `piper tts streaming sentence boundary` |
| Memory | `letta mem0 voice session episodic` (contract only) |
| Papers | arxiv: realtime voice agent, end-of-utterance, full-duplex dialogue |
| Social | HN “voice agent”; r/LocalLLaMA VAD; r/MachineLearning turn-taking |

Hundreds of improvements live one honest leaf away — **only if we write origin + love + grateful**, not another anonymous port.

## 11. One line

**We stole end-of-turn from the voice-agent field so Mag’s pad can be human; we kept it inside us so the host never owns the residual.**
