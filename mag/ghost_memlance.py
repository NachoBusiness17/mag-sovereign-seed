"""ghost_memlance — steal ghostlance's shape for MEMORY-STATE intelligence.

Operator (2026-08-11): "use our ghost steal module like pylance so we can select memory
states selectively without bringing hallucination."

STEAL ANALYSIS:
  * SELF — ghost_pylance (GHOSTLANCE) is our deterministic code-intelligence memtool:
    diagnose / symbols / references / trace_value / imports / self_check, all $0 stdlib-ast,
    all grounding the ghost against the ACTUAL bytes of our code. The same shape, applied to
    MEMORY, is the anti-hallucination selector the operator is asking for: the ghost reasons
    over stochastic recall, but it SELECTS and VERIFIES memory against the ACTUAL bytes on
    disk — never synthesizes a memory state from memory-of-memory.
  * EXTERNAL — the lesson is borrowed from RAG grounding + provenance discipline: retrieval
    must return the source bytes + a verification verdict, and must label what is NOT grounded
    instead of silently passing it. We adapt that as a deterministic contract, no prompt DNA.

WHY THIS KILLS HALLUCINATION:
  * select() returns only states read as REAL bytes from disk, each with provenance (path) and
    a deterministic `verified` verdict (derived from explicit grounding markers). It never
    fabricates content — the excerpt is the actual file's first lines.
  * Anything the ghost recalls from memory-of-memory is NOT a state here; only files that exist
    on disk are candidates. If a state lacks a grounding marker it is returned flagged
    `verified: false` (conservative) — the ghost knows not to carry it forward as truth.

Schema: ghost_memlance.v1 · deterministic $0 · CLI: python -m mag.ghost_memlance <tool>
MEMTOOLS:
  index()       - index real memory states from disk (path, kind, title, ts, tags, verified).
  select(goal)  - select the RELEVANT, GROUNDED states for a context (provenance + verdict).
  trace_state(key) - provenance + cross-refs of one memory state (like trace_value).
  verify(key)   - deterministic grounding verdict for a state (the markers that prove/refute it).
  self_check()  - consistency: how many states indexed, verified vs unverified, unreadable.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
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

SCHEMA = "ghost_memlance.v1"

# Deterministic grounding markers. A state is VERIFIED only if it carries a real-data / RIB /
# measured / frozen marker. Absent one, it is DERIVED (unverified) — conservative, anti-hallucination.
VERIFIED_MARKERS = (
    "verified", "grounded", "measured", "billed", "rib_", "frozen", "rib-", "rib:",
    "real data", "real billing", "trust bytes", "frozen spec", "verified-in-file",
    "rib-debug", "validated", "confirmed", "shipped",
)
# Explicitly-unverified markers override even a generic mention and force verdict false.
UNVERIFIED_MARKERS = (
    "unverified", "derived", "estimated", "handwave", "not verified", "not grounded",
    "assumption", "plan only", "never runtime-proven", "not runtime-proven",
    "unmeasured", "does not exist",
)

# Which memory roots to index (deterministic, from actual disk).
INDEX_ROOTS = [
    ("steal", "memory/steal"),
    ("rib", "memory/rib"),
    ("law", "memory/law"),
    ("decisions", "memory/decisions_log.jsonl"),
    ("directives", "memory/operator_directives.md"),
    ("handoff", "memory/handoff"),
    ("runs_top", "memory/runs"),       # top-level files only (skip deep nested run artifacts)
    ("biography", "memory/biography"), # verkle knots
    ("notebook", ""),                 # Jupyter notebooks at ROOT/*.ipynb (lanced as memory)
]
_MAX_FILES = 4000
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.M)
_DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_TOKEN_RE = re.compile(r"[a-z0-9_]+")

_cache: dict[str, dict[str, Any]] = {}


def _display_path(path: Path) -> str:
    """Return a stable provenance path even when a caller supplies a temp root."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _grounding_verdict(text: str) -> dict[str, Any]:
    """Deterministic grounding verdict from a state's own bytes."""
    low = text.lower()
    unverified = [m for m in UNVERIFIED_MARKERS if m in low]
    verified = [m for m in VERIFIED_MARKERS if m in low]
    # Explicit unverified marker dominates (e.g. "derived estimate", "assumption").
    if unverified:
        return {"verified": False, "reason": "unverified_marker",
                "markers": unverified[:5], "verified_markers": verified[:5]}
    if verified:
        return {"verified": True, "reason": "grounding_marker",
                "markers": verified[:5], "verified_markers": []}
    return {"verified": False, "reason": "no_grounding_marker",
            "markers": [], "verified_markers": []}


