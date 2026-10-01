"""Dropbox Watcher — catalog files dropped for research.

Watches a folder on the desktop. When files appear:
  1. Catalogs them (type, size, hash, date)
  2. Weaves a Bard passage for each
  3. Queues a research task if the content is novel
  4. Prompts the operator later: "You dropped X. Want me to research it?"

Linux path: ~/Desktop/Mag/Dropbox/
Windows path: ~/Desktop/Mag/Dropbox/

The folder is a PORTAL — drop anything in, Ghost catalogs it for later.
Never processes without asking. Never deletes. Never shares.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dropbox_path() -> Path:
    """Get the dropbox path, cross-platform (consolidated Desktop Mag/Dropbox)."""
    home = Path.home()
    desktop = home / "Desktop"
    if not desktop.is_dir():
        desktop = home / "desktop"
    if not desktop.is_dir():
        desktop = home
    return desktop / "Mag" / "Dropbox"


def init_dropbox() -> Path:
    """Create the dropbox folder if it doesn't exist. Returns the path."""
    path = _dropbox_path()
    path.mkdir(parents=True, exist_ok=True)

    # Create a README so the operator knows what this is
    readme = path / "README.md"
    if not readme.is_file():
        readme.write_text("""# Research Dropbox

Drop files here. Ghost will catalog them and ask if you want research run.

**What happens:**
1. You drop a file (PDF, URL list, markdown, image, anything)
2. Ghost catalogs it — type, size, hash, date
3. Ghost weaves a Bard passage: "The operator left a scroll in the dropbox..."
4. Ghost asks: "You dropped X. Want me to research it?"
5. If yes: Ghost queues a research task. If no: file stays cataloged for later.

**Nothing leaves this machine.** The dropbox is a local portal.
Files are never shared, never uploaded, never processed without asking.
""")

    # Create the catalog file
    catalog = path / "catalog.jsonl"
    if not catalog.is_file():
        catalog.write_text("")

    return path


def scan_dropbox() -> list[dict[str, Any]]:
    """Scan the dropbox for new files. Returns list of catalog entries."""
    path = _dropbox_path()
    if not path.is_dir():
        return []

    catalog_path = path / "catalog.jsonl"
    known_hashes = set()

    # Read existing catalog
    if catalog_path.is_file():
        for line in catalog_path.read_text().strip().splitlines():
            try:
                entry = json.loads(line)
                known_hashes.add(entry.get("hash", ""))
            except json.JSONDecodeError:
                continue

    new_entries: list[dict[str, Any]] = []

    for f in path.iterdir():
        if f.name in ("README.md", "catalog.jsonl", ".DS_Store"):
            continue
        if f.is_dir():
            continue

        try:
            content = f.read_bytes()
            file_hash = hashlib.sha256(content).hexdigest()

            if file_hash in known_hashes:
                continue

            entry = {
                "file": f.name,
                "path": str(f),
                "size": len(content),
                "hash": file_hash,
                "type": f.suffix.lower(),
                "cataloged_at": _now(),
                "researched": False,
                "operator_approved": False,
            }

            new_entries.append(entry)

            # Append to catalog
            with open(catalog_path, "a", encoding="utf-8") as cf:
                cf.write(json.dumps(entry) + "\n")

            known_hashes.add(file_hash)
        except OSError:
            continue

    return new_entries


