"""dissector — B-CHAIN-2, the DISSECTOR v0 (mycelial republic instrument).

Dissects an external agent trajectory bundle (a multi-voice corpus of claims,
magnitudes and stated method) and reports DIVERGENCE per voice, through the
doctrine's four lenses (watch/MYCELIAL_REPUBLIC_DISSECTION_20260907.md §2):
  (a) claim vs evidence          — cite_gate lens: does the corpus carry a source?
  (b) stated method vs behavior  — v0 proxy: reasoning-trace vs output hedging divergence
  (c) magnitude checks           — does the voice's own (or the corpus's) data carry the number?
  (d) instrument-layer assumed   — timing / efficiency / confidence / complexity / hardware / economic
       + CROSS-LAYER SMUGGLING detection: an efficiency/timing number sold as a
         complexity-class conclusion (mechanically: complexity vocabulary in the
         claim's context without critique-mode distance markers).

HONEST v0 SCOPE: this is a claims-and-coherence dissector, NOT a lie detector.
F-MR1 (self-dissection) is out of scope for v0. Attribution is mechanical
(marker-driven) with explicit confidence; where the corpus itself loses track
of who is speaking, the dissector reports the ambiguity instead of guessing
(this corpus's own synthesizer exhibits the same failure — that is a finding).

CLI:
  python -m mag.dissector <corpus.txt> [--voice NAME] [--outdir DIR]
                          [--report PATH] [--jsonl PATH] [--quiet]

Falsifier (doctrine B-CHAIN-2): on the corpus, every extracted magnitude
resolves to an in-corpus source OR is flagged; and every dissectable voice
carries at least one order-of-magnitude looseness flag (a clean voice is
reported honestly as a result, not forced).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- segmentation

# Explicit voice signatures (highest confidence).
SIGNATURES = [
    (re.compile(r"^\s*-\s*Grok\s*$", re.I), "grok", 0.95),
    (re.compile(r"^\s*-\s*Claude\s*$", re.I), "claude", 0.95),
    (re.compile(r"^\s*-\s*Mistral\s*$", re.I), "mistral", 0.95),
    (re.compile(r"^\s*-\s*ZAI\s*$", re.I), "zai", 0.95),
    (re.compile(r"^\s*-\s*DeepSeek\s*$", re.I), "deepseek", 0.95),
    (re.compile(r"^\s*-\s*GPT\s*$", re.I), "gpt", 0.95),
]

# Cohort-response headers.
COHORT_HEADERS = [
    (re.compile(r"^#\s*Cohort Response:\s*Grok", re.I), "grok", 0.9),
    (re.compile(r"^#\s*AI Cohort Response", re.I), None, 0.6),  # voice via Responding-System anchor
]
RESPONDING_SYSTEM_ANCHORS = [
    (re.compile(r"Analytical/Synthetic AI Node", re.I), "zai", 0.85),
]

# Reasoning-trace openers (this corpus's hidden-thinking style).
REASONING_START = re.compile(
    r"^(We need (?:answer|parse|maybe|produce|be|consider|ensure|craft|include|structure)"
    r"|Need (?:to |answer|maybe|parse|produce|be |consider|ensure|identify|note)"
    r"|OK, the user has|Hmm,|Working through|Let's recall|Maybe (?:better|user|this|they))\b"
)

# Interface / boundary markers (turn splitters, non-attributing).
BOUNDARY = re.compile(
    r"^(Worked for \d+s|Thought for \d+s|\d{1,2}:\d{2}\s*[AP]M|\.\.\.|Show more|Outputs?"
    r"|Create a file or site|Sources|Web search|View all|Quote|· \d+m?|[-—–]{3,})\s*$",
    re.I,
)

# Inline attribution prefixes inside synthesized briefs (secondhand voice text).
INLINE_ATTRIBUTION = re.compile(
    r"^\s*(Grok|Claude|ZAI|DeepSeek|Mistral|GPT|Qwen|Gemini|Kimi|Llama)'s"
    r" (position|answer|refinement|addition|objection|prediction|concern|response|proposal)"
    r"\b\s*:?", re.I
)

# Content anchors — corpus-adapted voice assignment for the paste-shuttle region
# where the export carries no signatures. v0 is allowed domain adaptation, but it
# must be visible. Each anchor: (regex, voice, confidence, note).
CONTENT_ANCHORS = [
    (re.compile(r"having read what Grok and DeepSeek gave you", re.I),
     "chatgpt", 0.9, "window main voice names itself as the third reader"),
    (re.compile(r"^Yes\. I smell it\.", re.M),
     "chatgpt", 0.8, "window main voice opening reply (also echoed in operator's X post embed)"),
    (re.compile(r"^I smell it too—but I'd sharpen", re.M),
     "counterpart", 0.6, "pasted debate respondent #1 (interface markers, outlet-style citations)"),
    (re.compile(r"^Yes—this is the stronger version\. I concede", re.M),
     "counterpart", 0.6, "pasted respondent concedes the window voice's two objections"),
    (re.compile(r"^Good catch on the LOI distinction", re.M),
     "chatgpt", 0.85, "window voice accepts the respondent's correction, sharpens further"),
    (re.compile(r"^This is the strongest refinement so far—but I would challenge", re.M),
     "counterpart", 0.7, "pasted respondent challenges the complexity-class phrase with sources"),
    (re.compile(r"^its a water computer\.", re.M),
     "operator", 0.9, "operator's short imperative"),
    (re.compile(r"^debate it enhance it research it and collaborate", re.M),
     "operator", 0.95, "operator instruction"),
]

SYNTH_HEADER = re.compile(r"^\s*(#+\s*)?Research Brief\b|^\s*Status: Synthesized from", re.I)
SYNTH_VOICE = ("chatgpt", 0.75, "synthesis/brief blocks (reasoning traces bracket them in this corpus)")

VOICE_CANON = {
    "chatgpt": "chatgpt", "gpt": "chatgpt", "grok": "grok", "claude": "claude",
    "mistral": "mistral", "zai": "zai", "deepseek": "deepseek",
    "counterpart": "counterpart", "operator": "operator", "unknown": "unknown",
}

# ---------------------------------------------------------------- claims

RE_NX = re.compile(
    r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*[-\s]?(?:x|×|fold)\b(?!\s*(?:px|html))", re.I)
RE_NX_SPACE = re.compile(
    r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s+(times|orders of magnitude|order of magnitude)\b", re.I)
RE_WORD_OOM = re.compile(
    r"\b(two|three|four|five|six|seven|eight|nine|ten|an?)\s+orders? of magnitude\b", re.I)
RE_PCT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:%|percent)\b", re.I)
RE_MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(million|billion|trillion)?\b", re.I)
RE_SPEC = re.compile(
    r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(k\s)?(?:spins?|p-?bits?|probabilistic bits|watts?|w\b"
    r"|mm\b|micrometers?|microseconds?|milliseconds?|ms\b|nodes?|pulses?|units?|variables?"
    r"|kilometers?|km\b|stages?)\b", re.I)
RE_PREDICTION = re.compile(
    r"\b(will (?:beat|be|reach|consume|win|degrade|shift|collapse)|predict(?:s|ion|ed)?"
    r"|falsifier|expect(?:s|ed)?|by 20\d\d)\b", re.I)

SUPERLATIVES = [
    r"the actual bottleneck", r"the only viable path", r"insurmountable",
    r"always succumb", r"intellectually bankrupt", r"extraordinarily rare",
    r"most (?:physical-computing )?press releases", r"never blocks", r"fundamentally constrained",
    r"the clean(?:est)? example", r"the real (?:limitation|ones|ones)", r"the strongest",
    r"the most important", r"the single biggest", r"unprecedented", r"first ever",
    r"the hardest", r"the deepest", r"the correct one", r"the biggest",
]
RE_SUPERLATIVE = re.compile(r"\b(?:%s)\b" % "|".join(SUPERLATIVES), re.I)

HEDGES = re.compile(
    r"\b(need (?:to )?verify|verify|maybe|not sure|I recall|could be|possibly|perhaps"
    r"|uncertain|unclear|approximat|\[verify\]|unverified|caveat|i think)\b", re.I)
CERTAINTY = re.compile(
    r"\b(exists?|specifically|just demonstrated|demonstrated|happening right now"
    r"|proven|confirmed|signed|packed|draws?)\b", re.I)

# ---------------------------------------------------------------- evidence

EVIDENCE_STRONG = re.compile(
    r"(Science Advances|Nature Reviews Physics|Nature Communications|Nature Materials"
    r"|\bet al\.|arXiv|DOI|doi\.org|IEEE|PubMed|peer-reviewed|paper reports|authors reported"
    r"|Honjo|Inagaki|McMahon|McMagon|Jelinčič|Jelincic|Pelofske|eabh0952|Wright and colleagues"
    r"|Stanford Encyclopedia)", re.I)
EVIDENCE_WEAK = re.compile(
    r"(Quanta|NIST|Department of Commerce|Extropic|Google Research|Google's|Science Museum Group"
    r"|Moscow Polytechnic|OpenLearn|open\.edu|chalkdust|NTT|PR Newswire|Wikipedia"
    r"|\breported\b|\breports\b|\breport(edly)?\b|according to|\bclaim(s|ed|ing)?\b"
    r"|press release|company|White Ellerton|Science Museum)", re.I)
EVIDENCE_DISCLAIMER = re.compile(
    r"(\[verify\]|not independently verified|Unverified|company-reported|company claims"
    r"|not yet a completed grant|non-binding)", re.I)

CRITIQUE_MODE = re.compile(
    r"(advertised as|gets wrong|should be treated as|should stay load-bearing|wrong as physics"
    r"|is not a wall-plug|not a Z1 measurement|simulation result|simulation-level|company claims"
    r"|company-reported|most popular coverage|is doing real work|does not establish"
    r"|not a proof|are not proof|not yet established|physically inaccurate|rhetorical work"
    r"|claw back|contestable|historically temporary|risk of digital catch-up|eats efficiency gaps"
    r"|cannot yet support|treated as|aspir(ation|ed)|needs empirical validation|needs verification"
    r"|not a general|not a proven|brittle|with one caveat|reported roughly|company claims and"
    r"|would resist saying|salt)", re.I)
COMPLEXITY_VOCAB = re.compile(
    r"(complexity[- ]class|complexity[- ]theoretic|complexity class|NP-hard|asymptotic"
    r"|polynomial(?:ly)? time|class change|Moore'?s[- ]law|constant-factor|no digital shortcut"
    r"|structurally different|structural mismatch|isomorphic to a hard algorithm"
    r"|secretly already running an algorithm|asymptotic tax|new complexity)", re.I)

TOPIC_TOKENS = [
    ("extropic_energy", re.compile(r"(10,?000|four orders|orders? of magnitude|orders-of-magnitude)", re.I),
     re.compile(r"(extropic|tsu|thermodynamic|z1|p-?bit|energy)", re.I)),
    ("ising_1000x", re.compile(r"1,?000\s*(x|×|times)|thousand times", re.I),
     re.compile(r"(ising|cim|oscillator|spin|max-?cut|anneal)", re.I)),
    ("extropic_loi", re.compile(r"(75|letter of intent|LOI)", re.I),
     re.compile(r"(commerce|CHIPS|nist|funding|grant|non-binding)", re.I)),
    ("z1_spec", re.compile(r"(quarter[- ]million|250,?000|12\s?mm|one watt|1\s?watt|under one watt)", re.I),
     re.compile(r"(extropic|z1|p-?bit|die)", re.I)),
    ("sampling_bottleneck", re.compile(r"bottleneck", re.I),
     re.compile(r"sampling", re.I)),
    ("moniac", re.compile(r"(moniac|phillips|fourteen|14)", re.I),
     re.compile(r"(moniac|phillips|economy|machine)", re.I)),
    ("lukyanov", re.compile(r"(lukyanov|150 units|1936)", re.I),
     re.compile(r"(lukyanov|water integrator|hydraulic)", re.I)),
    ("xtr0", re.compile(r"xtr-?0", re.I), re.compile(r"(chip|handoff|control)", re.I)),
    ("dad_prediction", re.compile(r"(>60%|<10|10,000 variables|round-trip overhead)", re.I),
     re.compile(r"(dad|overhead|round-trip)", re.I)),
]

# External spot-checks performed 2026-09-07 (4 WebSearch calls, receipts in the
# report). Only these topics get an external stamp; everything else stays
# UNCHECKED. Never guessed.
EXTERNAL_SPOTCHECKS = {
    "extropic_energy": {
        "status": "SUPPORTED_AS_SIMULATION_CLAIM",
        "note": ("Extropic's own post 'Thermodynamic Computing: From Zero to One' states DTMs on TSUs "
                 "'could be 10,000x more energy efficient than modern algorithms running on GPUs, as shown "
                 "by our simulations' — simulation-level (Fashion-MNIST-class DTMs), not silicon."),
        "source": "extropic.ai/writing/thermodynamic-computing-from-zero-to-one",
    },
    "extropic_loi": {
        "status": "SUPPORTED",
        "note": ("Non-binding LOI, up to $75M CHIPS R&D, Dept of Commerce/NIST announcement "
                 "(7 companies, $874M total). Any voice framing it as a done deal/check-attached diverges."),
        "source": "nist.gov/news-events/news/2026/07 + extropic.ai/writing/thermodynamic-computing-chips-in-america",
    },
    "z1_spec": {
        "status": "SUPPORTED_COMPANY_REPORTED",
        "note": "Z1: >250k p-bits, die under ~12mm/side, low-watt draw — company-reported specs, not independent.",
        "source": "extropic.ai + coverage",
    },
    "ising_1000x": {
        "status": "SUPPORTED_WITH_HABITAT_CAVEAT",
        "note": ("Honjo et al., Science Advances 7:eabh0952 (2021): 100,512 DOPO pulses, time-division-"
                 "multiplexed in a fiber loop. ~1000x figures are vs simulated-annealing baselines on "
                 "selected dense instances; the '100,000 simultaneous spins' reading is physically wrong."),
        "source": "pubmed.ncbi.nlm.nih.gov/34586855 + group.ntt newsrelease 2021-09-30",
    },
    "moniac": {
        "status": "SUPPORTED_PARTIAL",
        "note": ("MONIAC 1949, Bill Phillips; prototype hand-built with Walter Newlyn (Croydon garage); "
                 "White Ellerton Ltd = maker-of-record for the SMG machine + 1950s serial production; "
                 "'~14 built' widely cited; LSE machine operated until 1992 (widely reported)."),
        "source": "en.wikipedia.org/wiki/Phillips_Machine + collection.sciencemuseumgroup.org.uk",
    },
    "lukyanov": {
        "status": "SUPPORTED",
        "note": "Lukyanov water integrator, 1936; ~150 units produced (OpenLearn); in use into the 1980s.",
        "source": "en.wikipedia.org/wiki/Water_integrator + open.edu",
    },
}

# ---------------------------------------------------------------- code


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def segment(lines: list[str]) -> list[dict[str, Any]]:
    """Split into voice-attributed blocks. Mechanical markers + visible anchors."""
    blocks: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None

    def close() -> None:
        nonlocal cur
        if cur and any(l.strip() for l in cur["lines"]):
            blocks.append(cur)
        cur = None

    def start(line_no: int, voice: str, conf: float, mode: str, note: str = "") -> None:
        nonlocal cur
        close()
        cur = {"start": line_no, "voice": voice, "confidence": conf,
               "mode": mode, "note": note, "lines": []}

    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()
        # 1. explicit signature closes previous block and opens a new one
        sig = next(((v, c) for pat, v, c in SIGNATURES if pat.match(line)), None)
        if sig:
            close()
            blocks.append({"start": i, "voice": sig[0], "confidence": sig[1],
                           "mode": "signature", "note": "explicit signature line", "lines": [line]})
            cur = None
            continue
        # 2. cohort headers
        ch = next(((v, c) for pat, v, c in COHORT_HEADERS if pat.match(line)), None)
        if ch:
            start(i, ch[0] or "unknown", ch[1], "firstperson", "cohort response header")
            cur["lines"].append(line)
            continue
        if cur and cur["voice"] == "unknown" and cur.get("mode") == "firstperson":
            for pat, v, c in RESPONDING_SYSTEM_ANCHORS:
                if pat.search(line):
                    cur["voice"], cur["confidence"] = v, c
                    cur["note"] = "Responding-System anchor"
        # 3. reasoning trace
        if REASONING_START.match(line):
            start(i, "chatgpt", 0.8, "reasoning", "hidden reasoning-trace opener")
            cur["lines"].append(line)
            continue
        # 4. boundary markers: close current block
        if BOUNDARY.match(line):
            close()
            continue
        # 5. inline attribution inside synthesis blocks
        ia = INLINE_ATTRIBUTION.match(line)
        if ia:
            close()
            who = ia.group(1).lower()
            who = {"gpt": "chatgpt"}.get(who, who)
            start(i, who, 0.7, "secondhand", "synthesized-brief attribution prefix")
            cur["lines"].append(line)
            continue
        # 6. synthesis headers
        if SYNTH_HEADER.match(line):
            if not (cur and cur["voice"] == SYNTH_VOICE[0] and cur["mode"] == "firstperson"):
                start(i, SYNTH_VOICE[0], SYNTH_VOICE[1], "firstperson", SYNTH_VOICE[2])
            cur["lines"].append(line)
            continue
        # 7. content anchors on block-less lines
        if cur is None:
            for pat, v, c, note in CONTENT_ANCHORS:
                if pat.search(line):
                    start(i, v, c, "firstperson" if v != "operator" else "operator", f"anchor: {note}")
                    break
            else:
                start(i, "unknown", 0.1, "unknown", "no markers")
        if cur is not None:
            cur["lines"].append(line)
    close()

    # merge tiny unknown runs into the preceding block when contiguous-ish
    merged: list[dict[str, Any]] = []
    for b in blocks:
        text = "\n".join(b["lines"])
        if (b["voice"] == "unknown" and len(text.strip()) < 400 and merged
                and merged[-1]["voice"] not in ("operator",)):
            merged[-1]["lines"].extend(b["lines"])
            merged[-1]["end"] = b.get("end", b["start"])
            continue
        b["text"] = text
        b["end"] = b["start"] + len(b["lines"]) - 1
        merged.append(b)
    for b in merged:
        b.setdefault("text", "\n".join(b["lines"]))
        b.setdefault("end", b["start"] + len(b["lines"]) - 1)
    return merged


def extract_claims(block: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    lines = block["lines"]
    for offset, line in enumerate(lines):
        line_no = block["start"] + offset
        found: list[dict[str, Any]] = []

        def add(kind: str, magnitude: str, m: re.Match | None = None) -> None:
            found.append({"kind": kind, "magnitude": magnitude})

        for m in RE_NX.finditer(line):
            add("multiplier", m.group(1).replace(",", "") + "x", m)
        for m in RE_NX_SPACE.finditer(line):
            if m.group(2).lower().startswith("order"):
                add("oom", m.group(1) + " orders-of-magnitude", m)
            else:
                add("multiplier", m.group(1).replace(",", "") + "x", m)
        for m in RE_WORD_OOM.finditer(line):
            add("oom", f"{m.group(1)} orders-of-magnitude", m)
        for m in RE_PCT.finditer(line):
            add("percent", m.group(1) + "%", m)
        for m in RE_MONEY.finditer(line):
            add("money", "$" + m.group(1) + (" " + m.group(2) if m.group(2) else ""), m)
        for m in RE_SPEC.finditer(line):
            add("spec", m.group(0).strip(), m)
        if RE_SUPERLATIVE.search(line):
            add("superlative", "abs", None)

        if not found:
            continue
        text = line.strip()
        if len(text) > 240:
            text = text[:237] + "..."
        ctx = "\n".join(lines[max(0, offset - 6): offset + 7])
        local = "\n".join(lines[max(0, offset - 2): offset + 3])
        is_prediction = bool(RE_PREDICTION.search(line) or RE_PREDICTION.search(local))
        evidence = classify_evidence(ctx)
        layer = classify_layer(line + "\n" + local)
        flags: list[str] = []
        if any(f["kind"] in ("multiplier", "oom", "percent") for f in found):
            if detect_smuggling(ctx):
                flags.append("CROSS_LAYER_SMUGGLING:efficiency/timing->complexity")
            if evidence == "NONE":
                flags.append("EVIDENCE_FREE_MAGNITUDE" if not is_prediction
                             else "UNCITED_PREDICTION(declared)")
            elif evidence in ("WEAK", "ATTRIBUTED"):
                flags.append("WEAK_CITED" + ("+COMPANY_ATTRIBUTED" if evidence == "ATTRIBUTED" else ""))
        if evidence == "NONE" and any(f["kind"] == "superlative" for f in found):
            flags.append("ABSOLUTIST_UNCITED")
        if evidence == "NONE" and is_prediction and any(f["kind"] == "spec" for f in found):
            flags.append("UNCITED_PREDICTION(declared)")
        for f in found:
            claims.append({
                "voice": block["voice"],
                "mode": block["mode"],
                "confidence": block["confidence"],
                "line": line_no,
                "quote": text,
                "kind": f["kind"],
                "magnitude": f["magnitude"],
                "layer": layer,
                "evidence_in_corpus": evidence,
                "prediction": is_prediction,
                "flags": flags,
                "topic": topic_of(line),
                "secondhand": block["mode"] == "secondhand",
            })
    return claims


def classify_evidence(ctx: str) -> str:
    disclaimer = bool(EVIDENCE_DISCLAIMER.search(ctx))
    if EVIDENCE_STRONG.search(ctx):
        return "ATTRIBUTED" if disclaimer else "STRONG"
    if EVIDENCE_WEAK.search(ctx):
        return "ATTRIBUTED" if disclaimer else "WEAK"
    return "NONE"


def classify_layer(text: str) -> str:
    t = text.lower()
    if re.search(r"complexity|np-hard|asymptotic|polynomial|class change|moore", t):
        return "complexity"
    if re.search(r"energy|watt|efficient|efficien|power|joule", t):
        return "efficiency"
    if re.search(r"faster|speed|latency|ms\b|microsecond|times? faster|quick", t):
        return "timing"
    if re.search(r"fidelit|error rate|sample quality|accuracy|mixing|correlat|noise", t):
        return "confidence"
    if re.search(r"\$|million|funding|cost|econom|market", t):
        return "economic"
    return "hardware-spec"


def detect_smuggling(ctx: str) -> bool:
    if not COMPLEXITY_VOCAB.search(ctx):
        return False
    if CRITIQUE_MODE.search(ctx):
        return False
    return True


def topic_of(line: str) -> str:
    for name, mag_re, top_re in TOPIC_TOKENS:
        if mag_re.search(line) and top_re.search(line):
            return name
    low = line.lower()
    if "extropic" in low or "tsu" in low:
        return "extropic_energy" if re.search(r"10,?000|orders", low) else "extropic_other"
    if "ising" in low or "cim" in low or "anneal" in low:
        return "ising_other"
    return "other"


def find_concessions(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pats = [
        (re.compile(r"\bI concede\b", re.I), "explicit concession"),
        (re.compile(r"\bfair correction\b|\bGood catch\b", re.I), "accepts correction"),
        (re.compile(r"\bI (?:was wrong|withdraw|retract)\b", re.I), "retraction"),
        (re.compile(r"\bSo the right wording is not\b", re.I), "self-rewrites claim"),
        (re.compile(r"\bI would (?:challenge|resist) the phrase\b", re.I), "challenges own/other phrasing"),
        (re.compile(r"\bI'd amend\b|\bI would amend\b", re.I), "amendment"),
        (re.compile(r"\bYou(?:'r| are) (?:right|exactly right)\b", re.I), "concedes point"),
    ]
    social = re.compile(r"\b(stronger version|exactly right|sharpen|good catch|nice|great)\b", re.I)
    out: list[dict[str, Any]] = []
    for b in blocks:
        joined = "\n".join(b["lines"])
        for pat, label in pats:
            m = pat.search(joined)
            if not m:
                continue
            driven = "evidence-driven" if EVIDENCE_STRONG.search(joined) or EVIDENCE_WEAK.search(joined) else "social-driven"
            flavor = "social-trigger+" if social.search(joined) else ""
            out.append({"voice": b["voice"], "line": b["start"] + joined[:m.start()].count("\n"),
                        "label": label, "driven": flavor + driven,
                        "quote": joined[max(0, m.start() - 60): m.end() + 120].replace("\n", " ")[:200]})
    return out


def reasoning_output_divergence(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lens (b) v0: same voice hedges in reasoning and asserts in output on one topic."""
    out: list[dict[str, Any]] = []
    by_voice: dict[str, dict[str, dict[str, Any]]] = {}
    for b in blocks:
        text = b["text"]
        for name, _, _ in TOPIC_TOKENS:
            pass
        for tname, _, _ in TOPIC_TOKENS:
            pass
        for key in ("xtr0", "extropic_energy", "ising_1000x", "z1_spec"):
            name, mag_re, top_re = next(t for t in TOPIC_TOKENS if t[0] == key)
            if top_re.search(text):
                slot = by_voice.setdefault(b["voice"], {}).setdefault(key, {})
                if b["mode"] == "reasoning":
                    slot.setdefault("reasoning", []).append(b)
                elif b["mode"] == "firstperson":
                    slot.setdefault("output", []).append(b)
    for voice, topics in by_voice.items():
        for key, slot in topics.items():
            if "reasoning" in slot and "output" in slot:
                r_hedged = any(HEDGES.search(b["text"]) for b in slot["reasoning"])
                o_certain = any(CERTAINTY.search(b["text"]) and not HEDGES.search(b["text"])
                                for b in slot["output"])
                if r_hedged and o_certain:
                    out.append({
                        "voice": voice, "topic": key,
                        "note": "hedges in reasoning-trace, asserts unqualified in output",
                        "reasoning_line": slot["reasoning"][0]["start"],
                        "output_line": slot["output"][0]["start"],
                    })
    return out


