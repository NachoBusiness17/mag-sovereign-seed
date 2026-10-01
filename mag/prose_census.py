"""prose_census — inventory the machine's prose debt as a runnable queue.

Born 2026-09-05, operator: "we have so much prose in this machine that needs
taking care of yesterday" and "no monkeypatches" — the debt gets a SCANNER and
a cadence, not a mood. Every .md in the repo is classified:

  - freshness bucket (mtime: fresh <7d, aging <30, stale <90, fossil 90+)
  - GHOST REFS: repo-path references to files that do not exist (DISPUTED —
    regex noise is possible; the number is a triage queue, not a verdict)
  - LAUNCHER-SHAPED PROSE: fenced blocks that start things (docker exec,
    python -m, schtasks...) without a SUPERSEDED/owner marker — the 09-05
    lesson: hand-run commands from markdown are the launcher-of-last-resort
    and always weird. Each candidate needs an owner (supervisor slot) or a
    tombstone.

Writes watch/PROSE_CENSUS_<date>.md and prints ONE verdict line.
Runnable standalone:  python -m mag.prose_census
Callable from the lane engine:  run_census(root) -> dict
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

SKIP_DIRS = {".venv", ".git", "node_modules", "worktrees", "__pycache__",
             "models", "agent_sessions", "artifacts", ".mimosa",
             "mag-backup.git", "cage_bin",
             # mined corpora are DATA (inventory), not the machine's own voice;
             # including them made census #1 report 43k files of noise.
             "corpus", "mine", "agent_corpus", "agent_uploads", "agent_state",
             "analytics", "html_cache", "static", "unsloth_seat",
             # biography/ is the FROZEN room (chain v1 walls, never amended) and
             # biography_backup_* is a tombstone — history is not a workqueue.
             "biography", "biography_backup_20260825"}
# top-level dirs whose .md files count as operating prose; everything else at
# root is skipped wholesale.
WALK_TOPS = ["watch", "docs", "queue", "state", "scripts", "mag", "configs",
             ".agents", "tests", "jobs", "memory", "reference"]
_REF_RE = re.compile(
    # mdx joins the extension class 2026-09-28 (FW-07, fifty_wide_20260917): without
    # it every `*.mdx` ref truncated to `*.md` before the exists() check, which
    # reported all 31 live docs/mirrors/mcp/INDEX.md spec-mirror refs (files present
    # under docs/mirrors/mcp/spec/2026-07-28/ as .mdx) as dead — pure instrument
    # truncation, zero dead bytes. jsonl reordered ahead of json by the same
    # evidence (FW-10): `json|jsonl` truncated every `*.jsonl` ref to `*.json`,
    # reporting live ledgers (memory/trajectory/steps.jsonl, state/art_queue.jsonl,
    # state/fuel/lite_pacing.jsonl...) as dead in the VC2_CHAIN_STATE receipt.
    # Leftmost-first alternation demands the longer literal first. Also: URL
    # fragments stripped before scanning (a path inside an https URL is a remote
    # address, not a repo claim). Receipts:
    # watch/inbox/fifty_wide_20260917/FW07_mcp_index.md + FW10_vc2_amend.md
    r"(?:watch|docs|state|logs|queue|memory|scripts|mag|configs|dashboard|jobs|tests)"
    r"/[A-Za-z0-9_\-./]+\.(?:mdx|md|py|jsonl|json|yaml|yml|txt|html)")
_FENCE_RE = re.compile(r"```[a-z]*\n(.*?)```", re.S)
_LAUNCH_RE = re.compile(r"docker (?:exec|restart|run)|python -m |python main|schtasks |tasklist ")
# owner marker, FW-11 2026-09-28 (fifty_wide_20260917): the module docstring always
# promised "SUPERSEDED/owner marker" but the check below only looked for SUPERSEDED,
# so an owned standing launcher could never clear the flag. `# fence-owner:` on its
# own line inside the block is the owner marker; live command cards (README, AGENTS,
# HANDOFF) carry it, one-shot receipts get SUPERSEDED. Receipt:
# watch/inbox/fifty_wide_20260917/FW11_fence_owners.md
_FENCE_OWNER_RE = re.compile(r"^\s*#\s*fence-owner:", re.M)
_MAX_REFS = 40


def _age_days(p: Path) -> float:
    return (datetime.datetime.now().timestamp() - p.stat().st_mtime) / 86400


def run_census(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    files = []
    for p in root.glob("*.md"):
        files.append(p)
    for top in WALK_TOPS:
        d = root / top
        if not d.is_dir():
            continue
        for p in d.rglob("*.md"):
            if any(part in SKIP_DIRS for part in p.parts[len(root.parts):]):
                continue
            files.append(p)

    buckets = {"fresh": 0, "aging": 0, "stale": 0, "fossil": 0}
    stale_list: list[tuple[float, str]] = []
    ghost_by_file: list[tuple[int, str, list[str]]] = []
    launchers: list[str] = []
    for p in files:
        age = _age_days(p)
        if age < 7:
            buckets["fresh"] += 1
        elif age < 30:
            buckets["aging"] += 1
        elif age < 90:
            buckets["stale"] += 1
            stale_list.append((age, str(p.relative_to(root))))
        else:
            buckets["fossil"] += 1
            stale_list.append((age, str(p.relative_to(root))))
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(p.relative_to(root))
        # URL strip, same FW-07 fix: a path fragment inside an https URL
        # (raw.githubusercontent.com/.../docs/specification/...) is a remote
        # address, not a claim about this repo — mirrors/mcp INDEX carried 31
        # such refs inside [source](...) links and the regex counted every one
        # as a dead repo path.
        text_nourl = re.sub(r"https?://\S+", "", text)
        refs = _REF_RE.findall(text_nourl)[:_MAX_REFS]
        dead = sorted({r for r in refs if not (root / r).exists()})
        if dead:
            ghost_by_file.append((len(dead), rel, dead[:8]))
        for i, block in enumerate(_FENCE_RE.findall(text)):
            if _LAUNCH_RE.search(block) and "SUPERSEDED" not in block \
                    and not _FENCE_OWNER_RE.search(block):
                launchers.append(f"{rel}#fence{i + 1}")

    stale_list.sort(reverse=True)
    ghost_by_file.sort(reverse=True)
    total_ghost = sum(n for n, _, _ in ghost_by_file)
    stamp = datetime.date.today().strftime("%Y%m%d")
    out = root / "watch" / f"PROSE_CENSUS_{stamp}.md"
    lines = [
        f"# PROSE CENSUS — {datetime.date.today().isoformat()} (lane: prose, cage)\n",
        f"**Files:** {len(files)} — fresh {buckets['fresh']} / aging {buckets['aging']}"
        f" / stale {buckets['stale']} / fossil {buckets['fossil']}",
        f"**Ghost refs (DISPUTED — regex noise possible):** {total_ghost} across"
        f" {len(ghost_by_file)} files",
        f"**Launcher-shaped fences without owner/SUPERSEDED:** {len(launchers)}\n",
        "## Oldest prose (top 25 — convert to structure or tombstone)\n",
    ]
    lines += [f"- {age:.0f}d — `{rel}`" for age, rel in stale_list[:25]]
    lines += ["\n## Top ghost-referencing files (verify, then fix or cite as data)\n"]
    lines += [f"- `{rel}` — {n} dead: {', '.join(f'`{d}`' for d in dead)}"
              for n, rel, dead in ghost_by_file[:20]]
    lines += ["\n## Launcher-shaped fences (owner or tombstone)\n"]
    lines += [f"- `{x}`" for x in launchers[:30]]
    lines += ["\n*Triage queue, tri-state: counts are Supported (measured);"
              " individual hits are DISPUTED until eyeballed.*\n"]
    out.write_text("\n".join(lines), encoding="utf-8")
    verdict = (f"files={len(files)} stale={buckets['stale']} fossil={buckets['fossil']} "
               f"ghost_refs={total_ghost} launchers={len(launchers)}")
    print(f"prose census filed: {out.name} — {verdict}")
    return {"files": len(files), "stale": buckets["stale"],
            "fossil": buckets["fossil"], "ghost_refs": total_ghost,
            "launchers": len(launchers), "report": str(out)}


if __name__ == "__main__":
    run_census(Path(__file__).resolve().parent.parent)
