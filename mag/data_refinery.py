"""Data Refinery — convert every system output into training data.

The bridge only reads Copilot transcripts. The refinery pulls from EVERY source:
  - Copilot transcripts (6 MB/day)
  - Verkle chain entries (growing)
  - Ghost ledger (every model call)
  - Orchestrator task outputs
  - Constitutional critique logs
  - MoA consensus outputs
  - Bard tapestry passages
  - Dashboard events (once running)
  - Swarm outputs (once running)
  - REST API response logs
  - Ollama interaction logs

Everything the sovereign stack produces eventually becomes training data.
This is the closed loop: run → capture → refine → train → improve → run.

SCHEMA: data_refinery.v1
LAW: Never ingest T0/T1 data. Public and T2 only.
LAW: Quality filter before quantity. Bad data trains bad models.
LAW: Deduplicate. The same example twice is noise, not signal.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
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
# TRAINING EXAMPLE (normalized format)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TrainingExample:
    """One normalized training example from any source."""
    source: str              # which data source
    instruction: str         # what was asked
    input_context: str       # what context was provided
    output: str              # what the system produced
    quality_score: float     # 0-1, how good is this example
    source_id: str           # unique ID within source
    content_hash: str        # dedup hash
    tags: list[str] = field(default_factory=list)
    ts: str = field(default_factory=_now)

    def to_instruction_format(self) -> dict[str, str]:
        """Format for instruction fine-tuning."""
        return {
            "instruction": self.instruction[:2000],
            "input": self.input_context[:2000],
            "output": self.output[:4000],
        }

    def to_chat_format(self) -> dict[str, Any]:
        """Format for chat fine-tuning (user/assistant pairs)."""
        return {
            "messages": [
                {"role": "system", "content": "You are Ghost, the autonomous sovereign agent."},
                {"role": "user", "content": f"{self.instruction}\n\nContext: {self.input_context}"},
                {"role": "assistant", "content": self.output},
            ]
        }


# ═══════════════════════════════════════════════════════════════════
# SOURCE INGESTORS
# ═══════════════════════════════════════════════════════════════════

class DataRefinery:
    """Ingest from all sources, normalize, filter, output training data."""

    def __init__(self):
        self.output_path = ROOT / "memory" / "training" / "refined_training_data.jsonl"
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.stats: dict[str, dict[str, int]] = defaultdict(lambda: {"ingested": 0, "kept": 0, "filtered": 0})

    def ingest_all(self) -> dict[str, Any]:
        """Ingest from every available source. Returns summary."""
        results = {}

        # 1. Copilot transcripts (richest source)
        results["copilot"] = self._ingest_copilot()

        # 2. Verkle chain (system memory)
        results["verkle_chain"] = self._ingest_verkle_chain()

        # 3. Research packs (richest distilled content — full case-law docs)
        results["research_packs"] = self._ingest_research_packs()

        # 4. Training rows (already-formed instruction pairs from local inference runs)
        results["training_rows"] = self._ingest_training_rows()

        # 5. Ghost ledger (model interactions)
        results["ledger"] = self._ingest_ledger()

        # 6. Grok CLI / SuperGrok session transcripts (frontier-grade frontier data)
        results["grok_cli"] = self._ingest_grok_cli()

        # 7. DeepSeek (usage telemetry + routing decisions — the workhorse provider)
        results["deepseek"] = self._ingest_deepseek()

        # 4. Orchestrator tasks (completed work)
        results["orchestrator"] = self._ingest_orchestrator()

        # 5. Constitutional critique (self-correction pairs)
        results["critique"] = self._ingest_critique()

        # 6. MoA consensus (multi-model outputs)
        results["moa"] = self._ingest_moa()

        # 7. Frontier scout (research findings)
        results["scout"] = self._ingest_scout()

        # 8. Context checkpoints (conversation state)
        results["checkpoints"] = self._ingest_checkpoints()

        return self._summarize(results)

    # ── Copilot Transcripts ──────────────────────────────────────

    def _ingest_copilot(self) -> dict[str, int]:
        """Ingest Copilot conversation turns as training examples."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}

        try:
            from mag.copilot_bridge import find_transcript_path, parse_transcript
            path = find_transcript_path()
            if not path:
                return stats

            turns = parse_transcript(path, max_turns=200)
            examples = []

            # Pair user messages (instruction) with assistant responses (output)
            for i in range(len(turns) - 1):
                if turns[i].role == "user" and turns[i + 1].role == "assistant":
                    stats["ingested"] += 1
                    example = TrainingExample(
                        source="copilot_transcript",
                        instruction=turns[i].content[:2000],
                        input_context="",  # Copilot has its own context
                        output=turns[i + 1].content[:4000],
                        quality_score=self._score_quality(turns[i].content, turns[i + 1].content),
                        source_id=f"copilot-turn-{turns[i].turn_number}",
                        content_hash=hashlib.sha256((turns[i].content + turns[i + 1].content).encode()).hexdigest()[:16],
                        tags=["copilot", "conversation"],
                    )
                    examples.append(example)

            kept = self._write_examples(examples)
            stats["kept"] = kept
            stats["filtered"] = stats["ingested"] - kept
        except Exception:
            pass

        return stats

    # ── Verkle Chain ─────────────────────────────────────────────

    def _ingest_verkle_chain(self) -> dict[str, int]:
        """Ingest Verkle chain entries as training context."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}
        chain_paths = [
            ROOT / "memory" / "verkle_chain.jsonl",
            ROOT / "memory" / "biography" / "verkle_chain.jsonl",
        ]

        for chain_path in chain_paths:
            if not chain_path.is_file():
                continue
            try:
                lines = chain_path.read_text(encoding="utf-8").strip().splitlines()
            except (UnicodeDecodeError, OSError):
                continue

            examples = []
            for line in lines[-500:]:  # last 500 entries
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                stats["ingested"] += 1
                entry_type = entry.get("type", entry.get("event_type", "unknown"))
                entry_data = entry.get("data", entry)

                # Rich behavioral telemetry (the dashboard-grade data): theme, tension, duration.
                theme = str(entry.get("dominant_theme") or entry_type)
                try:
                    tension = float(entry.get("tension_index") or 0.0)
                except (TypeError, ValueError):
                    tension = 0.0
                tv = entry.get("theme_vector_normalized") or []
                dur_min = None
                try:
                    from datetime import datetime as _dt
                    def _p(v):
                        return _dt.fromisoformat((v or "").replace("Z", "+00:00"))
                    s, e = _p(entry.get("start_minute")), _p(entry.get("end_minute"))
                    dur_min = max(0, int((e - s).total_seconds() // 60))
                except Exception:
                    dur_min = None
                tension_band = "HIGH" if tension >= 0.7 else ("MID" if tension >= 0.55 else "LOW")

                example = TrainingExample(
                    source="verkle_chain",
                    instruction=f"Classify the behavioral state of this system session (theme: {theme}).",
                    input_context=(f"theme={theme} tension={round(tension,3)} "
                                   f"theme_vector={[round(float(v),3) for v in tv[:8]]} "
                                   f"duration_min={dur_min} amended={entry.get('amended')}"),
                    output=(f"Session behavioral read: theme={theme}, tension={tension_band} "
                            f"({round(tension,3)}), duration_min={dur_min}, amended={entry.get('amended')}. "
                            f"{'High-tension session — behavioral fingerprint risk.' if tension_band=='HIGH' else 'Within normal behavioral band.'}"),
                    quality_score=0.75,  # real behavioral telemetry, not raw noise
                    source_id=entry.get("id", entry.get("knot_id", hashlib.sha256(line.encode()).hexdigest()[:12])),
                    content_hash=hashlib.sha256((theme + str(tension) + str(dur_min)).encode()).hexdigest()[:16],
                    tags=["verkle_chain", entry_type, f"theme_{theme}"],
                )
                examples.append(example)

                kept = self._write_examples(examples)
                stats["kept"] += kept
                stats["filtered"] += len(examples) - kept

        return stats

    # ── Research Packs ───────────────────────────────────────────

    def _ingest_research_packs(self) -> dict[str, int]:
        """Ingest research packs (distilled case-law docs) as high-quality training examples."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}
        packs_dir = ROOT / "memory" / "research_packs"
        if not packs_dir.is_dir():
            return stats
        for p in sorted(packs_dir.glob("*.answer.*.md")):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if len(text.strip()) < 40:
                continue
            title = ""
            for ln in text.splitlines():
                if ln.startswith("# "):
                    title = ln[2:].strip()[:120]
                    break
            title = title or p.stem
            # split into sections -> instruction/output pairs
            sections = [s.strip() for s in text.split("\n## ") if len(s.strip()) > 60]
            for sec in sections[:8]:
                heading = sec.splitlines()[0][:120] if sec.splitlines() else ""
                body = "\n".join(sec.splitlines()[1:])[:3000] if sec.splitlines() else sec[:3000]
                stats["ingested"] += 1
                ex = TrainingExample(
                    source="research_pack",
                    instruction=f"{title} — {heading}" if heading else title,
                    input_context="",
                    output=body,
                    quality_score=0.85,  # distilled case law = high quality
                    source_id=f"pack:{p.stem[:40]}:{heading[:30]}",
                    content_hash=hashlib.sha256((title + body).encode()).hexdigest()[:16],
                    tags=["research_pack", "case_law", p.stem[:20]],
                )
                if self._write_examples([ex]):
                    stats["kept"] += 1
                else:
                    stats["filtered"] += 1
        return stats

    # ── Training Rows (already-formed pairs) ─────────────────────

    def _ingest_training_rows(self) -> dict[str, int]:
        """Ingest training_rows.jsonl (local-inference pairs: gpu_afk_train, stateless_local_steer)."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}
        path = ROOT / "memory" / "pile" / "training_rows.jsonl"
        if not path.is_file():
            return stats
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            stats["ingested"] += 1
            ex = TrainingExample(
                source=str(row.get("source") or "training_rows"),
                instruction=str(row.get("input") or row.get("task") or "")[:2000],
                input_context="",
                output=str(row.get("output") or "")[:3000],
                quality_score=0.7,  # local-inference pairs, decent but not frontier-refined
                source_id=f"row:{row.get('ts','')[:19]}",
                content_hash=hashlib.sha256((str(row.get("input")) + str(row.get("output"))).encode()).hexdigest()[:16],
                tags=["training_rows", str(row.get("source") or "local")],
            )
            if self._write_examples([ex]):
                stats["kept"] += 1
            else:
                stats["filtered"] += 1
        return stats

    # ── Grok CLI / SuperGrok transcripts ─────────────────────────

    def _ingest_grok_cli(self) -> dict[str, int]:
        """Ingest grok CLI / SuperGrok session transcripts (~/.grok/sessions) as high-quality pairs."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}
        # grok stores sessions under URL-encoded working-dir subfolders: sessions/<enc>/<id>/chat_history.jsonl
        sessions = sorted(str(p) for p in Path("~/.grok/sessions").expanduser().rglob("chat_history.jsonl"))
        for path in sessions[:80]:
            try:
                turns = []
                for line in open(path, encoding="utf-8", errors="replace").read().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    typ = rec.get("type")  # system / user / assistant
                    content = rec.get("content")
                    if isinstance(content, list):
                        content = " ".join(str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in content)
                    content = str(content or "")
                    # skip system boilerplate and empty turns
                    if typ in ("user", "assistant") and content and "<user_info>" not in content[:200]:
                        turns.append({"type": typ, "content": content})
            except (OSError, UnicodeDecodeError):
                continue
            for i in range(len(turns) - 1):
                u, a = turns[i], turns[i + 1]
                if u["type"] == "user" and a["type"] == "assistant":
                    # strip grok's own <user_query>/<assistant_response> wrapper noise lightly
                    uin = u["content"].replace("<user_query>", "").replace("</user_query>", "").strip()
                    aout = a["content"]
                    if not uin or not aout:
                        continue
                    stats["ingested"] += 1
                    ex = TrainingExample(
                        source="grok_cli",
                        instruction=uin[:2000],
                        input_context="",
                        output=aout[:4000],
                        quality_score=0.85,  # frontier-grade, Ghost's own recorded voice
                        source_id=f"grok:{Path(path).parent.name}:{i}",
                        content_hash=hashlib.sha256((uin + aout).encode()).hexdigest()[:16],
                        tags=["grok_cli", "frontier", "supergrok"],
                    )
                    if self._write_examples([ex]):
                        stats["kept"] += 1
                    else:
                        stats["filtered"] += 1
        return stats

    # ── DeepSeek (usage telemetry + routing) ─────────────────────

    def _ingest_deepseek(self) -> dict[str, int]:
        """Ingest DeepSeek data: provider_usage.jsonl (interaction telemetry) + routing decisions."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}
        # 1. Provider usage telemetry (the real 19k-call interaction record)
        p = ROOT / "logs" / "provider_usage.jsonl"
        if p.is_file():
            try:
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                lines = []
            for line in lines[-200:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(r.get("provider") or "").lower() != "deepseek":
                    continue
                stats["ingested"] += 1
                ex = TrainingExample(
                    source="deepseek_usage",
                    instruction="Record this DeepSeek interaction's cost/cache profile.",
                    input_context=json.dumps(r)[:2000],
                    output=(f"deepseek interaction: model={r.get('model')} "
                            f"hit_ratio={r.get('cache_hit_ratio') or r.get('hit_ratio')} "
                            f"input_tok={r.get('input_tokens')} output_tok={r.get('output_tokens')} "
                            f"cost={r.get('priced_usd') or r.get('cost')}"),
                    quality_score=0.5,  # telemetry, not instruction pairs
                    source_id=f"ds-usage:{r.get('ts') or r.get('session_id') or ''}"[:40],
                    content_hash=hashlib.sha256(line.encode()).hexdigest()[:16],
                    tags=["deepseek", "usage", "cost"],
                )
                if self._write_examples([ex]):
                    stats["kept"] += 1
                else:
                    stats["filtered"] += 1
        # 2. DeepSeek routing decisions (which task shape -> deepseek)
        q = ROOT / "memory" / "improve" / "pins" / "deepseek_routing.jsonl"
        if q.is_file():
            for line in q.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                stats["ingested"] += 1
                ex = TrainingExample(
                    source="deepseek_routing",
                    instruction=f"Route this task shape to the right provider/tier: {r.get('task_shape') or r.get('shape') or '?'}",
                    input_context=str(r.get("goal") or r.get("task") or "")[:1500],
                    output=f"route: {r.get('provider') or 'deepseek'} / {r.get('model') or 'deepseek-v4-flash'}",
                    quality_score=0.6,
                    source_id=f"ds-route:{r.get('ts') or ''}"[:40],
                    content_hash=hashlib.sha256((str(r.get('goal')) + str(r.get('provider'))).encode()).hexdigest()[:16],
                    tags=["deepseek", "routing", "rightsize"],
                )
                if self._write_examples([ex]):
                    stats["kept"] += 1
                else:
                    stats["filtered"] += 1
        return stats

    # ── Ghost Ledger ─────────────────────────────────────────────

    def _ingest_ledger(self) -> dict[str, int]:
        """Ingest ledger entries as cost-awareness training."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}
        ledger_path = ROOT / "memory" / "ledger" / "ghost_ledger.jsonl"

        if not ledger_path.is_file():
            return stats

        try:
            lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
        except (UnicodeDecodeError, OSError):
            return stats

        examples = []
        for line in lines[-200:]:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            stats["ingested"] += 1
            model = entry.get("model", "unknown")
            cost = entry.get("cost_usd", 0)
            tokens = entry.get("tokens_total", 0)

            example = TrainingExample(
                source="ghost_ledger",
                instruction="Track model usage cost",
                input_context=f"Model: {model}, Tokens: {tokens}",
                output=f"Cost recorded: ${cost:.6f} for {tokens} tokens on {model}",
                quality_score=0.5,
                source_id=entry.get("row_hash", hashlib.sha256(line.encode()).hexdigest()[:12]),
                content_hash=hashlib.sha256(line.encode()).hexdigest()[:16],
                tags=["ledger", model, "cost_tracking"],
            )
            examples.append(example)

        kept = self._write_examples(examples)
        stats["kept"] = kept
        stats["filtered"] = stats["ingested"] - kept
        return stats

    # ── Orchestrator Tasks ───────────────────────────────────────

    def _ingest_orchestrator(self) -> dict[str, int]:
        """Ingest completed orchestrator tasks as training examples."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}
        tasks_dir = ROOT / "memory" / "runs" / "orchestrator" / "tasks"

        if not tasks_dir.is_dir():
            return stats

        examples = []
        for task_file in sorted(tasks_dir.glob("*.json"))[-100:]:
            try:
                task = json.loads(task_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            stats["ingested"] += 1
            goal = task.get("goal", "")
            status = task.get("status", "")
            log = task.get("log", "")

            # Only keep completed tasks with output
            if status != "done" or not log:
                continue

            example = TrainingExample(
                source="orchestrator_task",
                instruction=goal[:2000],
                input_context=f"Task ID: {task.get('task_id', '?')}, Provider: {task.get('provider', '?')}",
                output=log[:4000] if isinstance(log, str) else json.dumps(log)[:4000],
                quality_score=0.7 if status == "done" else 0.3,
                source_id=task.get("task_id", task_file.stem),
                content_hash=hashlib.sha256((goal + str(log)[:500]).encode()).hexdigest()[:16],
                tags=["orchestrator", status, task.get("tag", "")],
            )
            examples.append(example)

        kept = self._write_examples(examples)
        stats["kept"] = kept
        stats["filtered"] = stats["ingested"] - kept
        return stats

    # ── Constitutional Critique ─────────────────────────────────

    def _ingest_critique(self) -> dict[str, int]:
        """Ingest critique/revision pairs as self-correction training."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}
        critique_path = ROOT / "memory" / "critique" / "critique_log.jsonl"

        if not critique_path.is_file():
            return stats

        try:
            lines = critique_path.read_text(encoding="utf-8").strip().splitlines()
        except (UnicodeDecodeError, OSError):
            return stats

        examples = []
        for line in lines[-100:]:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            stats["ingested"] += 1
            if entry.get("clean", True):
                continue  # skip clean passes — only keep revisions

            violations = entry.get("violations", [])
            if not violations:
                continue

            violation_desc = "; ".join(v.get("description", "")[:100] for v in violations[:3])

            example = TrainingExample(
                source="constitutional_critique",
                instruction=f"Revise this response to fix constitutional violations: {violation_desc}",
                input_context=f"Original had {len(violations)} violations. Tier: {entry.get('tier', 'T2')}",
                output=f"Revised: {entry.get('revised', entry.get('original', ''))[:4000]}",
                quality_score=0.8,  # revisions are high-quality training
                source_id=entry.get("ts", hashlib.sha256(line.encode()).hexdigest()[:12]),
                content_hash=hashlib.sha256(line.encode()).hexdigest()[:16],
                tags=["critique", "self_correction", "constitutional"],
            )
            examples.append(example)

        kept = self._write_examples(examples)
        stats["kept"] = kept
        stats["filtered"] = stats["ingested"] - kept
        return stats

    # ── MoA Consensus ────────────────────────────────────────────

    def _ingest_moa(self) -> dict[str, int]:
        """Ingest MoA consensus outputs as multi-perspective training."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}
        moa_path = ROOT / "memory" / "moa" / "moa_log.jsonl"

        if not moa_path.is_file():
            return stats

        try:
            lines = moa_path.read_text(encoding="utf-8").strip().splitlines()
        except (UnicodeDecodeError, OSError):
            return stats

        examples = []
        for line in lines[-50:]:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            stats["ingested"] += 1
            votes = entry.get("votes", [])
            consensus = entry.get("consensus", "")
            dissent = entry.get("dissent_preserved", "")

            if not consensus:
                continue

            # Instruction: the original goal. Output: the consensus.
            example = TrainingExample(
                source="moa_consensus",
                instruction=entry.get("goal", "Synthesize multi-model analysis")[:2000],
                input_context=f"{len(votes)} models contributed. Convergence: {entry.get('convergence', 0)}. Dissent: {dissent[:300]}",
                output=consensus[:4000],
                quality_score=entry.get("confidence", 0.7),
                source_id=entry.get("ts", hashlib.sha256(line.encode()).hexdigest()[:12]),
                content_hash=hashlib.sha256(line.encode()).hexdigest()[:16],
                tags=["moa", "consensus", "multi_model"],
            )
            examples.append(example)

        kept = self._write_examples(examples)
        stats["kept"] = kept
        stats["filtered"] = stats["ingested"] - kept
        return stats

    # ── Frontier Scout ───────────────────────────────────────────

    def _ingest_scout(self) -> dict[str, int]:
        """Ingest scout findings as research training."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}
        scout_path = ROOT / "memory" / "frontier" / "scout_findings.jsonl"

        if not scout_path.is_file():
            return stats

        try:
            lines = scout_path.read_text(encoding="utf-8").strip().splitlines()
        except (UnicodeDecodeError, OSError):
            return stats

        examples = []
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            stats["ingested"] += 1
            example = TrainingExample(
                source="frontier_scout",
                instruction=f"Assess this frontier technique: {entry.get('name', '')}",
                input_context=entry.get("description", "")[:2000],
                output=f"Verdict: {entry.get('verdict', '')}. Benefit: {entry.get('benefit', 0)}/10. Adaptation: {entry.get('adaptation_plan', '')[:2000]}",
                quality_score=0.7,
                source_id=entry.get("id", hashlib.sha256(line.encode()).hexdigest()[:12]),
                content_hash=hashlib.sha256(line.encode()).hexdigest()[:16],
                tags=["scout", entry.get("verdict", ""), entry.get("category", "")],
            )
            examples.append(example)

        kept = self._write_examples(examples)
        stats["kept"] = kept
        stats["filtered"] = stats["ingested"] - kept
        return stats

    # ── Context Checkpoints ──────────────────────────────────────

    def _ingest_checkpoints(self) -> dict[str, int]:
        """Ingest context checkpoints as conversation state training."""
        stats = {"ingested": 0, "kept": 0, "filtered": 0}
        cp_dir = ROOT / "memory" / "checkpoints"

        if not cp_dir.is_dir():
            return stats

        examples = []
        for cp_file in sorted(cp_dir.rglob("turn_*.json"))[-100:]:
            try:
                cp = json.loads(cp_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            stats["ingested"] += 1
            example = TrainingExample(
                source="context_checkpoint",
                instruction=f"Summarize conversation turn {cp.get('turn_number', 0)}",
                input_context=f"Session: {cp.get('session_id', '')}, Model: {cp.get('model_used', '')}",
                output=cp.get("summary", "")[:4000],
                quality_score=0.5,
                source_id=cp.get("verkle_knot_id", cp_file.stem),
                content_hash=hashlib.sha256(json.dumps(cp, default=str).encode()).hexdigest()[:16],
                tags=["checkpoint", cp.get("model_used", ""), "conversation_state"],
            )
            examples.append(example)

        kept = self._write_examples(examples)
        stats["kept"] = kept
        stats["filtered"] = stats["ingested"] - kept
        return stats

    # ── Quality scoring ──────────────────────────────────────────

    def _score_quality(self, instruction: str, output: str) -> float:
        """Score the quality of a training example. 0-1."""
        score = 0.5

        # Good: instruction is a real question
        if len(instruction) > 20 and "?" in instruction:
            score += 0.1

        # Good: output is substantive
        if len(output) > 100:
            score += 0.1

        # Bad: output is error message
        if any(e in output.lower()[:100] for e in ["error", "traceback", "failed", "exception"]):
            score -= 0.3

        # Bad: too short
        if len(output) < 50:
            score -= 0.2

        # Bad: instruction is a command, not a question
        if instruction.lower().startswith(("run ", "cd ", "ls ", "git ", "docker ")):
            score -= 0.2

        return max(0.0, min(1.0, score))

    # ── Write and deduplicate ────────────────────────────────────

    def _write_examples(self, examples: list[TrainingExample]) -> int:
        """Write examples to the output file, deduplicating by content hash."""
        # Load existing hashes
        existing_hashes = set()
        if self.output_path.is_file():
            try:
                for line in self.output_path.read_text(encoding="utf-8").strip().splitlines():
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        h = entry.get("content_hash", "")
                        if h:
                            existing_hashes.add(h)
                    except json.JSONDecodeError:
                        continue
            except (UnicodeDecodeError, OSError):
                pass

        written = 0
        with open(self.output_path, "a", encoding="utf-8") as f:
            for ex in examples:
                if ex.content_hash in existing_hashes:
                    continue  # duplicate
                if ex.quality_score < 0.3:
                    continue  # too low quality

                f.write(json.dumps({
                    "source": ex.source,
                    "instruction": ex.instruction[:2000],
                    "input": ex.input_context[:2000],
                    "output": ex.output[:4000],
                    "quality_score": ex.quality_score,
                    "content_hash": ex.content_hash,
                    "tags": ex.tags,
                    "ts": ex.ts,
                }, default=str) + "\n")
                existing_hashes.add(ex.content_hash)
                written += 1

        return written

    # ── Summary ──────────────────────────────────────────────────

    def _summarize(self, results: dict[str, dict[str, int]]) -> dict[str, Any]:
        total_ingested = sum(r.get("ingested", 0) for r in results.values())
        total_kept = sum(r.get("kept", 0) for r in results.values())
        total_filtered = sum(r.get("filtered", 0) for r in results.values())

        # Count output file
        output_count = 0
        output_size_kb = 0
        if self.output_path.is_file():
            try:
                lines = self.output_path.read_text(encoding="utf-8").strip().splitlines()
                output_count = len([l for l in lines if l.strip()])
                output_size_kb = self.output_path.stat().st_size / 1024
            except Exception:
                pass

        return {
            "schema": "data_refinery.v1",
            "ts": _now(),
            "total_ingested": total_ingested,
            "total_kept": total_kept,
            "total_filtered": total_filtered,
            "keep_rate": round(total_kept / max(1, total_ingested) * 100, 1),
            "output_examples": output_count,
            "output_size_kb": round(output_size_kb),
            "by_source": results,
            "annual_projection": self._project_annual(output_count),
        }

    def _project_annual(self, current_examples: int) -> dict[str, Any]:
        """Project annual training data volume."""
        # Conservative estimate: ~100 examples/day from all sources when system is running
        daily_estimate = max(current_examples, 100)
        annual = daily_estimate * 365
        avg_kb_per_example = 0.5  # rough
        annual_mb = annual * avg_kb_per_example / 1024

        return {
            "current_examples": current_examples,
            "estimated_daily": daily_estimate,
            "projected_annual_examples": annual,
            "projected_annual_mb": round(annual_mb, 1),
            "projected_annual_gb": round(annual_mb / 1024, 2),
            "note": "Actual volume depends on Ghost uptime, swarm activity, and operator engagement.",
        }


# ═══════════════════════════════════════════════════════════════════
# QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════

_REFINERY: Optional[DataRefinery] = None


def get_refinery() -> DataRefinery:
    global _REFINERY
    if _REFINERY is None:
        _REFINERY = DataRefinery()
    return _REFINERY


def refine_all() -> dict[str, Any]:
    """Ingest from all sources, write refined training data."""
    return get_refinery().ingest_all()
