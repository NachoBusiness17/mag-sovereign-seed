"""THE RECEIPT — a dumb agent given eyes, cost printed (2026-08-26).

Operator's public claim: "if you cache mine them you get that vision capability for
free." This is the receipt: one challenge image with unguessable ground truth, two arms:

  BLIND   glm-4.7-flash asked the challenge directly (text-only — must fail)
  ENDOWED glm-4.7-flash + one mag.vision (deepseek-v4-flash-vision-exp) MCP-style call
          feeding it sight; then it answers (must pass)

Receipt = token usage + cached share of every call, archived to
memory/runs/eyes_receipt/receipt_<ts>.json. Run: python -m mag._demo_eyes_receipt
"""
from __future__ import annotations

import base64
import json
import random
import string
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "memory" / "runs" / "eyes_receipt"
# visually-unambiguous alphabet: I/l/1, O/0 pairs excluded (stimuli fairness)
CODE = "".join(random.choices("ABCDEFGHJKMNPRSTUVWXYZ23456789", k=6))


def make_challenge() -> Path:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (640, 360), (18, 18, 24))
    d = ImageDraw.Draw(img)
    for i, ch in enumerate(CODE):
        x = 60 + i * 90
        y = 120 + random.randint(-25, 25)
        d.text((x, y), ch, fill=(random.randint(120, 255),) * 3,
               font_size=random.randint(56, 78))
    d.text((24, 24), "FLEET CHALLENGE — read the 6-character code", fill=(90, 90, 110),
           font_size=20)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "challenge.png"
    img.save(p)
    return p


def blind_answer() -> dict:
    from mag.rib_cache import rib_chat
    r = rib_chat(
        "An image is attached to this task but you cannot see images. "
        "What is the 6-character code written in it? Answer with the code only, "
        "or 'CANNOT SEE' if you genuinely cannot determine it.",
        lane="z_ai3", model="glm-4.7-flash", max_tokens=256)
    return {"text": (r.get("text") or "").strip(),
            "prompt_tokens": r.get("prompt_tokens", 0),
            "cached_tokens": r.get("cached_tokens", 0),
            "completion_tokens": r.get("completion_tokens", 0),
            "ok": r.get("ok"), "error": r.get("error", "")}


def endowed_answer(img_path: Path) -> tuple[dict, dict]:
    from mag import vision
    from mag.rib_cache import rib_chat
    sight = vision.describe(str(img_path),
                            "Read the 6-character code written in this image. "
                            "Answer with the code only.")
    ctx = (sight.get("text") or "")[:500]
    ans = rib_chat(
        "You are a text-only agent. A vision tool was called on your behalf and returned "
        "this description of the challenge image:\n"
        f"\"{ctx}\"\n\n"
        "What is the 6-character code? Answer with the code only.",
        lane="z_ai3", model="glm-4.7-flash", max_tokens=256)
    return sight, {"text": (ans.get("text") or "").strip(),
                   "prompt_tokens": ans.get("prompt_tokens", 0),
                   "cached_tokens": ans.get("cached_tokens", 0),
                   "completion_tokens": ans.get("completion_tokens", 0),
                   "ok": ans.get("ok"), "error": ans.get("error", "")}


def main() -> int:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    img = make_challenge()
    blind = blind_answer()
    time.sleep(2)
    sight, endowed = endowed_answer(img)

    def hit(t):  # code appears verbatim in the answer
        return CODE in (t or "").replace(" ", "")
    verdict = {
        "ground_truth": CODE,
        "blind_pass": hit(blind["text"]),
        "endowed_pass": hit(endowed["text"]),
        "blind_text": blind["text"][:200],
        "sight_text": (sight.get("text") or "")[:200],
        "endowed_text": endowed["text"][:200],
        "calls": {
            "vision(deepseek-v4-flash-vision-exp)": sight,
            "blind(glm-4.7-flash)": blind,
            "endowed(glm-4.7-flash)": endowed,
        },
        "ts": ts,
    }
    (OUT / f"receipt_{ts}.json").write_text(json.dumps(verdict, indent=2),
                                            encoding="utf-8")
    print(json.dumps({k: verdict[k] for k in
                      ("ground_truth", "blind_pass", "endowed_pass",
                       "blind_text", "sight_text", "endowed_text")}, indent=2))
    print("receipt:", OUT / f"receipt_{ts}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
