"""Icon Drop — the human-doorway surface on the operator's Desktop.

When ghost hits an action it CANNOT automate (secret entry, extension reload,
lab restart, manual Vast launch, one-off operator decision), it must NOT nag
the operator in chat. It DROPS a clickable icon into the Desktop "Mag/Tools"
folder and the operator clicks it when ready.

This is the trained behavior (see memory/operator_directives law #8 "don't nag"):
  can't automate? -> drop an icon, one line, move on.

Surfaces:
  Desktop\Mag\Tools\<name>.cmd   — double-click launcher (operator clicks it)
  memory/icons/ledger.jsonl      — which icons are pending / clicked
  skill_ledger + training_events (operator_behavior) — folded case law

CLI:
  python -m mag.icon_drop ensure
  python -m mag.icon_drop list
  python -m mag.icon_drop drop NAME "COMMAND" --desc "what it does"

SPEC (B2-414, 2026-09-26): a plain .cmd cannot carry an icon; the icon
belongs on a .lnk shortcut via drop_shortcut's IconLocation. Accordingly the
old ico_line ("start "" /D "%CD%" /B", a line that launched nothing and never
referenced the icon path) is removed from drop()'s .cmd body, and when an
icon is supplied drop() lays a companion <name>.lnk pointing at the .cmd
with the icon set. auto() keeps passing mag_agent.ico, so every known-action
drop now carries a real icon on the .lnk instead of a dead line in the .cmd.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

ICON_FOLDER_NAME = "Mag"
ICON_SUBFOLDER = "Tools"
LEDGER = ROOT / "memory" / "icons" / "ledger.jsonl"
ROOT_CMD = ROOT / "mag_agent.ico"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def desktop_folder() -> Path:
    """Resolve the Desktop Mag/Tools folder (the icon-drop surface)."""
    import os
    try:
        import ctypes.wintypes
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buf)  # CSIDL_DESKTOPDIRECTORY
        desktop = Path(buf.value)
    except Exception:
        desktop = Path.home() / "Desktop"
    if not desktop.is_dir():
        desktop = Path.home()
    folder = desktop / ICON_FOLDER_NAME / ICON_SUBFOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _append_ledger(row: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _ps_quote(value: Any) -> str:
    # B2-377 2026-09-26: drop_shortcut interpolated target_path/args/desc/icon
    # into single-quoted PowerShell literals raw, so a single quote in any
    # operator-chosen field terminated the PS string early (powershell exit 1
    # ParserError "The string is missing the terminator: '", no .lnk; proof
    # watch/inbox/burn_wave_20260926/B2_354_falsifier_probe_results.json
    # arm B). Inside a PS single-quoted literal the only escape is doubling
    # the quote, so every literal goes through here.
    return "'" + str(value).replace("'", "''") + "'"


def _cmd_echo_safe(value: str) -> str:
    # B2-377 2026-09-26: drop() echoed desc and command into the .cmd raw, so
    # batch metacharacters (& | < > ^) split or executed on the echo line and
    # a bare % ran variable expansion. % is doubled (the batch-file percent
    # escape), the metacharacters are caret-prefixed, and CR/LF is collapsed
    # to spaces (a newline in a field would inject a new batch line).
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = text.replace("%", "%%")
    for ch in "^&|<>":
        text = text.replace(ch, "^" + ch)
    return text


def _cmd_single_line(value: str) -> str:
    # B2-377 2026-09-26: the command line must run verbatim (e.g. the %VAR%
    # in "notepad %USERPROFILE%\.env" has to expand at click time), but an
    # embedded CR/LF would terminate it early and run the remainder as a new
    # batch line; collapse those to spaces, change nothing else.
    return str(value).replace("\r", " ").replace("\n", " ")


def drop(name: str, command: str, *, desc: str = "", icon: str | None = None) -> dict[str, Any]:
    """Write a double-clickable .cmd launcher into Desktop\Mag\Tools.

    The operator clicks it deliberately — this is the HUMAN-doorway surface,
    so a visible console window on click is correct and intended.
    """
    safe = "".join(c for c in name if c.isalnum() or c in " _-")
    folder = desktop_folder()
    target = folder / f"{safe}.cmd"

    # B2-414: no ico_line in the .cmd. The old line ('start "" /D "%CD%" /B')
    # was an f-string with no placeholders that launched nothing and never
    # referenced the icon path; a .cmd cannot carry an icon at all, so the
    # icon goes on a companion .lnk (drop_shortcut IconLocation) after the
    # .cmd is written.
    cmd_text = (
        "@echo off\r\n"
        "title Mag Action — {name}\r\n"
        "cd /d \"{root}\"\r\n"
        "echo.\r\n"
        "echo  M A G   A C T I O N\r\n"
        "echo  {name}\r\n"
        "{desc_line}"
        "echo.\r\n"
        "echo  Running: {command_echo}\r\n"
        "echo.\r\n"
        "{command}\r\n"
        "echo.\r\n"
        "echo  Done. Window will close in 8s...\r\n"
        "timeout /t 8 /nobreak >nul\r\n"
    ).format(
        name=safe,
        root=ROOT,
        desc_line=(f"echo  {_cmd_echo_safe(desc)}\r\n" if desc else ""),
        command_echo=_cmd_echo_safe(command),
        command=_cmd_single_line(command),
    )

    # B2-377 2026-09-26: newline="" so the embedded \r\n lands verbatim; the
    # default write translation re-expanded every \n and the .cmd carried
    # \r\r\n (CRCRLF) line endings on disk (byte-probed 2026-09-26 before
    # this fix: b'@echo off\r\r\ntitle ...').
    target.write_text(cmd_text, encoding="utf-8", newline="")

    row = {
        "schema": "icon_drop.v1",
        "ts": _now(),
        "name": safe,
        "path": str(target),
        "command": command[:300],
        "desc": desc,
        "status": "dropped",
    }
    # B2-414: the icon thread lands here — a companion .lnk (same safe name)
    # pointing at the .cmd, carrying the icon via IconLocation. drop_shortcut
    # keeps its own honest ledger row; the .cmd row notes the companion.
    if icon and Path(icon).is_file():
        lnk_row = drop_shortcut(safe, str(target), "", icon=icon, desc=desc)
        row["companion_lnk"] = str(lnk_row.get("path") or "")
        row["companion_status"] = str(lnk_row.get("status") or "unknown")
    _append_ledger(row)
    row["fold_status"] = _fold_training(row)  # B2-411: named fold failure surface
    return row


def drop_shortcut(name: str, target_path: str, args: str = "", *, icon: str | None = None, desc: str = "") -> dict[str, Any]:
    """Create a real .lnk shortcut (for launching .cmd / .exe with an icon)."""
    import subprocess
    # B2-377 2026-09-26: the name builds a filesystem path, so it gets the
    # same filter drop() applies before it reaches the .lnk filename and the
    # ledger rows; target_path/args/desc/icon stay verbatim behind quoting.
    safe = "".join(c for c in name if c.isalnum() or c in " _-")
    folder = desktop_folder()
    lnk = folder / f"{safe}.lnk"
    # B2-377 2026-09-26: every literal below goes through _ps_quote; raw
    # interpolation died on the first single quote in any operator-chosen
    # field (B2-354 probe arm B: powershell exit 1 ParserError, no .lnk).
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut"
        f"({_ps_quote(lnk)});$s.TargetPath={_ps_quote(target_path)};"
        f"$s.Arguments={_ps_quote(args)};$s.WorkingDirectory={_ps_quote(ROOT)};"
        + (f"$s.IconLocation={_ps_quote(icon)};" if icon else "")
        + f"$s.Description={_ps_quote(desc)};$s.Save()"
    )
    # B2-85 2026-09-26: bare "powershell" is not on PATH in every launch
    # context (sig run_shell:e566037def80 "[Errno 2] ... powershell",
    # 7,964 FKB rows since 2026-09-19). Resolve the full path; System32
    # fallback when PATH lookup misses (pattern mag/process_reaper.py).
    ps_exe = shutil.which("powershell") or shutil.which("powershell.exe")
    if not ps_exe and sys.platform == "win32":
        ps_exe = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    if not ps_exe:
        # honest ledger: never write status "dropped" for a shortcut that did
        # not run (no-fabrication law); the operator sees the skip by name.
        row = {
            "schema": "icon_drop.lnk.v1",
            "ts": _now(),
            "name": safe,
            "path": str(lnk),
            "target": target_path,
            "desc": desc,
            "status": "skipped_no_powershell",
        }
        _append_ledger(row)
        row["fold_status"] = _fold_training(row)  # B2-411: named fold failure surface
        return row
    # B2-354 2026-09-26: check=False plus an unconditional status "dropped" let
    # a failed WScript.Shell Save (nonzero powershell exit, or exit 0 with no
    # .lnk materialized) land a dropped ledger row with no shortcut on disk
    # (falsifier: a drop_shortcut whose powershell exits nonzero must not
    # record dropped; brief self-fed by
    # watch/inbox/burn_wave_20260926/B2_85_powershell_fix_20260926.md).
    # Capture stderr, then require BOTH exit 0 and the .lnk existing before
    # "dropped"; otherwise record a failed status naming the error.
    proc = subprocess.run([ps_exe, "-NoProfile", "-Command", ps],
                          capture_output=True, text=True, check=False,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0)
    lnk_ok = lnk.is_file()
    if proc.returncode == 0 and lnk_ok:
        row = {
            "schema": "icon_drop.lnk.v1",
            "ts": _now(),
            "name": safe,
            "path": str(lnk),
            "target": target_path,
            "desc": desc,
            "status": "dropped",
        }
    else:
        # honest ledger (no-fabrication law): the operator sees the failure by
        # name, never a dropped row for a shortcut that is not on disk.
        tail = ""
        for stream in (proc.stderr, proc.stdout):
            text = (stream or "").strip()
            if text:
                tail = text[-300:]
                break
        reasons = []
        if proc.returncode != 0:
            reasons.append(f"powershell exit {proc.returncode}")
        if not lnk_ok:
            reasons.append("no .lnk on disk after run")
        row = {
            "schema": "icon_drop.lnk.v1",
            "ts": _now(),
            "name": safe,
            "path": str(lnk),
            "target": target_path,
            "desc": desc,
            "status": "failed",
            "error": "; ".join(reasons) + (f"; {tail}" if tail else ""),
        }
    _append_ledger(row)
    row["fold_status"] = _fold_training(row)  # B2-411: named fold failure surface
    return row


def _fold_training(row: dict[str, Any]) -> dict[str, Any]:
    """Surface the lesson: operator-only action -> icon dropped, not a chat nag.

    B2-378 2026-09-26: outcome is the row status passed through, "ok" only
    when the status is "dropped", otherwise the status string verbatim
    ("failed", "skipped_no_powershell"). Cause: the hardcoded outcome "ok"
    folded every icon_drop row as a win in the operator_behavior case law
    (skill_ledger ok_rate counts outcome == "ok"), so the failed and skipped
    drop_shortcut rows that B2-354 made honest in the icons ledger were still
    counted as wins here; fixed on the brief
    watch/inbox/burn_wave_20260926/B2_378_fold_outcome_20260926.md, falsifier
    probe watch/inbox/burn_wave_20260926/B2_378_falsifier_probe.py.

    B2-411 2026-09-26: the fold failure is no longer silent. The whole fold
    body used to sit behind a bare `except Exception: pass`, so a broken fold
    (skill_ledger append error, training_events schema drift, import failure)
    left the drop landed but the case-law edge missing with no signal
    anywhere. Returns a bounded fold_status dict {ok, outcome?, error?} that
    the callers stamp onto the caller-visible row as "fold_status", and logs
    one WARNING line to stderr. Never raises: the drop path must not break
    because the case-law fold is broken (the brief's exact constraint).
    """
    try:
        from mag import skill_ledger, training_events
        status = str(row.get("status") or "unknown")
        skill_ledger.record_decision(
            goal="human-only action routing",
            task_shape="operator_action",
            provider="local",
            model="icon_drop",
            reasoning_level="none",
            source="icon_drop",
            outcome="ok" if status == "dropped" else status,
            detail=f"icon {row.get('name')} status {status} for operator click (no chat nag)",
        )
        training_events.emit(
            "operator_behavior",
            action={"kind": "icon_drop", "name": row.get("name")},
            outcome={"status": row.get("status"), "path": row.get("path")},
            pattern_tags=["desktop_icons", "donot_nag", "human_doorway"],
            tier_max="T1",
            exportable=False,
        )
        return {"ok": True, "outcome": "ok" if status == "dropped" else status}
    except Exception as exc:
        surface = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
        print(f"WARNING: [icon_drop] fold_training failed, case-law edge missing "
              f"for {row.get('name')}: {surface['error']}", file=sys.stderr)
        return surface


# Keyword -> (icon name, command, desc) for KNOWN operator-only actions that
# cannot be automated. When ghost hits one of these, it drops the icon and moves
# on (never nags in chat).
_KNOWN: dict[str, tuple[str, str, str]] = {
    "reload": ("Reload VS Code", "code --reuse-window .", "Reload/reopen the VS Code window (extension + agent reload)"),
    "restart lab": ("Lab Restart", "python -m mag.lifecycle restart_lab --port 8765", "Restart the dashboard lab on 8765"),
    "restart_lab": ("Lab Restart", "python -m mag.lifecycle restart_lab --port 8765", "Restart the dashboard lab on 8765"),
    "vast": ("Launch Vast Training", "python -m mag.vast_launcher launch_training", "Launch the Vast training run (needs VAST_API_KEY set)"),
    "secret": ("Set Secret (operator)", "notepad %USERPROFILE%\.env", "Set a secret/env value by hand (operator-only)"),
    "container": ("Mag Container", "launch_mag_container.cmd", "Bring up the Mag container (docker)"),
}


def auto(prompt: str) -> dict[str, Any]:
    """Route a human-only action to an icon drop. Returns the plan + dropped icon.

    If no known action matches, return a dry plan (no drop) so the caller can
    decide — we never guess-drop into the operator's Desktop folder.
    """
    t = (prompt or "").lower()
    for key, (name, cmd, desc) in _KNOWN.items():
        if key in t:
            row = drop(name, cmd, desc=desc, icon=str(ROOT_CMD) if ROOT_CMD.is_file() else None)
            return {"schema": "icon_drop.auto.v1", "ts": _now(), "ok": True,
                    "matched": key, "dropped": row}
    return {"schema": "icon_drop.auto.v1", "ts": _now(), "ok": True,
            "matched": None, "note": "no known human-only action matched; nothing dropped"}


def list_icons() -> list[dict[str, Any]]:
    folder = desktop_folder()
    icons = []
    for f in sorted(folder.glob("*.cmd")) + sorted(folder.glob("*.lnk")):
        icons.append({"name": f.stem, "path": str(f)})
    return icons


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="mag.icon_drop")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ensure = sub.add_parser("ensure")
    p_ensure.set_defaults(fn=lambda a: print(desktop_folder()))

    p_list = sub.add_parser("list")
    p_list.set_defaults(fn=lambda a: print(json.dumps(list_icons(), indent=2)))

    p_drop = sub.add_parser("drop")
    p_drop.add_argument("name")
    p_drop.add_argument("command")
    p_drop.add_argument("--desc", default="")
    p_drop.add_argument("--icon", default=None)
    p_drop.set_defaults(fn=lambda a: print(json.dumps(drop(a.name, a.command, desc=a.desc, icon=a.icon), indent=2)))

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
