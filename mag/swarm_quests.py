"""swarm_quests — THE RUN's quest source, fed by the real swarm queue.

R6 promotion (research/corpus_triangulation/R6_swarm_apk.md, promotion #1): point the
quest generator at memory/runs/swarm_worker/ — 1,275+ REAL tasks — instead of curated
content. The game then IS the backlog audit: quests are fleet state, verbatim,
hash-addressed (dissolves the DRAGON_HORDE falsifier "game and fleet state drift apart").

FORMAT-EATER LAW (the first boss): a task lands when it carries goal + format + verdict;
it no-ops on goal alone. Failed-format tasks become the boss encounter — defeat by
restating the goal in goal+format+verdict form. (R6 card, section 2.)

Transform (streaming, one task file at a time — never slurp the ledger):
  task {task_id, goal, tag, status, created_at, ...}
    -> quest {quest_id, title (goal trimmed), biome (status-mapped),
              verdict_source (REAL result-file path), reward (loot tier by age/depth)}
  biome: failed -> dark-zone-boss-room | done -> lit-loot-room | cancelled -> fog-zone
  verdict_source: results/<task_id>.json, else results_incoming/<task_id>.json.
  A task with NEITHER is a PHANTOM and never becomes a quest (anti-hallucination rule).

Emits: dashboard/static/shadow_quests.json {quests, boss: THE FORMATEATER, stats}.
$0, deterministic, offline. Does NOT touch shadow_walk.html (another builder owns it).

CLI:
  python -m mag.swarm_quests build    # transform + emit + falsifier
  python -m mag.swarm_quests verify   # every emitted verdict_source must EXIST
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "memory" / "runs" / "swarm_worker" / "queue"
RESULTS_DIR = ROOT / "memory" / "runs" / "swarm_worker" / "results"
INCOMING_DIR = ROOT / "memory" / "runs" / "swarm_worker" / "results_incoming"
OUT_JSON = ROOT / "dashboard" / "static" / "shadow_quests.json"

BIOMES = {
    "failed": "dark-zone-boss-room",
    "done": "lit-loot-room",
    "cancelled": "fog-zone",
}
LOOT_NAMES = ("common", "uncommon", "rare", "epic", "relic")  # tier 1..5, older = deeper
MAX_TITLE = 80


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _title(goal: str) -> str:
    """Trim the task goal to a quest title: collapse whitespace, drop fuel pointers,
    cut at the em-dash handler preamble, hard-cap."""
    g = " ".join((goal or "").split())
    g = re.sub(r"fuel:\S+", "", g)
    g = re.sub(r"\s{2,}", " ", g).strip(" -,;")
    for sep in (" — ", " -- ", " - "):
        if sep in g:
            g = g.split(sep, 1)[0].strip()
    return g[:MAX_TITLE]


def _tier(created_at: str, now: datetime) -> tuple[int, int]:
    """Loot tier by task age (backlog depth): deeper = older = rarer. -> (tier 1..5, age_days)"""
    try:
        c = datetime.fromisoformat(created_at)
    except (ValueError, TypeError):
        return 1, -1
    if c.tzinfo is None:
        c = c.replace(tzinfo=timezone.utc)
    age_days = int((now - c).total_seconds() // 86400)
    if age_days < 2:
        tier = 1
    elif age_days < 4:
        tier = 2
    elif age_days < 6:
        tier = 3
    elif age_days < 9:
        tier = 4
    else:
        tier = 5
    return tier, age_days


def _verdict_source(task_id: str) -> str | None:
    """The task's REAL result file. results/ first, then results_incoming/. None = phantom."""
    for d in (RESULTS_DIR, INCOMING_DIR):
        p = d / f"{task_id}.json"
        if p.is_file():
            return _rel(p)
    return None


def _iter_tasks() -> Iterator[dict[str, Any]]:
    """Stream the queue ledger: open one task file at a time, yield, release."""
    if not QUEUE_DIR.is_dir():
        return
    for name in sorted(os_scan(QUEUE_DIR)):
        if not name.endswith(".json"):
            continue
        try:
            with (QUEUE_DIR / name).open(encoding="utf-8") as fh:
                yield json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue


def os_scan(d: Path) -> list[str]:
    return sorted(p.name for p in d.iterdir() if p.is_file())


