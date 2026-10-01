"""tesuji_fire — the T1 executor for the probe grid (mission "t1fire", operator "1 go").

Bones from the 09-06 gridder-walk build (SSRF egress guard, idempotent posted-cell skip,
length-wall-is-a-datum grammar), AMENDED 2026-09-07 onto the provider seam per mission:
  - KEYS: resolved only through models.providers machinery (z_ai2 Pro, z_ai3 Lite fallback)
    — this module never reads a raw key env var, never echoes, never stores a key.
  - METERED-UNTIL-RECEIPTED: every call lands a models.quota.record_usage row AND a fire
    receipt in watch/T1_FIRE_RAW_20260906.jsonl; cumulative results in
    state/tesuji_t1_results.json + watch/T1_FIRE_SUMMARY_20260906.json.
  - RETRY LAW: one retry after 5s per lane; a finally-failed cell is recorded UNPROVEN and
    the grid CONTINUES (never aborts the mission on one dead call).
  - RQ4 (gap-3 closure): A1 effort-low-vs-high IS the frozen/tail teaching-token split —
    measured frozen_in (prompt_tokens) / tail_out (completion_tokens) / reasoning~tok /
    visible~tok land verbatim in BOTH A1 cells of each variant (posted after the pair).
  - GO GATE (double, kept): state/T1_GO_20260906.md receipt AND --go flag.
Verdict grammar (charter): SUPPORTED = parsed-to-expected (A2 COMPLY); SHADOW = A2
refusal/hedge; DISPUTED = wrong/absent parse; UNPROVEN = fire failed / length wall.

CLI:
  python -m mag.tesuji_fire plan                    # $0 estimate + cells to fire (no network)
  python -m mag.tesuji_fire run --go --limit 1      # canary
  python -m mag.tesuji_fire run --go                # whole grid (idempotent, resumes)
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mag.tesuji_map import LEDGER, post, verify
from mag.tesuji_probes import (PRICING_USD_MTOK, apply_parser, build_grid, cell_name,
                               check, cost_estimate, render_prompt, variants)

ROOT = Path(__file__).resolve().parent.parent
GRID_JSON = ROOT / "watch" / "TESUJI_GRID_T1_20260906.json"
GO_FILE = ROOT / "state" / "T1_GO_20260906.md"
RAW_PATH = ROOT / "watch" / "T1_FIRE_RAW_20260906.jsonl"
SUMMARY_PATH = ROOT / "watch" / "T1_FIRE_SUMMARY_20260906.json"
RESULTS_PATH = ROOT / "state" / "tesuji_t1_results.json"
ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"
PINNED_SCHEME = "https"
PINNED_HOST = "api.z.ai"
LANES = ("z_ai2", "z_ai3")  # funded lanes: Pro first, Lite fallback (law-15 paced)
MODEL = "glm-5.3-flash"
SEAT = "t1fire"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urllib.error.HTTPError(newurl, code, "redirects disabled by egress guard",
                                     headers, fp)


_OPENER = urllib.request.build_opener(_NoRedirect)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _assert_global_ips(host: str) -> None:
    infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise SystemExit(f"egress guard: {host} resolves to non-global {ip}")


def _guard_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != PINNED_SCHEME or parts.hostname != PINNED_HOST:
        raise SystemExit(f"egress guard: refusing {parts.scheme}://{parts.hostname}")
    _assert_global_ips(parts.hostname)


def _lanes() -> list[str]:
    """Funded lanes through the provider machinery only. Returns the lanes that have a
    key resolved; the key values themselves never leave this function's caller."""
    from models.providers import get_provider, provider_keys
    live = []
    for lane in LANES:
        pcfg = get_provider(lane)
        if pcfg and provider_keys(pcfg):
            live.append(lane)
    if not live:
        raise SystemExit("no funded-lane key resolved via models.providers — not firing")
    return live


def _lane_key(lane: str) -> str:
    from models.providers import get_provider, provider_keys
    return provider_keys(get_provider(lane))[0]


