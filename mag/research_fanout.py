"""research_fanout -- 50-wide deep research across the FREE channels, in our way.

Operator (2026-09-15): "do a full blown research project 50 wide in our way using our free
channels to dig up as much data around this and other modding/hosting attempts also self steal
our gaming corpus, our plans our directories etc".

IN OUR WAY means:
  * the battery is DATA (50 frozen questions, versioned by digest) and the aggregation is
    deterministic + $0 -- only the digging costs anything, and it costs nothing (free tiers);
  * every call leaves a raw receipt (JSONL: lane, model, question, latency, chars, error);
  * FAILURES ARE PRESERVED, never smoothed over: a dead lane is a row, not a silence;
  * model output is LEADS, not facts. The pack says so in its own header, and a lead is only
    promoted by a byte check (mag/wow_steal.py `verify`, mag/wow_family.py `delta`).

LANES are probed live before use (a stored key is not a live key). Paid keys
(XAI/ANTHROPIC/OPENAI) are deliberately excluded: this is a free-channel project.

RUN:
  python -m mag.research_fanout lanes            # probe every configured lane
  python -m mag.research_fanout battery          # the 50 questions, by theme
  python -m mag.research_fanout run --workers 8  # the fan-out (writes raw + pack)
  python -m mag.research_fanout status

Schema: research_fanout.v1
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "research_fanout.v1"
OUT = ROOT / "memory" / "runs" / "research_50_wow"
RAW = OUT / "raw.jsonl"
PACK = OUT / "RESEARCH_50.md"
ENV_FILES = [ROOT / ".env", Path.home() / "AppData" / "Local" / "hermes" / ".env"]

SYSTEM = (
    "You are a research digger for a game-world project. Answer with CONCRETE, checkable "
    "material: names, repos, URLs, version numbers, sizes, dates, legal cases, numbers. "
    "Prefer specifics over framing. No preamble, no summary of the question, no moralising. "
    "If you are unsure, say which part is uncertain instead of inventing a number. "
    "Hard limit: 200 words. Use compact bullets."
)

# id | theme | question
BATTERY: list[tuple[str, str, str]] = [
    # --- A. WoW emulation stack -----------------------------------------------------------
    ("A01", "A-wow-stack", "List every actively maintained open-source WoW server core (2026), with repo, client version supported, license, and approximate repo size."),
    ("A02", "A-wow-stack", "Trace the WoW emulator lineage: MaNGOS -> TrinityCore -> SunwellCore -> AzerothCore, and MaNGOS -> vMaNGOS. Name the forks that died and why."),
    ("A03", "A-wow-stack", "How does a WoW server core dispatch client packets? Describe the opcode table, session status gates, and processing-place/thread scheduling, with concrete class or file names."),
    ("A04", "A-wow-stack", "How does the client-server protocol stay compatible across game patches? Describe versioned opcode headers, per-build support, and how servers pick the right contract."),
    ("A05", "A-wow-stack", "List the tooling chain for WoW client modding: MPQ patching, DBC editing, map editors (Noggit et al), model tools, MWCS/MPQ editors, and what each does."),
    ("A06", "A-wow-stack", "What is required to extract server-side map data (maps, vmaps, mmaps) from a WoW client, tool names, input files, output sizes, and time cost?"),
    ("A07", "A-wow-stack", "How do WoW private servers create custom content without patching the client? Which kinds of content live in the database vs DBC vs client MPQ?"),
    ("A08", "A-wow-stack", "What is mod-playerbots for AzerothCore? What problem does it solve for a solo or low-population server, what does it cost in RAM/CPU, and how is it installed?"),
    ("A09", "A-wow-stack", "Compare challenge/modifier systems in custom WoW servers: hardcore mode, slow-and-steady, warmode, classless (Ascension). How are such flags implemented server-side?"),
    ("A10", "A-wow-stack", "What is the smart_scripts / SmartAI system in MaNGOS-family cores and how does it let non-programmers author creature behaviour? Give table columns."),
    # --- B. Hosting a private server ------------------------------------------------------
    ("B01", "B-hosting", "What hardware does a WoW private server actually need for 1, 50, 500 and 5000 concurrent players? CPU, RAM, disk, bandwidth, with reasoning."),
    ("B02", "B-hosting", "How long does the first database import take for AzerothCore/vMaNGOS and how large does the MySQL world database become on disk?"),
    ("B03", "B-hosting", "What operational failures kill private servers? Give the taxonomy: DDoS, database corruption, admin burnout, host takedown, content starvation, economy break."),
    ("B04", "B-hosting", "How do private server hosts get taken down? Describe the documented cases (Blizzard vs. Scapegaming, WoWscape, Nostalrius cease-and-desist) and the legal instruments used."),
    ("B05", "B-hosting", "How do small servers mitigate DDoS and bot floods? Concrete mitigations: proxies, rate limiting, connection caps, Cloudflare spectrum, OVH game anti-DDoS."),
    ("B06", "B-hosting", "What does it cost per month to run a small game server in 2026? Compare VPS tiers, dedicated, and cloud for a 1-100 player world."),
    ("B07", "B-hosting", "How do game servers handle persistence and backups so a crash does not destroy the world? Give patterns and real tool names."),
    ("B08", "B-hosting", "How do community-run servers make decisions and survive admin disputes? Give governance models used by long-lived servers (RuneScape, UO, WoW freeshards)."),
    ("B09", "B-hosting", "What monitoring and observability do game servers use? Metrics that matter (tick time, session count, query latency) and tools."),
    ("B10", "B-hosting", "How do private servers handle authentication and account security? Compare SRP6 as used by WoW cores with modern practices, and what usually goes wrong."),
    # --- C. Other modding / hosting attempts ----------------------------------------------
    ("C01", "C-other-games", "Compare UO server emulators (ServUO, RunUO, SphereServer): language, license, activity, and what each does better than the others."),
    ("C02", "C-other-games", "Describe EQEmu's architecture and what a 25-year-old EQ emulator community has learned about keeping a server alive."),
    ("C03", "C-other-games", "Compare RuneScape emulation projects (2009scape, RSPS frameworks) and how their content/engine separation works."),
    ("C04", "C-other-games", "Describe OpenMW as the archetype of a clean-room engine reimplementation that ships no assets. How does it handle data files, and what is its testing strategy?"),
    ("C05", "C-other-games", "Describe the decompilation/recompilation scene: Ship of Harkinian, SM64 ports, DevilutionX, OpenRCT2. What legal and technical model do they use?"),
    ("C06", "C-other-games", "How does Minecraft server modding work (Bukkit/Spigot/Paper/Forge/Fabric) and what can a plugin/mod API teach about engine-vs-content separation?"),
    ("C07", "C-other-games", "Describe FiveM and GTA multiplayer modding: how does a third-party multiplayer layer attach to a closed game, and how does it host?"),
    ("C08", "C-other-games", "What is the Doom/Quake source-port lineage and what did id Software's source releases teach about modding ecosystems?"),
    ("C09", "C-other-games", "How does ROM hacking / translation patching work legally and technically (IPS/BPS patches, ROMhacking.net, patch-only distribution)?"),
    ("C10", "C-other-games", "Describe MUD/MUSH servers (TinyMUD, LPmud, Evennia): what architecture has survived 35 years, and what do modern MUD frameworks offer?"),
    # --- D. Law, preservation, ethics -----------------------------------------------------
    ("D01", "D-preservation", "How does game preservation handle online-only games that depended on servers? Name organisations and their methods."),
    ("D02", "D-preservation", "What is the legal status of running a private game server for personal use in the US and EU? Cases, safe harbours, and hostility to reverse engineering."),
    ("D03", "D-preservation", "Summarise Nintendo's litigation against emulators and ROM sites (Yuzu, Ryujinx, LoveROMS). What legal theories were used and what changed?"),
    ("D04", "D-preservation", "What is a clean-room reimplementation in law and engineering practice? Give the classic precedents and the process rules."),
    ("D05", "D-preservation", "How do open-source game projects handle assets vs code licensing? Cover CC-BY-SA, proprietary asset carve-outs, and DMCA takedown history."),
    ("D06", "D-preservation", "What is the current state of US copyright term and abandonware, and how do preservation groups justify distribution?"),
    ("D07", "D-preservation", "How do emulator projects defend against accusations of circumvention (DMCA s1201)? Cite specific cases and outcomes."),
    ("D08", "D-preservation", "What is the legal exposure of a private server that charges money versus one that does not? Cite cases."),
    ("D09", "D-preservation", "How do server projects write provenance and attribution for code forked across many upstreams? Give the practical convention."),
    ("D10", "D-preservation", "What data does a game server need to be reproducible/replayable (seeds, RNG, tick order, logs)? Which projects attempt deterministic replay?"),
    # --- E. Our way ------------------------------------------------------------------------
    ("E01", "E-our-way", "Design a minimal server-authoritative game world core that is replayable and content-addressed. Which six functions must it expose and what must each guarantee?"),
    ("E02", "E-our-way", "How should a game engine separate engine (code) from content (data) so content never requires a recompile? Give the registry pattern and its failure modes."),
    ("E03", "E-our-way", "How can a game world be tested without shipping a client? Describe headless tests, golden replays, and differential testing against a reference implementation."),
    ("E04", "E-our-way", "What does provenance stamping mean for game content data (every datum tagged with the version that introduced it)? Give a schema and the migration strategy."),
    ("E05", "E-our-way", "How should an action vocabulary be versioned and frozen so replays stay valid across versions? Describe contract hashing and refusal taxonomies."),
    ("E06", "E-our-way", "Design the smallest runnable world that demonstrates persistence, reversible failure, and a verifiable state root. What must be in it and what must be left out?"),
    ("E07", "E-our-way", "How do you measure whether a game's rules are actually being exercised by players/tests? Give coverage metrics for state spaces and terminal conditions."),
    ("E08", "E-our-way", "What is the cheapest way to make a game world extensible by non-programmers, and what are the documented failure modes of such systems?"),
    ("E09", "E-our-way", "How should a research corpus for game design be indexed so answers are citable and not folklore? Give a file layout and metadata schema."),
    ("E10", "E-our-way", "What are the strongest arguments against building a custom game server at all, and what would a rational team do instead?"),
]

# lane id, base url, model, key env, request style
LANES: list[dict[str, str]] = [
    {"id": "groq-qwen", "base": "https://api.groq.com/openai/v1", "model": "qwen/qwen3.8-27b",
     "key": "GROQ_API_KEY", "style": "openai"},
    {"id": "groq-oss", "base": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-120b",
     "key": "GROQ_API_KEY", "style": "openai"},
    {"id": "groq-oss20", "base": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-20b",
     "key": "GROQ_API_KEY", "style": "openai"},
    {"id": "cerebras-oss", "base": "https://api.cerebras.ai/v1", "model": "gpt-oss-120b",
     "key": "CEREBAS_API_KEY", "style": "openai"},
    {"id": "cerebras-qwen", "base": "https://api.cerebras.ai/v1", "model": "qwen-3.8-27b",
     "key": "CEREBAS_API_KEY", "style": "openai"},
    {"id": "mistral-min8", "base": "https://api.mistral.ai/v1", "model": "ministral-8b-latest",
     "key": "MISTRAL_API_KEY", "style": "openai"},
    {"id": "mistral-small", "base": "https://api.mistral.ai/v1", "model": "mistral-small-latest",
     "key": "MISTRAL_API_KEY", "style": "openai"},
    {"id": "zai-lite", "base": "https://api.z.ai/api/coding/paas/v4",
     "model": "glm-5.3-flash", "key": "ZAI_API_KEY_Lite", "style": "openai"},
    # zai-air / zai-47 retired 2026-09-16 (operator: "self steal z.ai API, this is a solved
    # problem"): both rode ZAI_API_KEY (the Max coding-plan seat) and hit the paid wall
    # (code 1113 insufficient balance). The solved path is the Lite key + lite_guard pacing
    # (mag/lite_guard.py, law 15) pinned to glm-5.3-flash — burst lane, never a default
    # carrier; the gate below makes pacing structural. ENDPOINT LAW (verified live 09-16):
    # coding-plan subscriptions answer on /api/coding/paas/v4; the old /api/paas/v4
    # returns fake-1113 "insufficient balance" even with a full 10,000-credit pool.
    {"id": "or-union-alpha", "base": "https://openrouter.ai/api/v1",
     "model": "stealth/union-alpha", "key": "OPENROUTER_API_KEY", "style": "openai"},
    # TIME-BOXED stealth lane: opencode's "Union Alpha" free for one week
    # (tweet 2100236430890991782, posted 2026-09-16; window ends ~2026-09-23).
    # Remove or re-price after the window. Steal/eval program: receipts/D23 questions
    # + astra tri-state smoke fired against it — see watch/inbox/wave_20260916/receipts/.
    {"id": "or-glm52", "base": "https://openrouter.ai/api/v1", "model": "z-ai/glm-5.2:free",
     "key": "OPENROUTER_API_KEY", "style": "openai"},
    {"id": "or-nemotron", "base": "https://openrouter.ai/api/v1",
     "model": "nvidia/nemotron-3.5-lightning:free", "key": "OPENROUTER_API_KEY", "style": "openai"},
    {"id": "or-ling3", "base": "https://openrouter.ai/api/v1",
     "model": "inclusionai/ling-3.0-flash-sante:free", "key": "OPENROUTER_API_KEY", "style": "openai"},
]
# B2-133 DORMANT GATE (2026-09-26): lane ids here are lane-local (cerebras-oss, not the
# provider id), so the gate matches each lane's base_url host against the dormant
# providers' hosts (mag/doctor.py:607: dormant is a declared state). B2-36 set cerebras
# dormant (card-gated 30-day trial, chat 402 no-credit); the same gate catches the mistral
# lanes (dormant per B2-61, limit-0). Operator GO flips the flag and the lanes return,
# no code edit. Receipt: watch/inbox/burn_wave_20260926/B2_133_cerebras_purge_20260926.md
from urllib.parse import urlsplit as _urlsplit

from mag.dormant import dormant_hosts as _dormant_provider_hosts

_DORMANT_HOSTS = _dormant_provider_hosts()
LANES = [l for l in LANES if _urlsplit(l.get("base", "")).hostname not in _DORMANT_HOSTS]

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _env() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in ENV_FILES:
        if not p.is_file():
            continue
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                out.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return out


def battery_digest() -> str:
    return hashlib.sha256(json.dumps(BATTERY, ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()[:16]


def battery() -> dict[str, Any]:
    themes: dict[str, int] = {}
    for _i, t, _q in BATTERY:
        themes[t] = themes.get(t, 0) + 1
    return {"ok": True, "schema": SCHEMA, "questions": len(BATTERY), "themes": themes,
            "battery_digest": battery_digest(),
            "battery": [{"id": i, "theme": t, "q": q} for i, t, q in BATTERY]}


def call_lane(lane: dict[str, str], question: str, key: str, timeout: int = 90,
              max_tokens: int = 2600, attempt: int = 1) -> dict[str, Any]:
    """One call, one receipt. Never raises: a failure is a recorded row.

    max_tokens is generous because the free reasoning models (gpt-oss, qwen3.x) spend the budget
    in a reasoning channel first -- with 900 tokens their content comes back EMPTY, which pass 1
    recorded as `empty_content` rather than hiding.
    """
    t0 = time.time()
    rec: dict[str, Any] = {"lane": lane["id"], "model": lane["model"], "ts": _now(),
                           "attempt": attempt}
    lite = str(lane.get("key", "")) == "ZAI_API_KEY_Lite"
    if lite:
        # law 15 made structural: the Lite seat is paced before a single token leaves
        try:
            from mag import lite_guard
        except Exception:
            import lite_guard  # type: ignore
        g = lite_guard.check("research_fanout")
        if not g.get("ok"):
            rec.update({"ok": False, "error": "LITE_PACED", "detail": g.get("deny", "")})
            rec["latency_ms"] = 0
            return rec
    body = {"model": lane["model"], "temperature": 0.2, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": question}]}
    req = urllib.request.Request(
        lane["base"].rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "mag-research-fanout/1.0",
                 "HTTP-Referer": "https://local-sovereign-agent.invalid",
                 "X-Title": "Mag Research Fanout"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        msg = d["choices"][0]["message"]
        txt = (msg.get("content") or "").strip()
        if not txt:
            # a reasoning model can spend everything on reasoning and return no content:
            # keep the reasoning as evidence of WHY it is empty, never as an answer
            rec.update({"ok": False, "error": "empty_content",
                        "detail": (msg.get("reasoning") or msg.get("reasoning_content") or "")[:200],
                        "finish_reason": d["choices"][0].get("finish_reason")})
        else:
            rec.update({"ok": True, "answer": txt, "chars": len(txt),
                        "usage": d.get("usage") or {}})
            if lite:
                try:
                    from mag import lite_guard
                except Exception:
                    import lite_guard  # type: ignore
                lite_guard.record("research_fanout",
                                  int((d.get("usage") or {}).get("total_tokens") or 0),
                                  note=f"lane {lane['id']}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        rec.update({"ok": False, "error": f"HTTP {e.code}", "detail": detail})
    except Exception as e:
        rec.update({"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"})
    rec["latency_ms"] = int((time.time() - t0) * 1000)
    return rec


def probe_lanes() -> dict[str, Any]:
    env = _env()
    rows = []
    for lane in LANES:
        key = env.get(lane["key"], "")
        if not key:
            rows.append({"lane": lane["id"], "ok": False, "error": "NO_KEY"})
            continue
        r = call_lane(lane, "Reply with exactly: READY", key, timeout=45)
        rows.append({"lane": lane["id"], "model": lane["model"],
                     "ok": bool(r.get("ok")), "error": r.get("error"),
                     "latency_ms": r.get("latency_ms"),
                     "sample": (r.get("answer") or "")[:40]})
    live = [r["lane"] for r in rows if r["ok"]]
    return {"ok": True, "schema": SCHEMA, "lanes": rows, "live": live,
            "live_count": len(live), "dead": [r["lane"] for r in rows if not r["ok"]]}


def run(workers: int = 8, per_lane: int = 0, timeout: int = 120) -> dict[str, Any]:
    """The fan-out: every question to a lane, round-robin, receipts appended to raw.jsonl."""
    OUT.mkdir(parents=True, exist_ok=True)
    env = _env()
    live = [l for l in LANES if env.get(l["key"])]
    if not live:
        return {"ok": False, "schema": SCHEMA, "error": "no lanes with keys"}
    jobs = []
    for n, (qid, theme, q) in enumerate(BATTERY):
        lane = live[n % len(live)]
        jobs.append((qid, theme, q, lane))
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(call_lane, lane, q, env[lane["key"]], timeout): (qid, theme, q, lane)
                for (qid, theme, q, lane) in jobs}
        for f in futs:
            qid, theme, q, lane = futs[f]
            try:
                rec = f.result()
            except Exception as e:
                rec = {"ok": False, "error": f"worker:{e}", "lane": lane["id"],
                       "model": lane["model"], "latency_ms": 0}
            rec.update({"qid": qid, "theme": theme, "question": q})
            with _lock:
                results.append(rec)
                with RAW.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    ok = [r for r in results if r.get("ok")]
    summary = {
        "ok": True, "schema": SCHEMA, "ts": _now(),
        "battery_digest": battery_digest(), "questions": len(BATTERY),
        "answered": len(ok), "failed": len(results) - len(ok),
        "lanes_used": sorted({r["lane"] for r in results}),
        "per_lane": {ln: {"answered": sum(1 for r in results if r["lane"] == ln and r.get("ok")),
                          "failed": sum(1 for r in results if r["lane"] == ln and not r.get("ok"))}
                     for ln in sorted({r["lane"] for r in results})},
        "failures": [{"qid": r["qid"], "lane": r["lane"], "error": r.get("error")}
                     for r in results if not r.get("ok")],
        "raw": str(RAW),
        "median_latency_ms": sorted(r.get("latency_ms", 0) for r in results)[len(results) // 2],
    }
    _write_pack(results, summary)
    (OUT / "receipt.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    return summary


def _write_pack(results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    by_theme: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_theme.setdefault(r["theme"], []).append(r)
    lines = [
        "# RESEARCH 50 — WoW emulation, modding, hosting (free-channel fan-out)",
        "",
        f"*battery_digest `{summary['battery_digest']}` · {summary['answered']}/"
        f"{summary['questions']} answered · lanes {', '.join(summary['lanes_used'])} · "
        f"median latency {summary['median_latency_ms']} ms · generated {summary['ts']}*",
        "",
        "> **These are LEADS, not facts.** Every line below is model output from a free channel.",
        "> A lead is promoted only by a byte check against a clone or a file "
        "(`mag/wow_steal.py verify`, `mag/wow_family.py delta`). Failures are listed, not hidden.",
        "",
    ]
    if summary["failures"]:
        lines += ["## Failures (preserved)", ""]
        for f in summary["failures"]:
            lines.append(f"- `{f['qid']}` on `{f['lane']}` — {f['error']}")
        lines.append("")
    for theme in sorted(by_theme):
        lines += [f"## {theme}", ""]
        for r in sorted(by_theme[theme], key=lambda x: x["qid"]):
            lines.append(f"### {r['qid']} — {r['question']}")
            lines.append(f"*lane `{r['lane']}` · {r['model']} · {r.get('latency_ms')} ms*")
            lines.append("")
            lines.append(r.get("answer", f"**FAILED:** {r.get('error')}"))
            lines.append("")
    PACK.write_text("\n".join(lines), encoding="utf-8")


def _latest_by_qid() -> dict[str, dict[str, Any]]:
    """Latest receipt per question from the append-only raw tape."""
    best: dict[str, dict[str, Any]] = {}
    if RAW.is_file():
        for ln in RAW.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            qid = r.get("qid")
            if qid and (qid not in best or r.get("ok") or not best[qid].get("ok")):
                if r.get("ok") or qid not in best:
                    best[qid] = r
    return best


def retry(workers: int = 4, attempts: int = 2, timeout: int = 180,
          backoff: float = 4.0) -> dict[str, Any]:
    """Second pass: only the questions with no answer yet, on a rotating lane, with backoff.

    Pass 1 is not rewritten or deleted -- the retry appends, and the pack reports the merged view.
    """
    env = _env()
    lane_by_id = {l["id"]: l for l in LANES}
    live_ids = [l["id"] for l in LANES if env.get(l["key"])]
    got = _latest_by_qid()
    todo = [(i, t, q) for (i, t, q) in BATTERY if not got.get(i, {}).get("ok")]
    if not todo:
        return {"ok": True, "schema": SCHEMA, "note": "nothing to retry", "answered": len(got)}
    # prefer lanes that proved they answer, but rotate so a 429 does not own a question
    winners = [ln for ln in live_ids
               if any(r.get("ok") and r.get("lane") == ln for r in got.values())] or live_ids
    plan = [(qid, theme, q, winners[n % len(winners)]) for n, (qid, theme, q) in enumerate(todo)]
    results: list[dict[str, Any]] = []
    lock = threading.Lock()

    def job(item: tuple[str, str, str, str]) -> dict[str, Any]:
        qid, theme, q, start = item
        order = [start] + [ln for ln in winners if ln != start]
        last: dict[str, Any] = {}
        for n, ln in enumerate(order[:max(1, attempts)]):
            lane = lane_by_id[ln]
            if n:
                time.sleep(backoff * n)
            r = call_lane(lane, q, env[lane["key"]], timeout=timeout,
                          max_tokens=3000, attempt=2)
            r.update({"qid": qid, "theme": theme, "question": q, "pass": 2})
            with lock:
                results.append(r)
                with RAW.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            last = r
            if r.get("ok"):
                break
        return last

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        list(ex.map(job, plan))
    merged = _latest_by_qid()
    ok = [r for r in merged.values() if r.get("ok")]
    summary = {
        "ok": True, "schema": SCHEMA, "ts": _now(), "pass": 2,
        "battery_digest": battery_digest(), "questions": len(BATTERY),
        "answered": len(ok), "failed": len(BATTERY) - len(ok),
        "retried": len(todo),
        "answered_this_pass": sum(1 for r in results if r.get("ok")),
        "lanes_used": sorted({r["lane"] for r in merged.values()}),
        "per_lane": {ln: {"answered": sum(1 for r in merged.values() if r["lane"] == ln and r.get("ok")),
                          "failed": sum(1 for r in merged.values() if r["lane"] == ln and not r.get("ok"))}
                     for ln in sorted({r["lane"] for r in merged.values()})},
        "failures": [{"qid": r["qid"], "lane": r["lane"], "error": r.get("error")}
                     for r in merged.values() if not r.get("ok")],
        "raw": str(RAW),
        "median_latency_ms": sorted(r.get("latency_ms", 0) for r in merged.values())[len(merged) // 2],
    }
    _write_pack(list(merged.values()), summary)
    (OUT / "receipt.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    return summary


def status() -> dict[str, Any]:
    s = {"ok": True, "schema": SCHEMA, "battery_digest": battery_digest(),
         "questions": len(BATTERY), "lanes": len(LANES),
         "out": str(OUT), "raw_exists": RAW.is_file(),
         "pack_exists": PACK.is_file(),
         "cost": "free tiers only (groq, cerebras, mistral, z.ai; OpenRouter :free) — "
                 "paid keys XAI/ANTHROPIC/OPENAI deliberately excluded"}
    if (OUT / "receipt.json").is_file():
        s["last_run"] = json.loads((OUT / "receipt.json").read_text(encoding="utf-8"))
    return s


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="research-fanout")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["lanes", "battery", "run", "retry", "status"])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=120)
    a = ap.parse_args(argv)
    out = {"lanes": probe_lanes, "battery": battery, "status": status,
           "retry": lambda: retry(workers=max(1, a.workers // 2), timeout=a.timeout),
           "run": lambda: run(workers=a.workers, timeout=a.timeout)}[a.cmd]()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str)[:4000])
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
