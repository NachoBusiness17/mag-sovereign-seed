"""decl_attention — Declarative Attention as a byte-level view protocol.

FOLDS arXiv:2609.02737 ("Language Models Can Control Their Own Attention",
Ho et al., KAIST AI + Google DeepMind) into the fleet's attention lineage.
Card + cite-gate 5/5: watch/TRIAGE_HAUL_BOT_01_20260906.md.

Paper mechanics (§2.3, §5.1, verified against arxiv.org/html/2609.02737):
  the model DECLARES <global>/<focus>/<local> inside its own output; a state
  machine watches for the closing '>' of an opening tag, reverts on the closing
  tag, and <global> produces NO transition (it is the default state). Per decode
  step a vLLM metadata hook rewrites the KV block table so unattended blocks are
  never read — kept spans round OUTWARD to block boundaries so no declared token
  is ever dropped. No kernel changes. Their numbers: −52.0%/−31.1% attended
  tokens, −1.27pp/−2.75pp accuracy (Gemma-4-31B / Qwen-3.6-27B).

The reinterpretation (this cage has no GPU — do not fake kernels): the same
three modes as a BYTE-LEVEL view protocol over real fleet read loads. A block
table splits a doc into hashed blocks (the KV block table analog); declaration
spans select which blocks are READ FROM DISK. Skipped blocks are never read —
attended BYTES is the honest proxy for attended KV positions.

LINEAGE (steal the bones, name the reinterpretation):
  - memory/steal/STEAL_ZERO_MEM_20260814.md — "memory ops are not generation":
    this view is fully non-generative, deterministic routing at query time.
    Zero-Mem kept ONE reader LLM call; we go stricter — the spot-quiz reader is
    regex extraction. Zero tokens end to end.
  - memory/steal/STEAL_PYNCD_ATTENTION_20260814.md — "distinct axes stay
    distinct; the diagram is the check": mode / selector / window are separate
    declaration attributes that never merge, and the TEST is the composition
    check (GLOBAL reconstruction byte-identity + quiz-answer identity).
  - seat law "read the row, not the zone" = <focus> compiled into a mask
    (the triage card's own tape).
  - SparDA (arXiv:2606.04511, NVIDIA; abstract verified 2026-09-06) — B4 adds
    FORECAST: the paper's fourth per-layer projection ("the Forecast ...
    predicts the KV blocks needed by the next layer", decoupled from the
    attention query) as a byte-proxy lookahead prefetch over scripted query
    walks. Cheap deterministic adjacency instead of a learned head; a miss
    falls back to the on-demand path and is COUNTED, never silent (SparDA's
    honest-accuracy analog at proxy scale).

HONESTY: kernel/accuracy numbers are the PAPER's, not ours. Ours are byte-proxy
numbers on two real fleet artifacts. Table BUILD reads the whole file once
(computing offsets, hashes, lightweight per-block tags — the paper's analog is
the pre-placed magic-chunk transcript in the scaffold); build bytes are counted
and reported separately from per-query attended bytes.

Usage:
  python -m mag.decl_attention demo
  python -m mag.decl_attention forecast
  python -m mag.decl_attention view --doc corpus/CURRICULUM.md \
      --decl '<focus section="5.">'
"""
from __future__ import annotations

import argparse
import hashlib
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BLOCK_BYTES = 1200  # chunk target, bytes (paper targets ~2048-token segments)

# The paper's coarsest-boundary cascade, byte analog: never cut inside a word.
# paragraph break -> single newline -> sentence end -> clause end -> space
_CASCADE = ("\n\n", "\n", (". ", "! ", "? "), ("; ", ": ", ", "), " ")


@dataclass
class Block:
    idx: int
    start: int  # byte range in the raw file [start, end)
    end: int
    sha: str
    tags: list[str] = field(default_factory=list)  # lightweight build-time metadata


@dataclass
class Table:
    doc: str  # path as given
    total_bytes: int
    blocks: list[Block]
    build_bytes: int  # one-time table-build reads (honest, amortized)
    headings: list[tuple[int, str, int]] = field(default_factory=list)
    # (byte offset, heading text, level) — text docs only; the metadata that
    # lets <focus section="..."> name a span without attending its content.


@dataclass
class Span:
    mode: str  # GLOBAL | FOCUS | LOCAL
    attrs: dict[str, str]
    start: int
    end: int


# ---------------------------------------------------------------- block table

