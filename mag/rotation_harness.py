"""ROTATION HARNESS — the vision pipeline's falsifier #1, as code.

Spec (watch/SELF_STEAL_VISION_PIPELINE_20260905.md): same input batch, different
seat + time + input order -> cluster STRUCTURE invariant (count +/-1, key
citations identical); prose free to vary. If rotation fails without a named
cause, the standing-wave reading DIES and the card gets stamped so.

Usage:
    python -m mag.rotation_harness run corpus/frontier_thinking/FT_XBATCH_20260905.jsonl

Reference (the proof run, watch/INTAKE_XBATCH_20260905.md): 7 clusters, key
receipts = the load-bearing primary sources the original interpret attached.

$0: free lanes only, DORMANT-GATED (B2-133): groq rides; cerebras is dormant in
configs/providers.yaml (B2-36, card-gated trial) and returns on operator GO.
READ/FILTER steps are NOT re-run: the
capture is the frozen input; only INTERPRET varies (seat + order). Deterministic
shuffles, honest down-reporting, no retries. Stdlib only.
"""
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANES = [("groq", None), ("cerebras", "gpt-oss-120b")]
# B2-133 DORMANT GATE (2026-09-26): a provider declared dormant in configs/providers.yaml
# never rides a witness rotation (B2-36 set cerebras dormant: card-gated trial, chat 402;
# mag/doctor.py:607: dormant is a declared state). Operator GO flips the flag and the
# witness returns, no code edit.
from mag.dormant import dormant_ids as _dormant_provider_ids

LANES = [l for l in LANES if l[0] not in _dormant_provider_ids()]
OUT = ROOT / "state" / "rotation_harness.json"
REF_COUNT = 7
# Reference PARTITION (watch/INTAKE_XBATCH_20260905.md clusters A-G, author->letter).
# Salon ruling 09-06 (salon v1.1, 3/3 unanimous): agreement is measured on the
# PARTITION via Adjusted Rand Index, not on cluster counts; reference count
# becomes a calibrated interval [6,8]; print the ARI next to every run.
REF_PARTITION = {
    "polydao": "A", "TivadarDanka": "A",
    "HuggingPapers": "B", "gurtej__gill_": "B", "thisguyknowsai": "B",
    "LearnOpenCV": "C", "MATLAB": "C", "threejs": "C",
    "BryanKeIIy": "D", "cosmosarcive": "D",
    "MirTitles": "E", "mertmetindev": "E", "Infinite_Logiz": "E",
    "swapnakpanda": "E", "pickover": "E",
    "ExploreCosmos_": "F",
    "HowToPrompt__": "G", "predict_addict": "G", "miki_code": "G",
}
ARI_PASS = 0.60      # both witnesses (groq/cerebras fold; deepseek: 0.65 small-n strict)
ARI_PARTIAL = 0.55   # rescue window -> third witness
COUNT_INTERVAL = (6, 8)


def adjusted_rand(a: list[str], b: list[str]) -> float:
    """ARI over two label lists (same items, same order). Stdlib, deterministic."""
    from collections import Counter
    from math import comb
    pairs = Counter(zip(a, b))
    sum_comb = sum(comb(n, 2) for n in pairs.values())
    ca, cb = Counter(a), Counter(b)
    ea = sum(comb(n, 2) for n in ca.values())
    eb = sum(comb(n, 2) for n in cb.values())
    total = comb(len(a), 2)
    expected = ea * eb / total
    max_index = (ea + eb) / 2
    if max_index == expected:
        return 1.0
    return (sum_comb - expected) / (max_index - expected)


def parse_partition(text: str, authors: set[str]) -> dict[str, str] | None:
    """Parse 'A. theme | items: a, b | receipts: x' lines -> {author: letter}."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^\s*([A-Z])[.\)]\s*(.+)$", line.strip())
        if not m:
            continue
        seg = m.group(2)
        im = re.search(r"items:\s*([^|]+)", seg, re.I)
        if not im:
            continue
        for tok in re.split(r"[,;/]", im.group(1)):
            tok = tok.strip().lstrip("@")
            if tok in authors:
                out[tok] = m.group(1)
    return out if len(out) >= 15 else None

PROMPT = """You are one witness in a rotation test. Cluster the {n} captured items below by SUBSTANCE (shared subject matter), not by author, not by source order.

Calibration — the fleet's live arcs set the grain of a "substantive" cluster (items feed goals like): local model weights + quantization (QLoRA/4-bit), training-corpus and library building, autonomous agent fleets + graphs, embodied devices (phones/robots/vision), physical compute (optics/hardware), mathematics as training data, meta/systems reads on AI itself. Aim for the 5-9 broadest substance clusters that place every item; do not fragment by surface detail.

