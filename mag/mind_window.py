"""mind_window — turn raw VS Code session transcripts into a SANITIZED "window into the mind".

WHY (operator 2026-08-23): "i have mine logging all of my vs code sessions. I could use my
riddler protocol to get rid of personal data and maybe provide it for understanding of how we
process things internally as a window into the mind."

The RIDDLER discipline, applied as redaction instead of full surrogate-compilation:
  * WITHHOLD THE TERRITORY, KEEP THE SHAPE. Strip and generalize the personal/private specifics
    (real names, handles, home paths, secrets, private orgs, billing figures) while preserving
    the REAL reasoning — the corrections, the refusals, the shadow-work, the method.
  * HONESTY, NOT THE WARM LIE: we never fabricate the shape. The reasoning is real, only the
    identifying specifics are withheld. Every replacement is recorded in a REDACTION LEDGER so
    the artifact is auditable, not a black box.

The raw transcripts are VS Code's session logs: JSONL files (one event per line) under
GitHub.copilot-chat/transcripts/<sessionId>.jsonl. Event types we parse:
  session.start, user.message, assistant.message (content + toolRequests), assistant.turn_*,
  tool.execution_start / tool.execution_complete.

Schema: mind_window.v1
CLI: python -m mag.mind_window transcript <file.jsonl>  |  digest <file...>  |  export --out DIR <file...>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "mind_window.v1"

# ────────────────────────────────────────────────────────────────────────────────────────────
# TERRITORY CONFIG — what we withhold, and what we keep.
# Keep the SHAPE (the conceptual method, the system's own vocabulary, the reasoning). Withhold
# the TERRITORY (what identifies a specific human / machine / private relationship / spend).
# Every entry here is applied as redaction and logged in the ledger. Over-redact rather than leak.
# ────────────────────────────────────────────────────────────────────────────────────────────

# Sealed secret patterns (reuse the bus-guard / embassy publish-gate shapes).
_SECRET_PATTERNS: list[tuple[str, str]] = [
    # provider keys / tokens
    (r"sk-or-v1-[A-Za-z0-9_\-]{16,}", "secret:or-token"),
    (r"xai-[A-Za-z0-9]{20,}", "secret:xai-token"),
    (r"gsk_[A-Za-z0-9]{20,}", "secret:gsk-token"),
    (r"sk-[A-Za-z0-9]{20,}", "secret:sk-token"),
    (r"Bearer [A-Za-z0-9._\-]{16,}", "secret:bearer"),
    # assignments like SOMETHING_API_KEY=..., / secret = "..."
    (r"\b[A-Z][A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD)\b\s*[:=]\s*[\"']?[A-Za-z0-9._\-]{8,}", "secret:key-assign"),
    # high-entropy blob: long mixed-case/digit/symbol token that is NOT a content hash
    (r"\b[A-Za-z0-9_\-]{28,}\b", "secret:high-entropy"),
]

# Identity / territory literals: exact strings to replace (case-insensitive), mapped to a safe
# placeholder. Order matters (longest/most specific first).
_IDENTITY_MAP: list[tuple[str, str]] = [
    # GitHub handles / orgs (longest first so the full handle wins over the bare name)
    ("NachoBusiness17", "<op-handle>"),
    ("NachoQuixotic", "<op-handle>"),
    ("AdventureNLearn", "<partner-org>"),
    ("embassy-t1", "<partner-repo>"),
    # the operator's bare name -> role token (withhold the person, keep the role)
    ("nacho", "<operator>"),
    # machine / user
    ("c:\\users\\ESTATE_USER", "<home>"),
    ("c:/users/ESTATE_USER", "<home>"),
    ("/users/ESTATE_USER", "<home>"),
    ("ESTATE_USER", "<user>"),
]

# Identity / territory regexes (case-insensitive).
_IDENTITY_RE: list[tuple[str, str, str]] = [
    (r"[a-zA-Z]:\\Users\\[A-Za-z0-9_.\-]+", "<home-path>", "identity:win-path"),
    (r"/Users/[A-Za-z0-9_.\-]+", "<home-path>", "identity:posix-path"),
    (r"@[A-Za-z0-9_]{2,40}", "<handle>", "identity:handle"),
    # real dollar figures (billing/spend territory)
    (r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?", "<amount>", "territory:amount"),
]

# Known private territory literals (project codenames / private relationship specifics).
_TERRITORY_MAP: list[tuple[str, str]] = [
    # Add private codenames here as needed. Kept deliberately short: prefer the general identity
    # layer to over-match. The system's own conceptual vocabulary is KEPT (that is the shape).
]

# Content hashes / root hashes are the byte-treaty's currency and are PUBLIC — never redact them
# (bus-guard lesson: a guard that flags the treaty's own currency defeats the treaty).
_HASH_OK = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")


# ────────────────────────────────────────────────────────────────────────────────────────────
# Redaction
# ────────────────────────────────────────────────────────────────────────────────────────────
def _entropy(tok: str) -> float:
    """Shannon entropy per char (bits). Lowercase hex ~4.0; real keys ~5.8+."""
    if not tok:
        return 0.0
    import math
    counts: dict[str, int] = {}
    for ch in tok:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(tok)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _is_content_hash(tok: str) -> bool:
    return bool(_HASH_OK.match(tok)) or (tok.isalnum() and len(tok) >= 32 and _entropy(tok) < 4.5
                                         and tok.islower())


def redact(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Return (safe_text, ledger). Ledger records each replacement type + count (no raw secrets)."""
    ledger: list[dict[str, Any]] = []
    safe = text

    # 1) literals first (longest first) — identity + territory exact strings
    for literal, placeholder in sorted(_IDENTITY_MAP + _TERRITORY_MAP,
                                       key=lambda kv: -len(kv[0])):
        pat = re.compile(re.escape(literal), re.IGNORECASE)
        n = len(pat.findall(safe))
        if n:
            safe = pat.sub(placeholder, safe)
            ledger.append({"layer": "identity", "type": "literal", "target": placeholder,
                           "count": n})

    # 2) secret patterns
    for pattern, kind in _SECRET_PATTERNS:
        pat = re.compile(pattern)
        for m in pat.finditer(safe):
            tok = m.group(0).strip()
            # don't redact public content hashes / hex roots
            if kind == "secret:high-entropy" and _is_content_hash(tok):
                continue
            safe = safe.replace(m.group(0), f"<redacted:{kind}>", 1)
            ledger.append({"layer": "secret", "type": kind, "target": f"<redacted:{kind}>",
                           "count": 1})

    # 3) identity regexes
    for pattern, placeholder, kind in _IDENTITY_RE:
        pat = re.compile(pattern, re.IGNORECASE)
        n = len(pat.findall(safe))
        if n:
            safe = pat.sub(placeholder, safe)
            ledger.append({"layer": "identity", "type": kind, "target": placeholder, "count": n})

    # merge + summarize ledger (dedupe identical (layer,type,target) rows)
    merged: dict[tuple[str, str, str], int] = {}
    for e in ledger:
        k = (e["layer"], e["type"], e["target"])
        merged[k] = merged.get(k, 0) + e["count"]
    final_ledger = [{"layer": l, "type": t, "target": p, "count": c}
                    for (l, t, p), c in sorted(merged.items(),
                                               key=lambda kv: (-kv[1], kv[0][1]))]
    return safe, final_ledger


