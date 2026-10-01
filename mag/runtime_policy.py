"""ONE home for the Docker-only host runtime policy (state/DOCKER_ONLY).

Marker text (state/DOCKER_ONLY.stale-20260922): "Host Mag CLI and tests remain
available. Long-lived Ghost, autorun, and agent supervision must run inside
Docker. Set MAG_ALLOW_HOST_RUNTIME=1 only for deliberate operator maintenance."

Receipt (B2-51 autopsy, 2026-09-26). This policy used to live in three modules
(mag.governor_autorun, mag.ghost, mag.process_supervisor) as three private
copies of the marker path plus a predicate, and the copies disagreed: the child
copies gate on os.name == "nt", the supervisor gate did not.

Cause of the 2026-09-19 false crash-loop: the marker file was created
2026-08-30 22:56 -0400 and existed continuously until it was renamed
state/DOCKER_ONLY.stale-20260922 on 2026-09-22 (rename preserved the 8/30
mtime). The drainer child self-block landed 2026-09-14 (d575bc168). From then
on, every host spawn of the supervised default autorun loop printed
"[autorun] blocked: Docker-only runtime is active" and exited at startup, and
mag.process_supervisor.reap() classified that policy exit as a crash and
respawned it under crashLoopBackOff: supervisor.jsonl records 28 auto_restarts
of autorun on 2026-09-19 alone (bursts 15:06-15:08Z and 17:09-17:31:17Z; the
final four respawns at 17:30:39, 17:30:46, 17:31:02 and 17:31:17Z), with
earlier bursts on 09-14 (9) and 09-16 (44). logs/supervisor_autorun.out.log
holds 232 consecutive "[autorun] blocked" lines (lines 5477-5708); the
2026-09-19 gate comment's "5,708 'blocked' lines" misread that last line
number as a count, and its "marked 'crashed' for 20 days" claim is
unsupported by any log on disk. The gate (96b5f4b4e, 2026-09-19 21:58Z)
landed after the loop had already stopped respawning and logged zero
policy_blocked rows before the marker was renamed on 2026-09-22.

This module exists so the supervisor gate and the child self-block evaluate
the SAME predicate: a policy exit can never be mistaken for a crash by a
disagreeing copy again. Escape hatch: MAG_ALLOW_HOST_RUNTIME=1 for deliberate
operator maintenance.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCKER_ONLY_MARKER = ROOT / "state" / "DOCKER_ONLY"


def host_runtime_blocked(marker: Path | None = None, *, os_name: str | None = None) -> bool:
    """True when this host must not run long-lived Mag loops (drainer, ghost).

    Both the child loops (mag.governor_autorun, mag.ghost) and the process
    supervisor gate (mag.process_supervisor._policy_blocked) call this, so a
    policy-blocked exit is recognized as policy by the resurrector too.
    """
    return (
        (os_name or os.name) == "nt"
        and (marker or DOCKER_ONLY_MARKER).is_file()
        and os.environ.get("MAG_ALLOW_HOST_RUNTIME") != "1"
    )
