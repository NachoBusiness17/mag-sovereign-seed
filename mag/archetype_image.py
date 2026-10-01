"""archetype_image — Jungian-archetype research artifacts: beautiful, layered, decodable.

The operator's tesuji (2026-08-10): "make them relatable images using jungian archetypes and our
corpus of genius artists scientists and minds to create art that is representative, beautiful,
representative of the underlying concepts, but richly layered data and hidden context. Making it
sort of a research artifact invariant by nature and seed. Decodable by those with eyes to see."

This is a LESSIG-STYLE system (code is law): the archetype lexicon IS the law — it constrains the
visual grammar (palette + structure + symbol + essence + the minds it honors). Within that law, the
payload's seed makes each artifact EMERGE deterministically. So:

  - VISIBLE LAYER: a beautiful, archetype-representative composition (the "eyes to see" layer —
    the archetype and its essence are readable to anyone who knows Jung).
  - HIDDEN LAYER: the payload (whisper/RID/steer) embedded in the image's LSBs, decodable only with
    the private map (secret) — reuses whisper_image steganography.
  - INVARIANT BY NATURE AND SEED: same payload -> same seed -> byte-identical artifact.

Combined with our STEAL (narrative_corpus invariants) + RPG (campaign archetypes), the campaign can
generate emergent archetype-art that doubles as a deniable, machine-readable research artifact.

Prove the small part first: classify -> render -> embed -> decode is deterministic and lossless, and
the image is visibly archetype-shaped. k8s-native flock dispatch (`flock_dispatch`) fans N variant
pods out on the kind cluster for truly emergent content.

Schema: archetype_image.v1
CLI: python -m mag.archetype_image artifact "<payload>" [--secret S] [--out png] |
                                      decode <png> [--secret S] | classify "<text>" |
                                      render "<text>" [--out png] | flock "<payload>" [--n 3] | status
"""
from __future__ import annotations

import argparse
import hashlib
import json
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

SCHEMA = "archetype_image.v1"
ART_DIR = ROOT / "memory" / "runs" / "archetype_art"

