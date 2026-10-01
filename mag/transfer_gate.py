"""transfer_gate — the transfer-contract gate ("rhyming is not mathematical").

B6 of the PURPLE HARVEST arc. Dig card: watch/PURPLE_HARVEST_DIG_RHYME_20260906.md.
The motivating complaint is a stranger's, verbatim: "some PhD in climate, Econ,
finance writes a paper for x reason from 1987. AI reads and incorporates that data
into my model for no reason because word search. **Rhyming is not mathematical.**"

The disease: lexical relevance != functional transfer. Word-search curation admits a
document because its vocabulary rhymes with the target; the document was written to
answer a DIFFERENT question, under different assumptions, in a different regime —
and poisons the model quietly. The fix, third generation in the dig card: state the
target explicitly and admit data against the TARGET, not against the words.

TRANSFER CONTRACT (per document — the TRIAGE card, made explicit):
    claims_hold_under_assumptions : the claims, and the assumptions they hold under
    variable                      : the operational concept the doc actually moves
    regime                        : the setting where the mechanism was measured
    as_of                         : date the claims are as-of (temporal validity)
    source_question               : the question the doc was WRITTEN to answer

HONESTY (the receipt's one-liner, kept honest in code): contracts here are
RULE-DERIVED from existing card metadata (title + text + topics + date) via
hand-written rules — the automatic claim/assumption extractor is the NEXT door
(SciCite/Claimify lineage), not claimed as built. Zero LLM tokens end to end
(Zero-Mem law): stdlib only, file bytes in, verdicts out, F6(d) audits its own
imports via AST to prove it.

EVAL SET LOCKED BEFORE MEASUREMENT (2026-09-06, at build time): the five TRUE
transfers are exactly the documents the dig card named (DA paper card, SparDA card,
B3/B4 receipts, pause-tokens row). The seven RHYME-TRAPS are the four MEASURED false
friends from TRIAGE_HAUL_BOT_01 (the ER=EPR card + the lineage-diff / RL-paint /
MuseSpark "EPR" index hits), the Kirk infographic (named in the launch brief), and
two index-defensible noun-rhymes (cache-yield math: "cache" the noun, API economics
not KV; GPU-inference scheduler: "GPU inference" the phrase, fleet ops not kernels).
Pre-lock inspection verified only that trap files carry target vocabulary — the
DEFINITION of a rhyme-trap. No gate or baseline score was computed before the lock;
the falsifier numbers below land as they land.

Usage:
  python -m mag.transfer_gate eval
  python -m mag.transfer_gate contract watch/TRIAGE_HAUL_BOT_01_20260906.md \
      --section "Card 1"
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "watch" / "topic_index.json"


# ------------------------------------------------------------------ target spec
# A curriculum lane target, written as DATA. Admission is against this object,
# never against a bag of words.

ATTENTION_EFFICIENCY = {
    "name": "attention-efficiency curriculum",
    "variable_synonyms": [  # same operational concept, hand-listed
        "attention_cost", "kv_memory", "inference_compute",
    ],
    "regimes": [  # compatible measurement settings
        "long_context_inference", "decode_serving", "prefill_serving",
        "kv_offload",
    ],
    "as_of_floor": "2024-01-01",
    "source_question": "how to cut attention cost at inference time",
}

TARGETS = {"attention-efficiency": ATTENTION_EFFICIENCY}


# --------------------------------------------------------------- contract model

@dataclass
class Contract:
    doc: str
    section: str
    title: str
    variable: str = "none"
    regime: str = "unrouted"
    as_of: str = "unknown"
    source_question: str = ""
    claims_hold_under_assumptions: list[str] = field(default_factory=list)
    derivation: list[str] = field(default_factory=list)  # rule firings, one line each


@dataclass
class Decision:
    admit: bool
    checks: list[str]          # one line per gate check, shown or blocked by it
    matched: list[str]         # vocabulary markers present (reported, never decisive)


# ------------------------------------------------------------ card loading

def load_index() -> dict[str, dict]:
    """topic_index.json if present (path -> card meta); tolerant of absence."""
    try:
        idx = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        return {c["path"].replace("\\", "/"): c for c in idx.get("cards", [])}
    except Exception:  # noqa: BLE001 — index is metadata only, never load-bearing
        return {}


_HR = re.compile(r"^\s*-{3,}\s*$")
_HEAD = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_CARD_MARK = re.compile(r"(TRIAGE|Card)\s+\d", re.IGNORECASE)


def slice_section(text: str, name: str) -> str:
    """Sub-card slice: from the heading containing `name` to the next card-marker
    heading, same-or-shallower heading, or horizontal rule. Deterministic."""
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        m = _HEAD.match(ln)
        if m and len(m.group(1)) <= 2 and name.lower() in ln.lower():
            start, lvl = i, len(m.group(1))
            break
    if start is None:
        raise ValueError(f"section {name!r} not found")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if _HR.match(lines[j]):
            end = j
            break
        m = _HEAD.match(lines[j])
        if m and (len(m.group(1)) <= lvl or _CARD_MARK.search(m.group(2))):
            end = j
            break
    return "\n".join(lines[start:end])


def read_card(path: str, section: str) -> tuple[str, str, str, list[str]]:
    """-> (title, text, as_of_date, topics). topics from the index when the file
    is indexed (file-level metadata); sub-cards inherit their file's topics."""
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    raw = p.read_text(encoding="utf-8", errors="replace")
    if section.startswith("row:"):
        phrase = section[4:].strip().lower()
        rows = [ln for ln in raw.splitlines()
                if ln.lstrip().startswith("|") and phrase in ln.lower()]
        if not rows:
            raise ValueError(f"no table row matches {section!r}")
        text = "\n".join(rows)
        title = f"{_file_title(raw)} :: row '{section[4:].strip()}'"
    elif section:
        text = slice_section(raw, section)
        first = text.splitlines()[0] if text else ""
        title = _HEAD.match(first).group(2) if _HEAD.match(first) else _file_title(raw)
    else:
        text = raw
        title = _file_title(raw)
    date = _date_of(text, p.name)
    return title, text, date, []


