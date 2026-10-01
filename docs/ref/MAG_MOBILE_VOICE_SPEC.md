# Mag mobile voice — Grok-style handset, router-priced

**Commitment:** `mag-mobile-voice-001`  
**As-of:** 2026-08-05  
**Status:** Product spec — not v2 blocker; pilot after v2 gate  
**Parents:** `MAG_v3_SWARM_VISION.md` · `FRAMEWORK_LOAD.md` · `CONTAINER.md` · `configs/lanes.yaml`

**One breath:** Phone feels like **Grok voice mode**, but Mag **compiles intention cheaply** first (`intention_brief.v1`), then fires smart seats only when depth or escalate demands it. Always-frontier is a quality bar, not the bill. Subscription economics on their side; **pennies on yours**.

---

## 1. Product pitch (honest)

| Their product | Selling point | Mag equivalent |
|---------------|---------------|----------------|
| Grok / ChatGPT voice | Hands-free AI in your pocket | Same UX — **thin client** |
| $20–30/mo subscription | "Unlimited" voice | **Your** APIs + local Ollama — pay per hard turn |
| Cloud memory | Remembers everything | **Pack + residual** on your home disk — not their SaaS |
| One model | Always frontier | **Router** — gemma scut, DeepSeek code, Grok `[priority]` only |

**Mag win:** 80–95% of voice turns are classify / brief / status / scut → **L0 janitor (Ollama)** ≈ $0 marginal. Frontier only when depth demands it.

**Mag constraint:** Phone is a **viewport + microphone**, not the brain. Home PC (or homelab) runs Mag cage; phone connects over **private tunnel** (Tailscale / WireGuard), not public `:8765`.

---

## 2. Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│  PHONE (Android / iOS) — thin client                        │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────────┐  │
│  │ Mic/STT │→ │ Mag Voice │→ │ Speaker │  │ Layman cards │  │
│  │ (native)│  │  session  │  │ / TTS   │  │ Grove/status │  │
│  └─────────┘  └─────┬────┘  └─────────┘  └──────────────┘  │
└─────────────────────┼───────────────────────────────────────┘
                      │ TLS + device token (Tailscale or WSS)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  HOME — Mag container :8765                                 │
│  POST /api/v1/voice/turn  →  route.v2  →  seat execute    │
│  WS  /api/v1/voice/stream →  chunked TTS + partial text     │
│  GET /api/v1/home         →  "Mag OK" layman card           │
└─────────────────────────────────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
      Ollama      DeepSeek       Grok
     (janitor)    (heavy)      (scarce)
```

**Law carries forward:**

- G1 tiers — voice transcript T2 max over wire; T0/T1 never in mobile pack  
- G2 secrets — phone never sees `.env`  
- G3 irreversible — "delete", "publish", "send email" → `wait_human` card on phone  
- Pack-first — not full chat history on every turn  

---

## 3. What needs to be built

### 3.1 Mag backend (home server)

| # | Component | Why |
|---|-----------|-----|
| B1 | **`mag/voice_session.py`** | Turn state: STT text → route → answer → TTS plan |
| B2 | **`POST /api/v1/voice/turn`** | `{text, session_id?, speak?: bool}` → `{answer, seat, route, audio_url?}` |
| B3 | **`WS /api/v1/voice/stream`** | Low-latency partial tokens + TTS chunks (Grok-feel) |
| B4 | **Device auth** | Per-device token in `state/mobile_devices.json` — L3 register |
| B5 | **Voice router profile** | `depth=scut` bias; max 1 Grok escalation per voice session |
| B6 | **TTS server-side option** | Piper / edge-tts on homelab for consistent voice (optional) |
| B7 | **FILE trail** | `memory/runs/voice_trail.jsonl` + training_events `voice_turn` |

### 3.2 Mobile apps

| # | Component | Why |
|---|-----------|-----|
| M1 | **Shared core** (TypeScript) | One logic layer — Expo or React Native |
| M2 | **STT** | iOS `Speech` / Android `SpeechRecognizer` — on-device, no Google cloud if possible |
| M3 | **TTS playback** | Stream PCM/MP3 from Mag or native fallback |
| M4 | **Push UI** | Hold-to-talk + optional wake phrase ("strike the chord") |
| M5 | **Layman home** | Green/yellow/red + last night + top bond — `GET /api/v1/home` |
| M6 | **Offline banner** | "Mag unreachable — cached status only" |
| M7 | **Android + iOS store builds** | EAS / Xcode — after pilot |

### 3.3 Network / ops

| # | Component | Why |
|---|-----------|-----|
| N1 | **Tailscale** (recommended) | Phone → home Mag without port-forward theater |
| N2 | **Reverse proxy + mTLS** (alt) | If no Tailscale — still no raw `:8765` on internet |
| N3 | **Install doc** | Pair device → scan QR with token + tailnet hostname |

---

## 4. Why not build phone-as-brain

| Approach | Problem |
|----------|---------|
| On-phone LLM | Kills battery; weak models; no residual/trail |
| Phone → Grok API direct | Subscription bleed; no router; no FKB |
| Phone → ChatGPT app | Their memory throne |
| PWA only forever | iOS background mic limits — native needed for polish |

**Elegant fit:** Phone = **remote control + ear** for the swarm on your soil.

---

## 5. Voice turn flow (router-priced)

```text
1. Phone STT → transcript (local on device)
2. POST voice/turn { text, session_id }
3. Mag: gather_signals() + classify_depth(transcript)
4. If scut|simple → ask() biographer / janitor (Ollama)
5. If plan + [priority] in session → grok_tui (budget check)
6. If heavy_code → defer: "That's a desk job — queued for home"
7. Answer text → phone; optional TTS stream
8. emit training_event(pattern=voice_turn, …)
9. FILE voice_trail.jsonl
```

**Grok-style "personality" without persona theater:**

- Short spoken answers (conductor caps length for TTS)  
- Optional "voice profile" = **TTS voice id** + **system preamble** from pack — not mirror training  
- Resonance L0e can surface one soil echo: *"You filed a remedy for this last week"*  

---

## 6. Cost model (target)

| Turn type | % of voice | Seat | Marginal cost |
|-----------|------------|------|---------------|
| Status / "is Mag OK" | ~40% | REST home card | ~$0 |
| Ask / brief / bonds | ~35% | Ollama janitor | ~$0 |
| Research / code | ~20% | DeepSeek | $0.01–0.10 |
| Architecture | ~5% | Grok | $0.05–0.30 |

**vs subscription:** $20/mo ≈ 600+ janitor turns you already own.

**Router guardrails:**

- `max_voice_grok_per_day: 3` in `configs/lanes.yaml` (proposed)  
- Autorun never triggered from voice without explicit "run overnight" + L3 confirm  
- FKB blocks repeat failure signatures before burning API again  

---

## 7. Systems to use (recommended stack)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Mobile framework | **Expo (React Native)** | One codebase → Android + iOS; fast pilot |
| Phase 0 pilot | **PWA** + Web Speech API | Validate UX before store |
| Transport | **HTTPS + WSS** | Existing dashboard server extend |
| Tunnel | **Tailscale** | Nacho homelab pattern; zero public expose |
| STT | Native OS APIs | Privacy + latency; no extra subscription |
| TTS (server) | **Piper** (local) or **edge-tts** | Pennies; optional ElevenLabs for premium voice |
| TTS (client) | Native `AVSpeechSynthesizer` / Android TTS | Works offline for cached replies |
| Auth | Device token + tailnet ACL | Simple; rotate via Office UI |
| State | `voice_session_id` → run_trail | DNA law — not phone Keychain as memory |

**Future-proof:** Voice API schema `mag_voice_turn.v1` versioned; mobile app only implements client.

---

## 8. API sketch

### `POST /api/v1/voice/turn`

```json
// Request
{
  "schema": "mag_voice_turn.v1",
  "text": "what happened last night with autorun",
  "session_id": "voice-uuid",
  "speak": true,
  "device_id": "pixel-7-nacho"
}

