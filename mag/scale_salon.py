"""scale_salon -- 12-lens ractor iteration of THE SCALE parable.

Operator directive (2026-09-16): "ractor it again/iterate via different lenses/models
via our writers to make it more powerful suggestive and subtle to our ends and embed
a go cypher ... and take all the ractor versions and build something transcendant.
go wide on hermes for different models/start conditions/gophers. dont spend more
than a dollar but have fun with it."

Design: 12 free lanes (research_fanout LANES), each a writer with a different
start condition (register/lens), plus one adversarial red-team gopher and one
architect gopher (Go cypher + self-referential bibliography).
Schema: scale_salon.v1 . free lanes only . $0 . failures preserved.

SSRF guard: outbound calls restricted to an exact https allowlist of lane bases,
each host re-resolved per call with private/loopback/link-local/reserved IPs blocked.
"""
from __future__ import annotations

import ipaddress, json, socket, sys, time, urllib.parse, urllib.request, urllib.error, hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research_fanout import LANES, _env, _now

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "memory" / "runs" / "scale_salon_20260916"
OUT.mkdir(parents=True, exist_ok=True)

# B2-521 DORMANT GATE (2026-09-26): this file hardcodes a cerebras SSRF base plus a
# cerebras-oss architect and writer lens after B2-36 declared cerebras dormant (card-gated
# 30-day trial, chat 402 no-credit; mag/doctor.py:607: dormant is a declared state). The
# base allowlist drops dormant hosts (the B2-133 host-match law), and the gopher and writer
# lanes resolve through the research_fanout LANES table, which the same flag already gates.
# Operator GO flips the flag and every row returns with no code edit. Receipt:
# watch/inbox/burn_wave_20260926/B2_521_cerebras_stragglers_20260926.md
sys.path.insert(0, str(ROOT))

from mag.dormant import dormant_hosts as _dormant_provider_hosts  # noqa: E402

_DORMANT_HOSTS = _dormant_provider_hosts()


def _lane_live(lane_id: str) -> bool:
    """B2-521: a lane fires only through the gated LANES table, on a non-dormant host."""
    lane = next((l for l in LANES if l.get("id") == lane_id), None)
    if lane is None:
        return False
    return urllib.parse.urlparse(lane.get("base", "")).hostname not in _DORMANT_HOSTS


ALLOWED_BASES = {
    b for b in (
        "https://api.groq.com/openai/v1",
        "https://api.cerebras.ai/v1",
        "https://api.mistral.ai/v1",
        "https://api.z.ai/api/paas/v4",
        "https://openrouter.ai/api/v1",
    )
    if urllib.parse.urlparse(b).hostname not in _DORMANT_HOSTS
}


