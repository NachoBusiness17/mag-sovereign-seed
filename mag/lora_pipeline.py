"""LoRA Fine-Tuning Pipeline — Slashreboot Phase 2.

Trains a LoRA adapter on the sovereign training data to reinforce the
Ghost identity vector. Phase 1 (prompt-only) is done. Phase 2 (LoRA)
makes the vector persistent across sessions.

HARDWARE OPTIONS (auto-detected):
  - Local 6B inference card: QLoRA 4-bit on Qwen2.5-1.5B or Gemma-2B
  - Vast.ai: rent a 24GB+ GPU for larger models
  - AdventureNLearn SuperGrok: frontier inference (not training)

TRAINING DATA: memory/training/sovereign_training_data.jsonl (150 examples)
OUTPUT: memory/training/lora/ghost-adapter/ (LoRA weights)
TARGET: Qwen2.5-1.5B-Instruct (fits on 6GB with QLoRA 4-bit)

SLASHREBOOT METHOD:
  - Static Body: The LoRA adapter weights
  - Dynamic Body: The context window at inference time
  - ESDT: The tension between Static and Dynamic bodies
  - Vector-framework: The GHOST_IDENTITY_VECTOR injected + LoRA-reinforced

COST ESTIMATES:
  - Local 6B card: $0 (electricity only), ~2 hours for 1.5B model
  - Vast.ai RTX 4090: ~$0.50/hr, ~30 min for 1.5B model
  - Vast.ai A6000: ~$0.80/hr, can train up to 7B model

SCHEMA: lora_pipeline.v1
LAW: Never upload training data. Training is local or on rented GPU with encrypted disk.
LAW: Output is a LoRA adapter, not a full model. Weights are <100MB, easy to distribute.
LAW: The adapter reinforces the identity vector — it does not replace it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

TRAINING_DATA = ROOT / "memory" / "training" / "sovereign_training_data.jsonl"
LORA_OUTPUT = ROOT / "memory" / "training" / "lora" / "ghost-adapter"
PIPELINE_CONFIG = ROOT / "configs" / "lora_pipeline.yaml"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# HARDWARE DETECTION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class HardwareProfile:
    """What hardware is available for training."""

    gpu_name: str = ""
    vram_gb: float = 0.0
    cuda_available: bool = False
    recommended_model: str = ""
    recommended_method: str = ""       # "qlora_4bit", "qlora_8bit", "full_fine_tune"
    estimated_training_time: str = ""
    cost: str = "$0 (local)"


def detect_hardware() -> HardwareProfile:
    """Detect available GPU hardware and recommend training config."""
    profile = HardwareProfile()

    # Check for NVIDIA GPU via nvidia-smi
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = r.stdout.strip().split(",")
            profile.gpu_name = parts[0].strip()
            profile.vram_gb = float(parts[1].strip()) / 1024.0 if len(parts) > 1 else 0.0
    except Exception:
        pass

    # Check PyTorch CUDA
    try:
        import torch
        profile.cuda_available = torch.cuda.is_available()
        if profile.cuda_available and not profile.gpu_name:
            profile.gpu_name = torch.cuda.get_device_name(0)
            profile.vram_gb = torch.cuda.get_device_properties(0).total_mem / 1024**3
    except ImportError:
        pass

    # Recommend based on VRAM
    if profile.vram_gb >= 20:
        profile.recommended_model = "Qwen/Qwen2.5-7B-Instruct"
        profile.recommended_method = "qlora_4bit"
        profile.estimated_training_time = "~60 minutes"
    elif profile.vram_gb >= 8:
        profile.recommended_model = "Qwen/Qwen2.5-3B-Instruct"
        profile.recommended_method = "qlora_4bit"
        profile.estimated_training_time = "~90 minutes"
    elif profile.vram_gb >= 4:
        profile.recommended_model = "Qwen/Qwen2.5-1.5B-Instruct"
        profile.recommended_method = "qlora_4bit"
        profile.estimated_training_time = "~2 hours"
    else:
        profile.recommended_model = "google/gemma-2-2b-it"
        profile.recommended_method = "qlora_4bit"
        profile.estimated_training_time = "~2 hours (CPU fallback: ~8 hours)"

    return profile


# ═══════════════════════════════════════════════════════════════════
# DATA FORMATTER — convert JSONL to instruction format
# ═══════════════════════════════════════════════════════════════════

def format_training_data(
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Format the sovereign training data for instruction fine-tuning.

    Converts raw JSONL into instruction format:
      {"instruction": "...", "input": "...", "output": "..."}

    Each example teaches the model to embody the Ghost sovereign identity.
    """
    input_path = input_path or TRAINING_DATA
    output_path = output_path or (ROOT / "memory" / "training" / "lora" / "formatted_data.jsonl")

    if not input_path.is_file():
        return {"ok": False, "error": f"Training data not found: {input_path}"}

    formatted = []
    try:
        for line in input_path.read_text(encoding="utf-8").strip().splitlines():
            try:
                ex = json.loads(line)
                text = ex.get("text", "")
                source = ex.get("source", "unknown")
                ex_type = ex.get("type", "unknown")

                # Build instruction from source and type
                instruction = _instruction_for(source, ex_type)
                inp = ""
                output = text

                formatted.append({
                    "instruction": instruction,
                    "input": inp,
                    "output": output,
                })
            except json.JSONDecodeError:
                continue
    except OSError:
        return {"ok": False, "error": f"Could not read: {input_path}"}

    # Write formatted data
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in formatted:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    return {
        "ok": True,
        "output": str(output_path),
        "examples": len(formatted),
        "format": "instruction-fine-tuning (Alpaca format)",
        "ready": True,
    }


