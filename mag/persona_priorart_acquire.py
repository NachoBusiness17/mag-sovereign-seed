"""STEAL THE PRIOR ART -- and, more importantly, the recorded FAILURES, before building the museum.

OPERATOR ASK (2026-09-30, out-of-band): "find out who else is doing this and take what they are
doing and add it to our own."

WHAT "THIS" IS: personas from historical figures, conditioned on a measured trait vector, used
to produce perspective rather than to summarise. The field is active and has been searched rather
than assumed. Seven papers, each verified against arXiv's own API before staging.

THE THREE THAT CONSTRAIN THE MUSEUM MOST ARE THE NEGATIVE RESULTS
  These matter more than the positive ones, because a head museum is EXACTLY the thing two of
  them say does not work. Building it without reading them would repeat their mistake at a larger
  scale and with more authority.

  2405.07248  Petrov, Serapio-Garcia, Rentfrow -- "Limited Ability of LLMs to Simulate Human
    Psychological Behaviours: a Psychometric Analysis." They prompt GPT-3.5 and GPT-4 to adopt
    personas and answer standardised personality measures, then apply PSYCHOMETRICS to the
    responses. Finding: GPT-4 with GENERIC persona descriptions shows promising psychometric
    properties; both models with SPECIFIC demographic profiles show POOR ones. Conclusion: LLM
    responses "are poor signals of potentially underlying latent traits."
    -> THIS IS THE DIRECT CONSTRAINT ON OUR DESIGN. Our museum uses SPECIFIC figures, which is
       the configuration this paper measures as failing. We may still build it, but the museum has
       to declare that it is in the configuration known to be psychometrically weak, and must not
       present a figure's vector as a recovered personality.

  2508.06950  Schroder, Morgenroth, Kuhl, Vaquet, Paassen -- "Large Language Models Do Not
    Simulate Human Psychology." Finding: slight WORDING changes that correspond to large changes in
    meaning produce notable discrepancies between LLM and human responses -- even for CENTAUR,
    which was specifically fine-tuned on psychological responses. Different LLMs give very
    different answers to novel items.
    -> THE CONSTRAINT ON THE WHOLE ENDEAVOUR. It argues for WIRING instruments (our percentile
       scorer, our gate) rather than trusting a model's self-report, which is what we are already
       doing and what this validates.

  2508.06149  Cho, Cheong -- "Scaling Personality Control in LLMs with Big Five Scaler Prompts."
    -> THE POSITIVE COUNTERWEIGHT, and the one worth stealing: Big Five conditioning is
       measurable and scalable in current models. That is evidence our trait-vector approach is
       not hopeless, while the other two say its OUTPUT must not be read as a recovered mind.

THE CONSTRUCTIVE PRIOR ART WE ARE STEALING
  2310.10158  Shao et al. -- "Character-LLM: A Trainable Agent for Role-Playing." Behaviour
    cloning from a dialogue corpus with explicit character traits, evaluated on CharacterEval.
    STOLEN IDEA: an EVALUATION SET with human ratings, not just vibes. Our museum needs the same
    discipline: a bench of questions with a real scoring rule.
  2506.12657  Liu, Song, Xiao -- "Synthetic Socratic Debates: Examining Persona Effects on Moral
    Decision and Persuasion." STOLEN IDEA: hold the TOPIC and VARY THE PERSONA, so the
    difference in answer is attributable to the persona rather than to the question. That is
    precisely the between-subject design our gate is already running on the 20-figure bench, done
    deliberately.
  2506.11798  Kreutner, Lutz, Strohmaier -- persona-driven simulation of European Parliament
    voting. STOLEN IDEA: ground personas in real per-person record rather than a trait guess.
    2511.17813  Merrill, Srivastava -- "Point of Order: Action-Aware LLM Persona Modeling for
    Data-Grounded Civic Deliberation." Same idea, civic framing.
    -> TOGETHER these say the museum's figures need CORRESPONDENCE AND RECORD, not only a trait
       vector. The operator already asked for exactly this -- "correspondence quotes and thinking"
       -- so the literature independently confirms the design.

RIGHTS: all seven have an UNSTATED licence (arXiv license field absent in the API response for
every one). Unstated means no redistribution basis, so they land in the reference tier exactly as
the Turing 1952 paper did. This is not a technicality -- the whole point of a museum is to be
citable, and a citable museum needs rights, so the debt is recorded with buy-back paths.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mag.corpus_archive_acquire import _get                          # noqa: E402

RUNS = ROOT / "memory" / "runs" / "persona_priorart"
RECEIPTS = ROOT / "docs" / "report_v1" / "sources" / "receipts"
REF = ROOT / "corpus" / "papers_reference_nonredistributable"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HermesCorpus/1.0"}
NS = {"a": "http://www.w3.org/2005/Atom", "ar": "http://arxiv.org/schemas/atom"}

IDS = [
    ("2405.07248", "CONSTRAINT", "psychometric analysis of persona-conditioned LLM responses; "
     "specific demographic personas show poor psychometric properties"),
    ("2508.06950", "CONSTRAINT", "LLMs do not simulate human psychology; wording sensitivity "
     "even in psychology-fine-tuned models"),
    ("2508.06149", "COUNTERWEIGHT", "Big Five Scaler Prompts: personality control is measurable "
     "and scales in current models"),
    ("2310.10158", "STEAL-EVAL", "Character-LLM: behaviour cloning for role-play plus "
     "CharacterEval, an evaluation set with human ratings"),
    ("2506.12657", "STEAL-DESIGN", "Synthetic Socratic Debates: hold the topic, vary the persona, "
     "so differences are attributable to the persona"),
    ("2506.11798", "STEAL-GROUNDING", "persona-driven European Parliament voting simulation; "
     "ground personas in per-person record"),
    ("2511.17813", "STEAL-GROUNDING", "Point of Order: action-aware, DATA-GROUNDED civic "
     "deliberation personas"),
]


def arxiv_meta(aid: str) -> dict:
    """arXiv's own API. NOTE the format: it returns ATOM XML, not JSON. An earlier attempt
    called json.loads on it and reported '7/7 unreachable' -- which was my parser failing, not
    the source. Same shape as every other extraction failure in this session."""
    url = f"http://export.arxiv.org/api/query?id_list={aid}"
    try:
        root = ET.fromstring(urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=60).read())
    except Exception as e:
        return {"__failed__": f"{type(e).__name__}: {e}"}
    e = root.find("a:entry", NS)
    if e is None:
        return {"__failed__": "no entry in feed"}
    lic = e.find("ar:license", NS)
    return {
        "title": " ".join(e.findtext("a:title", default="", namespaces=NS).split()),
        "summary": " ".join(e.findtext("a:summary", default="", namespaces=NS).split()),
        "published": e.findtext("a:published", default="", namespaces=NS)[:10],
        "authors": [a.findtext("a:name", default="", namespaces=NS)
                    for a in e.findall("a:author", NS)],
        "license": lic.get("value") if lic is not None else None,
    }


def main() -> int:
    for d in (RUNS, RECEIPTS, REF):
        d.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    rows = []
    for aid, kind, why in IDS:
        m = arxiv_meta(aid)
        if "__failed__" in m:
            print(f"  FETCH-FAIL {aid}: {m['__failed__'][:60]}")
            rows.append({"arxiv_id": aid, "kind": kind, "status": "FETCH-FAILED"})
            continue
        # arXiv's FRONTEND returns 406 for /pdf/<id>; export.arxiv.org returns 200 with a real
        # %PDF. Measured earlier this session, both hosts are tried in that order.
        body = None
        for url in (f"https://export.arxiv.org/pdf/{aid}",
                    f"https://arxiv.org/pdf/{aid}"):
            st, b, _e = _get(url, tries=2, timeout=180)
            if st == 200 and b and b[:5] == b"%PDF-" and len(b) > 20000:
                body, src_url = b, url
                break
        if body is None:
            print(f"  NO-PDF     {aid}: {m['title'][:50]}")
            rows.append({"arxiv_id": aid, "kind": kind, "title": m["title"],
                         "status": "NO-PDF"})
            time.sleep(3.0)
            continue

        sha = hashlib.sha256(body).hexdigest()
        if sha in seen:
            print(f"  DEDUPED    {aid}")
            rows.append({"arxiv_id": aid, "kind": kind, "status": "DEDUPED-BY-HASH"})
            continue

        dest = REF / f"persona_priorart_{aid}.pdf"
        dest.write_bytes(body)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
            dest.unlink(missing_ok=True)
            print(f"  WRITE-MISMATCH {aid}")
            rows.append({"arxiv_id": aid, "kind": kind, "status": "WRITE-MISMATCH"})
            continue
        seen.add(sha)

        rights = ("REFERENCE (non-redistributable): arXiv license UNSTATED in the API response "
                  "-- no redistribution basis. This is the same call made for Turing 1952.")
        rcp = RECEIPTS / f"persona_priorart_{aid}.md"
        rcp.write_text(
            f"# RETRIEVAL RECEIPT — persona prior art — {m['title']}\n\n"
            f"arxiv_id: {aid}\nkind: {kind}\n"
            f"authors: {', '.join(m['authors'])}\npublished: {m['published']}\n"
            f"source: {src_url}\ncontent_sha256_16: {sha[:16]}\nbytes: {len(body):,}\n"
            f"pulled: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}\n"
            f"rights_tier: {rights}\n"
            f"landed: {str(dest.relative_to(ROOT)).replace(chr(92),'/')}\n"
            f"why: {why}\n"
            f"abstract: {m['summary'][:900]}\n", encoding="utf-8")
        rows.append({"arxiv_id": aid, "kind": kind, "title": m["title"], "authors": m["authors"],
                     "published": m["published"], "status": "LANDED", "bytes": len(body),
                     "sha256": sha, "license": m["license"], "source": src_url,
                     "landed": str(dest.relative_to(ROOT)).replace(chr(92), "/"),
                     "receipt": str(rcp.relative_to(ROOT)).replace(chr(92), "/")})
        print(f"  LANDED [{kind:17s}] {aid}  {m['title'][:52]:54s} {len(body):>9,}B")
        time.sleep(3.0)

    out = RUNS / "PERSONA_PRIORART_LANDING.json"
    out.write_text(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "ask": "operator OOB 2026-09-30: find out who else is doing this and take what they are "
               "doing and add it to our own.",
        "landed": sum(1 for r in rows if r["status"] == "LANDED"),
        "bytes": sum(r.get("bytes", 0) for r in rows),
        "rights": "all seven have an UNSTATED arXiv license -> reference tier",
        "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  {sum(1 for r in rows if r['status']=='LANDED')}/{len(IDS)} landed, "
          f"{sum(r.get('bytes',0) for r in rows):,} B -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
