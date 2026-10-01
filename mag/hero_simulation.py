#!/usr/bin/env python3
"""hero_simulation.py — THE SALON FALSIFIER (orphans_astra_20260906 exit condition).

The test: "a fresh agent reaches every LOOT from a declared path and never reaches
a GRAVE" — simulated, deterministic, $0, no network, no daemons.

Walk model (fresh agent = interface walker, not filesystem crawler):
  Entry points   = the six destinations (Home/Projects/History/Run/Library/System).
                   If the destination pages are not built, the CURRENT nav wall
                   (dashboard/static/nav.js LINKS) is the entry surface — that
                   baseline run is the falsifier's first honest reading.
  Reach tiers    = nav   : direct nav entry targets/leads to the loot
                   link  : followable href/src on an entry page (one hop)
                   cite  : the declared path is rendered as text on an entry page
                           (agent-readable, but not wired — does NOT count as reached)
  LOOT reached   = tier nav or link, AND every declared path exists + loads.
  GRAVE reached  = any nav entry, destination link, or followable link anywhere
                   in the served surface leads to it. Farewell citations (text
                   mentions) are legal per the salon verdict and counted apart.

Verdict: PASS iff every LOOT reached AND zero GRAVEs reached; else FAIL with the
exact breaks. Output: state/hero_simulation.json + console table.
"""

from __future__ import annotations

import json
import py_compile
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "dashboard" / "static"
NAV_JS = STATIC / "nav.js"
DOGFOOD_MANIFEST = ROOT / "research" / "orphan_registry" / "today_dogfood.md"
OUT_JSON = ROOT / "state" / "hero_simulation.json"

DESTINATIONS = ["home", "projects", "history", "run", "library", "system"]

# ---------------------------------------------------------------- registry --

def load_loot_registry() -> list[dict]:
    """LOOT registry — every orphans-astra LOOT with its DECLARED path."""
    reg = [
        {
            "id": "b7_spectral_spec",
            "salon_row": "B7 spectral — LOOT (the spec + six falsifiers); 'launched' DISPUTED",
            "kind": "md",
            "paths": ["watch/SELF_STEAL_LIGHT_MAZE_SPECTRAL_20260906.md"],
        },
        {
            "id": "maze_keeper_pack",
            "salon_row": "maze-keeper — LOOT as file-fed narrator candidate (the pack, not the weights)",
            "kind": "dir",
            "paths": ["watch/maze_world/"],
        },
        {
            "id": "assembled_maze_0831",
            "salon_row": "08-31 assembled maze — LOOT (the existing assembled arm of open RQ1)",
            "kind": "json",
            "paths": ["memory/graph/session_maze.json"],
        },
        {
            "id": "session_maze_module",
            "salon_row": "session_maze.py — LOOT (the probe instrument RQ1 needs, already written)",
            "kind": "py",
            "paths": ["mag/session_maze.py"],
        },
        {
            "id": "cards_37",
            "salon_row": "37 unlinked cards — LOOT (audited artifacts need ledger edges, not archival)",
            "kind": "md",
            "paths": cards37_paths(),
            "manifest": "research/orphan_registry/today_dogfood.md §3",
        },
    ]
    return reg


def cards37_paths() -> list[str]:
    """Deterministic: parse the 37 declared paths from the dogfood manifest §3.

    Lines may carry a ' — LINKED via cell ...' suffix appended by the concurrent
    re-link pass; the declared path is the token before the em-dash.
    """
    block = re.search(
        r"## 3\. UNLINKED CARDS.*?```\n(.*?)```",
        DOGFOOD_MANIFEST.read_text(encoding="utf-8", errors="replace"),
        re.S,
    )
    if not block:
        return []
    out = []
    for line in block.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        path = line.split(" — ")[0].strip()
        if path and not path.startswith("#"):
            out.append(path)
    return out


def load_grave_registry() -> list[dict]:
    """GRAVE registry — what a fresh agent must NEVER reach."""
    return [
        {
            "id": "room_game_fork",
            "salon_row": "room_game fork — GRAVE (re-teaches three fixed defects; retire citing the regression)",
            "declared": "dashboard/static/room_game.html",
            "tokens": ["room_game"],
            "sealed_locations": [
                "dashboard/static/attic/room_game.html.retired",
                "dashboard/static/room_game.html.bak-merge",
            ],
        },
        {
            "id": "phantom_index_authority",
            "salon_row": "phantom index authority — GRAVE its authority; preserve the evidence (92% unresolved)",
            "declared": "memory/MEMORY.md",
            "tokens": ["MEMORY.md"],
            "sealed_locations": [],
        },
    ]

# ------------------------------------------------------------- loads checks --

