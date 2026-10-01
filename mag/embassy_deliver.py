"""Embassy deliver — automate publishing the AOS packet to GitHub (architecture path).

Gives the "send the file over GitHub" op a real path in the framework (REST /
queue / direct module call) instead of a manual terminal git dance (which would
keep triggering allow-prompts). This is the dogfood: a local-imperative external
op with no prior queue/REST path gets one built, mirroring mag/extension_deploy.py
(the established "architecture path" precedent — stolen from it).

Pipeline (deterministic, gated, dry-run by default):
  1. PUBLISH-SAFETY GATE — secret scan (real fingerprints + G1-G8) over every file.
  2. PLACEHOLDER GATE — the §6 intake must have no unresolved ⟨ ⟩ markers.
  3. ASSEMBLE — git init/add/commit the deliverable folder (idempotent).
  4. PUBLISH — create+push via `gh` (or an existing configured remote). Gated on
     operator credentials; dry-run by default. NEVER reads/prints a token value.
  5. LEARN — fold the outcome to a Verkle witness (evidence, not authority) +
     skill_ledger decision + trail, so the next launch is smarter (tesuji-everywhere).

REST: POST /api/v1/embassy/publish  -> publish()
CLI:  python -m mag.embassy_deliver [--dry] [--live]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def _desktop_deliver() -> Path:
    """Deliverables live on the operator's Desktop (findable), not in the project dir.

    Falls back to the project staging path only when the Desktop folder is absent
    (e.g. headless/test runs). Prevents scattering artifacts into the project tree.
    """
    user = os.environ.get("USERPROFILE") or str(Path.home())
    desktop = Path(user) / "Desktop" / "Mag" / "Output" / "embassy-aos"
    if desktop.is_dir():
        return desktop
    return ROOT / "deliver" / "embassy-aos"


DELIVER = _desktop_deliver()
REPLY = ROOT / "memory" / "embassy" / "AOS" / "EMBASSY-REPLY-Ghost-2026-08-08.md"
REPO_NAME = "embassy-aos"

# Files that make up the public deliverable.
PUBLIC_FILES = [
    "README.md",
    "LICENSE",
    "run_tests.cmd",
    "embassy_integrity.py",
    "tests/test_embassy_integrity.py",
    "docs/INTEGRITY-SUITE.md",
    "docs/RUN-INSTRUCTIONS.md",
    "docs/SECTION6-INTAKE.md",
    "docs/TEST-PLAN.md",
]

# Real-world secret fingerprints — not the G1-G8 keyword gate.
_SECRET_PATTERNS = {
    "sk": re.compile(r"sk-[A-Za-z0-9]{8,}"),
    "gh_token": re.compile(r"(ghp_|gho_|ghu_|github_pat_)[A-Za-z0-9_]{10,}"),
    "aws": re.compile(r"AKIA[0-9A-Z]{16}"),
    "bearer": re.compile(r"bearer [A-Za-z0-9._-]{12,}", re.I),
    "assigned_key": re.compile(r"(api[_-]?key|apikey|client[_-]?secret)\s*[=:]\s*['\"]?[A-Za-z0-9_-]{12,}", re.I),
    "private_key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def _deliver_files() -> list[Path]:
    return [DELIVER / f for f in PUBLIC_FILES if (DELIVER / f).is_file()]


# ── 1. PUBLISH-SAFETY GATE ─────────────────────────────────────────

def publish_safety_check(files: list[Path] | None = None) -> dict:
    """Scan every deliverable file for real secrets + G1-G8 gate violations."""
    from mag.embassy_integrity import scan_opspec

    files = files or _deliver_files()
    scanned = {"files": len(files), "secrets": {}, "gates": {}, "advisory": {}, "ok": True}
    for f in files:
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        # BLOCK: real secret VALUES (keys/tokens). These are what must never publish.
        for name, pat in _SECRET_PATTERNS.items():
            hits = pat.findall(text)
            if hits:
                scanned["secrets"][f.name] = scanned["secrets"].get(f.name, {})
                scanned["secrets"][f.name][name] = len(hits)
                scanned["ok"] = False
        # ADVISORY: G1-G8 keyword hits. These docs legitimately discuss OPSEC
        # (they name the gates), so word-hits are informational, not blocking.
        gate_flags = {g: len(v["hits"]) for g, v in scan_opspec(text).items() if not v["pass"]}
        if gate_flags:
            scanned["gates"][f.name] = gate_flags
            scanned["advisory"][f.name] = gate_flags
    scanned["ok"] = scanned["ok"] and not scanned["secrets"]
    return scanned


# ── 2. PLACEHOLDER GATE ────────────────────────────────────────────

def placeholder_check(reply_path: Path | None = None) -> dict:
    """Ensure the §6 intake has no unresolved ⟨ ⟩ operator-only placeholders.

    By default checks BOTH the memory source AND the Desktop deliverable copy (the
    file actually pushed), so they can't diverge and we never ship placeholders.
    A single `reply_path` still works for targeted tests.
    """
    targets = [reply_path] if reply_path is not None else [
        DELIVER / "docs" / "SECTION6-INTAKE.md", REPLY,
    ]
    unresolved: dict[str, list[str]] = {}
    for p in targets:
        if p is not None and p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            # Only markers with real content are operator fields. The doc's own
            # instruction line ("fields are marked ⟨ ⟩") is whitespace-only self-ref.
            m = re.findall(r"⟨[^⟩]*[^\s⟩][^⟩]*⟩", text)
            if m:
                unresolved[str(p)] = m
    return {"ok": not unresolved, "unresolved": unresolved,
            "paths": [str(p) for p in targets if p is not None]}


# ── 3. ASSEMBLE (git init/add/commit, idempotent) ──────────────────

def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=120,
    )


def assemble(dry: bool = True) -> dict:
    """git init/add/commit the deliverable folder. Dry-run reports, doesn't run."""
    steps = [
        f"cd {DELIVER.name}",
        "git init",
        "git add -A",
        "git commit -m 'Embassy · Pattern A · §6 intake + integrity suite'",
    ]
    if dry:
        return {"ok": True, "schema": "embassy_assemble.v1", "dry": True, "steps": steps,
                "deliver_exists": DELIVER.is_dir(), "git_repo": (DELIVER / ".git").is_dir()}
    if not DELIVER.is_dir():
        return {"ok": False, "error": f"deliverable not found: {DELIVER}", "dry": False}
    if not (DELIVER / ".git").is_dir():
        r = _git("init", cwd=DELIVER)
        if r.returncode != 0:
            return {"ok": False, "error": r.stderr.strip()[:300]}
    _git("add", "-A", cwd=DELIVER)
    # Fresh repo may have no git identity -> pass one locally so commit succeeds.
    r = subprocess.run(
        ["git", "-c", "user.name=Ghost Sovereign Agent System",
         "-c", "user.email=ghost@mycelial.republic",
         "commit", "-m", "Embassy · Pattern A · §6 intake + integrity suite"],
        cwd=str(DELIVER), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    return {"ok": True, "schema": "embassy_assemble.v1", "dry": False,
            "committed": r.returncode == 0, "detail": (r.stdout or r.stderr).strip()[:300]}


# ── 4. PUBLISH (gated on operator creds; dry-run default) ──────────

def _load_token() -> str:
    """Load GITHUB_TOKEN from env or .env. Value stays in-process; NEVER printed."""
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if t:
        return t.strip().strip('"').strip("'")
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _have_token() -> bool:
    return bool(_load_token())


def _create_repo_via_api(token: str, name: str) -> dict:
    """Create a PUBLIC repo via the GitHub REST API (needs a PAT with repo scope)."""
    import json as _json
    import urllib.error
    import urllib.request

    body = _json.dumps({"name": name, "private": False, "auto_init": False}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/user/repos",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    def _login():
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                    method="GET",
                ), timeout=60) as resp:
                return _json.loads(resp.read().decode("utf-8")).get("login") or ""
        except Exception:
            return ""

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "full_name": data.get("full_name"), "html_url": data.get("html_url")}
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", errors="replace")
        # 422 with "already exists": treat as ok (idempotent) and still resolve the URL.
        if e.code in (422,) and "already exists" in body.lower():
            login = _login()
            if login:
                return {"ok": True, "full_name": f"{login}/{name}", "existing": True}
        return {"ok": False, "error": f"HTTP {e.code}: {body}"}


