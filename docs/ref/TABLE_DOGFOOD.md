# Mag Table — system test dogfood

**URL:** http://127.0.0.1:8765/table (alias `/play`)  
**File:** `dashboard/static/table.html`  
**Arch:** `docs/ref/TABLE_SHELL_ARCH.md` — shell vs domain (D&D optional later)

## Claim

If Mag works, you can exercise the **table shell** here. Default domain is classic keep dogfood: **text + voice + board + guest advice**.  
Battle Room / Primer surface — not a side toy. Sprites, base-reality, or plain web-ops modes bolt on the same shell.

## Acceptance (Primer hour) — DM skill drill

See also `docs/ref/DM_MAG_TRANSFER.md`.

1. Open `/table` → **New watch**  
2. **classic one (tavern)** → character  
3. **5 Fast turns** without guest (look / rumor / drink / leave / move)  
4. **what should I do?** → **take A** (Slow + confirm)  
5. Freestyle folly or **go fight something**  
6. Board matches log  
7. **seal session** → card under `memory/working/game_sessions/`  
8. Name which Mag seat fired each phase  
9. CLI: `python -m mag.play_benchmark --level B0` still green  

Red path = Mag failed.

## Surfaces

| Pane | Role |
|------|------|
| Pattern canvas | scene · crew · legal chips · guest options |
| Mission log | chat bubbles |
| Composer | text always + mic |

## API

- `POST /api/v1/voice/turn` — turns (game / salon / curveball)  
- `GET /api/v1/table/view?session_id=` — **ASCII map** (`mag_table_view.v1`)  
- `GET /api/v1/game?action=status&session_id=` — scene/legal  

Map is engine-true glyphs only — no image model on the hot path.
