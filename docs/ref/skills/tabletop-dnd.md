# tabletop-dnd

Engine-first campaign play for Mag Voice. The DM is the *emergent* narrator — the engine holds
state + legal actions, the LLM paints only what the engine truth allows. One campaign is ONE
instance of a WORLD FAMILY platform (genre corpus + systems grammar), not the product itself.

## Tools
- `mag.game_dice.roll_dice` — deterministic engine rolls, never the LLM.
- `mag.game_campaign` begin_play / set_character / apply_action / save / resume.
- `mag.game_narrate.narrate_scene` — constrained (TinyStories regime: paint engine truth only).
- Module: `memory/game_modules/dnd_classic_stub.v1.json` (classic keep, event tables, traits).
- (later) dnd5eapi / Open5E SRD lookup cache.

## Loop (save → character → act → narrate)
1. **Save check** — resume state first (`game_campaign` resume); never start blind.
2. **Character** — set/take the character from the module; traits are *mechanical levers*, not flavor.
3. **Engine action** — `apply_action` only legal actions; dice roll via `game_dice`.
4. **Narrate facts only** — TinyStories constrain: say what the engine truth allows, nothing invented.

## Steal (emergent systems → hilarious unexpected results)
- **DF / CK3 / RimWorld**: complex systems produce *unexpected* results — let interacting tables,
  traits, and consequences collide into comedy and tragedy. Emergence over script.
- **RimWorld incidents**: inject incident tables at run time so the world *acts*, not just reacts.
- **CK3 traits**: traits as mechanical modifiers that color every legal action.
- **MU\***: persistent, social, world-as-stage — other agents can enter the shared world.
- **TinyStories**: constrained narration — the discipline that makes the chaos legible.

## WORLD FAMILY (zoom out)
The DM product is a *platform*: genre corpus + systems grammar → many worlds. The classic-keep stub
is one seed; new modules (`*.v1.json`) instantiate new families. Steal grammar, not physics claims.