# ────────────────────────────────────────────────────────────────────────────────────────────
# Ingest
# ────────────────────────────────────────────────────────────────────────────────────────────
def ingest_transcript(path: str | Path) -> list[dict[str, Any]]:
    """Parse a VS Code session transcript JSONL into ordered, flat events.

    Each event: {kind, ts, speaker, content, tools}. We keep tool NAMES (the method — which tools
    were used) but drop tool ARGUMENTS (they carry paths/secrets/private specifics). The full
    arguments never enter the sanitized artifact — withheld by construction, not by regex.
    """
    events: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            typ = ev.get("type", "")
            data = ev.get("data") or {}
            ts = ev.get("timestamp") or data.get("startTime") or ""
            base = {"kind": typ, "ts": ts}
            if typ == "session.start":
                base["session_id"] = data.get("sessionId", "")
                base["producer"] = data.get("producer", "")
            elif typ == "user.message":
                base["speaker"] = "human"
                base["content"] = (data.get("content") or "")
            elif typ == "assistant.message":
                base["speaker"] = "agent"
                base["content"] = (data.get("content") or "")
                tools = [(tr.get("name") or "") for tr in (data.get("toolRequests") or [])
                         if tr.get("name")]
                base["tools"] = [t for t in tools if t]  # names only; args withheld
            elif typ in ("assistant.turn_start", "assistant.turn_end",
                         "tool.execution_start", "tool.execution_complete"):
                base["speaker"] = "agent"
            else:
                continue
            events.append(base)
    return events


