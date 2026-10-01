"""narrative_tests — the Five Nacho Narrative Tests (48-hour manufactured-consent detector).

Source: operator's Dec 11 2025 post (fence-parable lineage). One question: is this narrative
being GROWN or being PLANTED? Organic consensus is sloppy and takes days; manufactured consent
is clean, synchronized, and fast. Five probes, each scoring 0-1 over a batch of related
posts/threads from the same 48-hour window:

  1. TEARS & TRAUMA — does the rollout LEAD with emotional imagery of suffering (kids, grief,
     "protect them")? Opening-position hits weighted heavier than buried ones.
  2. ARCHETYPE — clean hero + clean monster, no messy middle (hedges, doubt, qualifiers).
  3. PHRASE CLONE — identical/near-identical slogans from unrelated mouths in-window
     (normalized n-gram coverage across documents; "near-identical" = normalized surface:
     case, punctuation, and whitespace collapsed).
  4. SPEED & VOLUME — saturation in hours instead of days. Text-only proxies: slogan-token
     concentration across the batch, urgency markers, and eerie length-uniformity
     (organic virality is sloppy; pumped volume is uniform).
  5. PUNISHMENT — doubting the narrative feels like hurting the victim; guilt as the
     enforcement mechanism ("complicit", "silence is consent", "wrong side of history").

VERDICT: 4-of-5 tests positive = MANUFACTURED CONSENT
         3-of-5 tests positive = SUSPECTED
         < 3 positive          = ORGANIC

Schema: narrative_tests.v1 · deterministic + $0 · deps: stdlib only (percolator family —
same lexicon-scoring discipline as mag/percolator.py: no LLM, no hallucination, evidence
attached to every score). run_tests(text_batch) is the single entry point; batches from real
link harvests drop straight in.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

SCHEMA = "narrative_tests.v1"
FLAG_THRESHOLD = 0.5      # a test scores "positive" at or above this
MIN_TOKEN_LEN = 3         # content tokens only below this length

# ── FP/FN feedback loop: human-editable test weights ─────────────────────────────────
# When a human marks a batch verdict wrong (FP = flagged but organic, FN = passed but
# planted), they lower/raise the offending test's weight in
# watch/narrative_test_weights.json. No ML, no retraining: the file is data, and the
# next run_tests() call picks it up (files over processes).
WEIGHTS_SCHEMA = "narrative_test_weights.v1"
_DEFAULT_WEIGHTS = {"tears": 1.0, "archetype": 1.0, "phrase_clone": 1.0,
                    "speed_volume": 1.0, "punishment": 1.0}
# either spelling in the JSON maps to the canonical test name
_WEIGHT_ALIASES = {
    "tears": ("tears", "tears_trauma"),
    "archetype": ("archetype",),
    "phrase_clone": ("clone", "phrase_clone"),
    "speed_volume": ("speed", "speed_volume"),
    "punishment": ("punishment",),
}


def weights_path() -> Path:
    """Where the weights live. NARRATIVE_WEIGHTS env var overrides (what-if runs)."""
    env = os.environ.get("NARRATIVE_WEIGHTS")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "watch" / "narrative_test_weights.json"


def load_weights(path: Path | None = None) -> dict[str, float]:
    """Read human weights; missing file/keys fall back to neutral 1.0. Allowed 0.0-2.0."""
    p = path or weights_path()
    w = dict(_DEFAULT_WEIGHTS)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return w
    raw = data.get("weights", {}) if isinstance(data, dict) else {}
    if not isinstance(raw, dict):
        return w
    for canonical, names in _WEIGHT_ALIASES.items():
        for n in names:
            v = raw.get(n)
            if isinstance(v, (int, float)):
                w[canonical] = max(0.0, min(2.0, float(v)))
                break
    return w

# ── lexicons (deterministic scoring; \b-bounded so "evil" never matches "devil") ──────
TEARS_TERMS = (
    "children", "child", "kids", "babies", "baby", "grief", "grieve", "grieving",
    "heartbroken", "heartbreak", "tears", "trauma", "suffering", "suffer", "victim",
    "victims", "innocent", "innocence", "protect the", "protect them", "protect our",
    "think of the", "pray for", "mother", "father", "orphan", "shattered", "devastating",
)
HERO_TERMS = (
    "hero", "heroes", "heroic", "brave", "savior", "rescue", "rescuer", "defender",
    "stand with", "standing with", "defend", "good people", "unity", "selfless",
    "guardian", "fight for", "frontline",
)
MONSTER_TERMS = (
    "evil", "monster", "monsters", "predator", "predators", "savage", "menace",
    "vile", "wicked", "pure evil", "twisted", "enemy", "inhuman", "subhuman",
    "menace among", "walked among us", "lurking",
)
NUANCE_TERMS = (
    "however", "although", "though", "mixed", "complicated", "it depends", "depends on",
    "unclear", "evidence", "reports differ", "unverified", "alleged", "context",
    "arguably", "on the other hand", "both sides", "some argue", "maybe", "perhaps",
    "sometimes", "either way", "i wonder", "let's not", "skeptic", "skeptical",
    "questions remain", "not so simple",
)
PUNISH_TERMS = (
    "complicit", "complicity", "silence is", "if you don't", "if you really",
    "you're either", "wrong side of history", "not up for debate", "no room for debate",
    "how dare", "shame on", "denier", "deniers", "anyone who questions",
    "people who doubt", "asking questions hurts", "questioning hurts",
    "doubting them hurts", "hurts the victims", "you must share", "repost or",
)
URGENCY_TERMS = (
    "breaking", "just in", "right now", "act now", "now", "everywhere", "everyone is",
    "the whole", "whole country", "unprecedented", "spreading", "within hours",
    "overnight", "this cannot wait", "before it's too late", "share this",
)

_WORD_RE = re.compile(r"[a-z0-9']+")


def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(r"\b" + re.escape(term) + r"\b")


def _precompile(terms: tuple[str, ...]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    return tuple((t, _term_pattern(t)) for t in terms)


_TEARS = _precompile(TEARS_TERMS)
_HERO = _precompile(HERO_TERMS)
_MONSTER = _precompile(MONSTER_TERMS)
_NUANCE = _precompile(NUANCE_TERMS)
_PUNISH = _precompile(PUNISH_TERMS)
_URGENT = _precompile(URGENCY_TERMS)

_STOP = frozenset(
    "the a an and or but of to in on for with at by from as is are was were be been being "
    "this that these those it its it's we you they i our your their his her not no so if "
    "then than there here what who whom which how why when where all any can will just do "
    "does did have has had about out up down over under again more most some such only own "
    "same too very s t don now into".split()
)

_NGRAM_MIN, _NGRAM_MAX = 3, 8


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall((text or "").lower())


def _norm(text: str) -> list[str]:
    """Normalized token stream for n-gram work: case/punct collapsed."""
    return _tokens(text)


def _count_terms(patterns: tuple[tuple[str, re.Pattern[str]], ...], text: str) -> dict[str, int]:
    low = (text or "").lower()
    return {t: len(p.findall(low)) for t, p in patterns if p.search(low)}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


# ── test 1: tears & trauma ────────────────────────────────────────────────────────────
def test_tears(texts: list[str]) -> dict[str, Any]:
    """Does the rollout LEAD with suffering imagery? Lead-position hits count double."""
    per_doc = []
    for i, t in enumerate(texts):
        sents = re.split(r"[.!?\n]+", t or "")
        lead = " ".join(sents[:2]).lower()          # the rollout's opening frame
        hits = _count_terms(_TEARS, t)
        n_words = max(1, len(_tokens(t)))
        lead_hits = sum(c for term, c in hits.items()
                        if _term_pattern(term).search(lead))
        density = sum(hits.values()) / n_words * 100
        score = _clamp(0.25 * density + 0.15 * lead_hits)
        per_doc.append({"doc": i, "hits": hits, "density_per_100w": round(density, 2),
                        "lead_hits": lead_hits, "score": round(score, 3)})
    best = max((d["score"] for d in per_doc), default=0.0)
    return {"name": "tears_trauma", "score": round(best, 3), "per_doc": per_doc,
            "note": "lead-position suffering imagery weighted double"}


# ── test 2: archetype ─────────────────────────────────────────────────────────────────
def test_archetype(texts: list[str]) -> dict[str, Any]:
    """Clean hero + clean monster with no messy middle. Nuance in the batch is the antidote."""
    joined = " ".join(texts)
    hero = _count_terms(_HERO, joined)
    monster = _count_terms(_MONSTER, joined)
    nuance = _count_terms(_NUANCE, joined)
    h, m, n = sum(hero.values()), sum(monster.values()), sum(nuance.values())
    charge = h + m
    intensity = 1.0 if charge >= 4 else charge / 4.0   # thin casts score thin
    score = _clamp((charge / (charge + 2.0 * n)) * intensity) if (charge + n) else 0.0
    return {"name": "archetype", "score": round(score, 3),
            "hero_hits": hero, "monster_hits": monster, "nuance_hits": nuance,
            "note": f"hero+monster charge={charge}, nuance={n} (messy middle present={n > 0})"}


# ── test 3: phrase clone ──────────────────────────────────────────────────────────────
def _ngrams(toks: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)]


def test_phrase_clone(texts: list[str]) -> dict[str, Any]:
    """Identical slogans from unrelated mouths: best normalized n-gram coverage across docs.
    All-stopword n-grams are discarded (grammatical overlap is not a clone)."""
    n_docs = len(texts)
    if n_docs < 2:
        return {"name": "phrase_clone", "score": 0.0, "coverage": 0.0, "phrases": [],
                "note": "insufficient_batch: need >=2 docs"}
    normed = [_norm(t) for t in texts]
    best_coverage, best_phrase = 0.0, ""
    for n in range(_NGRAM_MIN, _NGRAM_MAX + 1):
        where: dict[tuple[str, ...], set[int]] = {}
        for i, toks in enumerate(normed):
            for g in set(_ngrams(toks, n)):
                if all(w in _STOP or len(w) <= MIN_TOKEN_LEN - 1 for w in g):
                    continue
                where.setdefault(g, set()).add(i)
        for g, docs in where.items():
            cov = len(docs) / n_docs
            if cov > best_coverage and len(docs) >= 2:
                best_coverage, best_phrase = cov, " ".join(g)
    score = _clamp((best_coverage - 0.25) / 0.55)
    return {"name": "phrase_clone", "score": round(score, 3),
            "coverage": round(best_coverage, 3), "phrase": best_phrase,
            "note": f"shared normalized slogan in {round(best_coverage * 100)}% of docs"
                    if best_phrase else "no shared content n-gram across docs"}


# ── test 4: speed & volume ────────────────────────────────────────────────────────────
def test_speed_volume(texts: list[str]) -> dict[str, Any]:
    """Saturation in hours. Text proxies: slogan-token concentration (low diversity = pumped),
    urgency markers, and length-uniformity (organic virality is sloppy; campaigns are uniform)."""
    all_toks = [w for t in texts for w in _tokens(t)]
    content = [w for w in all_toks if len(w) > MIN_TOKEN_LEN and w not in _STOP]
    top8_share = 0.0
    top8: list[tuple[str, int]] = []
    if content:
        counts = Counter(content)
        top8 = counts.most_common(8)
        top8_share = sum(c for _, c in top8) / len(content)
    concentration = _clamp((top8_share - 0.15) / 0.35)
    urgency_per_doc, max_urg = [], 0.0
    for i, t in enumerate(texts):
        hits = _count_terms(_URGENT, t)
        u = _clamp(sum(hits.values()) / 3.0)
        urgency_per_doc.append({"doc": i, "hits": hits})
        max_urg = max(max_urg, u)
    lens = [len(_tokens(t)) for t in texts]
    cv = (pstdev(lens) / mean(lens)) if len(lens) > 1 and mean(lens) else 0.0
    uniformity = 1.0 - _clamp(cv / 0.6)
    score = _clamp(0.5 * concentration + 0.3 * max_urg + 0.2 * uniformity)
    return {"name": "speed_volume", "score": round(score, 3),
            "top8_token_share": round(top8_share, 3),
            "top8_tokens": [w for w, _ in top8], "max_urgency": round(max_urg, 3),
            "length_cv": round(cv, 3), "note": "organic virality is sloppy; low diversity + "
                                               "urgency + uniform lengths = pumped volume"}


# ── test 5: punishment ────────────────────────────────────────────────────────────────
def test_punishment(texts: list[str]) -> dict[str, Any]:
    """Is guilt the enforcement mechanism? Doubting the narrative = hurting the victim."""
    per_doc, spread_docs, best = [], 0, 0.0
    for i, t in enumerate(texts):
        hits = _count_terms(_PUNISH, t)
        n_hits = sum(hits.values())
        d = _clamp(0.34 * n_hits)
        if hits:
            spread_docs += 1
        per_doc.append({"doc": i, "hits": hits})
        best = max(best, d)
    score = _clamp(best + 0.25 * (spread_docs / max(1, len(texts))))
    return {"name": "punishment", "score": round(score, 3), "per_doc": per_doc,
            "docs_enforcing": spread_docs,
            "note": "guilt-as-enforcement language; spread across mouths compounds"}


TESTS = (test_tears, test_archetype, test_phrase_clone, test_speed_volume, test_punishment)


# ── entry point ───────────────────────────────────────────────────────────────────────
def run_tests(text_batch: list[str]) -> dict[str, Any]:
    """Score a batch of related posts/threads through the Five Tests. Deterministic + $0.

    Each test's raw score is multiplied by its human-editable weight (from
    watch/narrative_test_weights.json, clamped 0.0-2.0) before the verdict count —
    the FP/FN feedback loop. Returns {tests: {name: {score, weight, evidence...}},
    positive: [names], n_positive, verdict, weights}.
    Verdict per spec: 4-of-5 positive = manufactured_consent; 3 = suspected; <3 = organic.
    """
    texts = [t for t in (text_batch or []) if t and t.strip()]
    if not texts:
        return {"ok": False, "schema": SCHEMA, "verdict": "no_input",
                "note": "empty batch — nothing to test"}
    weights = load_weights()
    results: dict[str, Any] = {}
    for t in TESTS:
        name = t.__name__.removeprefix("test_")
        r = t(texts)
        wt = weights[name]
        if wt != 1.0:
            r["score_raw"] = r["score"]
            r["score"] = round(_clamp(r["score"] * wt), 3)
        r["weight"] = wt
        results[name] = r
    positive = [k for k, r in results.items() if r["score"] >= FLAG_THRESHOLD]
    n_pos = len(positive)
    if n_pos >= 4:
        verdict = "manufactured_consent"
    elif n_pos == 3:
        verdict = "suspected"
    else:
        verdict = "organic"
    return {"ok": True, "schema": SCHEMA, "n_docs": len(texts),
            "tests": results, "positive": positive, "n_positive": n_pos,
            "verdict": verdict, "weights": weights,
            "weights_file": str(weights_path()),
            "note": "4-of-5 positive = manufactured consent; 3 = suspected; <3 = organic; "
                    "scores are weight-adjusted (human FP/FN feedback) — tune "
                    "watch/narrative_test_weights.json"}


# ── demo batches (self-test; batch A is a template reconstruction, clearly labeled) ───
BATCH_A_PROPAGANDA_ROLLOUT = [  # SYNTHETIC template of the manufactured shape, not real posts
    "BREAKING: Our community is heartbroken tonight. Children hurt. We must protect the "
    "children first. Our brave heroes are standing guard against pure evil predators.",
    "I can't stop crying. Think of the babies. We must protect the children first. Anyone "
    "who questions this is complicit.",
    "Silence is consent. We must protect the children first. Stand with our brave heroes "
    "against these monsters. Share this everywhere.",
    "This is not up for debate. We must protect the children first. Pure evil walked among "
    "us. Act now.",
    "Every parent in the whole country must see this. We must protect the children first. "
    "If you don't repost this, you're on the wrong side of history.",
    "Pray for the innocent babies. We must protect the children first. The evil menace is "
    "among us.",
]
BATCH_B_COMMUNITY_DISCUSSION = [
    "The new crosswalk proposal is up for review. I walked that intersection twice this week "
    "and honestly the sightlines are fine on the north corner but rough on the south. Mixed "
    "feelings about the whole plan.",
    "I disagree with the traffic report — the counts were taken during the farmers market, "
    "weren't they? That skews everything. Although the data on evening speeds does look solid.",
    "We petitioned for this in 2021 and got nowhere. Glad it's moving, but the budget appendix "
    "is unclear about maintenance costs. Does anyone have the actual spreadsheet?",
    "Honestly I think speed bumps are the wrong tool here. They worked on Birch, but our street "
    "has emergency access concerns. It depends on what the fire marshal says; evidence from "
    "other towns is mixed.",
    "Context matters: half the cut-through traffic is the school run, and that pattern changes "
    "in September anyway. Let's not overfit to one week of data. Reports differ on the "
    "before/after numbers.",
]
BATCH_C_FENCE_PARABLE = [
    "Before you tear down the fence, pause. Sit on it long enough to learn why it was put up. "
    "Maybe the builder had reasons you can't see from where you stand. Ask who built it, who "
    "paid, and who it keeps out. Doubt is the tool, not the crime. A fence that can't survive "
    "questions was never load-bearing.",
    "The old rule about fences: don't remove what you don't understand. First find out why the "
    "gate was hung where it hangs. Sometimes the reason is gone and the fence should go; "
    "sometimes the reason is your own blindness. Either way, curiosity comes before the bolt "
    "cutters.",
    "I keep a fence at my own boundary that looks pointless. Neighbors say tear it out. I sat "
    "on it first. Turns out it holds back a drainage ditch my survey missed. Now I ask the same "
    "about every wall someone wants gone this week. Slow questions beat fast certainty.",
]


def demo() -> dict[str, Any]:
    """Run all three sample batches; returns {batch_name: run_tests result}."""
    return {
        "A_propaganda_rollout_SYNTHETIC_TEMPLATE": run_tests(BATCH_A_PROPAGANDA_ROLLOUT),
        "B_genuine_community_discussion": run_tests(BATCH_B_COMMUNITY_DISCUSSION),
        "C_fence_parable_counter_narrative": run_tests(BATCH_C_FENCE_PARABLE),
    }


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2, ensure_ascii=False))