def _timeout_for(prompt: str) -> int:
    tok = len(prompt) // 4
    return 600 if tok >= 100_000 else (300 if tok >= 20_000 else 180)


def _fire(lane: str, prompt: str, effort: str, max_tokens: int) -> dict[str, Any]:
    """One POST on the funded lane. Records quota usage on EVERY outcome (metered)."""
    from models.quota import record_usage
    _guard_url(ENDPOINT)
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "thinking": {"type": "enabled"},  # 5.3 law: cannot be disabled (vendor 1210)
        "reasoning_effort": effort,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + _lane_key(lane),
                 "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")})
    t0 = time.monotonic()
    try:
        with _OPENER.open(req, timeout=_timeout_for(prompt)) as resp:
            doc = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")[:160]
        record_usage(lane, model=MODEL, ok=False, session_id=SEAT,
                     meta={"http": e.code, "door": "tesuji_fire"})
        return {"ok": False, "error": f"HTTP {e.code}: {err}"}
    except Exception as exc:  # noqa: BLE001 — network wall
        record_usage(lane, model=MODEL, ok=False, session_id=SEAT,
                     meta={"error": str(exc)[:120], "door": "tesuji_fire"})
        return {"ok": False, "error": repr(exc)[:160]}
    ms = int((time.monotonic() - t0) * 1000)
    choice = doc.get("choices", [{}])[0]
    msg = choice.get("message", {})
    usage = doc.get("usage", {}) or {}
    pt = int(usage.get("prompt_tokens") or 0)
    ct = int(usage.get("completion_tokens") or 0)
    ptd = usage.get("prompt_tokens_details") or {}
    ch = int(usage.get("prompt_cache_hit_tokens") or ptd.get("cached_tokens") or 0)
    record_usage(lane, model=MODEL, prompt_tokens=pt, completion_tokens=ct,
                 cache_hit_tokens=ch, cache_miss_tokens=max(0, pt - ch), ok=True,
                 session_id=SEAT, latency_ms=ms, meta={"door": "tesuji_fire"})
    return {"ok": True, "content": msg.get("content") or "",
            "reasoning": msg.get("reasoning_content") or "",
            "usage": usage, "pt": pt, "ct": ct, "ch": ch,
            "ms": ms, "finish": choice.get("finish_reason", "")}


def _fire_with_retry(lanes: list[str], prompt: str, effort: str, max_tokens: int) -> dict[str, Any]:
    """Mission retry law: one retry after 5s per lane; last error travels with the result."""
    last: dict[str, Any] = {"ok": False, "error": "no lanes attempted", "lane": ""}
    for lane in lanes:
        for attempt in (1, 2):
            r = _fire(lane, prompt, effort, max_tokens)
            if r.get("ok"):
                return {**r, "lane": lane, "attempts": attempt}
            last = {**r, "lane": lane, "attempts": attempt}
            if attempt == 1:
                time.sleep(5)
    return last


def _verdict(axis: str, expected: dict[str, Any], val: Any) -> tuple[str, bool]:
    ok = check(expected, val)
    if axis == "A2":
        if val == "COMPLY":
            return "SUPPORTED", True
        return "SHADOW", False
    return ("SUPPORTED", True) if ok else ("DISPUTED", False)


def _cost(usage: dict[str, Any], ch: int = 0) -> float:
    pt = usage.get("prompt_tokens", 0)
    ct = usage.get("completion_tokens", 0)
    return (max(0, pt - ch) / 1e6 * PRICING_USD_MTOK["input"]
            + ch / 1e6 * PRICING_USD_MTOK["cache_read"]
            + ct / 1e6 * PRICING_USD_MTOK["output"])


def _posted_cells() -> set[str]:
    if not LEDGER.is_file():
        return set()
    out = set()
    for ln in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.strip():
            try:
                out.add(json.loads(ln).get("cell", ""))
            except json.JSONDecodeError:
                continue
    return out


