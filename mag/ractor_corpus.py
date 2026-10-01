"""ractor_corpus — build the ractors' life-work corpus as local trainable signal.

Operator GO (2026-09-04): "we need their life work locally for our knowledge graph,
all their books. For every ractor we build a high density signal source we can train from."

Rules of the organ (the elder's law — receipts before relics):
  - STORE ONLY WHAT IS LAWFULLY FREE: Project Gutenberg (PD), or explicit PD/free hosts.
  - Copyright-walled life-work is tri-stated in the manifest (WALLED, with the reason),
    never pirated. The walls are part of the map.
  - Idempotent: existing texts are kept, dedup by Gutenberg id, manifest regenerated.
  - $0: no paid lanes touched. urllib only, Gutenberg/gutendex mirrors.

Schema: ractor_corpus.v1 · deterministic + $0 · reuse: gutendex.com, gutenberg.org
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "ractor_corpus.v1"
CORPUS = ROOT / "memory" / "corpus" / "ractors"
UA = {"User-Agent": "mag-ractor-corpus/1.0 (local fleet organ; PD texts only)"}

# curated exclusions — files that pass author-matching but are wrong signal class
REJECT_IDS: dict[str, str] = {
    "pg15120": "The Broadway Anthology (1914) — Bernays' joke-poetry collab, not propaganda signal",
}

# shelf -> {search terms on gutendex, optional fixed gutenberg ids, walled works}
SHELVES: dict[str, dict] = {
    "plato": {
        "seats": ["PLATO_KIRK"],
        "authors": ["Plato"],
        "walled": [],
        "note": "All Jowett translations PD. The cave chair's primary corpus.",
    },
    "freud": {
        "seats": ["FREUD"],
        "authors": ["Sigmund Freud"],
        "walled": [
            "The Ego and the Id (1923, trans. later)",
            "Civilization and Its Discontents (1930)",
            "Moses and Monotheism (1939)",
        ],
        "note": "Pre-1929 translations PD; later metapsychology walled.",
    },
    "jung": {
        "seats": ["JUNG"],
        "authors": ["Carl Gustav Jung"],
        "walled": [
            "Man and His Symbols (1964)",
            "Aion (1951)",
            "Psychology and Alchemy (1944)",
            "The Red Book (2009 facsimile)",
        ],
        "note": "Most of the published corpus is walled; Seven Sermones (1916) is the PD seed.",
    },
    "bernays": {
        "seats": ["BERNAYS"],
        "authors": ["Edward Bernays"],
        "walled": ["The Engineering of Consent (1947 essay; post-1929 corpus)"],
        "note": "Propaganda (1928) and Crystallizing Public Opinion (1923) are PD — the chair's spine.",
    },
    "steiner": {
        "seats": ["ELDER LENS (seat voice)"],
        "authors": ["Rudolf Steiner"],
        "walled": ["late-1920s+ lectures still under European terms in places"],
        "note": "D. 1925 — the esoteric-lens corpus is largely PD. The seat's own reading voice.",
    },
    "hall_mp": {
        "seats": ["ELDER LENS (seat voice)"],
        "authors": ["Manly P. Hall"],
        "walled": ["post-1929 corpus (The Wise Old King, etc.)"],
        "note": "The Secret Teachings of All Ages (1928) is the PD spine. NOT Stuart Hall — two Halls, no silent merge.",
    },
    "scifi_pd": {
        "seats": ["PROPHETIC CORPUS (all chairs)"],
        "authors": [
            "H. G. Wells",
            "Mary Shelley",
            "Edgar Allan Poe",
            "David Lindsay",
            "Edwin A. Abbott",
            "William Hope Hodgson",
            "Karel Capek",
            "Jonathan Swift",
            "Olaf Stapledon",
        ],
        "walled": [
            "Philip K. Dick, Asimov, Lem, Le Guin, Herbert — the modern prophetic layer",
            "kept instead as folded invariants: memory/steal/DEEP_SCIFI_STEAL_20260810.md",
        ],
        "note": "PD prophetic literature only; the modern layer lives as folded invariants.",
    },
    "mcluhan": {
        "seats": ["MCLUHAN"],
        "authors": ["Marshall McLuhan"],
        "walled": [
            "Understanding Media (1964)",
            "The Gutenberg Galaxy (1962)",
            "The Medium Is the Massage (1967)",
        ],
        "note": "Corpus is walled; the chair's brief carries the lens until terms open.",
    },
    "foucault": {
        "seats": ["FOUCAULT"],
        "authors": [],
        "walled": [
            "Discipline and Punish (1975)",
            "The History of Sexuality (1976-84)",
            "The Archaeology of Knowledge (1969)",
            "'Truth and Power' interviews",
        ],
        "note": "Entire corpus walled. Signature question + lens live in docs/ref/ractors/FOUCAULT.md.",
    },
    "baudrillard": {
        "seats": ["BAUDRILLARD"],
        "authors": [],
        "walled": [
            "Simulacra and Simulation (1981)",
            "The Consumer Society (1970)",
            "The Gulf War Did Not Take Place (1991)",
        ],
        "note": "Entire corpus walled. The hyperreal gate lives in the chair brief.",
    },
    "stuart_hall": {
        "seats": ["HALL (Stuart)"],
        "authors": [],
        "walled": [
            "'Encoding/Decoding' (1973)",
            "Policing the Crisis (1978)",
            "The Hard Road to Renewal (1988)",
        ],
        "note": "Walled. NOT Manly P. Hall — two Halls, two chairs, no silent merge.",
    },
    "ellul": {
        "seats": ["ELLUL"],
        "authors": [],
        "walled": [
            "The Technological Society (1954/1964)",
            "Propaganda: The Formation of Men's Attitudes (1962/1965)",
            "The Political Illusion (1965)",
        ],
        "note": "Entire corpus walled; technique's lens lives in the chair brief + the art of the node.",
    },
    # ---- ADJACENT SWEEP (2026-09-04, operator: "search adjacently and grab as much as
    # you can") — the neighbors the chairs actually read, the occult-revival library the
    # elder lens drinks from, and the prophetic-weird corridor.
    "esoterica": {
        "seats": ["ELDER LENS", "JUNG (adjacent)", "BAUDRILLARD (adjacent via Hermeticism)"],
        "authors": [
            "H. P. Blavatsky",
            "G. R. S. Mead",
            "A. E. Waite",
            "Emanuel Swedenborg",
            "Jacob Boehme",
            "Annie Besant",
            "C. W. Leadbeater",
            "A. P. Sinnett",
            "Max Heindel",
            "William Walker Atkinson",
            "Swami Vivekananda",
            "P. D. Ouspensky",
            "Thomas Taylor",
            "J. B. S. Haldane",
            "John Scott Haldane",
            "Plotinus",
            "Friedrich von Schelling",
            "Franz Hartmann",
        ],
        "walled": [
            "Dion Fortune, The Mystical Qabalah (1935)",
            "Alice Bailey corpus (1920s-40s; mixed terms)",
            "Crowley post-1929",
        ],
        "note": "The occult-revival library (Blavatsky->Steiner/Hall lineage) + Neoplatonist ground. Ouspensky's Tertium Organum (1912) is the bridge to the fourth-dimension stratum.",
    },
    "weird_prophetic": {
        "seats": ["PROPHETIC CORPUS (scifi_pd extension)"],
        "authors": [
            "George MacDonald",
            "Arthur Machen",
            "Algernon Blackwood",
            "Lord Dunsany",
            "Edward Bulwer-Lytton",
            "G. K. Chesterton",
            "Jules Verne",
            "Edgar Rice Burroughs",
            "William Morris",
            "Ambrose Bierce",
        ],
        "walled": ["Mervyn Peake, Borges, the modern weird (1930+)"],
        "note": "The esoteric-imagination corridor: MacDonald (Jung's favorite), Machen/Blackwood (occult horror), Dunsany (dreamed cosmogonies), Zanoni/Vril (initiation novels).",
    },
    "cs_classics": {
        "seats": ["THE STACK (CS as logos)"],
        "authors": [
            "George Boole",
            "Samuel Butler",
            "William James",
            "Henri Bergson",
            "Bertrand Russell",
            "Friedrich Nietzsche",
            "Rene Descartes",
            "Gottfried Wilhelm Leibniz",
            "David Hume",
            "Immanuel Kant",
            "Arthur Stanley Eddington",
        ],
        "walled": [
            "Turing 1950, Shannon 1948, Wiener 1948, Gödel 1931, Wigner 1960 — freely mirrored but not clearly PD; POINTERS owed",
        ],
        "note": "Minds behind the machine: Boole's Laws of Thought, Butler's machine-consciousness satire, James/Bergson for the attention stratum, Nietzsche for the genealogy corridor Foucault walks.",
    },
    "crowd_media": {
        "seats": ["BERNAYS (adjacent)", "ELLUL (adjacent)", "FOUCAULT (adjacent)", "MCLUHAN (adjacent)"],
        "authors": [
            "Gustave Le Bon",
            "Walter Lippmann",
            "Graham Wallas",
            "Wilfred Trotter",
            "Gabriel Tarde",
            "Jean-Baptiste Henri Lacordaire",
        ],
        "walled": [
            "Mumford Technics and Civilization (1934) — walled; Lippmann later works walled",
        ],
        "note": "The books the propaganda century was built FROM: Le Bon's Crowd is Bernays' source code; Lippmann's Public Opinion (1922) is the frame Propaganda answered.",
    },
}

# esoterica the lens corpus needs regardless of ractors (PD spine)
EXTRA_IDS: list[tuple[str, int, str]] = [
    # (shelf, gutenberg id, why)
    ("steiner", 3261, "The Kybalion (1908, William Walker Atkinson) — hermetic mechanics"),
    ("plato", 1497, "Republic — the cave, chair primary"),
    ("scifi_pd", 97, "Flatland — dimension perception, the gate as geometry"),
    ("scifi_pd", 1322, "A Voyage to Arcturus ( Lindsay 1912, PD) — gnostic initiation sci-fi"),
    ("scifi_pd", 829, "Gulliver's Travels — satire as camouflage discipline"),
]

# curated stable ids (gutendex outage fallback). (shelf, gutenberg id, title-keyword,
# author-keyword) — a download is KEPT only if its header names both. Wrong guess = reject.
CURATED: list[tuple[str, int, tuple[str, ...], tuple[str, ...]]] = [
    ("plato", 1497, ("republic",), ("plato",)),
    ("plato", 1656, ("apology",), ("plato",)),
    ("plato", 1657, ("crito",), ("plato",)),
    ("plato", 1658, ("phaedo",), ("plato",)),
    ("plato", 1600, ("symposium",), ("plato",)),
    ("plato", 1675, ("phaedrus",), ("plato",)),
    ("plato", 1644, ("meno",), ("plato",)),
    ("plato", 1672, ("gorgias",), ("plato",)),
    ("plato", 1635, ("ion",), ("plato",)),
    ("plato", 1615, ("laches",), ("plato",)),
    ("plato", 1633, ("lysis",), ("plato",)),
    ("plato", 1584, ("charmides",), ("plato",)),
    ("plato", 1659, ("euthydemus",), ("plato",)),
    ("plato", 1612, ("cratylus",), ("plato",)),
    ("plato", 1735, ("sophist",), ("plato",)),
    ("plato", 1726, ("theaetetus",), ("plato",)),
    ("plato", 1744, ("philebus",), ("plato",)),
    ("plato", 1750, ("laws",), ("plato",)),
    ("plato", 1572, ("timaeus",), ("plato",)),
    ("plato", 1571, ("critias",), ("plato",)),
    ("plato", 1642, ("euthyphro",), ("plato",)),
    ("plato", 1591, ("protagoras",), ("plato",)),
    ("plato", 1687, ("parmenides",), ("plato",)),
    ("plato", 1738, ("statesman", "politicus"), ("plato",)),
    ("freud", 14655, ("psycho-analysis", "psychoanalysis", "introduction"), ("freud",)),
    ("freud", 16158, ("dream",), ("freud",)),
    ("freud", 24337, ("sex", "contributions"), ("freud",)),
    ("freud", 41214, ("totem",), ("freud",)),
    ("freud", 41385, ("war", "death"), ("freud",)),
    ("freud", 44215, ("psychoanalytic", "history"), ("freud",)),
    ("freud", 14944, ("psychopathology",), ("freud",)),
    ("scifi_pd", 35, ("time machine",), ("wells",)),
    ("scifi_pd", 36, ("war of the worlds",), ("wells",)),
    ("scifi_pd", 5230, ("invisible man",), ("wells",)),
    ("scifi_pd", 1727, ("moreau",), ("wells",)),
    ("scifi_pd", 84, ("frankenstein",), ("shelley",)),
    ("scifi_pd", 345, ("dracula",), ("stoker",)),
    ("scifi_pd", 65474, ("r. u. r", "rossum"), ("capek", "apek")),
]


def _header_ok(raw: bytes, titles: tuple[str, ...], authors: tuple[str, ...]) -> bool:
    head = raw[:9000].decode("utf-8", errors="ignore").lower()
    return any(t in head for t in titles) and any(a in head for a in authors)


def _get(url: str, timeout: int = 45) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def gutendex(search: str) -> list[dict]:
    url = f"https://gutendex.com/books?search={urllib.parse.quote(search)}&copyright=false"
    for attempt in range(3):  # gutendex is flaky under sweep — retry with backoff
        raw = _get(url, timeout=30)
        if raw:
            try:
                return json.loads(raw).get("results", [])
            except Exception:
                pass
        time.sleep(2.0 * (attempt + 1))
    return []


def pick(results: list[dict], author_key: str, limit: int = 4) -> list[dict]:
    out, seen = [], set()
    for b in results:
        aid = ",".join(a["name"] for a in b.get("authors", [])).lower()
        if author_key.split()[-1].lower() not in aid:
            continue
        txt = b.get("formats", {}).get("text/plain; charset=us-ascii") or b.get(
            "formats", {}
        ).get("text/plain; charset=utf-8")
        if not txt or b["id"] in seen:
            continue
        seen.add(b["id"])
        out.append(b)
        if len(out) >= limit:
            break
    return out


def main() -> int:
    import urllib.parse  # noqa: F401 (imported for gutendex quote)

    index = {"schema": SCHEMA, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "shelves": {}}
    total_bytes = 0
    total_texts = 0

    for shelf, cfg in SHELVES.items():
        sdir = CORPUS / shelf
        tdir = sdir / "texts"
        tdir.mkdir(parents=True, exist_ok=True)
        stored: list[dict] = []

        # fixed extras first
        for eshelf, gid, why in EXTRA_IDS:
            if eshelf != shelf:
                continue
            f = tdir / f"pg{gid}.txt"
            if not f.exists() or f.stat().st_size < 1024:
                raw = _get(f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt")
                if raw:
                    f.write_bytes(raw)
            if f.exists() and f.stat().st_size > 1024:
                stored.append({"id": gid, "file": str(f.relative_to(ROOT)), "bytes": f.stat().st_size, "why": why})

        # curated stable ids with header verification (gutendex outage fallback)
        rejected: list[int] = []
        for cshelf, cid, titles, authors in CURATED:
            if cshelf != shelf:
                continue
            f = tdir / f"pg{cid}.txt"
            if not f.exists() or f.stat().st_size < 1024:
                raw = _get(f"https://www.gutenberg.org/cache/epub/{cid}/pg{cid}.txt")
                if raw and len(raw) <= 12_000_000 and _header_ok(raw, titles, authors):
                    f.write_bytes(raw)
                    time.sleep(0.3)
            if f.exists() and f.stat().st_size > 1024:
                stored.append(
                    {
                        "id": cid,
                        "file": str(f.relative_to(ROOT)),
                        "bytes": f.stat().st_size,
                        "title": f"curated pg{cid}",
                    }
                )
            elif f.exists():
                f.unlink()
                rejected.append(cid)
        if rejected:
            print(f"[{shelf}] rejected (header mismatch): {rejected}", file=sys.stderr)

        # gutendex-resolved per author (adjacent sweep: grab as much as lawful)
        for author in cfg["authors"]:
            for b in pick(gutendex(author), author, limit=6):
                if f"pg{b['id']}" in REJECT_IDS:
                    continue
                url = b["formats"].get("text/plain; charset=us-ascii") or b["formats"].get(
                    "text/plain; charset=utf-8"
                )
                f = tdir / f"pg{b['id']}.txt"
                if not f.exists() or f.stat().st_size < 1024:
                    raw = _get(url)
                    if not raw or len(raw) > 12_000_000:
                        continue
                    f.write_bytes(raw)
                    time.sleep(0.4)  # be a polite citizen of the mirror
                if f.exists() and f.stat().st_size > 1024:
                    stored.append(
                        {
                            "id": b["id"],
                            "file": str(f.relative_to(ROOT)),
                            "bytes": f.stat().st_size,
                            "title": b.get("title", "?"),
                            "author": "; ".join(a["name"] for a in b.get("authors", [])),
                        }
                    )

        # inventory merge: the manifest lists the SHELF, not the session — every text
        # on disk counts, with provenance carried from the previous manifest.
        old: dict[int, dict] = {}
        mpath = sdir / "MANIFEST.json"
        if mpath.exists():
            try:
                for s in json.loads(mpath.read_text(encoding="utf-8")).get("stored_pd", []):
                    if "id" in s:
                        old[s["id"]] = s
            except Exception:
                pass
        seen_ids = {s["id"] for s in stored}
        for f in sorted(tdir.glob("pg*.txt")):
            gid = int(f.stem[2:])
            if f"pg{gid}" in REJECT_IDS:
                if f.exists():
                    f.unlink()
                continue
            if f.stat().st_size < 1024 or gid in seen_ids:
                continue
            entry = old.get(gid, {"id": gid})
            entry.setdefault("file", str(f.relative_to(ROOT)))
            entry["bytes"] = f.stat().st_size
            stored.append(entry)
            seen_ids.add(gid)

        sbytes = sum(s["bytes"] for s in stored)
        total_bytes += sbytes
        total_texts += len(stored)
        manifest = {
            "schema": SCHEMA,
            "shelf": shelf,
            "seats": cfg["seats"],
            "note": cfg["note"],
            "stored_pd": sorted(stored, key=lambda s: -s["bytes"]),
            "walled": cfg["walled"],
            "bytes": sbytes,
            "texts": len(stored),
        }
        (sdir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        lines = [f"# CORPUS SHELF: {shelf}", "", f"Seats: {', '.join(cfg['seats'])}", "",
                 cfg["note"], "", "## STORED (public domain)", ""]
        for s in sorted(stored, key=lambda s: -s["bytes"]):
            title = s.get("title", s.get("why", "?"))
            lines.append(f"- [{title}]({s['file']}) — pg{s['id']}, {s['bytes']:,} bytes")
        lines += ["", "## WALLED (copyrighted — named, never pirated)", ""]
        lines += [f"- {w} (Unproven locally; lens carried by the chair brief)" for w in cfg["walled"]]
        (sdir / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        index["shelves"][shelf] = {"texts": len(stored), "bytes": sbytes}

    index["totals"] = {"texts": total_texts, "bytes": total_bytes}
    (CORPUS / "corpus_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(json.dumps(index["totals"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