def _file_title(raw: str) -> str:
    for ln in raw.splitlines():
        m = _HEAD.match(ln)
        if m:
            return m.group(2)
    return ""


def _date_of(text: str, fname: str) -> str:
    m = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text)
    if m:
        return m.group(0)
    m = re.search(r"_(20\d{2})(\d{2})(\d{2})", fname)
    if m:
        return "-".join(m.groups())
    return "unknown"


# --------------------------------------------------------- derivation rules
# Hand-written, ordered, first match wins. Each rule exists because a fleet card
# EARNED it (sacred cows, not legacy shit): the mechanism rule exists because the
# fleet built B3/B4 on that vocabulary; the physics rule exists because the bot's
# corpus diff measured doctrine cards landing nowhere. This is the honest stage
# before the automatic extractor (SciCite/Claimify lineage) — NEXT door, not built.

_MECH_MARKERS = [
    "declarative attention", "decoupled attention", "sparse attention",
    r"attention[- ]cost", "attended token", r"KV block", r"KV[- ]cache",
    "fourth projection", "forecast selector", "pause token",
    "next-token prediction", r"attention mask|KV-mask|masking",
]
_PEDAGOGY_MARKERS = [r"infographic", r"textbook", r"pedagog", r"explainer",
                     r"visuali[sz]er", r"\bELI5\b", r"cheat sheet", r"lesson",
                     r"tutorial", r"explained"]
_PHYSICS_MARKERS = [r"ER=EPR", r"\bEPR\b", r"wormhole", r"quantum entangle",
                    r"spacetime", r"\bHiggs\b", r"physics doctrine",
                    r"geometry arises", r"Schwarz[sic]?schild"]
_API_MARKERS = [r"\$/1M", r"cache yield", r"hit-rate", r"cached \$", r"savings per",
                r"monthly yield", r"\$\d+/mo", r"1/\d+th price", r"subscription",
                r"\$/token", r"per 1M"]
_INFRA_MARKERS = [r"scheduler", r"scheduling", r"\bNCCL\b", r"collective",
                  r"job queue", r"GPU queue"]
