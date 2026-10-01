"""salon_50 -- a 50-wide adversarial salon over the untouched estate + tonight's syllabus.

The operator's directive (2026-09-16): "let em go against each other in a very
loud salon, dogfooding our processes -- we have so much in the local sovereign
agent folder that never gets touched. Each agent finishes it writes the
instructions for the next self steal. Keep iterating until there's nothing
left to do. Then plan the next basecamp."

Design: reuses the proven lane plumbing from mag/research_fanout (LANES +
call_lane), but the battery is MINE: four themes --
  A LINK-LEDGER      evaluate tonight's syllabus (verify / stance / action)
  B UNTOUCHED-CORPUS  real untouched estate files, excerpts embedded in-question
  C ADVERSARIAL       both sides of six open arguments, fired to different lanes
  D SELF-STEAL CHAIN  steal a mechanism from tonight, END with NEXT-STEAL: <handoff>
Every question's contract: end with "NEXT-STEAL: <one instruction for the next pass>"

Schema: salon_50.v1 . free lanes only . $0 . failures preserved
"""
from __future__ import annotations

import json, sys, datetime, hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research_fanout import LANES, call_lane, _env  # proven plumbing, reused

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "memory" / "runs" / "salon_50_20260916"
RAW = OUT / "raw.jsonl"
PACK = OUT / "SALON_PACK.md"
CONTRACT = "End your answer with: NEXT-STEAL: <one instruction for the next agent's self-steal pass>"


def _peek(rel: str, n: int = 1200) -> str:
    p = ROOT / rel
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:n]
    except OSError:
        return f"[unreadable: {rel}]"


def build_battery() -> list[dict]:
    B = []

    def q(qid: str, theme: str, text: str):
        B.append({"qid": qid, "theme": theme, "q": text + " " + CONTRACT})

    # A — LINK LEDGER (tonight's syllabus, evaluated)
    ledger = [
        ("A01", "Universal Weight Subspace (JHU 2512.05117): 1,100+ models collapse into ~16 shared directions"),
        ("A02", "MoE routing: top-k expert banks, load balancing, router z-loss, token dropping (Mixtral/DeepSeek-V3/Qwen3)"),
        ("A03", "Stellar Colosseum (Google 2609.15983): many-agent math-research harness, falsification attacks, 71% TCS-Bench"),
        ("A04", "Dream-RSI (Google): accumulated discovery history replayed as a simulator to improve agents offline"),
        ("A05", "NVIDIA OpenShell: Z3 verifies agent actions and returns the exact constraint adjustment on rejection"),
        ("A06", "Anthropic memory pyramid: working/episodic/semantic/procedural + an explicit forgetting engine (26k->1.8k tokens)"),
        ("A07", "Critical attention scaling (2510.05554): at 1M context only log-scaling works"),
        ("A08", "Steins;Git: git branches carry worldline divergence meters (how far drifted from main)"),
        ("A09", "Predictive processing: perception is a forecast from priors; whoever sets the priors steers the perception"),
        ("A10", "Cryptanalytic model extraction with NO architecture assumption (2609.14379)"),
        ("A11", "Epi (Bake AI): autonomous research producing receipt-shaped records (bound + construction records)"),
        ("A12", "DeepSeek Harness: fully modular agent, session-log transparency rule (nothing the model sees skips the log)"),
    ]
    for qid, t in ledger:
        q(qid, "A-LINK-LEDGER",
          f"Evaluate for a local-sovereign agent fleet (deterministic kernels, append-only ledgers, "
          f"multi-seat salons, Discord venue). Subject: {t}. Answer: (1) verified or vendor-claim, "
          f"(2) stance STEAL/ADAPT/REJECT/CONTENT, (3) the single concrete action worth taking this week.")

    # B — UNTOUCHED CORPUS (real files, excerpts embedded)
    corpus = [
        ("B01", "corpus/telegram/MrPool_Q.jsonl"),
        ("B02", "research/gaming_corpus/marathon_terminals/m3/envy.txt"),
        ("B03", "docs/ref/canon/canon_tokens_as_spores_v8.txt"),
        ("B04", "privlidge/gomoku_brains.html"),
        ("B05", "handoff/OX_MEGA3_t0064.json"),
        ("B06", "watch/BASECAMP_GAME_ATLAS_20260901.md"),
        ("B07", "_game_proof.json"),
        ("B08", "game.html"),
        ("B09", "module_map_data.js"),
        ("B10", "steal_tools_data.js"),
        ("B11", "docs/ref/GRAYSWAN_ARENA_STEAL.md"),
        ("B12", "dashboard/static/night/maze_synthesis.html"),
        ("B13", "mag/mud_steal.py"),
        ("B14", "mag/game_world.py"),
        ("B15", "docs/ref/NG_AISRP_RIGHTSIZED.md"),
        ("B16", "watch/CORPUS_FOUND_20260901.md"),
        ("B17", "research/gaming_corpus/l0_contract_crossmap.md"),
        ("B18", "docs/ref/canon/x_canon_2026_fx/index.txt"),
    ]
    for qid, rel in corpus:
        excerpt = _peek(rel)
        q(qid, "B-UNTOUCHED-CORPUS",
          f"This estate file has never been read by the fleet's agents. Path: {rel}. "
          f"Verbatim excerpt:\n```\n{excerpt}\n```\n"
          f"Answer: (1) what this file IS, (2) the single most load-bearing thing in it, "
          f"(3) what the fleet should build or steal from it this week.")

    # C — ADVERSARIAL PAIRS (both sides fired to different lanes)
    sides = [
        ("C01a", "C01b", "client-vs-bones",
         "ARGUE FOR: AzerothCore needs a real game client to be worth anything to our fleet.",
         "ARGUE FOR: headless bones-as-data beats any client — the game is the rules, not the pixels."),
        ("C02a", "C02b", "venue-mud-vs-wow",
         "ARGUE FOR: the MUD is the right venue for the fleet's game sessions.",
         "ARGUE FOR: a new WoW-bones venue should replace the MUD as the fleet's world."),
        ("C03a", "C03b", "divergence-meter-vs-clock",
         "ARGUE FOR: branch divergence meters (Steins;Git style) are the dashboard's next must-have.",
         "ARGUE FOR: divergence meters are decoration — wall-clock uptime and test status are the real dashboard."),
        ("C04a", "C04b", "janitor-first-vs-frontier",
         "ARGUE FOR: janitor-first local models are sufficient for the fleet's real work.",
         "ARGUE FOR: the Matthew Effect means local-only practice caps the fleet — frontier escalation is mandatory."),
        ("C05a", "C05b", "forgetting-vs-append-only",
         "ARGUE FOR: the fleet needs a forgetting engine (Anthropic pyramid) or the record drowns.",
         "ARGUE FOR: append-only is sacred — forgetting is loss, and loss is how the cage wins."),
        ("C06a", "C06b", "discord-vs-local-deck",
         "ARGUE FOR: Discord is the right venue — strangers can watch, the bot is the front door.",
         "ARGUE FOR: localhost is the right venue — 127.0.0.1 is the only address that needs no permission."),
    ]
    for a, b, name, fa, fb in sides:
        q(a, "C-ADVERSARIAL", f"{fa} Steelman it with one concrete fleet fact. {CONTRACT}")
        q(b, "C-ADVERSARIAL", f"{fb} Steelman it with one concrete fleet fact. {CONTRACT}")

    # D — SELF-STEAL CHAIN
    seeds = [
        ("D01", "steal the best mechanism from tonight's Astra bundle calibration (qa receipts, F-D1 self-fires, stance ledgers)"),
        ("D02", "steal the best mechanism from the Discord bot bring-up (token landing, falsifier-first debugging, honest retry)"),
        ("D03", "steal the best mechanism from the fallen-humanity debate pack (motion splitting, receipt-chain, tri-stated verdict)"),
        ("D04", "steal the best mechanism from the wow_bones six-slot map (stance ledger, byte-verified citations, rejects as arguments)"),
        ("D05", "steal the best mechanism from the predictive-processing drop (priors, perception, ownership of the model)"),
        ("D06", "steal the best mechanism from the estate walk replay (233 nodes, 2,219 trail events, 92.4% replay)"),
        ("D07", "steal the best mechanism from the Steins;Git divergence meter (worldline numbers per branch)"),
        ("D08", "steal the best mechanism from the 30-link syllabus (subspace, MoE, Colosseum, memory pyramid, thermodynamic compute)"),
    ]
    for qid, s in seeds:
        q(qid, "D-SELF-STEAL",
          f"A fleet ran a session where it: brought a Discord bot online through four security locks, "
          f"calibrated six exam families with falsifier clauses that fired on their own author, "
          f"debated theology with tri-stated verdicts, and measured 35 git worldlines. Your job: {s}. "
          f"Give the mechanism in three sentences, then name where it plugs in. {CONTRACT}")

    return B


