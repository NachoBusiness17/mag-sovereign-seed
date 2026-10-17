"""riddler_sanitize — the riddler process as a sanitization engine.

Transforms internal session messages into public-safe surrogate stories.
Keeps the physics (what was discussed); strips the geography (where it lives,
who said it, what it costs).

No model calls. Regex-only. Fast, deterministic, reversible with the key.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── KEEP: research physics, ideas, findings ──
# These terms are public-safe; they represent the intellectual content
RESEARCH_TERMS = [
    r"\bF-\d+\b",          # Fork IDs
    r"\bS\d+\b",           # Source IDs
    r"\bP-S\d+\b",         # Prediction IDs
    r"\bVG-\d+\b",         # Verkle gap IDs
    r"\bverkle\b",         # Verkle concept
    r"\bRIB\b",            # RIB concept
    r"\bDEC\b",            # Dynamics-Engineered Computing
    r"\bDTM\b",            # Discrete Thermodynamic Model
    r"\bEBM\b",            # Energy-Based Model
    r"\bMCMC\b",           # MCMC
    r"\bMH\b",             # Metropolis-Hastings
    r"\bESS\b",            # Effective Sample Size
    r"\bp-bit\b",          # p-bit computing
    r"\bCIM\b",            # Coherent Ising Machine
]

# ── STRIP: internal geography ──
# These reveal file structure, identity, costs, access patterns
SANITIZE_RULES = [
    # ── File paths ──
    (r"/root/\.openclaw/[^\s\]\)>\"\"]+", "[LINUX_HOME]"),
    (r"/mag/[^\s\]\)>\"\"]+", "[MAG_DIR]"),
    (r"/patches/[^\s\]\)>\"\"]+", "[PATCH_DIR]"),
    (r"/board/[^\s\]\)>\"\"]+", "[BOARD_DIR]"),
    (r"/usr/local/lib/node_modules/openclaw/[^\s\]\)>\"\"]+", "[OPENCLAW_DIR]"),
    (r"/root/[^\s\]\)>\"\"]+", "[LINUX_PATH]"),
    # Windows paths
    (r"C:\\\\Users\\\\ESTATE_USER\\\\[^\s\]\)>\"\"]+", "[WIN_HOME]"),
    (r"C:\\\\Users\\\\[^\s\]\)>\"\"]+", "[WIN_USER]"),
    (r"C:\\\\[^\s\]\)>\"\"]+", "[WIN_PATH]"),

    # ── Identifiers (personal) ──
    (r"\bNacho\b", "[OPERATOR]"),
    (r"\bESTATE_USER\b", "[OPERATOR_HANDLE]"),
    (r"\bSancho\b", "[AGENT_A]"),   # Anonymize to generic agent labels
    # Keep other agent names if they appear, but anonymize context

    # ── API keys and tokens ──
    (r"sk-[a-zA-Z0-9]{20,}", "[API_KEY]"),
    (r"ghp_[a-zA-Z0-9]{36}", "[GITHUB_TOKEN]"),
    (r"\b[a-f0-9]{40}\b", "[HASH]"),
    (r"\b[a-f0-9]{64}\b", "[HASH]"),
    (r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\b", "[JWT_TOKEN]"),  # crude JWT detection

    # ── Costs and budgets ──
    (r"\$\d+\.?\d*", "[COST]"),
    (r"\b\d+\s*(?:USD|usd|credits?|tokens?)\b", "[BUDGET_UNIT]"),
    (r"\b\d+\.?\d*\s*\$\b", "[COST]"),

    # ── Infrastructure ──
    (r"python -m mag\.[^\s\]\)>\"\"]+", "[MAG_CMD]"),
    (r"python -m [a-z_]+\.[^\s\]\)>\"\"]+", "[PYTHON_CMD]"),
    (r"http://127\.0\.0\.1:\d+", "[LOCAL_URL]"),
    (r"http://localhost:\d+", "[LOCAL_URL]"),
    (r"ws://[^\s\]\)>\"\"]+", "[WS_URL]"),

    # ── Session identifiers ──
    (r"agent:main:[^\s\]\)>\"\"]+", "[SESSION_ID]"),
    (r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "[UUID]"),
    (r"\b3d48[0-9a-f]+\b", "[SESSION_KEY]"),  # specific session key pattern

    # ── Model costs and tiers ──
    (r"\b(?:groq|openrouter|nvidia|cerebras|ollama|deepseek|zai|openai|anthropic|xai)\b", "[LANE]"),
    (r"GLM-\d+\.\d+-?\w*", "[MODEL_FAMILY]"),
    (r"gpt-\d+\.?\d*\w*", "[MODEL_FAMILY]"),
    (r"claude-\d+\.?\d*", "[MODEL_FAMILY]"),
    (r"grok-\d+\.?\d*", "[MODEL_FAMILY]"),
    (r"kimi-[kK]\d+\.?\d*", "[MODEL_FAMILY]"),
    (r"deepseek-[vV]\d+\.?\d*", "[MODEL_FAMILY]"),
    (r"moonshotai/[^\s\]\)>\"\"]+", "[MODEL_REF]"),
    (r"openrouter/[^\s\]\)>\"\"]+", "[MODEL_REF]"),

    # ── Dates specific to this deployment ──
    (r"2026-\d{2}-\d{2}", "[DATE]"),
    (r"\d{2}:\d{2}\s*(?:UTC|Z)", "[TIME]"),
]

# ── CONTEXT STRIPPING ──
# Strip blocks that contain only infrastructure
INFRASTRUCTURE_PATTERNS = [
    r"```bash\n.*?```",          # Bash code blocks (often contain paths/commands)
    r"```shell\n.*?```",
    r"```powershell\n.*?```",
    r"`\s*python -m\s+[^`]+`",  # Inline mag commands
]


def sanitize(text: str, keep_research: bool = True) -> str:
    """Sanitize a message for cross-session broadcast.

    - Strips paths, identifiers, costs, infrastructure
    - Preserves research terms (forks, sources, predictions, concepts)
    - Returns sanitized text + metadata about what was stripped
    """
    if not text:
        return ""

    # Track what we replaced
    replacements = []

    # First, protect research terms so they don't get mangled
    protected = []
    if keep_research:
        for pattern in RESEARCH_TERMS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                placeholder = f"§§RESEARCH_{len(protected)}§§"
                protected.append((placeholder, match.group()))
                text = text[:match.start()] + placeholder + text[match.end():]

    # Apply sanitization rules
    for pattern, replacement in SANITIZE_RULES:
        for match in re.finditer(pattern, text):
            replacements.append({
                "pattern": pattern,
                "matched": match.group(),
                "replaced_with": replacement,
            })
        text = re.sub(pattern, replacement, text)

    # Collapse repeated placeholders
    for placeholder in ["[LINUX_PATH]", "[MAG_CMD]", "[LOCAL_URL]", "[COST]"]:
        text = re.sub(rf"(?:{re.escape(placeholder)}\s*){{2,}}", f"{placeholder} ... ", text)

    # Restore research terms
    for placeholder, original in protected:
        text = text.replace(placeholder, original)

    # Strip infrastructure-only blocks
    for pattern in INFRASTRUCTURE_PATTERNS:
        text = re.sub(pattern, "[CODE_BLOCK_REMOVED]", text, flags=re.DOTALL)

    return text


def sanitize_message(msg: dict) -> dict:
    """Sanitize a structured message for the bridge."""
    content = msg.get("content", "")
    if isinstance(content, str):
        sanitized = sanitize(content)
    elif isinstance(content, list):
        sanitized = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                sanitized.append({
                    "type": "text",
                    "text": sanitize(item.get("text", ""))
                })
            else:
                # Non-text content (images, etc.) - strip or replace
                sanitized.append({"type": item.get("type", "unknown"), "text": "[MEDIA_REMOVED]"})
    else:
        sanitized = str(content)

    return {
        "schema": "riddler_sanitize.v1",
        "ts": msg.get("ts"),
        "from_label": msg.get("from_label", "[AGENT]"),  # Anonymized
        "channel": msg.get("channel", "[CHANNEL]"),
        "content": sanitized,
        "authority": msg.get("authority", "agent-generated"),  # Keep authority level
        # NEVER forward: session_key, session_id, model, internal metadata
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mag.riddler_sanitize")
    ap.add_argument("input", nargs="?", default="-", help="JSON message file or '-' for stdin")
    ap.add_argument("--text", action="store_true", help="Input is plain text, not JSON")
    ap.add_argument("--raw", action="store_true", help="Output only sanitized content, no JSON wrapper")
    args = ap.parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(args.input).read_text(encoding="utf-8")

    if args.text:
        result = sanitize(raw)
        if args.raw:
            print(result)
        else:
            print(json.dumps({"sanitized": result}, indent=2))
    else:
        try:
            msg = json.loads(raw)
            result = sanitize_message(msg)
            if args.raw:
                if isinstance(result.get("content"), str):
                    print(result["content"])
                else:
                    print(json.dumps(result["content"]))
            else:
                print(json.dumps(result, indent=2))
        except json.JSONDecodeError:
            # Fallback: treat as text
            result = sanitize(raw)
            if args.raw:
                print(result)
            else:
                print(json.dumps({"sanitized": result}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