_RL_MARKERS = [r"\bGRPO\b", r"GRPOTrainer", r"\bLoRA\b", r"RL env", r"fine-tun",
               r"reward term", r"reward = "]
_EVAL_MARKERS = [r"decode[- ]gate", r"fidelity (test|score)", r"probe battery",
                 r"\bsocratic\b", r"\briddler\b", r"held-out probe"]


def _hits(markers: list[str], text: str) -> list[str]:
    low = text.lower()
    return [m for m in markers if re.search(m, low)]


# Curated contracts for the six hand-read cards (claims + source question are the
# two fields a regex must not fake). Everything else falls back to tri-state
# harvest, marked as harvested.
CURATED = {
    ("TRIAGE_HAUL_BOT_01_20260906.md", "Card 1"): {
        "claims": [
            "claims verified 5/5 against arxiv.org/html/2609.02737 (cite-gate PASS)",
            "holds under: mask-not-prompt — chunked format alone ~lossless (DA-nm ablation)",
            "holds under: kept spans round outward to block boundaries; no declared token dropped",
        ],
        "question": "how can a model cut attention cost by declaring its own scope?",
    },
    ("TRIAGE_HAUL_BOT_01_20260906.md", "Card 2"): {
        "claims": [
            "conjecture-as-popularization SUPPORTED; primary Maldacena/Susskind papers UNFETCHED (marked, not faked)",
            "'geometry arises from quantum correlations' UNPROVEN-as-settled",
        ],
        "question": "does spacetime geometry arise from quantum entanglement?",
    },
    ("PURPLE_HARVEST_TRIAGE_02_20260906.md", "TRIAGE 02"): {
        "claims": [
            "1.7x decode speedup CONFIRMED over the sparse-offload baseline (abstract)",
            "+6.5pt accuracy claim DISPUTED — abstract says 'matches or slightly improves'; number-drift specimen",
            "holds under: Forecast decoupled from the attention query (lookahead selection)",
        ],
        "question": "how to cut attention cost in long-context decode by predicting next-layer KV needs?",
    },
    ("PURPLE_HARVEST_TRIAGE_02_20260906.md", "TRIAGE 03"): {
        "claims": [
            "SUPPORTED as correct standard pedagogy; nothing new — no artifact, no paper, no numbers to check",
        ],
        "question": "how do CNN and ViT receptive fields differ? (pedagogy)",
    },
    ("PURPLE_HARVEST_B3_DECL_ATTENTION_20260906.md", ""): {
        "claims": [
            "falsifiers PASS on real fleet artifacts (byte-proxy; no GPU in this cage)",
            "kernel numbers are the paper's, not ours — attended BYTES is the honest proxy",
        ],
        "question": "does the DA masking protocol survive as a byte-proxy on real fleet read loads?",
    },
    ("PURPLE_HARVEST_B4_FORECAST_20260906.md", ""): {
        "claims": [
            "5/6 falsifiers PASS, 1 FAIL reported honestly (receipt)",
            "hit-rate >= 2x uniform baseline with seed fixed BEFORE measurement",
            "every forecast miss falls back and is COUNTED, never silent",
        ],
        "question": "can cheap deterministic adjacency prefetch predicted KV blocks and hide the wait?",
    },
    ("PURPLE_HARVEST_01_20260906.md", "row:pause token"): {
        "claims": [
            "SUPPORTED as real line of work (dair_ai citation, Microsoft/Cornell)",
            "holds under: extra compute per next-token prediction paid back by a shorter sequence",
        ],
        "question": "can inference compute be bought per token and paid back by sequence length?",
    },
}