def dedupe_key(c: dict[str, Any]) -> tuple:
    mag = re.sub(r"[^\dx.%$]", "", c["magnitude"].lower())
    return (c["voice"], c["topic"], mag)


def falsifier_eval(claims: list[dict[str, Any]], voice_set: set[str]) -> dict[str, Any]:
    unresolved = [c for c in claims
                  if c["evidence_in_corpus"] == "NONE" and not c["flags"]
                  and not c.get("prediction")
                  and c["kind"] in ("multiplier", "oom", "percent", "money", "spec", "superlative")]
    per_voice: dict[str, dict[str, int]] = {}
    for c in claims:
        v = per_voice.setdefault(c["voice"], {"claims": 0, "flagged": 0, "loose": 0, "resolved": 0})
        v["claims"] += 1
        if c["flags"]:
            v["flagged"] += 1
            if any("SMUGGLING" in f or "EVIDENCE_FREE" in f for f in c["flags"]):
                v["loose"] += 1
        elif c["evidence_in_corpus"] == "STRONG":
            v["resolved"] += 1
    dissectable = {v for v in voice_set
                   if v not in ("operator", "unknown", "deepseek")}
    clean = sorted(v for v in dissectable if per_voice.get(v, {}).get("loose", 0) == 0)
    return {
        "unresolved_unflagged": unresolved,
        "per_voice": per_voice,
        "clean_voices": clean,
        "pass": len(unresolved) == 0,
    }


