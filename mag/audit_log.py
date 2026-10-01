"""Minimal audit logging for demonstration."""

import json
import os
from pathlib import Path
from datetime import datetime

AUDIT_LOG_FILE = Path("memory/audit.log")

def audit_log(event_type: str, data: dict):
    """Log an audit event."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        "data": data,
        "session_id": os.environ.get("HERMES_SESSION_ID", "unknown")
    }
    AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