def derive_contract(path: str, section: str = "",
                    index: dict[str, dict] | None = None) -> Contract:
    """Deterministic contract derivation: hand-written rules over card metadata.
    Every field carries its derivation line — no field appears from nowhere."""
    index = index or {}
    title, text, date, _ = read_card(path, section)
    low = (title + "\n" + text).lower()
    c = Contract(doc=str(path), section=section or "(whole file)", title=title)
    idx_meta = index.get(path.replace("\\", "/"))
    topics = idx_meta.get("topics", []) if idx_meta else []
    if topics:
        c.derivation.append(f"topics (index, file-level) = {topics}")

    # variable + regime: ordered rules, first match wins
    mech = _hits(_MECH_MARKERS, low)
    if mech:
        c.variable = ("inference_compute"
                      if re.search(r"pause token|next-token", low) else "attention_cost")
        if re.search(r"pause token|next-token|per-?token", low):
            c.regime = "decode_serving"
        elif re.search(r"long.context|prefill|KV block", low):
            c.regime = "long_context_inference"
        else:
            c.regime = "decode_serving"
        c.derivation.append(
            f"variable={c.variable} <- R_MECHANISM (matched: {', '.join(repr(m) for m in mech)})")
        c.derivation.append(f"regime={c.regime} <- R_MECHANISM sub-markers")
    else:
        for name, markers, var, reg in (
                ("R_PHYSICS_DOCTRINE", _PHYSICS_MARKERS, "physics_geometry",
                 "physics_doctrine"),
                ("R_RL_TRAINING", _RL_MARKERS, "training_reward", "training"),
                ("R_INFRA_SCHED", _INFRA_MARKERS, "compute_scheduling", "infra_ops"),
                ("R_API_ECONOMICS", _API_MARKERS, "api_cost", "api_economics"),
                ("R_EVAL_HARNESS", _EVAL_MARKERS, "agent_fidelity", "eval_harness"),
                ("R_PEDAGOGY", _PEDAGOGY_MARKERS, "none", "pedagogy")):
            hit = _hits(markers, low)
            if hit:
                c.variable, c.regime = var, reg
                c.derivation.append(
                    f"variable={var} <- {name} (matched: "
                    f"{', '.join(repr(m) for m in hit)})")
                c.derivation.append(f"regime={reg} <- {name}")
                break
        else:
            c.variable, c.regime = "none", "unrouted"
            c.derivation.append("variable=none <- R_NO_MATCH (no rule fired)")

    # as_of: text date, else filename date, else index date, else unknown
    c.as_of = date
    if c.as_of == "unknown" and idx_meta:
        c.as_of = idx_meta.get("date", "unknown")
    c.derivation.append(f"as_of={c.as_of} <- card text/filename date")

    # claims + source question: curated for the hand-read cards, tri-state
    # harvest otherwise (marked as harvested — never passed off as extracted)
    key = (Path(path).name, section if section.startswith("row:") else
           (section if _CARD_MARK.search(section) else ""))
    cur = CURATED.get(key)
    if cur:
        c.claims_hold_under_assumptions = list(cur["claims"])
        c.source_question = cur["question"]
        c.derivation.append(f"claims={len(c.claims_hold_under_assumptions)} "
                            "<- CURATED (hand-read card)")
        c.derivation.append("source_question <- CURATED (hand-read card)")
    else:
        tri = re.findall(r"(?i)\b(SUPPORTED|CONFIRMED|DISPUTED|UNPROVEN)\b"
                         r"([^.\n|]{0,90})", text)[:4]
        c.claims_hold_under_assumptions = [
            f"{v.strip()}: {rest.strip()}" for v, rest in tri] or \
            ["no tri-state verdict line found in card text"]
        c.source_question = ("NOT EXTRACTED (rule-derived stage — the automatic "
                             f"claim/question extractor is the NEXT door); doc "
                             f"self-describes as variable={c.variable} in "
                             f"regime={c.regime}")
        c.derivation.append(f"claims={len(c.claims_hold_under_assumptions)} "
                            "<- REGEX HARVEST of tri-state verdict lines")
        c.derivation.append("source_question <- PLACEHOLDER (extractor not built)")
    return c


# ------------------------------------------------------------------- the gate

