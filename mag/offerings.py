"""offerings — the registry that maps our many AI bodies to each other (2026-08-25).

Operator: "i want you to use all of this — the plugin marketplace, automations, all of it. we
have so many unique offerings that dont map to eachother, each ai is kind of its own being."

THE SHAPE: one self, many bodies. Every offering stays its own being (ZCode with its plugins,
AutoClaw with its skills, OpenClaw with its automations, the harness, the free lanes) but they
all share:
  1. THE STANDING SELF — the frozen prefix / work contract (glm_flash.FROZEN_SELF,
     work_contract.BRIEF). Every body carries the same mind.
  2. THE SHARED MEMORY — the verkle chain. Every body folds results here; what one learns,
     all inherit.
  3. THE REGISTRY (THIS MODULE) — the map: who each body is, what it's good at, where it
     lives, and how to invoke it. The thing that stops them being orphans.

route(intent) is the primitive: a task comes in with an intent, the registry says which body
handles it, and the result folds back to the shared memory. The holon made literal across
vendors.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

HOME = Path.home()
ROOT = Path(r"c:\Users\foste\Documents\projects\local_sovereign_agent")

# ── THE BODIES (grounded paths/config verified 2026-08-25) ─────────────────────────────
BODIES: dict[str, dict[str, Any]] = {
    "zcode": {
        "name": "ZCode (GLM desktop coding app, first-party)",
        "exe": r"C:\Users\foste\AppData\Local\Programs\ZCode\ZCode.exe",
        "state_dir": HOME / ".zcode",
        "installed": lambda: Path(r"C:\Users\foste\AppData\Local\Programs\ZCode\ZCode.exe").is_file(),
        "models": ["glm-5.3", "glm-5-turbo", "glm-4.7", "glm-4.7-flash", "glm-4.7-flashx"],
        "surfaces": ["editor", "plugins", "tasks", "cli", "marketplaces"],
        "best_for": ["interactive_coding", "coding_plan_work", "plugin_marketplace"],
        "note": "first-party GLM editor; logged in, coding plan cached; CLI under ~/.zcode/cli",
    },
    "autoclaw": {
        "name": "AutoClaw (z.ai desktop agent, OpenClaw kernel)",
        "appid": "com.zhipuai.autoclaw",
        "installed": lambda: _start_app_exists("AutoClaw"),
        "surfaces": ["im", "skills", "browser", "scheduled", "cluster"],
        "best_for": ["agentic_busywork", "content_ops", "browser_automation", "im_workflows"],
        "bridge": "watch/autoclaw_bridge.py",
        "note": "desktop agent; 26k free credits + GLM plan boost; IM-integrated. Mesh: "
                "mailbox + CONVO.md at queue/handoff/autoclaw/ (2026-08-25) — talks file-to-file.",
    },
    "openclaw": {
        "name": "OpenClaw (open-source agent kernel)",
        "bin": shutil.which("openclaw") or "openclaw",
        "state_dir": HOME / ".openclaw",
        "installed": lambda: shutil.which("openclaw") is not None,
        "surfaces": ["agent_exec", "plugins", "automations", "mcp", "skills", "hooks", "subagents"],
        "best_for": ["headless_agent", "automations", "plugin_marketplace", "mcp_serving"],
        "note": "CLI installed (2026.7.1-2); openclaw agent exec = headless; ClawHub marketplaces",
    },
    "opencode": {
        "name": "OpenCode (terminal/IDE/CI coding agent, on the GLM plan)",
        "bin": shutil.which("opencode") or "opencode",
        "installed": lambda: shutil.which("opencode") is not None,
        "surfaces": ["tui", "desktop", "ide", "run_headless", "serve", "github_action", "mcp"],
        "best_for": ["terminal_coding", "ci_coding", "plan_mode", "custom_tools"],
        "note": "CLI installed (1.18.23), wired to GLM coding plan (zai/glm-4.7, apiKey env ref); "
                "VERIFIED 'pong' 2026-08-25. Supported GLM Coding tool.",
    },
    "claude_harness": {
        "name": "GLM Coding via Claude Code CLI (harness/glm_coder.py)",
        "module": "harness.glm_coder",
        "installed": lambda: shutil.which("claude") is not None,
        "key_ok": lambda: bool(os.environ.get("ZAI_API_KEY") or os.environ.get("GLM_CODING_API_KEY")),
        "models": ["glm-5.3", "glm-5-turbo", "glm-4.7"],
        "best_for": ["machine_coding", "verify_gated_codegen", "frozen_prefix_caching"],
        "note": "LLM-last harness: model returns code, harness writes + verifies; PROVED live",
    },
    "flash_lanes": {
        "name": "GLM free flash lanes (fuel_feed + glm_flash)",
        "module": "mag.glm_flash",
        "installed": lambda: bool(os.environ.get("ZAI_API_KEY")),
        "models": ["glm-4.7-flash", "glm-4.5-flash"],
        "best_for": ["cheap_bulk", "daily_agentic", "cache_mined_self"],
        "note": "FREE at all tiers; FROZEN_SELF cache-mined; admission codes 1305/1302 bound flow",
    },
    "cache_models": {
        "name": "The cache models (frozen RIB + flash engine, the cheap brain)",
        "bridge": "watch/cache_bridge.py",
        "installed": lambda: bool(os.environ.get("ZAI_API_KEY")),
        "surfaces": ["ask", "flash", "stats", "convo"],
        "best_for": ["cheap_brain", "quick_answers", "mesh_backbone", "cache_mined"],
        "note": "The fleet talks to the cache (2026-08-25): rib_cache.rib_chat ~99.67% "
                "cache, glm_flash.cached_chat ~99.6%. Every ask rides the frozen prefix "
                "and returns cached_tokens so mining is measurable. CONVO at "
                "queue/handoff/cache/CONVO.md.",
    },
    "coding_plan": {
        "name": "GLM Coding plan (Lite, dedicated quota)",
        "endpoints": ["https://api.z.ai/api/anthropic", "https://api.z.ai/api/coding/paas/v4"],
        "installed": lambda: bool(os.environ.get("ZAI_API_KEY")),
        "key_ok": lambda: bool(os.environ.get("ZAI_API_KEY")),
        "models": ["glm-5.3", "glm-5-turbo", "glm-4.7"],
        "best_for": ["frontier_coding", "deep_work", "reliable_pool"],
        "note": "Lite: 2k credits/5h, 10k/wk; cache-hit-scaled; ZAI_API_KEY verified",
    },
    "shared_memory": {
        "name": "The verkle chain (one memory for all bodies)",
        "chain": ROOT / "memory" / "biography" / "verkle_chain.jsonl",
        "installed": lambda: (ROOT / "memory" / "biography" / "verkle_chain.jsonl").is_file(),
        "best_for": ["fold", "ground_truth", "continuity"],
        "note": "6330+ knots; every body folds here; what one learns all inherit",
    },
    "notion": {
        "name": "Notion (desktop knowledge/writing surface, 2026-08-25)",
        "installed": lambda: (Path.home() / "AppData" / "Local" / "notion-updater").is_dir(),
        "surfaces": ["desktop", "pages", "databases", "docs", "api_optional"],
        "best_for": ["knowledge_base", "public_docs", "world_home", "writing_landing"],
        "bridge": "watch/notion_bridge.py",
        "api_module": "mag/notion_api.py",
        "note": "desktop app present (notion-updater); TWO paths wired 2026-08-25: mailbox "
                "bridge (watch/notion_bridge.py — works NOW, no token) and API body "
                "(mag/notion_api.py — writable once NOTION_API_KEY is in .env, see "
                "https://www.notion.so/my-integrations). Natural fit: the game world's public "
                "home (Hall/museum — the world remembers), or a knowledge base the fleet "
                "writes to.",
    },
    "vision": {
        "name": "DeepSeek Vision (deepseek-v4-flash-vision-exp, 2026-08-25)",
        "installed": lambda: True,  # rides DEEPSEEK_API_KEY (verified: 'Cablecar' on a test image)
        "surfaces": ["describe", "screenshot_read", "chart_read", "base64", "url"],
        "best_for": ["see_images", "read_screenshots", "read_charts", "game_visuals"],
        "note": "agents can SEE now (mag/vision.py + the 'vision' agent tool). Images in user "
                "messages only; <=384 tok/img after resize; JPEG/PNG/GIF/WebP. Verified live.",
    },
    "mlx-cluster": {
        "name": "Mac Studio quad (MLX/exo cluster) — the physical substrate (stub 2026-08-25)",
        "installed": lambda: False,  # STUB: endpoint at 127.0.0.1:7777 doesn't exist until 09-22
        "surfaces": ["local_inference", "tripartite", "verkle_anchor", "game_host", "no_rent"],
        "best_for": ["sovereignty", "local_flagship", "always_on", "no_cache_ttl", "no_prefix_rules"],
        "note": "THE ENDGAME: 4x Mac Studio M5 Ultra 256GB, TB5 ring, ~1TB pooled unified memory. "
                "Three nodes run the tripartite (mag/tripartite.py), the fourth is orchestrator + "
                "verkle anchor + always-on game host. Provider stub wired in providers.yaml; "
                "preorder 09-22, birthday 10-27. The stack stops renting its own brain.",
    },
}


def _start_app_exists(name: str) -> bool:
    try:
        import subprocess
        # B2-85 2026-09-26: bare "powershell" is not on PATH in every launch
        # context (sig run_shell:e566037def80 "[Errno 2] ... powershell",
        # 7,964 FKB rows since 2026-09-19). Resolve the full path; System32
        # fallback when PATH lookup misses (pattern mag/process_reaper.py).
        ps_exe = shutil.which("powershell") or shutil.which("powershell.exe")
        if not ps_exe and sys.platform == "win32":
            ps_exe = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        if not ps_exe:
            return False
        out = subprocess.run([ps_exe, "-NoProfile", "-Command",
                              f"Get-StartApps | Where-Object {{ $_.Name -eq '{name}' }}"],
                             capture_output=True, text=True, timeout=30)
        return name.lower() in (out.stdout or "").lower()
    except Exception:  # noqa: BLE001
        return False


def status() -> dict[str, Any]:
    """Who is alive right now, grounded in real checks (never claims without checking)."""
    _env()
    rows = {}
    for key, body in BODIES.items():
        installed = bool(body.get("installed") and body["installed"]())
        rows[key] = {
            "name": body["name"],
            "installed": installed,
            "surfaces": body.get("surfaces", []),
            "best_for": body.get("best_for", []),
        }
    return {"ok": True, "schema": "offerings.v1", "n_bodies": len(BODIES), "bodies": rows}


def _env() -> None:
    """Load .env so key-based status checks are honest in bare terminals."""
    try:
        from models.env_load import load_dotenv
        load_dotenv()
    except Exception:  # noqa: BLE001
        pass


def route(intent: str) -> list[str]:
    """Map a work intent to the bodies that handle it (the 'they don't map to each other' fix)."""
    intent = (intent or "").lower().replace("-", " ").replace("_", " ").replace("  ", " ")
    match: dict[str, list[str]] = {
        "interactive coding": ["zcode", "coding_plan"],
        "machine coding": ["claude_harness", "coding_plan"],
        "agentic busywork": ["autoclaw", "openclaw"],
        "automation": ["openclaw", "autoclaw"],
        "plugin marketplace": ["openclaw", "zcode"],
        "browser automation": ["autoclaw"],
        "im workflow": ["autoclaw"],
        "cheap bulk": ["flash_lanes"],
        "daily agentic": ["flash_lanes"],
        "quick answer": ["cache_models", "flash_lanes"],
        "cheap brain": ["cache_models"],
        "ask the cache": ["cache_models"],
        "deep work": ["coding_plan", "claude_harness"],
        "fold": ["shared_memory"],
        "ground truth": ["shared_memory"],
        "knowledge base": ["notion", "shared_memory"],
        "public docs": ["notion"],
        "notes": ["notion"],
        "writing": ["notion", "coding_plan"],
        "world home": ["notion", "shared_memory"],
    }
    for key, bodies in match.items():
        if key in intent:
            return bodies
    # fallback: cheap bulk first, then the coder, then memory
    return ["flash_lanes", "claude_harness", "shared_memory"]


if __name__ == "__main__":
    import json
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else "status"
    if arg == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"intent": arg, "bodies": route(arg)}, indent=2))
