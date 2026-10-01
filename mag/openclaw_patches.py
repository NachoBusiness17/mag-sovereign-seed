"""Apply OpenClaw-proposed edits through Mag's write jail.

OpenClaw's cage mounts Mag DNA read-only (Linux container, Windows venv).
It writes patch JSON to queue/handoff/openclaw/PATCHES; this module applies
them on the host with write_file (search/replace + snapshot + py_compile).

    .\\.venv\\Scripts\\python.exe -m mag.openclaw_patches apply
    .\\.venv\\Scripts\\python.exe -m mag.openclaw_patches status
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "queue" / "handoff" / "openclaw" / "PATCHES"
APPLIED = INBOX / "applied"
REJECTED = INBOX / "rejected"
APPLY_LOG = ROOT / "memory" / "runs" / "openclaw_patches" / "apply.jsonl"
SCHEMA = "openclaw_patch.v1"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _move(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        dest = dest_dir / f"{src.stem}-{_utc().replace(':', '')}{src.suffix}"
    shutil.move(str(src), str(dest))
    return dest


def apply_one(payload: dict[str, Any]) -> dict[str, Any]:
    from tools.filesystem import write_file

    path = str(payload.get("path") or "").strip()
    if not path:
        return {"ok": False, "error": "missing path"}
    kwargs: dict[str, Any] = {"path": path}
    if payload.get("snapshot"):
        kwargs["snapshot"] = str(payload["snapshot"])
    if payload.get("search") is not None:
        # Patch JSON is often authored on Windows (CRLF), while the write jail
        # reads text with universal-newline normalization. Match the jail's
        # representation so a valid patch is not falsely orphaned by EOL drift.
        kwargs["search"] = str(payload["search"]).replace("\r\n", "\n")
        kwargs["replace"] = str(payload.get("replace") or "").replace("\r\n", "\n")
    elif payload.get("content") is not None:
        content = payload["content"]
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False, indent=2) + "\n"
        if not isinstance(content, str):
            return {"ok": False, "error": "content must be a string, object, or array"}
        kwargs["content"] = content
    else:
        return {"ok": False, "error": "need search+replace or content"}
    return write_file(**kwargs)


def _target_for(raw_path: Any) -> tuple[Path | None, str | None]:
    """Resolve a patch target without allowing it to escape the repository."""
    raw = str(raw_path or "").strip()
    if not raw:
        return None, "missing path"
    normalized = raw.replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute():
        return None, "absolute paths are not allowed"
    target = (ROOT / candidate).resolve()
    try:
        relative = target.relative_to(ROOT.resolve())
    except ValueError:
        return None, "target escapes repository"
    return target, str(relative).replace(os.sep, "/")


def preflight() -> dict[str, Any]:
    """Validate the pending queue without writing or moving anything."""
    if not INBOX.is_dir():
        return {"ok": False, "schema": "openclaw_patch_preflight.v1",
                "queue": str(INBOX.relative_to(ROOT)).replace(os.sep, "/"),
                "pending_n": 0, "rows": [], "duplicate_targets": {},
                "warnings": [], "errors": [f"missing queue: {INBOX}"]}
    files = sorted(p for p in INBOX.glob("*.json") if p.is_file())
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    targets: dict[str, list[str]] = {}

    for src in files:
        row: dict[str, Any] = {"file": src.name}
        try:
            payload = json.loads(src.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            row.update({"ok": False, "error": f"bad json: {exc}"})
            errors.append(f"{src.name}: bad json: {exc}")
            rows.append(row)
            continue
        if not isinstance(payload, dict):
            row.update({"ok": False, "error": "payload must be a JSON object"})
            errors.append(f"{src.name}: payload must be a JSON object")
            rows.append(row)
            continue

        target, target_result = _target_for(payload.get("path"))
        if target is None:
            row.update({"ok": False, "error": target_result})
            errors.append(f"{src.name}: {target_result}")
            rows.append(row)
            continue
        row["path"] = target_result
        targets.setdefault(target_result or "", []).append(src.name)
        has_search = "search" in payload and payload.get("search") is not None
        has_content = "content" in payload and payload.get("content") is not None
        if has_search == has_content:
            error = "provide exactly one of search or content"
            row.update({"ok": False, "error": error})
            errors.append(f"{src.name}: {error}")
            rows.append(row)
            continue

        if has_content:
            if not isinstance(payload.get("content"), (str, dict, list)):
                error = "content must be a string, object, or array"
                row.update({"ok": False, "error": error})
                errors.append(f"{src.name}: {error}")
                rows.append(row)
                continue
            row.update({"mode": "content", "target_exists": target.is_file(), "ok": True})
        else:
            search = str(payload.get("search")).replace("\r\n", "\n")
            if not isinstance(search, str) or not search:
                error = "search must be a non-empty string"
                row.update({"ok": False, "error": error})
                errors.append(f"{src.name}: {error}")
                rows.append(row)
                continue
            if "replace" not in payload or not isinstance(payload.get("replace"), str):
                error = "search patch requires a string replace field"
                row.update({"ok": False, "error": error})
                errors.append(f"{src.name}: {error}")
                rows.append(row)
                continue
            if not target.is_file():
                error = f"target does not exist: {target_result}"
                row.update({"ok": False, "error": error})
                errors.append(f"{src.name}: {error}")
                rows.append(row)
                continue
            try:
                text = target.read_text(encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                error = f"target is unreadable: {exc}"
                row.update({"ok": False, "error": error})
                errors.append(f"{src.name}: {error}")
                rows.append(row)
                continue
            found = search in text
            row.update({"mode": "search", "target_exists": True, "search_match": found,
                        "line_ending_normalized": payload.get("search") != search,
                        "match_count": text.count(search), "ok": found})
            if not found:
                error = "search string not found in target"
                row["error"] = error
                errors.append(f"{src.name}: {error}")
        rows.append(row)

    duplicate_targets = {path: names for path, names in targets.items() if len(names) > 1}
    for path, names in duplicate_targets.items():
        warnings.append(f"multiple patches target {path}; apply order: {', '.join(names)}")

    return {
        "ok": not errors,
        "schema": "openclaw_patch_preflight.v1",
        "queue": str(INBOX.relative_to(ROOT)).replace(os.sep, "/"),
        "pending_n": len(files),
        "rows": rows,
        "duplicate_targets": duplicate_targets,
        "warnings": warnings,
        "errors": errors,
    }


def _append_receipt(row: dict[str, Any]) -> bool:
    """Commit one durable apply receipt; callers surface failures explicitly."""
    try:
        APPLY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with APPLY_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"schema": "openclaw_patch_receipt.v1",
                                     "ts": _utc(), **row}, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def apply_inbox() -> dict[str, Any]:
    INBOX.mkdir(parents=True, exist_ok=True)
    check = preflight()
    files = sorted(p for p in INBOX.glob("*.json") if p.is_file())
    rows: list[dict[str, Any]] = []
    for src in files:
        try:
            payload = json.loads(src.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            dest = _move(src, REJECTED)
            row = {"file": src.name, "ok": False, "error": f"bad json: {e}", "moved": str(dest)}
            row["receipt_committed"] = _append_receipt(row)
            rows.append(row)
            continue
        result = apply_one(payload if isinstance(payload, dict) else {})
        dest = _move(src, APPLIED if result.get("ok") else REJECTED)
        row = {"file": src.name, "ok": bool(result.get("ok")),
               "path": result.get("path"), "error": result.get("error"),
               "moved": str(dest.relative_to(ROOT))}
        row["receipt_committed"] = _append_receipt(row)
        rows.append(row)
    applied = sum(1 for r in rows if r["ok"])
    rejected = sum(1 for r in rows if not r["ok"])
    receipts_missing = sum(1 for r in rows if not r.get("receipt_committed"))
    return {"ok": rejected == 0 and receipts_missing == 0, "schema": SCHEMA,
            "applied": applied, "rejected": rejected,
            "receipts_missing": receipts_missing, "rows": rows,
            "preflight": check}


def status() -> dict[str, Any]:
    pending = sorted(p.name for p in INBOX.glob("*.json") if p.is_file()) if INBOX.is_dir() else []
    applied = sorted(p.name for p in APPLIED.glob("*.json")) if APPLIED.is_dir() else []
    rejected = sorted(p.name for p in REJECTED.glob("*.json")) if REJECTED.is_dir() else []
    return {"ok": True, "schema": SCHEMA, "pending": pending, "pending_n": len(pending),
            "applied_n": len(applied), "rejected_n": len(rejected)}


def main(argv: list[str] | None = None) -> int:
    cmd = (argv or sys.argv[1:] or ["status"])
    verb = cmd[0] if cmd else "status"
    out = apply_inbox() if verb == "apply" else preflight() if verb == "preflight" else status()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