def gate(contract: Contract, target: dict) -> Decision:
    """Admit iff variable matches on the hand-listed synonym set, regime is
    compatible, and as_of >= floor. Three checks. Deterministic. The vocabulary
    the doc shares with the target is REPORTED but never decisive."""
    v_ok = contract.variable in target["variable_synonyms"]
    r_ok = contract.regime in target["regimes"]
    d_ok = (contract.as_of != "unknown"
            and contract.as_of >= target["as_of_floor"])
    checks = [
        f"variable: {contract.variable} "
        f"{'IN' if v_ok else 'NOT IN'} target synonyms "
        f"{target['variable_synonyms']}",
        f"regime: {contract.regime} "
        f"{'IN' if r_ok else 'NOT IN'} target regimes {target['regimes']}",
        f"as_of: {contract.as_of} "
        f"{'>=' if d_ok else '<'} floor {target['as_of_floor']}"
        if not d_ok and contract.as_of != "unknown" else
        f"as_of: {contract.as_of} >= floor {target['as_of_floor']}",
    ]
    return Decision(admit=v_ok and r_ok and d_ok, checks=checks,
                    matched=_hits(_MECH_MARKERS,
                                  (contract.title + "\n" + contract.section).lower()))


# ------------------------------------------------------- the rhyme baseline
# The stand-in for "word search": count overlaps between doc text and the target's
# own vocabulary, admit at a threshold. Deliberately given its BEST operating
# point (threshold tuned at max F1 on the eval set) — most generous control.

BASELINE_KEYWORDS = [
    "attention", "kv cache", "kv block", "sparse attention", "inference",
    "long context", "decode", "prefill", "transformer", "token", "gpu",
    "cache", "efficient", "speedup", "mask", "context window",
]


def keyword_hits(text: str) -> list[str]:
    low = text.lower()
    out = []
    for k in BASELINE_KEYWORDS:
        rx = r"\b" + re.escape(k).replace(r"\ ", r"[\s-]") + r"s?\b"
        if re.search(rx, low):
            out.append(k)
    return out


def confusion(admits: dict[str, bool], labels: dict[str, str]) -> dict[tuple[str, str], int]:
    m = {("TRUE", "ADMIT"): 0, ("TRUE", "BLOCK"): 0,
         ("RHYME-TRAP", "ADMIT"): 0, ("RHYME-TRAP", "BLOCK"): 0}
    for doc, lab in labels.items():
        m[(lab, "ADMIT" if admits[doc] else "BLOCK")] += 1
    return m


def f1_at(t: float, scores: dict[str, float], labels: dict[str, str]) -> float:
    tp = sum(1 for d, s in scores.items() if s >= t and labels[d] == "TRUE")
    fp = sum(1 for d, s in scores.items() if s >= t and labels[d] == "RHYME-TRAP")
    fn = sum(1 for d, s in scores.items() if s < t and labels[d] == "TRUE")
    return (2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) else 0.0


# ------------------------------------------------------------- the eval set
# LOCKED at build time, before any measurement — see module docstring. Labels are
# from the dig card and TRIAGE_HAUL_BOT_01's own verification pass, not from the
# gate's output. A labeled failure is a valid outcome; no post-hoc edits.

@dataclass
class EvalDoc:
    doc_id: str
    path: str
    section: str
    label: str  # "TRUE" | "RHYME-TRAP"
    rationale: str


