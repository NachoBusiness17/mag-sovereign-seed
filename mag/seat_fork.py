# seat_fork.py — fork a new seat branch from a frozen verkle tip
"""
Fork the frozen verkle chain tip into a new seat branch.
Writes a seat brief and returns the new seat's branch tip hash.
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime


def fork_seat(config_path: str) -> str:
    """Fork a seat from the frozen tip."""
    config = json.loads(Path(config_path).read_text())
    frozen_tip_hash = config["frozen_tip_hash"]
    persona = config["persona"]
    session_domain = config["session_domain"]
    wave_width = config.get("wave_width", 8)

    # 1) Compute new seat branch tip hash (simplified: hash of config + timestamp)
    payload = {
        "frozen_tip": frozen_tip_hash,
        "persona": persona,
        "session_domain": session_domain,
        "wave_width": wave_width,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    seat_branch_tip = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    # 2) Write seat brief
    seat_id = f"hofw_{session_domain}"
    brief_path = Path(f"memory/briefs/{seat_id}_brief.md")
    brief_path.write_text(
        f"# Seat Brief — {seat_id}\n"
        f"\n"
        f"- Forked from frozen tip: `{frozen_tip_hash}`\n"
        f"- Persona: `{persona}`\n"
        f"- Session domain: `{session_domain}`\n"
        f"- Wave width: {wave_width}\n"
        f"- Seat branch tip: `{seat_branch_tip}`\n"
        f"- Created: {payload['timestamp']}\n"
    )

    # 3) Write receipt
    receipt = {
        "seat_id": seat_id,
        "frozen_tip_hash": frozen_tip_hash,
        "persona": persona,
        "session_domain": session_domain,
        "wave_width": wave_width,
        "seat_branch_tip": seat_branch_tip,
        "start_time": payload["timestamp"],
        "end_time": None,
        "artifact_hash": None,
        "status": "started"
    }
    receipt_path = Path(f"memory/runs/hermes_jobs/{seat_id}_receipt.jsonl")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")

    return seat_branch_tip


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python mag/seat_fork.py configs/seat_fork.yaml", file=sys.stderr)
        sys.exit(1)
    tip = fork_seat(sys.argv[1])
    print(tip)