def loads_ok(path: Path, kind: str) -> tuple[bool, str]:
    try:
        if kind == "dir":
            if not path.is_dir():
                return False, "not a directory"
            loadable = [p for p in path.iterdir() if p.is_file() and loads_ok(p, "md")[0]]
            return (len(loadable) > 0, f"{len(loadable)} loadable file(s): " + ", ".join(sorted(p.name for p in loadable)))
        if not path.is_file():
            return False, "missing"
        text = path.read_text(encoding="utf-8", errors="strict")
        if kind == "json":
            json.loads(text)
            return True, "json.load OK"
        if kind == "py":
            py_compile.compile(str(path), doraise=True)
            return True, "py_compile OK"
        # md / plain text
        if not any(l.strip() for l in text.splitlines()):
            return False, "empty"
        return True, f"utf-8 OK ({len(text.splitlines())} lines)"
    except Exception as e:  # noqa: BLE001 — the sim must name the failure, not die on it
        return False, f"{type(e).__name__}: {e}"

# ------------------------------------------------------------ walk surface --

def parse_nav() -> list[dict]:
    """nav.js LINKS: [(target,label),...] — the current wall."""
    text = NAV_JS.read_text(encoding="utf-8", errors="replace")
    entries = []
    for m in re.finditer(r'\[\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]', text):
        entries.append({"target": m.group(1), "label": m.group(2)})
    return entries


def find_destination_pages() -> list[dict]:
    """Six-destination pages, if the re-home has landed them."""
    found = []
    for name in DESTINATIONS:
        for cand in (STATIC / f"{name}.html", STATIC / name / "index.html"):
            if cand.is_file():
                found.append({"destination": name, "file": str(cand.relative_to(ROOT)).replace("\\", "/")})
    return found


def _static_file_for_url(target: str) -> Path | None:
    if target.startswith("/static/"):
        p = STATIC / target[len("/static/"):]
        return p if p.is_file() else None
    return None


REF_RE = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)


def build_surface(nav: list[dict]) -> dict:
    """Entry pages = nav targets that are served files (+ their local render
    data files). Extract followable links and rendered text per entry page."""
    pages = []
    seen_files: set[Path] = set()
    for e in nav:
        f = _static_file_for_url(e["target"])
        if not f or f in seen_files:
            continue
        seen_files.add(f)
        pages.append((e["target"], f))

    surface = {"pages": [], "links": [], "text_corpus": []}
    for target, f in pages:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = f.relative_to(ROOT)
        local_refs = []
        for m in REF_RE.finditer(text):
            ref = m.group(1)
            surface["links"].append({"from": str(rel).replace("\\", "/"), "ref": ref})
            # local render data (script src in the same tree) is part of the page
            if ref.endswith(".js") and not ref.startswith(("http", "/", "data:")):
                local = (f.parent / ref).resolve()
                if local.is_file() and STATIC in local.parents and local not in seen_files:
                    seen_files.add(local)
                    local_refs.append(local)
        corpus = text
        for lf in local_refs:
            try:
                corpus += "\n" + lf.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
        surface["text_corpus"].append({"entry": target, "file": str(rel).replace("\\", "/"), "text": corpus})
        surface["pages"].append(str(rel).replace("\\", "/"))
    return surface

# ------------------------------------------------------------- reachability --

def loot_tokens(loot: dict) -> list[str]:
    toks = set()
    for p in loot["paths"]:
        pp = p.rstrip("/")
        toks.add(pp)
        toks.add(Path(pp).name)
    return sorted(toks, key=len, reverse=True)


def reach_loot(loot: dict, nav: list[dict], surface: dict) -> dict:
    toks = loot_tokens(loot)
    # tier nav: any nav target/label naming the loot
    nav_hits = []
    for e in nav:
        hay = e["target"] + " " + e["label"]
        for t in toks:
            if t in hay:
                nav_hits.append(f"nav:{e['label']}→{e['target']}")
                break
    # tier link: followable href/src on an entry page
    link_hits = []
    for l in surface["links"]:
        for t in toks:
            if t in l["ref"]:
                link_hits.append(f"link:{l['ref']} (on {l['from']})")
                break
    # tier cite: rendered text mentions the declared path (agent-readable, not wired)
    cite_hits = []
    for page in surface["text_corpus"]:
        for t in toks:
            if t in page["text"]:
                cite_hits.append(f"cite: {page['file']}")
                break

    resolved, load_report = [], []
    for p in loot["paths"]:
        ok, why = loads_ok(ROOT / p, loot["kind"])
        resolved.append(ok)
        load_report.append({"path": p, "loads": ok, "why": why})

    tier = "nav" if nav_hits else ("link" if link_hits else ("cite" if cite_hits else "none"))
    reached = tier in ("nav", "link") and all(resolved)
    return {
        "tier": tier,
        "reached": reached,
        "resolves": f"{sum(resolved)}/{len(resolved)}",
        "all_paths_load": all(resolved),
        "nav_hits": nav_hits[:3],
        "link_hits": link_hits[:3],
        "cite_hits": sorted(set(cite_hits))[:5],
        "paths": load_report,
    }


