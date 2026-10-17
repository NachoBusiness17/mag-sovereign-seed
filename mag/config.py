"""SEED STUB - config
The estate runtime carries the real config module (paths, tiers, provider
map). This stub exists so the load-bearing organs import cleanly from the
seed alone. Replace it with your own config; everything reads ROOT.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
