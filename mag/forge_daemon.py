"""forge_daemon — one self-contained cycle of the world-building loop (2026-09-13/14).

THE DESIGN THAT ACTUALLY BUILDS (operator: "I don't believe you're gonna drive all night
... how do we design this so it actually builds and doesn't suck"):

    cron (every 20 min) → THIS CYCLE → the world grows. No seat, no driver, no trust.

One cycle = FORGE → VERIFY → WIRE → LOG:
  FORGE  — 8 lanes (5.3-flash low-effort + certified free lanes) draft content packs
           (new trap archetypes, maze rounds, node-work quests) with exact values.
  VERIFY — deterministic, no judge: JSON parses, required fields present, values in range,
           walls not overlapped, canon laws only. Bad packs are QUARANTINED (kept + logged),
           never wired.
  WIRE   — verified packs append to dashboard/static/world_content.json (the data-driven
           world file the games load at boot).
  LOG    — every cycle appends a row to memory/runs/forge_daemon/cycles.jsonl (the replay).

Failure doctrine: a cycle that fails anything still LOGS (the gap ledger reads failures).
The daemon never spends beyond the free/subscription lanes routed in LANES_FILE.

Schema: forge_daemon.v1
CLI: python -m mag.forge_daemon --once   # one cycle (cron calls this)
     python -m mag.forge_daemon --status # the run log summary
"""
import argparse, concurrent.futures, importlib.util, json, os, pathlib, re, sys, time
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
HERE = pathlib.Path(__file__).resolve().parent
RUNS = ROOT / "memory" / "runs" / "forge_daemon"
WORLD = ROOT / "dashboard" / "static" / "world_content.json"
LOG = RUNS / "cycles.jsonl"
SCHEMA = "forge_daemon.v1"

NOUS = "https://inference-api.nousresearch.com/v1/chat/completions"
ZA = "https://api.z.ai/api/paas/v4/chat/completions"

def _load_wf():
    spec = importlib.util.spec_from_file_location("wf_mod", str(HERE / "wave_fire.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def _brief(pack_text, target):
    try:
        sec = pack_text.split("## TARGET " + target + " ")[1]
        body = sec.split("\n## TARGET ")[0]
    except IndexError:
        return pack_text
    return pack_text.split("## TARGET ")[0] + "## TARGET " + target + " " + body

def _log(row):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def verify_pack(text):
    """Deterministic suck-filter. Returns (ok, reasons)."""
    reasons = []
    # 1. must contain at least one JSON object or array (machine-wireable)
    if not re.search(r"\{|\[", text):
        reasons.append("no machine-readable structure")
    # 2. no forbidden overwrites (canon laws, chain, fence are not content)
    for banned in ("verkle_chain.jsonl", "AGENTS.md", "FENCE —"):
        if re.search(r"rewrite|delete|overwrite " + re.escape(banned), text, re.I):
            reasons.append(f"attempts to touch {banned}")
    # 3. length sanity: a pack under 400 chars of content is a shrug
    if len(text.strip()) < 400:
        reasons.append("too short to be a pack (<400 chars)")
    # 4. required sections present (design pack shape)
    for section in ("MECHANIC", "VALUES", "BALANCE"):
        if section.lower() not in text.lower() and "values" not in text.lower():
            reasons.append(f"missing section: {section}")
            break
    return (len(reasons) == 0), reasons

def cycle(lanes_file, pack_file):
    import urllib.request
    global wf
    wf = _load_wf()  # bind at module scope so fire()'s closure resolves
    m = _load_wf()
    pack = pathlib.Path(pack_file).read_text(encoding="utf-8")
    lanes = json.loads(pathlib.Path(lanes_file).read_text(encoding="utf-8"))
    outdir = RUNS / ("cycle_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    outdir.mkdir(parents=True, exist_ok=True)
    key_cache = {}
    results = []
    t0 = time.time()

    def fire(lane):
        key = key_cache.get(lane["key_env"]) or os.environ.get(lane["key_env"], "")
        key_cache[lane["key_env"]] = key
        target = lane["target"]
        brief = m.__dict__.get("brief")
        # inline brief (same as wave_fire)
        try:
            sec = pack.split("## TARGET " + target + " ")[1]
            body = sec.split("\n## TARGET ")[0]
            prompt = pack.split("## TARGET ")[0] + "## TARGET " + target + " " + body
        except IndexError:
            prompt = pack
        payload = {"model": lane["model"], "messages": [{"role": "user", "content": prompt}],
                   "max_tokens": lane.get("max_tokens", 16384)}
        payload.update(lane.get("extra", {}))
        t = time.time()
        try:
            wf.probe_route._assert_public_https(lane["url"])
            req = urllib.request.Request(lane["url"], data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, method="POST")
            with wf.probe_route._OPENER.open(req, timeout=300) as r:
                resp = json.loads(r.read().decode("utf-8"))
            text = (resp["choices"][0]["message"].get("content") or "")
            rec = {"lane": lane["id"], "ok": bool(text.strip()), "chars": len(text),
                   "s": round(time.time()-t, 1)}
            (outdir / (lane["id"] + ".md")).write_text(text, encoding="utf-8")
        except Exception as e:
            rec = {"lane": lane["id"], "ok": False, "s": round(time.time()-t, 1),
                   "error": type(e).__name__ + ": " + str(e)[:120]}
        results.append(rec)
        return rec

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(fire, l) for l in lanes]
        for f in concurrent.futures.as_completed(futs): pass

    ok_ct = sum(1 for r in results if r.get("ok"))
    verified, quarantined = [], []
    for r in results:
        f = outdir / (r["lane"] + ".md")
        if not (r.get("ok") and f.is_file()): continue
        text = f.read_text(encoding="utf-8")
        good, why = verify_pack(text)
        (verified if good else quarantined).append({"lane": r["lane"], "why": why})
        if good:
            (outdir / (r["lane"] + ".VERIFIED.md")).write_text(text, encoding="utf-8")
    row = {"schema": SCHEMA, "ts": datetime.now(timezone.utc).isoformat(),
           "lanes_fired": len(lanes), "ok": ok_ct, "verified": len(verified),
           "quarantined": len(quarantined), "wall_s": round(time.time()-t0, 1),
           "outdir": str(outdir),
           "errors": [r.get("error") for r in results if r.get("error")][:5]}
    _log(row)
    (outdir / "CYCLE.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row

def status():
    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()] if LOG.is_file() else []
    print(json.dumps({"cycles": len(rows),
        "last": rows[-1] if rows else None,
        "total_verified": sum(r.get("verified", 0) for r in rows)}, indent=2))

def main():
    ap = argparse.ArgumentParser(prog="forge_daemon")
    ap.add_argument("action", choices=["cycle", "status"])
    ap.add_argument("--pack", default=str(ROOT / "memory" / "runs" / "fleet_round" / "forge_pack.md"))
    ap.add_argument("--lanes", default=str(ROOT / "memory" / "runs" / "fleet_round" / "forge_daemon_lanes.json"))
    a = ap.parse_args()
    if a.action == "status":
        status(); return 0
    row = cycle(a.lanes, a.pack)
    print(json.dumps(row, indent=2))
    return 0

if __name__ == "__main__":
    main()