def _cut_at(data: bytes, lo: int, target: int) -> int:
    """Coarsest-boundary cut near `target`, mirroring the paper's segmenter:
    cut only over-cap units, coarsest boundary first, never inside a word."""
    base = max(lo + 1, target - 400)
    window = data[base:target + 400]
    for bound in _CASCADE:
        seps = (bound,) if isinstance(bound, str) else bound
        best = (-1, b"")
        for s in seps:
            p = window.rfind(s.encode())
            if p > best[0]:
                best = (p, s.encode())
        if best[0] != -1:
            return base + best[0] + len(best[1])
    return target  # hard cut (no boundary at all in the window)


def build_table(doc: str | Path, block_bytes: int = BLOCK_BYTES) -> Table:
    """One-time table build. Reads the file once; that cost is `build_bytes`."""
    path = Path(doc)
    if not path.is_absolute():
        path = ROOT / path
    raw = path.read_bytes()
    build_bytes = len(raw)
    headings: list[tuple[int, str, int]] = []
    if path.suffix == ".json" and b'"cards"' in raw[:4096]:
        blocks = _card_blocks(raw)
    else:
        blocks, headings = _text_blocks(raw, block_bytes)
    return Table(str(path), len(raw), blocks, build_bytes, headings)


def _text_blocks(raw: bytes, block_bytes: int) -> tuple[list[Block],
                                                        list[tuple[int, str, int]]]:
    data = raw.decode("utf-8", errors="replace")
    heads = [(m.start(), m.group(2).strip(), len(m.group(1))) for m in
             re.finditer(r"^(#{1,6})\s+(.*\S)\s*$", data, re.M)]
    blocks, lo = [], 0
    while lo < len(raw):
        hi = len(raw) if len(raw) - lo <= block_bytes else _cut_at(raw, lo, lo + block_bytes)
        blk = Block(len(blocks), lo, hi, hashlib.sha256(raw[lo:hi]).hexdigest()[:16])
        blk.tags = [txt for off, txt, _ in heads if lo <= off < hi]
        blocks.append(blk)
        lo = hi
    return blocks, heads


def _card_blocks(raw: bytes) -> list[Block]:
    """One block per card of a topic_index-shaped JSON (block = retrieval split,
    the magic-chunk analog for a card catalog). Depth-scans the raw bytes.
    Gaps and the tail are folded into neighboring blocks so the block table
    tiles the file exactly (F(a) GLOBAL reconstruction must be byte-identical)."""
    key = raw.find(b'"cards"')
    arr = raw.find(b"[", key)
    blocks = [Block(0, 0, arr + 1, hashlib.sha256(raw[:arr + 1]).hexdigest()[:16],
                    tags=["header"])]
    depth, start, in_str, esc = 0, None, False, False
    for i in range(arr + 1, len(raw)):
        c = raw[i:i + 1]
        if in_str:
            if esc:
                esc = False
            elif c == b"\\":
                esc = True
            elif c == b'"':
                in_str = False
            continue
        if c == b'"':
            in_str = True
        elif c == b"{":
            if depth == 0:
                start = i
            depth += 1
        elif c == b"}":
            depth -= 1
            if depth == 0:
                tags = []
                m = re.search(rb'"topics": \[([^\]]*)\]', raw[start:i + 1])
                if m:
                    tags = [t.strip(" \t\r\n\"") for t in
                            m.group(1).decode("utf-8", "replace").split(",")
                            if t.strip(" \t\r\n\"")]
                blocks.append(Block(len(blocks), start, i + 1,
                                    hashlib.sha256(raw[start:i + 1]).hexdigest()[:16],
                                    tags))
    for prev, nxt in zip(blocks, blocks[1:]):  # fold inter-card gaps backward
        if nxt.start > prev.end:
            prev.end = nxt.start
            prev.sha = hashlib.sha256(raw[prev.start:prev.end]).hexdigest()[:16]
    if blocks[-1].end < len(raw):  # fold the tail (array/doc closers) into last
        blocks[-1].end = len(raw)
        blocks[-1].sha = hashlib.sha256(raw[blocks[-1].start:blocks[-1].end]).hexdigest()[:16]
    return blocks


# ------------------------------------------------- declarations (state machine)

_TAG = re.compile(r"<(focus|local)\b([^>]*)>|</(focus|local)>|<global\s*/?>",
                  re.IGNORECASE)
