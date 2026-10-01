"""Constants for Mag harness."""

from pathlib import Path

# Spore seed file pattern
SPORE_SEED_FILE = Path("memory/spore_seeds/{seat_id}.jsonl")

# The ONE decay constant on compiled law (L3 unification, ball-20260929
# quantizer-hygiene): a compiled thought pack goes STALE past PACK_STALE_DAYS
# for its producer (recompile owed), its consumer (law hidden as visible
# debt), and the boot freshness meter. Before 2026-09-29 the three surfaces
# hardcoded three uncoordinated TTLs on the same resource: the producer probe
# said 24h (thought_quantizer.check), the consumer said 7d
# (context_pack._quantized_laws), boot docs said 7d/2d (freshness_check).
# 7 is the bar the estate's other freshness surfaces already shared
# (configs/fossil_registry.json bar_hours=168 for the compile report, the
# boot-doc bar, the census bar); the producer probe now agrees with it, so
# the subsumption relation w4-27 L3 found missing is stated here in code.
PACK_STALE_DAYS = 7
