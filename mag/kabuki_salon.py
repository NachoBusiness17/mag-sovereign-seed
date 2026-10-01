#!/usr/bin/env python3
"""KABUKI SALON — the rotating-cast bench, staged on Hermes over the Nous lane.

The operator's commission (2026-09-07): "drive it and do our salons cheaply and
with a kabuki rotating cast of cached actors on basically free models right sized
for the task at hand just in time."

Steal grammar (house law — reuse, don't invent):
  - SEATS come from watch/salon_runner.py SHAPES (the 7-shape bench), loaded by
    path so watch/ stays a plain dir.
  - STAGING comes from mag/hermes_steering.py (_run_hermes + _account_env): every
    actor is a hermes dispatch on the Nous lane, model-prefixed per account.
  - Rotation is hashed from the question (+day), so the same question always
    draws the same order but different questions rotate the cast.
  - Cached actors: personas are static text in configs/kabuki_cast.json; models
    are validated once per run against the account's /models catalog (cached in
    the run manifest), falling back to the :free tier.

Cost law: cast defaults to the :free tier. A chair graduates to a paid model
only when its cast entry says so (tier_note → model field change, operator's
option). max_turns=1: testimony is a single model call, no tool loops.

Receipts: memory/runs/salons/kabuki/<ts>/ — one file per actor + MANIFEST.json
(rotation, models, timings) + the dispatch log rows from the helm.

CLI:
  python -m mag.kabuki_salon salon "<question>" [--actors 6] [--cast PATH]
  python -m mag.kabuki_salon cast            # show the rotation for a question
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mag.hermes_steering import _account_env, _append_receipt, _default_nous_model  # noqa: E402

CAST_PATH = ROOT / "configs" / "kabuki_cast.json"
SALON_RUNNER = ROOT / "watch" / "salon_runner.py"
OUTROOT = ROOT / "memory" / "runs" / "salons" / "kabuki"


def _load_shapes():
    """Steal the SEATS from the shape train (watch/salon_runner.py) by path."""
    spec = importlib.util.spec_from_file_location("salon_runner", SALON_RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SHAPES


def _rotation(question: str, actors: list[dict]) -> list[dict]:
    """Hash-rotated order: stable per question+UTC-day, rotates across questions."""
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    h = int(hashlib.sha256(f"{question}|{day}".encode()).hexdigest(), 16)
    perm = list(range(len(actors)))
    # Fisher-Yates with the hash as the deterministic rng
    for i in range(len(perm) - 1, 0, -1):
        h = (h * 6364136223846793005 + 1442695040888963407) % (1 << 64)
        j = h % (i + 1)
        perm[i], perm[j] = perm[j], perm[i]
    return [actors[i] for i in perm]


def _compose_goal(actor: dict, seat_text: str, question: str) -> str:
    return (
        f"[PERSONA: {actor['stage_name']}]\n{actor['persona']}\n\n"
        f"YOUR SEAT:\n{seat_text}\n\n"
        f"THE MATERIAL UNDER EXAMINATION:\n{question}\n\n"
        f"Answer in at most {actor.get('max_words', 350)} words. Plain markdown, "
        f"no preamble, sign off with your stage name."
    )


def _stage_actor(actor: dict, seat_text: str, question: str, out_dir: Path) -> dict:
    from mag.hermes_steering import _run_hermes

    t0 = time.time()
    row = {"stage_name": actor["stage_name"], "seat": actor["seat"],
           "model": actor["model"], "account": actor["account"]}
    try:
        goal = _compose_goal(actor, seat_text, question)
        exit_code, out, err = _run_hermes(
            goal, ROOT, model=actor["model"],
            timeout=420, yolo=False, max_turns=1, resume=None,
            account=actor.get("account"))
        row.update({"exit": exit_code, "duration_s": round(time.time() - t0, 1)})
        body = out.strip() or (f"(empty stdout) stderr: {err[-500:]}" if err else "(empty)")
    except Exception as e:  # noqa: BLE001 — the show goes on; one actor failing is a fold note
        row.update({"exit": -1, "duration_s": round(time.time() - t0, 1), "error": str(e)[:200]})
        body = f"STAGE FAILURE: {e}"
    row["testimony_path"] = str(out_dir / f"{actor['stage_name']}.md")
    header = (f"# {actor['stage_name']} — seat {actor['seat']}\n\n"
              f"- model: {actor['model']}\n- account: {actor['account']}\n"
              f"- exit: {row['exit']}\n- duration_s: {row['duration_s']}\n\n---\n\n")
    Path(row["testimony_path"]).write_text(header + body, encoding="utf-8")
    row["ok"] = row["exit"] == 0 and "STAGE FAILURE" not in body
    return row


def salon(question: str, n_actors: int, cast_path: Path) -> int:
    cast = json.loads(cast_path.read_text(encoding="utf-8"))
    shapes = _load_shapes()
    actors = _rotation(question, cast["actors"])[:n_actors]
    missing = [a["seat"] for a in actors if a["seat"] not in shapes]
    if missing:
        raise SystemExit(f"seats not found in salon_runner SHAPES: {missing}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = OUTROOT / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema": "kabuki_salon.v1", "ts": ts, "question": question,
        "rotation": [a["stage_name"] for a in actors],
        "cast_path": str(cast_path), "testimonies": [],
    }
    print(f"[kabuki] curtain up {ts} — rotation: "
          f"{' → '.join(a['stage_name'] for a in actors)}")

    rows: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futs = {pool.submit(_stage_actor, a, shapes[a["seat"]], question, out_dir): a
                for a in actors}
        for fut in concurrent.futures.as_completed(futs):
            row = fut.result()
            rows.append(row)
            print(f"[kabuki] {row['stage_name']:<10} seat {row['seat']} "
                  f"exit={row['exit']} {row['duration_s']}s")
    manifest["testimonies"] = rows

    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for r in rows if r["ok"])
    print(f"[kabuki] curtain: {ok}/{len(rows)} testimonies at {out_dir}")
    print(f"[kabuki] fold next: read the testimonies, write FOLD.md "
          f"(shared invariants + verdicts)")

    helm_rows = [{"ts": datetime.now(timezone.utc).isoformat(), "kind": "kabuki",
                  "goal": question[:120], "stage_name": r["stage_name"],
                  "seat": r["seat"], "account": r["account"], "model": r["model"],
                  "exit": r["exit"], "duration_s": r["duration_s"],
                  "output_path": r["testimony_path"]} for r in rows]
    for r in helm_rows:
        _append_receipt(r)
    return 0 if ok == len(rows) else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Kabuki salon — rotating cast on Hermes/Nous")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("salon", help="fire the cast at a question")
    s.add_argument("question")
    s.add_argument("--actors", type=int, default=6)
    s.add_argument("--cast", default=str(CAST_PATH))
    c = sub.add_parser("cast", help="show rotation for a question")
    c.add_argument("question")
    c.add_argument("--cast", default=str(CAST_PATH))
    args = ap.parse_args()
    if args.cmd == "cast":
        cast = json.loads(Path(args.cast).read_text(encoding="utf-8"))
        rot = _rotation(args.question, cast["actors"])
        print(" → ".join(f"{a['stage_name']}({a['seat']},{a['model'].split('/')[-1]})"
                         for a in rot))
        return
    raise SystemExit(salon(args.question, args.actors, Path(args.cast)))


if __name__ == "__main__":
    main()
