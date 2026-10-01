#!/usr/bin/env python3
"""KV-OS P1 — content-addressed prefix blocks over the real corpus (kvos_block.py)

The addressing layer of the KV OS: every text surface the fleet produces gets
cut into fixed-size prefix blocks, each block gets a content hash, and each
file becomes a hash chain of its blocks (h_i = sha256(h_{i-1} || block_i)).

P1 question this answers with real numbers: how much of what the fleet
re-encodes is DUPLICATED prefix — i.e. what would a shared-page KV OS save
tomorrow? (refeed_guard B1 measured 94% of input is re-fed reads; this
measures the corpus-side duplication that makes that possible.)

stdlib only (cage law). No network. Reads repo files, writes one manifest.
"""
import hashlib, json, sys, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WALK_DIRS = ["memory/runs", "watch", "queue", "logs", "state"]
MANIFEST = ROOT / "state" / "kvos_blocks.jsonl"
BLOCK_WORDS = 400          # ~512-token-class block, word-proxy tokenization
MAX_FILES = 4000
MAX_FILE_BYTES = 1_000_000


def cut_blocks(text: str):
    words = text.split()
    for i in range(0, len(words), BLOCK_WORDS):
        yield " ".join(words[i:i + BLOCK_WORDS])


def chain_file(path: Path):
    """Return (list of block hashes, list of block chain links, n_words)."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], [], 0
    prev = b""
    hashes, links, n_words = [], [], 0
    for block in cut_blocks(raw):
        n_words += len(block.split())
        h = hashlib.sha256(block.encode()).digest()[:16]
        link = hashlib.sha256(prev + h).digest()[:16] if prev else h
        hashes.append(h.hex())
        links.append(link.hex())
        prev = link
    return hashes, links, n_words


def main():
    t0 = time.time()
    files = []
    for d in WALK_DIRS:
        base = ROOT / d
        if base.exists():
            for p in base.rglob("*"):
                if p.is_file() and p.suffix in (".md", ".txt", ".json", ".jsonl", ".py", ".html"):
                    try:
                        if p.stat().st_size <= MAX_FILE_BYTES:
                            files.append(p)
                    except OSError:
                        pass
    files = files[:MAX_FILES]

    block_freq = Counter()          # block hash -> occurrences across corpus
    block_first = {}                # block hash -> first file seen in
    file_records = []
    total_blocks = total_words = 0

    for p in files:
        hashes, links, n_words = chain_file(p)
        if not hashes:
            continue
        total_blocks += len(hashes)
        total_words += n_words
        for h in hashes:
            block_freq[h] += 1
            block_first.setdefault(h, str(p.relative_to(ROOT)))
        file_records.append({"file": str(p.relative_to(ROOT)), "blocks": len(hashes),
                             "words": n_words, "head": hashes[0], "chain_tip": links[-1]})

    uniq = len(block_freq)
    dup_blocks = total_blocks - uniq
    shared_files = sum(1 for c in block_freq.values() if c > 1)
    top = block_freq.most_common(10)

    print(f"== KV-OS P1 BLOCK STORE ==")
    print(f"files walked:        {len(file_records)}")
    print(f"blocks cut:          {total_blocks}  (~{total_words:,} words, {BLOCK_WORDS}-word blocks)")
    print(f"unique blocks:       {uniq}")
    print(f"duplicated blocks:   {dup_blocks}  ({100*dup_blocks/max(1,total_blocks):.1f}% of corpus is re-encoded prefix)")
    print(f"blocks in >1 file:   {shared_files}")
    print(f"chain: every file hashed block-by-block; manifest -> {MANIFEST.relative_to(ROOT)}")
    print(f"\ntop shared pages (times, first home, fingerprint):")
    for h, c in top:
        print(f"  {c:5d}x  {block_first[h][:52]:52s} {h[:16]}")
    print(f"\nwalked+hashed in {time.time()-t0:.1f}s")

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8") as fh:
        for r in file_records:
            fh.write(json.dumps(r) + "\n")
        fh.write(json.dumps({"schema": "kvos_blocks.v1", "total_blocks": total_blocks,
                             "unique": uniq, "dup_blocks": dup_blocks,
                             "dup_pct": round(100*dup_blocks/max(1,total_blocks), 1),
                             "block_words": BLOCK_WORDS}) + "\n")
    return 0 if total_blocks else 1


if __name__ == "__main__":
    sys.exit(main())
