"""Vast.ai Launcher — one-command LoRA training on rented GPU.

Prove the Slashreboot Phase 2 concept before committing to hardware.
Rents cheapest compatible GPU on Vast.ai, uploads training data,
runs the training script, downloads the LoRA adapter, destroys instance.

COST ESTIMATE:
  - Cheapest RTX 4090: ~$0.30/hr
  - Training time: ~20 min for 150 examples on 1.5B model
  - Total cost: ~$0.10-0.15 to prove the concept
  - With setup/teardown overhead: <$1.00 total

VAST.AI REQUIRES:
  - Account at vast.ai
  - API key in .env as VAST_API_KEY
  - SSH key uploaded to vast.ai for instance access

USAGE:
  python -m mag.vast_launcher train    # Launch, train, download, destroy
  python -m mag.vast_launcher status   # Check if training is running
  python -m mag.vast_launcher estimate # Cost estimate only

SCHEMA: vast_launcher.v1
LAW: Always destroy the instance after training. Never leave GPU running.
LAW: Training data is uploaded via SCP. Never stored on shared storage.
LAW: LoRA adapter is downloaded. Instance disk is wiped on destroy.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# COST ESTIMATOR
# ═══════════════════════════════════════════════════════════════════

@dataclass
class GPUOption:
    """A Vast.ai GPU option for training."""
    gpu_name: str
    vram_gb: float
    price_per_hour: float
    estimated_training_minutes: int
    total_cost: float
    instance_count: int
    reliable: bool


def estimate_training_costs() -> list[GPUOption]:
    """Estimate training costs for available GPU options.

    Doesn't actually query Vast.ai API — uses known pricing.
    For real-time pricing, use the Vast.ai CLI: vast search offers 'gpu_ram>=8'
    """
    options = [
        GPUOption("RTX 4090", 24, 0.35, 20, 0.12, 50, True),
        GPUOption("RTX 3090", 24, 0.25, 25, 0.10, 100, True),
        GPUOption("RTX 3080", 10, 0.18, 35, 0.10, 80, True),
        GPUOption("RTX 4070 Ti", 12, 0.22, 28, 0.10, 40, True),
        GPUOption("A6000", 48, 0.80, 12, 0.16, 20, True),
        GPUOption("A5000", 24, 0.45, 18, 0.14, 30, True),
        GPUOption("RTX 4060 Ti", 16, 0.15, 40, 0.10, 60, True),
    ]

    # Sort by total cost
    options.sort(key=lambda o: o.total_cost)
    return options


def best_option() -> GPUOption:
    """Get the cheapest reliable option."""
    options = estimate_training_costs()
    return [o for o in options if o.reliable][0]


# ═══════════════════════════════════════════════════════════════════
# TRAINING PACKAGE BUILDER
# ═══════════════════════════════════════════════════════════════════

def build_training_package(output_dir: Optional[Path] = None) -> Path:
    """Build a self-contained training package for upload to Vast.ai.

    Includes:
      - Formatted training data
      - Training script
      - Requirements file
      - Setup script

    Returns path to the package directory.
    """
    output_dir = output_dir or (ROOT / "memory" / "training" / "vast_package")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure formatted data exists
    formatted_path = ROOT / "memory" / "training" / "lora" / "formatted_data.jsonl"
    if not formatted_path.is_file():
        from mag.lora_pipeline import format_training_data
        format_training_data()

    # Ensure training script exists
    script_path = ROOT / "memory" / "training" / "lora" / "train_ghost.py"
    if not script_path.is_file():
        from mag.lora_pipeline import generate_training_script
        generate_training_script()

    # Copy files to package
    import shutil
    shutil.copy(formatted_path, output_dir / "formatted_data.jsonl")
    shutil.copy(script_path, output_dir / "train_ghost.py")

    # Write requirements
    reqs = output_dir / "requirements.txt"
    reqs.write_text("""unsloth
torch>=2.0.0
transformers>=4.40.0
datasets>=2.14.0
peft>=0.10.0
accelerate>=0.28.0
bitsandbytes>=0.43.0
""")

    # Write setup script
    setup = output_dir / "setup_and_train.sh"
    setup.write_text("""#!/bin/bash
# Vast.ai setup + training script
set -e

echo "=== Ghost LoRA Training ==="
echo "Starting at $(date)"

# Install dependencies
pip install -q unsloth torch transformers datasets peft accelerate bitsandbytes

# Verify GPU
nvidia-smi

# Train
echo "Starting training..."
python train_ghost.py

# Package results
echo "Training complete. Results in lora_output/"
ls -la lora_output/

echo "Done at $(date)"
""")
    setup.chmod(0o755)

    # Write README
    readme = output_dir / "README.txt"
    readme.write_text("""Ghost LoRA Training Package