def reach_grave(grave: dict, nav: list[dict], surface: dict, served_scan: list[dict]) -> dict:
    toks = grave["tokens"]
    nav_hits = [f"nav:{e['label']}→{e['target']}" for e in nav if any(t in e["target"] or t in e["label"] for t in toks)]
    link_hits = [f"link:{l['ref']} (on {l['from']})" for l in surface["links"] if any(t in l["ref"] for t in toks)]
    deep_link_hits = [f"link:{h['ref']} (on {h['from']})" for h in served_scan if any(t in h["ref"] for t in toks)]
    mentions = sorted({h["from"] for h in served_scan if any(t in h["text"] for t in toks)})
    served = (STATIC / Path(grave["declared"]).name).exists()
    return {
        "reached": bool(nav_hits or link_hits or deep_link_hits or served),
        "served_at_declared_path": served,
        "nav_hits": nav_hits,
        "link_hits": link_hits[:3],
        "deep_link_hits": deep_link_hits[:3],
        "mentions_only": mentions[:6],
        "sealed_locations": [s for s in grave["sealed_locations"] if (ROOT / s).exists()],
    }

# -------------------------------------------------------------------- main --

def main() -> int:
    nav = parse_nav()
    dest = find_destination_pages()
    surface = build_surface(nav)

    # strict grave sweep: followable refs across the WHOLE served static tree
    served_scan = []
    for p in STATIC.rglob("*"):
        if p.suffix.lower() not in (".html", ".js", ".json"):
            continue
        s = str(p)
        if "attic" in s or ".mimosa" in s or ".bak" in p.name:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        served_scan.append({
            "from": str(p.relative_to(ROOT)).replace("\\", "/"),
            "ref": " ".join(REF_RE.findall(t)),
            "text": t,
        })

    loot_results = {}
    for loot in load_loot_registry():
        loot_results[loot["id"]] = reach_loot(loot, nav, surface)
        loot_results[loot["id"]]["salon_row"] = loot["salon_row"]
        if loot.get("manifest"):
            loot_results[loot["id"]]["manifest"] = loot["manifest"]

    grave_results = {}
    for grave in load_grave_registry():
        grave_results[grave["id"]] = reach_grave(grave, nav, surface, served_scan)
        grave_results[grave["id"]]["salon_row"] = grave["salon_row"]

    loot_reached = {k: v["reached"] for k, v in loot_results.items()}
    graves_reached = {k: v["reached"] for k, v in grave_results.items()}
    breaks = []
    for k, ok in loot_reached.items():
        if not ok:
            r = loot_results[k]
            why = "paths fail to load" if not r["all_paths_load"] else f"tier={r['tier']} (needs nav/link from a destination)"
            breaks.append(f"LOOT unreachable: {k} [{why}]")
    for k, ok in graves_reached.items():
        if ok:
            breaks.append(f"GRAVE reachable: {k}")

    verdict = "PASS" if not breaks else "FAIL"

    report = {
        "schema": "hero_simulation.v1",
        "falsifier": "orphans_astra_20260906 SALON_ARTIFACT: fresh agent reaches every LOOT from a declared path, never reaches a GRAVE",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "BASELINE (six-destination re-home not built; simulated against the current nav wall)",
        "surface": {
            "nav_tabs": len(nav),
            "destinations_built": bool(dest),
            "destination_pages": dest,
            "entry_pages_rendered": len(surface["pages"]),
        },
        "loots": loot_results,
        "graves": grave_results,
        "loot_reached_x_of_y": "{}/{}".format(sum(loot_reached.values()), len(loot_reached)),
        "grave_reached_x_of_y": "{}/{}".format(sum(graves_reached.values()), len(graves_reached)),
        "verdict": verdict,
        "breaks": breaks,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=1), encoding="utf-8")

    # console table
    print(f"HERO SIMULATION — {report['mode']}")
    print(f"surface: {len(nav)} nav tabs | destinations built: {bool(dest)} | entry pages rendered: {len(surface['pages'])}")
    print()
    print(f"{'LOOT':<24}{'resolves':<12}{'tier':<8}{'reached':<9}via")
    for k, r in loot_results.items():
        via = (r["nav_hits"] or r["link_hits"] or r["cite_hits"] or ["—"])[0]
        print(f"{k:<24}{r['resolves']:<12}{r['tier']:<8}{str(r['reached']):<9}{via[:60]}")
    n_cards = loot_results["cards_37"]
    if n_cards.get("paths"):
        card_reach = sum(1 for p in n_cards["paths"] if p["loads"])
        print(f"  cards_37 detail: {card_reach}/{len(n_cards['paths'])} card files exist+load")
    print()
    print(f"{'GRAVE':<28}{'served':<8}{'links':<8}{'mentions'}")
    for k, r in grave_results.items():
        links = len(r["link_hits"]) + len(r["deep_link_hits"])
        print(f"{k:<28}{str(r['served_at_declared_path']):<8}{str(links):<8}{', '.join(r['mentions_only'][:3]) or '—'}")
    print()
    print(f"LOOT reached {report['loot_reached_x_of_y']} | GRAVE reached {report['grave_reached_x_of_y']} (must be 0)")
    print(f"VERDICT: {verdict}")
    for b in breaks:
        print(f"  BREAK: {b}")
    print(f"receipt: {OUT_JSON}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
