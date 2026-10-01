import json, subprocess, sys, time
from pathlib import Path

PY = r"c:\Users\foste\Documents\projects\local_sovereign_agent\.venv\Scripts\python.exe"
init = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "probe", "version": "1.0"},
    },
}
env = {"PYTHONPATH": r"c:\Users\foste\Documents\projects\local_sovereign_agent"}
try:
    p = subprocess.run(
        [PY, "-m", "mag.mcp_server"],
        input=json.dumps(init) + "\n",
        capture_output=True, text=True, timeout=25, env=env,
        cwd=r"c:\Users\foste\Documents\projects\local_sovereign_agent",
    )
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    print("rc=" + str(p.returncode))
    print("stdout=" + out[:300])
    print("stderr=" + err[:300])
    # did it answer initialize with a result?
    if out:
        try:
            j = json.loads(out)
            print("HANDSHAKE_OK result=" + str(j.get("result", {}).get("serverInfo", {})))
        except Exception as e:
            print("parse_err=" + str(e))
    else:
        print("NO_STDOUT (hung or silent)")
except subprocess.TimeoutExpired:
    print("TIMEOUT: mcp_server did not respond within 25s — THIS is the hang")
