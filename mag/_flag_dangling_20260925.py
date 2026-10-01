"""One-off ground-truth repair (2026-09-25 night, gala lane b2-stone2b).

Flag the two dangling-unflagged chain rows as evidence_lost under verkle_lock,
per the Stone 2b wave-2 punch list item 2 (queue/todo.md) and the wave-1
tier-2 verdict. Cause: chain_guard check() returned state=regression with
exactly these two rows dangling and unflagged (evidence: raw check output in
watch/inbox/gala_20260925/w1/lanes/b2-stone2b.check.txt, 2026-09-25):
  mag-agent-orc-t492d6fd54c  knot 2026-08-09_0343_..._ff2435af.knot.json  (ts 2026-09-11)
  mag-agent-orc-t039e3ee788  knot 2026-09-03_1518_..._52737592.knot.json  (ts 2026-09-22)
Both knot files are genuinely absent from memory/biography/knots/.

Backup-first. Preserves every committed root: the merkle commitment is over
leaf_hash only, and this edit touches no leaf_hash / verkle_root / index /
n_leaves field, so chain integrity and the tip are unchanged by construction.
Procedure copied from the 2026-08-26 precedent mag/_flag_dangling_264d0ba3.py.
"""
import json
import os
import shutil
import sys
import time
from contextlib import suppress
from pathlib import Path

ROOT = Path(r"C:\Users\foste\Documents\projects\local_sovereign_agent")
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
TIP = ROOT / "memory" / "biography" / "verkle_tip.json"
LOCK = ROOT / "memory" / "biography" / ".verkle.lock"
TARGETS = {
    "2026-08-09_0343_biography_mag-agen_ff2435af.knot.json",
    "2026-09-03_1518_biography_mag-agen_52737592.knot.json",
}

# 0) BACKUP FIRST (law)
ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
bak = ROOT / "memory" / f"biography_backup_flag_{ts}"
bak.mkdir(parents=True, exist_ok=True)
shutil.copy2(CHAIN, bak / "verkle_chain.jsonl")
shutil.copy2(TIP, bak / "verkle_tip.json")
print("backup ->", bak)

# 1) WAIT for any live writer to release, then acquire the single-writer lock
wait_until = time.time() + 600
while LOCK.is_file():
    if time.time() > wait_until:
        sys.exit("lock held >10min by another writer - aborting, no write done")
    if time.time() - LOCK.stat().st_mtime > 900:
        LOCK.unlink()  # crashed holder
        break
    time.sleep(1.0)
acquired = False
for _ in range(1200):
    try:
        fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"pid={os.getpid()} ts={ts}".encode())
        os.close(fd)
        acquired = True
        break
    except FileExistsError:
        if LOCK.is_file() and time.time() - LOCK.stat().st_mtime > 900:
            LOCK.unlink()
        time.sleep(0.05)
if not acquired:
    sys.exit("verkle_lock timeout - aborting, no write done")

try:
    lines = CHAIN.read_text(encoding="utf-8").splitlines()
    found = 0
    already = 0
    out = []
    for ln in lines:
        if not ln.strip():
            out.append(ln)
            continue
        row = json.loads(ln)
        if row.get("filename") in TARGETS:
            found += 1
            if row.get("evidence_lost"):
                already += 1
                out.append(ln)
                continue
            row["evidence_lost"] = True
            row["evidence_lost_reason"] = ("knot file missing; flagged under verkle_lock by "
                                           "gala b2-stone2b per Stone 2b wave-2 punch list")
            row["flagged_at"] = ts
            ln = json.dumps(row, ensure_ascii=False)
        out.append(ln)
    if found != len(TARGETS):
        sys.exit(f"expected exactly {len(TARGETS)} target rows, found {found} - aborting, no write done")
    # B2-393 byte-exact chain law: write_bytes so Windows never rewrites the
    # chain's LF line endings to CRLF (B2-83 rev 1 proved that live).
    CHAIN.write_bytes(("\n".join(out) + ("\n" if out else "")).encode("utf-8"))
    print(f"FLAGGED {found - already} rows (evidence_lost=true), already-flagged {already}")
finally:
    if acquired:
        with suppress(OSError):
            LOCK.unlink()

# 2) integrity check after the edit
sys.path.insert(0, str(ROOT))
try:
    from mag import verkle_knot as vk
    ok, why = vk._verify_chain_consistent()
    print("verify_chain_consistent:", ok, why)
except Exception as e:  # noqa: BLE001
    print("verify check error:", e)
