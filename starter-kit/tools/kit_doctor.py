#!/usr/bin/env python3
"""kit_doctor - environment check for the starter kit (any system, stdlib).

Verifies what the kit needs to run where it stands: python version, git,
an assistant harness hint, the kit's own files, and whether the profile
organ responds. Exit 0 = kit is live; exit 1 = gaps listed with the fix.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]


def check() -> tuple[list[str], list[str]]:
    ok, missing = [], []

    ok.append(f"python {sys.version.split()[0]} on {platform.system()} "
              "(stdlib-only kit: no pip installs required)")
    if sys.version_info < (3, 9):
        missing.append("python >= 3.9 required")

    if shutil.which("git"):
        r = subprocess.run(["git", "--version"], capture_output=True,
                           text=True)
        ok.append(r.stdout.strip())
    else:
        missing.append("git missing - install from https://git-scm.com "
                       "(or your phone's package manager); you will also "
                       "want a free GitHub account: https://github.com/signup")

    for doc in ("README.md", "BOOT.md", "LAWS.md", "PROTOCOLS.md",
                "SUBSYSTEMS.md"):
        if (KIT_ROOT / doc).is_file():
            ok.append(f"doc present: {doc}")
        else:
            missing.append(f"doc missing: {doc} (re-download the kit)")

    # the profile organ responds (clean-boot semantics)
    selftest = KIT_ROOT / ".profile-selftest"
    r = subprocess.run(
        [sys.executable, str(KIT_ROOT / "tools" / "profile_boot.py"),
         "--memory", str(selftest)],
        capture_output=True, text=True)
    if r.returncode in (0, 1):  # 1 = first boot = the organ works
        ok.append("profile_boot: responds (exit "
                  f"{r.returncode}, {'first boot created the shape' if r.returncode == 1 else 'profile found'})")
    else:
        missing.append(f"profile_boot broken (exit {r.returncode}): "
                       f"{r.stdout[-200:]} {r.stderr[-200:]}")
    # tidy the selftest dir it created
    p = KIT_ROOT / ".profile-selftest"
    if p.is_dir():
        import shutil as _sh
        _sh.rmtree(p)
    return ok, missing


def main() -> int:
    print("STARTER KIT DOCTOR")
    ok, missing = check()
    for line in ok:
        print(f"  ok    {line}")
    for line in missing:
        print(f"  MISS  {line}")
    if missing:
        print("kit not fully live - fix the MISS lines (setup/install.sh "
              "or setup/install.ps1 fetches the free stuff).")
        return 1
    print("kit is live. Next: python tools/profile_boot.py (first boot), "
          "then tutorial/TUTORIAL.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
