"""whisper_image — the whisper protocol carried through IMAGES (image-gen/communication).

The operator's idea (2026-08-10): "by using image gen/communication we can turn our whisper
protocol into something crazy." The whisper/Riddler protocol is already deniable text
(surrogate story + narrative steganography via Bard). THIS module carries the same deniable
payload through an IMAGE — LSB steganography: hide the whisper/territory/steer bytes in the
least-significant bits of a PNG's pixels. To a human it's art/a tileset/map; to a machine with
the private map (the secret) it's a scannable, recoverable message.

Why it's "crazy" and why it fits:
  - The RPG module is ALREADY a steganographic harness: riddler_campaign LAW = "Zero raw data in
    campaign output. All steganographic."; campaign.py = "every room is a territory task, every
    NPC whisper is a Ghost steer." An IMAGE (a treasure map, an NPC portrait, a DF tileset) is the
    natural carrier: it looks like campaign art, its LSBs carry the real whisper.
  - Machine-readable + deniable: any agent/seat can SCAN the image and recover state; anyone who
    just sees the picture sees nothing. Keyed by the private map (secret) — only we decode it.
  - $0 + deterministic: Pillow + numpy only (both present). No LLM, no network.

  encode_image(payload, secret)  -> PNG with payload hidden in LSBs (path + meta).
  decode_image(path, secret)     -> recover payload (only with the right secret).
  encode_whisper(topic, secret)  -> whisper(topic) -> render its scratch + public face as an image.
  decode_whisper_image(png)      -> recover image -> whisper.decode with the private map.
  campaign_carrier()             -> a real campaign-art PNG (df tileset) to hide inside, if present.

Schema: whisper_image.v1
CLI: python -m mag.whisper_image encode "<payload>" [--secret S] [--out png] |
                                      decode <png> [--secret S] |
                                      whisper "<topic>" [--secret S] |
                                      unwhisper <png> [--secret S] | status
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import struct
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

SCHEMA = "whisper_image.v1"
IMG_DIR = ROOT / "memory" / "runs" / "whisper_images"

MAGIC = b"WHSPIMG1"          # 8 bytes header
LEN_FMT = ">I"               # 4-byte big-endian payload length
HEADER_LEN = len(MAGIC) + struct.calcsize(LEN_FMT)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _keystream(secret: bytes, n: int) -> bytes:
    """Deterministic byte keystream from the secret (the private map). Same secret -> same key."""
    seed = int.from_bytes(hashlib.sha256(secret or b"").digest()[:8], "big")
    rng = random.Random(seed)
    return bytes(rng.randrange(256) for _ in range(n))


def _make_carrier(w: int, h: int, seed: int = 7) -> "Any":
    """Deterministic 'abstract art' carrier — looks like a pleasant gradient+noise image."""
    import numpy as np
    rng = np.random.default_rng(seed)
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for c in range(3):
        gx = np.linspace(0, 255, w).astype(np.float32)
        gy = np.linspace(0, 255, h).astype(np.float32)
        layer = (gx[None, :] * 0.55 + gy[:, None] * 0.55)
        layer = layer * (0.6 + 0.4 * rng.random((h, w)))
        arr[:, :, c] = np.clip(layer, 0, 255).astype(np.uint8)
    return arr


def _bits(blob: bytes):
    for b in blob:
        for i in range(8):
            yield (b >> i) & 1  # LSB-first


def _read_bits(flat: "Any", start: int, n: int) -> bytes:
    out = bytearray()
    for b in range(n):
        byte = 0
        for i in range(8):
            byte |= (int(flat[start + b * 8 + i]) & 1) << i
        out.append(byte)
    return bytes(out)


def encode_image(
    payload: str,
    *,
    secret: str = "",
    out: str | None = None,
    carrier: str | None = None,
    w: int = 128,
    h: int = 128,
) -> dict[str, Any]:
    """Hide a payload string in the LSBs of a PNG. $0, deterministic, deniable."""
    import numpy as np
    try:
        from PIL import Image
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"PIL required: {str(e)[:120]}"}

    payload = (payload or "").strip()
    if not payload:
        return {"ok": False, "schema": SCHEMA, "error": "empty payload"}
    data = payload.encode("utf-8")
    key = _keystream(secret.encode("utf-8"), len(data))
    xored = bytes(a ^ b for a, b in zip(data, key))
    blob = MAGIC + struct.pack(LEN_FMT, len(data)) + xored
    nbits = len(blob) * 8

    # carrier image: real campaign art (tileset) if given, else deterministic art
    if carrier:
        try:
            arr = np.array(Image.open(str(carrier)).convert("RGB"))
        except Exception as e:
            return {"ok": False, "schema": SCHEMA, "error": f"carrier unreadable: {str(e)[:120]}"}
        h, w = arr.shape[0], arr.shape[1]
    else:
        arr = _make_carrier(w, h)

    flat = arr.reshape(-1)
    if nbits > len(flat):
        return {"ok": False, "schema": SCHEMA,
                "error": f"payload too big: need {nbits} bits, carrier has {len(flat)}"}
    for i, bit in enumerate(_bits(blob)):
        flat[i] = (int(flat[i]) & ~1) | bit
    arr = flat.reshape(h, w, 3)

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    out_p = Path(out) if out else IMG_DIR / f"whisper_{_now()[:19].replace(':','').replace('-','').replace('T','_')}.png"
    Image.fromarray(arr.astype("uint8")).save(str(out_p), "PNG")

    return {"ok": True, "schema": SCHEMA, "mode": "lsb", "payload": payload,
            "payload_bytes": len(data), "secret_locked": bool(secret),
            "carrier": str(carrier) if carrier else "generated-art",
            "image": str(out_p), "image_bytes": out_p.stat().st_size,
            "w": w, "h": h, "capacity_bytes": (len(flat) // 8) - HEADER_LEN,
            "note": "deniable image whisper — scan the PNG with the private map to recover"}


def decode_image(path: str, *, secret: str = "") -> dict[str, Any]:
    """Recover the payload from an image's LSBs. Only the right secret (private map) decodes it."""
    import numpy as np
    try:
        from PIL import Image
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"PIL required: {str(e)[:120]}"}
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "schema": SCHEMA, "error": "image not found"}
    try:
        arr = np.array(Image.open(str(p)).convert("RGB"))
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"unreadable image: {str(e)[:120]}"}
    flat = arr.reshape(-1)
    if len(flat) < HEADER_LEN * 8:
        return {"ok": False, "schema": SCHEMA, "error": "image too small"}
    magic = _read_bits(flat, 0, len(MAGIC))
    if magic != MAGIC:
        return {"ok": False, "schema": SCHEMA, "error": "no whisper signature in this image",
                "found": magic[:8].hex()}
    (n,) = struct.unpack(LEN_FMT, _read_bits(flat, len(MAGIC) * 8, struct.calcsize(LEN_FMT)))
    if (HEADER_LEN + n) * 8 > len(flat):
        return {"ok": False, "schema": SCHEMA, "error": "payload length out of bounds"}
    xored = _read_bits(flat, HEADER_LEN * 8, n)
    key = _keystream(secret.encode("utf-8"), n)
    data = bytes(a ^ b for a, b in zip(xored, key))
    try:
        payload = data.decode("utf-8")
    except Exception:
        return {"ok": False, "schema": SCHEMA, "error": "decoded bytes not utf-8 (wrong secret?)",
                "secret_locked": bool(secret)}
    return {"ok": True, "schema": SCHEMA, "mode": "lsb", "payload": payload,
            "payload_bytes": n, "secret_locked": bool(secret), "image": str(p)}


