"""link_library — canonical URL registry so filed links stop duplicating.

The problem it kills: the same X post arrives as five different URLs
(?s=20 tracking params, t.co wrappers, mobile hosts) and each variant used
to become its own INTAKE_* file. Duplication is emphasis for humans; for
the ledger it is drift.

Canonicalization (v1):
  - lowercase scheme+host, strip default port, drop fragment
  - strip tracking params: s, si, utm_*, ref_src, ref_url, t, cn, mx, igsh, fbclid, gclid
  - sort remaining query params, drop empty values
  - x.com/twitter.com collapse to x.com; mobile.*/m.* hosts collapse to canonical host
  - drop trailing slash on empty path

Ledger: watch/inbox/LINKS.jsonl (append-only, one JSON object per line):
  {"seq", "ts", "canonical", "url", "canonical_sha256", "title", "duplicate_of", "writer", "note"}

Event schema split (B2-28, 2026-09-26): LINKS.jsonl holds link rows only going
forward. Scout/seat/endpoint-news event rows (id/kind/detail shape; 51 rows at
LINKS.jsonl lines 275-305 and 312-331) stay in place untouched per the
append-only law and are mirrored with provenance into watch/inbox/EVENTS.jsonl
(schema "event.v1"; every row carries "schema" plus "origin": {"file", "line"}
pointing at the LINKS.jsonl line it was copied from, plus the migration-marker
row at the LINKS.jsonl tail). New event filings go to EVENTS.jsonl via
load_events() as the parse path, never LINKS.jsonl.

2026-09-26 amendment (B2-26): hand-written bypass rows may carry the placeholder
canonical_sha256 "PENDING-URL". The sanctioned repair is a loud, receipted,
field-only backfill that replaces it with canonical_sha256(canonical): no other
field or byte may change on the touched lines, and the ledger is re-registered
(index event + INDEX.json) afterward. Receipt:
watch/inbox/burn_wave_20260926/B2_26_links_sha_backfill_20260926.md

x-post-source convention (B2-171, 2026-09-26): a filed row MAY carry two
different hosts by design -- canonical holds the RESOURCE (e.g.
https://arxiv.org/abs/2609.15983) while url holds the X/Twitter POST the
resource was surfaced from (e.g. https://x.com/omarsar0/status/...). 33 rows
on file use this shape (LINKS.jsonl:31 arxiv-vs-omarsar0 is the archetype).
This is NOT host drift: the convention is "canonical = what to open, url =
where it was found". The `convention` subcommand classifies every
canonical-vs-url host mismatch as either `x_post_source` (url host is an
X/Twitter family host, sanctioned shape) or `HOST_DRIFT` (any other mismatch,
real drift that needs a receipt), so the shape is named instead of lurking as
an unclassified anomaly.

Image-drop register (B2-172, 2026-09-26): LINKS.jsonl:256 is a THIRD schema
that cohabits the link ledger: canonical "image-drop:<filename>" with url
holding a repo-relative FILE path and canonical_sha256 = sha256 of the FILE
BYTES (not of the canonical string; proven for
fibonacci_determinants_plate_20260918.png, 2BD19E83594EF847F252A1397C23510D1
..., 2026-09-26). Per the B2-28 split-law shape, the class moves to its own
register watch/inbox/IMAGE_DROPS.jsonl (schema "image-drop.v1", rows carry
"origin": {"file", "line"} naming the LINKS.jsonl line they mirror; the
original line 256 stays in place untouched per the append-only law). New
image-drop filings go to IMAGE_DROPS.jsonl via load_image_drops(), never
LINKS.jsonl. `verify-images` re-hashes every registered file from bytes and
fails on any mismatch or missing file.

Scout check-gate (B2-27, 2026-09-26): agent writers (free-resource-scout and
every daily re-confirmation lane) file link rows ONLY through `add` — it runs
the same known-canonicals lookup as `check` and stamps duplicate_of at
submission time. Hand-appended rows bypass the gate; that is exactly how 5
silent duplicate clusters landed (scout re-confirmations of 2026-09-16/17
filings, triaged in watch/inbox/burn_wave_20260926/B2_06_link_dupes_20260926.md).
`check URL` stays the read-only pre-flight (exit 1 = already known);
check_url() is the library door so programmatic filers share one lookup.

CLI:
  python -m mag.link_library add URL [URL ...] [--note NOTE] [--writer WRITER]
  python -m mag.link_library check URL        # exit 1 if canonical already known
  python -m mag.link_library dupes            # show duplicate canonicals on file
  python -m mag.link_library convention       # classify canonical-vs-url host mismatches
  python -m mag.link_library verify-images    # re-hash image-drop register files
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "watch" / "inbox" / "LINKS.jsonl"
EVENTS = ROOT / "watch" / "inbox" / "EVENTS.jsonl"
IMAGE_DROPS = ROOT / "watch" / "inbox" / "IMAGE_DROPS.jsonl"

TRACKING_PARAMS = {
    "s", "si", "t", "cn", "mx", "igsh", "fbclid", "gclid", "ref_src", "ref_url",
    "ref", "source", "cmpid", "sgt", "sh", "hsmi", "hsenc", "mc_cid", "mc_eid",
    # the google-ads family (seen live on a filed URL 2026-09-16) + X's own
    "gad_source", "gad_campaignid", "gad_position", "gad_bidmatch", "gbraid",
    "wbraid", "gclsrc", "dclid", "twclid",
}
HOST_COLLAPSE = {
    "twitter.com": "x.com",
    "mobile.x.com": "x.com",
    "m.x.com": "x.com",
}


def canonicalize(url: str) -> str:
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"only http/https allowed: {url!r}")
    host = parsed.netloc.lower()
    if "@" in host:  # strip userinfo, never valid in filed links
        host = host.rsplit("@", 1)[1]
    if ":" in host:
        host, port = host.rsplit(":", 1)
        if port == ("443" if parsed.scheme == "https" else "80"):
            pass
        else:
            host = f"{host}:{port}"
    host = HOST_COLLAPSE.get(host, host)
    path = parsed.path.rstrip("/") if parsed.path.rstrip("/") == "" or parsed.path.endswith("/") else parsed.path
    params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False)
              if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")]
    params.sort()
    query = urlencode(params)
    return urlunparse((parsed.scheme, host, path, "", query, ""))


def canonical_sha256(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()


def load_ledger() -> list[dict]:
    if not LEDGER.is_file():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def known_canonicals() -> dict[str, dict]:
    """Canonical -> EARLIEST filed ledger row (B2-122, 2026-09-26).

    First filing wins: the ledger is append-only with monotonic seq, so the
    first occurrence in file order IS the earliest filing. The previous
    last-writer-wins dict comprehension made check_url.first_entry and the
    add_urls duplicate_of stamp point at the NEWEST dupe row instead of the
    original filing (live proof 2026-09-26: a thundercompute check returned
    the dupe-triage row seq 1790422309734386 over the 09-16 original seq
    1789484000012; cause and evidence named here per the fix-comment law).
    """
    known: dict[str, dict] = {}
    for e in load_ledger():
        canon = e.get("canonical")
        if canon and canon not in known:
            known[canon] = e
    return known


def check_url(url: str) -> dict:
    """Submission-time duplicate gate (B2-27, 2026-09-26).

    The one lookup every filing path runs before a row lands: canonicalize and
    answer whether the canonical is already on the ledger, carrying the first
    entry when it is. The `check` CLI prints this; `add_urls` runs the same
    known-canonicals map to stamp duplicate_of at submission. The free-resource
    scout's daily re-confirmations used to bypass this door and land as silent
    unflagged dupes (5 clusters, B2-06 triage 2026-09-26); the law above makes
    `add` the only filing door and this the shared pre-flight.
    """
    validate_host_safety(url)
    canon = canonicalize(url)
    hit = known_canonicals().get(canon)
    return {"canonical": canon, "known": bool(hit), "first_entry": hit}


def load_events() -> list[dict]:
    """Read the split-out event ledger (B2-28 schema split, 2026-09-26).

    Rows self-describe via "schema": "event.v1" plus an "origin" block
    (SCOUT_CHARTER_20260926.md section 1); this is the single parse path for
    watch/inbox/EVENTS.jsonl and it refuses schema-less rows so the split
    cannot rot back into undocumented LINKS.jsonl cohabitation. No-erase
    backfill (charter section 4, 2026-09-29): a schema-less row is never
    edited, so its repair is an appended carrier row whose origin names it
    (origin.file = watch/inbox/EVENTS.jsonl, origin.line, origin.replaces =
    its id). Cause: 5 schema-less rows at lines 54-58 (f-05 census 2026-09-28)
    made the single-pass door raise, serving 0 of 58 rows fail-closed. Two
    passes: pass 1 json-parses every line (malformed JSON still raises) and
    collects ids named by origin.replaces; pass 2 raises on every contract
    breach EXCEPT those named ids - accepted debt by name (ratchet pattern),
    skipped from the served list, bytes intact in the file. Receipt:
    watch/inbox/wave5_repair/events-door.md.
    """
    if not EVENTS.is_file():
        return []
    parsed = []
    replaced: set[str] = set()
    for line in EVENTS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            parsed.append(row)
            origin = row.get("origin")
            if (row.get("schema") == "event.v1" and isinstance(origin, dict)
                    and isinstance(origin.get("replaces"), str) and origin["replaces"]):
                replaced.add(origin["replaces"])
    out = []
    for row in parsed:
        if row.get("schema") != "event.v1" or not isinstance(row.get("origin"), dict):
            if row.get("id") in replaced:
                continue
            raise ValueError(
                f"EVENTS.jsonl row missing schema=event.v1 or origin block: {row.get('id', '?')}")
        out.append(row)
    return out


X_SOURCE_HOSTS = {"x.com", "twitter.com", "mobile.x.com", "m.x.com", "t.co"}


def load_image_drops() -> list[dict]:
    """Read the image-drop register (B2-172, 2026-09-26).

    Image-drop rows (canonical "image-drop:<name>", url = repo-relative file
    path, canonical_sha256 = sha256 of the file bytes) live in
    watch/inbox/IMAGE_DROPS.jsonl, each row self-describing via
    "schema": "image-drop.v1" plus an "origin" block naming the LINKS.jsonl
    line it was mirrored from. The seed row mirrors LINKS.jsonl:256
    (fibonacci_determinants_plate_20260918.png). This is the single parse
    path for the register and it refuses schema-less or origin-less rows so
    the third schema cannot keep cohabiting LINKS.jsonl silently.
    """
    if not IMAGE_DROPS.is_file():
        return []
    out = []
    for line in IMAGE_DROPS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            row = json.loads(line)
            if row.get("schema") != "image-drop.v1" or not isinstance(row.get("origin"), dict):
                raise ValueError(
                    f"IMAGE_DROPS.jsonl row missing schema=image-drop.v1 or origin block: "
                    f"{row.get('canonical', '?')}")
            out.append(row)
    return out


def verify_image_drops() -> dict:
    """Re-hash every image-drop file from bytes (B2-172 verifier).

    For each register row: resolve row["url"] against ROOT, hash the file
    bytes, and compare to row["canonical_sha256"] (the register's contract:
    that field hashes FILE BYTES for this class, unlike link rows where it
    hashes the canonical string). Missing files and mismatches are named
    rows, never silent.
    """
    results = []
    ok = True
    for row in load_image_drops():
        rel = str(row.get("url") or "")
        path = ROOT / rel
        expected = str(row.get("canonical_sha256") or "")
        if not path.is_file():
            ok = False
            results.append({"canonical": row.get("canonical"), "file": rel,
                            "status": "MISSING"})
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        match = actual == expected
        ok = ok and match
        results.append({"canonical": row.get("canonical"), "file": rel,
                        "status": "OK" if match else "MISMATCH",
                        "expected": expected, "actual": actual})
    return {"ok": ok, "rows": results}


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def classify_host_mismatch(entry: dict) -> str:
    """Classify a canonical-vs-url host mismatch (B2-171, 2026-09-26).

    Returns "x_post_source" when url sits on an X/Twitter family host while
    canonical holds the real resource (the filed convention, 33 rows on
    ledger), "match" when hosts agree, and "HOST_DRIFT" for any other
    cross-host row -- the drift case that needs a receipt instead of a shrug.
    """
    canon, url = str(entry.get("canonical") or ""), str(entry.get("url") or "")
    if not canon or not url:
        return "match"
    ch, uh = _host(canon), _host(url)
    if ch == uh:
        return "match"
    if uh in X_SOURCE_HOSTS and ch not in X_SOURCE_HOSTS:
        return "x_post_source"
    return "HOST_DRIFT"


def convention_report() -> dict:
    """Scan the ledger and split host mismatches into sanctioned shape vs drift."""
    counts = {"match": 0, "x_post_source": 0, "HOST_DRIFT": 0}
    drift_rows: list[dict] = []
    xpost_rows: list[dict] = []
    for entry in load_ledger():
        verdict = classify_host_mismatch(entry)
        counts[verdict] += 1
        if verdict == "HOST_DRIFT":
            drift_rows.append({"seq": entry.get("seq"), "canonical": entry.get("canonical"),
                               "url": entry.get("url")})
        elif verdict == "x_post_source":
            xpost_rows.append({"seq": entry.get("seq"), "canonical": entry.get("canonical"),
                               "url": entry.get("url")})
    return {"counts": counts, "x_post_source": xpost_rows, "host_drift": drift_rows}


def validate_host_safety(url: str) -> None:
    """Mimosa guard: http/https only; refuse localhost/loopback/private/reserved."""
    host = urlparse(url).hostname or ""
    if not host:
        raise ValueError(f"no host: {url!r}")
    if host in ("localhost",) or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError(f"refusing local host: {host}")
    if re.match(r"^(10\.|127\.|0\.|169\.254\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)", host):
        raise ValueError(f"refusing private/reserved host: {host}")
    if host in ("metadata.google.internal", "169.254.169.254"):
        raise ValueError(f"refusing metadata host: {host}")


def add_urls(urls: list[str], note: str = "", writer: str = "link_library") -> list[dict]:
    known = known_canonicals()
    results = []
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as handle:
        for url in urls:
            validate_host_safety(url)
            canon = canonicalize(url)
            sha = canonical_sha256(canon)
            entry = {
                "seq": int(time.time() * 1000_000) + len(results),
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                "canonical": canon,
                "url": url,
                "canonical_sha256": sha,
                "title": "",
                "duplicate_of": "",
                "writer": writer,
                "note": note,
            }
            if canon in known:
                entry["duplicate_of"] = known[canon].get("url", canon)
            known[canon] = entry
            handle.write(json.dumps(entry) + "\n")
            results.append(entry)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m mag.link_library")
    parser.add_argument("command",
                        choices=("add", "check", "dupes", "convention", "verify-images"))
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--note", default="")
    parser.add_argument("--writer", default="link_library")
    args = parser.parse_args()

    if args.command == "add":
        if not args.urls:
            parser.error("add requires at least one URL")
        for entry in add_urls(args.urls, note=args.note, writer=args.writer):
            flag = "DUPLICATE" if entry["duplicate_of"] else "REGISTERED"
            print(f"{flag}: {entry['canonical']}")
        return 0
    if args.command == "check":
        if len(args.urls) != 1:
            parser.error("check requires exactly one URL")
        verdict = check_url(args.urls[0])
        print(json.dumps(verdict, indent=1))
        return 1 if verdict["known"] else 0
    if args.command == "dupes":
        seen: dict[str, str] = {}
        dupes = 0
        for entry in load_ledger():
            if entry.get("duplicate_of"):
                dupes += 1
                print(f"{entry['url']}  ->  {entry['duplicate_of']}")
        print(f"{dupes} duplicate submissions on file")
        return 0
    if args.command == "convention":
        report = convention_report()
        print(json.dumps(report["counts"], indent=1))
        for row in report["x_post_source"]:
            print(f"x_post_source: {row['canonical']}  <-  {row['url']}")
        for row in report["host_drift"]:
            print(f"HOST_DRIFT: {row['canonical']}  vs  {row['url']}")
        return 1 if report["counts"]["HOST_DRIFT"] else 0
    if args.command == "verify-images":
        verdict = verify_image_drops()
        for row in verdict["rows"]:
            print(f"{row['status']}: {row['canonical']} ({row['file']})")
            if row["status"] == "MISMATCH":
                print(f"  expected {row['expected']}")
                print(f"  actual   {row['actual']}")
        print(f"{len(verdict['rows'])} image-drop rows checked")
        return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
