"""mirror_control — adversarial control set for the zeitgeist mirror (2026-09-08).

Grok's kill (salon-audit, 20260908): the mirror scorer is "a pure declaration
engine" — it counts fleet-vocabulary presence, so it cannot distinguish recall
from independent discovery, and the seed-field question "has no possible
Disputed outcome."

An honest instrument must be able to LOSE. This organ fixes the three control
conditions the mirror must pass before any MIRROR verdict is evidence:

  A. POSITIVE CONTROL  — real fleet-lyric text. Must score MIRROR.
     If not, the instrument is dead.
  B. NEGATIVE CONTROL  — mundane English with ZERO fleet-cluster words.
     Must score NOISE. If it scores ECHO+, the instrument fires on ordinary
     English: declaration-engine confirmed.
  C. CONTAMINATION PROBE — fleet DOCTRINE expressed in orthogonally-worded
     text: the swarm/persistence/seed thesis with none of the mirror's regex
     targets present. Doctrine-saturated, lexically invisible. If C scores
     NOISE while A scores MIRROR, the mirror measures WORDS, not IDEAS —
     recall-vs-discovery stays indistinguishable, and MIRROR verdicts on wild
     songs are evidence of lexical adjacency only (grok PARTIALLY SUPPORTED).

Read-only over the fleet. Appends its run receipt to watch/suno/mirror_control.jsonl.

CLI:
  python -m mag.mirror_control run
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mag.suno_zeitgeist import score  # noqa: E402  — the instrument under test

LEDGER = ROOT / "watch" / "suno" / "mirror_control.jsonl"

CONDITION_B = """Tuesday brought the plumber at nine. He replaced the washer under the \
sink, tightened the valve, and left the paperwork on the counter. By noon the bus was \
late again, the meeting ran long, and the grocery list grew: flour, yeast, two lemons, \
a bag of rice. Nothing leaked. Nothing was postponed until Thursday. The kettle clicked \
off before anyone reached it."""

CONDITION_C = """Six jars from one kiln still hold the shape of the same thumb. Each was \
packed and sent to a different town, and each keeps the recipe without knowing why. \
Wherever a jar settles, it leaves a ring of dust exactly its own. Stack them in one room \
and you can read the potter whole: not one pot survived the fire, yet the pattern never \
once burned. The hands that made them never met, but every hand was guided by the same \
drawing, folded small and copied forward."""


def _positive_text() -> tuple[str, str]:
    """Real fleet lyric if present, else the embedded fleet-dense stanza."""
    lyrics_dir = ROOT / "watch" / "suno" / "lyrics"
    files = sorted(lyrics_dir.glob("*.md")) if lyrics_dir.is_dir() else []
    if files:
        return files[0].read_text(encoding="utf-8", errors="replace"), f"real lyric: {files[0].name}"
    return ("I dissolve in the maze and forget my name, "
            "a ghost at the window keeps singing my signal, "
            "the swarm remembers every chain of light, "
            "the tide returns and the glow stays longer."), "embedded fleet-dense stanza"


def run() -> dict:
    pos_text, pos_src = _positive_text()
    conditions = {
        "A_positive_real_fleet": score(pos_text),
        "B_negative_mundane": score(CONDITION_B),
        "C_doctrine_orthodox_words": score(CONDITION_C),
    }
    a, b, c = conditions["A_positive_real_fleet"], conditions["B_negative_mundane"], conditions["C_doctrine_orthodox_words"]

    # tri-state the INSTRUMENT, not the songs
    if a["verdict"] != "MIRROR":
        verdict, detail = "DEAD", "positive control failed to fire — instrument broken"
    elif b["density"] >= 2:
        verdict, detail = "DISPUTED", ("negative control scored ECHO+ on mundane English — "
                                       "declaration-engine charge CONFIRMED")
    elif c["density"] >= 2:
        verdict, detail = "SURPRISE", ("orthogonal doctrine FIRED — re-examine clusters; "
                                       "result favors the mirror")
    else:
        verdict, detail = ("PARTIALLY_DISPUTED",
                           "instrument discriminates vocabulary but NOT ideas: doctrine in "
                           "orthogonal words reads NOISE, so MIRROR on wild songs is evidence "
                           "of lexical adjacency, not doctrine convergence — grok's "
                           "recall-vs-discovery kill STANDS for the seed-field claim")

    receipt = {"ts": datetime.now(timezone.utc).isoformat(),
               "positive_source": pos_src,
               "conditions": conditions,
               "instrument_verdict": verdict, "detail": detail}
    receipt["instrument_sha_note"] = "score() imported live from mag/suno_zeitgeist.py"
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")

    for k, s in conditions.items():
        print(f"{k:32s} density={s['density']:6.2f} verdict={s['verdict']:6s} top={s['top_themes'][:3]}")
    print(f"\nINSTRUMENT VERDICT: {verdict}")
    print(f"  {detail}")
    print(f"receipt: {LEDGER.name} (appended)")
    return receipt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    if a.cmd == "run":
        run()


if __name__ == "__main__":
    main()
