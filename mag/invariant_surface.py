#!/usr/bin/env python3
"""invariant_surface.py — surface the corpus's invariant information (v2, deterministic)

The operator's order: go through existing research + memory and surface the
INVARIANT information clearly and concisely — max fidelity/speed, rightsized
on the task. v0 was the rightsized floor: repetition-only ranking (duplication
is emphasis). v2 adds the scite steal (watch/inbox/steal_research_pipeline/
BOT_B_claims.md): scite's whole product is classifying DISAGREEMENT, and v0
had no disagreement detector, only accumulation. Percolator counts repeats
but never refutations — v2 binds the percolator-style repeat count as
agreement_count and adds a REFUTATION column on top.

v2 semantics (one regex pass, stdlib only, no model in the loop):
  agreement_count  = cross-file repetitions of a line (v0's count; duplication
                     is emphasis — unchanged)
  refutation_count = sum over distinct NEGATIVE lines (carrying a negation
                     marker: not/never/isn't/don't/wrong/false/disputed/...)
                     that reference the SAME SUBJECT (shared salient tokens,
                     >=2 shared and >=40% of the smaller side) whose subject
                     intersects a POSITIVE line. A contradiction repeated is
                     emphasis too, so the negative line's own repetition count
                     rides along. Direction: negative refutes positive; laws
                     like "never retry" refute positive "retry with backoff".
  net_score        = agreement_count - refutation_count (rank key; may go
                     negative — a negative net is a disputed claim, visible)
  CONTROVERTED     = lines with real agreement (>=2) AND >=1 refutation —
                     the live debates, ranked by how hard they are contested.

Fidelity = every surfaced line keeps its source pointer. Speed = one regex
pass + an inverted-index subject match, no reads beyond the corpus. The sheet
is the floor that never hallucinates; the LLM-grade distillation still rides
the deepseek pad-out lane later.

stdib only. Writes watch/INVARIANT_SHEET_V2.md (v0's INVARIANT_SHEET.md is
left frozen as the repetition-only baseline it compares against).
"""
import hashlib, re, sys, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "watch" / "INVARIANT_SHEET_V2.md"
MEMORY_DIR = ROOT / "memory"
WATCH_DIR = ROOT / "watch"
CAPS = {"memory": 400, "watch": 200}

VERDICT = re.compile(r"\b(SUPPORTED|DISPUTED|UNPROVEN|CONFIRMED|PRIMARY-READ)\b")
LAW = re.compile(r"\b(law\s?\d+|THE LAW|standing law|never\s+(start|retry|edit|paste|promise)|always\s+)\b", re.I)
FALSIF = re.compile(r"\bfalsif", re.I)
MEASURE = re.compile(r"(\d{1,3}(?:\.\d+)?%|\d+(?:\.\d+)?x\b|corr(eleration)?\s*=?\s*0?\.\d{2,})|(\b\d{2,}[,\d]*\s+(files|leaves|knots|tokens|bytes)\b)", re.I)

# v2: negation markers — a line carrying one of these is a NEGATIVE line.
NEG_MARK = re.compile(
    r"\b(not|never|isn.t|don.t|doesn.t|won.t|can.t|cannot|wrong|false|"
    r"disputed|refuted|fails?|without|no)\b", re.I)

MIN_LEN, MAX_LEN = 40, 400

STOP = set("""the and for with that this from are was were has have had its their there then than
when what which will would should could into onto under over about after before between through
during also been being both each more most other some such only same just like very can may might
must shall does did doing done dont doesnt isnt wont cant cannot not never no none nor but if
while because until against above below again further once here all any out up down off own too
aint arent couldnt didnt hadnt hasnt havent mightnt mustnt neednt shant shouldnt wasnt werent
wouldnt your you our we they them their theirs she he his her him us me my mine ours yours every
another per via etc eg ie card cards line lines file files folder sheet table section note notes
draft page pages data record records report rows row column corpus corpus domain value values
claim claims state status first second third next last then thus hence also based using used use""".split())