def _instruction_for(source: str, ex_type: str) -> str:
    """Generate an instruction based on the data source and type."""
    if source == "verkle_chain":
        return "Describe a system event in the sovereign architecture. What happened and what theme emerged?"
    elif source == "nacho_grok_prompt" and ex_type == "frontier_invariant":
        return "Identify a pattern from a frontier model's system prompt that could improve sovereign agent behavior."
    elif source == "nacho_grok_prompt" and ex_type == "reference":
        return "What file contains a frontier model system prompt, and what can we learn from it?"
    elif source == "research_pack":
        return "Summarize a research finding from the sovereign architecture's research library."
    elif source == "session_koan":
        return "What truth did the system learn from a previous session? Express it as a koan."
    elif source == "ghost_identity":
        return "What is the Ghost sovereign agent? Describe its identity, purpose, and constraints."
    else:
        return "Respond as the Ghost sovereign agent would, embodying the sovereign architecture's principles."


# ═══════════════════════════════════════════════════════════════════
# TRAINING CONFIG GENERATOR
# ═══════════════════════════════════════════════════════════════════

def generate_training_config(
    model_name: str = "",
    output_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Generate a training configuration for the LoRA pipeline.

    Returns a config dict that can be used with unsloth, axolotl, or
    a custom training loop. Optimized for consumer GPU (QLoRA 4-bit).
    """
    hw = detect_hardware()
    model = model_name or hw.recommended_model
    output_dir = output_dir or LORA_OUTPUT

    config = {
        "schema": "lora_pipeline.v1",
        "model": {
            "name": model,
            "load_in_4bit": True,
            "bnb_4bit_compute_dtype": "float16",
            "bnb_4bit_quant_type": "nf4",
            "use_flash_attention_2": hw.vram_gb >= 8,
        },
        "lora": {
            "r": 16,                    # LoRA rank — higher = more capacity, more VRAM
            "alpha": 32,                # LoRA alpha — scaling factor
            "dropout": 0.05,            # Regularization
            "target_modules": [
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
            "bias": "none",
            "task_type": "CAUSAL_LM",
        },
        "training": {
            "dataset": str(TRAINING_DATA),
            "formatted_dataset": str(ROOT / "memory" / "training" / "lora" / "formatted_data.jsonl"),
            "output_dir": str(output_dir),
            "num_train_epochs": 3,
            "per_device_train_batch_size": _batch_size(hw.vram_gb),
            "gradient_accumulation_steps": 4,
            "learning_rate": 2e-4,
            "lr_scheduler_type": "cosine",
            "warmup_ratio": 0.03,
            "logging_steps": 10,
            "save_steps": 50,
            "max_seq_length": 2048,
            "packing": False,
            "bf16": hw.vram_gb >= 8,
            "fp16": hw.vram_gb < 8,
        },
        "hardware": {
            "gpu": hw.gpu_name,
            "vram_gb": hw.vram_gb,
            "cuda_available": hw.cuda_available,
            "estimated_time": hw.estimated_training_time,
        },
        "estimated_lora_size_mb": "50-100 MB",
        "ts": _now(),
    }

    # Write config
    PIPELINE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_CONFIG.write_text(json.dumps(config, indent=2))

    return config


def _batch_size(vram_gb: float) -> int:
    if vram_gb >= 20:
        return 4
    elif vram_gb >= 8:
        return 2
    else:
        return 1


# ═══════════════════════════════════════════════════════════════════
# TRAINING SCRIPT GENERATOR (for unsloth)
# ═══════════════════════════════════════════════════════════════════

def generate_training_script(output_path: Optional[Path] = None) -> Path:
    """Generate a ready-to-run training script using unsloth.

    Unsloth is a free, open-source library that makes LoRA fine-tuning
    2-5x faster and uses 70% less memory. Perfect for consumer GPUs.

    Returns the path to the generated script.
    """
    output_path = output_path or (ROOT / "memory" / "training" / "lora" / "train_ghost.py")

    config = generate_training_config()

    script = f'''"""Ghost LoRA Training Script — generated by lora_pipeline.py.

Trains a LoRA adapter to reinforce the Ghost sovereign identity vector.
Uses unsloth for fast, memory-efficient fine-tuning on consumer GPUs.

Hardware: {config["hardware"]["gpu"]} ({config["hardware"]["vram_gb"]:.1f} GB)
Model: {config["model"]["name"]}
Method: QLoRA 4-bit
Estimated time: {config["hardware"]["estimated_time"]}
Output: {config["training"]["output_dir"]}
"""

# This script is designed to work with unsloth.
# Install: pip install unsloth
# Then run: python train_ghost.py

import json
import torch
from pathlib import Path

# === CONFIGURATION ===
MODEL_NAME = "{config['model']['name']}"
DATASET_PATH = "{config['training']['formatted_dataset']}"
OUTPUT_DIR = "{config['training']['output_dir']}"
LORA_R = {config['lora']['r']}
LORA_ALPHA = {config['lora']['alpha']}
LEARNING_RATE = {config['training']['learning_rate']}
NUM_EPOCHS = {config['training']['num_train_epochs']}
BATCH_SIZE = {config['training']['per_device_train_batch_size']}
MAX_SEQ_LENGTH = {config['training']['max_seq_length']}

# === LOAD MODEL WITH UNSLOTH ===
print(f"Loading model: {{MODEL_NAME}}")
print(f"GPU: {{torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}}")

try:
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,  # Auto-detect
        load_in_4bit=True,
    )

    # Add LoRA adapters
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=LORA_ALPHA,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    print(f"Model loaded. LoRA adapters added. Trainable params: {{model.num_parameters(only_trainable=True):,}}")

except ImportError:
    print("unsloth not installed. Install with: pip install unsloth")
    print("Falling back to standard transformers + peft...")

    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        TrainingArguments,
        Trainer,
        DataCollatorForLanguageModeling,
        BitsAndBytesConfig,
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from datasets import Dataset

    # Load in 4-bit
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    print(f"Model loaded (standard). Trainable params: {{model.num_parameters(only_trainable=True):,}}")


# === LOAD DATASET ===
print(f"Loading dataset: {{DATASET_PATH}}")
examples = []
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    for line in f:
        try:
            ex_data = json.loads(line)
            instruction = ex_data.get("instruction", "")
            output = ex_data.get("output", "")

            # Format as instruction prompt
            text = f"### Instruction:\\n{{instruction}}\\n\\n### Response:\\n{{output}}"
            examples.append({{"text": text}})
        except json.JSONDecodeError:
            continue

print(f"Loaded {{len(examples)}} training examples")

dataset = Dataset.from_list(examples)


# === TOKENIZE ===
def tokenize_function(examples_dict):
    return tokenizer(
        examples_dict["text"],
        truncation=True,
        max_length=MAX_SEQ_LENGTH,
        padding="max_length",
    )

tokenized_dataset = dataset.map(tokenize_function, batched=True)
print(f"Tokenized. Sample length: {{len(tokenized_dataset[0]['input_ids'])}} tokens")


# === TRAIN ===
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=4,
    learning_rate=LEARNING_RATE,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    logging_steps=10,
    save_steps=50,
    fp16=True,
    report_to="none",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
    data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
)

print(f"Starting training... {{NUM_EPOCHS}} epochs, {{BATCH_SIZE}} batch size")
trainer.train()

# === SAVE ===
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"LoRA adapter saved to: {{OUTPUT_DIR}}")
print(f"Training complete. The Ghost is now reinforced.")
'''

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(script)

    return output_path


# ═══════════════════════════════════════════════════════════════════
# PIPELINE STATUS — check readiness
# ═══════════════════════════════════════════════════════════════════

def pipeline_status() -> dict[str, Any]:
    """Check if the LoRA pipeline is ready to train."""
    hw = detect_hardware()

    checks = {
        "training_data_exists": TRAINING_DATA.is_file(),
        "training_data_examples": 0,
        "formatted_data_exists": False,
        "gpu_available": hw.cuda_available,
        "gpu_name": hw.gpu_name,
        "vram_gb": hw.vram_gb,
        "recommended_model": hw.recommended_model,
        "estimated_time": hw.estimated_training_time,
        "config_generated": PIPELINE_CONFIG.is_file(),
        "training_script_generated": (ROOT / "memory" / "training" / "lora" / "train_ghost.py").is_file(),
        "ready_to_train": False,
    }

    if checks["training_data_exists"]:
        try:
            lines = TRAINING_DATA.read_text(encoding="utf-8").strip().splitlines()
            checks["training_data_examples"] = len(lines)
        except OSError:
            pass

    # Check formatted data
    formatted_path = ROOT / "memory" / "training" / "lora" / "formatted_data.jsonl"
    checks["formatted_data_exists"] = formatted_path.is_file()

    # Ready check
    checks["ready_to_train"] = (
        checks["training_data_exists"] and
        checks["training_data_examples"] >= 50 and
        checks["gpu_available"] and
        checks["vram_gb"] >= 4
    )

    if not checks["ready_to_train"]:
        if not checks["gpu_available"]:
            checks["blocker"] = "No GPU detected. Use Vast.ai or AdventureNLearn SuperGrok."
        elif checks["vram_gb"] < 4:
            checks["blocker"] = f"Insufficient VRAM ({checks['vram_gb']:.1f} GB). Need 4+ GB for QLoRA 4-bit."
        elif checks["training_data_examples"] < 50:
            checks["blocker"] = f"Need 50+ training examples, have {checks['training_data_examples']}."

    return {
        "ok": True,
        "schema": "lora_pipeline.v1",
        "checks": checks,
        "phase_1_prompt_only": "COMPLETE — ghost_identity.py",
        "phase_2_lora": "READY" if checks["ready_to_train"] else f"BLOCKED: {checks.get('blocker', 'unknown')}",
        "next_action": _next_action(checks),
        "ts": _now(),
    }


def _next_action(checks: dict) -> str:
    if checks["ready_to_train"]:
        return "Run: python memory/training/lora/train_ghost.py"
    if not checks["training_data_exists"]:
        return "Run: from mag.training_packager import package_all; package_all()"
    if not checks["formatted_data_exists"]:
        return "Run: from mag.lora_pipeline import format_training_data; format_training_data()"
    if not checks["gpu_available"]:
        return "No GPU. Options: Vast.ai RTX 4090 (~$0.50/hr) or request AdventureNLearn SuperGrok access."
    return "Review pipeline_status() for details."
