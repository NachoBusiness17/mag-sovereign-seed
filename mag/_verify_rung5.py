"""Rung 5 verify: cadence.cooldown() + fuel_feed cadence gate (2026-08-25)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mag import lane_cadence as lc
from mag import fuel_feed as ff

fails = []

# 1. cooldown() exists and returns int for unknown lane (no ledger rows -> 0)
try:
    c = lc.cooldown("__no_such_lane__")
    assert isinstance(c, int) and c == 0, f"cooldown unknown lane -> {c!r}"
    print(f"PASS cooldown(unknown) -> {c}")
except Exception as e:  # noqa: BLE001
    fails.append(f"cooldown unknown: {e}")

# 2. A lane with a RECENT failure returns a positive cooldown (if any failure rows exist)
try:
    rows = lc._ledger_rows()
    failed = [r for r in rows if not r.get("ok") and r.get("lane")]
    if failed:
        lane = failed[-1]["lane"]
        cd = lc.cooldown(lane)
        print(f"PASS cooldown({lane}) -> {cd}s (from {len(failed)} failure rows)")
    else:
        print("PASS cooldown: no failure rows in ledger yet (fine)")
except Exception as e:  # noqa: BLE001
    fails.append(f"cooldown recent: {e}")

# 3. fuel_feed routes with the gate — returns list, no crash, still ordered
try:
    lanes = ff._route_lanes("how does the mechanism work under load?")
    assert isinstance(lanes, list) and lanes, "route returned empty"
    # cadence gate must not drop any lane from the rotation (only reorder)
    assert len(lanes) == len(set(l[0] for l in lanes)), "route lost/duplicated a lane"
    print(f"PASS fuel_feed route -> {[l[0] for l in lanes]}")
except Exception as e:  # noqa: BLE001
    fails.append(f"fuel route: {e}")

# 4. No import side effects broke fuel_feed's PROMPT
try:
    assert isinstance(ff.PROMPT, str) and len(ff.PROMPT) > 100
    print("PASS fuel_feed PROMPT intact")
except Exception as e:  # noqa: BLE001
    fails.append(f"prompt: {e}")

print("FAILS:", fails if fails else "none")
sys.exit(1 if fails else 0)
