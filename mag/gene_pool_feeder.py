"""gene_pool_feeder — build the FLEET GENE POOL from the 2026-09-04 self-audit and select the fittest.

**TOMBSTONED 2026-09-27 (FOSSIL_CENSUS_20260927.md P0-2, receipt
GENE_POOL_TOMBSTONE_20260927.md): DORMANT — do not run, do not feed.**
Cause: dead-at-birth artifact family. The 2026-09-04 audit inputs
(memory/audit/aud_*.json) have no regenerator anywhere in the repo (byte
search 2026-09-27), nothing consumes gene_pool_gen*.json or calls this
module (grep: only this file), and the meta_percolate seam injection happens
only when this script runs — which was once. Regenerating inputs for an
unconsumed output violates the no-bulk-self-processing law. The live
equivalents are the percolator invariants (315 rows, alive, feeding the
thought quantizer) and skill_ledger proven_moves (rides the context pack).
REVIVE CONDITION: a named consumer for gene_pool_gen*.json lands first;
then regenerate the audit (tools/ style builder) BEFORE rerunning this.
The operator law and fitness v1/v2 below remain recorded experiment truth.

OPERATOR LAW (binding, 2026-09-04): DUPLICATION IS EMPHASIS — duplicate genes get EMPHASIS-WEIGHTED
fitness (a theme with N files = Nx weighted direction), never fitness-zero. Orphan lists are not
retirement lists; each orphan cluster is an EMPHASIS class.

FITNESS v1 (pure numbers only, AlphaEvolve law; amendable by amendment):
    fitness = 3*emphasis + 2*(scored or receipted ? 1:0) + 1*(loaded ? 1:0) + recency_bonus(+2 if touched 2026-09-04/05)

Emphasis semantics per gene class (documented v1):
  - code/doc clusters: N = file count in the cluster
  - knot themes: N = theme row count in the verkle chain
  - memory structures: N = file/count figure parsed from the audit
  - unique notable items (orphan notables, sample knots): N = 1 (never zero)
SELECTION: top 25 by fitness. Then the OLD GA (mag.meta_percolate.genetic_pass) runs against the
same pool for lineage — fed through the _top_invariant_texts seam it consumes; if that seam can't
take injected texts cleanly, the stock default-domain pass is called as-is and the delta noted.

stdlib-only. Deterministic. $0. Honest — every fitness input traces to an audited number.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

AUDIT_DIR = ROOT / "memory" / "audit"
OUT_PATH = AUDIT_DIR / "gene_pool_gen1.json"
ROOM = ROOT / "watch" / "room.jsonl"
TODAY = {"2026-09-04", "2026-09-05", "20260904", "20260905"}
FITNESS_V1 = "3*emphasis + 2*(scored|receipted) + 1*loaded + recency_bonus(+2 touched_today)"

GENES: list[dict[str, Any]] = []


def _gene(gene_id: str, domain: str, text: str, emphasis: int, *, scored=False, receipted=False,
          loaded=False, stale=False, size: Any = "?", **extra: Any) -> None:
    text = re.sub(r"\s+", " ", str(text)).strip()[:200]
    fi = {"scored": bool(scored), "receipted": bool(receipted),
          "loaded": bool(loaded), "stale": bool(stale), "size": size}
    fi.update({k: v for k, v in extra.items() if k.startswith("touched")})
    GENES.append({
        "gene_id": gene_id, "domain": domain, "text": text, "emphasis": int(emphasis),
        "fitness_inputs": fi,
    })


def _first_int(s: Any) -> int:
    m = re.search(r"\d+", str(s))
    return int(m.group()) if m else 1


def resolve_verkle_basis(v: dict[str, Any]) -> dict[str, Any]:
    """Latest-per-session basis resolution for the aud_verkles seam (AH19 v2, 2026-09-30).

    This reader consumes AGGREGATES (memory/audit/aud_verkles.json), never raw
    chain rows, so what breaks under v2 append-leaves is the BASIS: `rows` and
    per-theme counts would count re-saves (one session spans multiple rows)
    and `session_diversity.dup_rate` would read as anomaly while it is
    canonical history. Resolution: read the SESSION basis
    (`distinct_session_ids`), flag append_mode when rows != distinct, and
    report BOTH denominators (census denominator law). Per-theme
    SESSION-distinct counts cannot be recovered from aggregates — the audit
    regenerator (the tombstone's revive condition) must dedupe rows per
    session before counting; this seam refuses to guess (no fabrication).
    Under v1 (rows == distinct) this is the identity and gene texts are
    byte-unchanged.
    """
    rows = int(v.get("rows") or 0)
    sd = v.get("session_diversity") or {}
    distinct = int(sd.get("distinct_session_ids") or 0)
    append_mode = rows > 0 and distinct > 0 and rows != distinct
    return {
        "rows": rows,
        "sessions": distinct or rows,
        "append_mode": append_mode,
        "dup_rate": sd.get("dup_rate"),
        "dup_rate_reading": ("canonical append-leaves history (AH19 v2), not anomaly"
                             if append_mode else "v1 anomaly signal"),
    }


def _knot_theme_text(theme: str, n: int, v: dict[str, Any], basis: dict[str, Any]) -> str:
    if not basis.get("append_mode"):
        return (f"chain theme '{theme}': {n} signed rows in verkle_chain.jsonl "
                f"({v['rows']} rows total, dup_rate {v['session_diversity']['dup_rate']})")
    # rows != sessions (v2-sourced audit): name both denominators, never equate them
    return (f"chain theme '{theme}': {n} signed rows in verkle_chain.jsonl "
            f"({basis['rows']} rows / {basis['sessions']} sessions under v2 append-leaves; "
            f"dup_rate {basis['dup_rate']} = {basis['dup_rate_reading']})")


def build_pool() -> None:
    # ── aud_files: code + md clusters (emphasis = file count) ──────────────────
    f = json.loads((AUDIT_DIR / "aud_files.json").read_text(encoding="utf-8"))
    c, ds = f["counts"], f["dir_summary"]
    clusters = [
        ("mag_py", ds["mag_py"], "loaded"), ("scripts_code", ds["scripts_code"], "loaded"),
        ("dash_static", ds["dash_static"], "loaded"),
        ("md_docs", ds["md"]["docs"], None), ("md_watch", ds["md"]["watch"], None),
        ("md_root", ds["md"]["root"], None),
    ]
    for name, blk, flag in clusters:
        notables = ", ".join((blk.get("notable") or [])[:2])
        _gene(f"code:{name}", "code_files", f"{name}: {blk['count']} files ({blk.get('bytes',0)} B); notable: {notables}",
              blk["count"], loaded=(flag == "loaded"), size=blk.get("bytes"))
    _gene("code:loaded_class", "code_files", f"LOADED class: {c['loaded']} code files referenced by live surfaces (ratio {f['loaded_vs_orphan']['ratio']})",
          c["loaded"], loaded=True)
    _gene("code:orphan_class", "code_files", f"ORPHAN class: {c['orphaned']} code files with no live mention — an EMPHASIS class, never a retirement list",
          c["orphaned"], stale=True)
    for o in f["orphans_top15"]:
        hot = o["last_modified"] in TODAY
        _gene(f"orphan:{Path(o['path']).stem}", "orphan_notables",
              f"orphan notable {o['path']} ({o['size']} B, mtime {o['last_modified']}) — emphasis-class member, never fitness-zero",
              1, stale=(not hot), touched_today_=hot, size=o["size"])
    for i, p in enumerate(f["loaded_sample"][:6]):
        _gene(f"loaded:{Path(p).stem}", "code_files", f"loaded sample {p} — live surface member", 1, loaded=True)

    # ── aud_verkles: chain themes (emphasis = row count) + samples ─────────────
    # AH19 (2026-09-30): the seam resolves the rows-vs-sessions basis first —
    # under a v2-sourced audit the row count still drives emphasis (the
    # operator law: duplication IS emphasis) but the gene TEXT names both
    # denominators instead of silently equating rows with sessions.
    v = json.loads((AUDIT_DIR / "aud_verkles.json").read_text(encoding="utf-8"))
    basis = resolve_verkle_basis(v)
    for theme, n in v["themes"].items():
        _gene(f"knot:theme:{theme}", "verkle_chain", _knot_theme_text(theme, n, v, basis),
              n, receipted=True, size=v["size_bytes"])
    for k in v["sample_knots"]:
        m = re.match(r"([^:]+):", k["records"])
        _gene(f"knot:sample:{k['index']}", "verkle_chain", f"knot {k['filename']}: {k['records']}",
              1, receipted=True, touched_today=("2026-09-04" in k["ts"]))
    _gene("knot:orphan_files", "verkle_chain",
          f"{v['bonus_findings']['knot_files_NOT_in_chain']} knot files on disk NOT in the chain index (of {v['bonus_findings']['knot_files_on_disk']}) — an EMPHASIS class",
          v["bonus_findings"]["knot_files_NOT_in_chain"], stale=True)

    # ── aud_memory: memory structures (emphasis = file/count figure) ───────────
    mem = json.loads((AUDIT_DIR / "aud_memory.json").read_text(encoding="utf-8"))
    for s in mem["structures"]:
        n = _first_int(s.get("count", "1"))
        parts = [p for p in str(s["path"]).replace("\\", "/").strip("/").split("/") if p]
        gid = parts[1] if len(parts) > 1 else (parts[0] if parts else "root")
        hot = any(d in str(s.get("last_touched", "")) for d in ("2026-09-04", "2026-09-05"))
        _gene(f"mem:{gid}", "memory_structures",
              f"{s['path']} — {s['kind']}; {s.get('note', s.get('referenced_by', [''])[0])}",
              n, loaded=bool(s.get("referenced_by_live_organ")), stale=(not hot),
              touched_today_=hot, size=s.get("size"))

    # ── aud_research: corpus economics (emphasis = card counts) ────────────────
    r = json.loads((AUDIT_DIR / "aud_research.json").read_text(encoding="utf-8"))
    cards, scored = r["cards"], r["scored_vs_unscored"]
    _gene("research:corpus", "research_corpus", f"research corpus: {cards['total']} cards, {cards['total_bytes']} B; {cards['by_prefix']['INTAKE_']} INTAKE cards", cards["total"])
    _gene("research:scored", "research_corpus", f"scored class: {scored['scored_estimate']} cards with fitness markers ({scored['ratio']})", scored["scored_estimate"], scored=True)
    _gene("research:unscored", "research_corpus", f"unscored class: {scored['unscored_estimate']} cards awaiting scoring — an EMPHASIS class", scored["unscored_estimate"])
    _gene("research:receipted_today", "research_corpus", f"{cards['receipted_today']['referenced_in_room_jsonl']} cards referenced in room.jsonl today ({cards['receipted_today']['d4_cards']} d4 cards)", cards["receipted_today"]["referenced_in_room_jsonl"], receipted=True, touched_today_=True)
    _gene("research:orphaned_never_receipted", "research_corpus", f"{cards['receipted_today']['orphaned_never_receipted']} cards orphaned, never receipted — an EMPHASIS class, never fitness-zero", cards["receipted_today"]["orphaned_never_receipted"], stale=True)
    _gene("research:falsifier_attached", "research_corpus", f"{scored['falsifier_attached']} cards carry an attached falsifier", scored["falsifier_attached"], scored=True)
    _gene("research:inbox_unread", "research_corpus", f"queue inbox: {r['inbox']['total_unread']} unread across {len(r['inbox']['per_lane'])} lanes; 8 lanes all live last run", r["inbox"]["total_unread"], touched_today_=True)

    # ── aud_orphans: external unmined artifacts (each notable = emphasis-1 gene) ─
    o = json.loads((AUDIT_DIR / "aud_orphans.json").read_text(encoding="utf-8"))
    for s in o["surfaces"]:
        _gene(f"ext:{Path(s['path']).name or 'root'}", "external_orphans",
              f"external surface {s['path']}: {s['count']} entries, {s.get('size','?')}, mined={s.get('mined')}",
              _first_int(s["count"]), stale=(s.get("mined") in (False, "partial")))
    for i, item in enumerate(o["unmined_notable"]):
        hot = "2026-09-04" in item or "2026-09-03" in item
        _gene(f"ext:notable:{i}", "external_orphans", f"unmined notable: {item}", 1,
              stale=(not hot), touched_today_=hot)


def fitness(g: dict[str, Any]) -> int:
    fi = g["fitness_inputs"]
    eff = fi
    scored = eff.get("scored", False)
    receipted = eff.get("receipted", False)
    loaded = eff.get("loaded", False)
    touched = eff.get("touched_today", False) or eff.get("touched_today_", False)
    return 3 * g["emphasis"] + 2 * (1 if (scored or receipted) else 0) + 1 * (1 if loaded else 0) + (2 if touched else 0)


def run_old_ga(top_texts: list[str]) -> dict[str, Any]:
    """Lineage: run mag.meta_percolate.genetic_pass against the same pool. Feed texts through the
    _top_invariant_texts seam genetic_pass consumes (its only text source); then the stock
    default-domain pass as-is for comparison."""
    out: dict[str, Any] = {}
    from mag import meta_percolate as mp
    orig = mp._top_invariant_texts
    try:
        mp._top_invariant_texts = lambda domains=None: list(top_texts)  # the seam it serves
        inj = mp.genetic_pass(domains=None, keep=5)
        out["injected"] = {"ok": inj.get("ok"), "n_population": inj.get("n_population"),
                           "best_genes": [{"gene": b["gene"][:80], "fitness": b["fitness"]} for b in inj.get("best_genes", [])]}
    except Exception as e:
        out["injected"] = {"ok": False, "error": str(e)[:120]}
    finally:
        mp._top_invariant_texts = orig
    try:
        stock = mp.genetic_pass(domains=None, keep=5)
        out["stock_default"] = {"ok": stock.get("ok"), "n_population": stock.get("n_population"),
                                "best_genes": [{"gene": b["gene"][:80], "fitness": b["fitness"]} for b in stock.get("best_genes", [])]}
    except Exception as e:
        out["stock_default"] = {"ok": False, "error": str(e)[:120]}
    return out


# ── FITNESS V2 (salon_ga_v2_fitness_20260904 fold, binding 2026-09-04) ──────
# 1. Two-axis reporting, never summed: mass_emphasis (v1 emphasis weighting with
#    recency service floor) and quality_value (additive) are SEPARATE axes.
# 2. NULL-thema: legacy-NULL chain rows tagged thema:legacy_import; NULL-mass
#    reported separately; never collapsed to one gene, never excluded.
# 3. Service floor: recency bonus 2x if touched within 7 days; beyond that it
#    decays to the floor 1.0x, never zero — serviced invariants stay alive.
# 4. JOINT_RANK selection: falsified_count>0 first, then quality_value desc,
#    then mass_emphasis desc. Selection reads the PAIR, never a sum.
# 5. Probe-yield kill-switch: probes_run/|pool| for gen1 = 2/73 (light replay
#    + LAW 13 conc probe, both gene-linked to mem:runs). If gen-2 ratio < gen-1
#    after 10 generations, revert to v1.
V2_OUT_PATH = AUDIT_DIR / "gene_pool_gen2.json"
SERVICE_FLOOR_DAYS = 7
FALSIFIER_PROBES = [
    {"probe": "light_replay_falsifier", "gene_id": "mem:runs",
     "evidence": "memory/runs/light_falsifier/20260905T004126Z.json (verdict PASS, p=1.04e-45)"},
    {"probe": "law13_conc_probe_CONC_PROBE_PAST50", "gene_id": "mem:runs",
     "evidence": "memory/runs/concurrency/ + watch/room.jsonl intake receipt 2026-09-04"},
]
GEN1_PROBES, GEN1_POOL = 2, 73


def recency_bonus_v2(g: dict[str, Any]) -> int:
    touched = g["fitness_inputs"].get("touched_today", False) or g["fitness_inputs"].get("touched_today_", False)
    # Audit inputs only distinguish touched-today vs not; treat touched-today as
    # inside the 7-day window. Beyond the window the bonus decays to the floor
    # (1.0x), never zero.
    return 2 if touched else 1


def fitness_v1_floor(g: dict[str, Any]) -> int:
    fi = g["fitness_inputs"]
    return (3 * g["emphasis"]
            + 2 * (1 if (fi.get("scored") or fi.get("receipted")) else 0)
            + 1 * (1 if fi.get("loaded") else 0)
            + recency_bonus_v2(g))


def run_v2() -> int:
    build_pool()
    fcount: dict[str, int] = {}
    for p in FALSIFIER_PROBES:
        fcount[p["gene_id"]] = fcount.get(p["gene_id"], 0) + 1
    for g in GENES:
        f = fcount.get(g["gene_id"], 0)
        g["mass_emphasis"] = fitness_v1_floor(g)
        g["quality_value"] = ((2 if f > 0 else 0)
                              + (1 if (g["fitness_inputs"].get("scored") or g["fitness_inputs"].get("receipted")) else 0)
                              + (1 if g["fitness_inputs"].get("loaded") else 0))
        g["falsified_count"] = f
        if g["gene_id"] == "knot:theme:NULL":
            g["thema"] = "legacy_import"
    ranked = sorted(GENES, key=lambda g: (0 if g["falsified_count"] > 0 else 1,
                                          -g["quality_value"], -g["mass_emphasis"]))
    selected = ranked[:25]
    null_genes = [g for g in GENES if g.get("thema") == "legacy_import"]
    null_mass = sum(g["mass_emphasis"] for g in null_genes)
    gen1_yield = GEN1_PROBES / GEN1_POOL
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "ts": ts,
        "law": "duplication-is-emphasis (operator, 2026-09-04)",
        "fitness_v2": "two-axis, never summed: {mass_emphasis = 3*emphasis + 2*(scored|receipted) + loaded + recency(floor 1.0x, 7-day window), quality_value = +2 falsifier-run-today +1 receipted|scored +1 loaded}",
        "selection_rule": "JOINT_RANK: falsified_count>0 first, then quality_value desc, then mass_emphasis desc; selection reads the pair, never a sum",
        "n_genes": len(GENES), "n_selected": len(selected),
        "null_thema": {"tag": "thema:legacy_import", "genes": [g["gene_id"] for g in null_genes],
                       "null_mass_emphasis": null_mass,
                       "note": "metadata tag only; not collapsed, not excluded, no fitness change beyond axes"},
        "probe_yield_kill_switch": {
            "gen1": {"probes_run": GEN1_PROBES, "pool": GEN1_POOL, "ratio": round(gen1_yield, 6)},
            "probes": FALSIFIER_PROBES,
            "rule": "after 10 generations, if gen-2 probes_run/|pool| < gen-1 ratio, revert to v1",
            "tri_state": "gen2_ratio<gen1_ratio=FAIL(revert) | ~=NEUTRAL | >PASS",
        },
        "genes": [{"gene_id": g["gene_id"], "domain": g["domain"], "text": g["text"],
                   "mass_emphasis": g["mass_emphasis"], "quality_value": g["quality_value"],
                   "falsified_count": g["falsified_count"],
                   **({"thema": g["thema"]} if g.get("thema") else {})} for g in ranked],
        "selected_25": [{"gene_id": g["gene_id"], "domain": g["domain"],
                         "mass_emphasis": g["mass_emphasis"], "quality_value": g["quality_value"],
                         "falsified_count": g["falsified_count"]} for g in selected],
    }
    V2_OUT_PATH.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"GENE POOL GEN-2  (fitness v2: two-axis {len(GENES)} genes, JOINT_RANK selected {len(selected)})")
    print(f"{'#':>3} {'mass_emp':>9} {'qual':>4} {'fals':>4}  gene_id")
    for i, g in enumerate(ranked[:10], 1):
        print(f"{i:>3} {g['mass_emphasis']:>9} {g['quality_value']:>4} {g['falsified_count']:>4}  {g['gene_id']}")
    print(f"null-thema: {len(null_genes)} gene(s) tagged legacy_import, null_mass_emphasis={null_mass} (reported separately, not collapsed)")
    print(f"probe-yield baseline: gen1 {GEN1_PROBES}/{GEN1_POOL} = {gen1_yield:.6f} (kill-switch after 10 gens)")
    print(f"-> {V2_OUT_PATH.relative_to(ROOT)}")

    gist = ("joint-rank top5: " + ", ".join(
        f"{g['gene_id']}(mass={g['mass_emphasis']},qual={g['quality_value']},fals={g['falsified_count']})"
        for g in ranked[:5]) +
        f"; axes separate never summed; falsified-first genes={sum(1 for g in GENES if g['falsified_count'] > 0)}; "
        f"probe-yield baseline gen1 {GEN1_PROBES}/{GEN1_POOL}={gen1_yield:.4f}; "
        f"files mag/gene_pool_feeder.py(--v2) memory/audit/gene_pool_gen2.json")
    row = {"ts": "2026-09-04", "thread": "audit", "seat": "card-worker", "type": "receipt",
           "item": "gene_pool_gen2", "gist": gist}
    with ROOM.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"room receipt appended -> {ROOM.relative_to(ROOT)}")
    return 0


def main() -> int:
    if "--v2" in sys.argv:
        return run_v2()
    build_pool()
    for g in GENES:
        g["fitness"] = fitness(g)
    GENES.sort(key=lambda g: -g["fitness"])
    top = GENES[:25]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ga = run_old_ga([g["text"] for g in top])

    payload = {
        "ts": ts, "law": "duplication-is-emphasis (operator, 2026-09-04)",
        "fitness_v1": FITNESS_V1,
        "n_genes": len(GENES), "n_selected": len(top),
        "emphasis_weighted": True,
        "top": [{"gene_id": g["gene_id"], "domain": g["domain"], "fitness": g["fitness"],
                 "emphasis": g["emphasis"], "text": g["text"]} for g in top],
        "old_ga_lineage": ga,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"GENE POOL GEN-1  (fitness v1: {FITNESS_V1})")
    print(f"pool={len(GENES)}  selected={len(top)}  -> {OUT_PATH.relative_to(ROOT)}")
    print(f"{'#':>3} {'fitness':>7} {'emp':>6}  {'gene_id':38} domain")
    for i, g in enumerate(top, 1):
        print(f"{i:>3} {g['fitness']:>7} {g['emphasis']:>6}  {g['gene_id']:38} {g['domain']}")
    inj, stock = ga.get("injected", {}), ga.get("stock_default", {})
    print("\nOLD-GA LINEAGE:")
    print(f"  injected({inj.get('n_population')} texts): " +
          "; ".join(f"{b['fitness']}:{b['gene'][:40]}" for b in inj.get("best_genes", [])[:3]))
    print(f"  stock default({stock.get('n_population')} texts): " +
          ("; ".join(f"{b['fitness']}:{b['gene'][:40]}" for b in stock.get("best_genes", [])[:3])
           if stock.get("ok") else f"unavailable: {stock.get('error')}"))

    gist = (f"{len(GENES)} genes, top5: " +
            ", ".join(f"{g['gene_id']}={g['fitness']}" for g in top[:5]) +
            f"; emphasis-weighted per operator law (3*emphasis term); old-GA injected-pop={inj.get('n_population')} vs stock-pop={stock.get('n_population')}")
    row = {"ts": "2026-09-04", "thread": "audit", "seat": "card-worker", "type": "receipt",
           "item": "gene_pool_gen1", "gist": gist}
    with ROOM.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nroom receipt appended -> {ROOM.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