_ATTR = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def parse_declarations(text: str) -> list[Span]:
    """The paper's state machine: transition on the '>' of an opening tag,
    revert to global on the closing tag. <global> produces NO transition."""
    spans, cur, cur_start, attrs_prev = [], "global", 0, ""
    for m in _TAG.finditer(text):
        open_tag, attrs_txt, close_tag = m.group(1), m.group(2), m.group(3)
        if close_tag:
            if cur != "global":
                spans.append(Span(cur, dict(_ATTR.findall(attrs_prev or "")),
                                  cur_start, m.start()))
            cur, cur_start = "global", m.end()
        elif open_tag:
            if cur != "global":
                spans.append(Span(cur, dict(_ATTR.findall(attrs_prev or "")),
                                  cur_start, m.start()))
            cur, cur_start, attrs_prev = open_tag.upper(), m.start(), attrs_txt
    if cur != "global":
        spans.append(Span(cur, dict(_ATTR.findall(attrs_prev or "")), cur_start,
                          len(text)))
    return spans


def plan_visible(table: Table, span: Span) -> set[int]:
    """Which blocks this declaration attends. Focus selectors mirror the
    paper's named-segment attributes; LOCAL takes the recent-N suffix.
    Kept spans are block-granular — the paper's "round the kept span outward
    to block boundaries" is inherent when the block IS the unit."""
    mode = span.mode.upper()
    if mode == "GLOBAL":
        return {b.idx for b in table.blocks}
    if mode == "LOCAL":
        n = int(span.attrs.get("window", "3"))
        return {b.idx for b in table.blocks[-n:]}
    vis: set[int] = set()
    if "magic_chunks" in span.attrs:  # exact paper attribute
        vis |= {int(x) for x in re.split(r"[,\s]+", span.attrs["magic_chunks"])
                if x.strip().isdigit()}
    if "topic" in span.attrs:
        want = span.attrs["topic"].lower()
        vis |= {b.idx for b in table.blocks if want in (t.lower() for t in b.tags)}
    if "section" in span.attrs and table.headings:
        pre = span.attrs["section"].lower()
        for i, (off, txt, lvl) in enumerate(table.headings):
            if not txt.lower().startswith(pre):
                continue
            end = table.total_bytes  # section span runs to the next heading
            for off2, _, lvl2 in table.headings[i + 1:]:
                if lvl2 <= lvl:
                    end = off2
                    break
            vis |= {b.idx for b in table.blocks if b.start < end and b.end > off}
    if "lines" in span.attrs:
        raw = Path(table.doc).read_bytes()  # offset math only; not attended content
        lines = raw.splitlines()
        a, _, bnd = span.attrs["lines"].partition("-")
        lo_off = sum(len(l) + 1 for l in lines[:int(a) - 1])
        hi_n = int(bnd) if bnd else int(a)
        hi_off = lo_off + sum(len(l) + 1 for l in lines[int(a) - 1:hi_n]) \
            if bnd else lo_off + 1
        vis |= {b.idx for b in table.blocks if b.start < hi_off and b.end > lo_off}
    return vis


# ------------------------------------------------------------- serving + quiz

def read_visible(table: Table, visible: set[int]) -> tuple[dict[int, bytes], int]:
    """Real disk reads: one open, seek per visible block. Skipped blocks are
    NEVER read — that is the entire point. Returns (blocks, bytes_from_disk)."""
    got, total = {}, 0
    with open(table.doc, "rb") as f:
        for idx in sorted(visible):
            b = table.blocks[idx]
            f.seek(b.start)
            got[idx] = f.read(b.end - b.start)
            total += b.end - b.start
    return got, total


def naive_read(doc: str | Path) -> bytes:
    path = Path(doc)
    return (path if path.is_absolute() else ROOT / path).read_bytes()


def extract(kind: str, needle: str, text: str) -> Any:
    if kind == "count":
        return len(re.findall(needle, text, re.S))
    m = re.search(needle, text, re.S)
    return m.group(1) if m else None


def extract_last(needle: str, text: str) -> str | None:
    hits = re.findall(needle, text, re.S)
    return hits[-1] if hits else None


# --------------------------------------------------------------- spot quiz
# Deterministic readers (Zero-Mem: zero reader tokens). Each item:
#   qid, kind (find|count|last), needle, declaration text, expect
#   expect="in"  -> answer must equal the GLOBAL answer (F(b)/F(c) integrity)
#   expect="out" -> the honest-drop analog: the answer is out of scope for
#                   this mode, and the protocol must DETECT and REPORT that
#                   (never silently answer from the wrong slice).

CURRICULUM_QUIZ = [
    ("q_nc_license", "find", r"anthropics/courses \((CC-BY-NC[^)]*)\)",
     '<focus section="Headline">', "in"),
    ("q_economist_lane", "find", r"## 5\. (ECONOMIST / COST)",
     '<focus section="5.">', "in"),
    ("q_addendum_clone", "find", r"Cloned to corpus/library/([a-z0-9-]+)",
     '<focus section="ADDENDUM">', "in"),
    ("q_wave1_license_w3", "find", r"`anthropic-courses` \| [^|]+\| ([^|]+?) \|",
     '<local window="3">', "in"),
    ("q_wave1_license_w2", "find", r"`anthropic-courses` \| [^|]+\| ([^|]+?) \|",
     '<local window="2">', "in"),
    ("q_nc_license_local", "find", r"anthropics/courses \((CC-BY-NC[^)]*)\)",
     '<local window="2">', "out"),
]