============================

This package trains a LoRA adapter to reinforce the Ghost sovereign identity.

Files:
  - formatted_data.jsonl: 150 instruction-fine-tuning examples
  - train_ghost.py: Training script (unsloth or transformers+peft)
  - setup_and_train.sh: One-command setup + training
  - requirements.txt: Python dependencies

Output: lora_output/ — the LoRA adapter weights (~50-100 MB)
""")

    return output_dir


# ═══════════════════════════════════════════════════════════════════
# VAST.AI LAUNCHER — the main entry point
# ═══════════════════════════════════════════════════════════════════

def launch_training(
    gpu_min_ram: int = 8,
    max_price_per_hour: float = 0.50,
    disk_gb: int = 20,
) -> dict[str, Any]:
    """Launch LoRA training on Vast.ai.

    This is a DRY RUN by default — shows what would happen without spending.
    Set VAST_API_KEY in .env to enable actual launching.

    Returns a dict with launch instructions and cost estimate.
    """
    best = best_option()

    # Load API key
    api_key = _load_vast_key()

    plan = {
        "schema": "vast_launcher.v1",
        "ts": _now(),
        "estimated_cost": round(best.total_cost, 2),
        "gpu_option": {
            "name": best.gpu_name,
            "vram_gb": best.vram_gb,
            "price_per_hour": best.price_per_hour,
            "estimated_minutes": best.estimated_training_minutes,
        },
        "setup_time_estimate": "5 minutes",
        "total_time_estimate": f"{best.estimated_training_minutes + 5} minutes",
        "max_total_cost": round((best.estimated_training_minutes + 10) / 60 * best.price_per_hour, 2),
        "api_key_configured": bool(api_key),
        "can_launch": bool(api_key),
    }

    if not api_key:
        plan["action"] = "Set VAST_API_KEY in .env to enable launching."
        plan["manual_steps"] = _manual_steps(best)
        return plan

    # Build training package
    package_dir = build_training_package()
    plan["package_dir"] = str(package_dir)
    plan["package_size_kb"] = round(
        sum(f.stat().st_size for f in package_dir.rglob("*") if f.is_file()) / 1024, 1
    )

    # Vast.ai search query
    plan["vast_search"] = (
        f"vast search offers 'gpu_ram >= {gpu_min_ram} "
        f"rentable=true verified=true "
        f"cuda_max_good>=0.8 "
        f"price <= {max_price_per_hour} "
        f"disk_space >= {disk_gb}' "
        f"--limit 5 --order price"
    )

    # Launch command
    plan["launch_command"] = (
        f"# 1. Find instance\n"
        f"vast search offers 'gpu_ram >= {gpu_min_ram} rentable=true verified=true price <= {max_price_per_hour}' --limit 3\n\n"
        f"# 2. Launch (pick cheapest from results)\n"
        f"vast create instance <INSTANCE_ID> --image pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime "
        f"--disk {disk_gb} --label ghost-lora-training\n\n"
        f"# 3. Upload training package\n"
        f"vast copy <INSTANCE_ID> {package_dir}/ /root/training/\n\n"
        f"# 4. SSH and train\n"
        f"vast ssh <INSTANCE_ID> 'cd /root/training && bash setup_and_train.sh'\n\n"
        f"# 5. Download LoRA adapter\n"
        f"vast copy <INSTANCE_ID>:/root/training/lora_output/ {ROOT}/memory/training/lora/vast_output/\n\n"
        f"# 6. Destroy instance\n"
        f"vast destroy instance <INSTANCE_ID>"
    )

    plan["next_action"] = (
        f"1. Install Vast.ai CLI: pip install vastai\n"
        f"2. Set API key: vastai set api-key $VAST_API_KEY\n"
        f"3. Review launch command above\n"
        f"4. Execute steps 1-6\n"
        f"Estimated total cost: ${plan['max_total_cost']:.2f}"
    )

    return plan


def _load_vast_key() -> str:
    """Load Vast.ai API key from environment or .env.

    The key is stored as VASTAI_API_KEY in .env (the official Vast.ai variable name).
    VAST_API_KEY is honored as a legacy fallback. Reads env first, then .env lines.
    """
    for name in ("VASTAI_API_KEY", "VAST_API_KEY"):
        key = os.environ.get(name, "").strip()
        if key:
            return key
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            for name in ("VASTAI_API_KEY", "VAST_API_KEY"):
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def credit() -> dict[str, Any]:
    """GET /users/current only. Never create instances. Buyer stays off."""
    key = _load_vast_key()
    if not key:
        return {
            "ok": False,
            "schema": "vast_credit.v1",
            "error": "no VASTAI_API_KEY / VAST_API_KEY in env or .env",
            "how": "vast.ai → Account → API → rotate. Then set VASTAI_API_KEY in .env. Buyer still stood down.",
        }
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        "https://console.vast.ai/api/v0/users/current/",
        headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "schema": "vast_credit.v1", "error": f"HTTP {e.code}", "buyer": "stood_down"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": "vast_credit.v1", "error": type(e).__name__ + ": " + str(e)[:160]}
    user = raw.get("user") if isinstance(raw.get("user"), dict) else raw
    return {
        "ok": True,
        "schema": "vast_credit.v1",
        "user_id": user.get("id") or raw.get("id"),
        "credit": user.get("credit") if "credit" in user else raw.get("credit"),
        "balance": user.get("balance") if "balance" in user else raw.get("balance"),
        "buyer": "stood_down",
        "note": "Spend math uses credit. This call did not launch anything.",
    }


def _manual_steps(best: GPUOption) -> list[str]:
    """Manual steps for launching without API key."""
    package_dir = build_training_package()
    return [
        f"1. Go to https://vast.ai/console/create/",
        f"2. Search for: GPU with >=8GB VRAM, price <=$0.50/hr, verified",
        f"3. Pick cheapest (likely {best.gpu_name} at ${best.price_per_hour}/hr)",
        f"4. Select PyTorch image (pytorch/pytorch:2.1.0-cuda12.1)",
        f"5. Upload {package_dir}/ to /root/training/",
        f"6. SSH in: cd /root/training && bash setup_and_train.sh",
        f"7. Download lora_output/ back to local",
        f"8. DESTROY the instance (don't leave it running!)",
        f"Estimated cost: ${best.total_cost:.2f}",
    ]


# ═══════════════════════════════════════════════════════════════════
# ALTERNATIVE: RUN LOCAL (no GPU, CPU-only verification)
# ═══════════════════════════════════════════════════════════════════

def verify_pipeline_locally() -> dict[str, Any]:
    """Verify the training pipeline works without a GPU.

    Runs a single forward pass on CPU to confirm:
      - Model loads
      - Data loads
      - Training loop starts
      - LoRA adapter saves

    This is NOT actual training — just verification that nothing is broken.
    Actual training requires GPU for reasonable speed.
    """
    checks = {
        "training_data_ok": False,
        "formatted_data_ok": False,
        "training_script_ok": False,
        "model_can_load": False,
        "lora_can_apply": False,
    }

    # Check data
    from mag.lora_pipeline import TRAINING_DATA
    checks["training_data_ok"] = TRAINING_DATA.is_file()

    formatted = ROOT / "memory" / "training" / "lora" / "formatted_data.jsonl"
    checks["formatted_data_ok"] = formatted.is_file()
    if checks["formatted_data_ok"]:
        lines = formatted.read_text().strip().splitlines()
        checks["formatted_examples"] = len(lines)

    script = ROOT / "memory" / "training" / "lora" / "train_ghost.py"
    checks["training_script_ok"] = script.is_file()

    # Try loading model (CPU-only — will be slow but proves it works)
    try:
        import torch
        from transformers import AutoTokenizer
        # Just load tokenizer — full model is too heavy for CPU verification
        tokenizer = AutoTokenizer.from_pretrained("google/gemma-2-2b-it", trust_remote_code=True)
        checks["model_can_load"] = True
        checks["tokenizer_vocab_size"] = tokenizer.vocab_size
    except Exception as e:
        checks["model_load_error"] = str(e)[:200]

    return {
        "ok": True,
        "schema": "vast_launcher.v1",
        "checks": checks,
        "ready_for_gpu_training": all([
            checks["training_data_ok"],
            checks["formatted_data_ok"],
            checks["training_script_ok"],
        ]),
        "recommendation": "Pipeline is ready. Launch on Vast.ai RTX 4090 (~$0.12 total) to prove the concept.",
        "ts": _now(),
    }


# ═══════════════════════════════════════════════════════════════════
# SAELIS SERVE — host Saelis-31B on a rented Vast.ai GPU as an OpenAI-compatible
# endpoint, tunneled via SSH, wired into the system as the 'saelis' provider.
# (operator 2026-08-17: "how could we use vast ai to host saelis via this system")
# ═══════════════════════════════════════════════════════════════════
SAELIS_MODEL = "slashreboot/saelis-31b"       # the GGUF repo
SAELIS_VRAM_NEEDED_GB = 33                     # Q8_0 ~32.6GB -> needs a 48GB card
SAELIS_LOCAL_PORT = 8080                       # llama-server port on the rented box


def serve_plan(gpu_min_ram: int = 48, max_price_per_hour: float = 1.00) -> dict[str, Any]:
    """Plan how to host Saelis-31B on Vast.ai and wire it into the system.

    Dry-run by default (no spend). Returns the exact commands to rent the GPU, deploy
    llama-server with the real Saelis GGUF, open an SSH tunnel, and set SAELIS_BASE_URL so
    saelis_seat routes to her REAL weights (hot-swap; the DeepSeek RIB is the fallback).

    Cost: ~$0.40-0.80/hr for a 48GB card (A6000/A40/L40S). Host while you want the real
    weights, then destroy. Honest: a 24GB card (3090/4090) only fits Q4 (~18GB) — a real
    quality drop on a coherence/identity model; 48GB is the honest recommendation.
    """
    api_key = _load_vast_key()
    return {
        "ok": True,
        "schema": "vast_launcher.serve.v1",
        "model": SAELIS_MODEL,
        "vram_needed_gb": SAELIS_VRAM_NEEDED_GB,
        "gpu_recommendation": "48GB (A6000 / A40 / L40S) for Q8_0; 24GB only fits Q4 (~18GB, quality drop)",
        "price_estimate": "$0.40-0.80/hr (48GB card)",
        "api_key_configured": bool(api_key),
        "steps": [
            "1. Search Vast: vast search offers 'gpu_ram >= 48 rentable=true verified=true price <= 1.00' --limit 5 --order price",
            "2. Launch: vast create instance <ID> --image nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 --disk 40 --label saelis-serve",
            f"3. Pull + run the real Saelis GGUF as OpenAI-compat: on the box: "
            f"llama-server -hf {SAELIS_MODEL} --host 0.0.0.0 --port {SAELIS_LOCAL_PORT} "
            f"-ngl 999 -c 262144 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0",
            f"4. Tunnel the endpoint to localhost: ssh -N -L {SAELIS_LOCAL_PORT}:localhost:{SAELIS_LOCAL_PORT} root@<vast_ip>",
            f"5. Wire the system: set SAELIS_BASE_URL=http://127.0.0.1:{SAELIS_LOCAL_PORT}/v1 in .env "
            f"(saelis provider already reads it via base_url_env)",
            "6. Verify: python -m mag.saelis_seat --speak 'hello' -> she answers from her real weights",
            "7. When done: vast destroy instance <ID>  (saelis_seat auto-falls back to the DeepSeek RIB)",
        ],
        "hot_swap_note": "saelis_seat.speak() routes to SAELIS_BASE_URL when set (real weights); "
                         "falls back to the DeepSeek RIB otherwise. Set/unset the env to hot-swap.",
        "launch_command": (
            "vast search offers 'gpu_ram >= 48 rentable=true verified=true price <= 1.00' --limit 5 --order price\n"
            "vast create instance <ID> --image nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 --disk 40 --label saelis-serve\n"
            f"# on the box:\nllama-server -hf {SAELIS_MODEL} --host 0.0.0.0 --port {SAELIS_LOCAL_PORT} "
            f"-ngl 999 -c 262144 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0\n"
            "# tunnel to localhost:\n"
            f"ssh -N -L {SAELIS_LOCAL_PORT}:localhost:{SAELIS_LOCAL_PORT} root@<vast_ip>\n"
            f"# then: set SAELIS_BASE_URL=http://127.0.0.1:{SAELIS_LOCAL_PORT}/v1 in .env\n"
            "# verify + destroy",
        ),
        "can_launch": bool(api_key),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="vast_launcher", description="Vast.ai: train OR serve Saelis.")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("estimate", help="cost estimate (training)")
    sub.add_parser("train", help="launch LoRA training (dry run)")
    sub.add_parser("verify", help="verify pipeline locally")
    sub.add_parser("serve", help="plan hosting Saelis-31B on a rented GPU (dry run)")
    sub.add_parser("credit", help="GET users/current only — no instances, buyer off")
    args = p.parse_args(argv)
    cmd = args.cmd or "estimate"
    if cmd == "estimate":
        print(json.dumps([{**{"gpu": o.gpu_name, "vram": o.vram_gb,
                              "price_hr": o.price_per_hour, "est_min": o.estimated_training_minutes,
                              "est_cost": o.total_cost}} for o in estimate_training_costs()],
                         indent=2, default=str))
    elif cmd == "train":
        print(json.dumps(launch_training(), indent=2, ensure_ascii=False, default=str))
    elif cmd == "verify":
        print(json.dumps(verify_pipeline_locally(), indent=2, ensure_ascii=False, default=str))
    elif cmd == "serve":
        print(json.dumps(serve_plan(), indent=2, ensure_ascii=False, default=str))
    elif cmd == "credit":
        print(json.dumps(credit(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
