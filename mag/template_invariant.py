"""template_invariant — turn a structural TEMPLATE into a single INVARIANT; instances become data.

Operator (2026-08-10): "how can we make the structural template an invariant?" (after the doctrine
audit found 225 near-duplicate pairs that were mostly TEMPLATE similarity — e.g. the 31 per-vendor
`leaked:*` nodes all share one sentence skeleton.)

THE MECHANISM (the invariant/data split — the same discipline as "steal the invariant, never the
DNA"):
  * The TEMPLATE is the invariant — the constant skeleton a family of nodes conforms to (its
    schema/contract). Fold it ONCE.
  * The INSTANCES are data — the variable slots (vendor, count, list) that fill the template.
    Keep them as a compact ledger, NOT as N near-duplicate doctrine nodes.

So instead of 31 nodes each re-encoding the template, the graph holds ONE structural invariant
(the template/schema) + a data ledger of the 31 instances under it. This is exactly how RISpec /
the open-contract lesson said to abstract: the durable asset is the STRUCTURE (the contract), not
each concrete instance.

extract(nodes)        -> the common structural template: constant skeleton + variable slots.
fold_template(nodes)  -> fold the template as ONE doctrine invariant (source=template_invariant).
instance_ledger(...)  -> write the instances as a compact JSON ledger (content-preserving).
consolidate(source)   -> fold template + emit ledger for a whole family (per-instance nodes stay,
                         but the graph now has the template invariant as the authority).

Deterministic, $0. Schema: template_invariant.v1 · CLI: python -m mag.template_invariant extract|consolidate
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "template_invariant.v1"
OUT_DIR = ROOT / "memory" / "runs" / "template_invariant"


def _common_prefix(strings: list[str]) -> str:
    if not strings:
        return ""
    p = strings[0]
    for s in strings[1:]:
        while not s.startswith(p):
            p = p[:-1]
            if not p:
                return ""
    return p


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def extract(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract the common structural TEMPLATE from a family of doctrine nodes.

    Returns the label skeleton (common prefix + '<slot>'), the constant summary tokens (present in
    EVERY node), and the variable slots (tokens that differ across instances).
    """
    labels = [str(n.get("label") or "") for n in nodes]
    sums = [str(n.get("summary") or "") for n in nodes]
    if not labels:
        return {"ok": False, "error": "no nodes"}
    label_prefix = _common_prefix(labels)
    # label slot = what varies after the common prefix
    label_slots = sorted({lab[len(label_prefix):].strip(": ") for lab in labels if len(lab) > len(label_prefix)})
    # constant summary tokens = present in EVERY summary
    const = None
    for s in sums:
        t = _tokens(s)
        const = t if const is None else (const & t)
    const = sorted(const or set())
    return {"ok": True, "schema": SCHEMA, "n_instances": len(nodes),
            "label_template": (label_prefix + "<slot>") if label_slots else labels[0],
            "label_slots": label_slots[:40],
            "constant_summary_tokens": const,
            "summary_template": "constant-token-skeleton + per-instance slots"}


def _template_label(nodes: list[dict[str, Any]]) -> str:
    ex = extract(nodes)
    return "template:" + (ex.get("label_template") or "family").strip(":").replace("<slot>", "family")


def fold_template(nodes: list[dict[str, Any]], *, source: str = "template_invariant") -> dict[str, Any]:
    """Fold the structural TEMPLATE as ONE doctrine invariant (the contract the family conforms to)."""
    from mag.knowledge_graph import fold
    ex = extract(nodes)
    if not ex.get("ok"):
        return {"ok": False, "error": ex.get("error")}
    label = _template_label(nodes)
    body = (f"STRUCTURAL TEMPLATE INVARIANT: every node in this family conforms to "
            f"label '{ex.get('label_template')}' (slots: {ex.get('label_slots')[:8]}) and shares "
            f"the constant summary tokens {ex.get('constant_summary_tokens')[:20]}. The template "
            f"is the invariant; the instances are data. {ex.get('n_instances')} instances.")
    r = fold(label, "doctrine", body, source=source)
    return {"ok": True, "schema": SCHEMA, "template_label": label,
            "already_present": r.get("already_present"), "extract": ex}