Return STRICTLY this format, nothing else:
CLUSTERS: <count>
A. <theme, max 10 words> | items: <author1, author2> | receipts: <arxiv ids, domains, or ->
B. ...
(letters sequential, every item placed exactly once)

Items:
{rows}"""


def _rows_text(rows: list[dict], seed: int) -> str:
    rng = random.Random(seed)
    rs = rows[:]
    rng.shuffle(rs)
    lines = []
    for r in rs:
        t = re.sub(r"\s+", " ", str(r.get("text", "")))[:900]
        lines.append(json.dumps({"author": r.get("author"), "text": t},
                                ensure_ascii=True))
    return "\n".join(lines)


def _ask(provider: str, model: str | None, prompt: str) -> tuple[bool, str, str]:
    try:
        sys.path.insert(0, str(ROOT))
        from models.providers import reload_providers, chat_provider
        reload_providers()
        kw = {"tier": "T2", "max_tokens": 3500}
        if model:
            kw["model"] = model
        r = chat_provider(provider, system="You cluster captured items by substance. Terse, structured, no prose.",
                          user=prompt, **kw)
        return bool(r.get("ok")), (r.get("text") or ""), (r.get("error") or "")[:120]
    except Exception as e:  # noqa: BLE001
        return False, "", f"unreachable: {str(e)[:120]}"


def run(capture: Path, rotations: int = 2) -> dict:
    rows = [json.loads(l) for l in capture.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    authors = {str(r.get("author")) for r in rows}
    results = []
    for i in range(rotations):
        provider, model = LANES[i % len(LANES)]
        label = provider
        prompt = PROMPT.format(n=len(rows), rows=_rows_text(rows, seed=1000 + i))
        ok, text, err = _ask(provider, model, prompt)
        m = re.search(r"CLUSTERS:\s*(\d+)", text)
        n_clusters = int(m.group(1)) if m else None
        part = parse_partition(text, authors) if ok else None
        ari_v = None
        if part:
            common = sorted(set(part) & set(REF_PARTITION))
            ari_v = round(adjusted_rand([part[a] for a in common],
                                        [REF_PARTITION[a] for a in common]), 3)
        cnt_ok = n_clusters is not None and \
            COUNT_INTERVAL[0] <= n_clusters <= COUNT_INTERVAL[1]
        r_verdict = ("NO-PARTITION" if part is None else
                     "PASS" if ari_v is not None and ari_v >= ARI_PASS and cnt_ok
                     else "PARTIAL" if ari_v is not None and ari_v >= ARI_PARTIAL
                     else "FAIL")
        results.append({
            "rotation": i + 1, "lane": label, "seed": 1000 + i, "ok": ok,
            "error": err if not ok else "",
            "clusters": n_clusters, "ref_clusters": REF_COUNT,
            "count_interval_ok": cnt_ok,
            "ari_vs_reference": ari_v,
            "partition_parsed": len(part) if part else 0,
            "verdict": r_verdict,
            "answer_excerpt": text[:1200],
        })
    # Scoring v3 (salon 09-06, 3/3 unanimous): agreement is measured on the
    # PARTITION (ARI vs the reference partition), not on cluster counts.
    # ARI >= 0.60 = PASS both witnesses; 0.55-0.60 = PARTIAL (third-witness
    # rescue); counts live inside a calibrated interval [6,8] as sanity only.
    full = [r for r in results if r["ok"]]
    passed = [r for r in full if r["verdict"] == "PASS"]
    partial = [r for r in full if r["verdict"] == "PARTIAL"]
    verdict = ("PASS" if full and len(passed) == len(full)
               else "PARTIAL" if passed or partial else "FAIL")
    aris = [r["ari_vs_reference"] for r in full if r["ari_vs_reference"] is not None]
    data = {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "capture": str(capture.relative_to(ROOT)), "verdict": verdict,
            "metric": "adjusted_rand_index vs reference partition (salon ruling "
                      "0906: partition not count; ARI>=0.60 pass, >=0.55 partial)",
            "mean_ari": round(sum(aris) / len(aris), 3) if aris else None,
            "rotations": results}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "run"]
    cap = Path(args[0]) if args else \
        ROOT / "corpus/frontier_thinking/FT_XBATCH_20260905.jsonl"
    cap = cap if cap.is_absolute() else (ROOT / cap)
    d = run(cap)
    for r in d["rotations"]:
        print(f"rotation {r['rotation']} [{r['lane']}]: "
              f"{'ok' if r['ok'] else 'DOWN ' + r['error']} "
              f"clusters={r['clusters']} ARI={r['ari_vs_reference']} "
              f"({r['verdict']}, partition {r['partition_parsed']}/19)")
    print(f"mean ARI: {d.get('mean_ari')}")
    print(f"ROTATION VERDICT: {d['verdict']} -> {OUT.relative_to(ROOT)}")