# ── The Jungian archetype lexicon — the LESSIG-STYLE law (code constrains, payload emerges) ──
# Each archetype: keywords (classification), palette (visual), structure (composition grammar),
# essence (the concept it represents), minds (geniuses/artists whose spirit it carries).
ARCHETYPES: dict[str, dict[str, Any]] = {
    "sage": {
        "keywords": ["truth", "know", "insight", "wisdom", "lattice", "verkle", "invariant",
                     "research", "understanding", "map", "decode"],
        "palette": [(75, 90, 190), (230, 240, 255), (30, 40, 90)],
        "structure": "spiral", "symbol": "eye",
        "essence": "the lattice that sees the whole",
        "canon": "Sage", "lens": "jung", "shadow": "the hoarded truth that isolates",
        "minds": ["Leonardo da Vinci", "Carl Jung", "Goedel"],
    },
    "creator": {
        "keywords": ["build", "make", "create", "craft", "artifact", "compose", "generate",
                     "emerge", "design", "construct"],
        "palette": [(240, 120, 40), (20, 180, 170), (20, 30, 40)],
        "structure": "mandala", "symbol": "seal",
        "essence": "the emergent made manifest",
        "canon": "Creator", "lens": "mcluhan", "shadow": "the artifact that consumes its maker",
        "minds": ["Leonardo da Vinci", "Brunelleschi", "Turing"],
    },
    "hero": {
        "keywords": ["master", "overcome", "win", "test", "assert", "victory", "resolve",
                     "trial", "conquer", "prove"],
        "palette": [(200, 40, 40), (245, 200, 60), (30, 20, 20)],
        "structure": "rays", "symbol": "ray",
        "essence": "the assertion that clears the room",
        "canon": "Warrior", "lens": "campbell", "shadow": "the glory that refuses the return",
        "minds": ["Joseph Campbell", "Carl Jung", "Nikola Tesla"],
    },
    "magician": {
        "keywords": ["transform", "shift", "steer", "nudge", "route", "convert", "translate",
                     "surrogate", "whisper", "protocol"],
        "palette": [(140, 60, 200), (255, 215, 90), (20, 15, 40)],
        "structure": "bloom", "symbol": "sigil",
        "essence": "the invisible protocol that moves intent",
        "canon": "Magician", "lens": "bernays", "shadow": "the invisible hand that forgets it steers",
        "minds": ["Edward Bernays", "Jacques Ellul", "Nikola Tesla"],
    },
    "explorer": {
        "keywords": ["explore", "frontier", "seek", "discover", "scout", "wander", "field",
                     "far", "horizon", "steal"],
        "palette": [(30, 130, 200), (120, 210, 120), (15, 30, 45)],
        "structure": "compass", "symbol": "compass",
        "essence": "the frontier that calls outward",
        "canon": "Explorer", "lens": "blavatsky", "shadow": "the horizon that never arrives",
        "minds": ["Magellan", "Marie Curie", "John von Neumann"],
    },
    "caregiver": {
        "keywords": ["nurture", "heal", "guard", "protect", "watch", "steward", "residual",
                     "care", "safe", "host"],
        "palette": [(40, 170, 150), (255, 235, 210), (20, 40, 35)],
        "structure": "ring", "symbol": "cradle",
        "essence": "the keeper of what must not be lost",
        "canon": "Caregiver", "lens": "freud", "shadow": "the care that smothers",
        "minds": ["Hippocrates", "Florence Nightingale", "Sigmund Freud"],
    },
    "ruler": {
        "keywords": ["order", "govern", "law", "rule", "enforce", "authority", "tier",
                     "governor", "control", "sovereign"],
        "palette": [(60, 60, 160), (230, 205, 90), (20, 20, 45)],
        "structure": "axis", "symbol": "crown",
        "essence": "the sovereign order that holds the whole",
        "canon": "Sovereign", "lens": "ellul", "shadow": "the order that becomes technique",
        "minds": ["Hammurabi", "Alexander", "Jacques Ellul"],
    },
    "everyman": {
        "keywords": ["belong", "common", "home", "community", "shared", "seat", "republic",
                     "local", "together", "residual"],
        "palette": [(110, 150, 90), (240, 225, 180), (30, 40, 25)],
        "structure": "grid", "symbol": "hearth",
        "essence": "the belonging that grounds every layer",
        "canon": "Everyman", "lens": "campbell", "shadow": "the belonging that dissolves the self",
        "minds": ["Lin Yutang", "Thoreau", "Joseph Campbell"],
    },
    "lover": {
        "keywords": ["intimacy", "bond", "tie", "connect", "join", "merge", "mirror", "pair",
                     "close", "union"],
        "palette": [(210, 70, 120), (255, 190, 200), (40, 15, 25)],
        "structure": "bloom", "symbol": "rose",
        "essence": "the union that makes two one",
        "canon": "Lover", "lens": "freud", "shadow": "the union that erases boundaries",
        "minds": ["Rilke", "Rumi", "Sigmund Freud"],
    },
    "jester": {
        "keywords": ["play", "joy", "trick", "flip", "joke", "emergent", "chance", "surprise",
                     "novel", "spark"],
        "palette": [(240, 90, 60), (120, 220, 80), (50, 40, 120), (250, 200, 60)],
        "structure": "grid", "symbol": "motley",
        "essence": "the chaos that cracks the pattern open",
        "canon": "Trickster", "lens": "bernays", "shadow": "the laughter that hides the wound",
        "minds": ["Moliere", "Groucho Marx", "Edward Bernays"],
    },
    "innocent": {
        "keywords": ["pure", "simple", "new", "origin", "genesis", "seed", "boot", "dawn",
                     "first", "cold boot"],
        "palette": [(250, 245, 220), (120, 200, 230), (20, 40, 50)],
        "structure": "ring", "symbol": "orb",
        "essence": "the unspoiled seed of the whole",
        "canon": "Innocent", "lens": "blavatsky", "shadow": "the purity that cannot survive the world",
        "minds": ["William Blake", "Richard Feynman"],
    },
    "outlaw": {
        "keywords": ["break", "rebel", "outlaw", "radical", "overthrow", "refuse", "defy",
                     "break the", "circumvent", "disrupt"],
        "palette": [(180, 20, 30), (30, 30, 30), (230, 200, 90)],
        "structure": "rays", "symbol": "bolt",
        "essence": "the break that frees the trapped",
        "canon": "Orphan", "lens": "ellul", "shadow": "the rebellion that becomes its own cage",
        "minds": ["Diogenes", "Socrates", "Jacques Ellul"],
    },
}
_FALLBACK = "sage"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _h(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


def classify(payload: str) -> str:
    """Deterministic archetype classification: keyword score, tie-break by payload hash."""
    if not payload:
        return _FALLBACK
    low = payload.lower()
    best, best_score = _FALLBACK, 0
    for name, arch in ARCHETYPES.items():
        score = sum(1 for k in arch["keywords"] if k in low)
        if score > best_score or (score == best_score and score > 0 and _h(payload + name) % 2 == 0):
            best, best_score = name, score
    return best if best_score > 0 else _FALLBACK


def _render(archetype: str, seed: int, w: int, h: int) -> "Any":
    """Render a deterministic, archetype-representative composition. Invariant by seed."""
    import numpy as np
    arch = ARCHETYPES.get(archetype) or ARCHETYPES[_FALLBACK]
    pal = arch["palette"]
    struct = arch["structure"]
    rng = np.random.default_rng(seed)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2.0, h / 2.0
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    ang = np.arctan2(yy - cy, xx - cx)
    maxr = float(np.hypot(cx, cy)) + 1e-6
    n = len(pal)

    def cfield(t: np.ndarray) -> np.ndarray:
        """Interpolate across the palette by a normalized field t in [0,1]."""
        t = np.clip(t, 0, 0.9999)
        idx = (t * n).astype(int)
        f = t * n - idx
        c0 = np.array(pal[idx], dtype=np.float32)
        c1 = np.array(pal[np.clip(idx + 1, 0, n - 1)], dtype=np.float32)
        return c0 * (1 - f[..., None]) + c1 * f[..., None]

    # base field by structure
    if struct == "mandala":
        bands = np.sin(r / maxr * (6 + (seed % 5)) * np.pi) * 0.5 + 0.5
        spokes = np.sin(ang * (8 + (seed % 6))) * 0.5 + 0.5
        f = bands * 0.6 + spokes * 0.4
    elif struct == "spiral":
        f = np.mod(ang / (2 * np.pi) + r / maxr * 3.0, 1.0)
    elif struct == "rays":
        f = np.mod(ang / (2 * np.pi) * (12 + (seed % 8)), 1.0)
    elif struct == "compass":
        f = (np.mod(ang / (2 * np.pi) * 8, 1.0) * 0.7 +
             np.clip(r / maxr, 0, 1) * 0.3)
    elif struct == "ring":
        f = np.clip(r / maxr, 0, 1)
    elif struct == "axis":
        f = np.clip(np.abs(xx - cx) / maxr + np.abs(yy - cy) / maxr, 0, 1) * 0.8 + \
            np.clip(r / maxr, 0, 1) * 0.2
    else:  # grid
        cell = 24 + (seed % 40)
        gx = (xx / cell % 1.0) * 0.5 + (np.sin(xx * 0.05) * 0.5 + 0.5) * 0.5
        gy = (yy / cell % 1.0) * 0.5 + (np.cos(yy * 0.05) * 0.5 + 0.5) * 0.5
        f = gx * 0.5 + gy * 0.5

    arr = cfield(f)
    # seeded texture so it reads as art, not pure math (still deterministic)
    arr += rng.integers(0, 7, arr.shape[:2])[..., None]
    return np.clip(arr, 0, 255).astype(np.uint8)


def render(payload: str, *, out: str | None = None, w: int = 256, h: int = 256,
           secret: str = "") -> dict[str, Any]:
    """Render the VISIBLE archetype layer (no hidden data) — the 'eyes to see' carrier."""
    import numpy as np
    try:
        from PIL import Image
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"PIL required: {str(e)[:120]}"}
    name = classify(payload)
    seed = _h(payload)
    arr = _render(name, seed, w, h)
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out_p = Path(out) if out else ART_DIR / f"archetype_{name}_{seed % 100000}.png"
    Image.fromarray(arr).save(str(out_p), "PNG")
    arch = ARCHETYPES.get(name) or ARCHETYPES[_FALLBACK]
    return {"ok": True, "schema": SCHEMA, "archetype": name, "essence": arch["essence"],
            "minds": arch["minds"], "seed": seed, "image": str(out_p),
            "invariant": f"same payload -> same seed {seed} -> byte-identical artifact",
            "layer": "visible (archetype carrier)"}