def campaign_carrier() -> dict[str, Any]:
    """A real campaign-art PNG to hide inside (DF tileset) if present — else generated art."""
    try:
        from mag.df_tileset import ensure_cached_png
        r = ensure_cached_png() or {}
        p = r.get("png")
        if p and Path(str(p)).is_file():
            return {"ok": True, "carrier": str(p), "note": "DF tileset as whisper carrier"}
    except Exception:
        pass
    return {"ok": True, "carrier": None, "note": "no tileset — use generated art"}


def encode_whisper(topic: str, *, secret: str = "", carrier: str | None = None) -> dict[str, Any]:
    """Whisper a topic (Riddler surrogate) then hide its decode key + public face in an image."""
    try:
        from mag.ghost_whisper import whisper
        rec = whisper(topic)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"whisper failed: {str(e)[:120]}"}
    scratch = str(rec.get("scratch_id") or "")
    public_face = str(rec.get("public_face") or "")
    payload = f"{scratch}\n{public_face}".rstrip()
    if not carrier:
        c = campaign_carrier()
        carrier = c.get("carrier")
    enc = encode_image(payload, secret=secret, carrier=carrier)
    enc["whisper_scratch"] = scratch
    return enc


def decode_whisper_image(path: str, *, secret: str = "") -> dict[str, Any]:
    """Recover an image whisper and decode it with the Riddler private map."""
    r = decode_image(path, secret=secret)
    if not r.get("ok"):
        return r
    text = str(r.get("payload") or "")
    lines = [l for l in text.splitlines() if l.strip()]
    scratch = lines[0] if lines else ""
    try:
        from mag.ghost_whisper import decode as _wdecode
        w = _wdecode(scratch)
        r["whisper"] = w
        r["decoded_topic"] = (w.get("joined_knowledge") or {}).get("ok")
    except Exception as e:
        r["whisper_error"] = str(e)[:120]
    return r


def status() -> dict[str, Any]:
    """Which image-whisper pieces are ready."""
    out: dict[str, Any] = {"schema": SCHEMA, "ok": True, "pillow": False, "numpy": False,
                           "carrier": campaign_carrier()}
    try:
        import PIL  # noqa: F401
        out["pillow"] = True
    except Exception:
        pass
    try:
        import numpy  # noqa: F401
        out["numpy"] = True
    except Exception:
        pass
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="whisper_image", description="whisper protocol through images")
    sub = p.add_subparsers(dest="cmd")
    e = sub.add_parser("encode"); e.add_argument("payload")
    d = sub.add_parser("decode"); d.add_argument("png")
    w = sub.add_parser("whisper"); w.add_argument("topic")
    u = sub.add_parser("unwhisper"); u.add_argument("png")
    for sp in (e, d, w, u):
        sp.add_argument("--secret", default="")
    e.add_argument("--out", default=None); e.add_argument("--carrier", default=None)
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "encode":
        print(json.dumps(encode_image(a.payload, secret=a.secret, out=a.out, carrier=a.carrier), indent=2, ensure_ascii=False))
    elif a.cmd == "decode":
        print(json.dumps(decode_image(a.png, secret=a.secret), indent=2, ensure_ascii=False))
    elif a.cmd == "whisper":
        print(json.dumps(encode_whisper(a.topic, secret=a.secret), indent=2, ensure_ascii=False))
    elif a.cmd == "unwhisper":
        print(json.dumps(decode_whisper_image(a.png, secret=a.secret), indent=2, ensure_ascii=False))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    else:
        p.print_help(); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