def files_under(base, cap, exclude=()):
    if not base.exists():
        return []
    fs = [p for p in base.rglob("*.md") if p.name not in exclude]
    fs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return fs[:cap]


def bucket_of(line: str):
    if VERDICT.search(line):
        return "VERDICT"
    if FALSIF.search(line):
        return "FALSIFIER"
    if LAW.search(line):
        return "LAW"
    if MEASURE.search(line):
        return "MEASURED"
    return None


def clean(line: str) -> str:
    s = line.strip().lstrip("-*#> ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower())[:160]


def subject_of(s: str):
    """Salient subject tokens: words >=4 chars, stopwords + negation markers out."""
    toks = {t for t in re.findall(r"[a-z][a-z0-9/+_-]{3,}", s.lower())
            if t not in STOP and not NEG_MARK.fullmatch(t)}
    return frozenset(toks)


def contradicts(subj_pos, subj_neg):
    """Same subject = >=2 shared salient tokens AND >=40% of the smaller side."""
    shared = len(subj_pos & subj_neg)
    smaller = min(len(subj_pos), len(subj_neg)) or 1
    return shared >= 2 and shared / smaller >= 0.4


def main():
    t0 = time.time()
    corpus = [(p, "memory") for p in files_under(MEMORY_DIR, CAPS["memory"], exclude={"MEMORY.md"})] \
           + [(p, "watch") for p in files_under(WATCH_DIR, CAPS["watch"], exclude={OUT.name})]

    seen = {}          # norm_key -> rec {text,bucket,count,files,mtime,neg,subj}
    for p, lane in corpus:
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        mt = p.stat().st_mtime
        for raw in lines:
            s = clean(raw)
            if not (MIN_LEN <= len(s) <= MAX_LEN):
                continue
            b = bucket_of(s)
            if not b:
                continue
            k = hashlib.sha256(norm(s).encode()).hexdigest()[:12]
            rec = seen.get(k)
            if rec is None:
                seen[k] = {"text": s, "bucket": b, "count": 1,
                           "files": [str(p.relative_to(ROOT))], "mtime": mt,
                           "neg": bool(NEG_MARK.search(s)), "subj": subject_of(s)}
            else:
                rec["count"] += 1
                rel = str(p.relative_to(ROOT))
                if rel not in rec["files"]:
                    rec["files"].append(rel)

    recs = list(seen.values())
    pos = [r for r in recs if not r["neg"]]
    neg = [r for r in recs if r["neg"]]

    # refutations: inverted index token -> negative recs; each match scores the
    # negative line's repetition count against the positive line.
    inv = defaultdict(list)
    by_id = {}
    for n in neg:
        by_id[id(n)] = n
        for t in n["subj"]:
            inv[t].append(n)
    for r in pos:
        hits = defaultdict(int)
        for t in r["subj"]:
            for n in inv.get(t, ()):
                hits[id(n)] += 1
        refs = 0
        for nid, shared in hits.items():
            n = by_id[nid]
            if contradicts(r["subj"], n["subj"]):
                refs += n["count"]
        r["refutations"] = refs
    for n in neg:
        n["refutations"] = 0
    for r in recs:
        r["net"] = r["count"] - r["refutations"]

    buckets = defaultdict(list)
    for rec in recs:
        buckets[rec["bucket"]].append(rec)
    # v0 baseline rank (repetition-only) for the movement comparison
    old_rank = {}
    for b in buckets:
        order = sorted(buckets[b], key=lambda r: (-r["count"], -r["mtime"]))
        old_rank[b] = {id(r): i for i, r in enumerate(order)}
        buckets[b].sort(key=lambda r: (-r["net"], -r["mtime"]))

    controverted = [r for r in recs if r["refutations"] >= 1 and r["count"] >= 2]
    controverted.sort(key=lambda r: (-min(r["count"], r["refutations"] + 1), -r["refutations"]))

    lines_out = ["# INVARIANT SHEET V2 — corpus floor + refutation column (scite steal)", "",
                 f"_generated {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())} · "
                 f"{len(corpus)} files walked · {len(recs)} unique invariant lines · "
                 f"negative lines: {len(neg)} · contradicted: {sum(1 for r in pos if r['refutations'])} · "
                 f"{time.time()-t0:.1f}s · every line keeps its source pointer_", "",
                 "_rank = net_score = agreement_count − refutation_count. agreement = cross-file "
                 "repetition (percolator semantics, duplication is emphasis). refutation = a "
                 "negation-marker line on the same subject counts AGAINST the positive line "
                 "(scite contrasting-citation steal, watch/inbox/steal_research_pipeline/BOT_B_claims.md). "
                 "v0 ranked by raw repetition and never counted disagreement._", ""]

    take = {"LAW": 20, "VERDICT": 20, "FALSIFIER": 12, "MEASURED": 20}
    for b in ("LAW", "VERDICT", "FALSIFIER", "MEASURED"):
        rows = buckets.get(b, [])[:take[b]]
        lines_out += [f"## {b} ({len(buckets.get(b, []))} unique, ranked by net_score)", ""]
        for r in rows:
            fp = r["files"][0]
            more = f" +{len(r['files'])-1} files" if len(r["files"]) > 1 else ""
            delta = ""
            oi = old_rank[b].get(id(r))
            if oi is not None:
                d = oi - buckets[b].index(r)
                if abs(d) >= 2:
                    delta = f" ↑{d}" if d > 0 else f" ↓{-d}"
            lines_out.append(
                f"- [net={r['net']:+d} · agree={r['count']} · refute={r['refutations']}{delta}] "
                f"{r['text'][:260]} _( {fp}{more} )_")
        lines_out.append("")

    lines_out += [f"## CONTROVERTED ({len(controverted)} lines with agreement AND refutation — the live debates)", ""]
    if not controverted:
        lines_out += ["_none: no positive invariant line shares a subject with a negation line._", ""]
    for r in controverted[:15]:
        fp = r["files"][0]
        lines_out.append(f"- [agree={r['count']} vs refute={r['refutations']} · net={r['net']:+d}] "
                         f"{r['text'][:260]} _( {fp} )_")
    lines_out.append("")

    lines_out += ["## MOVEMENT vs v0 (repetition-only rank → net_score rank)", ""]
    movers = []
    for b in ("LAW", "VERDICT", "FALSIFIER", "MEASURED"):
        for i, r in enumerate(buckets.get(b, [])[:20]):
            oi = old_rank[b].get(id(r))
            if oi is not None and abs(oi - i) >= 2:
                movers.append((oi - i, b, oi, i, r))
    movers.sort(key=lambda m: -abs(m[0]))
    if not movers:
        lines_out += ["_no rank moved by 2+ places — net_score agrees with raw repetition here._", ""]
    for d, b, oi, ni, r in movers[:10]:
        arrow = "UP" if d > 0 else "DOWN"
        lines_out.append(f"- {arrow} {abs(d)} places ({b} #{oi+1}→#{ni+1}) [net={r['net']:+d} · "
                         f"agree={r['count']} · refute={r['refutations']}] {r['text'][:180]}")
    lines_out.append("")

    OUT.write_text("\n".join(lines_out), encoding="utf-8")
    print(f"INVARIANT SHEET V2 -> {OUT.relative_to(ROOT)}")
    for b in ("LAW", "VERDICT", "FALSIFIER", "MEASURED"):
        print(f"  {b:9s} unique={len(buckets.get(b, [])):4d} surfaced={min(len(buckets.get(b, [])), take[b])}")
    print(f"  negative lines: {len(neg)} | positives with >=1 refutation: "
          f"{sum(1 for r in pos if r['refutations'])} | CONTROVERTED: {len(controverted)}")
    print("  TOP CONTROVERTED:")
    for r in controverted[:5]:
        print(f"    [a={r['count']} r={r['refutations']}] {r['text'][:150]}")
    print("  TOP MOVERS:")
    for d, b, oi, ni, r in movers[:5]:
        print(f"    {'UP' if d>0 else 'DOWN'} {abs(d)} ({b} #{oi+1}->#{ni+1}) {r['text'][:120]}")
    print(f"  walked {len(corpus)} files in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
