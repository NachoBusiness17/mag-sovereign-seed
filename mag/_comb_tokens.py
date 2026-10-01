"""Find token/usage counters and estimate corpus size on Mag disk."""
from pathlib import Path
from collections import Counter
import json, re, os

root = Path("/app")
print("ROOT", root, root.exists())

# likely logs
cands = []
for pat in [
    "**/usage*.json", "**/tokens*.json", "**/llm*.jsonl", "**/dm*.jsonl",
    "**/*token*", "**/*usage*", "**/game_dm*", "memory/**/*.jsonl",
]:
    pass

# walk memory and mag for token-ish files
hits = []
for base in [root / "memory", root / "mag", root / "logs", root / "data"]:
    if not base.exists():
        continue
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        n = p.name.lower()
        if any(k in n for k in ("token", "usage", "billing", "llm_call", "ollama", "deepseek")):
            hits.append(p)

print("NAME HITS", len(hits))
for p in hits[:40]:
    print(" ", p, p.stat().st_size)

# grep token fields in json/jsonl under memory
field_counts = Counter()
token_sums = Counter()
files_with = []
for base in [root / "memory"]:
    if not base.exists():
        continue
    for p in base.rglob("*"):
        if p.suffix.lower() not in {".json", ".jsonl", ".md", ".txt", ".log"}:
            continue
        if p.stat().st_size > 8_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if not re.search(r"token", text, re.I):
            continue
        files_with.append((str(p), p.stat().st_size))
        if p.suffix == ".jsonl":
            for line in text.splitlines():
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                for k, v in (row.items() if isinstance(row, dict) else []):
                    if "token" in str(k).lower() and isinstance(v, (int, float)):
                        field_counts[k] += 1
                        token_sums[k] += int(v)
        elif p.suffix == ".json":
            try:
                row = json.loads(text)
            except Exception:
                continue
            def walk(o, prefix=""):
                if isinstance(o, dict):
                    for k, v in o.items():
                        if "token" in str(k).lower() and isinstance(v, (int, float)):
                            field_counts[prefix+k] += 1
                            token_sums[prefix+k] += int(v)
                        else:
                            walk(v, prefix+str(k)+".")
                elif isinstance(o, list) and len(o) < 50:
                    for i, x in enumerate(o[:20]):
                        walk(x, prefix)
            walk(row)

print("TOKEN FIELDS", field_counts.most_common(30))
print("TOKEN SUMS", token_sums.most_common(30))
print("FILES mentioning token", len(files_with))
for fp, sz in files_with[:25]:
    print(" ", sz, fp)