def transform(now: datetime | None = None) -> dict[str, Any]:
    """Queue ledgers -> RUN quests. Streaming read, deterministic output."""
    now = now or datetime.now(timezone.utc)
    quests: list[dict[str, Any]] = []
    by_status = {"failed": 0, "done": 0, "cancelled": 0}
    by_tag: dict[str, int] = {}
    phantom_ids: list[str] = []
    total = 0

    for t in _iter_tasks():
        total += 1
        status = t.get("status") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        by_tag[t.get("tag") or "untagged"] = by_tag.get(t.get("tag") or "untagged", 0) + 1
        task_id = t.get("task_id") or Path(t.get("_src", "x")).stem
        src = _verdict_source(task_id)
        if src is None:
            phantom_ids.append(task_id)
            continue  # NO PHANTOM QUESTS: no real result file, no quest
        tier, age_days = _tier(t.get("created_at"), now)
        biome = BIOMES.get(status, "fog-zone")
        if status == "done":
            loot = "verified artifact"
        elif status == "failed":
            loot = "format-contract scroll (restate: goal+format+verdict)"
        else:
            loot = "fog shard"
        quests.append({
            "quest_id": task_id,
            "title": _title(t.get("goal") or task_id),
            "biome": biome,
            "status": status,
            "tag": t.get("tag"),
            "domain": t.get("domain"),
            "created_at": t.get("created_at"),
            "age_days": age_days,
            "verdict_source": src,
            "reward": {"tier": tier, "name": LOOT_NAMES[tier - 1], "loot": loot},
        })

    quests.sort(key=lambda q: q["quest_id"])
    boss_horde = [q["quest_id"] for q in quests if q["status"] == "failed"]
    out = {
        "schema": "swarm_quests.v1",
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {
            "queue": _rel(QUEUE_DIR),
            "results": _rel(RESULTS_DIR),
            "results_incoming": _rel(INCOMING_DIR),
        },
        "quests": quests,
        "boss": {
            "id": "formateater",
            "name": "THE FORMATEATER",
            "biome": "dark-zone-boss-room",
            "hp": len(boss_horde),
            "weakness": "goal+format+verdict",
            "mechanic": "defeat it by restating its goal in goal+format+verdict form "
                        "(a no-op on goal alone; lands only with an explicit output contract)",
            "horde": boss_horde,
            "lore": "It ate 480 goals whole because they carried no format. "
                    "Every failed swarm task is one of its teeth.",
        },
        "stats": {
            "tasks_total": total,
            "by_status": by_status,
            "by_tag": dict(sorted(by_tag.items(), key=lambda kv: -kv[1])),
            "quests_emitted": len(quests),
            "resolved_to_result_files": len(quests),
            "phantom_count": len(phantom_ids),
            "phantom_ids_sample": phantom_ids[:10],
            "biome_counts": {
                b: sum(1 for q in quests if q["biome"] == b) for b in BIOMES.values()
            },
            "resolution_rate": round(len(quests) / total, 4) if total else 0.0,
        },
    }
    return out


def _falsifier(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Anti-hallucination rule: every quest's verdict_source must EXIST on disk."""
    missing = []
    for q in data.get("quests", []):
        if not (ROOT / q["verdict_source"]).is_file():
            missing.append(q["verdict_source"])
    return not missing, missing


def build() -> dict[str, Any]:
    data = transform()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    ok, missing = _falsifier(data)
    s = data["stats"]
    size = OUT_JSON.stat().st_size
    print(f"WROTE {_rel(OUT_JSON)} ({size} B)")
    print(f"tasks_total={s['tasks_total']} by_status={s['by_status']}")
    print(f"quests_emitted={s['quests_emitted']} "
          f"biomes={s['biome_counts']}")
    print(f"resolved_to_result_files={s['resolved_to_result_files']}/{s['tasks_total']} "
          f"(rate {s['resolution_rate']:.1%})")
    print(f"PHANTOM_QUESTS={s['phantom_count']} "
          f"(tasks with no result file: excluded, never emitted as quests)")
    if ok:
        print("FALSIFIER PASS: every emitted verdict_source exists on disk")
    else:
        print(f"FALSIFIER FAIL: {len(missing)} phantom verdict_sources: {missing[:5]}")
        sys.exit(1)
    return data


def verify() -> tuple[bool, str]:
    if not OUT_JSON.is_file():
        return False, f"{_rel(OUT_JSON)} missing — run `python -m mag.swarm_quests build`"
    data = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    ok, missing = _falsifier(data)
    if not ok:
        return False, f"{len(missing)} PHANTOM verdict_sources (e.g. {missing[:3]})"
    s = data["stats"]
    return True, (f"{s['quests_emitted']} quests / {s['tasks_total']} tasks, "
                  f"phantom=0, boss hp={data['boss']['hp']}, "
                  f"all verdict_sources exist — {_rel(OUT_JSON)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "verify"])
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    if args.cmd == "build":
        build()
    else:
        ok, msg = verify()
        print(("PASS " if ok else "FAIL ") + msg)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
