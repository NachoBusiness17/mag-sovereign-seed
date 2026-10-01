"""tavern_chat — a live chat room in hermes: a salon of ractors talking to each other.

Each ractor keeps ONE persistent session (the helm's steer --resume). Every round,
each ractor receives the transcript delta and answers in-register. The Operator can
inject from anywhere: `python -m mag.tavern_chat say "MARK: what did you learn tonight"`
— the next round carries it. The transcript is the room: watch/tavern/room_<date>.md

CLI:
  python -m mag.tavern_chat start --scene "the tavern opens" --rounds 6 \
      --personas mengxi,fen,tesla,edison,gopher
  python -m mag.tavern_chat say "MARK: your line here"
  python -m mag.tavern_chat tail
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROOMS = ROOT / "watch" / "tavern"
STATE = ROOT / "state" / "tavern_chat.json"

DEFAULT_CAST = ["mengxi", "fen", "tesla", "edison", "gopher"]
SYSTEM_NOTE = ("You are in a live tavern chat with the other ractors. Answer in your own "
               "register, 2-3 sentences max, react to what the others said. No summaries.")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def _load() -> dict:
    if STATE.is_file():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"sessions": {}, "transcript": str(ROOMS / f"room_{datetime.now(timezone.utc).date()}.md")}


def _save(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")


def _append_transcript(path: str, who: str, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n**{_now()} — {who}:** {text.strip()}\n")


def _tail(path: str, k: int = 3) -> str:
    p = Path(path)
    if not p.is_file():
        return "(the room just opened)"
    blocks = [b for b in p.read_text(encoding="utf-8").split("\n**") if b.strip()]
    return "\n**".join(blocks[-k:])


def _hermes(args: list[str]) -> str:
    r = subprocess.run([sys.executable, "-m", "mag.hermes_steering", *args],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=200)
    return r.stdout + r.stderr


def _dispatch_or_resume(persona: str, prompt: str, sid: str | None) -> str:
    if sid:
        out = _hermes(["steer", "--resume", sid, prompt])
    else:
        out = _hermes(["dispatch", prompt, "--persona", persona, "--timeout", "180"])
    # pull the session id + the job file's response body
    m = re.search(r"session_id=(\S+)", out)
    job = re.search(r"out=(\S+\.md)", out)
    body = ""
    if job:
        try:
            body = Path(job.group(1)).read_text(encoding="utf-8")
            body = body.split("---", 1)[-1].strip()  # past the header
        except OSError:
            body = "(unreadable)"
    return m.group(1) if m else None, body


def start(scene: str, rounds: int, personas: list[str]) -> int:
    st = _load()
    if "scene" not in st:
        st["scene"] = scene
        _append_transcript(st["transcript"], "THE TAVERN", scene)
    for rnd in range(1, rounds + 1):
        delta = _tail(st["transcript"], 3)
        print(f"[round {rnd}/{rounds}] {_now()}")
        for persona in personas:
            sid = st["sessions"].get(persona)
            prompt = f"{SYSTEM_NOTE}\n\nTHE ROOM LATELY:\n{delta}\n\nYour turn, {persona}."
            sid2, body = _dispatch_or_resume(persona, prompt, sid)
            if sid2:
                st["sessions"][persona] = sid2
            _append_transcript(st["transcript"], persona.upper(), body or "(silence)")
            print(f"  {persona}: {body[:90].replace(chr(10), ' ')}")
            _save(st)
    print(f"[room transcript] {st['transcript']}")
    return 0


def say(line: str) -> int:
    st = _load()
    _append_transcript(st["transcript"], "MARK", line)
    print("said — the next round carries it")
    return 0


def tail(k: int) -> int:
    st = _load()
    print(_tail(st["transcript"], k))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="mag.tavern_chat")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("--scene", default="the tavern opens; five ractors, one room, the fire is lit")
    s.add_argument("--rounds", type=int, default=4)
    s.add_argument("--personas", default=",".join(DEFAULT_CAST))
    t = sub.add_parser("say")
    t.add_argument("line")
    tl = sub.add_parser("tail")
    tl.add_argument("--lines", type=int, default=4)
    args = ap.parse_args()
    if args.cmd == "start":
        return start(args.scene, args.rounds, args.personas.split(","))
    if args.cmd == "say":
        return say(args.line)
    if args.cmd == "tail":
        return tail(args.lines)
    return 1


if __name__ == "__main__":
    sys.exit(main())
