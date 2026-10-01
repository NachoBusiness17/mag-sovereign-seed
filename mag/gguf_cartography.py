"""gguf_cartography — pure-stdlib GGUF weights-volume cartographer (shadow work sw50).

Turns the model already on our disk into an environment you traverse: parse the GGUF
container with zero third-party deps, census every tensor, and render per-tensor
volume + statistics.

Honesty law (v1): dtype 0 (F32) and 1 (F16) get EXACT float statistics (mean/std/
min/max/rms) computed on decoded elements of the sampled windows. EVERY quantized
dtype (2+) gets byte-level PROXY statistics only (zero-byte ratio, byte entropy,
byte mean/std) — NO dequantization in v1, records are labeled PROXY.

$0: no network, no pip. numpy is used when importable with a pure-python fallback
(streaming; works without it). Read-only on the GGUF: header via buffered reads,
tensor payload via a read-only mmap sampled in aligned windows — never slurped.

GGUF v2/v3 container layout (https://github.com/ggml-org/ggml/blob/master/docs/gguf.md):
  magic b"GGUF" | version le32 | tensor_count le64 | metadata_kv_count le64
  then typed metadata kvs, then tensor infos (name, n_dims le32, dims le64*,
  dtype le32, offset le64 relative to data section start), then the data section,
  aligned to `general.alignment` (default 32).

CLI:
  python -m mag.gguf_cartography scan <path.gguf> [--sample-mb 4] [--out PATH]
  python -m mag.gguf_cartography summary [JSON_PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import mmap
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "state" / "shadow_work" / "weights_volume_qwen3b.json"
MAGIC = b"GGUF"
DEFAULT_ALIGNMENT = 32

try:  # optional accelerator — everything below works without it
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None

# ggml_type -> (name, itemsize or None-if-block-quant, block_elems, block_bytes)
DTYPES = {
    0: ("F32", 4, 1, 4),
    1: ("F16", 2, 1, 2),
    2: ("Q4_0", None, 32, 18),
    3: ("Q4_1", None, 32, 20),
    4: ("Q4_2", None, 32, 14),   # removed upstream; kept for old files
    5: ("Q4_3", None, 32, 18),   # removed upstream; kept for old files
    6: ("Q5_0", None, 32, 22),
    7: ("Q5_1", None, 32, 24),
    8: ("Q8_0", None, 32, 34),
    9: ("Q8_1", None, 32, 40),
    10: ("Q2_K", None, 256, 84),
    11: ("Q3_K", None, 256, 110),
    12: ("Q4_K", None, 256, 144),
    13: ("Q5_K", None, 256, 176),
    14: ("Q6_K", None, 256, 210),
    15: ("Q8_K", None, 256, 200),
    16: ("IQ2_XXS", None, 256, 66),
    17: ("IQ2_XS", None, 256, 50),
    18: ("IQ3_XXS", None, 256, 98),
    19: ("IQ1_S", None, 256, 50),
    20: ("IQ4_NL", None, 32, 16),
    21: ("IQ3_S", None, 256, 110),
    22: ("IQ2_S", None, 256, 65),
    23: ("IQ4_XS", None, 256, 40),
    24: ("I8", 1, 1, 1),
    25: ("I16", 2, 1, 2),
    26: ("I32", 4, 1, 4),
    27: ("I64", 8, 1, 8),
    28: ("F64", 8, 1, 8),
    29: ("IQ1_M", None, 256, 56),
    30: ("BF16", 2, 1, 2),
}
EXACT_DTYPES = {0, 1}  # F32, F16 — everything else is byte-proxy in v1
FILE_TYPES = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 7: "Q8_0", 8: "Q5_0",
              9: "Q5_1", 10: "Q2_K", 11: "Q3_K_S", 12: "Q3_K_M", 13: "Q3_K_L",
              14: "Q4_K_S", 15: "Q4_K_M", 16: "Q5_K_S", 17: "Q5_K_M", 18: "Q6_K",
              19: "IQ2_XXS", 20: "IQ2_XS", 21: "Q2_K_S", 22: "Q3_K_XS",
              24: "IQ1_S", 25: "IQ4_NL", 26: "IQ3_S", 27: "IQ2_S", 28: "IQ4_XS",
              29: "IQ1_M", 30: "BF16"}


class GGUFError(Exception):
    pass


class _Reader:
    """Little-endian primitive reader over a buffered file object."""

    def __init__(self, f):
        self.f = f

    def raw(self, n: int) -> bytes:
        b = self.f.read(n)
        if b is None or len(b) != n:
            raise GGUFError(f"unexpected EOF (wanted {n} bytes, got {len(b) if b else 0})")
        return b

    def u8(self) -> int:
        return self.raw(1)[0]

    def i8(self) -> int:
        return struct.unpack("<b", self.raw(1))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.raw(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.raw(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.raw(8))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self.raw(8))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.raw(4))[0]

    def f64(self) -> float:
        return struct.unpack("<d", self.raw(8))[0]

    def string(self) -> str:
        n = self.u64()
        return self.raw(n).decode("utf-8", errors="replace")

    def value(self, vtype: int):
        if vtype == 0:
            return self.u8()
        if vtype == 1:
            return self.i8()
        if vtype == 2:
            return struct.unpack("<H", self.raw(2))[0]
        if vtype == 3:
            return struct.unpack("<h", self.raw(2))[0]
        if vtype == 4:
            return self.u32()
        if vtype == 5:
            return self.i32()
        if vtype == 6:
            return self.f32()
        if vtype == 7:
            return bool(self.u8())
        if vtype == 8:
            return self.string()
        if vtype == 9:  # array: elem_type le32, count le64, elems
            etype = self.u32()
            count = self.u64()
            return {"__array__": True, "elem_type": etype, "count": count,
                    "items": [self.value(etype) for _ in range(count)]}
        if vtype == 10:
            return self.u64()
        if vtype == 11:
            return self.i64()
        if vtype == 12:
            return self.f64()
        raise GGUFError(f"unknown metadata value type {vtype}")


def align_up(x: int, a: int) -> int:
    return (x + a - 1) // a * a


def tensor_nbytes(dims, dtype_id: int) -> int:
    name, itemsize, block_elems, block_bytes = DTYPES[dtype_id]
    n = 1
    for d in dims:
        n *= d
    if itemsize is not None:
        return n * itemsize, n
    blocks = (n + block_elems - 1) // block_elems
    return blocks * block_bytes, n


def parse_header(path: Path):
    """Parse header + metadata + tensor infos. Returns (doc, data_start)."""
    size = path.stat().st_size
    with path.open("rb") as f:
        r = _Reader(f)
        if r.raw(4) != MAGIC:
            raise GGUFError("not a GGUF file (bad magic)")
        version = r.u32()
        if version < 1 or version > 3:
            raise GGUFError(f"unsupported GGUF version {version}")
        tensor_count = r.u64()
        kv_count = r.u64()

        meta = {}
        for _ in range(kv_count):
            key = r.string()
            vtype = r.u32()
            val = r.value(vtype)
            # keep small scalars and short strings; big arrays -> count only
            if isinstance(val, dict) and val.get("__array__"):
                meta[key] = {"elem_type": DTYPES.get(val["elem_type"], ("?",))[0],
                             "count": val["count"]}
            else:
                meta[key] = val
        infos = []
        for _ in range(tensor_count):
            name = r.string()
            n_dims = r.u32()
            dims = [r.u64() for _ in range(n_dims)]
            dtype_id = r.u32()
            if dtype_id not in DTYPES:
                raise GGUFError(f"unknown tensor dtype {dtype_id} on {name!r}")
            offset = r.u64()
            infos.append({"name": name, "dims": dims,
                          "dtype_id": dtype_id, "offset": offset})
        header_end = f.tell()
    alignment = meta.get("general.alignment", DEFAULT_ALIGNMENT)
    if not isinstance(alignment, int) or alignment <= 0:
        alignment = DEFAULT_ALIGNMENT
    data_start = align_up(header_end, alignment)
    return {"version": version, "tensor_count": tensor_count,
            "kv_count": kv_count, "meta": meta, "infos": infos,
            "file_size": size, "header_end": header_end,
            "alignment": alignment, "data_start": data_start}, data_start


def sample_windows(nbytes: int, budget: int, unit: int, n_windows: int = 16):
    """Evenly-spaced aligned windows totaling ~budget bytes. unit = block/item size."""
    if nbytes <= 2 * budget:
        return [(0, nbytes)]
    window = max(unit, (budget // n_windows // unit) * unit)
    windows = []
    for i in range(n_windows):
        a = (i * (nbytes - window)) // (n_windows - 1)
        a = (a // unit) * unit
        windows.append((a, window))
    return windows


# ---------------- stats backends ----------------

def _entropy_from_hist(hist, total: int) -> float:
    e = 0.0
    for c in hist:
        if c:
            p = c / total
            e -= p * math.log2(p)
    return e


def byte_proxy(mv) -> dict:
    """Byte-level PROXY stats over a memoryview of sampled bytes."""
    total = len(mv)
    if _np is not None:
        arr = _np.frombuffer(mv, dtype=_np.uint8)
        hist = _np.bincount(arr, minlength=256)
        zero = int(hist[0])
        mean = float(arr.mean())
        std = float(arr.std())
    else:
        counts = [0] * 256
        for b in mv:
            counts[b] += 1
        hist = counts
        zero = counts[0]
        mean = sum(i * c for i, c in enumerate(counts)) / total
        var = sum(c * (i - mean) ** 2 for i, c in enumerate(counts)) / total
        std = math.sqrt(var)
    return {"mode": "PROXY_bytes",
            "sampled_bytes": total,
            "zero_byte_ratio": round(zero / total, 6),
            "byte_entropy_bits": round(_entropy_from_hist(hist, total), 4),
            "byte_mean": round(mean, 3),
            "byte_std": round(std, 3)}


def exact_float_stats(mv, dtype_name: str) -> dict:
    """EXACT float stats over decoded F32/F16 sampled elements."""
    if _np is not None:
        if dtype_name == "F32":
            x = _np.frombuffer(mv, dtype="<f4").astype(_np.float64)
        else:
            x = _np.frombuffer(mv, dtype="<f2").astype(_np.float64)
        n = int(x.size)
        mean = float(x.mean())
        std = float(x.std())
        rms = float(math.sqrt(float((x * x).mean())))
        return {"mode": "EXACT_floats", "n": n, "mean": round(mean, 6),
                "std": round(std, 6), "min": round(float(x.min()), 6),
                "max": round(float(x.max()), 6), "rms": round(rms, 6)}
    fmt, isz = ("<f", 4) if dtype_name == "F32" else ("<e", 2)
    n = len(mv) // isz
    s = ss = s2 = 0.0
    mn, mx = float("inf"), float("-inf")
    for (v,) in struct.iter_unpack(fmt, mv[: n * isz]):
        s += v
        ss += v * v
        mn = min(mn, v)
        mx = max(mx, v)
    mean = s / n
    std = math.sqrt(ss / n - mean * mean)
    return {"mode": "EXACT_floats", "n": n, "mean": round(mean, 6),
            "std": round(std, 6), "min": round(mn, 6), "max": round(mx, 6),
            "rms": round(math.sqrt(ss / n), 6)}


# ---------------- scan ----------------

def scan(path: Path, sample_mb: float, out: Path) -> dict:
    doc, data_start = parse_header(path)
    meta = doc["meta"]
    infos = doc["infos"]
    budget = int(sample_mb * 1024 * 1024)

    tensors = []
    total_bytes = 0
    max_end = data_start
    with path.open("rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            for info in infos:
                nbytes, n_elems = tensor_nbytes(info["dims"], info["dtype_id"])
                dtype_name, itemsize, block_elems, block_bytes = DTYPES[info["dtype_id"]]
                abs_start = data_start + info["offset"]
                abs_end = abs_start + nbytes
                if abs_end > doc["file_size"]:
                    raise GGUFError(f"tensor {info['name']!r} overruns file "
                                    f"({abs_end} > {doc['file_size']})")
                unit = itemsize if itemsize else block_bytes
                windows = sample_windows(nbytes, budget, unit)
                rec = {"name": info["name"], "dims": info["dims"],
                       "dtype_id": info["dtype_id"], "dtype": dtype_name,
                       "n_elems": n_elems, "nbytes": nbytes,
                       "sampled_bytes": 0}
                stats_acc = []
                for a, w in windows:
                    blob = mm[abs_start + a: abs_start + a + w]  # bytes copy, ~256KB max
                    if info["dtype_id"] in EXACT_DTYPES:
                        stats_acc.append(exact_float_stats(blob, dtype_name))
                    else:
                        stats_acc.append(byte_proxy(blob))
                if info["dtype_id"] in EXACT_DTYPES:
                    n = sum(s["n"] for s in stats_acc)
                    if len(stats_acc) == 1:
                        st = stats_acc[0]
                    else:  # pooled across windows
                        mean = sum(s["mean"] * s["n"] for s in stats_acc) / n
                        var = sum(s["std"] ** 2 * s["n"] for s in stats_acc) / n
                        st = {"mode": "EXACT_floats", "n": n, "mean": round(mean, 6),
                              "std": round(math.sqrt(var), 6),
                              "min": min(s["min"] for s in stats_acc),
                              "max": max(s["max"] for s in stats_acc),
                              "rms": round(math.sqrt(var + mean * mean), 6)}
                    rec["stats"] = st
                    rec["sampled_bytes"] = n * itemsize
                else:
                    total_s = sum(s["sampled_bytes"] for s in stats_acc)
                    if len(stats_acc) == 1:
                        st = stats_acc[0]
                    else:
                        zero = sum(s["zero_byte_ratio"] * s["sampled_bytes"]
                                   for s in stats_acc) / total_s
                        ent = sum(s["byte_entropy_bits"] * s["sampled_bytes"]
                                  for s in stats_acc) / total_s
                        bmean = sum(s["byte_mean"] * s["sampled_bytes"]
                                    for s in stats_acc) / total_s
                        bstd = sum(s["byte_std"] * s["sampled_bytes"]
                                   for s in stats_acc) / total_s
                        st = {"mode": "PROXY_bytes", "sampled_bytes": total_s,
                              "zero_byte_ratio": round(zero, 6),
                              "byte_entropy_bits": round(ent, 4),
                              "byte_mean": round(bmean, 3),
                              "byte_std": round(bstd, 3)}
                    rec["stats"] = st
                    rec["sampled_bytes"] = total_s
                tensors.append(rec)
                total_bytes += nbytes
                max_end = max(max_end, abs_end)

    layers = group_layers(tensors)
    gradient = layer_gradient(layers)

    ft = meta.get("general.file_type")
    out_doc = {
        "schema": "weights_volume/v1",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(path),
        "file_size": doc["file_size"],
        "gguf_version": doc["version"],
        "arch": meta.get("general.architecture"),
        "model_name": meta.get("general.name"),
        "quant_file_type": FILE_TYPES.get(ft, ft),
        "alignment": doc["alignment"],
        "header_bytes": doc["header_end"],
        "data_start": data_start,
        "metadata_kv_count": doc["kv_count"],
        "tensor_count": len(tensors),
        "context_length": meta.get(f"{meta.get('general.architecture', '')}.context_length"),
        "block_count": meta.get(f"{meta.get('general.architecture', '')}.block_count"),
        "totals": {"tensor_data_bytes": total_bytes,
                   "data_section_used": max_end - data_start,
                   "unaccounted_bytes": doc["file_size"] - max_end,
                   "coverage_of_file": round(total_bytes / doc["file_size"], 6)},
        "sample_policy": {"sample_mb": sample_mb, "windows_per_tensor": 16,
                          "exact_dtypes": [DTYPES[d][0] for d in EXACT_DTYPES],
                          "proxy_note": "quantized dtypes: byte-level proxies only, NO dequant (v1)"},
        "layer_gradient": gradient,
        "layers": layers,
        "tensors": tensors,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(out_doc, indent=1), encoding="utf-8")
    return out_doc


# ---------------- grouping + gradient ----------------

def classify(name: str):
    if name.startswith("token_embd"):
        return "embedding", None
    if name.startswith("output_norm"):
        return "norm", None
    if name.startswith("output."):
        return "output_head", None
    if name.startswith("blk."):
        rest = name.split(".", 2)[2] if name.count(".") >= 2 else ""
        idx = int(name.split(".")[1])
        if rest.startswith("attn_norm") or rest.startswith("ffn_norm"):
            return "norm", idx
        if rest.startswith("attn"):
            return "attn", idx
        if rest.startswith("ffn"):
            return "mlp", idx
        return "other", idx
    return "other", None


def group_layers(tensors) -> list:
    by_idx = {}
    for t in tensors:
        grp, idx = classify(t["name"])
        if idx is None:
            continue
        by_idx.setdefault(idx, {"layer": idx, "norm_rms": None,
                                "norm_tensors": 0,
                                "attn_entropy": [], "mlp_entropy": [],
                                "attn_zero": [], "mlp_zero": [],
                                "nbytes_by_group": {}})
        L = by_idx[idx]
        L["nbytes_by_group"][grp] = L["nbytes_by_group"].get(grp, 0) + t["nbytes"]
        st = t["stats"]
        if st["mode"] == "EXACT_floats":
            if grp == "norm":
                L["norm_tensors"] += 1
                L["norm_rms"] = st["rms"] if L["norm_rms"] is None \
                    else round((L["norm_rms"] + st["rms"]) / 2, 6)
        else:
            if grp == "attn":
                L["attn_entropy"].append(st["byte_entropy_bits"])
                L["attn_zero"].append(st["zero_byte_ratio"])
            elif grp == "mlp":
                L["mlp_entropy"].append(st["byte_entropy_bits"])
                L["mlp_zero"].append(st["zero_byte_ratio"])
    layers = []
    for idx in sorted(by_idx):
        L = by_idx[idx]
        L["attn_entropy_mean"] = round(sum(L["attn_entropy"]) / len(L["attn_entropy"]), 4) if L["attn_entropy"] else None
        L["mlp_entropy_mean"] = round(sum(L["mlp_entropy"]) / len(L["mlp_entropy"]), 4) if L["mlp_entropy"] else None
        L["attn_zero_mean"] = round(sum(L["attn_zero"]) / len(L["attn_zero"]), 6) if L["attn_zero"] else None
        L["mlp_zero_mean"] = round(sum(L["mlp_zero"]) / len(L["mlp_zero"]), 6) if L["mlp_zero"] else None
        for k in ("attn_entropy", "mlp_entropy", "attn_zero", "mlp_zero"):
            L.pop(k)
        layers.append(L)
    return layers


def layer_gradient(layers) -> dict:
    pts = [(L["layer"], L["norm_rms"]) for L in layers if L["norm_rms"] is not None]
    if len(pts) < 3:
        return {"basis": "insufficient exact F32/F16 norm tensors", "n": len(pts),
                "verdict": "UNPROVEN"}
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(pts)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in pts)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    slope = sxy / sxx
    r = sxy / math.sqrt(sxx * syy) if syy else 0.0
    first, last = ys[0], ys[-1]
    ratio = last / first if first else None
    geo = ratio ** (1.0 / (n - 1)) if ratio and ratio > 0 else None
    # classify on end-to-end change, not linear slope: real weight-norm ramps are
    # geometric (late-network), which a linear-fit threshold under-calls as FLAT.
    if ratio is None:
        verdict = "UNPROVEN"
    elif ratio >= 1.25:
        verdict = "RISES"
    elif ratio <= 0.8:
        verdict = "FALLS"
    else:
        verdict = "FLAT"
    return {"basis": "exact F32/F16 RMS-norm weights, one value per layer",
            "verdict_basis": f"first-to-last ratio {round(ratio, 4) if ratio else None} "
                             f"(thresholds: >=1.25 RISES, <=0.8 FALLS)",
            "n_layers": n, "slope_per_layer": round(slope, 8),
            "slope_relative": round(slope / my, 5), "pearson_r": round(r, 4),
            "first_layer_rms": first, "last_layer_rms": last,
            "first_to_last_ratio": round(ratio, 4) if ratio else None,
            "geometric_growth_per_layer": round(geo, 5) if geo else None,
            "verdict": verdict}


# ---------------- summary ----------------

def summarize(path: Path) -> str:
    d = json.loads(path.read_text(encoding="utf-8"))
    lines = []
    lines.append(f"weights-volume: {d.get('model_name')} arch={d.get('arch')} "
                 f"quant={d.get('quant_file_type')} gguf_v{d.get('gguf_version')}")
    lines.append(f"file {d['file_size']:,} B | header {d['header_bytes']:,} B | "
                 f"tensors {d['tensor_count']} | blocks {d.get('block_count')} | "
                 f"tensor data {d['totals']['tensor_data_bytes']:,} B "
                 f"({d['totals']['coverage_of_file']*100:.2f}% of file, "
                 f"{d['totals']['unaccounted_bytes']:,} B unaccounted)")
    by_group = {}
    for t in d["tensors"]:
        g, _ = classify(t["name"])
        by_group.setdefault(g, {"n": 0, "bytes": 0})
        by_group[g]["n"] += 1
        by_group[g]["bytes"] += t["nbytes"]
    lines.append("groups: " + " | ".join(
        f"{g}: {v['n']} tensors, {v['bytes']:,} B"
        for g, v in sorted(by_group.items(), key=lambda kv: -kv[1]['bytes'])))
    g = d.get("layer_gradient", {})
    lines.append(f"LAYER GRADIENT: {g.get('verdict')} "
                 f"(slope/layer={g.get('slope_per_layer')}, rel={g.get('slope_relative')}, "
                 f"r={g.get('pearson_r')}, first={g.get('first_layer_rms')}, "
                 f"last={g.get('last_layer_rms')}, ratio={g.get('first_to_last_ratio')})")
    lines.append(f"{'blk':>4} {'norm_rms':>10} {'attn_ent':>9} {'mlp_ent':>9} "
                 f"{'attn_zero':>10} {'mlp_zero':>10}")
    for L in d.get("layers", []):
        def fmt(v, w=9):
            return f"{v:.4f}".rjust(w) if isinstance(v, float) else "-".rjust(w)
        lines.append(f"{L['layer']:>4} {fmt(L['norm_rms'], 10)} "
                     f"{fmt(L['attn_entropy_mean'])} {fmt(L['mlp_entropy_mean'])} "
                     f"{fmt(L['attn_zero_mean'], 10)} {fmt(L['mlp_zero_mean'], 10)}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gguf_cartography",
                                 description="pure-stdlib GGUF weights-volume cartographer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan", help="parse + census a GGUF file")
    p_scan.add_argument("path")
    p_scan.add_argument("--sample-mb", type=float, default=4.0)
    p_scan.add_argument("--out", default=str(DEFAULT_OUT))
    p_sum = sub.add_parser("summary", help="print aggregates from a weights JSON")
    p_sum.add_argument("json", nargs="?", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    if args.cmd == "scan":
        path = Path(args.path)
        out = Path(args.out)
        doc = scan(path, args.sample_mb, out)
        print(f"scanned {path.name}: {doc['tensor_count']} tensors, "
              f"{doc['totals']['tensor_data_bytes']:,} B data, "
              f"quant={doc['quant_file_type']}, blocks={doc.get('block_count')}")
        print(f"layer gradient: {doc['layer_gradient'].get('verdict')} "
              f"({doc['layer_gradient']})")
        top = sorted(doc["tensors"], key=lambda t: -t["nbytes"])[:10]
        print("top tensors by volume:")
        for t in top:
            print(f"  {t['name']:<40} {t['dtype']:<7} {str(t['dims']):<24} {t['nbytes']:>13,} B")
        print(f"written: {out}")
    else:
        print(summarize(Path(args.json)))


if __name__ == "__main__":
    main(sys.argv[1:])
