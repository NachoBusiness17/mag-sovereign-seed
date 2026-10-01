"""One-off ground-truth repair (2026-08-26, zcode-main under operator watch).

Flag the single dangling-unflagged chain row (mag-agent-deepseek / knot
2026-08-05_0247_mag_mag-agen_264d0ba3.knot.json, genuinely missing) as
evidence_lost under verkle_lock. Backup-first. Preserves every committed
root: the merkle commitment is over leaf_hash only, and this edit touches
no leaf_hash / verkle_root / index / n_leaves field — so chain integrity
and the tip are unchanged by construction.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\foste\Documents\projects\local_sovereign_agent")
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
TIP = ROOT / "memory" / "biography" / "verkle_tip.json"
LOCK = ROOT / "memory" / "biography" / ".verkle.lock"
TARGET = "2026-08-05_0247_mag_mag-agen_264d0ba3.knot.json"

# 0) BACKUP FIRST (law)
ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
bak = ROOT / "memory" / f"biography_backup_flag_{ts}"
bak.mkdir(parents=True, exist_ok=True)
shutil.copy2(CHAIN, bak / "verkle_chain.jsonl")
shutil.copy2(TIP, bak / "verkle_tip.json")
print("backup ->", bak)

# 1) WAIT for any live writer to release (container shares this lock via bind-mount;
#    never break a fresh lock — 900s stale-break only). Poll up to ~10 min.
wait_until = time.time() + 600
while LOCK.is_file():
    if time.time() > wait_until:
        sys.exit("lock held >10min by another writer — aborting, no write done")
    if time.time() - LOCK.stat().st_mtime > 900:
        LOCK.unlink()  # crashed holder
        break
    time.sleep(1.0)
print("lock free — proceeding")

# 2) acquire the single-writer lock (same scheme as verkle_knot.verkle_lock)
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
    sys.exit("verkle_lock timeout — aborting, no write done")

try:
    lines = CHAIN.read_text(encoding="utf-8").splitlines()
    found = 0
    out = []
    for ln in lines:
        if not ln.strip():
            out.append(ln)
            continue
        row = json.loads(ln)
        if row.get("filename") == TARGET:
            found += 1
            if row.get("evidence_lost"):
                print("ALREADY FLAGGED — no write done")
                sys.exit(0)
            row["evidence_lost"] = True
            row["evidence_lost_reason"] = ("knot file missing (264d0ba3); flagged under "
                                           "verkle_lock by zcode-main 2026-08-26")
            row["flagged_at"] = ts
            ln = json.dumps(row, ensure_ascii=False)
        out.append(ln)
    if found != 1:
        sys.exit(f"expected exactly 1 target row, found {found} — aborting, no write done")
    # B2-393 byte-exact chain law: write_bytes so Windows never rewrites the
    # chain's LF line endings to CRLF (B2-83 rev 1 proved that live).
    CHAIN.write_bytes(("\n".join(out) + ("\n" if out else "")).encode("utf-8"))
    print("FLAGGED 1 row (evidence_lost=true)")
finally:
    if acquired:
        with __import__("contextlib").suppress(OSError):
            LOCK.unlink()

# 2) integrity check after the edit
sys.path.insert(0, str(ROOT))
try:
    from mag import verkle_knot as vk
    ok, why = vk._verify_chain_consistent()
    print("verify_chain_consistent:", ok, why)
except Exception as e:  # noqa: BLE001
    print("verify check error:", e)