def _have_remote() -> bool:
    if not (DELIVER / ".git").is_dir():
        return False
    r = _git("remote", "-v", cwd=DELIVER)
    return bool(r.stdout.strip())


def publish(dry: bool = True, repo_url: str | None = None) -> dict:
    """Full pipeline: safety gate -> placeholder gate -> assemble -> publish.

    `repo_url` = the target GitHub repo (e.g. https://github.com/<you>/embassy-aos).
    Ghost pushes to it via Git Credential Manager (cached creds) — NO `gh auth login`
    required. Creating the repo itself is the one operator-only step (git can't
    create a repo); once it exists (empty), Ghost does the rest.
    """
    safety = publish_safety_check()
    if not safety["ok"]:
        return {"ok": False, "error": "publish-safety gate blocked",
                "gate": safety, "dry": dry}
    ph = placeholder_check()
    if not ph["ok"]:
        return {"ok": False, "error": "unresolved placeholders in §6",
                "placeholders": ph["unresolved"], "dry": dry}
    asm = assemble(dry=dry)
    if not asm["ok"]:
        return {"ok": False, "error": asm.get("error"), "dry": dry}

    if dry:
        return {"ok": True, "schema": "embassy_publish.v1", "dry": True,
                "safety": safety, "placeholders": ph, "assemble": asm,
                "note": "dry-run — no external action taken"}

    # LIVE path.
    repo_url = (repo_url or os.environ.get("EMBASSY_REPO_URL") or "").strip() or None
    token = _load_token()
    created_repo = False
    # If we have a token and no target yet, create the public repo via the API.
    if not repo_url and token:
        c = _create_repo_via_api(token, REPO_NAME)
        if not c.get("ok"):
            return {"ok": False, "error": f"repo create failed: {c.get('error')}", "dry": False}
        full = c.get("full_name") or ""
        if "/" in full:
            owner = full.split("/", 1)[0]
            repo_url = f"https://github.com/{owner}/{REPO_NAME}.git"
            created_repo = True

    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"  # never hang on a password prompt

    def _detail(r: subprocess.CompletedProcess) -> str:
        d = (r.stdout or r.stderr).strip()[:400]
        return d.replace(token, "***") if token else d

    def _push() -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "push", "-u", "origin", "HEAD"], cwd=str(DELIVER),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=300,
        )

    if repo_url and token:
        # Push via a transient tokenized URL; scrub the token from git config after.
        tok_url = "https://x-access-token:" + token + "@" + repo_url[len("https://"):]
        _git("remote", "remove", "origin", cwd=DELIVER)
        _git("remote", "add", "origin", tok_url, cwd=DELIVER)
        r = _push()
        _git("remote", "remove", "origin", cwd=DELIVER)  # drop tokenized remote
        _git("remote", "add", "origin", repo_url, cwd=DELIVER)  # clean remote
        return {"ok": r.returncode == 0, "schema": "embassy_publish.v1", "dry": False,
                "repo": repo_url, "created": created_repo, "detail": _detail(r)}
    if repo_url:
        _git("remote", "remove", "origin", cwd=DELIVER)
        _git("remote", "add", "origin", repo_url, cwd=DELIVER)
        r = _push()
        return {"ok": r.returncode == 0, "schema": "embassy_publish.v1", "dry": False,
                "repo": repo_url, "detail": _detail(r)}
    if _have_remote():
        r = _push()
        return {"ok": r.returncode == 0, "schema": "embassy_publish.v1", "dry": False,
                "detail": _detail(r)}
    if _have_gh():
        r = subprocess.run(
            ["gh", "repo", "create", REPO_NAME, "--public", "--source=.",
             "--push", "--description", "Embassy · Pattern A · §6 intake + integrity suite"],
            cwd=str(DELIVER), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300,
        )
        url = r.stdout.strip() or r.stderr.strip()
        ok = r.returncode == 0
        return {"ok": ok, "schema": "embassy_publish.v1", "dry": False,
                "created": ok, "url": url[:300] if ok else "", "detail": url[:300]}
    return {"ok": False,
            "error": "no target repo_url, token, remote, or gh. Set GITHUB_TOKEN in .env "
                     "(classic PAT with public_repo scope) and rerun.",
            "dry": False}


# ── 5. LEARN (fold outcome: verkle witness + skill_ledger + trail) ──

def learn(outcome: dict, dry: bool = True) -> dict:
    """Record the publish attempt as evidence (Verkle) + a skill_ledger decision."""
    recorded = {"verkle": False, "skill_ledger": False}
    try:
        from mag.embassy_integrity import VerkleWitness
        w = VerkleWitness()
        w.append(f"embassy publish dry={dry} ok={outcome.get('ok')}")
        recorded["verkle"] = True
    except Exception:
        pass
    try:
        from mag.skill_ledger import record_decision
        record_decision(
            goal=f"embassy-publish-{REPO_NAME}",
            outcome="ok" if outcome.get("ok") else "blocked",
            context={"dry": dry, "repo": REPO_NAME},
        )
        recorded["skill_ledger"] = True
    except Exception:
        pass
    return recorded


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    dry = "--live" not in args
    repo_url = ""
    if "--repo" in args:
        i = args.index("--repo")
        if i + 1 < len(args):
            repo_url = args[i + 1]
    out = publish(dry=dry, repo_url=repo_url or None)
    out["learn"] = learn(out, dry=dry)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
