import json, sys
from pathlib import Path
sys.path.insert(0, r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
ROOT = Path(r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
KNOTS = ROOT / "memory" / "biography" / "knots"
rows = [json.loads(l) for l in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
dangling = [r for r in rows if r.get("filename") and not (KNOTS / str(r["filename"])).is_file()]
print("RESULT dangling=" + str(len(dangling)))
keys = set()
for r in dangling[:300]:
    keys.update(r.keys())
print("KEYS_SAMPLE=" + str(sorted(keys)))
with_content = sum(1 for r in dangling if r.get("content") or r.get("payload") or r.get("body"))
print("with_content=" + str(with_content))
colon = [r for r in dangling if ":" in str(r.get("filename",""))]
print("colon_filenames=" + str(len(colon)))
kfiles = [p.name for p in KNOTS.iterdir()] if KNOTS.is_dir() else []
print("knot_files_on_disk=" + str(len(kfiles)))
print("sample_disk_names=" + str(kfiles[:5]))
disk_8 = {f[:8] for f in kfiles}
match8 = sum(1 for r in dangling if str(r.get("leaf_hash",""))[:8] in disk_8)
print("dangling_match_disk_by_8char=" + str(match8))
healthy = [r for r in rows if r.get("filename") and (KNOTS / str(r["filename"])).is_file()]
print("healthy_count=" + str(len(healthy)))
if healthy:
    print("HEALTHY_SAMPLE=" + json.dumps(healthy[0])[:300])
    hp = KNOTS / str(healthy[0]["filename"])
    print("healthy_file_size=" + str(hp.stat().st_size))
