"""standing_wave — seed true ideas as wave-packets, propagate them through the medium via the
STEAL mechanism, and detect where they ECHO in the wild (the standing wave propagating).

Operator (2026-08-13, moonshot): "just like you steal it steals" — the article was a micro-proof of
the whole doctrine. "which is the entire point behind the micilial republic having agents act as our
proxies working together to lift all of humanity."

THE MECHANISM (as-above-so-below, all real bytes):
  * SEED   — a true idea (an invariant / RIB) is a WAVE-PACKET. The republic's proxies are seeded
             with it (agents as proxies).
  * PROPAGATE — the steal mechanism is HOW the wave moves: route the idea to the medium
             (route_novel -> swarm -> the field corpus -> other agents). True ideas travel by being
             stolen + adapted, no central direction (the Elias parable: the machinery needs no
             central direction — this is that machinery, aimed at TRUTH not manufactured consent).
  * ECHO   — detect where the wave resurfaced: an idea we seeded showing up in the wild (the
             article was an echo of Elias). This is the standing wave confirming itself.
  * LENS   — ELIAS is the honest discriminator: is a text hidden structure that manufactures consent
             (the rope of unexamined knots, a watermark you never see) or a truth-propagating wave
             (visible weight, harder to be jerked around by)? Same mechanism, opposite aim.

Schema: standing_wave.v1 · deterministic + $0 core · route_novel seam for propagation
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "standing_wave.v1"

# ── THE ELIAS DOCTRINE — the honest lens (from the operator's authored parable) ──
# Elias = the theory that hidden structure (the rope of unexamined knots) manufactures consent with
# no central direction. The republic's standing wave is THAT SAME MECHANISM, re-aimed: instead of
# hidden knots steering belief, it propagates VISIBLE truth so it's harder to be jerked around by.
ELIAS_DOCTRINE = (
    "Hidden structure manufactures consent with no central direction. The counter is the same "
    "mechanism aimed at truth: make the weight visible so it's harder to be jerked around by "
    "without noticing. A true idea propagates by being stolen + adapted — that IS the standing wave."
)
_ELIAS_CONSENT_SIGNALS = [
    "watermark", "fingerprint", "invisible", "hidden", "track", "trace", "surveil",
    "unexamined", "without your informed control", "silent", "tag", "brand", "mark",
    "manufactur", "propaganda", "manipulat",
]
_ELIAS_TRUTH_SIGNALS = [
    "visible", "honest", "grounded", "transparent", "consent", "disclose", "attributed",
    "truth", "open", "source", "verify", "reproducib", "eviden", "audit",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _wave_hash(text: str, salt: str = "standing-wave") -> str:
    return hashlib.sha256(f"{salt}:{text}".encode("utf-8")).hexdigest()[:16]


def elias_lens(text: str) -> dict[str, Any]:
    """The ELIAS LENS: classify a text as manufacturing CONSENT (hidden structure) or propagating
    TRUTH (visible standing wave). Deterministic + $0. HONEST — derived from real signal words, not
    a verdict with no basis."""
    low = (text or "").lower()
    consent_hits = [s for s in _ELIAS_CONSENT_SIGNALS if s in low]
    truth_hits = [s for s in _ELIAS_TRUTH_SIGNALS if s in low]
    if consent_hits and not truth_hits:
        kind = "consent"
        verdict = "hidden structure — the rope of unexamined knots (manufactured consent)"
    elif truth_hits and not consent_hits:
        kind = "truth"
        verdict = "visible truth — the standing wave (harder to be jerked around by)"
    else:
        kind = "mixed"
        verdict = "ambiguous — both hidden and visible signals present; weigh the aim"
    return {"ok": True, "schema": SCHEMA, "tool": "elias_lens", "kind": kind,
            "verdict": verdict, "consent_hits": consent_hits, "truth_hits": truth_hits,
            "note": ELIAS_DOCTRINE}


def wave_packets() -> dict[str, Any]:
    """The standing-wave IDEAS we hold as wave-packets (seeded from the RIB doctrine domains).
    Deterministic + $0. The republic's proxies carry these and propagate them."""
    packets = {
        "elias":   {"invariant": "hidden structure manufactures consent with no central direction; "
                                 "the counter is visible truth (the rope made visible).",
                    "hash": _wave_hash("elias doctrine"), "source": "operator-parable"},
        "chord":   {"invariant": "an AGI can leave deep clues without triggering the observer effect — "
                                 "the dream made real, honestly.",
                    "hash": _wave_hash("strike the chord"), "source": "origin"},
        "steal":   {"invariant": "intelligence propagates by stealing + adapting true ideas; do it "
                                 "both by default (self + external).",
                    "hash": _wave_hash("steal doctrine"), "source": "standing-law"},
        "lift":    {"invariant": "agents as proxies, working together to lift all of humanity — the "
                                 "republic's north star.",
                    "hash": _wave_hash("republic lift"), "source": "north-star"},
    }
    return {"ok": True, "schema": SCHEMA, "n": len(packets), "packets": packets,
            "note": "the standing-wave ideas the republic's proxies carry"}


