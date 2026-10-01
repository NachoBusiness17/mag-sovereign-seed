"""Voice dictate — per-surface cleanup for spoken transcripts.

Stolen invariant (credit: VS Code 1.132 dictation, microsoft/vscode PRs #328217/#328225,
code.visualstudio.com/updates/v1_132):
  - ONE STT engine, but the final text is adapted to the SURFACE it lands on:
      terminal/command -> shell-aware (spoken flag words -> flags, auto-quote a value tail)
      chat/prose       -> punctuation + numeral cleanup, preserve meaning, prefer numerals
  - layered instruction files on top of built-in rules (user ~/.mag/dictation.md + repo .mag/dictation.md)

Schema: mag_voice_dictate.v1
LAW: steal the invariant, not VS Code DNA.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_voice_dictate.v1"
SURFACES = ("chat", "terminal", "command")

# symbols (dash handled separately as a flag prefix)
_SYMBOLS: list[tuple[str, str]] = [
    ("equals", "="),
    ("equal", "="),
    ("dollar", "$"),
    ("asterisk", "*"),
    ("star", "*"),
    ("underscore", "_"),
    ("slash", "/"),
    ("backslash", "\\"),
    ("dot", "."),
    ("period", "."),
    ("comma", ","),
    ("colon", ":"),
    ("semicolon", ";"),
    ("open paren", "("),
    ("close paren", ")"),
    ("open bracket", "["),
    ("close bracket", "]"),
    ("open brace", "{"),
    ("close brace", "}"),
    ("at sign", "@"),
    ("hash", "#"),
    ("pound", "#"),
    ("percent", "%"),
    ("ampersand", "&"),
    ("pipe", "|"),
    ("tilde", "~"),
    ("caret", "^"),
    ("greater than", ">"),
    ("less than", "<"),
]
# chat filler / disfluency to strip (word boundaries)
_FILLER = re.compile(r"\b(?:um|uh|er|like|you know|i mean)\b\s*", re.I)
# number words -> digits (prefer numerals where appropriate)
_NUMBERS: list[tuple[str, str]] = [
    ("zero", "0"), ("one", "1"), ("two", "2"), ("three", "3"), ("four", "4"),
    ("five", "5"), ("six", "6"), ("seven", "7"), ("eight", "8"), ("nine", "9"),
    ("ten", "10"),
]


def _dictation_files() -> list[Path]:
    files: list[Path] = []
    for p in (Path.home() / ".mag" / "dictation.md", ROOT / ".mag" / "dictation.md"):
        if p.is_file():
            files.append(p)
    return files


def _load_rules() -> list[tuple[str, str]]:
    """Load 'from -> to' (or 'from|to') replacement lines from layered dictation files."""
    rules: list[tuple[str, str]] = []
    for p in _dictation_files():
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith(("#", "//")):
                    continue
                if "->" in line:
                    a, b = line.split("->", 1)
                    rules.append((a.strip(), b.strip()))
                elif "|" in line:
                    a, b = line.split("|", 1)
                    rules.append((a.strip(), b.strip()))
        except Exception:
            continue
    return rules


def _apply_rules(text: str) -> str:
    for a, b in _load_rules():
        try:
            text = re.sub(re.escape(a), lambda _m: b, text, flags=re.I)
        except Exception:
            continue
    return text


def _chat_cleanup(text: str) -> str:
    t = _FILLER.sub(" ", text).strip()
    t = re.sub(r"\s+", " ", t)
    for word, digit in _NUMBERS:
        t = re.sub(rf"\b{word}\b", digit, t, flags=re.I)
    if t and t[-1] not in ".!?":
        t += "."
    if t:
        t = t[0].upper() + t[1:]
    return t


def _quote_value_tail(tokens: str) -> str:
    """git commit dash m hello world -> git commit -m "hello world"."""
    parts = tokens.split(" ")
    for i, tok in enumerate(parts):
        if tok.startswith("-"):
            tail = [p for p in parts[i + 1:] if p and not p.startswith("-") and p not in ("=", ">", "<", "|")]
            if len(tail) >= 2:
                return " ".join(parts[:i + 1]) + ' "' + " ".join(tail) + '"'
            break
    return tokens


def _map_symbol(tok: str) -> str:
    low = tok.lower()
    for word, sym in _SYMBOLS:
        if low == word:
            return sym
    return tok


def _terminal_cleanup(text: str) -> str:
    """Spoken -> shell: 'dash m' -> '-m', 'dash dash failed' -> '--failed', then quote value tail."""
    t = re.sub(r"\b(?:double dash|dash dash)\b", "##D2##", text, flags=re.I)
    t = re.sub(r"\b(?:dash)\b", "##D1##", t, flags=re.I)
    toks = t.split()
    out: list[str] = []
    i = 0
    n = len(toks)
    while i < n:
        tok = toks[i]
        if tok in ("##D1##", "##D2##"):
            prefix = "-" if tok == "##D1##" else "--"
            if i + 1 < n and toks[i + 1] not in ("##D1##", "##D2##"):
                out.append(prefix + _map_symbol(toks[i + 1]))
                i += 2
                continue
            out.append(prefix)
            i += 1
            continue
        out.append(_map_symbol(tok))
        i += 1
    line = " ".join(out)
    return _quote_value_tail(line)


def cleanup(text: str, surface: str = "chat") -> str:
    """Adapt a spoken transcript to the surface it lands on (I2)."""
    surface = (surface or "chat").strip().lower()
    if surface not in SURFACES:
        surface = "chat"
    t = (text or "").strip()
    if not t:
        return t
    t = _apply_rules(t)
    return _terminal_cleanup(t) if surface in ("terminal", "command") else _chat_cleanup(t)


def cleanup_for_terminal(text: str) -> str:
    return cleanup(text, "terminal")


def handle_dictate(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """REST helper — POST {text, surface} -> cleaned text."""
    body = body or {}
    text = str(body.get("text") or "").strip()
    surface = str(body.get("surface") or "chat").strip().lower()
    if not text:
        return {"ok": False, "schema": SCHEMA, "error": "text required", "cleaned": ""}
    cleaned = cleanup(text, surface)
    return {
        "ok": True,
        "schema": SCHEMA,
        "surface": surface if surface in SURFACES else "chat",
        "input": text,
        "cleaned": cleaned,
    }
