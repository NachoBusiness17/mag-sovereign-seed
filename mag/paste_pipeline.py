"""paste_pipeline — the research window's 72-step paste pipeline, made runnable (2026-09-13).

THE PROMISE (watch/DECK_INTERFACE_CONTEXT_20260904.md): "paste here = full 72-step
socratic treatment (sweep, falsifiers, salon, tri-state card)." The promise was never
a runnable organ — this module writes it down and wires the first steps.

Shape (L02 fold, obstacle wave): 7 macro-stages x 10 micro-steps = steps 1-70,
plus STEP 0 (the probe-before-route gate) and STEP 72 (the DISPOSITIONS write).
Per paste: `run --paste <file|url> --steps 0-2` executes what exists and marks the
rest DECLARED (SAID-NOT-BUILT) — the pipeline never pretends.

Executable today:
  step 0  GATE          probe-before-route on the wave slugs (mag.probe_route)
  step 1  INGEST-WRITE  intake scaffold card -> watch/inbox/
  step 2  MAP-TRIAGE    triage table skeleton (8-column rubric row per link)
Declared (3-70): the sweep, cite-gate, MATH/ORGAN/SPECIMEN scoring, attack lanes,
salon bench, fold — names and inputs/outputs listed; each becomes executable by
wiring an existing organ (wave runner, cite_gate, dispositions classifier).
  step 72 DISPOSITIONS  WIRED/OPEN-WIRE classification write (dispositions law).

Schema: paste_pipeline.v1
CLI: python -m mag.paste_pipeline run --paste <path|url> [--steps 0-2] [--title "..."]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# watch/ is not bind-mounted into the cage; scaffold cards land in memory/ (mounted)
# and are placed into watch/inbox/ host-side by the seat.
INBOX = ROOT / "memory" / "runs" / "paste_pipeline"
SCHEMA = "paste_pipeline.v1"

# (step, stage, name, inputs -> outputs, executable)
STEPS = [(0, "GATE", "probe-before-route on wave slugs", "slug list -> live set + PROBE_LOG", True),
         (1, "INGEST", "intake scaffold card", "paste bytes -> watch/inbox card", True),
         (2, "MAP", "triage table skeleton", "links -> rubric rows", True),
         (3, "INGEST", "fetch + quote bytes per link", "urls -> quoted digests", False),
         (4, "MAP", "genre classify (ore/noise/specimen)", "digests -> genre tags", False),
         (5, "MAP", "connect-to-corpus grep", "digests -> referent paths", False),
         (6, "MAP", "invariant hunt queries", "digests -> law-language hits", False),
         (7, "MAP", "trace the pheromone (who else posted it)", "urls -> cascade map", False),
         (8, "MAP", "freshness check on cited models/slugs", "claims -> TTL verdicts", False),
         (9, "MAP", "number-drift scan", "claims vs receipts -> drift rows", False),
         (10, "ASSERT", "cite-gate primary source", "claims -> CONFIRMED/UNPROVEN", False),
         (11, "ASSERT", "MATH score 1-10", "mechanism -> score", False),
         (12, "ASSERT", "ORGAN score 1-10", "fleet composition -> score", False),
         (13, "ASSERT", "SPECIMEN score 1-10", "record value -> score", False),
         (14, "ASSERT", "route: BUILD small | SHELF | library | doctrine | specimen", "scores -> route", False),
         (15, "ASSERT", "same-turn launch decision (launch law)", "route -> B-lane spawn", False),
         (16, "ASSERT", "falsifier per claim", "claims -> falsifiers", False),
         (17, "ASSERT", "secret scan before card", "card -> clean", False),
         (18, "ASSERT", "resemblance-to-harm pass", "card -> flag/clear", False),
         (19, "ASSERT", "rightsizing check (lane cost quote)", "plan -> cost", False),
         (20, "ASSERT", "wave width decision", "load -> width", False),
         (21, "ATTACK", "adversarial lane on the strongest claim", "claim -> attack", False),
         (22, "ATTACK", "sponsored/rumor specimen checks", "links -> SOURCE CHECK Y/N", False),
         (23, "ATTACK", "baseline qualifier hunt (tweet drops the baseline)", "claims -> baseline rows", False),
         (24, "ATTACK", "vendor-cavity disclosure", "tools -> cavity lines", False),
         (25, "ATTACK", "convergence-by-mimicry check", "derivation -> scaffold disclosure", False),
         (26, "ATTACK", "self-dispute chair", "card -> dispute", False),
         (27, "ATTACK", "false-negative hunt (what did the sweep miss)", "corpus -> misses", False),
         (28, "ATTACK", "worst-case reading of the operator's gloss", "gloss -> steelman", False),
         (29, "ATTACK", "unit-semantics audit (per what?)", "prices -> unit rows", False),
         (30, "ATTACK", "anti-resonance check (is the loop feeding itself)", "cadence -> phase check", False),
         (31, "MEASURE", "wave fire + receipts", "lanes -> receipts", False),
         (32, "MEASURE", "cache-read ratio", "receipts -> ratio", False),
         (33, "MEASURE", "cost per lane", "receipts -> $ table", False),
         (34, "MEASURE", "tri-state coverage (no untagged bullets)", "returns -> coverage", False),
         (35, "MEASURE", "falsifier run receipts", "falsifiers -> pass/fail", False),
         (36, "MEASURE", "dogfood battery where applicable", "organ -> 32/32", False),
         (37, "MEASURE", "latency/wall receipt", "wave -> seconds", False),
         (38, "MEASURE", "reroute/exception count", "gate log -> count", False),
         (39, "MEASURE", "operator-attention force spent", "actions -> minutes", False),
         (40, "MEASURE", "quotient check: movement vs force", "logs -> ratio", False),
         (41, "CORRECT", "fold: cross-lane convergence", "returns -> fold card", False),
         (42, "CORRECT", "drift rows appended (never amended)", "errors -> strata", False),
         (43, "CORRECT", "corrections owned in failure voice", "faults -> rows", False),
         (44, "CORRECT", "whiff-gate: broad claim needs broad evidence", "claims -> narrowed", False),
         (45, "CORRECT", "amend memory index", "finds -> MEMORY.md", False),
         (46, "CORRECT", "amend recipe organs", "quirks -> recipe rows", False),
         (47, "CORRECT", "demote organs without with/without delta", "organs -> demotions", False),
         (48, "CORRECT", "retire dead slugs/lanes from tables", "probe log -> tables", False),
         (49, "CORRECT", "close loops opened (inbox, holds, holds TTL)", "loops -> closed", False),
         (50, "CORRECT", "carry-owed ledger update", "owes -> ledger", False),
         (51, "CROP", "the crop: what survives, one screen", "fold -> summary", False),
         (52, "CROP", "CONVO row same turn", "card -> mesh row", False),
         (53, "CROP", "operator-readable file landed", "fold -> path", False),
         (54, "CROP", "next builds named smallest-first", "seams -> go menu", False),
         (55, "CROP", "pilot candidate named", "crop -> pilot", False),
         (56, "CROP", "doctrine deltas (did a law change?)", "finds -> law rows", False),
         (57, "CROP", "specimen tagged for the record pool", "noise -> specimen", False),
         (58, "CROP", "open questions carried to basecamp", "unknowns -> basecamp", False),
         (59, "CROP", "gratitude/attribution rows (borrow good artists)", "sources -> credits", False),
         (60, "CROP", "the one-line thesis, operator register", "all -> line", False),
         (61, "SWEEP", "re-sweep surfaces the paste touched", "paste -> surfaces", False),
         (62, "SWEEP", "second-door check (same doctrine elsewhere?)", "thesis -> doors", False),
         (63, "SWEEP", "house-native grep before new build", "need -> existing organ", False),
         (64, "SWEEP", "sacred-cow audit (steal bones, name reinterpretation)", "elders -> rows", False),
         (65, "SWEEP", "record-pool census delta", "files -> delta", False),
         (66, "SWEEP", "orphan check (cards without owners)", "cards -> owners", False),
         (67, "SWEEP", "chain health (knots moving, root stable)", "chain -> health", False),
         (68, "SWEEP", "quota/pace guard", "burn -> pace", False),
         (69, "SWEEP", "operator surface check (his eyes, his files)", "output -> his surface", False),
         (70, "SWEEP", "silence valid: declare the null entry", "nothing -> line", False),
         (72, "DISPOSITIONS", "WIRED/OPEN-WIRE classification write", "card -> dispositions.json", False)]

STAGE_ORDER = ["GATE", "INGEST", "MAP", "ASSERT", "ATTACK", "MEASURE", "CORRECT", "CROP", "SWEEP", "DISPOSITIONS"]


def _slugify(text: str) -> str:
    keep = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return keep[:48] or "paste"


URL_RE = re.compile(r"https?://[^\s)>\]\"']+")


def _canonical_footer(text: str) -> list[str]:
    """B7 (2026-09-16): canonical-ledger check on links about to be filed.

    Every URL goes through link_library.check_url(), the B2-27 single door
    (host-safety guard + canonicalize + known-canonicals lookup), instead of
    re-implementing the lookup inline (B2-124, 2026-09-26: the inline
    canonicalize + known_canonicals().get copy had already drifted once, skipping
    the door's validate_host_safety guard; cause named per the fix-comment law).
    The card gets a footer annotating the canonical form and whether this exact
    canonical is already on file (links-duplicate-of = first URL seen, else empty).
    Annotate, never gate: any door failure degrades to an '(unresolved)' line —
    a ledger outage can never block intake.
    """
    urls: list[str] = []
    for m in URL_RE.finditer(text):
        url = m.group(0).rstrip(".,;:!?'\"]>")
        if url not in urls:
            urls.append(url)
    if not urls:
        return []
    out = ["## Link canonical check (link_library — annotate, never gate)"]
    try:
        from mag import link_library
    except Exception as e:
        out.append(f"- ledger unavailable ({type(e).__name__}: {str(e)[:80]}) — links unannotated")
        out.append("")
        return out
    for url in urls:
        try:
            verdict = link_library.check_url(url)
            entry = verdict.get("first_entry")
            first = entry.get("url", "") if isinstance(entry, dict) else ""
        except Exception as e:
            out.append(f"- {url}")
            out.append(f"  links-canonical: (unresolved: {type(e).__name__}: {str(e)[:80]})")
            out.append("  links-duplicate-of: ")
            continue
        out.append(f"- {url}")
        out.append(f"  links-canonical: {verdict.get('canonical', '')}")
        out.append(f"  links-duplicate-of: {first}")
    out.append("")
    return out


def run(paste: str, steps: str, title: str, key_env: str = "") -> int:
    paste_path = Path(paste)
    if paste_path.is_file():
        paste_ref = str(paste_path)
        digest = paste_path.read_text(encoding="utf-8", errors="replace")[:2000]
    else:
        paste_ref = paste
        digest = f"(URL paste — bytes fetched by the web-reader lane, not this step: {paste})"
    ts = datetime.now(timezone.utc)
    stamp = ts.strftime("%Y%m%d")
    base = title or f"PASTE_{stamp}"
    card_path = INBOX / f"{base}_{_slugify(paste_ref)[:40]}.md"

    lo, hi = (map(int, steps.split("-")) if "-" in steps else (int(steps), int(steps)))
    gate_result, triage_rows = None, []
    executed, declared = [], []
    for step, stage, name, io, exe in STEPS:
        if lo <= step <= hi:
            if step == 0 and exe:
                gate_result = _run_gate(key_env)
                if gate_result is not None:
                    executed.append((step, stage, name, io))
                else:
                    declared.append((step, stage, name, io + " [needs --key-env]"))
            elif step == 2 and exe:
                triage_rows = [ln.strip() for ln in digest.splitlines() if "http" in ln][:12]
                executed.append((step, stage, name, io))
            elif exe:
                executed.append((step, stage, name, io))
            else:
                declared.append((step, stage, name, io))

    lines = [f"# {base} — intake scaffold (paste_pipeline.v1)",
             f"- pasted: {paste_ref}",
             f"- steps executed: {[s[0] for s in executed]}",
             f"- steps declared (SAID-NOT-BUILT): {[s[0] for s in declared]}",
             f"- ts: {ts.isoformat()}",
             ""]
    if gate_result is not None:
        lines += ["## Step 0 — probe-before-route gate",
                  "```json", json.dumps(gate_result, indent=2), "```", ""]
    if triage_rows:
        lines += ["## Step 2 — triage table skeleton (rows found in paste)",
                  "| # | link |", "|---|---|"] + [f"| {i+1} | {ln} |" for i, ln in enumerate(triage_rows)] + [""]
    lines += ["## Paste digest (first 2000 chars, verbatim)",
              "```", digest, "```", "",
              "## Tri-state discipline",
              "- bytes fetched: see step 3 (declare until wired)",
              "- every claim gets [Supported/Unproven] before any route", ""]
    lines += _canonical_footer(digest)
    INBOX.mkdir(parents=True, exist_ok=True)
    card_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"PASTE PIPELINE steps {lo}-{hi}")
    for step, stage, name, io in executed:
        print(f"  step {step:2d} [{stage}] EXECUTED: {name} ({io})")
    for step, stage, name, io in declared:
        print(f"  step {step:2d} [{stage}] declared: {name} — SAID-NOT-BUILT, wire to run")
    print(f"card: {card_path}")
    return 0


WAVE_SLUGS = ["inclusionai/ling-3.0-flash-sante:free", "inclusionai/ling-3.0-flash-fin:free",
              "meituan/longcat-2.0:free", "poolside/laguna-s-2.1:free",
              "stepfun/step-3.7-flash:free", "upstage/solar-pro4:free"]
NOUS_URL = "https://inference-api.nousresearch.com/v1/chat/completions"


def _run_gate(key_env: str):
    """Step 0: actually run the probe gate on the wave slugs (import, never print keys)."""
    if not key_env:
        return None
    try:
        import os
        from mag import probe_route
        key = os.environ.get(key_env, "")
        if not key:
            return None
        result = probe_route.route(WAVE_SLUGS, NOUS_URL, key_env)
        return result
    except Exception as e:
        return {"gate_error": f"{type(e).__name__}: {str(e)[:140]}"}


def main() -> int:
    ap = argparse.ArgumentParser(prog="paste_pipeline")
    ap.add_argument("action", choices=["run", "table"])
    ap.add_argument("--paste", default="")
    ap.add_argument("--steps", default="0-2")
    ap.add_argument("--title", default="")
    ap.add_argument("--key-env", default="")
    args = ap.parse_args()
    if args.action == "table":
        for step, stage, name, io, exe in STEPS:
            print(f"{step:3d} [{stage:12s}] {'EXEC' if exe else 'decl'} {name} :: {io}")
        return 0
    if not args.paste:
        print("--paste required")
        return 2
    return run(args.paste, args.steps, args.title, args.key_env)


if __name__ == "__main__":
    raise SystemExit(main())
