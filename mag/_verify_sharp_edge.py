"""Verify the vendored integrity kernel + its wiring (2026-08-25).

The sharp edge, proven: Supported requires Evidence; Disputed requires contradicting
evidence; a claim that tries to over-claim is degraded to Unproven, never auto-truthed.
"""
import sys
from pathlib import Path

ROOT = Path(r"c:\Users\foste\Documents\projects\local_sovereign_agent")
sys.path.insert(0, str(ROOT))

from mag import integrity_kernel as ik  # noqa: E402

fails = []

# 1) kernel validates: Supported WITHOUT evidence is refused
c_bad = ik.Claim("x works", "Supported", ("Assumption",), ())
ok, why = c_bad.validate()
assert not ok and "Evidence" in why, f"bad claim should fail: {why}"
print("PASS kernel refuses Supported-without-Evidence")

# 2) tri_state() degrades instead of over-claiming
d = ik.tri_state("x works", "Supported", ("Assumption",), ())
assert d["status"] == "Unproven", f"should degrade to Unproven, got {d}"
print("PASS tri_state degrades over-claim -> Unproven")

# 3) a real Supported claim (evidence attached) validates + survives
good = ik.tri_state("queue gate works", "Supported", ("Evidence",),
                     ["verify suite passed"])
assert good["status"] == "Supported" and good["valid"], f"good claim failed: {good}"
print("PASS tri_state keeps genuine Supported")

# 4) queue_gate still routes through the kernel (refactor intact)
from mag import queue_gate as qg  # noqa: E402
p = qg.plan(n=3)
assert all(r["claim"]["status"] == "Supported" for r in p["runs"])
print(f"PASS queue_gate via kernel: {len(p['runs'])} runs Supported")

# 5) work_register.record() carries a validated claim + ledger line
from mag.work_register import record  # noqa: E402
kn = record("test", "sharp-edge-verify",
            path="mag/integrity_kernel.py",
            note="kernel vendored + wired",
            claim={"statement": "kernel wired into folds", "status": "Supported",
                   "basis": ["Evidence"], "evidence": ["this verify suite"]})
assert kn["row"].get("claim", {}).get("status") == "Supported", kn["row"]
assert kn["row"].get("claim", {}).get("valid"), kn["row"]
led = Path(ROOT) / "logs" / "claims.jsonl"
lines = led.read_text(encoding="utf-8", errors="replace").splitlines() if led.is_file() else []
assert lines, "claims ledger empty"
print(f"PASS fold carries claim (verkle={kn['row'].get('verkle')}) + ledger {len(lines)} lines")

# 6) work_contract BRIEF carries the sharp edge
from mag.work_contract import BRIEF  # noqa: E402
assert "TRI-STATE" in BRIEF and "falsification" in BRIEF, "BRIEF missing sharp edge"
print("PASS work contract carries the sharp edge")

print("FAILS:", fails if fails else "none")
sys.exit(1 if fails else 0)
