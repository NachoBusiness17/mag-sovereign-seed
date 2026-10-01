# Salon loop — local · frontier · clarify · confirm · output

**Schema:** `mag_game_salon.v1`  
**Code:** `mag/game_salon.py` · voice sticky game path  

## Protocol

1. **Local** — parse skills + engine scene  
2. **Frontier guest** — advice card (options + recommend + optional clarify)  
3. **Clarify** — re-speak if chair babbles  
4. **Confirm** — `take A` / `ignore guest` / `surprise me`  
5. **Output** — apply engine + herald  

Frontier never writes map without confirm.

## Voice lines

| You say | Happens |
|---------|---------|
| what should I do / ask the guest / salon | Advice card |
| surprise me | Auto-confirm recommend |
| take A / b / option 1 | Apply that option |
| ignore guest | Dismiss, stay on road |

## Roles

Doorkeeper → Scribe → Herald (local) · Guest of honor (DeepSeek/fallback) · Chair (you)