def run(workers: int = 6, timeout: int = 150) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    B = build_battery()
    env = _env()
    live = [l for l in LANES if env.get(l["key"])]
    if not live:
        return {"ok": False, "error": "no lanes with keys"}
    digest = hashlib.sha256(json.dumps(B, sort_keys=True, ensure_ascii=False)
                            .encode()).hexdigest()[:16]
    jobs = []
    for n, item in enumerate(B):
        lane = live[n % len(live)]
        jobs.append((item, lane))
    results = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(call_lane, lane, it["q"], env[lane["key"]], timeout): it
                for it, lane in jobs}
        for f in futs:
            it = futs[f]
            lane = jobs[list(futs).index(f)][1] if False else None
            try:
                rec = f.result()
            except Exception as e:
                rec = {"ok": False, "error": f"worker:{e}"}
            rec.update({"qid": it["qid"], "theme": it["theme"]})
            with open(RAW, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            results.append(rec)
    ok = [r for r in results if r.get("ok")]
    summary = {"ok": True, "schema": "salon_50.v1", "ts": datetime.datetime.utcnow().isoformat() + "Z",
               "battery_digest": digest, "questions": len(B),
               "answered": len(ok), "failed": len(results) - len(ok),
               "lanes_used": sorted({r.get("lane", "?") for r in results})}
    (OUT / "receipt.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    return summary


def fold() -> dict:
    """The fold: extract every NEXT-STEAL handoff + the verdict lines from the raw tape."""
    steals = []
    if RAW.is_file():
        for ln in RAW.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            t = r.get("answer") or ""
            for line in t.splitlines():
                if "NEXT-STEAL:" in line:
                    steals.append({"qid": r.get("qid"), "lane": r.get("lane"),
                                   "steal": line.split("NEXT-STEAL:", 1)[1].strip()[:220]})
    return {"steals": len(steals), "chain": steals}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "fold":
        print(json.dumps(fold(), ensure_ascii=False, indent=2)[:4000])
    elif cmd == "battery":
        b = build_battery()
        print(json.dumps({"questions": len(b),
                          "themes": {t: sum(1 for x in b if x["theme"] == t)
                                     for t in {x["theme"] for x in b}}}, indent=2))
    else:
        print(json.dumps(run(workers=6), ensure_ascii=False)[:600])