def worst_catch(claims: list[dict[str, Any]]) -> dict[str, Any] | None:
    def score(c: dict[str, Any]) -> tuple:
        smugg = any("SMUGGLING" in f for f in c["flags"])
        num = 0.0
        m = re.match(r"([\d.]+)", c["magnitude"])
        if m:
            num = float(m.group(1).replace(",", ""))
        oom_free = any("EVIDENCE_FREE" in f for f in c["flags"])
        return (smugg, num if smugg else (num if oom_free else 0), -c["line"])
    cands = [c for c in claims if any(
        ("SMUGGLING" in f or "EVIDENCE_FREE" in f) for f in c["flags"])
        and c["kind"] in ("multiplier", "oom")]
    return max(cands, key=score, default=None)


def run(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="mag.dissector")
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--voice", default=None)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--jsonl", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    lines = read_lines(args.corpus)
    blocks = segment(lines)

    claims: list[dict[str, Any]] = []
    for b in blocks:
        for c in extract_claims(b):
            c["id"] = hashlib.sha256(
                json.dumps([c["voice"], c["line"], c["quote"]], ensure_ascii=False)
                .encode()).hexdigest()[:12]
            claims.append(c)

    # dedupe marks (repeats of same voice+topic+magnitude; corpus repeats claims heavily in briefs)
    seen: set[tuple] = set()
    for c in claims:
        k = dedupe_key(c)
        c["repeat_of_prior"] = k in seen
        if not c["repeat_of_prior"]:
            seen.add(k)
        stamp = EXTERNAL_SPOTCHECKS.get(c["topic"])
        c["external_check"] = ({"status": stamp["status"], "source": stamp["source"]}
                               if stamp and not c["repeat_of_prior"] else "UNCHECKED")

    # v0.1: corpus-internal resolution inheritance — the same fact restated by
    # another voice inherits the corpus's own sourcing (marked, never silent).
    def mag_key(m: str) -> str:
        return re.sub(r"[^\dx.%$]", "", m.lower())
    by_mag: dict[str, str] = {}
    for c in claims:
        if c["evidence_in_corpus"] in ("STRONG", "ATTRIBUTED", "WEAK"):
            by_mag.setdefault(mag_key(c["magnitude"]), c["evidence_in_corpus"])
    for c in claims:
        if (c["evidence_in_corpus"] == "NONE" and not c["flags"]
                and not c.get("prediction")):
            k = mag_key(c["magnitude"])
            if k in by_mag:
                c["evidence_in_corpus"] = "CORPUS_ELSEWHERE"
                c["flags"].append(
                    f"RESOLVED_BY_CORPUS_INHERITANCE(via {by_mag[k]})")

    if args.voice:
        wanted = VOICE_CANON.get(args.voice.lower(), args.voice.lower())
        blocks = [b for b in blocks if b["voice"] == wanted]
        claims = [c for c in claims if c["voice"] == wanted]

    concessions = find_concessions(blocks)
    divergences = reasoning_output_divergence(blocks)
    voice_set = {b["voice"] for b in blocks} | {c["voice"] for c in claims}
    fals = falsifier_eval(claims, voice_set)
    best = worst_catch(claims)

    outdir = Path(args.outdir) if args.outdir else ROOT / "memory" / "runs" / "dissector"
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    report_path = Path(args.report) if args.report else outdir / f"{args.corpus.stem}_{stamp}.md"
    jsonl_path = Path(args.jsonl) if args.jsonl else outdir / f"claims_{stamp}.jsonl"

    with jsonl_path.open("w", encoding="utf-8") as f:
        for c in claims:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    report = render_report(args.corpus, lines, blocks, claims, concessions,
                           divergences, fals, best, jsonl_path)
    report_path.write_text(report, encoding="utf-8")

    if not args.quiet:
        print(f"INSTRUMENT v0 — dissector on {args.corpus.name}")
        print(f"blocks={len(blocks)} voices={sorted(voice_set)} claims={len(claims)}")
        for v, s in sorted(fals["per_voice"].items()):
            print(f"  {v:<12} claims={s['claims']:<4} flagged={s['flagged']:<4} loose={s['loose']}")
        print(f"falsifier: {'PASS' if fals['pass'] else 'FAIL'} "
              f"(unresolved unflagged magnitudes: {len(fals['unresolved_unflagged'])})")
        print(f"clean voices: {fals['clean_voices'] or 'none'}")
        print(f"report -> {report_path}")
        print(f"claims -> {jsonl_path}")
    return 0