TOPIC_INDEX_QUIZ = [
    ("q_mcp_bucket", "count", r'"topics": \[[^\]]*"mcp"[^\]]*\]',
     '<focus topic="mcp">', "in"),
    ("q_newest_title", "last", r'"title": "([^"]+)"', '<local window="100">', "in"),
    ("q_first_card", "find", r'"path": "([^"]+)"', '<local window="100">', "out"),
    ("q_header_total", "find", r'"cards_indexed": (\d+)',
     '<focus topic="mcp">', "out"),
]


def answer(table: Table, span: Span, kind: str, needle: str) -> Any:
    visible = plan_visible(table, span)
    got, _ = read_visible(table, visible)
    text = b"".join(got[i] for i in sorted(got)).decode("utf-8", errors="replace")
    if kind == "count":
        return extract("count", needle, text)
    if kind == "last":
        return extract_last(needle, text)
    return extract("find", needle, text)


def run_quiz(table: Table, items: list[tuple]) -> dict[str, Any]:
    global_span = Span("global", {}, 0, 0)
    _, gbytes = read_visible(table, plan_visible(table, global_span))
    out: dict[str, Any] = {"global_bytes": gbytes, "rows": []}
    for qid, kind, needle, decl, expect in items:
        spans = parse_declarations(decl + " ")
        span = spans[0] if spans else global_span
        ans = answer(table, span, kind, needle)
        gans = answer(table, global_span, kind, needle)
        visible = plan_visible(table, span)
        _, abytes = read_visible(table, visible)
        cut = 100.0 * (1 - abytes / gbytes) if gbytes else 0.0
        intact = ans == gans
        detected_drop = ans is None or not intact  # honest-drop detection
        verdict = ("PASS" if intact else "MISS") if expect == "in" else \
                  ("PASS(drop reported)" if detected_drop else "FAIL(hidden drop)")
        out["rows"].append({
            "qid": qid, "decl": decl, "mode": span.mode, "expect": expect,
            "answer": ans, "global_answer": gans, "attended_bytes": abytes,
            "cut_pct": round(cut, 1), "intact": intact,
            "detected_drop": detected_drop, "verdict": verdict,
            "blocks": f"{len(visible)}/{len(table.blocks)}",
        })
    return out


# ---------------------------------------------------------------- falsifiers

def demo() -> bool:
    """Spot quiz over two real fleet artifacts. Prints the falsifier table and
    returns overall PASS/FAIL. No LLM, no writes — bytes in, verdicts out."""
    ok = True
    for name, doc, quiz in (("CURRICULUM", "corpus/CURRICULUM.md", CURRICULUM_QUIZ),
                            ("TOPIC_INDEX", "watch/topic_index.json",
                             TOPIC_INDEX_QUIZ)):
        table = build_table(doc)
        raw = naive_read(doc)
        q = run_quiz(table, quiz)
        print(f"\n=== {name} — {Path(table.doc).name} "
              f"({table.total_bytes} bytes, {len(table.blocks)} blocks, "
              f"table build read {table.build_bytes} bytes once) ===")
        # F(a): GLOBAL mode attended bytes == naive full read, byte-identical.
        visible = plan_visible(table, Span("global", {}, 0, 0))
        got, gbytes = read_visible(table, visible)
        rebuilt = b"".join(got[i] for i in sorted(got))
        fa = (rebuilt == raw) and gbytes == len(raw)
        print(f"F(a) GLOBAL byte-identity: {'PASS' if fa else 'FAIL'} "
              f"(attended {gbytes} == naive {len(raw)}, "
              f"sha {hashlib.sha256(rebuilt).hexdigest()[:12]})")
        ok &= fa
        for r in q["rows"]:
            print(f"  [{r['mode']:5}] {r['qid']:20} blocks {r['blocks']:9} "
                  f"attended {r['attended_bytes']:6}B  cut {r['cut_pct']:5.1f}%  "
                  f"-> {str(r['answer'])[:52]!r} [{r['verdict']}]")
            if r["verdict"].startswith("FAIL") or \
                    (r["expect"] == "in" and r["verdict"] == "MISS"):
                ok = False
        # F(b): FOCUS cuts >= 30% with in-scope answers intact, out reported.
        foci = [r for r in q["rows"] if r["mode"] == "FOCUS"]
        fb = bool(foci) and max(r["cut_pct"] for r in foci) >= 30.0 and \
            all(r["verdict"] != "FAIL" and r["verdict"] != "MISS" for r in foci)
        print(f"F(b) FOCUS cut>=30% w/ answers intact: "
              f"{'PASS' if fb else 'FAIL'} "
              f"(max cut {max((r['cut_pct'] for r in foci), default=0):.1f}%)")
        ok &= fb
        # F(c): LOCAL cuts >= 60%; out-of-window answers DETECTED + REPORTED.
        locs = [r for r in q["rows"] if r["mode"] == "LOCAL"]
        reported = [r["qid"] for r in locs if r["expect"] == "out" and
                    r["detected_drop"]]
        hidden = [r["qid"] for r in locs if r["verdict"] == "FAIL(hidden drop)"]
        fc = bool(locs) and max(r["cut_pct"] for r in locs) >= 60.0 and not hidden
        print(f"F(c) LOCAL cut>=60%: {'PASS' if fc else 'FAIL'} "
              f"(max cut {max((r['cut_pct'] for r in locs), default=0):.1f}%) | "
              f"out-of-window answers REPORTED: "
              f"{', '.join(reported) if reported else 'none'}"
              + (f" | HIDDEN DROPS: {', '.join(hidden)}" if hidden else ""))
        ok &= fc
    print(f"\nOVERALL: {'PASS' if ok else 'FAIL'} — "
          f"byte-proxy numbers on fleet loads; kernel numbers are the paper's")
    return ok