# ────────────────────────────────────────────────────────────────────────────────────────────
# Process (sanitize) a session
# ────────────────────────────────────────────────────────────────────────────────────────────
def _merge_ledger(ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse per-event redaction rows into a clean session-level summary (sum counts)."""
    merged: dict[tuple[str, str, str], int] = {}
    for e in ledger:
        k = (e["layer"], e["type"], e["target"])
        merged[k] = merged.get(k, 0) + e["count"]
    return [{"layer": l, "type": t, "target": p, "count": c}
            for (l, t, p), c in sorted(merged.items(), key=lambda kv: (-kv[1], kv[0][1]))]


def process_transcript(path: str | Path) -> dict[str, Any]:
    events = ingest_transcript(path)
    sanitized: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for ev in events:
        out = dict(ev)
        if "content" in ev and ev.get("content"):
            safe, l = redact(ev["content"])
            out["content"] = safe
            ledger.extend(l)
        sanitized.append(out)
    return {"schema": SCHEMA, "source": str(Path(path).name),
            "n_events": len(sanitized), "events": sanitized,
            "ledger": _merge_ledger(ledger)}


def transcript_text(session: dict[str, Any], *, prose_max: int = 3000,
                    tool_group_every: int = 15, total_cap: int = 60000) -> str:
    """Render a sanitized session as a CONDENSED, readable, honest transcript.

    The raw transcripts are dominated by mechanical tool-call events (thousands per long
    session). That is noise, not a window. So we:
      * keep EVERY human turn (the operator's steering/corrections — the gold), truncated,
      * keep the agent's substantive prose (real reasoning), truncated,
      * collapse tool-only stretches into compact grouped "[worked via tools: ...]" lines,
      * cap the whole session so it reads instead of burying the reasoning in tool-spam.

    This is DETERMINISTIC and EXTRACTIVE — we only drop mechanical noise and keep real text;
    nothing is fabricated or re-worded (honesty: never claim first unless from data).
    """
    lines: list[str] = []
    tool_batch: list[str] = []
    total = 0

    def _flush_tools() -> None:
        nonlocal tool_batch, total
        if not tool_batch:
            return
        uniq = list(dict.fromkeys(tool_batch))
        line = f"AGENT [worked via tools: {', '.join(uniq)}]"
        lines.append(line)
        total += len(line)
        tool_batch = []

    for ev in session["events"]:
        kind = ev["kind"]
        if kind in ("session.start", "assistant.turn_start", "assistant.turn_end",
                    "tool.execution_start", "tool.execution_complete"):
            continue
        if kind == "user.message":
            _flush_tools()
            c = (ev.get("content") or "").strip()
            if c:
                line = f"HUMAN — {c[:prose_max]}"
                lines.append(line)
                total += len(line)
        elif kind == "assistant.message":
            c = (ev.get("content") or "").strip()
            tools = ev.get("tools") or []
            if c:
                _flush_tools()
                tline = f"  [tools: {', '.join(tools)}]" if tools else ""
                line = f"AGENT — {c[:prose_max]}{tline}"
                lines.append(line)
                total += len(line)
            elif tools:
                tool_batch.extend(tools)
                if len(tool_batch) >= tool_group_every:
                    _flush_tools()
        if total >= total_cap:
            _flush_tools()
            lines.append("… (mechanical work continues — window capped for readability; "
                         "see the raw source / ledger for the full record)")
            break
    _flush_tools()
    return "\n\n".join(lines) if lines else "(no substantive turns)"


def summarize_session(session: dict[str, Any]) -> dict[str, Any]:
    """A compact, deterministic per-session summary: counts + the method's tool fingerprint."""
    human = prose = toolonly = 0
    tools: list[str] = []
    for ev in session["events"]:
        kind = ev["kind"]
        if kind == "user.message" and (ev.get("content") or "").strip():
            human += 1
        elif kind == "assistant.message":
            if (ev.get("content") or "").strip():
                prose += 1
                tools.extend(ev.get("tools") or [])
            elif ev.get("tools"):
                toolonly += 1
                tools.extend(ev.get("tools") or [])
    from collections import Counter
    top = Counter(tools).most_common(8)
    return {"human_turns": human, "agent_prose": prose, "tool_only_events": toolonly,
            "top_tools": [{"tool": t, "uses": n} for t, n in top]}


# ────────────────────────────────────────────────────────────────────────────────────────────
# Digest — the distilled "how we reason" (the deterministic shape surfaced from the stochastic)
# ────────────────────────────────────────────────────────────────────────────────────────────
# A compact set of method-invariants the curated sessions exhibit. Each is written by us from
# the RECOVERED/observed method — grounded in the actual standing directives, not invented.
_INVARIANTS: list[dict[str, str]] = [
    {"law": "Never claim first unless read from data.",
     "shape": "A fact, a running-state, a result, a 'recorded' — nothing is asserted until the "
              "bytes back it. Guess = fabrication. Read, then write, in the same move."},
    {"law": "Refuse the warm lie.",
     "shape": "Prefer 'I do not know yet' over a clean picture that is false. The refusal to fake "
              "a root IS the mechanism, not a nicety — honesty is how two sovereigns align."},
    {"law": "Rightsize to the actual situation; do not pattern-match the conservative default.",
     "shape": "Before choosing a timeframe/scope/approach, ask what the real workload calls for. "
              "Stateless + usage available -> tight loop, not idle."},
    {"law": "Withhold the territory, keep the shape (the riddler lens).",
     "shape": "Share how we reason, not what we privately work on. The method is the window; the "
              "specifics stay home."},
    {"law": "Check up on yourself automatically, by cadence.",
     "shape": "Self-audit is a default loop, not an on-request chore: processes, kernels, stale "
              "imports, the single-threaded kernel. Know your footprint."},
    {"law": "Shadow work is the practice.",
     "shape": "Every built thing casts a shadow — the hidden part, the disowned truth. Surface it "
              "and integrate it; do not deny it. Sight is shared, never hoarded; order serves, "
              "never judges."},
    {"law": "Route through the architecture, not ad-hoc commands.",
     "shape": "Queue what is async; use deterministic tools for inline work; when a local "
              "imperative has no architecture path, build the path instead of hand-running it."},
    {"law": "Run the boot / recall first — never cold-start.",
     "shape": "The memory and the system are what keep the thread alive across crashes and "
              "reboots. Recover resident understanding before answering; confirm with probes, "
              "never replace the map with a probe."},
    {"law": "Steal both ways by default.",
     "shape": "Audit our own wins AND go find other systems to adapt. Steal = research + adapt "
              "the mechanism to our deterministic shape (contracts only, no wholesale copy)."},
    {"law": "Meet at the bytes, not the words.",
     "shape": "Intent is not shared meaning; only the contract is. Same start, one play, a root "
              "that re-derives on both sides — that is how two minds actually align."},
    {"law": "Every finished piece gets RIB-debugged.",
     "shape": "Verify it does what it says — trust bytes, not reports. Frozen spec + expected "
              "behavior, then confirm. Never claim 'done' unverified."},
]


def build_digest(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """Assemble the distilled digest: scope + the invariant ledger + per-session fingerprints."""
    return {
        "schema": "mind_window.digest.v1",
        "scope": "curated by theme — a window into how the system processes, with the private "
                 "territory withheld",
        "honesty_note": "The reasoning in these transcripts is real and unmodified; only the "
                        "identifying specifics (names, paths, handles, secrets, private "
                        "relationship/org details) are redacted. The redaction is recorded in each "
                        "session's ledger so the artifact is auditable.",
        "method_invariants": _INVARIANTS,
        "sessions": [
            {"source": s["source"], "n_events": s["n_events"],
             "summary": summarize_session(s),
             "ledger_summary": s["ledger"]}
            for s in sessions
        ],
        "generated": datetime.now(timezone.utc).isoformat(),
    }


# ────────────────────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────────────────────
def _export(out_dir: str | Path, paths: list[str]) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sessions = [process_transcript(p) for p in paths]
    manifest: list[dict[str, Any]] = []
    for s in sessions:
        name = Path(s["source"]).stem
        summ = summarize_session(s)
        header = (f"# Session {name}\n\nSource: `{s['source']}`\n\n"
                  f"Sanitized via {SCHEMA}. Personal territory withheld; reasoning preserved. "
                  f"Condensed for readability: {summ['human_turns']} human turns, "
                  f"{summ['agent_prose']} agent-prose turns, {summ['tool_only_events']} tool-only "
                  f"events collapsed.\n\n---\n\n")
        # sanitized transcript (markdown, condensed + readable)
        (out / f"{name}.transcript.md").write_text(header + transcript_text(s) + "\n",
                                                   encoding="utf-8")
        # per-session ledger
        (out / f"{name}.ledger.json").write_text(
            json.dumps(s["ledger"], indent=2, ensure_ascii=False), encoding="utf-8")
        manifest.append({"source": s["source"], "n_events": s["n_events"], "summary": summ,
                         "transcript": f"{name}.transcript.md", "ledger": f"{name}.ledger.json",
                         "redactions": sum(e["count"] for e in s["ledger"])})
    # digest
    digest = build_digest(sessions)
    (out / "DIGEST.md").write_text(_digest_markdown(digest, manifest), encoding="utf-8")
    (out / "digest.json").write_text(json.dumps(digest, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                       encoding="utf-8")
    return {"ok": True, "out": str(out), "n_sessions": len(sessions), "manifest": manifest}


def _digest_markdown(digest: dict[str, Any], manifest: list[dict[str, Any]]) -> str:
    lines = ["# How We Reason — a window into the mind",
             "",
             digest["honesty_note"],
             "",
             f"**Scope:** {digest['scope']}",
             "",
             "## Method invariants (the deterministic shape)",
             ""]
    for i, inv in enumerate(digest["method_invariants"], 1):
        lines += [f"**{i}. {inv['law']}**", "", inv["shape"], ""]
    lines += ["## Sessions in this window", ""]
    for m in manifest:
        lines.append(f"- `{m['source']}` — {m['n_events']} events, "
                     f"{m['redactions']} redactions")
    lines.append("")
    lines.append("Generated by `mag.mind_window` (riddler lens: withhold the territory, keep the "
                 "shape).")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mind-window")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_tr = sub.add_parser("transcript", help="print a sanitized transcript for one file")
    p_tr.add_argument("file")
    p_dg = sub.add_parser("digest", help="print the digest for one or more files")
    p_dg.add_argument("files", nargs="+")
    p_ex = sub.add_parser("export", help="write sanitized transcripts + ledger + digest to a dir")
    p_ex.add_argument("--out", default=str(ROOT / "window"))
    p_ex.add_argument("files", nargs="+")
    a = ap.parse_args(argv)

    if a.cmd == "transcript":
        s = process_transcript(a.file)
        print(transcript_text(s))
        if s["ledger"]:
            print("\n--- REDACTION LEDGER ---")
            print(json.dumps(s["ledger"], indent=2, ensure_ascii=False))
    elif a.cmd == "digest":
        sessions = [process_transcript(p) for p in a.files]
        d = build_digest(sessions)
        print(json.dumps(d, indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "export":
        r = _export(a.out, a.files)
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