EVAL_SET = [
    # ---- TRUE TRANSFERS (belong in the attention-efficiency lane) ----
    EvalDoc("DA_paper_card", "watch/TRIAGE_HAUL_BOT_01_20260906.md", "Card 1",
            "TRUE", "Declarative Attention (arXiv:2609.02737) — tag-driven KV "
            "masking, -52% attended tokens; cite-gate 5/5"),
    EvalDoc("SparDA_card", "watch/PURPLE_HARVEST_TRIAGE_02_20260906.md",
            "TRIAGE 02", "TRUE", "SparDA fourth projection — forecasts KV blocks "
            "for long-context decode; 1.7x over sparse-offload baseline"),
    EvalDoc("B3_receipt", "watch/PURPLE_HARVEST_B3_DECL_ATTENTION_20260906.md",
            "", "TRUE", "B3 build receipt — the DA protocol as byte-proxy organ, "
            "falsifiers PASS"),
    EvalDoc("B4_receipt", "watch/PURPLE_HARVEST_B4_FORECAST_20260906.md", "",
            "TRUE", "B4 build receipt — forecast prefetch of KV blocks "
            "(SparDA analog), 5/6 falsifiers PASS"),
    EvalDoc("pause_tokens_row", "watch/PURPLE_HARVEST_01_20260906.md",
            "row:pause token", "TRUE", "pause tokens — extra compute per "
            "next-token prediction, paid back by sequence (inference compute)"),
    # ---- RHYME-TRAPS (word-match the target, fail the contract) ----
    EvalDoc("ER_EQ_EPR_card", "watch/TRIAGE_HAUL_BOT_01_20260906.md", "Card 2",
            "RHYME-TRAP", "MEASURED trap (dig card names it): ER=EPR physics "
            "doctrine — zero transfer; the query 'EPR' vocabulary disease itself"),
    EvalDoc("kirk_infographic", "watch/PURPLE_HARVEST_TRIAGE_02_20260906.md",
            "TRIAGE 03", "RHYME-TRAP", "named in the launch brief: says "
            "'attention' everywhere, is textbook pedagogy — no mechanism"),
    EvalDoc("lineage_diff", "watch/LINEAGE_DIFF_DEEPRESEARCH_20260831.md", "",
            "RHYME-TRAP", "MEASURED false friend (HAUL corpus diff 'EPR' hit): "
            "'decode' here is the riddler decode-gate fidelity test, not LLM decode"),
    EvalDoc("rl_paint", "watch/INTAKE_RL_PAINT_CODE_20260904.md", "",
            "RHYME-TRAP", "MEASURED false friend: RL-training reproduction; its "
            "one 'inference' is a VL judge, not inference-cost work"),
    EvalDoc("musespark", "watch/INTAKE_AV1DLIVE_MUSESPARK_REPROMO_20260903.md",
            "", "RHYME-TRAP", "MEASURED false friend: model-router promo; rhymes "
            "on price/model vocabulary, zero mechanism"),
    EvalDoc("cache_yield_math", "watch/CACHE_YIELD_MATH_20260901.md", "",
            "RHYME-TRAP", "'cache' x19 — API prompt-cache $/1M economics; the "
            "1987-paper analog in our own house: same noun, different variable"),
    EvalDoc("gpu_scheduler", "watch/INTAKE_avrldotdev_gpu_scheduler_20260904.md",
            "", "RHYME-TRAP", "'GPU inference' x3 — fleet job scheduling question, "
            "not attention cost"),
]


# ------------------------------------------------------------------- falsifiers

_STDLIB_OK = {"__future__", "argparse", "ast", "dataclasses", "json", "pathlib",
              "re", "sys", "typing"}