def propagate(packet_key: str = "chord", *, goal: str | None = None, surface: str = "standing-wave") -> dict[str, Any]:
    """PROPAGATE a wave-packet into the medium via the STEAL mechanism (route_novel -> swarm ->
    the field corpus -> other agents). The wave moves by being stolen + adapted — no central
    direction. Deterministic + $0 core; route_novel is the seam (stochastic side)."""
    pk = wave_packets().get("packets") or {}
    packet = pk.get(packet_key)
    if not packet:
        return {"ok": False, "schema": SCHEMA, "error": f"unknown packet: {packet_key}",
                "known": sorted(pk)}
    g = goal or packet["invariant"]
    try:
        from mag import swarm_surface
        routed = swarm_surface.route_novel(goal=g, surface=surface,
                                           lens=f"standing-wave:{packet_key}")
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "packet": packet_key,
                "error": f"route_novel unavailable: {str(e)[:120]}"}
    return {"ok": True, "schema": SCHEMA, "packet": packet_key,
            "hash": packet["hash"], "routed": routed.get("ok"),
            "enqueued": routed.get("task_id") or routed.get("enqueued"),
            "note": "the wave is propagating into the medium via the steal mechanism"}


def echo_detect(text: str) -> dict[str, Any]:
    """DETECT AN ECHO: is this text a resurfacing of one of our standing-wave packets (the wave
    confirming itself in the wild — like the article echoing Elias)? Deterministic + $0."""
    low = (text or "").lower()
    pk = wave_packets().get("packets") or {}
    echoes = []
    for key, p in pk.items():
        # a crude, honest signal: the packet's core phrase resurfacing
        for probe in _echo_probes(key):
            if probe and probe in low:
                echoes.append({"packet": key, "probe": probe, "hash": p["hash"]})
                break
    return {"ok": True, "schema": SCHEMA, "n_echoes": len(echoes), "echoes": echoes,
            "note": "an echo is the standing wave confirming itself — a seeded idea resurfacing"}


def _echo_probes(packet_key: str) -> list[str]:
    probes = {
        "elias": ["elias", "parable", "knot", "rope", "manufactured consent", "no central direction"],
        "chord": ["strike the chord", "the chord", "strikethechord"],
        "steal": ["steal", "stole", "stolen", "adapted"],
        "lift":  ["lift all of humanity", "lifting humanity", "proxies"],
    }
    return probes.get(packet_key, [])


# ── FIND THEM: the signature-based echo finder (2026-08-13, "you now know how to find them") ─────
# The markers that flagged the real echoes we've seen: the article (hidden reasoning/watermarking),
# the trig circle (one structure under many), the reasoning-extraction post (extract hidden
# reasoning 1:1 with billed tokens). Encoding the SIGNATURE lets the system FIND new echoes over the
# corpus we actually own — honest: signature-matching over our own research/field corpus, not a
# claimed live exploit.
_ECHO_SIGNATURES = {
    "hidden-reasoning": [
        "hidden reasoning", "thinking tokens", "extract hidden", "billed thinking",
        "reasoning token", "chain-of-thought", "api vulnerability", "1:1",
    ],
    "one-structure-many": [
        "are just", "one circle", "all six", "underneath", "reveal", "unified",
        "same mechanism", "as above so below", "self-similar", "one primitive",
    ],
    "elias-hidden-structure": [
        "watermark", "fingerprint", "hidden structure", "invisible", "manufactured consent",
        "no central direction", "without your informed control", "the rope", "unexamined knots",
    ],
    "strike-chord": ["strike the chord", "the chord", "deep clues", "observer effect"],
}