# ----------------------------------------------------------------- forecast
# SparDA (arXiv:2606.04511, verified against the abstract 2026-09-06): a
# fourth per-layer projection, the Forecast, sits "alongside Query, Key, and
# Value" and "predicts the KV blocks needed by the next layer" — decoupled
# from the attention query, enabling lookahead prefetch that overlaps the
# current layer's execution. Byte-proxy reinterpretation, no learned head and
# no GPU: before serving query k+1 of a scripted walk, predict its blocks
# from CHEAP DETERMINISTIC ADJACENCY ONLY —
#   topic docs: co-occurrence from the cards' own topic lists (within-card
#     cliques plus consecutive-card links); prefetch the top-`budget` blocks
#     by shared-neighbor count, ties by block index;
#   text docs: the next `budget` blocks in document order (next-section read).
# Prefetched blocks are read ONCE into a buffer; hits are served from it; a
# miss falls back to the existing on-demand seek()+read path and is COUNTED —
# never silent. The reader-visible slice is ALWAYS the declaration's mask:
# the forecast changes who pays the read, never what is read.

FORECAST_TOPIC_BUDGET = 60  # blocks prefetched per step, topic-index walk
FORECAST_DOC_LOOKAHEAD = 2  # blocks prefetched past the current max, text
BASELINE_SEED = 2609        # uniform-draw baseline seed (the arXiv id, fixed
                            # before measurement — never tuned)


@dataclass
class WalkStep:
    qid: str
    decl: str
    needle: str
    kind: str = "find"  # find | count | last — the spot-quiz readers, reused


# WALKS — chosen from the artifacts' shapes BEFORE any forecast measurement
# (triage law: pick the walk, then measure; a failed falsifier with numbers
# is a valid outcome, so no step may be edited after seeing its hit-rate).
# TOPIC_WALK: a plausible session — open the mcp bucket, move through its
# co-occurring neighbors, end on the newest cards and the operator-daily
# overseer topic (a deliberate low-adjacency jump: its miss must be visible).
TOPIC_WALK = [
    WalkStep("w_mcp_bucket", '<focus topic="mcp">',
             r'"topics": \[[^\]]*"mcp"[^\]]*\]', "count"),
    WalkStep("w_intake", '<focus topic="intake">',
             r'"topics": \[[^\]]*"intake"[^\]]*\]', "count"),
    WalkStep("w_auth_lite", '<focus topic="auth-lite">',
             r'"topics": \[[^\]]*"auth-lite"[^\]]*\]', "count"),
    WalkStep("w_vision", '<focus topic="vision">',
             r'"topics": \[[^\]]*"vision"[^\]]*\]', "count"),
    WalkStep("w_docker_fleet", '<focus topic="docker-fleet">',
             r'"topics": \[[^\]]*"docker-fleet"[^\]]*\]', "count"),
    WalkStep("w_economics", '<focus topic="economics">',
             r'"topics": \[[^\]]*"economics"[^\]]*\]', "count"),
    WalkStep("w_self_steal", '<focus topic="self-steal">',
             r'"topics": \[[^\]]*"self-steal"[^\]]*\]', "count"),
    WalkStep("w_verkle", '<focus topic="verkle-chain">',
             r'"topics": \[[^\]]*"verkle-chain"[^\]]*\]', "count"),
    WalkStep("w_trajectory", '<focus topic="trajectory">',
             r'"topics": \[[^\]]*"trajectory"[^\]]*\]', "count"),
    WalkStep("w_concurrency", '<focus topic="concurrency">',
             r'"topics": \[[^\]]*"concurrency"[^\]]*\]', "count"),
    WalkStep("w_newest_cards", '<local window="100">',
             r'"title": "([^"]+)"', "last"),
    WalkStep("w_overseer", '<focus topic="overseer">',
             r'"topics": \[[^\]]*"overseer"[^\]]*\]', "count"),
]

