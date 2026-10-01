# Remote Direct Mag

Remote Direct Mag is a narrow tablet/phone control surface for filing work into
Mag. It is intentionally separate from the full dashboard: remote devices can
read handoff readiness and queue an outcome, but cannot run arbitrary shell
commands or approve tools.

## Start it on the PC

In PowerShell, set a private token of at least 24 characters for this session:

```powershell
$env:MAG_REMOTE_TOKEN = "replace-with-a-long-private-random-token"
.venv\Scripts\python.exe main.py cast --lan
```

The start banner prints the PC address. On a device using the same Wi-Fi, open:

```text
http://PC-ADDRESS:8766/control
```

Enter the same token. It remains in the page only while that page is open.

## What happens after Route and queue

1. Mag creates the platform-agnostic `mag_intent.v1` routing envelope.
2. The intent is filed as a durable peer handoff.
3. The governor routes it to the cheapest capable provider and queues it.
4. A hashed receipt and a private training event preserve what was decided.
5. Existing trust, drainer, privacy, and evidence gates still decide whether
   queued work may execute and whether its result may graduate into training.

The full dashboard on port 8765 should remain local. Only the narrow cast/control
service on port 8766 is intended for LAN access.

## Let Mag choose the next roadmap branch

From PowerShell, run:

```powershell
.\run_roadmap.ps1
```

This does not ask for a new goal. It reads `configs/version_roadmap.yaml` and
`configs/releases.yaml`, skips gates already recorded green, freezes the next
gate-sized BUILD, creates its roadmap branch, and runs the factory. Versions
whose curriculum is still `TBD` fail closed instead of inventing work.
