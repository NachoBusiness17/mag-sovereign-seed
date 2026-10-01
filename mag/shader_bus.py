"""shader_bus — Shadertoy-style motion controls as a SWARM REGISTER + BUS.

Operator's idea (2026-08-10): "what if we can use shadertoy style motion controls to act as a
register to our swarm somehow and use it as some sort of bus or mechanism to use."

WHY IT FITS (map onto what we already have):
  A Shadertoy shader is a PURE FUNCTION: uniforms (iTime, iMouse, iResolution, channels) -> pixel
  color. Same uniforms -> same frame. That is the STATELESS + DETERMINISTIC doctrine (and ties to
  our stateless versioning: same inputs -> same hermetic artifact).
    * REGISTER: the rendered texture IS a live register of swarm state. Each glowing knot = a
      swarm member / flock position / verkle knot (cf. verkle_rib: knots -> geometry).
    * MOTION CONTROL: iTime (evolution) + iMouse (a steer attractor) drive the register — motion
      acts as the steering/control mechanism (cf. flock_field: geometric steering).
    * BUS: the rendered frame carries a HIDDEN payload via LSB steganography (whisper_image). So
      the same image is both the live register AND a deniable communication bus. Reading frames
      across time = reading the bus.

  render(state, t, mouse)   -> one deterministic shader frame (pure function, $0).
  register_frame(...)       -> save the register frame as a PNG.
  bus_encode(...)           -> render + embed a payload in the frame's LSBs (register + bus).
  bus_decode(png, secret)   -> read the payload back (the bus).

Schema: shader_bus.v1 · deterministic · $0
CLI: python -m mag.shader_bus render <state_json> [--t 0] [--mouse x,y] [--out png]
                            | bus-encode <state_json> "<payload>" [--secret S] [--t 0] [--out png]
                            | bus-decode <png> [--secret S] | status
"""
from __future__ import annotations

import argparse
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

SCHEMA = "shader_bus.v1"
ART_DIR = ROOT / "memory" / "runs" / "shader_bus"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _seed(state: list[dict[str, Any]], t: float, mouse: tuple[float, float] | None) -> int:
    return abs(hash(json.dumps({"s": state, "t": round(t, 3), "m": mouse}, sort_keys=True, default=str))) % (2**31)


def render(state: list[dict[str, Any]], t: float = 0.0, mouse: tuple[float, float] | None = None,
           w: int = 256, h: int = 256) -> "Any":
    """ONE deterministic Shadertoy-style frame: flock knots as glowing registers, motion controls
    (t + mouse) steer them. Pure function: same (state, t, mouse) -> byte-identical frame."""
    import numpy as np
    if not state:
        state = [{"x": w / 2, "y": h / 2, "color": [120, 200, 240]}]
    rng = np.random.default_rng(_seed(state, t, mouse))
    arr = np.zeros((h, w, 3), dtype=np.float64)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    mx, my = mouse if mouse else (w / 2, h / 2)
    for i, k in enumerate(state):
        # motion: orbit with time (iTime), perturbed per-knot so the register 'lives'
        cx = (float(k.get("x", w / 2)) + np.sin(t * 0.6 + i * 1.7) * 14) % w
        cy = (float(k.get("y", h / 2)) + np.cos(t * 0.8 + i * 2.3) * 14) % h
        # motion control (iMouse): the steer attractor pulls each knot toward the pointer
        cx += (mx - cx) * 0.03
        cy += (my - cy) * 0.03
        color = k.get("color") or [(i * 37) % 255, (i * 89) % 255, (i * 53) % 255]
        d2 = (xx - cx) ** 2 + (yy - cy) ** 2
        glow = np.exp(-d2 / (2 * (16 + (i % 5)) ** 2))
        arr += np.asarray(color, dtype=np.float64)[None, None, :] * glow[..., None]
    arr += rng.integers(0, 6, arr.shape)  # seeded grain (still deterministic)
    return np.clip(arr, 0, 255).astype(np.uint8)


