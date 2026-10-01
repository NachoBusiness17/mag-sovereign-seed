"""auth_switchboard — the AUTH track on the mag switchboard.

Lineage (self-steal 2026-09-05): env_switch/registry switched CODE tracks
(branch+port), switchboard.py routed the mesh, switchboard_v2 gated policy.
None of them switched the seat's IDENTITY: which z.ai account / provider key /
coding plan the ZCode app rides. The 09-05 account-swap mess (dead API key left
enabled on builtin:zai while the OAuth coding-plan lane was healthy) is the
birth receipt. Same grammar, new face:

    registry: configs/auth_tracks.yaml      (the named tracks)
    marker:   .mag_active_auth              (which track the seat rides)
    vault:    state/auth_switchboard/<ts>_<name>/   (byte snapshots + MANIFEST)
    trail:    memory/runs/auth_switchboard_trail.jsonl

Laws bound in:
  - secrets never echoed (fingerprints only, sha256[:12])
  - never edit own credentials -> `use` is GO-gated (typed RESTORE), and the
    operator runs it; seats run `status` and `snapshot` freely (reads + copies)
  - backup-first -> `use` auto-snapshots current state before restoring

CLI:
    python -m mag.auth_switchboard status [--all]
    python -m mag.auth_switchboard snapshot <name>
    python -m mag.auth_switchboard list
    python -m mag.auth_switchboard use <name>       # GO-gated, operator hand
    python -m mag.auth_switchboard trail [n]

Falsifier (live test vector 09-05): status MUST flag builtin:zai as FAIL
(vendor code 1000, dead key) while the coding-plan lanes read available; and a
snapshot -> mutate -> use roundtrip must restore sha256-identical files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

V2 = Path.home() / ".zcode" / "v2"
REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "configs" / "auth_tracks.yaml"
MARKER = REPO / ".mag_active_auth"
VAULT = REPO / "state" / "auth_switchboard"
TRAIL = REPO / "memory" / "runs" / "auth_switchboard_trail.jsonl"
AUTH_FILES = ["config.json", "setting.json", "credentials.json", "coding-plan-cache.json"]
PROBE_URL = "https://api.z.ai/api/anthropic/v1/models"
PROBE_HOSTS = {"api.z.ai"}  # fixed allowlist — probe target is a module constant, never user input


def _guard_probe_url(url: str) -> None:
    """SSRF fence: https-only, host allowlist, resolved IPs must be public."""
    from urllib.parse import urlparse
    import ipaddress
    import socket
    p = urlparse(url)
    if p.scheme != "https" or p.hostname not in PROBE_HOSTS:
        raise ValueError("probe host outside allowlist: %r" % (p.hostname,))
    for _fam, _typ, _proto, _canon, sa in socket.getaddrinfo(p.hostname, 443):
        ip = ipaddress.ip_address(sa[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("probe host resolved to non-public address: %s" % ip)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

SUPPORTED_FILES = ["builtin:zai", "builtin:bigmodel", "builtin:zai-coding-plan",
                   "builtin:zai-start-plan", "builtin:bigmodel-coding-plan", "builtin:bigmodel-start-plan"]


def fp(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12] if value else "-"


def jload(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def provider_table() -> list[dict]:
    cfg = jload(V2 / "config.json")
    provs = cfg.get("provider", {})
    rows = []
    for pid in SUPPORTED_FILES:
        p = provs.get(pid)
        if not isinstance(p, dict):
            continue
        key = (p.get("options") or {}).get("apiKey", "") or ""
        rows.append({
            "id": pid,
            "name": p.get("name", ""),
            "enabled": bool(p.get("enabled")),
            "has_key": bool(key),
            "key_fp": fp(key),
            "key_len": len(key),
            "baseURL": (p.get("options") or {}).get("baseURL", ""),
            "disabled_reason": p.get("systemDisabledReason", ""),
        })
    return rows


def probe_key(key: str) -> dict:
    """$0 read probe. Returns vendor verdict; never the key."""
    if not key:
        return {"ok": None, "detail": "no key (OAuth lane or empty)"}
    _guard_probe_url(PROBE_URL)
    req = urllib.request.Request(PROBE_URL, headers={
        "x-api-key": key, "Authorization": "Bearer " + key, "User-Agent": "mag-auth-switchboard/1"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=15) as r:
            raw = r.read()
        try:
            body = json.loads(raw.decode("utf-8", "replace"))
            if body.get("success") is False:
                return {"ok": False, "detail": "code=%s msg=%s" % (body.get("code"), str(body.get("msg", ""))[:60])}
            return {"ok": True, "detail": "HTTP 200, %dB body" % len(raw)}
        except json.JSONDecodeError:
            return {"ok": True, "detail": "HTTP 200, non-JSON %dB" % len(raw)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "detail": "HTTP %s" % e.code}
    except Exception as e:  # transport wall != auth verdict
        return {"ok": None, "detail": "transport: %s" % str(e)[:60]}


def plan_cache() -> dict:
    try:
        cache = jload(V2 / "coding-plan-cache.json")
        items = (cache.get("entryStatus") or {}).get("items", {})
        return {k: "%s%s" % (v.get("status"), " (%s)" % v["reason"] if v.get("reason") else "")
                for k, v in items.items()}
    except Exception as e:
        return {"error": str(e)[:60]}


def active_track() -> str:
    return MARKER.read_text(encoding="utf-8").strip() if MARKER.exists() else "(unmarked)"


def trail_row(event: str, **kw) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "event": event, **kw}
    with open(TRAIL, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def cmd_status(args):
    rows = provider_table()
    probes = {}
    for r in rows:
        if r["has_key"] and (r["enabled"] or args.all):
            key = (jload(V2 / "config.json")["provider"][r["id"]]["options"] or {}).get("apiKey", "")
            probes[r["id"]] = probe_key(key)
    plans = plan_cache()
    setting = jload(V2 / "setting.json")
    fam = setting.get("providerFamilyDomain", "?")
    fam_keys = setting.get("modelProviderFamilySelectedKeys", {})
    print("AUTH SWITCHBOARD STATUS  %s" % dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"))
    print("active track : %s" % active_track())
    print("family domain: %s  (updated %s)" % (
        fam, dt.datetime.fromtimestamp(setting.get("providerFamilyDomainUpdatedAt", 0) / 1000, dt.timezone.utc).strftime("%m-%d %H:%MZ")))
    print()
    print("PROVIDERS (v2/config.json)")
    for r in rows:
        state = "ENABLED " if r["enabled"] else "disabled"
        line = "  %-28s %s key=%s fp=%s len=%d" % (r["id"], state, "yes" if r["has_key"] else "no", r["key_fp"], r["key_len"])
        if r["disabled_reason"]:
            line += "  [%s]" % r["disabled_reason"]
        print(line)
        if r["id"] in probes:
            verdict = {True: "PASS", False: "FAIL", None: "?????"}[probes[r["id"]]["ok"]]
            print("      probe: %s  %s" % (verdict, probes[r["id"]]["detail"]))
    print()
    print("CODING-PLAN CACHE")
    for k, v in sorted(plans.items()):
        print("  %-34s %s" % (k, v))
    print()
    print("FAMILY SELECTED KEYS (setting.json)")
    for k, v in fam_keys.items():
        print("  %-10s fp=%s len=%d" % (k, fp(v), len(v)))
    print()
    dead = [r["id"] for r in rows if probes.get(r["id"], {}).get("ok") is False]
    if dead:
        print("VERDICT: DEAD LANE(S) ENABLED: %s" % ", ".join(dead))
        print("  way back A: point windows at the OAuth coding-plan provider (cache availability above)")
        print("  way back B: paste the live key from that account's dashboard, then: snapshot known_good")
    else:
        print("VERDICT: no enabled key lane failing (OAuth lanes + cache above)")
    trail_row("status", dead=dead)


def cmd_snapshot(args):
    name = re.sub(r"[^a-zA-Z0-9_.-]", "_", args.name)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = VAULT / ("%s_%s" % (ts, name))
    dest.mkdir(parents=True, exist_ok=True)
    manifest = {"ts": ts, "name": name, "files": {}, "providers": provider_table(),
                "plan_cache": plan_cache(), "family": jload(V2 / "setting.json").get("providerFamilyDomain", "?")}
    for fn in AUTH_FILES:
        src = V2 / fn
        if not src.exists():
            continue
        raw = src.read_bytes()
        (dest / fn).write_bytes(raw)
        manifest["files"][fn] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    MARKER.write_text(name, encoding="utf-8")
    print("[snapshot] %s" % dest)
    for fn, meta in manifest["files"].items():
        print("  %-24s %8d B  sha256:%s" % (fn, meta["bytes"], meta["sha256"][:12]))
    print("[marker] active track = %s" % name)
    trail_row("snapshot", name=name, dest=str(dest), files=list(manifest["files"]))


def cmd_list(args):
    if not VAULT.exists():
        print("(vault empty — run: python -m mag.auth_switchboard snapshot <name>)")
        return
    rows = sorted(p for p in VAULT.iterdir() if p.is_dir())
    for p in rows:
        mf = p / "MANIFEST.json"
        if mf.exists():
            m = jload(mf)
            dead = [r["id"] for r in m.get("providers", []) if r["enabled"] and r["has_key"] and r["key_len"] > 0]
            print("%s   family=%-8s providers=%d  %s" % (p.name, m.get("family", "?"), len(m.get("files", {})),
                                                         "note: had enabled key lanes: %s" % ",".join(dead) if dead else ""))
        else:
            print("%s   (no manifest)" % p.name)
    print("active track : %s" % active_track())


def cmd_use(args):
    snap = None
    for p in sorted(VAULT.iterdir(), reverse=True):
        if p.is_dir() and (p.name == args.name or p.name.endswith("_" + args.name)):
            snap = p
            break
    if snap is None:
        sys.exit("no snapshot matching %r — run 'list'" % args.name)
    m = jload(snap / "MANIFEST.json")
    print("RESTORE %s -> %s" % (snap.name, V2))
    for fn, meta in m["files"].items():
        cur = V2 / fn
        cur_sha = hashlib.sha256(cur.read_bytes()).hexdigest() if cur.exists() else None
        print("  %-24s vault sha256:%s -> current sha256:%s %s" % (
            fn, meta["sha256"][:12], cur_sha[:12] if cur_sha else "(missing)",
            "(identical)" if cur_sha == meta["sha256"] else "(DIFFERS)"))
    print("\nThis touches the seat's own credentials (never-edit-own-credentials law).")
    print("A safety snapshot of the CURRENT state is taken first (backup-first law).")
    answer = input('Type RESTORE to proceed: ').strip()
    if answer != "RESTORE":
        print("aborted — nothing written")
        return
    pre = cmd_snapshot(argparse.Namespace(name="pre_restore"))
    for fn in m["files"]:
        shutil.copy2(snap / fn, V2 / fn)
    print("[restored] %d files from %s" % (len(m["files"]), snap.name))
    print("[verify]   run: python -m mag.auth_switchboard status")
    trail_row("restore", snapshot=snap.name, safety_snapshot=str(pre))


def cmd_trail(args):
    n = args.n or 10
    if not TRAIL.exists():
        print("(trail empty)")
        return
    with open(TRAIL, encoding="utf-8") as f:
        for line in f.readlines()[-n:]:
            print(line.rstrip()[:220])


def main():
    ap = argparse.ArgumentParser(prog="mag.auth_switchboard")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status"); s.add_argument("--all", action="store_true"); s.set_defaults(fn=cmd_status)
    p = sub.add_parser("snapshot"); p.add_argument("name"); p.set_defaults(fn=cmd_snapshot)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    u = sub.add_parser("use"); u.add_argument("name"); u.set_defaults(fn=cmd_use)
    t = sub.add_parser("trail"); t.add_argument("n", nargs="?", type=int, default=10); t.set_defaults(fn=cmd_trail)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
