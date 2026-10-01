"""grammar_transfer — THE TRANSFER TEST frozen walker protocol (salon-licensed 2026-09-06).

License terms: memory/runs/salons/unified_fold_20260906/SALON_ARTIFACT.md (test 1, grok-cli).
Hypothesis C1: the cartography grammar transfers across surfaces with ONE frozen protocol.
This file is written ONCE. Per-surface runs change CONFIG ONLY (unit-source + marker words).
If a surface needs new FEATURE code, the grammar is poetry and C1 is DISPUTED.

FROZEN PROTOCOL (byte-identical on every surface):
  carve(units, markers)
    -> per-unit features [size_chars, marker_hits, query_hits('?'), digit_ratio]
    -> CSV -> sha256[:16]
  audit(rows, corrupt_idx)
    -> seed one corrupt unit (frozen corruption verb), recompute with the SAME
       feature function, robust-z (median/MAD, Iglewicz-Hoaglin 3.5) outlier scan;
       PASS iff the flagged unit IS the corrupt unit.
  -> ledger cell per surface (python -m mag.tesuji_map post --axis G ...)

CSV schema (frozen, one header for all surfaces):
  unit_id,size_chars,marker_hits,query_hits,digit_ratio

Frozen corruption verb (same class of occlusion on every surface):
  corrupt(text) = text*3 + text[:len//4], then every marker occurrence -> '?'.
  Fires on size_chars (x~3.25), marker_hits (->0), query_hits (spike), digit_ratio.

Surface configs only (below). Unit-source adapters are CONFIG (the license allows
"unit source" per surface); zero per-surface feature code exists anywhere.

CLI: python -m mag.grammar_transfer A|B|C|all
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import deque
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "memory" / "runs" / "transfer_test_20260906"

Z_THRESH = 3.5          # Iglewicz-Hoaglin modified z-score threshold (frozen)
FEATURES = ("size_chars", "marker_hits", "query_hits", "digit_ratio")
HEADER = "unit_id," + ",".join(FEATURES)

# --------------------------------------------------------------------------
# FROZEN PROTOCOL — nothing below this line is editable per surface.
# --------------------------------------------------------------------------

def features(text: str, markers: tuple[str, ...]) -> tuple[int, int, int, float]:
    """The one feature function. Lowercased matching, frozen feature set."""
    low = text.lower()
    size = len(text)
    marker_hits = sum(low.count(m) for m in markers)
    query_hits = text.count("?")
    digits = sum(ch.isdigit() for ch in text)
    return size, marker_hits, query_hits, digits / max(1, size)


def corrupt(text: str, markers: tuple[str, ...]) -> str:
    """The one corruption verb. Same occlusion class on every surface."""
    grown = text * 3 + text[: len(text) // 4]
    for m in markers:
        grown = grown.replace(m, "?" * len(m))
        grown = grown.replace(m.capitalize(), "?" * len(m))
        grown = grown.replace(m.upper(), "?" * len(m))
    return grown


def carve(units: Iterable[str], markers: tuple[str, ...], out_csv: Path) -> dict:
    """carve -> per-unit features -> CSV -> sha256[:16]. Frozen."""
    rows = []
    for i, text in enumerate(units):
        size, mh, qh, dr = features(text, markers)
        rows.append((i, size, mh, qh, dr))
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    lines = [HEADER] + [",".join(str(v) for v in r) for r in rows]
    blob = "\n".join(lines) + "\n"
    out_csv.write_text(blob, encoding="utf-8")
    sha16 = hashlib.sha256(out_csv.read_bytes()).hexdigest()[:16]
    return {"csv": out_csv, "sha16": sha16, "rows": rows, "n_units": len(rows)}


def _modified_z(values: list[float]) -> list[float]:
    """v3 audit statistic (cross-surface amendment, one rule for ALL surfaces):
    MAD scale; if MAD==0 but the column still varies (zero-inflated/lumpy),
    fall back to IQR scale (IQR/1.349, the standard robust-normal mapping);
    only a fully CONSTANT column treats any deviation as total evidence."""
    s = sorted(values)
    n = len(s)
    med = s[n // 2]
    mad = sorted(abs(v - med) for v in s)[n // 2]
    if mad > 0:
        return [0.6745 * (v - med) / mad for v in values]
    q1, q3 = s[n // 4], s[(3 * n) // 4]
    iqr = q3 - q1
    if iqr == 0:
        return [0.0 if v == med else 1e9 for v in values]
    scale = iqr / 1.349
    return [(v - med) / scale for v in values]


def audit(rows: list[tuple], corrupt_idx: int, markers: tuple[str, ...],
          corrupt_text_of: Callable[[int], str]) -> dict:
    """Seed one corrupt unit, recompute with the SAME feature fn, flag the outlier.
    PASS iff flagged unit == corrupt unit (the audit must point, not just shout)."""
    # recompute features for every unit from its source text (same fn, no new code)
    feat_rows = [features(corrupt_text_of(uid), markers) for (uid, *_rest) in rows]
    zcols = []
    for j in range(4):
        zcols.append(_modified_z([r[j] for r in feat_rows]))
    # v2 audit rule (cross-surface amendment, applied once to ALL surfaces):
    # primary evidence = max |z| over features; ties (zero-inflated columns give
    # many units the same MAD=0 sentinel) break by SUM of |z| — the unit must
    # carry the most aggregate evidence, not merely share an infinite column.
    per_max = [max(abs(zcols[j][i]) for j in range(4)) for i in range(len(feat_rows))]
    per_sum = [sum(abs(zcols[j][i]) for j in range(4)) for i in range(len(feat_rows))]
    flagged = max(range(len(per_max)), key=lambda i: (per_max[i], per_sum[i]))
    ok = flagged == corrupt_idx and per_max[flagged] >= Z_THRESH
    clean = [r for r in feat_rows]
    return {"corrupt_idx": corrupt_idx, "flagged_idx": flagged,
            "max_z": round(per_max[flagged], 2), "evidence_sum": round(per_sum[flagged], 2),
            "threshold": Z_THRESH,
            "verdict": "FLAGGED" if ok else "MISSED",
            "corrupt_features": clean[corrupt_idx]}


def run_surface(name: str, units: list[str], markers: tuple[str, ...],
                corrupt_idx: int | None = None) -> dict:
    """One frozen walk: carve -> CSV+hash -> seeded audit. Byte-identical order."""
    markers = tuple(m.lower() for m in markers)
    out_csv = OUT_DIR / f"surface_{name}.csv"
    res = carve(units, markers, out_csv)
    if corrupt_idx is None:
        corrupt_idx = res["n_units"] // 3  # frozen rule: unit n//3 gets the seed
    src = list(units)
    aud = audit(res["rows"], corrupt_idx, markers,
                corrupt_text_of=lambda i: corrupt(src[i], markers) if i == corrupt_idx else src[i])
    return {"surface": name, "n_units": res["n_units"], "csv": str(out_csv.relative_to(ROOT)),
            "sha16": res["sha16"], "audit": aud,
            "first_rows": res["rows"][:3], "last_row": res["rows"][-1]}

# --------------------------------------------------------------------------
# CONFIG ONLY below — unit sources + marker words. No feature code.
# --------------------------------------------------------------------------

def units_chunks(path: Path, n: int) -> list[str]:
    """Generic any-text source: n equal byte chunks (surface A config)."""
    raw = path.read_bytes()
    step = len(raw) // n
    return [raw[i * step:(i + 1) * step if i < n - 1 else len(raw)]
            .decode("utf-8", errors="replace") for i in range(n)]


def units_sections(paths: list[Path], delim: str, must_contain: str = "") -> list[str]:
    """Generic delimiter splitter: terminal sections (surface B config).
    must_contain: optional substring a delimiter line must carry to start a new
    unit (config filter — Marathon nav stubs share the '### ' prefix)."""
    units = []
    for p in paths:
        body = p.read_text(encoding="utf-8", errors="replace")
        cur = []
        started = False  # content before the first delimiter is preamble, not a unit
        for line in body.splitlines():
            if line.startswith(delim) and must_contain in line:
                if started and cur:
                    units.append("\n".join(cur))
                cur, started = [], True
            elif started:
                cur.append(line)
        if started and cur:
            units.append("\n".join(cur))
    return units


def units_grid_rows(n_bands: int) -> list[str]:
    """Surface C config: the physics-lab eikonal travel-time grid (BFS block copied
    VERBATIM from notebooks/shadow_work_physics.py lines 61-95), rows serialized to
    text: reached/path cell -> travel-time digit (T mod 10), wall -> '#',
    unreached -> '.'. Rows sliced into n_bands consecutive bands = units."""
    import numpy as np
    GW, GH = 480, 270                    # eikonal grid (canvas W=480, H=270)
    WORLD_W, WORLD_H = 2.0, 2.7          # arena extents in meters
    walls = [                            # [cx,cy,halfw,halfh] world coords
        [0.5, 0.5, 0.03, 0.30], [0.25, 0.30, 0.20, 0.03], [0.25, 0.72, 0.20, 0.03],
        [0.50, 0.50, 0.03, 0.28], [0.75, 0.30, 0.20, 0.03], [0.75, 0.72, 0.20, 0.03],
        [0.12, 0.52, 0.03, 0.22], [0.88, 0.50, 0.03, 0.22],
        [0.62, 0.14, 0.03, 0.16], [0.38, 0.88, 0.03, 0.16],
    ]
    walls = [[w[0] * 2, w[1] * 2.7, w[2] * 2, w[3] * 2.7] for w in walls]
    CHEESE = (1.2, 1.35)

    def sdf(x, y):
        d = 1e9
        for cx, cy, hw, hh in walls:
            ax, ay = abs(x - cx) - hw, abs(y - cy) - hh
            d = min(d, max(ax, ay))
        return min(d, min(x - 0.05, WORLD_W - 0.05 - x, y - 0.05, WORLD_H - 0.05 - y))

    xs = (np.arange(GW) + 0.5) / GW * WORLD_W
    ys = (np.arange(GH) + 0.5) / GH * WORLD_H
    XX, YY = np.meshgrid(xs, ys)
    wall_mask = np.vectorize(sdf)(XX, YY) < 0.012

    T = np.full((GH, GW), np.inf)
    sx, sy = int(CHEESE[0] / WORLD_W * GW), int(CHEESE[1] / WORLD_H * GH)
    T[sy, sx] = 0.0
    q = deque([(sx, sy)])
    while q:
        x, y = q.popleft()
        d = T[y, x] + 1.0
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < GW and 0 <= ny < GH and not wall_mask[ny, nx] and T[ny, nx] > d:
                T[ny, nx] = d
                q.append((nx, ny))
    # --- serialization: the ONLY surface-C-specific lines, and they are the
    # unit-source config (cells -> chars), not feature code ---
    digits = np.where(np.isfinite(T), (np.nan_to_num(T, posinf=0) % 10).astype(int), 0)
    lines = []
    for r in range(GH):
        chars = []
        for c in range(GW):
            if np.isfinite(T[r, c]):
                chars.append(str(digits[r, c]))
            elif wall_mask[r, c]:
                chars.append("#")
            else:
                chars.append(".")
        lines.append("".join(chars))
    per = GH // n_bands
    return ["\n".join(lines[b * per:(b + 1) * per]) for b in range(n_bands)]


SURFACES: dict[str, dict] = {
    "A": {"label": "LLM bank (control)",
          "markers": ("standing wave", "tri-state", "falsifier", "cite"),
          "units": lambda: units_chunks(ROOT / "memory" / "thinking" / "app_reasoning.jsonl", 10)},
    "B": {"label": "GAME/literary — Marathon terminals",
          "markers": ("durandal", "leela", "rampancy", "melancholia", "security"),
          "units": lambda: units_sections(
              [p for sub in ("m1", "m2") for p in
               sorted((ROOT / "research" / "gaming_corpus" / "marathon_terminals" / sub).glob("*.txt"))],
              "### ", "(Terminal")},
    "C": {"label": "GAME/grid — eikonal travel-time rows",
          "markers": tuple("0123456789#"),  # digits = path cells, '#' = dead/wall cells
          "units": lambda: units_grid_rows(10)},
}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    which = sys.argv[1].upper() if len(sys.argv) > 1 else "ALL"
    keys = list(SURFACES) if which == "ALL" else [which]
    for k in keys:
        cfg = SURFACES[k]
        units = cfg["units"]()
        res = run_surface(k, units, cfg["markers"])
        print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
