import json, sys, hashlib
from pathlib import Path
sys.path.insert(0, r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
ROOT = Path(r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
LIVE = ROOT / "memory" / "biography" / "verkle_chain.jsonl"

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

print("LIVE sha=" + sha(LIVE))

candidates = sorted(ROOT.glob("memory/biography_backup*/**/verkle_chain.jsonl")) + \
             sorted(ROOT.glob("memory/biography_backup*/**/biography/verkle_chain.jsonl"))
for b in candidates:
    same = "MATCH" if sha(b) == sha(LIVE) else "diff"
    print(f"{same} {str(b.relative_to(ROOT))} sha={sha(b)}")

# dup-session count in live (pre-repair snapshot has 6 dups; post-repair has 0)
rows = [json.loads(l) for l in LIVE.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
sids = [r.get("session_id") for r in rows]
dups = len(sids) - len(set(sids))
print("live_dup_sessions=" + str(dups))
# first-row ts and last-row ts of live vs 13:06 backup
b1306 = ROOT / "memory" / "biography_backup" / "biography_backup_20260825" / "verkle_chain.jsonl"
if b1306.is_file():
    brow = [json.loads(l) for l in b1306.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    print("live_first_ts=" + str(rows[0].get("ts")) + " live_last_ts=" + str(rows[-1].get("ts")))
    print("b1306_first_ts=" + str(brow[0].get("ts")) + " b1306_last_ts=" + str(brow[-1].get("ts")))
    # compare last 3 session ids to see if live has appends beyond backup
    print("live_last3_sid=" + str([r.get("session_id") for r in rows[-3:]]))
    print("b1306_last3_sid=" + str([r.get("session_id") for r in brow[-3:]]))
