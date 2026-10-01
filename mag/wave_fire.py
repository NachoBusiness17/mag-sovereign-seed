"""wave_fire — the house's standard wave runner: gate, fire, measure, break (2026-09-13).

This is the organ that makes probe-before-route and the lane breaker the DEFAULT
path, so no wave script ever re-fires a dead slug again (the 09-13 lesson: the fix
lived in a recipe note, not in the runner — runners are where fixes must live).

Pipeline per wave:
  1. GATE    — every candidate slug probed (mag.probe_route, TTL-cached); suspended
               slugs (mag.lane_breaker state) refused before spend.
  2. FIRE    — lanes through ThreadPool; preferred slug or live fallback; per-lane
               receipt {routed_slug, tokens, cached, seconds}.
  3. MEASURE — per-slug success ratio from receipts.
  4. BREAK   — ratio fed to mag.lane_breaker.check(); a slug that fails its lanes
               trips and is suspended for future waves until cleared.

Pack format: one markdown file; lane briefs split on "## TARGET <id> " (head = shared
material). Lanes JSON: [{"id":..,"target":..,"url":..,"key_env":..,"model":..}, ...]

Schema: wave_fire.v1
CLI:
  python -m mag.wave_fire run --pack pack.md --lanes lanes.json [--workers 12] --outdir returns/
Keys read from env, never printed. Hosts allowlisted in mag.probe_route.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import pathlib
import time
from datetime import datetime, timezone

from mag import probe_route, lane_breaker

SCHEMA = "wave_fire.v1"
ALLOWED = probe_route._assert_public_https  # single source of truth for host policy


def load_pack(path: str) -> str:
    return pathlib.Path(path).read_text(encoding="utf-8")


def brief(pack: str, target: str) -> str:
    try:
        sec = pack.split("## TARGET " + target + " ")[1]
        body = sec.split("\n## TARGET ")[0]
    except IndexError:
        return pack
    return pack.split("## TARGET ")[0] + "## TARGET " + target + " " + body


def fire_lane(lane: dict, pack: str, live: set, outdir: pathlib.Path) -> dict:
    lane_id, slug = lane["id"], lane["model"]
    routed = slug if slug in live else next((s for s in probe_route.FALLBACK_CHAIN if s in live), None)
    rec = {"schema": SCHEMA, "lane": lane_id, "requested_slug": slug, "routed_slug": routed, "ts": datetime.now(timezone.utc).isoformat()}
    if not routed:
        rec["status"] = "skip-no-live-slug"
        return rec
    key = os.environ.get(lane["key_env"], "")
    if not key:
        rec["status"] = "skip-no-key"
        return rec
    payload = {"model": routed, "messages": [{"role": "user", "content": brief(pack, lane["target"])}],
               "max_tokens": lane.get("max_tokens", 8192), "temperature": lane.get("temperature", 0.4)}
    payload.update(lane.get("extra", {}))  # per-lane body params (e.g. reasoning_effort)
    t0 = time.time()
    rec.update({"max_tokens": payload["max_tokens"]})
    try:
        import urllib.request
        probe_route._assert_public_https(lane["url"])
        req = urllib.request.Request(lane["url"], data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                                     method="POST")
        with probe_route._OPENER.open(req, timeout=300) as r:
            resp = json.loads(r.read().decode("utf-8"))
        text = resp["choices"][0]["message"]["content"] or ""
        usage = resp.get("usage", {})
        rec.update({"status": "ok", "completion_tokens": usage.get("completion_tokens"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "cached": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                    "seconds": round(time.time() - t0, 1)})
        (outdir / f"{lane_id}.md").write_text(text, encoding="utf-8")
    except Exception as e:
        rec.update({"status": "fail", "error": f"{type(e).__name__}: {str(e)[:140]}"})
    (outdir / f"{lane_id}.receipt.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def run(pack_path: str, lanes_path: str, outdir: str, workers: int = 12) -> int:
    pack = load_pack(pack_path)
    lanes = json.loads(pathlib.Path(lanes_path).read_text(encoding="utf-8"))
    out = pathlib.Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # 1. GATE — probe every distinct slug, refuse suspended ones
    key_env = lanes[0]["key_env"]
    url = lanes[0]["url"]
    key = os.environ.get(key_env, "")
    slugs = sorted({l["model"] for l in lanes} | set(probe_route.FALLBACK_CHAIN))
    rows = [probe_route.probe_one(s, url, key) for s in slugs]
    live = {r["slug"] for r in rows if r["verdict"] in {"live", "flaky"}}
    breaker_state = lane_breaker._load().get("suspended", {})
    suspended = {f"wave:{s}" for s in list(live) if f"wave:{s}" in breaker_state}
    live -= suspended
    gate = {"slugs_probed": len(rows), "live": sorted(live), "suspended_refused": sorted(suspended),
            "excluded": [{"slug": r["slug"], "verdict": r["verdict"]} for r in rows if r["verdict"] == "dead"]}
    (out / "GATE.json").write_text(json.dumps(gate, indent=2), encoding="utf-8")
    print(f"GATE: {len(live)} live, {len(gate['excluded'])} dead, {len(suspended)} suspended-refused", flush=True)

    # 2. FIRE
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        receipts = list(pool.map(lambda l: fire_lane(l, pack, live, out), lanes))
    for r in receipts:
        print(f"{r['lane']} [{r.get('routed_slug')}]: {r['status']} {r.get('completion_tokens','')}tok", flush=True)

    # 3+4. MEASURE + BREAK — per-slug success ratio into the breaker (only on >=2-lane
    # samples; a perfect wave auto-clears its suspension so one bad wave can't brick the pool)
    by_slug = {}
    for r in receipts:
        by_slug.setdefault(r.get("routed_slug"), []).append(1 if r["status"] == "ok" else 0)
    verdicts = {}
    for slug, oks in by_slug.items():
        ratio = sum(oks) / len(oks)
        if ratio == 1.0:
            lane_breaker.clear(f"wave:{slug}", note="perfect wave — auto-clear")
            verdicts[slug] = {"ratio": ratio, "action": "clear"}
        elif len(oks) >= 2:
            verdicts[slug] = lane_breaker.check(ratio, f"wave:{slug}", note=f"{len(oks)} lanes")
        else:
            verdicts[slug] = {"ratio": ratio, "action": "unsampled(<2), not tripped"}
    (out / "WAVE.json").write_text(json.dumps({"schema": SCHEMA, "gate": gate, "receipts": receipts,
                                               "breaker": verdicts, "wall_s": round(time.time() - t0, 1)},
                                              indent=2), encoding="utf-8")
    tripped = [s for s, v in verdicts.items() if v.get("tripped")]
    print(f"WAVE DONE {time.time()-t0:.1f}s — breaker tripped: {tripped or 'none'}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="wave_fire")
    ap.add_argument("action", choices=["run"])
    ap.add_argument("--pack", required=True)
    ap.add_argument("--lanes", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    return run(a.pack, a.lanes, a.outdir, a.workers)


if __name__ == "__main__":
    raise SystemExit(main())
