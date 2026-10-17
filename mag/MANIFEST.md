# MAG MANIFEST - the honest map of this directory

Cold numbers first (measured by import-graph analysis, not vibes):

- **1,075** Python files live here.
- **16** of them are imported by other organs. Those are the machine.
- The rest (~1,050) are experiments, probes, one-shots, and fossils that
  import nothing and are imported by nothing. They are kept because a seed
  shows the whole organism, including the sediment. Read them freely; assume
  nothing runs.

## THE CORE (the actual machine, ~285 KB total)

Import them and the skeleton stands up. `python mag/smoke.py` proves it.

| Organ | Role | Imported by |
|---|---|---|
| `harness.py` | THE HUB - wires organs together; 12 inbound imports | everything |
| `organ_map.py` | what organs exist, how they connect | 2 |
| `policy_engine.py` | the behavior-law layer | 2 |
| `lite_guard.py` | safety guard on organ calls | 2 |
| `research_fanout.py` | parallel research lanes | 2 |
| `atlas.py` | the doctrine shelf | 1 |
| `cascade_research.py` | staged research pipeline | 1 |
| `daemon.py` | the background loop (see KNOWN WOUND) | 1 |
| `steer_bus.py` | steering messages between organs | 1 |
| `switchboard.py` | routing | 1 |
| `verkle_lance.py` | tamper-evident chaining | 1 |
| `water_computer.py` | liquidity/compute tracking | 1 |
| `wave.py` | the wave protocol | 1 |
| `kvos_block.py` | kv storage block | 1 |
| `riddler_sanitize.py` | input sanitization | 1 |
| `scale_salon.py` | scale experiments | 1 |
| `config.py` | SEED STUB - swap in your own (reads/writes ROOT) | 2 |
| `audit.py` | SEED STUB - your receipt chain (log_event) | 1 |
| `smoke.py` | the cold boot: tri-state import + receipt check | you |

## KNOWN WOUND (tri-state honesty, filed not hidden)

`daemon` imports `act`, `act` imports `harness.grok_cli` (harness as a
PACKAGE), and `harness.py` line 35 imports `from . import effect_broker`
(also expecting package context) - but the export shipped harness as one
flat file. The code agrees with itself; the export severed it. On the
estate, harness is a directory.

**CONTRIBUTION #1, if you want it:** split `harness.py` into the
`harness/` package it already pretends to be (`__init__.py`,
`effect_broker.py`, `grok_cli.py`, ...). `daemon` comes alive, smoke goes
18/18, and you will have understood the whole organism to do it.

## THE SEDIMENT (~1,050 files)

Experiments, probes, demos, one-shot burns, flagged danglers. Notable
fossils: `_demo_telepathy.py`, `_probe_burst_20260903.py`,
`_flag_dangling_*.py`. Grep freely; there are real ideas buried here, which
is why they ship. Nothing in the sediment is load-bearing.

## FOR BUILDERS, THE 30-SECOND VERSION

    pip install -r requirements.txt   # pyyaml, that's all
    python mag/smoke.py               # tri-state cold boot, no keys, no net

Then: read `boot/CONSTITUTION.md`, read `../THE_SYSTEMS.md`, pick an organ
from the table above, and go. The sediment is a library, not a labyrinth:
`grep -l "def " *.py | head` is a perfectly valid discovery method here.
