import json, sys, os, datetime
from pathlib import Path
sys.path.insert(0, r"c:\Users\foste\Documents\projects\local_sovereign_agent")
ROOT = Path(r"c:\Users\foste\Documents\projects\local_sovereign_agent")
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
KNOTS = ROOT / "memory" / "biography" / "knots"
rows = [json.loads(l) for l in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
missing = [r for r in rows if r.get("filename") and not (KNOTS / str(r["filename"])).is_file()]
flagged = [r for r in rows if r.get("evidence_lost")]
print("chain_rows=" + str(len(rows)))
print("dangling=" + str(len(missing)))
print("evidence_lost_flags=" + str(len(flagged)))
# tip
tip = ROOT / "memory" / "biography" / "verkle_tip.json"
if tip.is_file():
    t = json.loads(tip.read_text(encoding="utf-8"))
    print("tip_root=" + str(t.get("root"))[:16])
    print("tip_leaves=" + str(t.get("n_leaves")))
else:
    print("tip_missing")
mt = os.path.getmtime(CHAIN)
print("chain_mtime=" + datetime.datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M:%S"))
# sample flagged row
if flagged:
    print("FLAGGED_SAMPLE=" + json.dumps(flagged[0])[:200])
# last row ts
if rows:
    print("last_row_ts=" + str(rows[-1].get("ts"))[:30])
# backup dirs + their chain mtimes/rows
for b in sorted(ROOT.glob("memory/biography_backup*/**/verkle_chain.jsonl")):
    n = sum(1 for _ in b.open(encoding="utf-8", errors="replace"))
    print("BACKUP chain=" + str(b.relative_to(ROOT)) + " rows=" + str(n) + " mtime=" + datetime.datetime.fromtimestamp(os.path.getmtime(b)).strftime("%H:%M:%S"))
