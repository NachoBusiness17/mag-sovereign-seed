"""Local inventory of the MCP mirror: sizes + SDK README heads. Local files only."""
import os
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

rows = []
for root, ds, fs in os.walk("."):
    if "_raw" in root:
        continue
    for f in fs:
        p = os.path.join(root, f)
        rel = os.path.relpath(p, ".").replace(os.sep, "/")
        rows.append((rel, os.path.getsize(p)))
tot = sum(s for _, s in rows)
for p, s in sorted(rows):
    print(f"{s:>8}  {p}")
print("TOTAL bytes (excl _raw):", tot, " files:", len(rows))
print()
for r in [
    "sdks/python-sdk/README.md",
    "sdks/typescript-sdk/README.md",
    "sdks/servers/README.md",
    "README.upstream.md",
]:
    head = open(r, encoding="utf-8").read(700).replace("\n", " | ")
    print("==", r, "==")
    print(head[:460])
    print()