# CURRICULUM_WALK: an onboarding read in document order, Headline through
# section 10, then ONE jump to the ADDENDUM (the newest clone) — the jump is
# the honest miss the forecast must report, not hide.
CURRICULUM_WALK = [
    WalkStep("w_headline", '<focus section="Headline">',
             r"anthropics/courses \((CC-BY-NC[^)]*)\)"),
    WalkStep("w_s1_agents", '<focus section="1.">',
             r"OpenAI Agents SDK \((openai-agents-python)\)"),
    WalkStep("w_s2_rl", '<focus section="2.">',
             r"verl \(verl-project/verl, 23k★ lab standard\) — (Apache W)"),
    WalkStep("w_s3_kernels", '<focus section="3.">',
             r"RadixAttention (cache reuse)"),
    WalkStep("w_s4_evals", '<focus section="4.">',
             r"promptfoo — (MIT W)"),
    WalkStep("w_s5_economist", '<focus section="5.">',
             r"## 5\. (ECONOMIST / COST)"),
    WalkStep("w_s6_data", '<focus section="6.">',
             r"mlabonne/llm-course \((\d+)k★\)"),
    WalkStep("w_s7_builder", '<focus section="7.">',
             r"LangGraph — (MIT W)"),
    WalkStep("w_s8_embodied", '<focus section="8.">',
             r"LeRobot — (Apache W)"),
    WalkStep("w_s9_security", '<focus section="9.">',
             r"OWASP LLM Top 10 — (CC-BY-SA)"),
    WalkStep("w_s10_handbooks", '<focus section="10.">',
             r"ms-genai-beginners \((21 lessons, 119k★)\)"),
    WalkStep("w_addendum_jump", '<focus section="ADDENDUM">',
             r"Cloned to corpus/library/([a-z0-9-]+)"),
]


def build_topic_adjacency(table: Table) -> dict[str, set[str]]:
    """topic -> topics seen with it, from the cards' own topic lists: every
    card contributes a clique over its tags, and consecutive cards also link
    their tag sets (the "between consecutive cards" reading). Build-time
    metadata only — the deterministic stand-in for the learned head."""
    adj: dict[str, set[str]] = {}
    prev: set[str] = set()
    for b in table.blocks:
        tags = {t.lower() for t in b.tags}
        if not tags:
            prev = tags
            continue
        for t in tags:
            adj.setdefault(t, set()).update(tags)
        if prev:
            for t in prev:
                adj.setdefault(t, set()).update(tags)
            for t in tags:
                adj.setdefault(t, set()).update(prev)
        prev = tags
    return adj


def forecast_prefetch(table: Table, cur_visible: set[int], cur_attrs: dict,
                      adjacency: dict[str, set[str]], budget: int,
                      rng: random.Random) -> set[int]:
    """The Forecast analog: predict the NEXT query's blocks. Topic docs —
    top-`budget` blocks by shared-neighbor count with the current topic's
    co-occurrence set (ties by block index). Text docs (or no-topic steps) —
    the next `budget` blocks in document order. Deterministic: `rng` exists
    only so forecast and baseline share one signature."""
    topic = (cur_attrs.get("topic") or "").lower()
    if topic and adjacency:
        nbrs = adjacency.get(topic, set())
        scored = sorted((-len(nbrs & {t.lower() for t in b.tags}), b.idx)
                        for b in table.blocks)
        return {i for _, i in scored[:budget]}
    nxt = max(cur_visible, default=-1) + 1  # document-order lookahead
    return set(range(nxt, min(nxt + budget, len(table.blocks))))


def baseline_prefetch(table: Table, cur_visible: set[int], cur_attrs: dict,
                      adjacency: dict[str, set[str]], budget: int,
                      rng: random.Random) -> set[int]:
    """F4(a) control: same walk, `budget` blocks drawn uniformly — no
    adjacency knowledge, same prefetch size. Honest by construction."""
    n = len(table.blocks)
    return set(rng.sample(range(n), min(budget, n)))


