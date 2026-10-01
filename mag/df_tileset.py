"""Dwarf Fortress tileset bridge — load user's local DF art (no redistribute).

Default Steam path on this operator machine; override MAG_DF_ROOT / MAG_DF_TILESET.
Schema helpers for table REST. CP437 sheet = 16×16 tiles in 256×256 image.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from config import ROOT

# Operator-local default (Windows Steam). Not shipped in Mag repo.
_DEFAULT_DF = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Dwarf Fortress")
_PREFERRED = (
    "curses_square_16x16.png",
    "curses_square_16x16.bmp",
    "curses_800x600.png",
    "curses_800x600.bmp",
    "curses_640x300.png",
    "curses_640x300.bmp",
)

# Our map glyphs → CP437 code points (index into DF sheet row-major 16×16)
CHAR_TO_CP437: dict[str, int] = {
    " ": 0x20,
    "#": 0xDB,  # full block wall
    ".": 0xFA,  # middle dot floor
    "@": 0x01,  # smiling face — classic player (or 0x40 @)
    "g": 0x67,  # g
    "+": 0xCE,  # double cross door
    "≈": 0xF7,  # approx equals / water-ish prop
    "^": 0x1E,  # up triangle
    "v": 0x1F,  # down
    "<": 0x11,  # left
    ">": 0x10,  # right
    "-": 0xC4,
    "|": 0xB3,
}

# Prefer @ as @ for readability in some skins
CHAR_TO_CP437["@"] = 0x40


def df_root() -> Path:
    env = (os.environ.get("MAG_DF_ROOT") or "").strip()
    if env:
        return Path(env)
    return _DEFAULT_DF


def resolve_tileset_path() -> Path | None:
    env = (os.environ.get("MAG_DF_TILESET") or "").strip()
    if env:
        p = Path(env)
        return p if p.is_file() else None
    art = df_root() / "data" / "art"
    if not art.is_dir():
        return None
    for name in _PREFERRED:
        p = art / name
        if p.is_file():
            return p
    return None


def cache_png_path() -> Path:
    d = ROOT / "dashboard" / "static" / "tiles"
    d.mkdir(parents=True, exist_ok=True)
    return d / "df_curses_local.png"


def ensure_cached_png() -> dict[str, Any]:
    """Copy/convert DF tileset into Mag static cache for HTTP serving.

    Does not commit Bay12 art to git — local cache only.
    """
    src = resolve_tileset_path()
    if not src:
        return {
            "ok": False,
            "error": "DF tileset not found",
            "hint": "Set MAG_DF_ROOT or MAG_DF_TILESET; expected data/art/curses_square_16x16.*",
            "df_root": str(df_root()),
        }
    dest = cache_png_path()
    try:
        # Refresh if source newer or missing
        if dest.is_file() and dest.stat().st_mtime >= src.stat().st_mtime:
            pass
        else:
            from PIL import Image

            im = Image.open(src)
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA")
            else:
                im = im.convert("RGBA")
            # DF often uses magenta / black as key — keep as-is for canvas
            im.save(dest, "PNG")
        tw = th = 16
        # infer tile size from square sheet
        w, h = Image.open(dest).size
        if w == h and w % 16 == 0:
            tw = th = w // 16
        return {
            "ok": True,
            "source": str(src),
            "url": "/static/tiles/df_curses_local.png",
            "path": str(dest.relative_to(ROOT)).replace("\\", "/"),
            "tile_w": tw,
            "tile_h": th,
            "sheet_w": w,
            "sheet_h": h,
            "cols": 16,
            "rows": 16,
            "char_map": CHAR_TO_CP437,
            "license_note": "Local DF install asset — do not redistribute; Mag only references your copy",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "source": str(src)}


def tileset_meta() -> dict[str, Any]:
    src = resolve_tileset_path()
    cached = cache_png_path()
    return {
        "ok": bool(src),
        "df_root": str(df_root()),
        "df_root_exists": df_root().is_dir(),
        "source": str(src) if src else None,
        "cached": cached.is_file(),
        "cache_url": "/static/tiles/df_curses_local.png" if cached.is_file() else None,
        "char_map": CHAR_TO_CP437,
    }
