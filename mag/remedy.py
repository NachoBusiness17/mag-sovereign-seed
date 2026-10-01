# remedy — the at-will error toolkit (behavioral map, machine-readable).
#
# The behavioral map used to live as scattered prose (playbook.md, skills pins,
# deepseek_api/error_codes.txt, run case law). This module turns those lessons
# into CALLABLE cards: an agent (or the harness itself) looks up a remedy by
# error text / tool signature BEFORE or WHEN the error strikes, and gets the
# prevent + fix + probe pattern in one shot.
#
# Cards live at memory/remedies/*.md with a simple key: value header block so
# they stay human-diggable (they ARE the case law) AND machine-parseable.
#
# Wire points (mag/agent_cli.py):
#   * L1 preflight: blocked tool calls append the matching remedy hint.
#   * L3 collapse detector: nudge text appends the matching remedy card.
#   * !remedy <keyword> steer command: pull a card at will mid-run.
#
# Usage:
#   python -m mag.remedy list
#   python -m mag.remedy lookup "missing 1 required positional argument"
#   python -m mag.remedy prevent write_file
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REMEDY_DIR = ROOT / "memory" / "remedies"


def _parse_card(text: str) -> dict:
    """Parse the key: value header block (before first blank line)."""
    card: dict = {"body": text}
    head, _, body = text.partition("\n\n")
    for line in head.splitlines():
        line = line.strip()
        if not line or line.startswith("--") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        card[k.strip().lower().replace("-", "_")] = v.strip()
    card["body"] = body.strip()
    return card


def cards() -> list[dict]:
    """Load all remedy cards, sorted by id."""
    if not REMEDY_DIR.exists():
        return []
    out = []
    for p in sorted(REMEDY_DIR.glob("*.md")):
        try:
            out.append(_parse_card(p.read_text(encoding="utf-8")))
        except OSError:
            continue
    return out


def _tool_matches(card: dict, tool: str | None) -> bool:
    if not tool:
        return True
    tools = card.get("tools", "")
    return tool in [t.strip() for t in tools.split(",") if t.strip()]


def _sig_matches(card: dict, text: str) -> bool:
    sig = card.get("signature", "")
    if not sig:
        return False
    try:
        return re.search(sig, text, re.IGNORECASE | re.MULTILINE) is not None
    except re.error:
        return sig.lower() in text.lower()


def lookup(text: str, *, tool: str | None = None) -> dict | None:
    """Best remedy for an error text (or keyword). Most specific first."""
    best = None
    best_len = -1
    for c in cards():
        if not _tool_matches(c, tool):
            continue
        hit = _sig_matches(c, text) or (
            text.strip().lower() in (c.get("id", "").lower(), c.get("name", "").lower())
        )
        if hit:
            sig_len = len(c.get("signature", ""))
            if sig_len > best_len:
                best, best_len = c, sig_len
    if best is None:
        best = by_tool(text.strip())  # bare tool name → its card
    return best


def card_md(card: dict, max_chars: int = 900) -> str:
    """Render a card as injectable text (prevent + fix, truncated)."""
    if not card:
        return ""
    name = card.get("name") or card.get("id", "remedy")
    body = card.get("body", "")
    # cut to the Prevent/Fix sections only — skip long commentary
    cut = body
    low = body.lower()
    for marker in ("## probe", "## example"):
        i = low.find(marker)
        if i > 0:
            cut = body[:i].rstrip()
    cut = cut[:max_chars]
    return f"[REMEDY {name}] {cut}"


def by_tool(tool: str) -> dict | None:
    """First card registered for a tool (tool-name-only match)."""
    for c in cards():
        if _tool_matches(c, tool):
            return c
    return None


def prevent(tool: str, args_text: str = "") -> dict | None:
    """Preflight-style lookup: card for a tool whose signature matches its args."""
    return lookup(args_text or tool, tool=tool) or by_tool(tool)


def _cli(argv: list[str]) -> int:
    if not argv or argv[0] == "list":
        cs = cards()
        print(f"{len(cs)} remedy cards in {REMEDY_DIR}")
        for c in cs:
            print(f"  {c.get('id', '?'):42s} tools={c.get('tools', '-')}")
        return 0
    if argv[0] == "lookup":
        c = lookup(" ".join(argv[1:]))
        print(card_md(c) if c else "(no remedy found)")
        return 0 if c else 1
    if argv[0] == "prevent":
        c = prevent(argv[1], " ".join(argv[2:]))
        print(card_md(c) if c else f"(no remedy for tool {argv[1]})")
        return 0 if c else 1
    print("usage: python -m mag.remedy [list | lookup <text> | prevent <tool> <args>]")
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