def run_walk(table: Table, walk: list[WalkStep], budget: int,
             predict) -> dict[str, Any]:
    """Serve a scripted walk under a prefetch policy. Serving order is
    SparDA's: step k's predict runs at the END of step k; step 0 is a cold
    start (empty buffer) and counts its miss honestly. Serving never leaves
    the declaration mask — the invariant below is the never-silent guard."""
    ggot, gbytes = read_visible(table, plan_visible(table, Span("global",
                                                                {}, 0, 0)))
    gtext = b"".join(ggot[i] for i in sorted(ggot)).decode("utf-8",
                                                           errors="replace")
    adjacency = build_topic_adjacency(table)
    rng = random.Random(BASELINE_SEED)
    prefetch: dict[int, bytes] = {}
    rows, misses = [], []
    tot = {"fbytes": 0, "fbbytes": 0, "pfbytes": 0, "true_bytes": 0,
           "hits": 0, "blocks": 0}
    for step in walk:
        spans = parse_declarations(step.decl + " ")
        span = spans[0] if spans else Span("global", {}, 0, 0)
        visible = plan_visible(table, span)
        hit_ids = visible & prefetch.keys()
        miss_ids = sorted(visible - prefetch.keys())
        got = {i: prefetch[i] for i in hit_ids}
        fb_bytes = 0
        with open(table.doc, "rb") as f:  # the on-demand fallback path
            for i in miss_ids:
                b = table.blocks[i]
                f.seek(b.start)
                got[i] = f.read(b.end - b.start)
                fb_bytes += b.end - b.start
        text = b"".join(got[i] for i in sorted(got)).decode("utf-8",
                                                            errors="replace")
        if step.kind == "count":
            ans, gans = (extract("count", step.needle, text),
                         extract("count", step.needle, gtext))
        elif step.kind == "last":
            ans, gans = extract_last(step.needle, text), \
                extract_last(step.needle, gtext)
        else:
            ans, gans = (extract("find", step.needle, text),
                         extract("find", step.needle, gtext))
        hit_bytes = sum(table.blocks[i].end - table.blocks[i].start
                        for i in hit_ids)
        served = hit_bytes + fb_bytes
        assert served == sum(table.blocks[i].end - table.blocks[i].start
                             for i in visible)  # mask invariant: no silent serve
        if miss_ids:
            misses.append((step.qid, len(miss_ids), fb_bytes))
        tot["fbytes"] += hit_bytes
        tot["fbbytes"] += fb_bytes
        tot["true_bytes"] += served
        tot["hits"] += len(hit_ids)
        tot["blocks"] += len(visible)
        rows.append({"qid": step.qid, "blocks": len(visible),
                     "hits": len(hit_ids), "misses": len(miss_ids),
                     "hit_bytes": hit_bytes, "fallback_bytes": fb_bytes,
                     "answer": ans, "global_answer": gans,
                     "intact": ans == gans, "prefetch_bytes": 0})
        # end of step k: predict + prefetch for step k+1 (real reads, counted)
        pf = predict(table, visible, span.attrs, adjacency, budget, rng)
        pf_bytes = 0
        buf: dict[int, bytes] = {}
        with open(table.doc, "rb") as f:
            for i in sorted(pf):
                b = table.blocks[i]
                f.seek(b.start)
                buf[i] = f.read(b.end - b.start)
                pf_bytes += b.end - b.start
        prefetch = buf
        rows[-1]["prefetch_bytes"] = pf_bytes
        tot["pfbytes"] += pf_bytes
    tot["global_bytes"] = gbytes * len(walk)
    tot["hit_rate"] = (100.0 * tot["hits"] / tot["blocks"]) \
        if tot["blocks"] else 0.0
    tot["rows"], tot["misses"] = rows, misses
    return tot