def catalog_and_prompt() -> dict[str, Any]:
    """Scan dropbox, catalog new files, and generate prompts.

    Returns a dict with:
      - new_files: list of newly cataloged files
      - prompts: list of prompt strings to show the operator
      - bard_passages: narrative descriptions of each drop
    """
    init_dropbox()
    new_files = scan_dropbox()

    if not new_files:
        return {
            "new_files": [],
            "prompts": [],
            "bard_passages": [],
            "message": "Dropbox is empty. Drop files on ~/Desktop/Mag/Dropbox/",
        }

    prompts = []
    bard_passages = []

    for entry in new_files:
        name = entry["file"]
        size_kb = entry["size"] / 1024
        ftype = entry["type"]

        # Human prompt
        prompts.append(
            f"New in dropbox: **{name}** ({ftype}, {size_kb:.1f}KB). "
            f"Research it?"
        )

        # Bard passage
        bard_passages.append(
            f"The operator left a scroll in the dropbox: {name}, "
            f"{size_kb:.0f}KB of {ftype} parchment. "
            f"It awaits the librarian's sorting."
        )

        # Weave to Bard
        try:
            from mag.bard import bard_sense, bard_publish_sync
            passage = bard_sense({
                "type": "dropbox_catalog",
                "ts": _now(),
                "file": name,
                "size_kb": round(size_kb, 1),
                "file_type": ftype,
            })
            bard_publish_sync(passage, {"type": "dropbox_catalog"})
        except Exception:
            pass

    return {
        "new_files": new_files,
        "prompts": prompts,
        "bard_passages": bard_passages,
        "message": f"{len(new_files)} new file(s) cataloged. Awaiting operator approval for research.",
    }


def approve_research(file_hash: str) -> dict[str, Any]:
    """Operator approved research on a cataloged file. Queue the task."""
    path = _dropbox_path()
    catalog_path = path / "catalog.jsonl"
    if not catalog_path.is_file():
        return {"ok": False, "error": "No catalog found"}

    # Find the entry
    entry = None
    lines = catalog_path.read_text().strip().splitlines()
    for i, line in enumerate(lines):
        try:
            e = json.loads(line)
            if e.get("hash") == file_hash:
                entry = e
                e["operator_approved"] = True
                e["approved_at"] = _now()
                lines[i] = json.dumps(e)
                break
        except json.JSONDecodeError:
            continue

    if entry is None:
        return {"ok": False, "error": f"Hash {file_hash} not found in catalog"}

    # Update catalog
    catalog_path.write_text("\n".join(lines) + "\n")

    # Queue research task
    try:
        inbox_path = ROOT / "memory" / "copilot" / "inbox.jsonl"
        task = json.dumps({
            "id": f"dropbox-research-{file_hash[:12]}",
            "action": "exec",
            "goal": f"Research the file dropped by the operator: {entry['file']} ({entry['type']}, {entry['size']/1024:.0f}KB). Catalog findings. Do NOT share, upload, or transmit the file contents. Research is local only.",
            "provider": "xai",
            "model": "grok-3-mini",
            "timeout_s": 180,
            "ts": _now(),
            "source": "dropbox-research",
        })
        with open(inbox_path, "a", encoding="utf-8") as f:
            f.write(task + "\n")
    except Exception as e:
        return {"ok": False, "error": f"Failed to queue: {str(e)}"}

    return {
        "ok": True,
        "file": entry["file"],
        "queued": True,
        "message": f"Research queued for {entry['file']}. Check inbox for results.",
    }


def dropbox_status() -> dict[str, Any]:
    """Status of the dropbox — what's cataloged, what's researched, what's pending."""
    path = _dropbox_path()
    catalog_path = path / "catalog.jsonl"

    if not catalog_path.is_file():
        return {"ok": True, "files": [], "message": "No catalog yet. Drop files to start."}

    files = []
    for line in catalog_path.read_text().strip().splitlines():
        try:
            files.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return {
        "ok": True,
        "total": len(files),
        "pending_approval": sum(1 for f in files if not f.get("operator_approved")),
        "researched": sum(1 for f in files if f.get("researched")),
        "files": [
            {
                "name": f["file"],
                "type": f["type"],
                "size_kb": round(f["size"] / 1024, 1),
                "cataloged": f.get("cataloged_at", "")[:19],
                "approved": f.get("operator_approved", False),
                "researched": f.get("researched", False),
            }
            for f in files[-10:]  # Last 10
        ],
    }
