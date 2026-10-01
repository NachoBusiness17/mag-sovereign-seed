"""lite_scale -- the lite-key seat joins the scale salon (operator: "you also have
the lite key seat we need to use").

Three jobs on glm-5.3-flash (the strong seat):
  1. DOSTOEVSKY INTERIOR (lost to 429 twice on mistral-small)
  2. CALVINO LIGHTNESS (lost to 429 twice on or-glm52)
  3. FUSION DRAFT: the strongest salon returns folded into one transcendent cut

Pacing: rides lite_guard.check/record (law 15 ceiling).
SSRF guard: one literal https allowlist entry, host re-resolved per call with
private/loopback/link-local/reserved IPs blocked. Failures preserved as rows.
Schema: lite_scale.v1 . burst lane, paced . failures preserved.
"""
from __future__ import annotations

import ipaddress, json, socket, sys, time, urllib.parse, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scale_salon import PARABLE, CANON, CONSTRAINTS, WRITER_HEAD, OUT, _now
import lite_guard

CALL_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"  # 09-16: coding-plan keys 1113 on the old /api/paas/v4 path even with full pool
MODEL = "glm-5.3-flash"


def _guard(url: str) -> str:
    """Protocol + exact-URL allowlist + resolved-IP boundary check. Returns the url or raises."""
    if url != CALL_URL:
        raise ValueError(f"url not allowlisted: {url!r}")
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError("non-https url")
    host = urllib.parse.urlparse(url).hostname
    for _fam, _typ, _proto, _canon, sa in socket.getaddrinfo(host, 443):
        ip = ipaddress.ip_address(sa[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast):
            raise ValueError(f"resolved address blocked: {ip}")
    return url


def _key() -> str:
    env: dict[str, str] = {}
    for p in (ROOT := Path(__file__).resolve().parent.parent) and [ROOT / ".env"]:
        if p.is_file():
            for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
                ln = ln.strip()
                if ln and not ln.startswith("#") and "=" in ln:
                    k, v = ln.split("=", 1)
                    env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    for var in ("ZAI_API_KEY_Lite", "ZAI_API_KEY_L", "ZAI_API_KEY_LITE", "ZAI_API_KEY"):
        if env.get(var):
            return env[var]
    return ""


def call(prompt: str, temperature: float, max_tokens: int = 3200) -> dict:
    t0 = time.time()
    rec: dict = {"lane": "lite-glm53flash", "model": MODEL, "ts": _now()}
    gate = lite_guard.check("scale_salon")
    if not gate.get("allowed", True):
        rec.update({"ok": False, "error": f"lite_pacing_denied: {gate}"})
        rec["latency_ms"] = 0
        return rec
    try:
        url = _guard(CALL_URL)
    except ValueError as e:
        rec.update({"ok": False, "error": f"ssrf_guard: {e}"})
        rec["latency_ms"] = 0
        return rec
    body = {"model": MODEL, "temperature": temperature, "max_tokens": max_tokens,
            "thinking": {"type": "enabled"}, "reasoning_effort": "low",
            "messages": [{"role": "system", "content":
                          "You are a master parable writer working an assignment. "
                          "Output only the work and the two contract lines. No preamble."},
                         {"role": "user", "content": prompt}]}
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {_key()}", "Content-Type": "application/json",
                 "User-Agent": "mag-lite-scale/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        msg = d["choices"][0]["message"]
        txt = (msg.get("content") or "").strip()
        usage = d.get("usage") or {}
        tokens = int(usage.get("total_tokens") or 0)
        if txt:
            try:
                lite_guard.record("scale_salon", tokens, "scale salon lite seat")
            except Exception:
                pass
            rec.update({"ok": True, "answer": txt, "chars": len(txt), "usage": usage})
        else:
            rec.update({"ok": False, "error": "empty_content",
                        "detail": (msg.get("reasoning_content") or "")[:200]})
    except urllib.error.HTTPError as e:
        rec.update({"ok": False, "error": f"HTTP {e.code}", "detail": e.read().decode("utf-8", "replace")[:200]})
    except Exception as e:
        rec.update({"ok": False, "error": f"{type(e).__name__}: {str(e)[:140]}"})
    rec["latency_ms"] = int((time.time() - t0) * 1000)
    return rec


BEST = """BEST RETURNS SO FAR (harvested moves from the 9-lane salon):
- KJV: "complaint is weight, and the scale bore it away" / final line variant "The price was good."
- Zhuangzi lane: the old man "knew where the grain of the wood ran, and he cut around the knots, not through them"; "He was not wise in the way of the market."
- Go-mind lane: the vineyard as a field of nineteen lines; "Neither spoke for what might have been a ko"; invasion instead of blight; stones that "seemed to conflict yet saved each other."
- Beast fable lane: the scale as a creature called the Weigher ("a tongue of iron and a belly of glass"); its closing line "The Weigher is a good thing, but it does not know the names."
- Plains lane: "the wind turning his coat"; the boundary as "a thin line."
- The constant lines every version kept: one instrument sold to every farm; lists that shorten with no order given; "he could not have named five of the people he had let go"; the final exchange ending "It was a good price." """

JOBS = [
    ("dostoevsky", 0.8,
     WRITER_HEAD + PARABLE + "\n\n" + CANON + "\n\n" + CONSTRAINTS + """

YOUR LANE: Dostoevsky interior. The vineyard man's own voice, the night after the third list. First person. He is not sorry yet, and he almost is. He must never say which. The scale speaks only in his quotations of it. End before morning.

End with exactly two lines:
HIDDEN: <where you hid one thing>
MOVE: <your single strongest change>"""),
    ("calvino", 0.8,
     WRITER_HEAD + PARABLE + "\n\n" + CANON + "\n\n" + CONSTRAINTS + """

YOUR LANE: Calvino lightness. The scale as a merchant of invisible things: exact, playful, weightless; the heaviest idea in the lightest prose. Geography may go fable-wide.

End with exactly two lines:
HIDDEN: <where you hid one thing>
MOVE: <your single strongest change>"""),
    ("fusion", 0.7,
     WRITER_HEAD + PARABLE + "\n\n" + CANON + "\n\n" + CONSTRAINTS + "\n\n" + BEST + """

YOUR LANE: the fusion seat. Fold the strongest harvested moves above into ONE transcendent cut of THE SCALE -- keep the vineyard (not the Go board, not the bees), keep every constant line listed, and choose which harvested lines earn their place. The result must read as if written by one hand in one sitting. This will be published; make it permanent.

End with exactly two lines:
HIDDEN: <where you hid one thing>
MOVE: <your single strongest change>"""),
]


def main() -> int:
    rows = []
    with ThreadPoolExecutor(max_workers=len(JOBS)) as ex:
        futs = [ex.submit(call, p, t) for _n, t, p in JOBS]
        for f, (_n, _t, _p) in zip(futs, JOBS):
            r = f.result()
            r["job"] = _n
            rows.append(r)
            print(f"  {_n:11s} {'OK ' if r['ok'] else 'ERR'} {r.get('chars', '')} chars {r['latency_ms']}ms"
                  + ("" if r["ok"] else f"  {str(r.get('error', ''))[:60]}"))
    raw = OUT / "lite_raw.jsonl"
    with raw.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    pack = OUT / "LITE_PACK.md"
    pack.write_text("\n\n".join(
        f"## {r['job']} -- {'OK' if r['ok'] else 'ERR ' + str(r.get('error', ''))}\n\n{r.get('answer', r.get('detail', ''))}"
        for r in rows), encoding="utf-8")
    print(f"pack: {pack}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