// Response
{
  "ok": true,
  "answer": "Last night autorun filed two jobs. Both passed routing smoke.",
  "seat": "local",
  "provider": "ollama",
  "route": { "schema": "route.v2", "depth": "scut" },
  "tts": { "mode": "stream_url", "url": "/api/v1/voice/tts/chunk/abc" },
  "layman": { "status": "green", "headline": "Mag OK" },
  "training_event_id": "evt-…"
}
```

### `WS /api/v1/voice/stream`

```text
client → { type: "transcript", text: "…" }
server → { type: "partial", text: "…" }
server → { type: "final", text: "…", route: {...} }
server → { type: "audio", chunk: base64… }
```

---

## 9. Phases (no calendar — gates)

| Phase | Deliverable | Ship criteria |
|-------|-------------|---------------|
| **0** | PWA voice page on `:8765/voice` | Tailscale + ask endpoint works |
| **1** | `voice/turn` REST + device auth | 20 real turns/day dogfood |
| **2** | Expo app TestFlight + internal APK | STT + TTS + home card |
| **3** | WSS streaming + Piper TTS | Feels "Grok smooth" |
| **4** | Store release + Grove widget | Layman Office parity |
| **5** | Training `voice_turn` labels | Conductor learns voice vs desk routing |

**v2 gate first** — router #8 merged before voice profile matters.

---

## 10. Training data (voice patterns)

Emit `voice_turn` events into `memory/training/events.jsonl`:

```json
{
  "pattern": "voice_turn",
  "input": { "transcript": "…", "duration_ms": 3200 },
  "action": { "seat": "local", "depth": "scut" },
  "outcome": { "success": true, "user_barge_in": false, "tts_played": true },
  "pattern_tags": ["status_query", "janitor_sufficient"]
}
```

**Useful labels for conductor:**

- Was janitor enough?  
- Did user re-ask within 10s? (mis-route signal)  
- Did user say "run that on my repo" → desk defer correct?  

Adds to `MAG_TRAINING_DATA_SPEC.md` pattern list.

---

## 11. Security checklist

- [ ] No `:8765` on public internet without auth  
- [ ] Device tokens revocable in Office  
- [ ] Transcripts FILE to trail — operator owns data  
- [ ] Optional: "voice lock" — Face ID before hearing T1 paths  
- [ ] Irreversible intents → push notification + L3 approve on phone  

---

## 12. Backlog registration

**ID:** `v3-013` — Mobile voice client (Android + iOS)  
**Usefulness:** 5 · **Alignment:** 5 (P4 seat economics) · **Alpha blocker:** yes (needs router v2 + tunnel ops)

---

## 13. One paragraph for the roadmap

Grok-style voice is a **UX layer**, not a new brain. Build **thin Android/iOS clients** (Expo) that STT locally and call **Mag home** over Tailscale. Extend dashboard with **`voice/turn` + optional WSS stream**; let **route.v2** keep 80%+ turns on Ollama janitor. TTS via native playback or Piper on homelab. Device auth + layman home card + voice trail FILE to disk. Training emits `voice_turn` events so conductor learns when voice suffices vs defer-to-desk. Subscription apps charge for always-frontier; **Mag charges only when the router escalates** — that's the selling point for pennies.

---

*End mobile voice spec — pair with `MAG_TRAINING_DATA_SPEC.md` for voice_turn labels.*