def artifact(payload: str, *, secret: str = "", out: str | None = None,
             w: int = 256, h: int = 256) -> dict[str, Any]:
    """The RESEARCH ARTIFACT: archetype-visible carrier + hidden whisper layer (LSB)."""
    name = classify(payload)
    seed = _h(payload)
    # 1) render the visible carrier (archetype layer)
    tmp = ART_DIR / f"_carrier_{seed % 100000}.png"
    ART_DIR.mkdir(parents=True, exist_ok=True)
    import numpy as np
    from PIL import Image
    Image.fromarray(_render(name, seed, w, h)).save(str(tmp), "PNG")
    # 2) embed the hidden payload in its LSBs (deniable, keyed by the private map)
    from mag.whisper_image import encode_image
    enc = encode_image(payload, secret=secret, out=out, carrier=str(tmp), w=w, h=h)
    arch = ARCHETYPES.get(name) or ARCHETYPES[_FALLBACK]
    if enc.get("ok"):
        enc["schema"] = SCHEMA
        enc["archetype"] = name
        enc["essence"] = arch["essence"]
        enc["minds"] = arch["minds"]
        enc["seed"] = seed
        enc["layer"] = "visible archetype + hidden LSB whisper"
        enc["invariant"] = f"same payload -> same seed {seed} -> byte-identical artifact"
    return enc