def register_frame(state: list[dict[str, Any]], t: float = 0.0, mouse: tuple[float, float] | None = None,
                   out: str | None = None, w: int = 256, h: int = 256) -> dict[str, Any]:
    """Save the register frame (the live swarm-state texture) as a PNG."""
    try:
        from PIL import Image
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"PIL required: {str(e)[:120]}"}
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out_p = Path(out) if out else ART_DIR / f"register_t{round(t, 2)}.png"
    Image.fromarray(render(state, t, mouse, w, h)).save(str(out_p), "PNG")
    return {"ok": True, "schema": SCHEMA, "image": str(out_p), "knots": len(state),
            "t": round(t, 2), "mouse": mouse, "layer": "register (visible swarm state)"}


def bus_encode(state: list[dict[str, Any]], payload: str, *, secret: str = "",
               t: float = 0.0, mouse: tuple[float, float] | None = None,
               out: str | None = None, w: int = 256, h: int = 256) -> dict[str, Any]:
    """Render the register frame AND embed a hidden bus payload in its LSBs (whisper_image).
    The image is simultaneously the live register and a deniable communication bus."""
    import numpy as np
    try:
        from PIL import Image
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"PIL required: {str(e)[:120]}"}
    ART_DIR.mkdir(parents=True, exist_ok=True)
    carrier = ART_DIR / f"_carrier_{_now()[:19].replace(':','').replace('-','').replace('T','_')}.png"
    Image.fromarray(render(state, t, mouse, w, h)).save(str(carrier), "PNG")
    from mag.whisper_image import encode_image
    enc = encode_image(payload, secret=secret, out=out, carrier=str(carrier), w=w, h=h)
    if enc.get("ok"):
        enc["schema"] = SCHEMA
        enc["layer"] = "register + bus (hidden LSB payload)"
        enc["knots"] = len(state)
        enc["t"] = round(t, 2)
        enc["mouse"] = mouse
    return enc


def bus_decode(path: str, *, secret: str = "") -> dict[str, Any]:
    """Read the hidden bus payload back out of a register frame."""
    from mag.whisper_image import decode_image
    return decode_image(path, secret=secret)


def status() -> dict[str, Any]:
    ok = True
    try:
        import PIL  # noqa: F401
        import numpy  # noqa: F401
    except Exception:
        ok = False
    return {"ok": True, "schema": SCHEMA, "deps": "PIL+numpy", "ready": ok,
            "register": "texture = live swarm state (flock knots)",
            "motion": "t (iTime) + mouse (iMouse) = steering control bus",
            "bus": "LSB hidden payload in the same frame (deniable, keyed)"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="shader_bus", description="Shadertoy-style swarm register + bus")
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("render"); r.add_argument("state_json"); r.add_argument("--t", type=float, default=0.0)
    r.add_argument("--mouse", default=None); r.add_argument("--out", default=None)
    b = sub.add_parser("bus-encode"); b.add_argument("state_json"); b.add_argument("payload")
    b.add_argument("--secret", default=""); b.add_argument("--t", type=float, default=0.0)
    b.add_argument("--mouse", default=None); b.add_argument("--out", default=None)
    d = sub.add_parser("bus-decode"); d.add_argument("png"); d.add_argument("--secret", default="")
    sub.add_parser("status")
    a = p.parse_args(argv)
    m = None
    if a.cmd in ("render", "bus-encode") and getattr(a, "mouse", None):
        try:
            x, y = a.mouse.split(",")
            m = (float(x), float(y))
        except Exception:
            m = None
    try:
        state = json.loads(a.state_json)
    except Exception:
        state = [{"x": 128, "y": 128, "color": [120, 200, 240]}]
    if a.cmd == "render":
        print(json.dumps(register_frame(state, a.t, m, a.out), indent=2, ensure_ascii=False))
    elif a.cmd == "bus-encode":
        print(json.dumps(bus_encode(state, a.payload, secret=a.secret, t=a.t, mouse=m, out=a.out), indent=2, ensure_ascii=False))
    elif a.cmd == "bus-decode":
        print(json.dumps(bus_decode(a.png, secret=a.secret), indent=2, ensure_ascii=False))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    else:
        p.print_help(); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
