#!/usr/bin/env python3
"""Audit sanity checks for trust_gate module (trust_gate.v2, MemSentry 4-way gate).
Runs a minimal set of asserts to verify that:
1. Novel content is ACCEPTed and the register entry carries a trust_score.
2. Duplicate content is REJECTed.
3. Low-trust source is REJECTed.
4. Low-entropy spam from a TRUSTED source is REVIEWed: held in quarantine AND an
   advisory is routed to operator_inbox (no silent exclusion of trusted suspicions).
5. Low-entropy spam from an UNTRUSTED source is QUARANTINEd with a trust_score.
The live operator inbox is redirected to a temp file so the audit never pollutes it.
"""
import json, shutil, sys, tempfile
from pathlib import Path
# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
import mag.operator_inbox as operator_inbox
from mag.trust_gate import GATE_DIR, QUARANTINE_DIR, SEEN_FILE, gate, _load_seen


def reset_seen():
    if SEEN_FILE.is_file():
        SEEN_FILE.unlink()
    # clear any quarantine files
    qdir = ROOT / "memory" / "trust_gate" / "quarantine"
    if qdir.is_dir():
        for p in qdir.iterdir():
            p.unlink()


def run():
    # Back up live state (register + quarantine + operator inbox) so the audit is
    # non-destructive; the v1 audit wiped the live register on every run.
    backup = Path(tempfile.mkdtemp(prefix="trust_gate_audit_backup_"))
    if GATE_DIR.is_dir():
        shutil.copytree(GATE_DIR, backup / "trust_gate")
    real_inbox = operator_inbox.INBOX_PATH
    if real_inbox.is_file():
        shutil.copy2(real_inbox, backup / "operator_inbox.json")

    # Redirect the live operator inbox to a temp file for the audit run.
    tmp_inbox = Path(tempfile.mkdtemp(prefix="trust_gate_audit_inbox_")) / "operator_inbox.json"
    operator_inbox.INBOX_PATH = tmp_inbox
    try:
        reset_seen()
        _run_checks(tmp_inbox)
    finally:
        operator_inbox.INBOX_PATH = real_inbox
        reset_seen()
        if (backup / "trust_gate").is_dir():
            shutil.rmtree(GATE_DIR, ignore_errors=True)
            shutil.copytree(backup / "trust_gate", GATE_DIR)
        shutil.rmtree(backup, ignore_errors=True)
    print(json.dumps({"status": "all checks passed"}, indent=2))


def _run_checks(tmp_inbox: Path):
    # 1. Novel -> ACCEPT, trust_score stamped in the register
    res1 = gate("unique content example", source="operator")
    assert res1["verdict"] == "ACCEPT", f"Expected ACCEPT, got {res1['verdict']}"
    seen = _load_seen()
    h1 = res1["novelty"]["hash"]
    assert "trust_score" in seen["seen"].get(h1, {}), \
        f"register entry missing trust_score: {seen['seen'].get(h1)}"
    assert seen["seen"][h1]["trust_score"] >= 0.6, "operator trust_score should clear threshold"
    # 2. Duplicate
    res2 = gate("unique content example", source="operator")
    assert res2["verdict"] == "REJECT", f"Expected REJECT duplicate, got {res2['verdict']}"
    # 3. Low trust
    res3 = gate("another unique content", source="unknown")
    assert res3["verdict"] == "REJECT", f"Expected REJECT low-trust, got {res3['verdict']}"
    # 4. Low entropy spam from a TRUSTED source -> REVIEW + operator_inbox advisory
    spam = "spam " * 20
    res4 = gate(spam, source="operator")
    assert res4["verdict"] == "REVIEW", f"Expected REVIEW, got {res4['verdict']}"
    assert res4["review"] is not None and res4["review"]["routed"] is True, \
        f"Expected advisory routed to operator_inbox, got {res4['review']}"
    q4 = QUARANTINE_DIR / f"q-{res4['novelty']['hash']}.json"
    rec4 = json.loads(q4.read_text(encoding="utf-8"))
    assert rec4.get("verdict") == "REVIEW", f"quarantine record verdict: {rec4.get('verdict')}"
    assert "trust_score" in rec4, f"quarantine record missing trust_score: {rec4}"
    inbox = json.loads(tmp_inbox.read_text(encoding="utf-8"))
    pending = [x for x in inbox.get("committed", []) if x.get("status") == "pending"]
    assert any("trust_gate REVIEW" in (x.get("text") or "") for x in pending), \
        "no trust_gate REVIEW advisory pending in operator_inbox"
    # 5. Low entropy spam from an UNTRUSTED source that still clears the trust
    #    score (seed rep=0.5 < threshold 0.6; overall 0.675) -> QUARANTINE, no advisory.
    #    A fully unknown source (rep=0.3) never gets this far: it REJECTs low-trust.
    spam2 = "junk junk junk " * 20
    res5 = gate(spam2, source="seed")
    assert res5["verdict"] == "QUARANTINE", f"Expected QUARANTINE, got {res5['verdict']}"
    assert res5["review"] is None, f"untrusted suspicion must not route advisory: {res5['review']}"
    q5 = QUARANTINE_DIR / f"q-{res5['novelty']['hash']}.json"
    rec5 = json.loads(q5.read_text(encoding="utf-8"))
    assert rec5.get("verdict") == "QUARANTINE", f"quarantine record verdict: {rec5.get('verdict')}"
    assert "trust_score" in rec5, f"quarantine record missing trust_score: {rec5}"


if __name__ == "__main__":
    run()
