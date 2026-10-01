"""Generate the MCP mirror fetch script (bash, literal URLs only).

Reads the already-downloaded git tree (fixed literal path), emits
_raw/fetch.sh where every network command is a single curl line with a
literal raw.githubusercontent.com URL. No parameterized URL construction
at fetch time. Python only touches local files.
"""
import json

t = json.load(open("docs/mirrors/mcp/_raw/git_tree.json", encoding="utf-8"))
paths = sorted(e["path"] for e in t["tree"] if e["type"] == "blob")
V = "2026-07-28"
BASE = "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/"

jobs = []
for p in paths:
    if p.startswith("docs/specification/" + V + "/") and p.endswith(".mdx"):
        rel = "spec/" + p[len("docs/specification/"):]
        jobs.append((BASE + p, rel))
    elif p.startswith("schema/" + V + "/schema."):
        rel = "schema/" + p.split("/")[-1]
        jobs.append((BASE + p, rel))

sdks = [
    ("https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md", "sdks/python-sdk/README.md"),
    ("https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md", "sdks/typescript-sdk/README.md"),
    ("https://raw.githubusercontent.com/modelcontextprotocol/servers/main/README.md", "sdks/servers/README.md"),
    ("https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/README.md", "README.upstream.md"),
]

lines = [
    "#!/usr/bin/env bash",
    "# MCP docs mirror fetch. Every URL below is a LITERAL raw.githubusercontent.com URL.",
    "set -u",
    'LOG="docs/mirrors/mcp/_raw/fetch_log.txt"',
    ': > "$LOG"',
    'mkdir -p "docs/mirrors/mcp/spec/' + V + '" "docs/mirrors/mcp/schema"'
    ' "docs/mirrors/mcp/sdks/python-sdk" "docs/mirrors/mcp/sdks/typescript-sdk"'
    ' "docs/mirrors/mcp/sdks/servers"',
]
dirs = set()
for _, rel in jobs + sdks:
    d = rel.rsplit("/", 1)[0] if "/" in rel else "."
    dirs.add("docs/mirrors/mcp/" + d)
for d in sorted(dirs):
    lines.append('mkdir -p "' + d + '"')
for url, rel in jobs + sdks:
    lines.append(
        'code=$(curl -sS -m 60 -w "%{http_code}" -o "docs/mirrors/mcp/' + rel + '" ' + url + ')'
        ' ; echo "$code ' + url + ' -> ' + rel + '" >> "$LOG"'
    )
lines.append('cat "$LOG"')

open("docs/mirrors/mcp/_raw/fetch.sh", "w", encoding="utf-8", newline="\n").write(
    "\n".join(lines) + "\n"
)
print("fetch commands:", len(jobs) + len(sdks))
