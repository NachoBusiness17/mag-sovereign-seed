# Chat play loop (R0) — only dogfood path

**Active phase:** Play Ladder R0  
**Job:** Chat (or Talk) plays classic keep under engine law. Measure later (R1).

## How to play (voice window)

1. Open **http://127.0.0.1:8765/voice** (lab must be up: `python main.py lab`)  
2. Say or type: **classic one** (keep) or **water one** (hydraulic keep)  
3. **I'm Ash a greedy fighter** (or **random classic**)  
4. Moves: **go north**, **look**, **help**, **inventory**, **attack**, **rest**  
   Water: **go west**, **open valve**, **wait**, **pour bucket** (cheat — not a win)  
5. Pause: **quit game**  

Sticky in-game: while a campaign is active, non-moves stay in the keep (no RAM sludge).

**Talk UI** tab works the same via voice/turn if wired; prefer **/voice** for mic.

**CLI:**

```powershell
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent
$py = ".\.venv\Scripts\python.exe"
& $py -c @"
from mag.game_campaign import begin_play, set_character, parse_character, apply_action
b = begin_play(module_id='classic', voice_session_id='r0', force_new=True)
c = b['campaign_id']
print(set_character(c, parse_character(\"I'm Ash a greedy fighter\")).get('speak','')[:300])
for act in [{'type':'look'},{'type':'move','direction':'north'},{'type':'look'}]:
    r = apply_action(c, act)
    print(act, r.get('ok'), (r.get('narrate') or '')[:120])
"@
& $py -m mag.play_benchmark --level B0
```

## Law

- Engine owns truth; narrate paints only  
- Illegal moves refuse  
- Scoreboard: B0 green + your session feel  
- Thrash? `log_catch` then come back here — don’t invent a new stack  

## Not this phase

Coding auto-agent, skill marketplace, Bernays corpus, overnight code edits.
