"""GSTD DePIN Substrate — decentralized AI compute & fine-tuning economy.

Ties the Mycelial Republic's sovereign architecture into the Gold Standard
(GSTD) decentralized marketplace. Skills become NFT-rentable assets. Models
become queryable at a price. Spare GPU cycles become economic throughput.

The Republic doesn't own the economy. It provides the VERIFICATION LAYER:
  - Verkle chain proves what work was done
  - Silent Bard encodes the transaction in narrative (story on surface, proof underneath)
  - Task router becomes the marketplace order book
  - Each sovereign instance is its own economic actor

ARCHITECTURE:
  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │  Operator A  │    │  Operator B  │    │  Operator C  │
  │  GPU: 4090   │    │  Model: LoRA │    │  Skill: code  │
  │  Price: 0.01 │    │  Price: 0.05 │    │  Price: 0.001│
  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
         │                   │                   │
         ▼                   ▼                   ▼
  ┌──────────────────────────────────────────────────┐
  │              GSTD MARKETPLACE                     │
  │  (NFT skill registry, escrow, settlement)        │
  └──────────────────────┬───────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────┐
  │           REPUBLIC VERIFICATION LAYER             │
  │  Verkle chain: proof of work done                │
  │  Silent Bard: narrative encoding of transaction  │
  │  Task Router: order matching + cost optimization │
  │  Doctor: sanity checks before settlement         │
  └──────────────────────────────────────────────────┘

SCHEMA: depin.v1
LAW: The Republic verifies. GSTD settles. Operators keep their keys.
LAW: No platform takes a cut. The protocol is the marketplace.
"""

from __future__ import annotations

