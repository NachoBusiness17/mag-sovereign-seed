"""shelf_pdf — the operator's hand-carry door for purchased books (PDF → corpus shelf).

Operator ruling (2026-09-06): "I might just give you the pdfs, I will buy them when we
can afford them." This organ receives a bought PDF, shelves it into the right ractor
shelf, updates the shelf manifest, and (if pypdf is installed) extracts a text layer so
the swarm can digest it. Legal chain-of-custody: the operator bought it; we shelve OUR
copy for fair personal/training use inside the fleet; provenance is recorded.

Usage:
  python mag/shelf_pdf.py <pdf-path> <shelf> "<Title (Year) — author>" [note]
Example:
  python mag/shelf_pdf.py ~/Downloads/understanding_media.pdf mcluhan "Understanding Media (1964) — Marshall McLuhan" "operator-purchased 2026-09"
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

CORPUS = ROOT / "memory" / "corpus" / "ractors"
INBOX = CORPUS / "_INBOX"


def shelf_pdf(pdf: Path, shelf: str, title: str, note: str = "") -> dict:
    sdir = CORPUS / shelf
    tdir = sdir / "texts"
    tdir.mkdir(parents=True, exist_ok=True)
    dest = tdir / pdf.name
    shutil.copy2(pdf, dest)

    # best-effort text layer (swarm digestion needs text, not bytes)
    text_path = None
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(dest))
        txt = "\n".join((page.extract_text() or "") for page in reader.pages)
        if len(txt) > 2000:
            text_path = tdir / (dest.stem + ".txt")
            text_path.write_text(txt, encoding="utf-8")
    except ImportError:
        pass

    # manifest update (append-style provenance row)
    manifest = {}
    mp = sdir / "MANIFEST.json"
    if mp.exists():
        try:
            manifest = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    stored = manifest.setdefault("stored_pd", [])
    entry = {
        "id": "op-" + str(int(time.time())),
        "file": str(dest.relative_to(ROOT)),
        "bytes": dest.stat().st_size,
        "title": title,
        "provenance": "operator-purchased (hand-carry door); " + note,
        "text_layer": str(text_path.relative_to(ROOT)) if text_path else "",
    }
    stored.append(entry)
    manifest["texts"] = len(stored)
    manifest["bytes"] = sum(s["bytes"] for s in stored)
    mp.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "shelf": shelf, "file": entry["file"], "text_layer": bool(text_path)}


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        # show pending inbox items (the drop folder)
        if INBOX.is_dir():
            pending = [p.name for p in INBOX.glob("*.pdf")]
            print(f"\ninbox pending ({len(pending)}):")
            for p in pending:
                print("  -", p)
            print("shelf with: python mag/shelf_pdf.py", str(INBOX / "<file>"), "<shelf> \"<Title>\"")
        return 0
    pdf, shelf, title = Path(argv[0]), argv[1], argv[2]
    note = argv[3] if len(argv) > 3 else ""
    if not pdf.is_file():
        if INBOX.is_dir() and (INBOX / pdf.name).is_file():
            pdf = INBOX / pdf.name
        else:
            print("pdf not found:", pdf)
            return 1
    r = shelf_pdf(pdf, shelf, title, note)
    print(json.dumps(r, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