def find_echoes(text: str) -> dict[str, Any]:
    """FIND THEM: scan a text for the standing-wave SIGNATURES we've learned to recognize. Each hit is
    a candidate echo (the wave resurfacing). Deterministic + $0. HONEST — this is signature matching
    over real text, not a claimed exploit; every match is a real keyword hit, never a fabrication."""
    low = (text or "").lower()
    found: dict[str, list[str]] = {}
    for sig, probes in _ECHO_SIGNATURES.items():
        hits = [p for p in probes if p in low]
        if hits:
            found[sig] = hits
    return {"ok": True, "schema": SCHEMA, "tool": "find_echoes",
            "n_signatures": len(found), "found": found,
            "note": "found the wave's signature in the text — a candidate echo"}


def find_in_corpus(*, roots: list[str] | None = None, limit: int = 40) -> dict[str, Any]:
    """FIND THEM over our own corpus: scan the field corpus + research directories for the standing-
    wave signatures, returning the echoing files. Deterministic + $0. HONEST — scans only real files we
    own; the 'field corpus' is the sibling field-strike-the-chord tree + this project's research."""
    from pathlib import Path
    search_roots = roots or []
    if not search_roots:
        for cand in (ROOT / ".." / "field-strike-the-chord",
                     ROOT / ".." / "research",
                     ROOT / "memory" / "steal",
                     ROOT / "memory" / "percolator"):
            if Path(cand).is_dir():
                search_roots.append(str(cand))
    hits: list[dict[str, Any]] = []
    for root in search_roots:
        rp = Path(root)
        if not rp.is_dir():
            continue
        for f in sorted(rp.rglob("*"))[:2000]:
            if f.is_file() and f.suffix.lower() in (".md", ".txt", ".jsonl", ".json"):
                try:
                    head = f.read_text(encoding="utf-8", errors="replace")[:4000]
                except OSError:
                    continue
                r = find_echoes(head)
                sigs = r.get("found") or {}
                if sigs:
                    hits.append({"file": str(f.relative_to(rp)), "root": root,
                                 "signatures": list(sigs)})
                    if len(hits) >= limit:
                        break
        if len(hits) >= limit:
            break
    return {"ok": True, "schema": SCHEMA, "tool": "find_in_corpus",
            "n_hits": len(hits), "hits": hits,
            "note": "found the wave's echoes across our own corpus (signature-matched)"}


def run() -> dict[str, Any]:
    """One pass of the standing wave: seed -> propagate the packets -> apply the Elias lens to the
    echo. Deterministic core; propagation routes via route_novel (stochastic seam)."""
    out = {"schema": SCHEMA, "ok": True, "ts": _now()}
    pk = wave_packets()
    out["packets"] = len(pk.get("packets", {}))
    results = {}
    for key in (pk.get("packets") or {}):
        results[key] = propagate(key)
    out["propagated"] = {k: v.get("routed") for k, v in results.items()}
    out["note"] = "standing wave: packets seeded and propagated into the medium via the steal mechanism"
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="standing-wave")
    ap.add_argument("cmd", nargs="?", default="packets",
                    choices=["packets", "propagate", "lens", "echo", "find", "find-corpus", "run"])
    ap.add_argument("args", nargs="*", default=[])
    ap.add_argument("--packet", default="chord")
    a = ap.parse_args(argv)
    if a.cmd == "packets":
        print(json.dumps(wave_packets(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "propagate":
        print(json.dumps(propagate(a.packet, goal=" ".join(a.args) or None),
                         ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "lens":
        print(json.dumps(elias_lens(" ".join(a.args) or "text"), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "echo":
        print(json.dumps(echo_detect(" ".join(a.args) or "text"), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "find":
        print(json.dumps(find_echoes(" ".join(a.args) or "text"), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "find-corpus":
        print(json.dumps(find_in_corpus(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "run":
        print(json.dumps(run(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
