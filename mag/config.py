"""SEED STUB - config
The estate runtime carries the real config module (paths, tiers, provider
map). This stub exists so the load-bearing organs import cleanly from the
seed alone. Replace it with your own config; everything reads ROOT.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = ROOT / "configs"
PROMPTS_DIR = ROOT / "prompts"
HANDOFF_DIR = ROOT / "memory" / "handoffs"
RESULTS_DIR = ROOT / "memory" / "results"
WORKING_MD = ROOT / "memory" / "working.md"