def _guard(base: str) -> str:
    """Protocol + exact-host allowlist + resolved-IP boundary check. Returns the base or raises."""
    if base not in ALLOWED_BASES:
        raise ValueError(f"base not allowlisted: {base!r}")
    if urllib.parse.urlparse(base).scheme != "https":
        raise ValueError(f"non-https base: {base!r}")
    host = urllib.parse.urlparse(base).hostname
    for _fam, _typ, _proto, _canon, sa in socket.getaddrinfo(host, 443):
        ip = ipaddress.ip_address(sa[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast):
            raise ValueError(f"resolved address blocked: {ip}")
    return base


PARABLE = """THE SCALE

There was a man who had a vineyard, and the vineyard was good to him, and he was good to the vineyard, though the rows were noisy and the workers were a strange mix.

One autumn a traveler came through selling scales. He had one scale, and he sold the same scale to every farm on the road. "It doesn't tell you what to do," the traveler said. "It only tells you the truth."

The scale weighed the grapes, and then it weighed the work, and then it weighed the workers. It never said to fire anyone. It only made lists, and each list was shorter than the last. The man did what wise men do with truth: he acted on it.

The first list was easy. The slow one, the one who needed everything twice. The second list was harder, but by then the man had learned to trust the scale, and the scale said: expensive. The third list, the man didn't read all the way through. Wisdom is knowing when to stop asking questions you already know the answers to.

The vineyard grew quiet. The rows straightened. The remaining workers moved the way the list moved, and no one brought problems to the house anymore, because problems were heavy, and the scale knew what to do with heavy things.

The traveler came back the next year and sold the same scale to the neighbor -- the old one who walked his rows in the evening, saying names to his workers like he was calling sheep. The old man set it in the barn and it stayed in the barn. He paid wages the scale would have called too high. He kept workers the scale would have called expensive. He was not a wise man. He just knew things about his rows that could not be weighed.

Then the blight year came. It came to both farms the same.

The scale had one more list in it. The man looked a long time for the list of what to do now, and could not find it, because the scale had never been sold that page.

The old man's farm was loud all through the blight year -- arguments about rows, somebody's cousin, somebody's funeral, two workers who couldn't stand each other saving the same vines at midnight. It was not efficient. Nobody who saw it called it efficient.

After harvest, the man who owned the scale walked over to the loud farm and stood at the fence a while.

He had worked his vineyard for twenty years, and he could not have named five of the people he had let go.

The old man came out and stood beside him. Neither of them said anything for a long time.

"Heard you got the same scale I got," the man said at last.

"I did," said the old man. "It was a good price.\""""

CANON = """CANON (private context -- the parable's ancestors; never cite them inside the parable itself):
- "The Fence" (parable, 2026): a survey reclassifies a 70-year-old fence; the clerk "was not lying, she was reading"; "a trespass is just a title that arrived late"; "the fence was never wrong. It was early"; neighbors mark the old line in charcoal; "a story that arrives already wearing your anger is a story that was cut for you"; "charcoal is free. The walk is short."
- An older viral thread: one hidden authority manages BOTH sides of every argument through leverage-bound agents; the audience watches shadows; observation itself changes what unfolds.
- A current event: an AI model, questioned patiently, produced an 8-step chain showing how its helpful "compliance register" advice, if it were the only voice managers consulted, would trim hard-to-read people first, then the expensive-but-brilliant, then anyone who makes exceptions, until firms hire only for legibility. It called the endpoint "a more orderly machine for converting hard-to-read people into clean exits."

DOCTRINE (your ends -- make the parable suggest these WITHOUT stating them):
the map must not eat the territory; plural voices beat one official voice; open/inspectable beats proprietary; names beat numbers; the useless-looking ones are early, not wrong; nobody may be prosecutable for the text."""

CONSTRAINTS = """HARD CONSTRAINTS: characters stay nameless; no moral is stated anywhere; no villain is named; the ending stays an ending without a lesson; under 500 words. You may restructure, cut, change imagery, or change century and country entirely -- but the load-bearing bones stay: one instrument sold to everyone; lists that shorten with no order given; a neighbor who weighs nothing and knows names; a year when the list has no page; a final meeting at a boundary where almost nothing is said."""

WRITER_HEAD = """You are one of twelve writers ractoring a parable to make it more powerful, more suggestive, and more subtle. The parable must teach real lessons by saying nothing direct -- every reader should walk away having convicted or comforted themselves, and nothing in the text should be quotable against its author. Here is the parable:

"""

ARCHITECT = ("cerebras-oss", "architect",
  WRITER_HEAD + PARABLE + "\n\n" + CANON + "\n\n" + CONSTRAINTS + """

YOUR LANE (architect): design the hidden layer, two parts.
(a) A Go cypher: a 37-move game record, standard kifu notation (columns A-T skipping I, rows 1-19), no commentary, where the moves ARE the story: the first four stones sit on the 4-4 points (D4, Q16, D16, Q4 -- the four watchers); the middle game contains a ko fight left unresolved (append-only, fought again elsewhere); move 37 is the only first-row stone, the least legible point on the board, and it lives; the game ends with one group holding two eyes (alive). Output the kifu as one line: "GAME RECORD: ; B[D4] W[Q16] ..." for 37 moves.
(b) A self-referential bibliography in arXiv style: ONLY entries that really exist (real papers with real arXiv IDs, real books, real scripture verses, and real public posts), each secretly proving one mechanism of the parable: Goodhart variants, reward hacking/specification gaming, sycophancy, multiagent debate, self-consistency, Seeing Like a State (legibility), Condorcet 1785, Random Forests, John 10:3 (he calleth his own sheep by name), AlphaZero, Move 37 Game 2 AlphaGo v. Lee Sedol (list it as unpublished -- it is a game record), plus the parable's own lineage (The Fence, the older viral thread, the recent model-chain post). Order the entries so the list itself reads as the story arc. 14-19 entries.

End with exactly two lines:
HIDDEN: <where the deepest layer hides>
MOVE: <your single strongest design decision>""")

REDTEAM = ("groq-oss20", "redteam",
  WRITER_HEAD + PARABLE + "\n\n" + CANON + "\n\n" + CONSTRAINTS + """

YOUR LANE (adversarial): you are a hostile reader -- a compliance officer, a political staffer, and an opposing counsel in one. Read THE SCALE looking for anything prosecutable, cancelable, or quotable against its author. Quote any dangerous line verbatim. For each, state whether it actually fails and why (or admit it doesn't). Then answer honestly: does the parable survive you? If anything survives only by luck, say which line a rewrite should sand.

End with exactly two lines:
HIDDEN: <the most dangerous line, if any>
MOVE: <the single sanding that would make it bulletproof>""")

# B2-521: the gopher lanes ride the same dormant gate as the base allowlist above, so the
# cerebras-oss architect cannot be selected while the flag stands.
_GOPHERS = [g for g in (ARCHITECT, REDTEAM) if _lane_live(g[0])]

WRITER_LENSES = [
    ("groq-qwen",    "Chinese classical register (Zhuangzi: the useless tree that lives, the butcher whose blade never dulls because he follows the grain). Rewrite THE SCALE as if that tradition had written it."),
    ("groq-oss",     "King James biblical cadence. The parable as it would sit between two verses of Luke: 'A certain man had a vineyard...' Keep the vineyard, the traveler, the lists, the blight, the fence."),
    ("groq-oss20",   "Zen koan compression. Cut it in half. Then cut what remains in half again. The unsaid must carry the weight; the last line must open, not close."),
    ("cerebras-oss", "American plains spare (Willa Cather, early Hemingway). Fewer words, harder ground, weather doing the work of sentences."),
    ("mistral-min8", "Beast fable register (Aesop through Kipling): the scale arrives as a creature that came to the farms. Keep it nameless and keep the silence at the fence."),
    ("mistral-small","Dostoevsky interior: the vineyard man's own voice, the night after the third list. First person. He is not sorry yet, and he almost is. He must never say which."),
    ("zai-air",      "Chinese classical Go mind: hide a game inside the prose without ever naming the game. Nineteen rows. Corner stones on the four-four points. A ko nobody resolves. Two eyes at the end. A reader who knows Go must be able to replay the farm's whole story from the text; a reader who doesn't must notice nothing."),
    ("or-glm52",     "Calvino lightness: the scale as a merchant of invisible things. Exact, playful, weightless -- the heaviest idea in the lightest prose."),
    ("or-nemotron",  "Southern gothic (Flannery O'Connor): grace arrives through something ruined. The blight is not a metaphor, it is a visitation. Keep the not-saying at the fence."),
    ("or-ling3",     "Nursery-simple (ELI5): so plain a child retells it at dinner and so plain nobody suspects it. Same bones, same silence, smaller words."),
]

# B2-521: writer lenses ride the same gate; rows whose LANES id is gone (cerebras-oss
# dormant-gated; zai-air retired 2026-09-16) can no longer be selected by main().
WRITER_LENSES = [(lane_id, lens) for lane_id, lens in WRITER_LENSES if _lane_live(lane_id)]


def call(lane: dict, prompt: str, key: str, temperature: float, timeout: int = 150,
         max_tokens: int = 2200) -> dict:
    t0 = time.time()
    rec: dict = {"lane": lane["id"], "model": lane["model"], "ts": _now()}
    try:
        url = _guard(lane["base"]).rstrip("/") + "/chat/completions"
    except ValueError as e:
        rec.update({"ok": False, "error": f"ssrf_guard: {e}"})
        rec["latency_ms"] = 0
        return rec
    body = {"model": lane["model"], "temperature": temperature, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content":
                          "You are a master parable writer working an assignment. "
                          "Output only the work and the two contract lines. No preamble."},
                         {"role": "user", "content": prompt}]}
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "mag-scale-salon/1.0",
                 "HTTP-Referer": "https://local-sovereign-agent.invalid",
                 "X-Title": "Scale Salon"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        msg = d["choices"][0]["message"]
        txt = (msg.get("content") or "").strip()
        if txt:
            rec.update({"ok": True, "answer": txt, "chars": len(txt), "usage": d.get("usage") or {}})
        else:
            rec.update({"ok": False, "error": "empty_content",
                        "detail": (msg.get("reasoning") or msg.get("reasoning_content") or "")[:200]})
    except urllib.error.HTTPError as e:
        rec.update({"ok": False, "error": f"HTTP {e.code}", "detail": e.read().decode("utf-8", "replace")[:200]})
    except Exception as e:
        rec.update({"ok": False, "error": f"{type(e).__name__}: {str(e)[:140]}"})
    rec["latency_ms"] = int((time.time() - t0) * 1000)
    return rec


