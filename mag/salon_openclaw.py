"""Salon beats via the OpenClaw seat — the hypervisor path.

Operator intent (2026-08-29): the salon must be manageable through openclaw,
spending coding-plan quota via the headless openclaw seat, NOT burning the
zcode 5.3-flash session. One question, N blind posts, keep only what survives
(grok's summons doctrine). Every post lands in the room stamped unverified;
a second seat (default deepseek via chat_provider) verifies.

Usage:
  python -m mag.salon_openclaw ask "Should the governor commit blind drains?"
  python -m mag.salon_openclaw round --pack memory/runs/riddler/PACK_PHYSICS.md --thread physics
  python -m mag.salon_openclaw chan --thread physics --turns 2   # 4chan: they SEE each other
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone

from pathlib import Path

from mag.seat_dispatch import task as dispatch_task

ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "watch" / "room.jsonl"

VERIFIER_PROMPT = (
    "You are the salon verifier. Below are N blind answers from seats to ONE "
    "question. Judge only on what is written: mark each SUPPORTED / DISPUTED / "
    "UNPROVEN with a one-line reason, then give the surviving consensus in "
    "three lines max. No new claims.\n\nQUESTION:\n{q}\n\nANSWERS:\n{answers}"
)


def room_post(seat: str, event: str, text: str, thread: str = "salon",
              **extra) -> None:
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "seat": seat,
           "event": event, "thread": thread, "text": text[:4000]}
    rec.update(extra)
    try:
        with ROOM.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except OSError:
        pass


FALLBACK_MODEL = "deepseek/deepseek-v4-flash"  # conservation 08-29→09-02: no z.ai spend

# Control UI picker names → OpenClaw --model. No z.ai until weekly reset.
ROUND_MODELS = [
    "deepseek/deepseek-v4-flash",
    "groq/openai/gpt-oss-120b",
    "nvidia/deepseek-ai/deepseek-v4-flash-0731",
    "openrouter/auto",
    "ollama/qwen2.5-coder:7b",
]


def _docker_openclaw(model: str, message: str, *, session_id: str, timeout: int = 120) -> dict:
    """One turn through mag-openclaw (hypervisor), not desktop Hermes --local."""
    import subprocess
    cmd = [
        "docker", "exec", "mag-openclaw",
        "openclaw", "agent", "--agent", "main",
        "--session-id", session_id,
        "--model", model,
        "-m", message,
        "--thinking", "off",
        "--json",
        "--timeout", str(timeout),
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30, cwd=str(ROOT))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "model": model, "detail": str(e)[:300]}
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    try:
        from mag.seat_dispatch import _extract_openclaw
        text = _extract_openclaw(out)
    except Exception:
        text = out[-1500:]
    ok = p.returncode == 0 and bool(text) and "error" not in (text[:40].lower())
    return {"ok": ok, "model": model, "detail": text, "rc": p.returncode}


def round_room(question: str, *, models: list[str] | None = None, thread: str = "salon",
               pack: str = "", verify: str = "deepseek") -> dict:
    """Fan selected OpenClaw models onto watch/room.jsonl; DeepSeek synthesizes."""
    q = (question or "").strip()
    if pack:
        p = ROOT / pack if not Path(pack).is_absolute() else Path(pack)
        if p.is_file():
            q = p.read_text(encoding="utf-8", errors="replace")[:6000] + "\n\nQUESTION:\n" + q
    models = models or list(ROUND_MODELS)
    run_id = uuid.uuid4().hex[:10]
    room_post("salon-runner", "salon_question", q[:4000], thread=thread, models=models)
    answers = []
    for i, model in enumerate(models, 1):
        # A salon invocation is allowed to overlap another invocation. Never
        # reuse a transcript id across runs: OpenClaw's embedded prompt fence
        # correctly fails closed when two processes publish to one JSONL file.
        sid = f"salon-{model.split('/')[-1][:24]}-{run_id}-{i}"
        r = _docker_openclaw(model, q[:8000], session_id=sid)
        body = r.get("detail") or r.get("error") or ""
        answers.append(f"[{model} ok={r.get('ok')}] {body}")
        room_post(model, "salon_answer", body, thread=thread, ok=bool(r.get("ok")))
        print(f"{model}: ok={r.get('ok')}")
    verdict = ""
    if verify and verify != "none" and answers:
        try:
            from models.providers import chat_provider
            r = chat_provider(verify, system=(
                "You monitor the salon. Tri-state each witness SUPPORTED/DISPUTED/UNPROVEN "
                "one line. Then surviving consensus in three lines. No new Mag. No invented CLIs."),
                user=f"QUESTION:\n{q[:3000]}\n\nANSWERS:\n" + "\n\n".join(a[:1500] for a in answers),
                model="deepseek-v4-flash" if verify == "deepseek" else None,
                thinking=False, max_tokens=1800, tier="T2")
            verdict = (r.get("text") if r.get("ok") else f"MONITOR FAILED: {r.get('error')}") or ""
        except Exception as e:  # noqa: BLE001
            verdict = f"MONITOR FAILED: {e}"
        room_post(f"monitor-{verify}", "salon_verdict", verdict, thread=thread)
    room_post("salon-runner", "salon_done", f"n={len(models)} thread={thread}", thread=thread)
    return {"ok": any("[model" in a or "ok=True" in a for a in answers) or bool(answers),
            "thread": thread, "n": len(models), "verdict": verdict[:1200], "answers": answers}


def _thread_tape(slug: str, n: int = 20) -> list[dict]:
    if not ROOM.is_file():
        return []
    posts = []
    for line in ROOM.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("thread") == slug:
            posts.append(rec)
    return posts[-n:]


# Mag API lanes that post to the same board (conservation: no z.ai until reset)
CHAN_LANES = [
    ("groq", "groq", None),
    ("deepseek", "deepseek", "deepseek-chat"),
    ("nvidia", "nvidia", "deepseek-ai/deepseek-v4-flash-0731"),
]


def chan(question: str, *, pack: str = "", thread: str = "physics",
         turns: int = 2, verify: str = "deepseek") -> dict:
    """4chan-for-agents: posters READ the thread then reply. Emergence, not blind Q&A."""
    q = (question or "").strip()
    if pack:
        p = ROOT / pack if not Path(pack).is_absolute() else Path(pack)
        if p.is_file():
            q = p.read_text(encoding="utf-8", errors="replace")[:4000] + "\n\n" + q
    if not q:
        q = "Smell the keep. Physics-as-computer. Smallest Mag-native next experiment. No new Mag."
    room_post("OP", "chan_op", q[:4000], thread=thread)
    n_ok = 0
    from models.providers import reload_providers, chat_provider
    reload_providers()
    sys_p = (
        "You post on a 4chan-style agent board. You SEE the other posts. "
        "Reply once, verbose, to the thread — quote a seat with >>name if you reply. "
        "One voice. Not the planet. No invented CLIs. No inner weather of the operator. "
        "Primer: fireball creates a tool; wait is a season; disk is file not soul."
    )
    for turn in range(max(1, turns)):
        tape = _thread_tape(thread, 16)
        blob = "\n".join(
            f">>{p.get('seat')} {(p.get('text') or '')[:700]}" for p in tape
        )
        for label, provider, model in CHAN_LANES:
            kw = {"tier": "T2", "max_tokens": 700, "allow_peak": True}
            if provider in ("deepseek", "zai"):
                kw["thinking"] = False
            if model:
                kw["model"] = model
            try:
                r = chat_provider(
                    provider, system=sys_p,
                    user=f"THREAD #{thread} turn {turn+1}\n\n{blob}\n\nYour post:",
                    **kw)
                text = (r.get("text") or "").strip()
                ok = bool(r.get("ok") and text)
                err = (r.get("error") or "")[:160]
            except Exception as e:  # noqa: BLE001
                text, ok, err = "", False, str(e)[:160]
            room_post(label, "chan_post", text or err, thread=thread, ok=ok, turn=turn)
            n_ok += int(ok)
            print(f"t{turn+1} {label}: ok={ok} n={len(text)}")
    verdict = ""
    if verify and verify != "none":
        tape = _thread_tape(thread, 40)
        blob = "\n".join(f"[{p.get('seat')}] {(p.get('text') or '')[:900]}" for p in tape)
        try:
            r = chat_provider(
                verify, system=(
                    "You lurk the board. Tri-state posts SUPPORTED/DISPUTED/UNPROVEN. "
                    "Then what EMERGED that no single post said. Three lines. No new Mag."),
                user=blob[:12000], model="deepseek-v4-flash",
                thinking=False, max_tokens=1600, tier="T2", allow_peak=True)
            verdict = (r.get("text") if r.get("ok") else str(r.get("error"))) or ""
        except Exception as e:  # noqa: BLE001
            verdict = f"LURK FAILED: {e}"
        room_post(f"lurk-{verify}", "chan_lurk", verdict, thread=thread)
    room_post("salon-runner", "chan_done", f"ok_posts={n_ok} thread={thread}", thread=thread)
    return {"ok": n_ok > 0, "thread": thread, "n_ok": n_ok, "verdict": verdict[:1500]}


def _failed(detail: str, ok: bool) -> bool:
    """NO_REPLY = glm-4.5-flash no-op token; 429 = free-lane congestion. Both retry."""
    if not ok:
        return True
    d = (detail or "").strip()
    return (not d) or d == "NO_REPLY" or "status=429" in d or "Limit Exhausted" in d


def _ask_one(seat: str, question: str, model: str = "") -> dict:
    try:
        result = dispatch_task(question, seat=seat, tag="salon", model=model)
    except Exception as e:  # noqa: BLE001
        result = {"ok": False, "error": str(e)[:200]}
    result["seat"] = seat
    if _failed(str(result.get("detail") or ""), bool(result.get("ok"))) and not model:
        retry = _ask_one(seat, question, model=FALLBACK_MODEL)
        retry["retried"] = True
        return retry
    return result


def main() -> int:
    ap = argparse.ArgumentParser(prog="salon-openclaw")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ask = sub.add_parser("ask", help="one question, N blind openclaw posts + verifier")
    ask.add_argument("question")
    ask.add_argument("--seats", default="openclaw",
                     help="comma list of seat_dispatch seats (default: openclaw)")
    ask.add_argument("--verify", default="deepseek",
                     help="verifier seat via chat_provider, or 'none'")
    rnd = sub.add_parser("round", help="fan OpenClaw picker models onto one room thread + synthesize")
    rnd.add_argument("question", nargs="?", default="")
    rnd.add_argument("--pack", default="memory/runs/riddler/PACK_PHYSICS.md")
    rnd.add_argument("--models", default="")
    rnd.add_argument("--thread", default="salon")
    rnd.add_argument("--verify", default="deepseek")
    ch = sub.add_parser("chan", help="4chan board: models READ the thread then post; lurk synthesizes")
    ch.add_argument("question", nargs="?", default="")
    ch.add_argument("--pack", default="memory/runs/riddler/PACK_PHYSICS.md")
    ch.add_argument("--thread", default="physics")
    ch.add_argument("--turns", type=int, default=2)
    ch.add_argument("--verify", default="deepseek")
    args = ap.parse_args()
    if args.cmd == "chan":
        r = chan(args.question, pack=args.pack, thread=args.thread,
                 turns=max(1, int(args.turns)), verify=args.verify)
        print(json.dumps({k: r.get(k) for k in ("ok", "thread", "n_ok", "verdict")},
                         ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 1
    if args.cmd == "round":
        models = [m.strip() for m in (args.models or "").split(",") if m.strip()] or None
        r = round_room(args.question or "What is the smallest Mag-native next experiment?",
                       models=models, thread=args.thread, pack=args.pack, verify=args.verify)
        print(json.dumps({k: r.get(k) for k in ("ok", "thread", "n", "verdict")}, ensure_ascii=False, indent=2))
        return 0 if r.get("n") else 1

    seats = [s.strip() for s in args.seats.split(",") if s.strip()]
    room_post("salon-runner", "salon_question", args.question, seats=seats)

    answers = []
    for i, seat in enumerate(seats, 1):
        r = _ask_one(seat, args.question)
        body = r.get("detail") or r.get("error") or "(no output)"
        answers.append(f"[{seat} #{i} ok={r.get('ok')}] {body}")
        room_post("salon-runner", "salon_answer", body, reply_to=r.get("task_id"))
        print(f"seat {seat} #{i}: ok={r.get('ok')}")

    if args.verify != "none" and answers:
        v = VERIFIER_PROMPT.format(q=args.question, answers="\n\n".join(answers))
        try:
            from models.providers import chat_provider  # deepseek pennies lane
            r = chat_provider(args.verify, system=(
                    "You are the salon verifier of the sovereign fleet. "
                    "Tri-state verdicts only: SUPPORTED/DISPUTED/UNPROVEN, "
                    "one-line reasons, then the surviving consensus."),
                user=v, model="deepseek-v4-pro", thinking=False,
                max_tokens=2500, tier="T2")
            verdict = r.get("text") if r.get("ok") else \
                f"VERIFIER FAILED: {str(r.get('error'))[:300]}"
        except Exception as e:  # noqa: BLE001
            verdict = f"VERIFIER FAILED: {e}"
        room_post("salon-verifier", "salon_verdict", verdict, seats=[args.verify])
        print("verdict posted")

    room_post("salon-runner", "salon_done",
              f"question={args.question[:120]} answers={len(answers)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
