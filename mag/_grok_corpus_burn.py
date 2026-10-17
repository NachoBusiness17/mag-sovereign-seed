"""GROK CORPUS BURN — the writing-craft library + HIVE red-team reply, both seats,
parallel (2026-08-26, operator: "i dont see grok usage meaningfully spiking").

Drives mag.grok_seat_burner._launch_one across nacho + sd in parallel threads,
one PDF per job, deterministic contract per the burner's own doctrine:
deliverable = digest file, acceptance = file exists with 300-600 words,
forbid = framework loading / web research / narration.

Output: memory/runs/grok_burn/<slug>.md per PDF + burn_manifest.json with spend.
Run: python -m mag._grok_corpus_burn [--limit N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mag.grok_seat_burner import _launch_one  # noqa: E402

OUT = ROOT / "memory" / "runs" / "grok_burn"

CORPUS = [
    # the HIVE red-team reply (Desktop)
    r"C:/Users/ESTATE_USER/Desktop/New folder/HIVE_RESPONSE_TO_RED_TEAM_REPLY_20260820.pdf",
    # the writing-craft library (Downloads)
    r"C:/Users/ESTATE_USER/Downloads/3NovelBlueprint-210917-111553 (1).pdf",
    r"C:/Users/ESTATE_USER/Downloads/6TwentyStrategiesforYourFirstParagraph-210917-111732.pdf",
    r"C:/Users/ESTATE_USER/Downloads/8PointofView-210917-111732 (1).pdf",
    r"C:/Users/ESTATE_USER/Downloads/9CharacterProfile-210917-111732 (1).pdf",
    r"C:/Users/ESTATE_USER/Downloads/11TwelveWaystoEndaChapter-210917-111732 (1).pdf",
    r"C:/Users/ESTATE_USER/Downloads/14FiveStorytellingGuideropes-210917-111848 (1).pdf",
    r"C:/Users/ESTATE_USER/Downloads/15ChapterChecklist-210917-111848 (1).pdf",
    r"C:/Users/ESTATE_USER/Downloads/17TwoWaystoCreateSuspense-210917-111848 (1).pdf",
    r"C:/Users/ESTATE_USER/Downloads/19DefeatWritersBlock-210917-111948.pdf",
    r"C:/Users/ESTATE_USER/Downloads/20EscalateYourPlotinMiddleNovel-210917-111948 (1).pdf",
    r"C:/Users/ESTATE_USER/Downloads/23PlotBoxes3StoryProgressions-210917-111948 (1).pdf",
    r"C:/Users/ESTATE_USER/Downloads/30GuideRopesfortheClimax-210917-112055.pdf",
    r"C:/Users/ESTATE_USER/Downloads/35TypesofEndings-210917-112055 (2).pdf",
]


def slug(pdf: str) -> str:
    s = Path(pdf).stem
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:48]
    return s.lower()


def goal_for(pdf: str) -> str:
    out_md = f"memory/runs/grok_burn/{slug(pdf)}.md"
    return (
        f"Read the PDF at \"{pdf}\". Do NOT load any framework. Do NOT do web research. "
        f"Write a fleet-grade digest of it directly to the file {out_md} "
        f"(300-600 words: what it teaches, its 3 strongest techniques, and one line on "
        f"how a multi-agent fleet could apply it). Then reply DONE."
    )


def burn_one(seat: str, pdf: str) -> dict:
    r = _launch_one(seat, goal_for(pdf), max_turns=8, timeout=420, always_approve=True)
    f = OUT / f"{slug(pdf)}.md"
    return {"pdf": Path(pdf).name, "seat": seat, "ok": bool(r.get("ok")),
            "file_landed": f.is_file() and f.stat().st_size > 500,
            "out_head": (r.get("output") or r.get("error") or "")[:120],
            "started": r.get("started"), "finished": r.get("finished")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    pdfs = CORPUS[: a.limit] if a.limit else CORPUS
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(["nacho", "sd"][i % 2], p) for i, p in enumerate(pdfs)]
    t0 = time.time()
    results = []
    # two at a time = one job per seat in flight (each account is one concurrency lane)
    for i in range(0, len(jobs), 2):
        with ThreadPoolExecutor(max_workers=2) as ex:
            results += list(ex.map(lambda j: burn_one(*j), jobs[i:i + 2]))
        time.sleep(2)
    manifest = {"schema": "grok_corpus_burn.v1",
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "n": len(jobs), "elapsed_s": round(time.time() - t0, 1),
                "landed": sum(1 for r in results if r["file_landed"]),
                "results": results}
    (OUT / "burn_manifest.json").write_text(json.dumps(manifest, indent=2),
                                            encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("n", "elapsed_s", "landed")}, indent=2))
    for r in results:
        print(f"  [{'OK ' if r['file_landed'] else 'FAIL'}] {r['seat']:5s} {r['pdf'][:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
