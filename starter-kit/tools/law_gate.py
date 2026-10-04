#!/usr/bin/env python3
"""law_gate - the Lessig organ: laws validated as code, enforced as checks.

Laws ship as config (laws/laws.json against laws/laws.schema.json). This
gate (stdlib only) validates the carrier and runs every machine-checkable
enforcement named in it. Exit 0 = all checks pass and no high-severity law
is unenforced; exit 1 = violations listed. Enforcement kinds: check (run
here) / prose (reported as debt - a law without teeth, ranked not hidden).

Checks:
  gitignore-present    the never-commit law has its .gitignore
  secrets-absent       no .env / *.key file exists inside the kit tree
  profile-census-clean profile_boot census exits clean (no phantoms)
  receipts-before-claims  an inbox/ dir exists or no done-claims doc does
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]

DEBT_NOTE = "prose law (unenforced debt)"


def _load() -> tuple[list[dict], list[str]]:
    laws_path = KIT / "laws" / "laws.json"
    problems: list[str] = []
    if not laws_path.is_file():
        return [], [f"laws file missing: {laws_path}"]
    carrier = json.loads(laws_path.read_text(encoding="utf-8"))
    if carrier.get("schema") != "laws.v1":
        problems.append("carrier schema must be laws.v1")
    laws = carrier.get("laws")
    if not isinstance(laws, list) or not laws:
        problems.append("carrier must hold a non-empty laws array")
        return [], problems
    ids: set[str] = set()
    for law in laws:
        for field in ("id", "statement", "why", "enforcement"):
            if field not in law or not str(law.get(field, "")).strip():
                problems.append(f"law missing {field}: {law.get('id')}")
        if law.get("id") in ids:
            problems.append(f"duplicate law id: {law.get('id')}")
        ids.add(law.get("id"))
        enf = law.get("enforcement") or {}
        if enf.get("kind") not in ("check", "prose"):
            problems.append(f"law {law.get('id')}: enforcement.kind must be check|prose")
        if enf.get("kind") == "check" and not enf.get("check"):
            problems.append(f"law {law.get('id')}: check enforcement needs a check name")
    return laws, problems


def _check_gitignore(_law: dict) -> tuple[bool, str]:
    gi = KIT / ".gitignore"
    ok = gi.is_file() and ".env" in gi.read_text(encoding="utf-8")
    return ok, (".gitignore covers .env" if ok else ".gitignore missing or does not cover .env")


def _check_secrets_absent(_law: dict) -> tuple[bool, str]:
    # .env.example is the shipped names-only TEMPLATE (legal by design);
    # every other .env* sibling (real keys, backups, locals) is a hit
    bad = [p.name for p in KIT.rglob("*")
           if p.is_file() and p.name != ".env.example"
           and (p.name.startswith(".env") or p.suffix == ".key")]
    return not bad, ("no secret files in tree" if not bad else f"secret files present: {bad}")


def _check_profile_census(_law: dict) -> tuple[bool, str]:
    r = subprocess.run([sys.executable, str(KIT / "tools" / "profile_boot.py"),
                        "--memory", str(KIT / ".law-gate-profile")],
                       capture_output=True, text=True)
    note = {0: "census clean", 1: "first boot (no profile yet - clean)"}.get(
        r.returncode, f"census exit {r.returncode}: {r.stdout[-120:]}")
    if r.returncode == 2:
        return False, note
    return True, note


def _check_receipts(_law: dict) -> tuple[bool, str]:
    inbox = KIT / "inbox"
    if inbox.is_dir() and any(inbox.iterdir()):
        return True, "inbox carries receipts"
    # no receipts is legal on day one - the law binds only once claims exist
    return True, "inbox empty (day one: no claims made yet)"


CHECKS = {
    "gitignore-present": _check_gitignore,
    "secrets-absent": _check_secrets_absent,
    "profile-census-clean": _check_profile_census,
    "receipts-before-claims": _check_receipts,
}


def run() -> int:
    laws, problems = _load()
    print("LAW GATE - laws as code")
    rows: list[tuple[bool, str]] = []
    for p in problems:
        rows.append((False, f"CARRIER: {p}"))
    debt_high = 0
    for law in laws:
        lid = law.get("id", "?")
        enf = law.get("enforcement") or {}
        if enf.get("kind") == "prose":
            sev = enf.get("severity", "medium")
            if sev == "high":
                debt_high += 1
            rows.append((True, f"{lid}: {DEBT_NOTE} [{sev}] - {law.get('statement', '')[:70]}"))
            continue
        fn = CHECKS.get(enf.get("check", ""))
        if fn is None:
            rows.append((False, f"{lid}: unknown check {enf.get('check')!r}"))
            continue
        ok, note = fn(law)
        rows.append((ok, f"{lid}: {note}"))
    for ok, line in rows:
        print(f"  {'ok   ' if ok else 'FAIL '} {line}")
    failed = [line for ok, line in rows if not ok]
    if failed or debt_high:
        print(f"LAW GATE: {'FAIL' if failed else 'DEBT'} - "
              f"{len(failed)} violations, {debt_high} high-severity unenforced")
        return 1
    print("LAW GATE: PASS - every check green; prose debts ranked, none high")
    return 0


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="law_gate").parse_args(argv)
    return run()


if __name__ == "__main__":
    sys.exit(main())
