# Table shell architecture — core vs domain skins

**Commitment:** `table-shell-arch-001`  
**Parents:** TABLE_DOGFOOD · PLAY_BENCHMARK · OPERATOR_CARD · game_view  

## Law

**D&D is the default dogfood load, not Mag’s identity.**  
Core = interface + state law + seats. Domains plug in. Views (ASCII → tiles → sprites) sit on the projection API.

```text
TABLE SHELL     chat · composer · voice · canvas host · session · REST
VIEW LAYER      ASCII now → DF tiles optional → sprites later
DOMAIN ENGINE   classic keep now → base_reality / web_desk / code later
MAG LAW         engine truth · pack-first · tiers · FILE · improve
```

## Core (stable)

| Piece | Contract |
|-------|----------|
| `/table` | Log + board pane + composer |
| `POST /api/v1/voice/turn` | intent in → speak + optional state out |
| `GET /api/v1/table/view` | session → grid/board + hud fields |
| Salon pattern | parse → advise → confirm → apply |
| training_events | self-improve soil |

Strip fantasy: shell chrome says **Board / Scene / Legal / Guest**, not “goblin.”

## Domain engine must provide

```text
LOAD state(session)
legal_actions[]
apply(intent) → events + state
scene_or_board for view
optional ask_advice → options
```

Today: `game_campaign` + curveball + salon.  
Later: same interface for ops/web/code modules.

## View must consume only

```text
grid / cells / kinds
title, hooks, legal, guest options
```

Sprites later = same cells, different blit. No engine rewrite.

## Swaps

| You want | Change |
|----------|--------|
| Sprites | tileset/sprite sheet on view layer |
| Base reality / other problems | new domain module + mode |
| Web-only UI | domain = desk/ops; board = status not dungeon |
| No D&D | disable keep module; shell remains |

## Non-goals

- Hardcoded keep nouns in shell JS forever  
- Per-domain full dashboards  
- Image gen every turn as architecture  

## One line

**Shell is the product surface; D&D is the first domain; everything else is a skin or module.**
