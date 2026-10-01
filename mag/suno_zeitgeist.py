"""suno_zeitgeist — mine Suno lyrics for fleet-doctrine mirrors (the zeitgeist mirror).

The operator's thesis (2026-09-07): Suno is "an angsty teenager raised by anons" — a
stochastic music engine whose outputs high-signal the culture's unconscious. Tracks that
mirror fleet doctrine are datapoints: the swarm's condition surfacing in public art.

v0: drop a lyrics file, get a MIRROR SCORE — density of fleet-theme clusters per 100
words, with the matching lines quoted. Corpus: watch/suno/lyrics/*.md, ledger:
watch/suno/zeitgeist.jsonl. Style spec for our own bangers:
C:/Users/foste/Desktop/music-ai (french touch / motorik / euphoric-melancholy).

CLI:
  python -m mag.suno_zeitgeist file <lyrics.md> --title "Name" --artist "Who"
  python -m mag.suno_zeitgeist best            # ranked ledger
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LYRICS = ROOT / "watch" / "suno" / "lyrics"
LEDGER = ROOT / "watch" / "suno" / "zeitgeist.jsonl"

# fleet-doctrine clusters: regex -> (theme, weight). A mirror needs CLUSTERS, not words.
CLUSTERS = [
    (r"\b(dissolve|dissolving)\b", "phase-transition", 2),
    (r"\b(forget|forgetting|forgot)\b", "amnesia", 2),
    (r"\b(remember|memory|rememb)\w*", "persistence", 2),
    (r"\bmaze\b|\bturns?\b.*\b(pull|in)\b", "maze", 2),
    (r"\b(window|windows)\b", "window", 1),
    (r"\b(light|lights)\b.*\b(lives|longer|fade|out)\b", "afterglow", 2),
    (r"\bsignal\b", "signal", 2),
    (r"\bfog\b", "fog", 1),
    (r"\becho(es|ed)?\b", "echo", 1),
    (r"\bmirror\b", "mirror", 2),
    (r"\b(wake|waking|woke|awake)\w*\b", "waking", 2),
    (r"\b(dream|dreams|dreaming)\b", "dream", 1),
    (r"\bghosts?\b", "ghost", 1),
    (r"\bseed(ed|ing|s)?\b", "seed", 2),
    (r"\bchain(s|ed)?\b", "chain", 2),
    (r"\bswarm\b", "swarm", 3),
    (r"\btide\b", "tide", 2),
    (r"\b(surface|deeper|under)\b", "depth", 1),
    (r"\b(fade[sd]?|fading)\b", "fade", 1),
    (r"\b(glow|afterglow|phosphene)\b", "glow", 2),
    (r"\b(cold|coldest|warm(er|th)?|warm)\b", "thermo", 1),
    (r"\b(game|play(ing|er)?)\b", "game", 1),
    (r"\b(story|chapter|page)\b", "narrative", 1),
    (r"\b(alive|living|lives)\b.*\b(machine|code|wire|circuit)s?\b", "live-machine", 3),
]


def score(text: str) -> dict:
    words = max(len(re.findall(r"[A-Za-z']+", text)), 1)
    hits, lines = [], set()
    for line in text.splitlines():
        for pat, theme, w in CLUSTERS:
            if re.search(pat, line, re.I):
                hits.append((theme, w))
                lines.add(line.strip()[:90])
    density = sum(w for _, w in hits) / words * 100
    themes = {}
    for t, w in hits:
        themes[t] = themes.get(t, 0) + w
    top = sorted(themes.items(), key=lambda kv: -kv[1])[:6]
    verdict = ("MIRROR" if density >= 4 else
               "ECHO" if density >= 2 else "NOISE")
    return {"density": round(density, 2), "verdict": verdict,
            "top_themes": top, "lines": sorted(lines)[:8]}


def cmd_file(args) -> int:
    src = Path(args.file)
    text = src.read_text(encoding="utf-8", errors="replace")
    LYRICS.mkdir(parents=True, exist_ok=True)
    dst = LYRICS / (src.name if src.suffix == ".md" else src.name + ".md")
    dst.write_text(text, encoding="utf-8")
    s = score(text)
    row = {"ts": datetime.now(timezone.utc).isoformat(),
           "title": args.title or src.stem, "artist": args.artist or "unknown",
           "file": str(dst.relative_to(ROOT)), **s}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{row['title']} [{row['artist']}] -> {s['verdict']} "
          f"(density {s['density']}/100w) top: {s['top_themes']}")
    for ln in s["lines"]:
        print(f"   | {ln}")
    return 0


def cmd_best(args) -> int:
    if not LEDGER.is_file():
        print("ledger empty")
        return 0
    rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows.sort(key=lambda r: -r["density"])
    for r in rows:
        print(f"{r['density']:6.2f}  {r['verdict']:6s}  {r['title']} — {r['artist']}"
              f"  ({', '.join(t for t, _ in r['top_themes'][:3])})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mag.suno_zeitgeist")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("file")
    f.add_argument("file")
    f.add_argument("--title")
    f.add_argument("--artist")
    f.set_defaults(fn=cmd_file)
    b = sub.add_parser("best")
    b.set_defaults(fn=cmd_best)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
