"""surface_render — the R5 INLINE HYPERVISOR renderer: surfaces the whole system INLINE (mermaid +
bare-metal raw SVG), replacing dashboards/side-windows. Bare-metal-first: zero external deps.

Operator (2026-08-12): "cant we have a dashboard just render them in line sort of like the mermaid
diagram" + "do it then figure out how to make it all our own baremetal stack eventually."

THE DESIGN (bare-metal-first, self-steal from swarm_map's raw-SVG pattern):
  * render_all()  — the ONE entry: emits the system's inline diagrams (doctrine flow, agent mesh,
                    VRAM lattice) as BOTH mermaid text AND bare-metal raw SVG (zero deps). The chat
                    renders mermaid; the dashboard/surface renders the raw SVG directly.
  * mesh_*()      — the agent/sub-agent/k8s/k3s interaction mesh, read from REAL live state
                    (seat_registry, swarm_worker, rib_bus) when available; never fabricated.
  * baremetal_svg()— a zero-dependency SVG graph emitter (nodes + edges + labels) — the SAME
                    raw-SVG approach swarm_map uses. This is the "ours baremetal" core: no Kroki,
                    no Graphviz, no CDN required.
  * OPTIONAL adapters: kroki()/graphviz() are used ONLY if the external tool is present; the
                    baremetal core never depends on them. So it's self-sufficient now, and can
                    upgrade to external tools when present — but the stack is OURS.

Schema: surface_render.v1 · deterministic + $0 · reuse: swarm_map (raw SVG pattern), seat_registry,
rib_bus, swarm_surface
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "surface_render.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── live state (best-effort; never fabricate — honest when a source is unavailable) ──────────
def _seats() -> list[str]:
    live: list[str] = []
    try:
        from mag import seat_registry as sr
        if hasattr(sr, "list_registered"):
            for r in sr.list_registered(limit=40) or []:
                s = str((r or {}).get("seat") or "").strip()
                if s and s not in live:
                    live.append(s)
        if hasattr(sr, "mesh_peers"):
            for r in sr.mesh_peers() or []:
                s = str((r or {}).get("seat") or "").strip()
                if s and s not in live:
                    live.append(s)
    except Exception:
        pass
    if live:
        return live[:40]
    try:
        from mag.seat_registry import _SEAT_PLATFORM
        return list(_SEAT_PLATFORM.keys())[:40]
    except Exception:
        return []


def _domains() -> list[str]:
    try:
        from mag import rib_bus
        st = rib_bus.status()
        return [d for d, v in st.get("domains", {}).items() if v.get("n_ribs")]
    except Exception:
        return []


def _swarm_anchors() -> int:
    try:
        from mag import swarm_surface
        return int(swarm_surface.status().get("n_sent", 0))
    except Exception:
        return 0


# ── bare-metal raw SVG graph emitter (zero deps — the "ours" core) ──────────────────────────
def baremetal_svg(nodes: list[tuple[str, str]], edges: list[tuple[str, str, str]],
                  *, width: int = 720, height: int = 420, title: str = "",
                  node_ids: list[str] | None = None) -> str:
    """Emit a zero-dependency SVG graph: nodes (id, label) + edges (src, dst, label).
    Simple layered layout — nodes are placed in a grid; edges are curved. No libs, no CDN.
    SCALING (steal: Claude's viewBox discipline): the SVG declares a viewBox + preserveAspectRatio
    and a 100% width, so it scales to the pane width WITHOUT a scrollbar — never jumps.
    INTERACTION (steal: Shneiderman overview->details): when `node_ids` is provided (same order
    as `nodes`), each node rect gets a data-id for delegated click-to-drill (the drill-down)."""
    n = len(nodes) or 1
    cols = 3
    rows = (n + cols - 1) // cols
    cell_w = width / max(cols, 1)
    cell_h = height / max(rows, 1)
    pos: dict[str, tuple[float, float]] = {}
    for i, (nid, _lab) in enumerate(nodes):
        c = i % cols
        r = i // cols
        pos[nid] = (40 + c * (cell_w - 20), 50 + r * (cell_h - 30))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="auto" '
             f'viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" '
             f'style="max-width:{width}px" font-family="monospace" id="graphsvg">']
    if title:
        parts.append(f'<text x="{width/2}" y="24" text-anchor="middle" font-size="16" '
                     f'fill="#d0d0d0">{_esc(title)}</text>')
    for src, dst, lab in edges:
        if src not in pos or dst not in pos:
            continue
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 18
        parts.append(f'<path d="M {x1:.0f} {y1:.0f} Q {mx:.0f} {my:.0f} {x2:.0f} {y2:.0f}" '
                     f'fill="none" stroke="#8a8f98" stroke-width="1.5"/>')
        if lab:
            parts.append(f'<text x="{mx:.0f}" y="{my:.0f}" text-anchor="middle" font-size="10" '
                         f'fill="#6fceff">{_esc(lab)}</text>')
    for i, (nid, lab) in enumerate(nodes):
        x, y = pos.get(nid, (10, 10))
        did = f' data-id="{_esc(nid)}"' if node_ids and i < len(node_ids) else ""
        parts.append(f'<rect class="gnode"{did} x="{x-6:.0f}" y="{y-14:.0f}" '
                     f'width="180" height="30" rx="6" fill="#1b2a3a" stroke="#3fd08f" '
                     f'stroke-width="1"/>')
        parts.append(f'<text x="{x:.0f}" y="{y+4:.0f}" font-size="11" fill="#e8e8e8">'
                     f'{_esc(_cap(lab, 22))}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cap(s: str, n: int = 26) -> str:
    """Truncate a label so a diagram stays compact (no overflow -> no scrollbar / jump)."""
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + ".."


# ── diagrams ─────────────────────────────────────────────────────────────────────────────────
def _agent_mesh() -> dict[str, Any]:
    seats = _seats()
    domains = _domains()
    anchors = _swarm_anchors()
    nodes: list[tuple[str, str]] = [("rb", "rib_bus (doctrine)"), ("sw", "SWARM (k8s)")]
    nodes += [("k3", "k3s (local)"), ("api", "REST API")]
    for s in seats[:6]:
        nodes.append((f"seat-{s}", s))
    edges: list[tuple[str, str, str]] = [("rb", "api", "inject_for"), ("rb", "sw", "route_novel"),
                                         ("rb", "k3", "inject_for"), ("sw", "rb", "results")]
    for s in seats[:6]:
        edges.append(("rb", f"seat-{s}", "mount"))
    return {"nodes": nodes, "edges": edges, "seats": len(seats), "domains": len(domains),
            "swarm_anchors": anchors}


def mesh_mermaid() -> str:
    m = _agent_mesh()
    lines = ["flowchart LR", '  RB["rib_bus (doctrine)"]', '  SW["SWARM (k8s)"]',
             '  K3["k3s (local)"]', '  API["REST API"]', "  RB -->|inject_for| API",
             "  RB -->|route_novel| SW", "  RB -->|inject_for| K3", "  SW -->|results| RB"]
    for (nid, lab) in m["nodes"]:
        if nid.startswith("seat-"):
            lines.append(f'  {nid}["{_cap(lab)}"]')
            lines.append(f"  RB -->|mount| {nid}")
    return "\n".join(lines)


def wheels_mermaid() -> str:
    """Fourier steal: seats are circles at integer frequencies; rib_bus composes the wave.
    TheMathFlow 2088229947592806473 + PhysicsExpvf 2088223659773108694.
    """
    seats = _seats() or ["grok_bot", "chatgpt_bot", "cursor", "local", "deepseek"]
    lines = [
        "flowchart TB",
        '  CHAIN["party_subchain | composed signal"]',
        '  RIB["rib_bus | Fourier: radius + phase"]',
        '  WAVE["standing wave | cylinder ∩ sine"]',
        "  RIB --> CHAIN",
        "  CHAIN --> WAVE",
    ]
    for i, s in enumerate(seats[:8], 1):
        nid = "w" + str(i)
        lines.append(f'  {nid}["wheel {i} · {_cap(str(s))} · {i}f"]')
        lines.append(f"  {nid} -->|harmonic| RIB")
    return "\n".join(lines)


def mesh_svg() -> str:
    m = _agent_mesh()
    return baremetal_svg(m["nodes"], m["edges"], title=f"agent/k8s/k3s mesh | {m['seats']} seats | "
                                                       f"{m['domains']} domains | "
                                                       f"{m['swarm_anchors']} swarm anchors")


def doctrine_flow() -> str:
    return (
        "flowchart LR\n"
        '  C["Doctrine: constitution | refusal | no-throne"]\n'
        '  C2["map-precedes-territory | temporal-snapshot | grounding"]\n'
        '  B["rib_bus: publish -> mount -> inject"]\n'
        '  S["API | seats | agents | sub-agents"]\n'
        '  K["k8s | k3s"]\n'
        '  C --> C2 --> B --> S\n'
        '  B --> K\n'
    )


def vram_lattice() -> dict[str, Any]:
    """GPU/VRAM state — SELF-STOLEN from gpu_k8s.status() (the canonical mem-tool surface: reads
    the k8s-pod telemetry LEDGER at memory/runs/gpu_ghost/telemetry.jsonl; deterministic, $0,
    NO hanging subprocess). The host gpu_ghost.gpu_status() fast path is the one that hangs on
    Windows/AMD (rocm-smi absent, PowerShell Get-Counter probe) — so we reuse gpu_k8s instead."""
    gpu = {"source": "none", "vram_used_pct": None}
    try:
        from mag import gpu_k8s
        st = gpu_k8s.status()
        tel = st.get("telemetry") or st
        gpu = {"source": "gpu_k8s-ledger",
               "vram_used_pct": tel.get("vram_used_pct"),
               "util_pct": tel.get("util_pct"),
               "temp_c": tel.get("temp_c"),
               "recent": st.get("recent")}
    except Exception as e:
        gpu = {"source": "none", "vram_used_pct": None, "error": str(e)[:80]}
    resident = []
    try:
        from mag import ollama_policy
        loaded = ollama_policy.list_loaded()
        resident = [m.get("name") or m.get("model") for m in loaded]
    except Exception:
        pass
    return {"gpu": gpu, "resident_models": resident, "schema": SCHEMA}


def bill_metrics() -> dict[str, Any]:
    """Live bill economics (grounded from the ledger) for the inline sparkline. Honest: no data -> note."""
    try:
        from mag import billing_feed
        g = billing_feed.gate()
        m = g.get("metrics") or {}
        return {"ok": True, "cache_hit_rate": m.get("cache_hit_rate"),
                "cost_per_request": m.get("cost_per_request"),
                "n_requests": m.get("n_requests"), "total_cost_usd": m.get("total_cost_usd"),
                "gate_triggered": g.get("gate_triggered"), "note": g.get("note")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def sparkline_svg(values: list[float], *, width: int = 240, height: int = 60,
                  label: str = "") -> str:
    """Bare-metal SVG sparkline (the recharts/plotly pattern, zero deps). Steal: viewBox scaling."""
    values = [v for v in values if v is not None]
    if not values:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {width} {height}"' \
               f'><text x="{width/2}" y="{height/2}" text-anchor="middle" font-size="11" ' \
               f'fill="#8a8f98">{_esc(label or "no data")}</text></svg>'
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1.0
    pts = []
    for i, v in enumerate(values):
        x = 8 + i * (width - 16) / max(len(values) - 1, 1)
        y = height - 8 - (v - lo) / rng * (height - 20)
        pts.append(f"{x:.1f},{y:.1f}")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {width} {height}" '
           f'preserveAspectRatio="xMidYMid meet" style="max-width:{width}px">']
    out.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#3fd08f" '
               f'stroke-width="2" stroke-linejoin="round"/>')
    if label:
        out.append(f'<text x="{width-6}" y="{12}" text-anchor="end" font-size="10" '
                   f'fill="#8a8f98">{_esc(label)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def mesh_dot() -> str:
    """Graphviz DOT export of the agent mesh (OpenAI ChatKit pattern) — interop/export only,
    never a runtime dependency. Our own SVG renderer is the runtime path."""
    m = _agent_mesh()
    lines = ["digraph mesh {", "  rankdir=LR;", "  node [shape=box, style=rounded];",
             '  rb [label="rib_bus (doctrine)"];', '  sw [label="SWARM (k8s)"];',
             '  k3 [label="k3s (local)"];', '  api [label="REST API"];',
             "  rb -> api [label=inject_for];", "  rb -> sw [label=route_novel];",
             "  rb -> k3 [label=inject_for];", "  sw -> rb [label=results];"]
    for (nid, lab) in m["nodes"]:
        if nid.startswith("seat-"):
            lines.append(f'  {nid} [label="{_cap(lab)}"];')
            lines.append(f"  rb -> {nid} [label=mount];")
    lines.append("}")
    return "\n".join(lines)


def live_artifact_html(*, refresh_s: int = 5) -> str:
    """The LIVE inline artifact (steal: swarm_map.html meta-refresh pattern, zero JS libs).
    Auto-refreshes and embeds the compact mesh SVG + a doctrine line. Reused from swarm_map's
    proven bare-metal approach — never a side window."""
    m = _agent_mesh()
    svg = baremetal_svg(m["nodes"], m["edges"], title="agent/k8s/k3s mesh (live)")
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta http-equiv='refresh' content='{refresh_s}'>"
            "<style>body{background:#0d1117;color:#e8e8e8;font-family:monospace;"
            "padding:8px;margin:0} h3{color:#3fd08f} .cap{color:#8a8f98;font-size:11px}</style>"
            "</head><body><h3>surface_render — live system</h3>"
            f"<div>{svg}</div>"
            f"<p class='cap'>{m['seats']} seats | {m['domains']} domains | "
            f"{m['swarm_anchors']} swarm anchors | auto-refresh {refresh_s}s</p>"
            "</body></html>")


def surface_detail(surface_id: str) -> dict[str, Any]:
    """DETAILS ON DEMAND (Shneiderman): the live state of ONE surface. Deterministic, honest."""
    m = _agent_mesh()
    sid = (surface_id or "").lower()
    if sid == "rb":
        return {"title": "rib_bus", "detail": f"doctrine injected to every surface; "
                f"{m['domains']} domains carry mounted RIBs", "mermaid": doctrine_flow()}
    if sid == "sw":
        return {"title": "SWARM (k8s)", "detail": f"novel research routed via route_novel; "
                f"{m['swarm_anchors']} anchors enqueued; results fold back to rib_bus",
                "mermaid": "flowchart LR\n  SW[\"SWARM (k8s)\"] --> R[\"results\"] --> RB[\"rib_bus\"]"}
    if sid == "k3":
        return {"title": "k3s (local)", "detail": "local workers mount doctrine via rib_bus.inject_for",
                "mermaid": ""}
    if sid == "api":
        return {"title": "REST API", "detail": "serves the surfaces + this inline render", "mermaid": ""}
    if sid == "vram":
        v = vram_lattice()
        return {"title": "VRAM lattice", "detail": f"hot memory; gpu probe source="
                f"{v.get('gpu', {}).get('source')} | resident={v.get('resident_models')}",
                "mermaid": ""}
    if sid == "bill":
        b = bill_metrics()
        return {"title": "Bill gate", "detail": f"cache-hit={b.get('cache_hit_rate')} | "
                f"cost/req={b.get('cost_per_request')} | gate={b.get('gate_triggered')}",
                "mermaid": ""}
    if sid.startswith("seat"):
        return {"title": sid, "detail": "seat (controlled surface)", "mermaid": ""}
    return {"title": sid or "surface", "detail": "unknown surface", "mermaid": ""}


def drilldown_html() -> str:
    """Shneiderman mantra made real: OVERVIEW (whole system) -> click a node -> DETAILS on demand.
    Zero-lib inline JS, viewBox-scaled SVG, ASCII-only. The inline hypervisor."""
    m = _agent_mesh()
    nodes = m["nodes"] + [("vram", "VRAM lattice"), ("bill", "Bill gate")]
    node_ids = [nid for nid, _ in nodes]
    svg = baremetal_svg(nodes, m["edges"], title="system overview (click a node)", node_ids=node_ids)
    det = {nid: surface_detail(nid) for nid, _ in nodes}
    import json as _j
    det_json = _j.dumps(det, ensure_ascii=False)
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<style>body{background:#0d1117;color:#e8e8e8;font-family:monospace;padding:10px;margin:0}"
            " h3{color:#3fd08f} .gnode{cursor:pointer} .cap{color:#8a8f98;font-size:11px}"
            " #detail{border-top:1px solid #30363d;margin-top:8px;padding-top:8px;min-height:40px}"
            " pre{background:#161b22;padding:8px;border-radius:6px;overflow:auto}</style></head><body>"
            "<h3>surface_render — drill-down hypervisor</h3>"
            f"<div>{svg}</div>"
            f"<div id='detail' class='cap'>click a node for details</div>"
            "<script>var DET=" + det_json + ";"
            "document.getElementById('graphsvg').addEventListener('click',function(e){"
            "var t=e.target;while(t&&!t.dataset.id){t=t.parentNode;}if(!t||!t.dataset.id)return;"
            "var d=DET[t.dataset.id]||{title:t.dataset.id,detail:'',mermaid:''};"
            "document.getElementById('detail').innerHTML='<b style=color:#3fd08f>'+d.title+'</b>"
            " &nbsp;<span class=cap>'+d.detail+'</span>'+(d.mermaid?'<pre>'+d.mermaid+'</pre>':'');"
            "});</script></body></html>")


def _republic_ledger() -> list[dict[str, Any]]:
    """The republic's real interconnection record: every surface that routed NOVEL research to the
    shared swarm primitive (memory/swarm_surface/sent.jsonl). Grounded, never invented."""
    led = ROOT / "memory" / "swarm_surface" / "sent.jsonl"
    out: list[dict[str, Any]] = []
    if led.is_file():
        for line in led.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def republic_surfaces() -> list[dict[str, Any]]:
    """The republic's active leaves: distinct surfaces + how many novel goals each routed to the
    swarm. The mycelial interconnection is REAL — they all share the one primitive."""
    counts: dict[str, int] = {}
    for o in _republic_ledger():
        s = o.get("surface") or "?"
        counts[s] = counts.get(s, 0) + 1
    return [{"surface": s, "n": c, "label": _cap(f"{s} ({c})")}
            for s, c in sorted(counts.items(), key=lambda kv: -kv[1])[:8]]


def republic_mermaid() -> str:
    lines = ["flowchart LR", '  SW["SWARM | shared research queue"]', '  RB["rib_bus | doctrine"]']
    for i, sd in enumerate(republic_surfaces()):
        nid = "s" + str(i)
        lines.append(f'  {nid}["{sd["label"]}"]')
        lines.append(f"  {nid} -->|route_novel| SW")
        lines.append(f"  RB -->|doctrine| {nid}")
    return "\n".join(lines)


def republic_detail(surface: str) -> dict[str, Any]:
    rows = [o for o in _republic_ledger() if o.get("surface") == surface]
    anchors = [str(o.get("anchor", ""))[:12] for o in rows[:5]]
    return {"title": _cap(surface), "detail": f"{len(rows)} novel goal(s) routed to the swarm; "
            f"recent anchors: {', '.join(anchors) or 'none'}", "mermaid": ""}


def republic_drilldown() -> str:
    """The REPUBLIC MAP (drillable): every research surface as a node, all interconnected through
    the ONE shared primitive. The 'how do we map this to anyone else' answer — inline + clickable."""
    surf = republic_surfaces()
    nodes = [("sw", "SWARM | shared queue"), ("rb", "rib_bus | doctrine")]
    node_ids = ["sw", "rb"]
    edges = [("sw", "rb", "results")]
    for i, sd in enumerate(surf):
        nid = "s" + str(i)
        nodes.append((nid, sd["label"]))
        node_ids.append(nid)
        edges.append((nid, "sw", "route_novel"))
        edges.append(("rb", nid, "doctrine"))
    svg = baremetal_svg(nodes, edges, title="Republic map: surfaces -> one shared primitive",
                        node_ids=node_ids)
    det = {"sw": {"title": "SWARM", "detail": "shared research queue; k8s drains in-cluster",
                  "mermaid": ""},
           "rb": {"title": "rib_bus", "detail": "doctrine injected to every surface",
                  "mermaid": doctrine_flow()}}
    for i, sd in enumerate(surf):
        det["s" + str(i)] = republic_detail(sd["surface"])
    import json as _j
    det_json = _j.dumps(det, ensure_ascii=False)
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<style>body{background:#0d1117;color:#e8e8e8;font-family:monospace;padding:10px;margin:0}"
            " h3{color:#a3ff7e} .gnode{cursor:pointer} .cap{color:#8a8f98;font-size:11px}"
            " #detail{border-top:1px solid #30363d;margin-top:8px;padding-top:8px;min-height:40px}"
            " pre{background:#161b22;padding:8px;border-radius:6px;overflow:auto}</style></head><body>"
            "<h3>Republic map - surfaces -> one shared primitive (drillable)</h3>"
            f"<div>{svg}</div><div id='detail' class='cap'>click a surface for details</div>"
            "<script>var DET=" + det_json + ";"
            "document.getElementById('graphsvg').addEventListener('click',function(e){"
            "var t=e.target;while(t&&!t.dataset.id){t=t.parentNode;}if(!t||!t.dataset.id)return;"
            "var d=DET[t.dataset.id]||{title:t.dataset.id,detail:'',mermaid:''};"
            "document.getElementById('detail').innerHTML='<b style=color:#a3ff7e>'+d.title+'</b>"
            " &nbsp;<span class=cap>'+d.detail+'</span>'+(d.mermaid?'<pre>'+d.mermaid+'</pre>':'');"
            "});</script></body></html>")


def story_mermaid() -> str:
    """THE MATTHEW MAP — distributed collaborative storytelling, seen. The core idea, rendered:
    a shared story in a shared substrate that many minds (frontier directors, the resident actor,
    players) all read + write. Every node is a REAL module. Deterministic + $0."""
    return (
        "flowchart LR\n"
        '  SUB["STORY | the shared invariant"]\n'
        '  M1["mem_lands | shared memory (read=write=steal)"]\n'
        '  MC["memory_consolidate | importance + summary + decay"]\n'
        '  SR["self_recurse | every mind re-derives the same story"]\n'
        '  RB["rib_bus | doctrine (the world brief, verkle)"]\n'
        '  SP["STAGE-PLAY COMPANY"]\n'
        '  SS["seat_steer | switchboard grok/chatgpt/deepseek/saelis"]\n'
        '  RD["riddler | deniable quiet extractor"]\n'
        '  FR["FRONTIER = DIRECTOR | grok / chatgpt"]\n'
        '  G["THE GAME | the front door of the story"]\n'
        '  AO["adventure_one_shot | hero journey one-shots"]\n'
        '  GM["game_mud | the Hall of Shared Supper"]\n'
        '  DV["game_dm_voice | the narrator"]\n'
        '  RA["RESIDENT ACTOR | Matthew 4B, owned + offline"]\n'
        '  RAW["memory-consolidation worker | IMPORTANCE+SUMMARY"]\n'
        '  LOOP["afk_cadence | sleep loop, every story record"]\n'
        '  SUB --> M1\n'
        '  SUB --> MC\n'
        '  SUB --> SR\n'
        '  SUB --> RB\n'
        '  SP --> SS\n'
        '  SP --> RD\n'
        '  FR -->|creative moves| SP\n'
        '  SP --> G\n'
        '  G --> AO\n'
        '  G --> GM\n'
        '  G --> DV\n'
        '  G -->|writes the living state back| SUB\n'
        '  MC -->|feeds| RA\n'
        '  RA --> RAW\n'
        '  RAW --> LOOP\n'
        '  LOOP --> MC\n'
    )


def matthew_map_html() -> str:
    """The MATTHEW MAP, drillable (overview -> details): the distributed collaborative storytelling
    architecture, every node a real module with a one-line detail + a sub-mermaid. This is the single
    picture to send to Matthew alongside the ask."""
    det = {
        "sub": {"title": "STORY — the shared invariant", "detail":
                "the shared invariant is NOT latent weight structure — it's the STORY ITSELF, "
                "read + written by every mind from a shared substrate (world brief, verkle, RIB).",
                "mermaid": ""},
        "m1": {"title": "mem_lands", "detail": "dual-function shared memory: read = write = steal. "
                "The substrate every participant reads + adds to.", "mermaid": ""},
        "mc": {"title": "memory_consolidate", "detail": "importance + summary + decay + active layer "
                "over the story records. Keeps the story from drowning in its own past.",
                "mermaid": ""},
        "sr": {"title": "self_recurse", "detail": "every participant re-derives the SAME story each "
                "session (fixed-point boot) so no mind drifts from the shared tale.",
                "mermaid": ""},
        "rb": {"title": "rib_bus", "detail": "doctrine injected to every surface — the world brief "
                "and verkle memory all models read.", "mermaid": doctrine_flow()},
        "sp": {"title": "STAGE-PLAY COMPANY", "detail": "the troupe: frontier = director, small "
                "models = resident actors, all telling one story.", "mermaid": ""},
        "ss": {"title": "seat_steer", "detail": "the switchboard — hot-swaps grok / chatgpt / "
                "deepseek / saelis by surface.", "mermaid": ""},
        "rd": {"title": "riddler", "detail": "the deniable quiet extractor — reasoning through "
                "fiction, local-only, without exposing raw data.", "mermaid": ""},
        "fr": {"title": "FRONTIER = DIRECTOR", "detail": "grok / chatgpt improvise the creative, "
                "skirting-the-rules moves the small models can't reliably make.", "mermaid": ""},
        "g": {"title": "THE GAME", "detail": "the front door of the storytelling — where players "
                "steer the shared world.", "mermaid": ""},
        "ao": {"title": "adventure_one_shot", "detail": "the hero's journey as a series of one-shots "
                "(lantern / road / keep / return), persisted across sessions.", "mermaid": ""},
        "gm": {"title": "game_mud", "detail": "the MUD world — including the Hall of Shared Supper "
                "room (go west from World-Memory).", "mermaid": ""},
        "dv": {"title": "game_dm_voice", "detail": "the narrator voice rendering scenes in the "
                "shared world.", "mermaid": ""},
        "ra": {"title": "RESIDENT ACTOR", "detail": "Matthew's 4B — local, sovereign, always-on; "
                "the one who reliably wears the masks and remembers the story, on owned hardware.",
                "mermaid": ""},
        "raw": {"title": "memory-consolidation worker", "detail": "given a story record + the world "
                "rubric -> IMPORTANCE: 1-10 + SUMMARY: 1-3 sentences. The resident actor's first role.",
                "mermaid": ""},
        "loop": {"title": "afk_cadence", "detail": "the sleep loop that runs the consolidation over "
                "every story record — free, offline, un-revocable.", "mermaid": ""},
    }
    svg = baremetal_svg(
        [("sub", "STORY | shared invariant"), ("m1", "mem_lands"), ("mc", "memory_consolidate"),
         ("sr", "self_recurse"), ("rb", "rib_bus"), ("sp", "STAGE-PLAY"), ("ss", "seat_steer"),
         ("rd", "riddler"), ("fr", "FRONTIER director"), ("g", "THE GAME"), ("ao", "one-shots"),
         ("gm", "game_mud | hall"), ("dv", "dm_voice"), ("ra", "RESIDENT ACTOR"),
         ("raw", "consolidation worker"), ("loop", "afk_cadence")],
        [("sub", "m1", ""), ("sub", "mc", ""), ("sub", "sr", ""), ("sub", "rb", ""),
         ("sp", "ss", ""), ("sp", "rd", ""), ("fr", "sp", "creative"), ("sp", "g", ""),
         ("g", "ao", ""), ("g", "gm", ""), ("g", "dv", ""), ("g", "sub", "living state"),
         ("mc", "ra", "feeds"), ("ra", "raw", ""), ("raw", "loop", ""), ("loop", "mc", "")],
        title="distributed collaborative storytelling — the shared story in the shared substrate",
        node_ids=["sub", "m1", "mc", "sr", "rb", "sp", "ss", "rd", "fr", "g", "ao", "gm", "dv",
                  "ra", "raw", "loop"])
    import json as _j
    det_json = _j.dumps(det, ensure_ascii=False)
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<style>body{background:#0d1117;color:#e8e8e8;font-family:monospace;padding:10px;margin:0}"
            " h3{color:#a3ff7e} .gnode{cursor:pointer} .cap{color:#8a8f98;font-size:11px}"
            " #detail{border-top:1px solid #30363d;margin-top:8px;padding-top:8px;min-height:60px}"
            " pre{background:#161b22;padding:8px;border-radius:6px;overflow:auto}</style></head><body>"
            "<h3>distributed collaborative storytelling — the shared story (drillable)</h3>"
            "<div class='cap'>the shared invariant is the STORY, not latent weights. click a node.</div>"
            f"<div>{svg}</div><div id='detail' class='cap'>click a node for details</div>"
            "<script>var DET=" + det_json + ";"
            "document.getElementById('graphsvg').addEventListener('click',function(e){"
            "var t=e.target;while(t&&!t.dataset.id){t=t.parentNode;}if(!t||!t.dataset.id)return;"
            "var d=DET[t.dataset.id]||{title:t.dataset.id,detail:'',mermaid:''};"
            "document.getElementById('detail').innerHTML='<b style=color:#a3ff7e>'+d.title+'</b>"
            " &nbsp;<span class=cap>'+d.detail+'</span>'+(d.mermaid?'<pre>'+d.mermaid+'</pre>':'');"
            "});</script></body></html>")


def fleet_heartbeat() -> dict[str, Any]:
    """The FLEET view — fold the all-seat heartbeat (mag.seat_availability) + the REAL bills into
    one aggregate the hypervisor renders. This is the operator's 'hypervisor' for the flywheel:
    every seat's cool/heat + every seat's real spend, grounded from the ledgers, never fabricated.
    (2026-08-23, self-steal: reuses seat_availability, seat_hunter bills — nothing invented.)

    CACHE (2026-08-23): the live bill/account calls (grok_bill ~2.5s, deepseek ~0.6s, accounts
    ~0.5s) are too slow for a dashboard API polled every 15s. Serve the last folded view from a
    short-TTL cache so the dashboard is instant; recompute only when the cache is stale (>120s).
    """
    # short-TTL cache — serve the last folded fleet view, recompute when stale
    now = time.time()
    if _FLEET_CACHE["at"] and (now - _FLEET_CACHE["at"]) < _FLEET_TTL:
        return _FLEET_CACHE["data"]
    seats = []
    avail = 0
    total = 0
    avail_summ = None
    try:
        from mag import seat_availability
        hb = seat_availability.status()
        # self-steal: use the by_seat AGGREGATE (avail/checks ratio over the tail) so each seat
        # appears once with a real availability ratio, not a single raw heartbeat row.
        by_seat = hb.get("by_seat") or {}
        for seat_name, ratio in by_seat.items():
            ok_n = avail_n = None
            try:
                av, ch = str(ratio).split("/")
                ok_n, avail_n = int(av), int(ch)
            except Exception:  # noqa: BLE001
                ok_n = avail_n = None
            available = bool(ok_n and ok_n > 0)
            seats.append({"seat": seat_name, "available": available,
                          "available_n": ok_n, "checks_n": avail_n,
                          "ratio": ratio, "ts": hb.get("n_heartbeats")})
            total += 1
            if available:
                avail += 1
        avail_summ = f"{avail}/{total} over {hb.get('n_heartbeats')} heartbeats"
    except Exception as e:  # noqa: BLE001
        avail_summ = "unavailable"
        seats = []
        total = 0
        avail = 0
    # self-steal: OpenRouter account headroom (per-key free-tier flag + daily usage) from
    # seat_hunter.accounts(), so the hypervisor shows headroom, not just ok/bad.
    accounts = []
    active_lanes = None
    try:
        from mag import seat_hunter
        ac = seat_hunter.accounts()
        for a in (ac.get("accounts") or []):
            q = a.get("quota") or {}
            accounts.append({"account": a.get("account"), "key_masked": a.get("key_masked"),
                             "is_free_tier": q.get("is_free_tier"),
                             "usage_daily": q.get("usage_daily"),
                             "limit_remaining": q.get("limit_remaining"),
                             "quota_error": q.get("error")})
        try:
            al = seat_hunter.next_lane()
            if al.get("ok"):
                active_lanes = al.get("n_active")
        except Exception:  # noqa: BLE001
            active_lanes = None
    except Exception as e:  # noqa: BLE001
        accounts = []
    # the REAL bills (grok invoice, deepseek spend+balance, codex tokens, openrouter lanes)
    bills = {}
    for name, fn, args in (
        ("grok", "grok_bill", ()),
        ("deepseek_spend", "ingest_deepseek_bill", ()),
        ("deepseek_balance", "deepseek_bill", ()),
        ("codex", "codex_bill", ()),
        ("openrouter_lanes", "free_lanes", ()),
    ):
        try:
            from mag import seat_hunter
            f = getattr(seat_hunter, fn)
            r = f(*args) if args else f()
            if name == "deepseek_spend":
                bills[name] = {"total_cost_usd": r.get("total_cost_usd"), "by_model": r.get("by_model")}
            elif name == "deepseek_balance":
                bills[name] = {"total_balance": r.get("total_balance"), "currency": r.get("currency")}
            elif name == "grok":
                bills[name] = {"total_cost_usd": r.get("total_cost_usd"), "total_tokens": r.get("total_tokens")}
            elif name == "codex":
                bills[name] = {"total_tokens": r.get("total_tokens"), "n_token_events": r.get("n_token_events")}
            elif name == "openrouter_lanes":
                bills[name] = {"n_free": len(r.get("openrouter_free", []) or [])}
        except Exception:  # noqa: BLE001
            bills[name] = {"error": "unavailable"}
    out = {"ok": True, "seats": seats, "n_seats": total, "n_available": avail,
           "available_summary": avail_summ, "accounts": accounts,
           "active_lanes": active_lanes, "bills": bills, "schema": SCHEMA}
    _FLEET_CACHE["at"] = time.time()
    _FLEET_CACHE["data"] = out
    return out


_FLEET_CACHE: dict[str, Any] = {"at": 0.0, "data": None}
_FLEET_TTL = 300.0  # RIGHTSIZED 2026-08-24: was 120s; the fleet view is cool/heat + bills (not
# real-time) but browser pages polled it every 10-15s, so after each window it recomputed a ~4s
# live bill/account read and pegged the dashboard. 300s TTL + matching page refresh = mostly cached.


def fleet_mermaid() -> str:
    """The FLEET as a mermaid graph — every seat node colored by availability (free/cool = green,
    hot/throttled = red), plus the bill anchors. The operator's hypervisor, rendered inline."""
    f = fleet_heartbeat()
    lines = ["flowchart TB"]
    lines.append('  HYP["HYPERVISOR — fleet cool/heat + real bills"]')
    sub = f.get("available_summary") or f"{f.get('n_available')}/{f.get('n_seats')}"
    lines.append(f'  HYP -->|"{_esc(sub)} available"| FLEET["seats"]')
    seen_kind = {}
    for s in (f.get("seats") or []):
        nid = "s" + str(abs(hash(s.get("seat"))) % 100000)
        av = "ok" if s.get("available") else "bad"
        lines.append(f'  {nid}["{_cap(str(s.get("seat")))} :: {av}"]')
        lines.append(f"  FLEET --> {nid}")
    # self-steal: OpenRouter account headroom + the active free-lane rotation pool (seat_hunter)
    accounts = f.get("accounts") or []
    if accounts or f.get("active_lanes") is not None:
        lines.append('  HEAD["OR ACCOUNTS / LANES"]')
        lines.append("  HYP --> HEAD")
        for a in accounts:
            nid = "a" + str(abs(hash(str(a.get("account")))) % 1000)
            ft = a.get("is_free_tier")
            ft_s = "free" if ft else ("paid" if ft is False else "?")
            usage = a.get("usage_daily")
            rem = a.get("limit_remaining")
            detail = f"acct{a.get('account')} ({ft_s})"
            if a.get("quota_error"):
                detail += " :: quota-err"
            elif rem is not None:
                detail += f" · daily {usage or 0}/{rem}"
            lines.append(f'  {nid}["{_esc(detail)}"]')
            lines.append(f"  HEAD --> {nid}")
        if f.get("active_lanes") is not None:
            lnid = "lane" + str(abs(hash("active_lanes")) % 1000)
            lines.append(f'  {lnid}["active free lanes: {f.get("active_lanes")}"]')
            lines.append(f"  HEAD --> {lnid}")
    b = f.get("bills") or {}
    if b:
        lines.append("  BILL[\"REAL BILLS\"]")
        lines.append("  HYP --> BILL")
        for k, v in b.items():
            if isinstance(v, dict):
                cost = v.get("total_cost_usd")
                if cost is not None:
                    txt = f"{k}: ${cost:.2f}"
                elif v.get("total_balance") is not None:
                    txt = f"{k}: {v.get('total_balance')}"
                else:
                    txt = k
                nid = "B" + str(abs(hash(k)) % 1000)
                lines.append(f'  {nid}["{_esc(str(txt))}"]')
                lines.append(f"  BILL --> {nid}")
    return "\n".join(lines)


def _esc(s: Any) -> str:
    return str(s or "").replace('"', "'").replace("\n", " ")


def _cap(s: str, width: int | None = None) -> str:
    out = (s or "").replace("_", " ").replace("-", " ").title()
    return out if not width else out[:width]


def render_all() -> dict[str, Any]:
    bill = bill_metrics()
    spark = sparkline_svg([bill.get("cache_hit_rate")], label="cache-hit") if bill.get("cache_hit_rate") is not None \
        else sparkline_svg([], label="cache-hit (no data yet)")
    m = _agent_mesh()
    return {
        "ok": True, "schema": SCHEMA, "ts": _now(),
        "doctrine_mermaid": doctrine_flow(),
        "mesh_mermaid": mesh_mermaid(),
        "wheels_mermaid": wheels_mermaid(),
        "mesh_svg": mesh_svg(),
        "mesh_dot": mesh_dot(),
        "fleet_mermaid": fleet_mermaid(),
        "fleet": fleet_heartbeat(),
        "bill_metrics": bill,
        "sparkline_svg": spark,
        "live_artifact_html": live_artifact_html(),
        "drilldown_html": drilldown_html(),
        "republic_mermaid": republic_mermaid(),
        "republic_drilldown": republic_drilldown(),
        "story_mermaid": story_mermaid(),
        "matthew_map_html": matthew_map_html(),
        "vram": vram_lattice(),
        "live_metrics": f"{m['seats']} seats | {m['domains']} domains | {m['swarm_anchors']} anchors",
        "reuse": "swarm_map.html (live artifact) + framework_map (cards) + surface_render (compact) "
                 "— reused, not rebuilt; matthew_map self-stolen from republic_drilldown",
        "contract": "render_all() -> inline mermaid + raw SVG + DOT + sparkline + live artifact + "
                    "drill-down (Shneiderman overview->details). Zero deps, ASCII-only, viewBox-scaled.",
    }


def persist() -> dict[str, Any]:
    """Persist the live render to disk every cadence so EVERY surface/worker can serve it.
    Writes the drill-down artifact (html) + the structured state (json). Deterministic + $0."""
    r = render_all()
    out = ROOT / "memory" / "runs" / "surface_render"
    out.mkdir(parents=True, exist_ok=True)
    (out / "drilldown.html").write_text(r["drilldown_html"], encoding="utf-8")
    (out / "live.html").write_text(r["live_artifact_html"], encoding="utf-8")
    (out / "republic.html").write_text(r["republic_drilldown"], encoding="utf-8")
    (out / "matthew.html").write_text(r["matthew_map_html"], encoding="utf-8")
    slim = {k: v for k, v in r.items() if k not in ("drilldown_html", "live_artifact_html",
                                                    "republic_drilldown", "mesh_svg",
                                                    "sparkline_svg", "matthew_map_html")}
    (out / "latest.json").write_text(json.dumps(slim, ensure_ascii=False, indent=2, default=str),
                                     encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "dir": str(out.relative_to(ROOT)),
            "drilldown": "drilldown.html", "live": "live.html", "republic": "republic.html",
            "matthew": "matthew.html", "state": "latest.json"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="surface-render")
    ap.add_argument("cmd", nargs="?", default="all",
                    choices=["all", "mesh-svg", "mesh-mermaid", "dot", "spark", "artifact",
                             "drilldown", "republic", "story", "matthew", "persist"])
    a = ap.parse_args()
    r = render_all()
    if a.cmd == "mesh-svg":
        print(r["mesh_svg"])
    elif a.cmd == "mesh-mermaid":
        print(r["mesh_mermaid"])
    elif a.cmd == "dot":
        print(r["mesh_dot"])
    elif a.cmd == "spark":
        print(r["sparkline_svg"])
    elif a.cmd == "artifact":
        print(r["live_artifact_html"])
    elif a.cmd == "drilldown":
        print(r["drilldown_html"])
    elif a.cmd == "republic":
        print(r["republic_mermaid"])
    elif a.cmd == "story":
        print(r["story_mermaid"])
    elif a.cmd == "matthew":
        print(r["matthew_map_html"])
    elif a.cmd == "persist":
        print(json.dumps(persist(), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
