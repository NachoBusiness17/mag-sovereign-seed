import json, sys, os, datetime
from pathlib import Path
sys.path.insert(0, r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
ROOT = Path(r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
KNOTS = ROOT / "memory" / "biography" / "knots"
rows = [json.loads(l) for l in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
missing = [r for r in rows if r.get("filename") and not (KNOTS / str(r["filename"])).is_file()]
print("RESULT chain_rows=" + str(len(rows)) + " dangling=" + str(len(missing)))
src = (ROOT / "mag" / "verkle_knot.py").read_text(encoding="utf-8", errors="replace")
print("lock_in_verkle_knot=" + str(any(x in src.lower() for x in ("msvcrt", "fcntl", "flock", "single-writer", "threading.lock", "filelock"))))
print("sanitizer_present=" + str("_safe_sid" in src))
mt = os.path.getmtime(ROOT / "mag" / "verkle_knot.py")
print("verkle_knot_mtime=" + datetime.datetime.fromtimestamp(mt).strftime("%H:%M:%S"))
print("Mag-backup.git_local=" + str((ROOT / "Mag-backup.git").is_dir()))
print("Mag-backup.git_sibling=" + str((ROOT.parent / "Mag-backup.git").is_dir()))