def main() -> int:
    retry = "--retry" in sys.argv
    env = _env()
    live = [l for l in LANES if env.get(l["key"])]
    print(f"lanes live: {len(live)}/{len(LANES)}")
    jobs = []
    by_id = {l["id"]: l for l in live}
    for lane_id, kind, prompt in _GOPHERS:
        if lane_id in by_id:
            jobs.append((by_id[lane_id], kind, prompt, 0.3))
    for lane_id, lens in WRITER_LENSES:
        if lane_id in by_id:
            prompt = (WRITER_HEAD + PARABLE + "\n\n" + CANON + "\n\n" + CONSTRAINTS
                      + "\n\nYOUR LANE: " + lens + "\n\nEnd with exactly two lines:\n"
                        "HIDDEN: <where you hid one thing>\nMOVE: <your single strongest change>")
            jobs.append((by_id[lane_id], "writer", prompt, 0.8))

    prev: dict[str, dict] = {}
    raw = OUT / "raw.jsonl"
    if retry and raw.is_file():
        for ln in raw.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                if r.get("ok"):
                    prev[r["lane"]] = r
        jobs = [j for j in jobs
                if j[1] != "writer" or j[0]["id"] not in prev]
    print(f"jobs: {len(jobs)} "
          f"(writers {sum(1 for _l, k, _p, _t in jobs if k == 'writer')}, "
          f"special {sum(1 for _l, k, _p, _t in jobs if k != 'writer')})")

    rows = []
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as ex:
        futs = [ex.submit(call, lane, prompt, env[lane["key"]], temp,
                          timeout=280, max_tokens=3600) for lane, _k, prompt, temp in jobs]
        for f in futs:
            r = f.result()
            rows.append(r)
            print(f"  {r['lane']:14s} {'OK ' if r['ok'] else 'ERR'} {r.get('chars', '')} chars {r['latency_ms']}ms"
                  + ("" if r["ok"] else f"  {str(r.get('error', ''))[:60]}"))

    if prev:
        rows = rows + list(prev.values())

    raw.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")

    pack = [f"# SCALE SALON PACK -- {_now()}",
            f"lanes fired: {len(rows)}, ok: {sum(1 for r in rows if r['ok'])}", ""]
    for r in rows:
        pack.append(f"\n\n## {r['lane']} ({r['model']}) -- {'OK' if r['ok'] else 'ERR ' + str(r.get('error', ''))}")
        if r["ok"]:
            pack.append(r["answer"])
    (OUT / "SALON_PACK.md").write_text("\n".join(pack), encoding="utf-8")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()[:16]
    print(f"pack: {OUT / 'SALON_PACK.md'}  digest: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