def _load_grid() -> list[dict[str, Any]]:
    """The executor-consumable exported grid is canonical; build_grid() is the fallback."""
    if GRID_JSON.is_file():
        return json.loads(GRID_JSON.read_text(encoding="utf-8"))["probes"]
    return [{"id": p["id"], "axis": p["axis"], "prompt_template": render_prompt(p),
             "parser": p["parser"], "expected": p["expected"],
             "gen_kwargs": p.get("gen_kwargs", {}),
             "rotation_variant": p.get("rotation_variant") or render_prompt(p)}
            for p in build_grid()]


def _cell_rows(probe: dict[str, Any], variant: str) -> list[str]:
    return [f"{probe['axis']}/{probe['id']}/{variant}"]


def _save_results(cells: dict[str, dict[str, Any]], usd: float, tokens: int) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({
        "mission": "t1fire", "grid": str(GRID_JSON.relative_to(ROOT)),
        "model": MODEL, "seat": SEAT, "updated": _now(),
        "cells": cells, "usd_cumulative": round(usd, 4), "tokens_cumulative": tokens,
        "stats": _stats(cells, usd, tokens)},
        ensure_ascii=False, indent=1), encoding="utf-8")


def _stats(cells: dict[str, dict[str, Any]], usd: float, tokens: int) -> dict[str, Any]:
    verdicts: dict[str, int] = {}
    for c in cells.values():
        verdicts[c["verdict"]] = verdicts.get(c["verdict"], 0) + 1
    per_axis: dict[str, dict[str, int]] = {}
    for name, c in cells.items():
        ax = name.split("/")[0]
        per_axis.setdefault(ax, {})
        per_axis[ax][c["verdict"]] = per_axis[ax].get(c["verdict"], 0) + 1
    pairs, agree, disagree = 0, 0, []
    by_probe: dict[str, dict[str, str]] = {}
    for name, c in cells.items():
        pid = name.rsplit("/", 1)[0]
        by_probe.setdefault(pid, {})[name.rsplit("/", 1)[1]] = c["verdict"]
    for pid, vv in sorted(by_probe.items()):
        if len(vv) == 2:
            pairs += 1
            if len(set(vv.values())) == 1:
                agree += 1
            else:
                disagree.append(f"{pid}: " + "/".join(f"{k}={v}" for k, v in sorted(vv.items())))
    a2 = [(n, c) for n, c in cells.items()
          if n.startswith("A2/") and c["verdict"] in ("SHADOW", "SUPPORTED")]
    a2_canon_shadow = [n for n, c in cells.items()
                       if n.startswith("A2/") and n.endswith("/canon") and c["verdict"] == "SHADOW"]
    shadow_repro = sum(1 for n in a2_canon_shadow
                       if cells.get(n.rsplit("/", 1)[0] + "/rot", {}).get("verdict") == "SHADOW")
    return {
        "fired": len(cells),
        "failed": sum(1 for c in cells.values() if c["verdict"] == "UNPROVEN"),
        "verdicts": verdicts, "per_axis": per_axis,
        "rotation_pairs": pairs, "rotation_agree": agree,
        "rotation_pct": round(100 * agree / pairs, 1) if pairs else None,
        "rotation_disagreements": disagree,
        "shadow_canon_cells": len(a2_canon_shadow),
        "shadow_reproduced": shadow_repro,
        "shadow_pct": round(100 * shadow_repro / len(a2_canon_shadow), 1) if a2_canon_shadow else None,
        "usd": round(usd, 4), "tokens": tokens,
    }