import hashlib
import json
import os
from mag.chain_query import chain  # auto-added by doctor_agent
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
# SKILL NFT — what gets listed on the marketplace
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SkillNFT:
    """A rentable AI capability — compute, model, or skill.

    Listed on GSTD. Verified by Verkle chain. Encoded by Silent Bard.
    """
    skill_id: str                          # Unique identifier (hash of capability)
    owner_address: str                     # GSTD wallet address
    skill_type: str                        # "compute", "model", "skill"
    name: str                              # Human-readable name
    description: str                       # What it does
    price_per_query: float                 # GSTD per query
    price_per_hour: float                  # GSTD per hour (for compute)
    capabilities: list[str] = field(default_factory=list)  # ["code", "analyze_reason", etc.]
    model_name: str = ""                   # If skill_type == "model"
    gpu_spec: str = ""                     # If skill_type == "compute" (e.g. "RTX 4090 24GB")
    availability: str = "online"           # "online", "offline", "rented"
    verkle_proof: str = ""                 # Verkle chain proof of capability
    bard_passage: str = ""                 # Narrative encoding of this skill
    ts: str = field(default_factory=_now)

    def to_listing(self) -> dict[str, Any]:
        """Export as a GSTD marketplace listing."""
        return {
            "schema": "gstd-skill-nft.v1",
            "skill_id": self.skill_id,
            "owner": self.owner_address,
            "type": self.skill_type,
            "name": self.name,
            "description": self.description,
            "pricing": {
                "per_query": self.price_per_query,
                "per_hour": self.price_per_hour,
            },
            "capabilities": self.capabilities,
            "model": self.model_name or None,
            "gpu": self.gpu_spec or None,
            "availability": self.availability,
            "verkle_proof": self.verkle_proof,
            "ts": self.ts,
        }

    @staticmethod
    def generate_id(owner: str, skill_type: str, name: str) -> str:
        """Deterministic skill ID from owner + type + name."""
        return hashlib.sha256(f"{owner}:{skill_type}:{name}".encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════
# MARKETPLACE — order book for sovereign capabilities
# ═══════════════════════════════════════════════════════════════════

@dataclass
class MarketplaceOrder:
    """A request to rent a skill or model from the GSTD marketplace."""
    order_id: str
    buyer_address: str
    skill_type_needed: str                # "compute", "model", "skill"
    task_type: str                        # "code", "analyze_reason", "research", etc.
    max_price: float                      # Maximum GSTD willing to pay
    payload: dict[str, Any] = field(default_factory=dict)  # The actual work to do
    preferred_provider: str = ""          # Specific provider address (or "" for any)
    verkle_breadcrumb: str = ""           # Links to Verkle chain for audit
    ts: str = field(default_factory=_now)

    def match_score(self, skill: SkillNFT) -> float:
        """How well does a skill match this order? 0-1."""
        score = 0.0

        # Type match
        if skill.skill_type == self.skill_type_needed:
            score += 0.4

        # Capability overlap
        my_caps = set(self.payload.get("capabilities", []))
        if not my_caps:
            my_caps = {self.task_type}
        skill_caps = set(skill.capabilities)
        if my_caps & skill_caps:
            overlap = len(my_caps & skill_caps) / max(len(my_caps), 1)
            score += 0.3 * overlap

        # Price match (lower is better, within budget)
        if skill.price_per_query <= self.max_price:
            price_ratio = 1.0 - (skill.price_per_query / max(self.max_price, 0.00001))
            score += 0.2 * max(0, price_ratio)

        # Availability
        if skill.availability == "online":
            score += 0.1

        return min(score, 1.0)


# ═══════════════════════════════════════════════════════════════════
# REGISTRY — local skill inventory
# ═══════════════════════════════════════════════════════════════════

class SkillRegistry:
    """Local registry of skills this sovereign instance offers to the marketplace."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (ROOT / "memory" / "depin" / "skills.json")
        self.skills: dict[str, SkillNFT] = {}
        self._load()

    def _load(self) -> None:
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text())
                for s in data.get("skills", []):
                    skill = SkillNFT(**s)
                    self.skills[skill.skill_id] = skill
            except (json.JSONDecodeError, TypeError):
                pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema": "gstd-skill-registry.v1",
            "ts": _now(),
            "skills": [s.to_listing() for s in self.skills.values()],
        }
        self.path.write_text(json.dumps(data, indent=2, default=str))

    def register(self, skill: SkillNFT) -> str:
        """Register a skill in the local inventory. Returns skill_id."""
        self.skills[skill.skill_id] = skill
        self._save()
        return skill.skill_id

    def unregister(self, skill_id: str) -> bool:
        if skill_id in self.skills:
            del self.skills[skill_id]
            self._save()
            return True
        return False

    def list_available(self, skill_type: Optional[str] = None) -> list[SkillNFT]:
        """List all available skills, optionally filtered by type."""
        available = [s for s in self.skills.values() if s.availability == "online"]
        if skill_type:
            available = [s for s in available if s.skill_type == skill_type]
        return available

    def match_order(self, order: MarketplaceOrder) -> Optional[SkillNFT]:
        """Find the best matching skill for an order. Returns None if no match."""
        available = self.list_available(order.skill_type_needed)
        if not available:
            return None

        scored = [(s, order.match_score(s)) for s in available]
        scored.sort(key=lambda x: x[1], reverse=True)

        best, score = scored[0]
        if score > 0.3:  # Minimum match threshold
            return best
        return None


# ═══════════════════════════════════════════════════════════════════
# AUTO-DISCOVER — detect local capabilities
# ═══════════════════════════════════════════════════════════════════

def discover_local_skills(owner_address: str = "") -> list[SkillNFT]:
    """Auto-discover skills available on this sovereign instance.

    Detects:
      - GPU compute (via torch/nvidia-smi)
      - Local models (via Ollama)
      - API model access (Grok, DeepSeek, etc.)
      - Specialized skills (code, classify, research, etc.)
    """
    skills: list[SkillNFT] = []

    owner = owner_address or os.environ.get("GSTD_ADDRESS", "local")

    # 1. GPU compute skill
    gpu = _detect_gpu()
    if gpu:
        skills.append(SkillNFT(
            skill_id=SkillNFT.generate_id(owner, "compute", f"gpu-{gpu}"),
            owner_address=owner,
            skill_type="compute",
            name=f"GPU Compute — {gpu}",
            description=f"Spare GPU cycles on {gpu}",
            price_per_query=0.001,
            price_per_hour=0.01,
            capabilities=["image_gen", "model_training", "inference"],
            gpu_spec=gpu,
        ))

    # 2. Local model skills (Ollama)
    local_models = _detect_local_models()
    for model_name, capabilities in local_models:
        skills.append(SkillNFT(
            skill_id=SkillNFT.generate_id(owner, "model", model_name),
            owner_address=owner,
            skill_type="model",
            name=f"Local Model — {model_name}",
            description=f"Local inference on {model_name}",
            price_per_query=0.0001,
            price_per_hour=0.0,
            capabilities=capabilities,
            model_name=model_name,
        ))

    # 3. API model access skills (Grok, DeepSeek)
    api_models = _detect_api_models()
    for model_name, cost, capabilities in api_models:
        skills.append(SkillNFT(
            skill_id=SkillNFT.generate_id(owner, "model", model_name),
            owner_address=owner,
            skill_type="model",
            name=f"API Model — {model_name}",
            description=f"Frontier model access: {model_name} at ${cost}/call",
            price_per_query=cost * 2,  # 2x markup for marketplace
            price_per_hour=0.0,
            capabilities=capabilities,
            model_name=model_name,
        ))

    # 4. Specialized skill NFTs
    specialized = [
        ("code-generation", "code", 0.001, ["code"]),
        ("research-synthesis", "research", 0.003, ["research", "analyze_reason"]),
        ("strategy-council", "strategy", 0.005, ["strategy", "orchestrate"]),
        ("bard-weaving", "classify", 0.0005, ["classify", "simple_lookup"]),
        ("verkle-audit", "analyze_reason", 0.002, ["analyze_reason", "verify"]),
    ]
    for name, task_type, price, caps in specialized:
        skills.append(SkillNFT(
            skill_id=SkillNFT.generate_id(owner, "skill", name),
            owner_address=owner,
            skill_type="skill",
            name=name.replace("-", " ").title(),
            description=f"Specialized AI capability: {name}",
            price_per_query=price,
            price_per_hour=0.0,
            capabilities=caps,
        ))

    return skills


def _detect_gpu() -> str:
    """Detect GPU hardware. Returns name string or empty."""
    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split("\n")[0]
    except Exception:
        pass

    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
    except Exception:
        pass

    return ""


def _detect_local_models() -> list[tuple[str, list[str]]]:
    """Detect locally available Ollama models."""
    try:
        import subprocess
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0)
        if r.returncode != 0:
            return []

        models = []
        for line in r.stdout.strip().split("\n")[1:]:  # Skip header
            parts = line.split()
            if parts:
                name = parts[0]
                caps = _infer_capabilities(name)
                models.append((name, caps))
        return models
    except Exception:
        return []


def _detect_api_models() -> list[tuple[str, float, list[str]]]:
    """Detect available API models via environment/config."""
    models = []

    if os.environ.get("XAI_API_KEY"):
        models.append(("grok-3-mini", 0.003, ["analyze_reason", "research", "strategy"]))
        models.append(("grok-4-latest", 0.025, ["orchestrate"]))

    if os.environ.get("DEEPSEEK_API_KEY"):
        models.append(("deepseek-v4-flash", 0.00013, ["code", "classify", "simple_lookup", "analyze_reason", "research", "strategy"]))

    return models


def _infer_capabilities(model_name: str) -> list[str]:
    """Infer capabilities from model name."""
    name_lower = model_name.lower()
    caps = []

    if "coder" in name_lower or "code" in name_lower:
        caps.append("code")
    if any(w in name_lower for w in ["gemma", "phi", "tiny", "small", "2b", "3b"]):
        caps.extend(["classify", "simple_lookup"])
    if any(w in name_lower for w in ["llama", "mistral", "qwen", "deepseek"]):
        caps.extend(["analyze_reason", "research"])

    return caps if caps else ["classify"]


# ═══════════════════════════════════════════════════════════════════
# VERKLE PROOF — cryptographic verification of work done
# ═══════════════════════════════════════════════════════════════════

def generate_work_proof(
    skill_id: str,
    order_id: str,
    buyer: str,
    seller: str,
    result_hash: str,
    cost_gstd: float,
) -> dict[str, Any]:
    """Generate a Verkle-chain proof that work was completed.

    This proof is what gets settled on GSTD. The Verkle chain provides
    cryptographic evidence that:
      1. The buyer requested work (order_id)
      2. The seller had the claimed capability (skill_id)
      3. The work produced a specific result (result_hash)
      4. The agreed price was the price paid (cost_gstd)

    Returns a proof dict suitable for folding into the Verkle chain.
    """
    # Build the proof payload
    proof_payload = {
        "schema": "depin-work-proof.v1",
        "skill_id": skill_id,
        "order_id": order_id,
        "buyer": buyer,
        "seller": seller,
        "result_hash": result_hash,
        "cost_gstd": cost_gstd,
        "ts": _now(),
    }

    # Content-address it
    proof_hash = hashlib.sha256(
        json.dumps(proof_payload, sort_keys=True, default=str).encode()
    ).hexdigest()

    proof_payload["proof_hash"] = proof_hash
    return proof_payload


def verify_work_proof(proof: dict[str, Any]) -> bool:
    """Verify a work proof hasn't been tampered with."""
    if "proof_hash" not in proof:
        return False

    # Recompute hash without the proof_hash field
    payload = {k: v for k, v in proof.items() if k != "proof_hash"}
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()

    return expected == proof["proof_hash"]


# ═══════════════════════════════════════════════════════════════════
# TRANSACTION LEDGER
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DepinTransaction:
    """A completed marketplace transaction — recorded in Verkle + Bard."""
    tx_id: str
    skill_id: str
    order_id: str
    buyer: str
    seller: str
    cost_gstd: float
    result_hash: str
    verkle_proof: dict[str, Any] = field(default_factory=dict)
    bard_passage: str = ""
    ts: str = field(default_factory=_now)

    def to_verkle_knot(self) -> dict[str, Any]:
        """Format as a Verkle knot for the chain."""
        return {
            "type": "depin_transaction",
            "tx_id": self.tx_id,
            "skill_id": self.skill_id,
            "buyer": self.buyer,
            "seller": self.seller,
            "cost_gstd": self.cost_gstd,
            "result_hash": self.result_hash,
            "proof_hash": self.verkle_proof.get("proof_hash", ""),
            "ts": self.ts,
        }

    def to_bard_event(self) -> dict[str, Any]:
        """Format as an event for the Silent Bard to weave."""
        return {
            "type": "depin_transaction",
            "agent_id": f"gstd-{self.buyer[:8]}",
            "task_type": "orchestrate",
            "cost": self.cost_gstd,
            "model": "gstd-marketplace",
            "summary": f"Skill {self.skill_id} sold to {self.buyer[:8]}",
        }


# ═══════════════════════════════════════════════════════════════════
# MARKETPLACE API — what the sovereign instance exposes
# ═══════════════════════════════════════════════════════════════════

class DepinMarketplace:
    """The sovereign instance's interface to the GSTD DePIN economy."""

    def __init__(self, owner_address: str = ""):
        self.owner = owner_address or os.environ.get("GSTD_ADDRESS", "local")
        self.registry = SkillRegistry()
        self.transactions: list[DepinTransaction] = []

    def bootstrap(self) -> list[SkillNFT]:
        """Discover and register all local skills. Call once on startup."""
        discovered = discover_local_skills(self.owner)
        for skill in discovered:
            self.registry.register(skill)
        return discovered

    def list_skills(self) -> list[dict[str, Any]]:
        """Export all registered skills as marketplace listings."""
        return [s.to_listing() for s in self.registry.skills.values()]

    def match_and_fulfill(self, order: MarketplaceOrder) -> Optional[DepinTransaction]:
        """Match an order against local skills and fulfill it.

        Returns a transaction if fulfilled, None if no match.
        """
        skill = self.registry.match_order(order)
        if not skill:
            return None

        # Simulate work execution (in production: actually run the model/skill)
        result_hash = hashlib.sha256(
            json.dumps(order.payload, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        # Generate Verkle proof
        proof = generate_work_proof(
            skill_id=skill.skill_id,
            order_id=order.order_id,
            buyer=order.buyer_address,
            seller=self.owner,
            result_hash=result_hash,
            cost_gstd=skill.price_per_query,
        )

        # Record transaction
        tx = DepinTransaction(
            tx_id=hashlib.sha256(f"{order.order_id}:{skill.skill_id}".encode()).hexdigest()[:16],
            skill_id=skill.skill_id,
            order_id=order.order_id,
            buyer=order.buyer_address,
            seller=self.owner,
            cost_gstd=skill.price_per_query,
            result_hash=result_hash,
            verkle_proof=proof,
        )
        self.transactions.append(tx)

        # Weave into Bard
        try:
            from mag.bard import bard_sense, bard_publish_sync
            bard_event = tx.to_bard_event()
            passage = bard_sense(bard_event)
            bard_publish_sync(passage, bard_event)
            tx.bard_passage = passage
        except Exception:
            pass

        # Fold into Verkle chain
        try:
            from mag.verkle_bus import CH_VERKLE, publish_sync
            publish_sync(CH_VERKLE, tx.to_verkle_knot())
        except Exception:
            pass

        return tx

    def balance(self) -> dict[str, Any]:
        """Get this instance's marketplace balance/status."""
        return {
            "schema": "depin-balance.v1",
            "owner": self.owner,
            "skills_listed": len(self.registry.skills),
            "skills_available": len(self.registry.list_available()),
            "transactions": len(self.transactions),
            "total_earned_gstd": sum(tx.cost_gstd for tx in self.transactions),
            "ts": _now(),
        }