def instance_ledger(nodes: list[dict[str, Any]], *, name: str = "family") -> dict[str, Any]:
    """Write the instances as a compact JSON ledger under the template (content-preserving)."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}_instances.json"
    rows = [{"label": str(n.get("label")), "summary": str(n.get("summary"))[:220],
             "source": str(n.get("source"))} for n in nodes]
    path.write_text(json.dumps({"schema": "template_invariant.ledger.v1", "name": name,
                                "n_instances": len(rows), "instances": rows},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "n_instances": len(rows), "ledger": str(path)}


def consolidate(*, source: str = "leaked_prompt_mine", label_prefix: str = "leaked:",
                write_ledger: bool = True) -> dict[str, Any]:
    """For a whole family (by source + label prefix): fold the structural template as THE invariant
    and (optionally) emit the instances as a data ledger. Non-destructive — instance nodes stay; the
    graph now has the template invariant as the authority."""
    from mag.knowledge_graph import GRAPH_PATH
    g = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    family = [n for n in g.get("nodes", [])
              if n.get("kind") == "doctrine"
              and str(n.get("source")) == source
              and str(n.get("label", "")).startswith(label_prefix)]
    if not family:
        return {"ok": False, "error": f"no family {source}/{label_prefix}*"}
    t = fold_template(family, source="template_invariant")
    ledger = instance_ledger(family, name=label_prefix.strip(":")) if write_ledger else None
    return {"ok": True, "schema": SCHEMA, "source": source, "label_prefix": label_prefix,
            "family_size": len(family), "template": t.get("template_label"),
            "template_new": not t.get("already_present"),
            "ledger": ledger.get("ledger") if ledger else None,
            "note": "template now the invariant; instances are data under it (nodes preserved)"}


def consolidate_all(*, min_instances: int = 2, min_const_ratio: float = 0.25,
                    min_const_tokens: int = 4, min_label_prefix: int = 3,
                    write_ledger: bool = True) -> dict[str, Any]:
    """Apply the template-invariant consolidation EVERYWHERE: every doctrine source family that
    genuinely shares a structural template gets ONE template invariant + a data ledger.

    A family qualifies when it has >= min_instances nodes sharing a common label prefix (the
    template skeleton) AND a high ratio of constant summary tokens (the shared sentence skeleton).
    Families with genuinely distinct nodes (low const ratio / no common prefix) are left alone so
    we never collapse distinct doctrine into noise. Deterministic, $0, non-destructive.
    """
    from mag.knowledge_graph import GRAPH_PATH
    from collections import defaultdict
    g = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    by_src: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in g.get("nodes", []):
        if n.get("kind") == "doctrine":
            by_src[str(n.get("source") or "?")].append(n)

    # Subgroup each source by LABEL-PREFIX FAMILY (the token before the first ':'), because a
    # source can hold multiple families (e.g. leaked_prompt_mine has leaked:* AND frontier:*).
    def _family(label: str) -> str:
        return str(label).split(":", 1)[0] if ":" in str(label) else str(label)

    consolidated, skipped_distinct, skipped_small = [], [], []
    for src, nodes in sorted(by_src.items()):
        if len(nodes) < min_instances:
            skipped_small.append(src)
            continue
        by_fam: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for n in nodes:
            by_fam[_family(str(n.get("label")) )].append(n)
        for fam, fam_nodes in sorted(by_fam.items()):
            if len(fam_nodes) < min_instances:
                continue
            ex = extract(fam_nodes)
            if not ex.get("ok"):
                continue
            const = ex.get("constant_summary_tokens") or []
            union = set()
            for n in fam_nodes:
                union |= _tokens(str(n.get("summary")))
            const_ratio = len(const) / len(union) if union else 0
            prefix_ok = len(_common_prefix([str(n.get("label") or "") for n in fam_nodes])) >= min_label_prefix
            # qualifies when it shares a label prefix AND either a high const-ratio OR a solid
            # absolute set of constant (recurring) skeleton tokens. The leaked family has a short
            # shared skeleton phrase (6 words) but low ratio vs its unique model-name union — the
            # ABSOLUTE constant-token count is the reliable signal of a real template.
            if prefix_ok and (const_ratio >= min_const_ratio or len(const) >= min_const_tokens):
                t = fold_template(fam_nodes, source=src)
                led = instance_ledger(fam_nodes, name=f"{src}-{fam}") if write_ledger else None
                consolidated.append({"source": src, "family": fam, "n_instances": len(fam_nodes),
                                     "template": t.get("template_label"),
                                     "const_ratio": round(const_ratio, 2),
                                     "ledger": led.get("ledger") if led else None})
            else:
                skipped_distinct.append({"source": src, "family": fam, "n_instances": len(fam_nodes),
                                         "const_ratio": round(const_ratio, 2), "prefix_ok": prefix_ok})
    return {"ok": True, "schema": SCHEMA, "consolidated": consolidated,
            "n_consolidated": len(consolidated),
            "skipped_distinct": skipped_distinct, "n_skipped_distinct": len(skipped_distinct),
            "skipped_small": skipped_small}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="template-invariant")
    ap.add_argument("cmd", nargs="?", default="consolidate",
                    choices=["extract", "consolidate", "all"])
    ap.add_argument("--source", default="leaked_prompt_mine")
    ap.add_argument("--prefix", default="leaked:")
    args = ap.parse_args(argv)
    if args.cmd == "extract":
        from mag.knowledge_graph import GRAPH_PATH
        g = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        fam = [n for n in g.get("nodes", []) if n.get("kind") == "doctrine"
               and str(n.get("source")) == args.source
               and str(n.get("label", "")).startswith(args.prefix)]
        print(json.dumps(extract(fam), indent=2))
    elif args.cmd == "all":
        print(json.dumps(consolidate_all(), indent=2))
    else:
        print(json.dumps(consolidate(source=args.source, label_prefix=args.prefix), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
