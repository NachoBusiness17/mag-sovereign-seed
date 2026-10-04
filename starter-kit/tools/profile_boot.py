#!/usr/bin/env python3
"""profile_boot - the clean-boot organ (any system, stdlib only).

Reaches for the user profile at session start; if none exists, creates the
empty shape and says so plainly (FIRST BOOT - the designed state). Exit
codes: 0 profile found, 1 first boot (created empty shape), 2 corrupt
(phantom index rows - run the census before trusting recall).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# windows consoles default to a non-utf8 codepage; the brief must not crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEADER = (
    "# Memory Index\n\n"
    "# One line per fact, shaped like:  - Title -> file.md - the hook\n"
    "# (a real markdown link once the file exists; under ~200 chars a line)\n"
    "# Topic files carry the detail; this index is the only always-loaded\n"
    "# surface. Never store what a repo or transcript already records.\n"
)

# exit contract (50-wide dogfood fix): 0 found / 1 FIRST BOOT (the designed
# empty state) / 2 corrupt (phantoms) / 3 crash (anything unexpected). The
# doctor and integration docs key on the difference: a crash must never
# wear first-boot's clothes.
EXIT_FOUND, EXIT_FIRST_BOOT, EXIT_CORRUPT, EXIT_CRASH = 0, 1, 2, 3


def _inside(memory_dir: Path, target: str) -> bool:
    """Traversal law: an index row may only point INSIDE the memory dir.
    A pasted row pointing elsewhere must not pull foreign files into the
    always-loaded boot brief."""
    try:
        (memory_dir / target).resolve().relative_to(memory_dir.resolve())
        return True
    except ValueError:
        return False


def boot(memory_dir: Path) -> int:
    if memory_dir.exists() and not memory_dir.is_dir():
        print("CRASH: memory path exists but is not a directory")
        return EXIT_CRASH
    index = memory_dir / "MEMORY.md"
    if not index.is_file():
        try:
            memory_dir.mkdir(parents=True, exist_ok=True)
            index.write_text(HEADER, encoding="utf-8")
        except OSError as e:
            print(f"CRASH: cannot create the profile shape: {e}")
            return EXIT_CRASH
        print("FIRST BOOT: no profile found. Created the empty shape at")
        print(f"  {index}")
        print("Start the mining loop (agent/conversation-miner card): bank")
        print("corrections as feedback, identity as user, settled things as")
        print("project. Append one index line per topic file, same session.")
        return EXIT_FIRST_BOOT

    text = index.read_text(encoding="utf-8", errors="ignore")
    rows = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
    outside = [f for _t, f in rows if not _inside(memory_dir, f)]
    missing = [f for _t, f in rows
               if _inside(memory_dir, f)
               and not (memory_dir / f).is_file()]
    if outside:
        print("CORRUPT: index rows point OUTSIDE the memory dir "
              "(traversal law):")
        for f in outside[:10]:
            print(f"  {f}")
        return EXIT_CORRUPT
    print(f"PROFILE: {len(rows)} index rows, {len(rows) - len(missing)} "
          f"live, {len(missing)} phantom")
    if missing:
        print("CORRUPT: phantom rows (targets missing) - census before "
              "trusting recall:")
        for f in missing[:10]:
            print(f"  {f}")
        return EXIT_CORRUPT
    # the boot brief: every topic file's frontmatter description
    brief = []
    for _t, f in rows:
        p = memory_dir / f
        if p.is_file():
            m = re.search(r"^description:\s*(.+)$",
                          p.read_text(encoding="utf-8", errors="ignore"),
                          re.MULTILINE)
            if m:
                brief.append(f"- {m.group(1).strip()}")
    if brief:
        print("BOOT BRIEF:")
        print("\n".join(brief[:20]))
    return EXIT_FOUND


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="profile_boot")
    ap.add_argument("--memory", default="memory",
                    help="profile directory (default ./memory)")
    a = ap.parse_args(argv)
    return boot(Path(a.memory))


if __name__ == "__main__":
    sys.exit(main())