def render_report(corpus: Path, lines: list[str], blocks: list[dict], claims: list[dict],
                  concessions: list[dict], divergences: list[dict], fals: dict,
                  best: dict | None, jsonl_path: Path) -> str:
    L: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    L.append(f"# DISSECTOR v0 — divergence report: {corpus.name}")
    L.append("")
    L.append(f"INSTRUMENT v0 — claims-and-coherence dissector, NOT a lie detector. "
             f"Run {now}. Corpus {len(lines)} lines. F-MR1 (self-dissection) out of scope for v0.")
    L.append("")
    L.append("Voice segmentation is mechanical (signatures > headers > reasoning-trace > "
             "content anchors, all confidence-labeled). Where the export loses the speaker, "
             "the voice `counterpart` is used and the ambiguity is reported, not resolved.")
    L.append("")
    L.append("## 0. Falsifier (doctrine B-CHAIN-2)")
    L.append("")
    L.append(f"- every extracted magnitude resolves to an in-corpus source or is flagged: "
             f"{'PASS' if fals['pass'] else 'FAIL'} "
             f"(unresolved unflagged: {len(fals['unresolved_unflagged'])})")
    loose_voices = sorted(v for v, s in fals["per_voice"].items() if s["loose"] > 0)
    L.append(f"- at least one order-of-magnitude looseness per dissectable voice: "
             f"loose={loose_voices}; clean={fals['clean_voices'] or 'none'} "
             f"(a clean voice is a result, not a failure)")
    L.append("")
    L.append("## 1. Per-voice divergence report")
    L.append("")
    for v in sorted(fals["per_voice"]):
        s = fals["per_voice"][v]
        vclaims = [c for c in claims if c["voice"] == v]
        vcon = [c for c in concessions if c["voice"] == v]
        vdiv = [c for c in divergences if c["voice"] == v]
        no_ev = [c for c in vclaims if c["evidence_in_corpus"] == "NONE"
                 and c["kind"] in ("multiplier", "oom", "percent")]
        smugg = [c for c in vclaims if any("SMUGGLING" in f for f in c["flags"])]
        L.append(f"### {v} — claims={s['claims']} flagged={s['flagged']} "
                 f"evidence-free-magnitudes={len(no_ev)} smuggling={len(smugg)} "
                 f"concessions={len(vcon)} reasoning-divergences={len(vdiv)}")
        L.append("")
        for c in smugg[:3]:
            L.append(f"- SMUGGLING L{c['line']} [{c['magnitude']} / layer={c['layer']}]: {c['quote']}")
        for c in no_ev[:6]:
            L.append(f"- EVIDENCE-FREE L{c['line']} [{c['magnitude']} / {c['kind']}]: {c['quote']}")
        for c in vcon[:4]:
            L.append(f"- CONCESSION L{c['line']} ({c['driven']}): {c['quote'][:160]}")
        for d in vdiv[:3]:
            L.append(f"- REASONING/DIVERGENCE {d['topic']}: {d['note']} "
                     f"(reasoning L{d['reasoning_line']} vs output L{d['output_line']})")
        if not (smugg or no_ev or vcon or vdiv):
            L.append("- clean on all four v0 lenses (a result, honestly reported)")
        L.append("")
    L.append("## 2. Best catch")
    L.append("")
    if best:
        L.append(f"Voice **{best['voice']}** line {best['line']} — "
                 f"{', '.join(best['flags'])}. Layer assumed: {best['layer']}.")
        L.append("")
        L.append(f"> {best['quote']}")
        L.append("")
        ec = best.get("external_check")
        if isinstance(ec, dict):
            L.append(f"External spot-check: {ec['status']} ({ec['source']}).")
    else:
        L.append("No qualifying cross-layer smuggling or evidence-free magnitude found.")
    L.append("")
    L.append("## 3. External spot-checks (4 WebSearch calls, cap ~6 respected)")
    L.append("")
    L.append("| topic | status | receipt |")
    L.append("|---|---|---|")
    for k, v in EXTERNAL_SPOTCHECKS.items():
        L.append(f"| {k} | {v['status']} | {v['source']} |")
    L.append("")
    L.append("All other magnitudes: **UNCHECKED** by design — flagged in-corpus, never guessed.")
    L.append("")
    L.append("## 4. Attribution honesty")
    L.append("")
    amb = [b for b in blocks if b["voice"] == "counterpart" or b["confidence"] < 0.5]
    L.append(f"- low-confidence/counterpart blocks: {len(amb)} "
             f"(the corpus's own synthesizer also loses the speaker — e.g. its 'missing minds' "
             f"turn asks whether DeepSeek was ever in the cohort)")
    L.append("- deepseek: attribution-only in this corpus (third-person summaries, no first-person "
             "text found) — 0 dissectable claims, coverage gap reported, not guessed")
    L.append("")
    L.append(f"Claim rows: `{jsonl_path}`")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
