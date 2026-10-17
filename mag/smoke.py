"""SEED SMOKE TEST - the 30-second cold boot for builders.

Run:  python mag/smoke.py
Needs: Python 3.10+, PyYAML for one organ. Everything else is stdlib.

It does three things, tri-stated like the system itself:
  1. imports every load-bearing organ listed in MANIFEST.md
  2. runs one no-key operation (hashes the seed manifest = a receipt)
  3. prints the first law from the constitution
No network. No keys. No .env. If this passes, the skeleton is alive.
"""

import hashlib
import importlib
import sys
from pathlib import Path

MAG = Path(__file__).resolve().parent
SEED = MAG.parent
sys.path.insert(0, str(SEED))  # package mode: organs using relative imports
sys.path.insert(0, str(MAG))   # flat mode: organs using sibling imports

# The load-bearing organs (see MANIFEST.md for what each one does).
ORGANS = [
    "harness",        # the hub - wires organs together, 12 inbound imports
    "organ_map",      # what organs exist and how they connect
    "policy_engine",  # the behavior law layer
    "lite_guard",     # the safety guard on organ calls
    "research_fanout",# parallel research lanes
    "cascade_research",
    "atlas",          # the doctrine shelf
    "daemon",         # long-running loops
    "steer_bus",      # steering messages between organs
    "switchboard",    # routing
    "verkle_lance",   # tamper-evident chaining
    "water_computer", # liquidity/compute tracking
    "wave",           # the wave protocol
    "kvos_block",     # kv storage block
    "riddler_sanitize",
    "scale_salon",
    "config",         # seed stub - swap in your own
    "audit",          # seed stub - your receipt chain
]

results = []
for name in ORGANS:
    try:
        importlib.import_module(f"mag.{name}")
        results.append((name, "Supported"))
    except Exception as e:  # noqa: BLE001
        results.append((name, f"Disputed ({type(e).__name__}: {e})"))

ok = sum(1 for _, r in results if r == "Supported")

print("=" * 56)
print("MAG SEED SMOKE TEST")
print("=" * 56)
for name, r in results:
    print(f"  [{r:^22}] {name}")
print("-" * 56)
print(f"  organs alive: {ok}/{len(results)}")

manifest = SEED / "SEED_MANIFEST.sha256"
if manifest.exists():
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()[:16]
    print(f"  manifest receipt: sha256:{digest} (tamper-evident chain head)")
else:
    print("  manifest receipt: Disputed (SEED_MANIFEST.sha256 missing)")

constitution = SEED / "boot" / "CONSTITUTION.md"
if constitution.exists():
    first_law = ""
    for line in constitution.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("**"):
            first_law = s
            break
    print(f"  first law: {first_law[:90]}")

print("-" * 56)
verdict = "Supported" if ok >= len(results) - 2 else "Disputed"
print(f"  COLD BOOT: {verdict}")
print("  Tri-state honesty: anything Disputed above is a real defect, not a")
print("  mood. Fix it, delete the organ from ORGANS, or write your own.")
sys.exit(0 if verdict == "Supported" else 1)