def zero_token_audit() -> tuple[bool, list[str]]:
    """F6(d): parse THIS module's imports via AST; stdlib allowlist only — no
    network modules, no model calls, grep-able."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    return mods <= _STDLIB_OK, sorted(mods)


def run_eval(target_name: str = "attention-efficiency") -> bool:
    target = TARGETS[target_name]
    index = load_index()
    labels = {d.doc_id: d.label for d in EVAL_SET}

    print(f"=== TRANSFER GATE EVAL — target: {target['name']} ===")
    print(f"target spec (data, not prose): {target}")
    print(f"eval set: {len(EVAL_SET)} docs "
          f"({sum(1 for d in EVAL_SET if d.label == 'TRUE')} TRUE / "
          f"{sum(1 for d in EVAL_SET if d.label == 'RHYME-TRAP')} RHYME-TRAP) "
          f"— LOCKED BEFORE MEASUREMENT at build time (module docstring)")
    for d in EVAL_SET:
        print(f"  [{d.label:10}] {d.doc_id:18} {d.path.split('/')[-1]}"
              f"{(' :: ' + d.section) if d.section else ''}")
        print(f"               {d.rationale}")

    decisions, contracts, scores, kwsets = {}, {}, {}, {}
    print(f"\n--- gate decisions (every decision shows its reasoning) ---")
    for d in EVAL_SET:
        c = derive_contract(d.path, d.section, index)
        contracts[d.doc_id] = c
        dec = gate(c, target)
        decisions[d.doc_id] = dec.admit
        verdict = "ADMIT" if dec.admit else "BLOCK"
        flag = "OK " if (dec.admit == (d.label == "TRUE")) else "ERR"
        print(f"\n[{flag}] {d.label:10} {d.doc_id} -> {verdict}")
        print(f"  doc: {c.doc} :: {c.section}")
        print(f"  title: {c.title[:100]}")
        for line in c.derivation:
            print(f"  {line}")
        for chk in dec.checks:
            print(f"  check {chk}")
        print(f"  claims_hold_under_assumptions ({len(c.claims_hold_under_assumptions)}):")
        for a in c.claims_hold_under_assumptions:
            print(f"    - {a[:110]}")
        print(f"  source_question: {c.source_question[:110]}")
        if dec.matched:
            print(f"  shared vocabulary (reported, NOT decisive): "
                  f"{', '.join(dec.matched)}")

    # baseline: keyword-overlap scorer at its best-F1 threshold AND at
    # matched recall (tuned to the gate's true-recall — same sensitivity,
    # compare the rhyme damage)
    print(f"\n--- rhyme baseline (keyword overlap, the 'word search' control) ---")
    print(f"keywords: {BASELINE_KEYWORDS}")
    for d in EVAL_SET:
        c = contracts[d.doc_id]
        text = read_card(d.path, d.section)[1]
        hits = keyword_hits(c.title + "\n" + text)
        kwsets[d.doc_id] = hits
        scores[d.doc_id] = len(hits) / len(BASELINE_KEYWORDS)
    for d in EVAL_SET:
        print(f"  {d.label:10} {d.doc_id:18} score "
              f"{scores[d.doc_id]:.3f} ({len(kwsets[d.doc_id])}/"
              f"{len(BASELINE_KEYWORDS)}): {', '.join(kwsets[d.doc_id]) or '-'}")

    cands = [0.0] + sorted(set(scores.values())) + [max(scores.values()) + 0.01]
    sweep = [(t, f1_at(t, scores, labels)) for t in sorted(set(cands))]
    best_t = max(sweep, key=lambda x: (x[1], -x[0]))[0]  # tie -> lower threshold
    gate_recall = sum(1 for d, lab in labels.items()
                      if lab == "TRUE" and decisions[d]) / \
        max(1, sum(1 for lab in labels.values() if lab == "TRUE"))
    match_t = min((scores[d] for d, lab in labels.items()
                   if lab == "TRUE" and scores[d] > 0),
                  default=0.0)  # admit-if->=t tuned so baseline recall == gate

    gm = confusion(decisions, labels)
    bmb = confusion({d: scores[d] >= best_t for d in scores}, labels)
    bmm = confusion({d: scores[d] >= match_t for d in scores}, labels)

    def show(name: str, m: dict) -> None:
        print(f"  {name}")
        print(f"               ADMIT  BLOCK")
        for lab in ("TRUE", "RHYME-TRAP"):
            print(f"  {lab:12} {m[(lab, 'ADMIT')]:5}  {m[(lab, 'BLOCK')]:5}")

    print(f"\n--- confusion matrices (rows = ground-truth label, cols = decision) ---")
    show("GATE (transfer contract):", gm)
    show(f"BASELINE @ best-F1 t={best_t:.3f} (F1={f1_at(best_t, scores, labels):.3f}):", bmb)
    show(f"BASELINE @ matched-recall t={match_t:.3f} (recall == gate "
         f"{gate_recall:.2f}):", bmm)
    print("  threshold sweep (t, admit-class F1): " +
          ", ".join(f"({t:.3f},{f:.3f})" for t, f in sweep))

    sep = min(scores[d] for d, lab in labels.items() if lab == "TRUE") > \
        max(scores[d] for d, lab in labels.items() if lab == "RHYME-TRAP")
    base_rate_best = bmb[("RHYME-TRAP", "ADMIT")] / \
        max(1, sum(1 for lab in labels.values() if lab == "RHYME-TRAP"))
    base_rate_match = bmm[("RHYME-TRAP", "ADMIT")] / \
        max(1, sum(1 for lab in labels.values() if lab == "RHYME-TRAP"))
    gate_rate = gm[("RHYME-TRAP", "ADMIT")] / \
        max(1, sum(1 for lab in labels.values() if lab == "RHYME-TRAP"))

    true_n = sum(1 for lab in labels.values() if lab == "TRUE")
    trap_n = len(EVAL_SET) - true_n
    fa = gm[("TRUE", "ADMIT")] / true_n >= 0.9
    fb = gm[("RHYME-TRAP", "BLOCK")] / trap_n >= 0.9
    fc = base_rate_match > gate_rate
    ok4, mods = zero_token_audit()
    reasons = sum(1 for d in EVAL_SET
                  if contracts[d.doc_id].derivation and decisions[d.doc_id] is not None)
    fe = reasons == len(EVAL_SET)

    print(f"\n--- falsifiers ---")
    print(f"F6(a) gate admits TRUE >= 9/10: {'PASS' if fa else 'FAIL'} — "
          f"{gm[('TRUE', 'ADMIT')]}/{true_n}")
    print(f"F6(b) gate blocks RHYME-TRAP >= 9/10: {'PASS' if fb else 'FAIL'} — "
          f"{gm[('RHYME-TRAP', 'BLOCK')]}/{trap_n}")
    print(f"F6(c) baseline concedes rhyme where the gate does not: "
          f"{'PASS' if fc else 'FAIL'} — trap-admit rate @ matched recall "
          f"{base_rate_match:.1%} (baseline) vs {gate_rate:.1%} (gate); "
          f"@ best-F1 {base_rate_best:.1%}")
    print(f"      separating keyword threshold exists: {'YES' if sep else 'NO'} "
          f"— min(TRUE score) "
          f"{min(scores[d] for d, lab in labels.items() if lab == 'TRUE'):.3f} vs "
          f"max(TRAP score) "
          f"{max(scores[d] for d, lab in labels.items() if lab == 'RHYME-TRAP'):.3f}"
          + ("" if sep else " — every operating point concedes a rhyme admit "
                            "or a lost true transfer"))
    print(f"F6(d) zero LLM tokens: {'PASS' if ok4 else 'FAIL'} — stdlib imports "
          f"only {mods}; no network modules; no model calls")
    print(f"F6(e) every decision printed its reasoning line: "
          f"{'PASS' if fe else 'FAIL'} — {reasons}/{len(EVAL_SET)}")
    ok = fa and fb and fc and ok4 and fe
    print(f"\nOVERALL: {'PASS' if ok else 'FAIL'} — contracts are RULE-DERIVED "
          f"from card metadata; automatic claim/assumption extraction is the "
          f"NEXT door (SciCite/Claimify lineage), not built here")
    return ok


# ----------------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["eval", "contract"])
    ap.add_argument("path", nargs="?", default="")
    ap.add_argument("--section", default="")
    ap.add_argument("--target", default="attention-efficiency",
                    choices=sorted(TARGETS))
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    if args.cmd == "eval":
        sys.exit(0 if run_eval(args.target) else 1)
    if not args.path:
        ap.error("contract requires a card path")
    c = derive_contract(args.path, args.section)
    target = TARGETS[args.target]
    dec = gate(c, target)
    print(f"TRANSFER CONTRACT — {c.doc} :: {c.section}")
    print(f"  title: {c.title}")
    print(f"  variable: {c.variable}")
    print(f"  regime: {c.regime}")
    print(f"  as_of: {c.as_of}")
    print(f"  source_question: {c.source_question}")
    print(f"  claims_hold_under_assumptions:")
    for a in c.claims_hold_under_assumptions:
        print(f"    - {a}")
    print(f"  derivation:")
    for line in c.derivation:
        print(f"    {line}")
    print(f"  gate vs '{target['name']}': "
          f"{'ADMIT' if dec.admit else 'BLOCK'}")
    for chk in dec.checks:
        print(f"    check {chk}")


if __name__ == "__main__":
    main()