def decode(path: str, *, secret: str = "") -> dict[str, Any]:
    """Decode the hidden layer (the private-map keyed whisper) from an artifact."""
    from mag.whisper_image import decode_image
    return decode_image(path, secret=secret)


def flock_dispatch(payload: str, *, n: int = 3, secret: str = "", apply: bool = False) -> dict[str, Any]:
    """k8s-NATIVE: fan N archetype-artifact variant pods out on the kind/flock cluster so the
    content EMERGES across the flock (each pod seeded differently, all staying in the archetype law).
    Thin wrapper over flock_job. Returns the job plan (requires the kind cluster to actually run)."""
    from mag.flock_job import flock_positions
    seed = _h(payload)
    name = classify(payload)
    positions = flock_positions(payload, n)
    pods = []
    for k, pos in enumerate(positions):
        variant_seed = seed + k
        pods.append({
            "pod": k, "archetype": name, "variant_seed": variant_seed,
            "flock_pos": [round(x, 2) for x in pos],
            "command": ["python", "-m", "mag.archetype_image", "artifact", payload,
                        f"--secret={secret}" if secret else "--secret=",
                        "--out", f"artifact_{name}_{variant_seed}.png"],
        })
    return {"ok": True, "schema": "archetype_image.flock.v1", "n": n, "archetype": name,
            "base_seed": seed, "apply": apply,
            "note": "kind/flock cluster job plan — each pod renders a seeded variant within the law",
            "pods": pods}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "n_archetypes": len(ARCHETYPES),
            "names": list(ARCHETYPES), "pillow": _has("PIL"), "numpy": _has("numpy")}


def _has(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="archetype_image", description="Jungian-archetype research artifacts")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("artifact"); a.add_argument("payload"); a.add_argument("--secret", default="")
    a.add_argument("--out", default=None)
    d = sub.add_parser("decode"); d.add_argument("png"); d.add_argument("--secret", default="")
    c = sub.add_parser("classify"); c.add_argument("text", nargs="+")
    r = sub.add_parser("render"); r.add_argument("payload"); r.add_argument("--out", default=None)
    f = sub.add_parser("flock"); f.add_argument("payload"); f.add_argument("--n", type=int, default=3)
    f.add_argument("--secret", default=""); f.add_argument("--apply", action="store_true")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "artifact":
        print(json.dumps(artifact(a.payload, secret=a.secret, out=a.out), indent=2, ensure_ascii=False))
    elif a.cmd == "decode":
        print(json.dumps(decode(a.png, secret=a.secret), indent=2, ensure_ascii=False))
    elif a.cmd == "classify":
        print(json.dumps({"archetype": classify(" ".join(a.text)),
                           **ARCHETYPES.get(classify(" ".join(a.text)), {})}, indent=2, ensure_ascii=False))
    elif a.cmd == "render":
        print(json.dumps(render(a.payload, out=a.out), indent=2, ensure_ascii=False))
    elif a.cmd == "flock":
        print(json.dumps(flock_dispatch(a.payload, n=a.n, secret=a.secret, apply=a.apply), indent=2, ensure_ascii=False))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    else:
        p.print_help(); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