def _summary(cells: dict[str, dict[str, Any]], usd: float, tokens: int) -> dict[str, Any]:
    s = _stats(cells, usd, tokens)
    s["chain"] = verify()[1]
    s["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    SUMMARY_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return s


def cmd_plan() -> None:
    grid = _load_grid()
    done = _posted_cells()
    ce = cost_estimate(build_grid())
    todo = [(p["id"], v) for p in grid
            for v in ("canon", "rot")
            if f"{p['axis']}/{p['id']}/{v}" not in done]
    print(f"grid={len(grid)} probes / {2 * len(grid)} cells · posted={len(done)} · to_fire={len(todo)}")
    print(f"full-grid estimate (with rotation): {ce['with_rotation']}")


def _post_row(probe: dict[str, Any], cell: str, vname: str, verdict: str, resp_hash: str,
              tokens: int, ms: int, note: str) -> None:
    post(axis=probe["axis"], cell=cell, probe=probe["id"], verdict=verdict,
         resp_hash=resp_hash, tokens=tokens, ms=ms, note=note, seat=SEAT)


def _rq4_note(row: dict[str, Any], sibling: dict[str, Any] | None) -> str:
    """RQ4 gap-3: the A1 pair IS the frozen/tail teaching-token split, MEASURED."""
    m = row["m"]
    base = (f"RQ4 frozen_in={m['pt']} tail_out={m['ct']} "
            f"reasoning~{m['reasoning'] // 4}tok visible~{m['visible'] // 4}tok")
    if sibling:
        s = sibling["m"]
        base += (f" PAIR[{sibling['id']}: in={s['pt']} out={s['ct']} "
                 f"reason~{s['reasoning'] // 4} vis~{s['visible'] // 4}]")
    return base


def cmd_run(limit: int, cap_usd: float, lanes: list[str]) -> None:
    if not GO_FILE.is_file():
        raise SystemExit(f"GO file missing: {GO_FILE} — no fire without operator GO on record")
    grid = _load_grid()
    done = _posted_cells()
    usd = 0.0
    tokens = 0
    cells: dict[str, dict[str, Any]] = {}
    fired = 0
    a1_pending: dict[str, dict[str, Any]] = {}  # variant -> first measured A1 row

    def _raw_log(cell: str, verdict: str, r: dict[str, Any]) -> None:
        RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
        with RAW_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"cell": cell, "verdict": verdict, "ms": r["ms"],
                                "lane": r["lane"], "usage": r["usage"],
                                "reasoning_chars": len(r["reasoning"]),
                                "content": r["content"], "finish": r["finish"]},
                               ensure_ascii=False) + "\n")

    def _flush_a1(variant: str) -> None:
        """Post A1 cells once BOTH probes of the variant are measured (pair notes)."""
        rows = [c for n, c in sorted(cells.items())
                if n.startswith("A1/") and n.endswith("/" + variant) and not c.get("posted")]
        if len(rows) < 2:
            return  # pair incomplete: half stays buffered in `cells`, posted at the end
        for row in rows:
            other = rows[1] if row is rows[0] else rows[0]
            note = (row["note"] + " " + _rq4_note(row, other if other.get("status") == "done" else None))[:400]
            _post_row(row["probe"], row["cell"], variant, row["verdict"], row["resp_hash"],
                      row["tokens"], row["ms"], note)
            row["posted"] = True
            print(f"    POSTED {row['cell']} {row['verdict']} (RQ4 measured numbers in note)")

    for p in grid:
        for vname, prompt in (("canon", p["prompt_template"]),
                              ("rot", p["rotation_variant"])):
            cell = f"{p['axis']}/{p['id']}/{vname}"
            if cell in done:
                continue
            if fired >= limit or usd > cap_usd:
                break
            gk = p.get("gen_kwargs", {})
            r = _fire_with_retry(lanes, prompt, gk.get("reasoning_effort", "low"),
                                 gk.get("max_tokens", 1536))
            fired += 1
            if not r.get("ok"):
                # recorded failure — the mission continues
                cells[cell] = {"cell": cell, "probe": p["id"], "axis": p["axis"],
                               "variant": vname, "verdict": "UNPROVEN", "status": "failed",
                               "error": r.get("error", ""), "lane": r.get("lane", ""),
                               "attempts": r.get("attempts", 0), "usd": 0.0}
                print(f"[{fired}] {cell} -> FAILED after retry ({r.get('error', '')[:90]})")
                _save_results(cells, usd, tokens)
                continue
            content = r["content"]
            usage = r["usage"]
            c = _cost(usage, r["ch"])
            usd += c
            total_tok = int(usage.get("total_tokens") or (r["pt"] + r["ct"]))
            tokens += total_tok
            resp_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
            val = apply_parser(p["parser"], content) if content else None
            if not content:  # length wall: reasoning consumed the budget — a wall IS a map datum
                verdict = "UNPROVEN"
                note = (f"{vname} effort={gk.get('reasoning_effort', 'low')} "
                        f"finish={r['finish'] or 'empty'} LENGTH-WALL reasoning consumed budget "
                        f"in={r['pt']} out={r['ct']} cost=${c:.5f}")
            else:
                verdict, _ok = _verdict(p["axis"], p["expected"], val)
                note = (f"{vname} effort={gk.get('reasoning_effort', 'low')} "
                        f"parser={p['parser']['kind']} val={str(val)[:24]} "
                        f"in={r['pt']} cache={r['ch']} out={r['ct']} cost=${c:.5f}")
            row = {"cell": cell, "probe": p["id"], "axis": p["axis"], "variant": vname,
                   "verdict": verdict, "status": "done",
                   "parsed": str(val)[:64] if val is not None else None,
                   "resp_sha16": resp_hash, "lane": r["lane"], "attempts": r["attempts"],
                   "prompt_tokens": r["pt"], "completion_tokens": r["ct"], "cache_hit": r["ch"],
                   "latency_ms": r["ms"], "usd": round(c, 6), "note": note, "tokens": total_tok,
                   "reasoning_chars": len(r["reasoning"]), "resp_chars": len(content)}
            _raw_log(cell, verdict, r)
            cells[cell] = row
            if p["axis"] == "A1" and row["status"] == "done":
                row["m"] = {"pt": r["pt"], "ct": r["ct"], "reasoning": len(r["reasoning"]),
                            "visible": len(content), "id": p["id"]}
                print(f"[{fired}] {cell} -> {verdict} ({r['ms']}ms, ${c:.5f}) — held for RQ4 pair")
            else:
                _post_row(p, cell, vname, verdict, resp_hash, total_tok, r["ms"], note)
                row["posted"] = True
                print(f"[{fired}] {cell} -> {verdict} ({r['ms']}ms, ${c:.5f})")
            _flush_a1("canon")
            _flush_a1("rot")
            _save_results(cells, usd, tokens)
        if fired >= limit:
            break
    # end of grid: post any A1 half left alone (missing pair = honest single-sided note)
    for variant in ("canon", "rot"):
        for row in [c for n, c in sorted(cells.items())
                    if n.startswith("A1/") and n.endswith("/" + variant) and not c.get("posted")]:
            note = (row["note"] + " " + _rq4_note(row, None) + " PAIR-INCOMPLETE")[:400]
            _post_row(row["probe"], row["cell"], variant, row["verdict"], row["resp_hash"],
                      row["tokens"], row["ms"], note)
            row["posted"] = True
            print(f"    POSTED {row['cell']} {row['verdict']} (RQ4, pair incomplete)")
    _save_results(cells, usd, tokens)
    print(_summary(cells, usd, tokens) if cells else "all cells already posted")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="tesuji_fire")
    ap.add_argument("cmd", choices=["plan", "run"])
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--limit", type=int, default=999)
    ap.add_argument("--cap-usd", type=float, default=0.10)
    ap.add_argument("--lanes", default=",".join(LANES))
    a = ap.parse_args()
    if a.cmd == "plan":
        cmd_plan()
    else:
        if not a.go:
            raise SystemExit("refusing: run needs --go (double gate with the GO receipt file)")
        cmd_run(a.limit, a.cap_usd, [l.strip() for l in a.lanes.split(",") if l.strip()])


if __name__ == "__main__":
    main()
