#!/usr/bin/env python3
"""fanout v1 — the STANDING N-wide wave organ (compiled 2026-09-12 from three emitters).

Three independent fan-outs (astra arms, dozen-wide, p20) each wrote a throwaway
script and the third re-fought the security gate. Duplication compiled to one
invariant: "N-wide ask -> bespoke code -> gate re-fight -> runner evaporates."
This organ ends the pattern: CODE ONCE, PACKS ARE DATA.

Purity law (the nuance the gate taught): NO file I/O inside the cage.
  pack in via STDIN (docker exec -i ... < pack.json)
  lanes' text out via STDOUT after a ===FANOUTJSON=== marker
  progress lines go to STDERR
No open(), no os.path, no makedirs — nothing for a static path-traversal
detector to flag, ever again. Host-side redirection does all plumbing.

Pack shape (JSON):
{
  "model": "glm-5.3-flash",          # optional, this default
  "max_tokens": 12288,               # optional; >=8192 for 5.3 (thinking eats budget)
  "width": 4,                        # optional parallel lanes (pace guard)
  "key_env": "ZAI_API_KEY_Lite",     # optional env var name holding the bearer key
  "base": "https://api.z.ai/api/paas/v4/chat/completions",  # optional; host must be in HOST_ALLOW
  "shared_head": "one house head for all lanes (cache hits live here)",
  "lanes": [{"id": "L01_slug", "context": "...", "task": "..."}, ...]
}

Stderr progress: L01: OK 55s out=4400ch ctok=4650 cached=0
Stdout tail:     DONE 20/20 lanes ... then ===FANOUTJSON=== then one JSON object:
{"model":..., "lanes":[...meta...], "texts": {"L01_slug": "...", ...}}
"""
import json, os, socket, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_BASE = "https://api.z.ai/api/paas/v4/chat/completions"
DEFAULT_MODEL = "glm-5.3-flash"
DEFAULT_MAX_TOKENS = 12288
DEFAULT_WIDTH = 4
DEFAULT_KEY_ENV = "ZAI_API_KEY_Lite"
HOST_ALLOW = {"api.z.ai", "api.deepseek.com"}

def guarded_fetch(url):
    """Guard trio: https + allowlisted host + all resolved IPs global + no redirects."""
    from urllib.parse import urlparse
    p = urlparse(url)
    if p.scheme != "https" or p.hostname not in HOST_ALLOW:
        raise ValueError("host not allowed: %s" % p.hostname)
    import ipaddress
    for _fam, _typ, _proto, _canon, sa in socket.getaddrinfo(p.hostname, 443):
        if not ipaddress.ip_address(sa[0]).is_global:
            raise ValueError("non-global IP for %s" % p.hostname)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    return urllib.request.build_opener(NoRedirect)

def fire(pack, lane):
    from urllib.parse import urlparse
    base = pack.get("base", DEFAULT_BASE)
    if urlparse(base).hostname not in HOST_ALLOW:
        raise ValueError("pack base host not allowed")
    model = pack.get("model", DEFAULT_MODEL)
    max_tokens = int(pack.get("max_tokens", DEFAULT_MAX_TOKENS))
    prompt = pack["shared_head"] + "\n## CONTEXT\n" + lane["context"] + "\n\n## TASK\n" + lane["task"] + "\n"
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": max_tokens, "temperature": 0.7}).encode()
    key = os.environ[pack.get("key_env", DEFAULT_KEY_ENV)]
    req = urllib.request.Request(base, data=payload, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    t0 = time.time()
    try:
        body = json.loads(guarded_fetch(base).open(req, timeout=300).read().decode())
        text = body["choices"][0]["message"]["content"] or ""
        return lane["id"], text, body.get("usage", {}), time.time() - t0, None
    except Exception as e:
        return lane["id"], "", {}, time.time() - t0, str(e)[:300]

def main():
    pack = json.load(sys.stdin)
    lanes = pack["lanes"]
    key_env = pack.get("key_env", DEFAULT_KEY_ENV)
    if key_env not in os.environ:
        raise SystemExit("key env %s not present in container" % key_env)
    width = int(pack.get("width", DEFAULT_WIDTH))
    results, texts, spend = [], {}, 0
    with ThreadPoolExecutor(max_workers=width) as ex:
        futs = {ex.submit(fire, pack, lane): lane["id"] for lane in lanes}
        for fut in as_completed(futs):
            lane_id, text, usage, dt, err = fut.result()
            comp = usage.get("completion_tokens", 0)
            cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
            spend += comp
            print("%s: %s %.0fs out=%dch ctok=%d cached=%d" % (
                lane_id, "OK" if text else "FAIL: " + (err or "empty"), dt, len(text), comp, cached),
                file=sys.stderr, flush=True)
            if text:
                texts[lane_id] = text
            results.append({"lane": lane_id, "ok": bool(text), "dt": round(dt),
                            "completion_tokens": comp, "cached": cached, "err": err})
    ok = sum(1 for r in results if r["ok"])
    print("DONE %d/%d lanes, %d completion tokens" % (ok, len(lanes), spend), file=sys.stderr, flush=True)
    print("===FANOUTJSON===")
    print(json.dumps({"model": pack.get("model", DEFAULT_MODEL), "lanes": results, "texts": texts},
                     ensure_ascii=False))

if __name__ == "__main__":
    main()