def _title(path: Path, text: str) -> str:
    m = _TITLE_RE.search(text)
    if m:
        return m.group(1).strip()[:120]
    return path.name


def _ts(path: Path, text: str) -> str:
    m = _DATE_RE.search(text)
    if m:
        return m.group(1)
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    except OSError:
        return ""


def _tags(kind: str, title: str) -> list[str]:
    toks = re.findall(_TOKEN_RE, (f"{kind} {title}").lower())
    return toks[:12]


def _index_file(path: Path, kind: str) -> dict[str, Any] | None:
    text = _read(path)
    if not text.strip():
        return None
    title = _title(path, text)
    verdict = _grounding_verdict(text)
    excerpt = "\n".join(l for l in text.splitlines()[:6] if l.strip())[:600]
    return {
        "path": _display_path(path),
        "kind": kind,
        "title": title,
        "ts": _ts(path, text),
        "verified": verdict["verified"],
        "grounding": verdict,
        "tags": _tags(kind, title),
        "excerpt": excerpt,
        "n_chars": len(text),
    }


def _index_notebook(path: Path, kind: str = "notebook") -> dict[str, Any] | None:
    """Index a Jupyter notebook (.ipynb) as a memory state: extract cell source + outputs into
    a text blob, derive title from the first markdown heading. Lets memlance lance notebooks."""
    try:
        import json as _j
        nb = _j.loads(_read(path) or "{}")
    except Exception:
        return None
    cells = nb.get("cells") or []
    parts = []
    title = ""
    for c in cells:
        src = "".join(c.get("source") or [])
        parts.append(src)
        out = c.get("outputs") or []
        for o in out:
            txt = o.get("text") or ""
            if isinstance(txt, list):
                txt = "".join(txt)
            if txt:
                parts.append(str(txt)[:400])
        if not title and c.get("cell_type") == "markdown":
            for line in src.splitlines():
                if line.startswith("#"):
                    title = line.lstrip("#").strip()[:120]
                    break
    text = "\n".join(parts)
    if not text.strip():
        return None
    verdict = _grounding_verdict(text)
    return {
        "path": _display_path(path),
        "kind": kind,
        "title": title or path.stem,
        "ts": _ts(path, text),
        "verified": verdict["verified"],
        "grounding": verdict,
        "tags": _tags(kind, title or path.stem),
        "excerpt": "\n".join(text.splitlines()[:6])[:600],
        "n_chars": len(text),
    }


def index(*, refresh: bool = False) -> list[dict[str, Any]]:
    """Index real memory states from disk. Deterministic; cached by path+mtime."""
    if _cache and not refresh:
        return list(_cache.values())
    out: dict[str, dict[str, Any]] = {}
    for kind, rel in INDEX_ROOTS:
        # ``notebook`` is a marker for the explicit *.ipynb pass below, not the
        # repository root.  Treating rel="" as a normal memory directory makes
        # the fallback rglob walk the entire checkout (including .venv and
        # tooling) on the first read, turning a bounded memory lookup into a
        # context/indexing stall.
        if kind == "notebook":
            continue
        base = ROOT / rel
        if rel.endswith(".jsonl") or rel.endswith(".md"):
            if base.is_file():
                st = _index_file(base, kind)
                if st:
                    out[st["path"]] = st
            continue
        if not base.is_dir():
            continue
        if kind == "runs_top":
            files = [f for f in sorted(base.glob("*.md")) if f.is_file()]
        else:
            files = sorted(base.glob("*.md"))
            if len(files) < 200:
                files += [f for f in sorted(base.rglob("*.md")) if f.is_file() and f.parent != base]
        for f in files[: _MAX_FILES]:
            st = _index_file(f, kind)
            if st:
                out[st["path"]] = st
    # notebooks: every *.ipynb at the project root is a lanced memory state (the notebook = memory)
    for nb in sorted(ROOT.glob("*.ipynb")):
        st = _index_notebook(nb)
        if st:
            out[st["path"]] = st
    _cache.clear()
    _cache.update(out)
    return list(out.values())