def forecast_demo() -> bool:
    """FORECAST falsifiers over both real artifacts. Prints the walk tables
    and returns overall PASS/FAIL. Walks and budgets were chosen BEFORE
    measurement (see WALKS above) — numbers land as they land, pass or fail.
    No LLM, no writes — bytes in, verdicts out."""
    ok = True
    for name, doc, walk, budget in (
            ("TOPIC_INDEX", "watch/topic_index.json", TOPIC_WALK,
             FORECAST_TOPIC_BUDGET),
            ("CURRICULUM", "corpus/CURRICULUM.md", CURRICULUM_WALK,
             FORECAST_DOC_LOOKAHEAD)):
        table = build_table(doc)
        fc = run_walk(table, walk, budget, forecast_prefetch)
        bl = run_walk(table, walk, budget, baseline_prefetch)
        print(f"\n=== {name} — FORECAST walk ({len(walk)} queries, budget "
              f"{budget} blocks, seed {BASELINE_SEED}, "
              f"{len(table.blocks)} blocks total) ===")
        for r in fc["rows"]:
            print(f"  {r['qid']:18} blocks {r['blocks']:4} hit {r['hits']:3} "
                  f"miss {r['misses']:3}  served {r['hit_bytes']:6}B+"
                  f"{r['fallback_bytes']:6}B  pf {r['prefetch_bytes']:6}B  "
                  f"-> {str(r['answer'])[:32]!r} "
                  f"[{'intact' if r['intact'] else 'DRIFT'}]")
        if fc["misses"]:
            print("  misses (fallback cost, never silent): " + "; ".join(
                f"{q}:{c}blk/{b}B" for q, c, b in fc["misses"]))
        integ = all(r["intact"] for r in fc["rows"]) and \
            all(r["intact"] for r in bl["rows"])
        base = 100.0 * bl["hits"] / bl["blocks"] if bl["blocks"] else 0.0
        ratio = fc["hit_rate"] / base if base else float("inf")
        attended = fc["fbytes"] + fc["fbbytes"]
        cut = 100.0 * (1 - attended / fc["global_bytes"])
        traffic = fc["fbbytes"] + fc["pfbytes"]  # real disk traffic, forecast
        fa = ratio >= 2.0
        fb = cut >= 30.0
        fv = integ and bool(fc["misses"]) == (fc["fbbytes"] > 0)
        print(f"  walk integrity (served answer == GLOBAL answer, both "
              f"policies): {'PASS' if integ else 'FAIL'}")
        print(f"F4(a) hit-rate >= 2x uniform baseline: "
              f"{'PASS' if fa else 'FAIL'} — forecast {fc['hit_rate']:.1f}% "
              f"({fc['hits']}/{fc['blocks']} block-visits) vs baseline "
              f"{base:.1f}% ({bl['hits']}/{bl['blocks']}) = {ratio:.2f}x")
        print(f"F4(b) attended cut vs GLOBAL >= 30%: "
              f"{'PASS' if fb else 'FAIL'} — {attended}B attended vs "
              f"{fc['global_bytes']}B GLOBAL = {cut:.1f}% cut "
              f"(plain FOCUS, same walk, no forecast: {fc['true_bytes']}B "
              f"— the mask is unchanged; the forecast changes who pays, "
              f"not what is read)")
        print(f"F4(c) every miss reported + mask invariant: "
              f"{'PASS' if fv else 'FAIL'} — {len(fc['misses'])} misses, "
              f"fallback {fc['fbbytes']}B; disk traffic incl. prefetch "
              f"{traffic}B vs no-forecast {fc['true_bytes']}B "
              f"(prefetch {'saves' if traffic < fc['true_bytes'] else 'costs'} "
              f"{abs(fc['true_bytes'] - traffic)}B real reads)")
        ok &= fa and fb and fv
    print(f"\nFORECAST OVERALL: {'PASS' if ok else 'FAIL'} — byte-proxy "
          f"numbers on fleet loads; SparDA's 1.7x decode speedup is the "
          f"paper's kernel number, not ours")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["demo", "view", "forecast"])
    ap.add_argument("--doc", default="corpus/CURRICULUM.md")
    ap.add_argument("--decl", default="")
    ap.add_argument("--block-bytes", type=int, default=BLOCK_BYTES)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    if args.cmd == "demo":
        sys.exit(0 if demo() else 1)
    if args.cmd == "forecast":
        sys.exit(0 if forecast_demo() else 1)
    table = build_table(args.doc, args.block_bytes)
    spans = parse_declarations(args.decl) or [Span("global", {}, 0, 0)]
    print(f"{Path(table.doc).name}: {len(table.blocks)} blocks, "
          f"total {table.total_bytes}B, build cost {table.build_bytes}B (once)")
    for b in table.blocks:
        print(f"  #{b.idx:3} [{b.start:7},{b.end:7}) sha:{b.sha} "
              f"tags={b.tags[:3]}")
    for s in spans:
        vis = plan_visible(table, s)
        _, total = read_visible(table, vis)
        print(f"  {s.mode} {s.attrs or ''}: {len(vis)}/{len(table.blocks)} "
              f"blocks, {total}B attended from disk "
              f"({100 * (1 - total / table.total_bytes):.1f}% cut)")


if __name__ == "__main__":
    main()
