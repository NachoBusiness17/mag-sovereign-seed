#!/usr/bin/env python3
"""Hermes warm boot — load fleet state into the seat at session start.

Closes the "Hermes forgets everything between sessions" gap.
Reads the Verkle chain tip, deployment registry, and session brief,
writes memory/warm_state.json so the seat can read it at startup.

CLI:
    python -m mag.hermes_warm_boot            # write warm_state.json
    python -m mag.hermes_warm_boot --json     # print payload, don't write
    python -m mag.hermes_warm_boot --verify   # just validate state
    python -m mag.hermes_warm_boot --check-deployments  # HEAD-probe known URLs

Schema: hermes_warm_state.v1
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

STATE = ROOT / "memory" / "warm_state.json"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
DEPLOY = ROOT / "vercel-deploy"
BRIEF = ROOT / "memory" / "briefs" / "latest.md"
DEPLOYMENTS_CONFIG = ROOT / "configs" / "deployments.json"

# AH5 (audit §2.3, 2026-09-30): this list was hardcoded inline in _deployments
# (old L86-89). It stays here as the last-resort default so a missing
# configs/deployments.json and a missing MAG_DEPLOYMENTS env break nothing.
_DEFAULT_KNOWN_URLS = [
    "https://vercel-deploy-7jx41m3r3-mag-d961.vercel.app/public/soul_frontier.html",
]

# AGENTS.md law: Vercel URLs may return 302 SSO redirects — verify with
# `curl -I` before reporting a deployment live. --check-deployments does the
# same HEAD probe (no auth) but a 302 it reports is still a redirect, not
# proof the surface is live.


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chain_tip() -> dict:
    """Read the last knot from the Verkle chain.

    AG5 (audit finding #3, 2026-09-30): this used to report keys ``leaves``/
    ``tag`` that chain rows never carry (rows use ``n_leaves`` and
    ``dominant_theme``), so both fields were always empty in warm_state.json.
    Field names now match the row schema verkle_knot writes.
    """
    if not CHAIN.exists():
        return {"ok": False, "error": "chain file not found"}
    lines = CHAIN.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if not lines:
        return {"ok": False, "error": "empty chain"}
    last = lines[-1]
    try:
        knot = json.loads(last)
        return {
            "ok": True,
            "index": knot.get("index"),
            "verkle_root": knot.get("verkle_root", "")[:16] + "...",
            "parent_root": knot.get("parent_verkle_root", "")[:16] + "...",
            "ts": knot.get("ts", ""),
            "n_leaves": knot.get("n_leaves"),
            "dominant_theme": knot.get("dominant_theme", ""),
        }
    except json.JSONDecodeError:
        return {"ok": False, "error": "last line not valid JSON"}


def _verify_chain() -> dict:
    """AG5: --verify actually proves the chain instead of echoing a flag."""
    try:
        from mag.verkle_knot import _verify_chain_consistent

        ok, why = _verify_chain_consistent()
        return {"ok": bool(ok), "reason": why}
    except Exception as e:  # a broken verify surfaces, never crashes the boot
        return {"ok": False, "reason": f"verify raised: {type(e).__name__}: {e}"}


def _deployment_urls() -> tuple[list[str], str, list[str]]:
    """Resolve known deployment URLs: env MAG_DEPLOYMENTS > configs/deployments.json > default.

    AH5 (audit §2.3, 2026-09-30): _deployments hardcoded the Vercel URL inline;
    the list now lives in config with the old inline value kept as the default
    fallback so nothing breaks when config and env are both absent. The env
    override is JSON — either a bare list of URLs or {"known_urls": [...]}.
    Returns (urls, source, notes); a bad env/config value is a note, not a crash.
    """
    notes: list[str] = []
    raw = os.environ.get("MAG_DEPLOYMENTS")
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            notes.append(f"MAG_DEPLOYMENTS is not valid JSON ({e}); ignored")
        else:
            candidate = parsed.get("known_urls") if isinstance(parsed, dict) else parsed
            if isinstance(candidate, list) and candidate and all(isinstance(u, str) for u in candidate):
                return list(candidate), "env", notes
            notes.append('MAG_DEPLOYMENTS must be a JSON list of URLs or {"known_urls": [...]}; ignored')
    if DEPLOYMENTS_CONFIG.exists():
        try:
            cfg = json.loads(DEPLOYMENTS_CONFIG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            notes.append(f"configs/deployments.json unreadable ({e}); using default")
        else:
            candidate = cfg.get("known_urls") if isinstance(cfg, dict) else None
            if isinstance(candidate, list) and candidate and all(isinstance(u, str) for u in candidate):
                return list(candidate), "configs", notes
            notes.append("configs/deployments.json has no usable known_urls list; using default")
    return list(_DEFAULT_KNOWN_URLS), "default", notes


def _deployments() -> dict:
    """Read the deployment registry from vercel-deploy/ + known URLs from config."""
    urls = []
    if DEPLOY.exists():
        for f in DEPLOY.rglob("*"):
            if f.suffix in (".html", ".json", ".md") and not f.name.endswith(".bak"):
                urls.append(str(f.relative_to(ROOT)))
    known, source, notes = _deployment_urls()
    return {"ok": True, "files": urls, "known_urls": known,
            "known_urls_source": source, "notes": notes}


def _head_no_redirect(url: str, timeout: float = 10.0) -> dict:
    """HEAD one URL without following redirects, no auth (AH5).

    Redirects are refused at the handler so a 302 SSO surfaces as a status +
    Location pair instead of silently landing on the sign-in page — the
    curl -I law in AGENTS.md, mechanized.
    """
    import urllib.error
    import urllib.request

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None  # refuse -> 3xx raises HTTPError carrying the headers

    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": "mag-warm-boot/ah5"})
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=timeout) as resp:
            return {"url": url, "status": resp.status, "redirect": None}
    except urllib.error.HTTPError as e:
        redirect = e.headers.get("Location") if 300 <= e.code < 400 else None
        return {"url": url, "status": e.code, "redirect": redirect}
    except Exception as e:  # DNS/timeout/SSL — reported, never crashes the boot
        return {"url": url, "status": None, "error": f"{type(e).__name__}: {e}"}


def check_deployments(timeout: float = 10.0) -> dict:
    """HEAD-probe every known deployment URL; ok=True when each got an HTTP status.

    A 302 counts as responded (it is reported with its Location and the
    verify-before-live caveat) — only a transport failure (timeout, DNS, TLS)
    makes ok False.
    """
    urls, source, notes = _deployment_urls()
    results = [_head_no_redirect(u, timeout=timeout) for u in urls]
    return {"ok": all(r["status"] is not None for r in results),
            "source": source, "notes": notes, "results": results}


def _session_brief() -> dict:
    """Read the latest session brief."""
    if not BRIEF.exists():
        return {"ok": False, "error": "no latest brief"}
    text = BRIEF.read_text(encoding="utf-8", errors="replace")
    return {"ok": True, "path": str(BRIEF), "chars": len(text), "updated": _now()}


def warm_boot(verify: bool = False) -> dict:
    """Generate the warm state payload."""
    state = {
        "schema": "hermes_warm_state.v1",
        "generated": _now(),
        "chain": _chain_tip(),
        "deployments": _deployments(),
        "session_brief": _session_brief(),
        "verify": verify,
    }
    if verify:
        # AG5: --verify used to set a flag and echo it back — now it runs the
        # real integrity gate over the chain before the seat trusts the tip.
        state["chain_verify"] = _verify_chain()
    return state


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Hermes warm boot")
    parser.add_argument("--json", action="store_true", help="print payload to stdout")
    parser.add_argument("--verify", action="store_true", help="validate only, don't write")
    parser.add_argument("--check-deployments", action="store_true",
                        help="HEAD-probe known deployment URLs (10s timeout, no auth)")
    args = parser.parse_args()

    if args.check_deployments:
        report = check_deployments()
        print(f"deployment URLs (source={report['source']}):")
        for r in report["results"]:
            if r["status"] is None:
                print(f"  {r['url']} -> ERROR {r['error']}")
            elif r["redirect"]:
                # curl -I law: a 302 is a redirect, not proof of live
                print(f"  {r['url']} -> {r['status']} redirect={r['redirect']} "
                      "(verify with curl -I before reporting live)")
            else:
                print(f"  {r['url']} -> {r['status']}")
        for note in report["notes"]:
            print(f"  note: {note}")
        return 0 if report["ok"] else 1

    state = warm_boot(verify=args.verify)

    if args.json:
        print(json.dumps(state, indent=2))
        return 0

    if not args.verify:
        STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print(f"warm_state.json written: {STATE}")

    # Summary line for the seat
    chain = state["chain"]
    deploys = state["deployments"]
    print(f"chain: index={chain.get('index')} root={chain.get('verkle_root','?')} ts={chain.get('ts')}")
    if args.verify:
        cv = state.get("chain_verify") or {}
        print(f"chain_verify: ok={cv.get('ok')} reason={cv.get('reason')}")
    print(f"deployments: {len(deploys.get('files', []))} files, {len(deploys.get('known_urls', []))} known URLs")
    print(f"session_brief: {state['session_brief'].get('chars', 0)} chars")
    if args.verify:
        return 0 if (state.get("chain_verify") or {}).get("ok") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
