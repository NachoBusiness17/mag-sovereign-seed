"""Verify concurrency_gate enforces the in-flight cap across PROCESSES (2026-08-25).

flash concurrency = 1: main process holds the only slot; a subprocess must fail to
acquire (short timeout) while held, then succeed after release. This is the 1305 fix.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
sys.path.insert(0, str(ROOT))

from mag import concurrency_gate as cg  # noqa: E402

PY = sys.executable
CHILD = r"""
import sys
sys.path.insert(0, %r)
from mag import concurrency_gate as cg
tok = cg.acquire("glm-4.7-flash", timeout=3, owner="child")
print("CHILD_TOK=" + str(tok))
if tok:
    cg.release(tok)
""" % str(ROOT)

# main holds flash (limit 1)
tok = cg.acquire("glm-4.7-flash", timeout=5, owner="parent")
assert tok, "parent should acquire flash (limit 1)"
print("PASS parent holds flash slot:", tok)

# child must be BLOCKED while parent holds (short timeout -> None)
r = subprocess.run([PY, "-c", CHILD], capture_output=True, text=True, timeout=60)
out = (r.stdout or "").strip()
assert "CHILD_TOK=None" in out, f"child should be blocked, got: {out} | err: {r.stderr[:300]}"
print("PASS child blocked while parent holds (concurrency 1 enforced cross-process)")

# release; child retry must now acquire
cg.release(tok)
r2 = subprocess.run([PY, "-c", CHILD], capture_output=True, text=True, timeout=60)
out2 = (r2.stdout or "").strip()
assert "CHILD_TOK=" in out2 and "None" not in out2.split("CHILD_TOK=")[1][:20], \
    f"child should acquire after release, got: {out2}"
print("PASS child acquires after release")

# status reflects reality
st = cg.status()
print("PASS gate status:", json.dumps(st))
print("ALL PASS")