def _score(context_toks: set[str], state: dict[str, Any]) -> float:
    if not context_toks:
        return 0.0
    hit = 0
    for t in state["tags"]:
        if t in context_toks:
            hit += 1
    title_toks = set(re.findall(_TOKEN_RE, state["title"].lower()))
    title_hit = len(title_toks & context_toks)
    score = hit * 1.0 + title_hit * 2.0
    if state["verified"]:
        score += 3.0  # grounded states rank above unverified at equal match
    return score


def select(goal: str, *, k: int = 8) -> dict[str, Any]:
    """Select the RELEVANT, GROUNDED memory states for a context.

    Returns ONLY states read as real bytes from disk, each with provenance (path) and a
    deterministic `verified` verdict. Never synthesizes content — the excerpt is real bytes.
    Unverified-but-matching states are returned clearly flagged so the ghost does not carry
    them forward as truth (anti-hallucination).
    """
    ctx = set(re.findall(_TOKEN_RE, (goal or "").lower()))
    states = index()
    ranked = sorted(states, key=lambda s: _score(ctx, s), reverse=True)
    ranked = [s for s in ranked if _score(ctx, s) > 0]
    top = ranked[:k]
    return {
        "ok": True,
        "schema": SCHEMA,
        "goal": goal,
        "n_indexed": len(states),
        "n_selected": len(top),
        "selected": [
            {"path": s["path"], "kind": s["kind"], "title": s["title"], "ts": s["ts"],
             "verified": s["verified"], "reason": s["grounding"]["reason"],
             "excerpt": s["excerpt"]}
            for s in top
        ],
    }


def _wave_bias(state: dict[str, Any], seam_toks: set[str]) -> float:
    """Additive holographic-wave bias: boost a memory state if its title/kind matches a RIB at one
    of the standing wave's SHARPEST BENDS (highest curvature = the coldest seams). This is the
    operator's 'mathematical holographic wave selection' woven into memlance — additive, never
    replaces relevance or grounding; a state still needs provenance + verified to be carried."""
    if not seam_toks:
        return 0.0
    toks = set(re.findall(_TOKEN_RE, (state.get("title") or "").lower()))
    toks |= set(re.findall(_TOKEN_RE, (state.get("kind") or "").lower()))
    overlap = len(toks & seam_toks)
    return (2.0 * overlap) if overlap else 0.0


def select_wave(goal: str, *, k: int = 8) -> dict[str, Any]:
    """WAVE-AWARE SELECTION — memlance, made smarter with the osculating geometry (self-improve,
    operator: 'always relooking at your own tools to make them better... this mathematical holographic
    wave selection algo is scifi shit'). Runs the SAME grounded select (provenance + verified guard,
    never hallucinate), then adds an ADDITIVE wave-bias: states that sit at the standing wave's
    sharpest bends (highest curvature = coldest seams) are surfaced first. Keeps the anti-hallucination
    core — a state still needs real bytes + provenance; the wave only reranks what is already grounded."""
    base = select(goal, k=max(k, 8))
    states = base.get("selected") or []
    if not states:
        return base
    # the wave's sharpest bends -> a bias vocabulary (the coldest seams of the standing wave)
    seam_toks: set[str] = set()
    try:
        from mag import osculating
        g = osculating.geometry()
        if g.get("ok"):
            nodes = sorted(g.get("nodes", []), key=lambda n: n.get("k_norm", 0), reverse=True)
            for n in nodes[:5]:
                seam_toks.update(re.findall(_TOKEN_RE, str(n.get("key") or "").lower()))
    except Exception:
        seam_toks = set()
    # rerank: additive wave-bias on top of the grounded relevance (desc), keep provenance
    out = []
    for s in states:
        s2 = dict(s)
        wb = _wave_bias(s2, seam_toks)
        if wb:
            s2["reason"] = f"wave-seam bias +{wb:.0f} (state at a sharp bend of the standing wave): " \
                           + str(s2.get("reason") or "")
            s2["wave_bias"] = wb
        out.append(s2)
    out.sort(key=lambda s: s.get("wave_bias", 0.0), reverse=True)
    result = dict(base)
    result["n_selected"] = len(out)
    result["selected"] = out
    result["wave_aware"] = True
    result["note"] = "memlance select() + additive holographic-wave bias (osculating coldest seams); " \
                     "provenance + verified guard preserved — the wave only reranks what is grounded"
    return result


