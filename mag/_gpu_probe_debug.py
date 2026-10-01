"""gpu_probe — run ghost's REAL local GPU reader (rocm-smi/nvidia-smi, the performance screen).
Debug helper only — mirrors ghost.sense()'s direct GPU path. Deterministic, $0."""
import json
import subprocess as sp
import sys

sys.path.insert(0, r"c:\Users\foste\Documents\projects\local_sovereign_agent")

g = {"vram_used_pct": None, "temp_c": None, "util_pct": None, "source": "none"}

# rocm-smi first (AMD)
try:
    r = sp.run(["rocm-smi", "--showmeminfo", "vram", "--showuse", "--showtemp", "--json"],
               capture_output=True, text=True, timeout=8)
    if r.returncode == 0 and r.stdout.strip():
        cards = json.loads(r.stdout)
        c = list(cards.values())[0] if isinstance(cards, dict) else cards[0]
        g = {
            "vram_used_pct": round(float(c.get("VRAM", c).get("Used", 0)) / max(float(c.get("VRAM", c).get("Total", 1)), 1) * 100, 1) if isinstance(c, dict) else None,
            "temp_c": c.get("Temperature", c.get("temp")) if isinstance(c, dict) else None,
            "util_pct": float(c.get("GPU", c).get("Use", 0)) if isinstance(c, dict) else None,
            "source": "rocm-smi",
        }
except Exception as e:
    g["error"] = str(e)[:100]

# nvidia-smi fallback
if g.get("source") == "none":
    try:
        r = sp.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu,utilization.gpu",
                    "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            p = [x.strip() for x in r.stdout.strip().split(",")]
            g = {"vram_used_pct": round(float(p[0]) / max(float(p[1]), 1) * 100, 1),
                 "temp_c": float(p[2]), "util_pct": float(p[3]), "source": "nvidia-smi"}
    except Exception as e:
        g["error"] = str(e)[:100]

print(json.dumps(g, default=str))