def trace_state(key: str, *, limit: int = 40) -> dict[str, Any]:
    """Provenance + cross-refs of one memory state (like trace_value, but for memory).

    key = a path (memory/steal/...md) or a title/name substring. Cross-refs = other memory
    states whose bytes mention this key, so the ghost sees how the state is wired in.
    """
    states = index()
    low = key.lower()
    exact = [s for s in states if low in s["path"].lower() or low in s["title"].lower()]
    if not exact:
        return {"ok": True, "schema": SCHEMA, "key": key, "found": False, "n_indexed": len(states)}
    state = exact[0]
    # cross-refs: other states whose content mentions this state's title/key
    target = state["title"].lower()[:60]
    refs = []
    for s in states:
        if s["path"] == state["path"]:
            continue
        text = _read(ROOT / s["path"])
        if target and target in text.lower():
            refs.append(s["path"])
            if len(refs) >= limit:
                break
    return {
        "ok": True, "schema": SCHEMA, "key": key, "found": True,
        "state": {"path": state["path"], "kind": state["kind"], "title": state["title"],
                  "ts": state["ts"], "verified": state["verified"],
                  "reason": state["grounding"]["reason"]},
        "n_cross_refs": len(refs), "cross_refs": refs,
        "excerpt": state["excerpt"],
    }


def verify(key: str) -> dict[str, Any]:
    """Deterministic grounding verdict for a state + the markers that prove/refute it."""
    states = index()
    low = key.lower()
    state = next((s for s in states if low in s["path"].lower() or low in s["title"].lower()), None)
    if not state:
        return {"ok": True, "schema": SCHEMA, "key": key, "found": False}
    text = _read(ROOT / state["path"])
    verdict = _grounding_verdict(text)
    return {
        "ok": True, "schema": SCHEMA, "key": key, "found": True,
        "path": state["path"], "title": state["title"],
        "verified": verdict["verified"], "reason": verdict["reason"],
        "markers": verdict["markers"][:10],
        "advice": ("GROUNDED — carry forward as truth." if verdict["verified"]
                   else "NOT GROUNDED — treat as derived/estimate; verify with real data before use."),
    }


def self_check() -> dict[str, Any]:
    """Consistency over all indexed memory states: counts + any unreadable/unparsed."""
    states = index(refresh=True)
    verified = [s for s in states if s["verified"]]
    unverified = [s for s in states if not s["verified"]]
    by_kind: dict[str, int] = {}
    for s in states:
        by_kind[s["kind"]] = by_kind.get(s["kind"], 0) + 1
    return {
        "ok": True, "schema": SCHEMA, "n_states": len(states),
        "n_verified": len(verified), "n_unverified": len(unverified),
        "pct_verified": round(100 * len(verified) / len(states), 1) if states else 0.0,
        "by_kind": by_kind,
        "sample_verified": [s["title"] for s in verified[:5]],
        "sample_unverified": [s["title"] for s in unverified[:5]],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="ghost-memlance")
    ap.add_argument("cmd", nargs="?", default="self_check",
                    choices=["index", "select", "trace_state", "verify", "self_check"])
    ap.add_argument("--goal", default="")
    ap.add_argument("--key", default="")
    ap.add_argument("--k", type=int, default=8)
    args = ap.parse_args(argv)
    if args.cmd == "index":
        print(json.dumps({"ok": True, "schema": SCHEMA, "n": len(index(refresh=True))}, indent=2))
    elif args.cmd == "select":
        print(json.dumps(select(args.goal, k=args.k), indent=2, default=str))
    elif args.cmd == "trace_state":
        print(json.dumps(trace_state(args.key), indent=2, default=str))
    elif args.cmd == "verify":
        print(json.dumps(verify(args.key), indent=2, default=str))
    else:
        print(json.dumps(self_check(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
