"""bones_adapter -- the thin /bones Discord adapter over mag.wow_bones_session.

Directive: watch/inbox/HERMES_DIRECTIVE_BONES_REFEREE_20260916.md names the referee;
the Sep-20 critical path adds the human door. LAWS (binding):

  * THE ADAPTER FORMATS TEXT ONLY -- ZERO GAME LOGIC. Every payload below is the
    kernel CLI's own output envelope (start / turn / status / receipt / verbs in
    mag.wow_bones_session.main), rebuilt from BonesSession return values verbatim.
    The adapter decides nothing about legality, state, draws, or verdicts.
  * The bot token is read at RUNTIME, at process start, from
    %LOCALAPPDATA%\\hermes\\.env (var DISCORD_BOT_TOKEN). The value is never
    printed, logged, or copied into any file.
  * Guild-scoped to NT-ACv2 and answers only in #game-c-overview (constant block
    below, citing watch/inbox/HERMES_DISCORD_SETUP_20260915.md).

SURFACE:
  /bones start  [seed] [world_boss]   -> kernel start (seed optional, world-boss flag)
  /bones move   <verb> [session]      -> one turn through the referee
  /bones status [session]             -> session status
  /bones receipt [session]            -> wow_session.v1 receipt (file is kernel-written)
  /bones verbs  [session] [limit]     -> legal verbs for the current status

RUN:
  .venv\\Scripts\\python.exe -m mag.bones_adapter --check    # dry-run: registers the
                                                            # commands, prints them,
                                                            # never reads the token,
                                                            # never connects
  .venv\\Scripts\\python.exe -m mag.bones_adapter            # live (OPERATOR GATES:
                                                            # token rotation + channel
                                                            # permission must clear first)

The adapter may format; only the kernels decide.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from config import ROOT
except Exception:  # pragma: no cover - mirrors mag.wow_bones_session's own fallback
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from discord import app_commands  # noqa: E402
import discord  # noqa: E402

from mag.wow_bones_session import (  # noqa: E402
    SESSION_SCHEMA,
    BonesSession,
    _fixture_or_none,  # the kernel's own fixture gate, reused verbatim rather than
)                     # re-implemented (adapter stays logic-free by construction)

# --- pinned surfaces: watch/inbox/HERMES_DISCORD_SETUP_20260915.md -----------------
GUILD_ID = 799817554549800982        # NT-ACv2
CHANNEL_ID = 1050760558883913780     # #game-c-overview (the only answering channel)
# --- token surface: runtime read only, value never persisted anywhere -------------
ENV_FILE = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"
TOKEN_VAR = "DISCORD_BOT_TOKEN"

MAX_MESSAGE = 1900  # Discord cap is 2000; leave margin for the code fence


# --- formatting (the adapter's whole job) ------------------------------------------

def fmt_inline(obj: Any) -> str:
    """Canonical one-line JSON -- the kernel's own serialization style."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fmt_any(obj: Any, indent: int = 0) -> str:
    """Render any kernel-emitted payload as readable key/value text.

    Pure formatting: dicts become `key: value` lines, lists become dash lines with
    inline canonical JSON items, scalars pass through. No field is interpreted.
    """
    pad = "  " * indent
    if isinstance(obj, dict):
        lines: list[str] = []
        for key, val in obj.items():
            if isinstance(val, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(fmt_any(val, indent + 1))
            else:
                lines.append(f"{pad}{key}: {val}")
        return "\n".join(lines)
    if isinstance(obj, list):
        if not obj:
            return f"{pad}(none)"
        return "\n".join(f"{pad}- {fmt_inline(item)}" for item in obj)
    return f"{pad}{obj}"


def fmt_block(obj: Any) -> str:
    """Wrap a formatted payload in a Discord code fence, truncating if needed."""
    text = obj if isinstance(obj, str) else fmt_any(obj)
    body = f"```\n{text.strip()}\n```"
    if len(body) > MAX_MESSAGE:
        body = body[: MAX_MESSAGE - 20].rstrip("\n` ") + "\n… (truncated)\n```"
    return body


# --- session pointer (wiring, not game logic) ---------------------------------------

class BonesHub:
    """Per-channel pointer to the active session id.

    Sessions themselves live only in the kernel's own store
    (memory/runs/wow_bones/sessions via BonesSession.save/load). The hub holds
    one id per channel so /bones move works without retyping the id.
    """

    def __init__(self) -> None:
        self.current: dict[int, str] = {}

    def set(self, channel_id: int, session_id: str) -> None:
        self.current[channel_id] = session_id

    def resolve(self, channel_id: int, session_id: Optional[str]) -> Optional[BonesSession]:
        sid = session_id or self.current.get(channel_id)
        if not sid:
            return None
        return BonesSession.load(sid)


def no_session_msg(session_id: Optional[str]) -> dict[str, Any]:
    """Same refusal envelopes the kernel CLI emits for missing/unknown sessions."""
    if session_id:
        return {"ok": False, "reason": "UNKNOWN_SESSION", "session": session_id}
    return {"ok": False, "reason": "NO_SESSION",
            "hint": "/bones start first, or pass session=<id>"}


# --- the slash surface --------------------------------------------------------------

class BonesGroup(app_commands.Group):
    """Every handler: channel gate -> kernel call -> format. Nothing else."""

    def __init__(self, hub: Optional[BonesHub] = None) -> None:
        super().__init__(
            name="bones",
            description="Bones referee (kernel: mag/wow_bones_session, wow_session.v1)",
        )
        self.hub = hub or BonesHub()

    # -- the one reply path ----------------------------------------------------------

    async def _reply(self, interaction: discord.Interaction,
                     build: Callable[[int], str]) -> None:
        """Gate: only #game-c-overview gets answers, in-channel."""
        if interaction.channel_id != CHANNEL_ID:
            await interaction.response.send_message(
                f"This command answers only in <#{CHANNEL_ID}> (#game-c-overview).",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(build(interaction.channel_id))

    # -- payload builders (kernel envelopes, kernel calls only) ----------------------

    def _start(self, seed: Optional[str], world_boss: bool) -> str:
        fixture = _fixture_or_none()
        if fixture is None:
            # same refusal envelope as the kernel CLI's start
            return fmt_block({"ok": False, "reason": "NO_FIXTURE",
                              "hint": "python -m mag.wow_bones extract"})
        ses = BonesSession(fixture, seed or "0", world_boss=world_boss)
        ses.save()
        return fmt_block({
            "ok": True,
            "schema": SESSION_SCHEMA,
            "session_id": ses.session_id,
            "seed": ses.seed,
            "world_boss_alive": ses.world_boss,
            "session_status": ses.session_status,
            "encounter_state": ses.encounter_name(),
            "draw_index": 0,
            "verdict": ses.verdict(),
        })

    def _move(self, channel_id: int, verb: str, session_id: Optional[str]) -> str:
        ses = self.hub.resolve(channel_id, session_id)
        if ses is None:
            return fmt_block(no_session_msg(session_id))
        entry = ses.turn(verb)
        ses.save()
        return fmt_block({
            "ok": True,
            "turn": entry,
            "session_status": ses.session_status,
            "encounter_state": ses.encounter_name(),
            "draw_index": ses.stream.index,
            "verdict": ses.verdict(),
        })

    def _status(self, channel_id: int, session_id: Optional[str]) -> str:
        ses = self.hub.resolve(channel_id, session_id)
        if ses is None:
            return fmt_block(no_session_msg(session_id))
        return fmt_block({
            "ok": True,
            "session_id": ses.session_id,
            "seed": ses.seed,
            "session_status": ses.session_status,
            "encounter_state": ses.encounter_name(),
            "draw_index": ses.stream.index,
            "turn_count": ses.turn_count,
            "verdict": ses.verdict(),
        })

    def _receipt(self, channel_id: int, session_id: Optional[str]) -> str:
        ses = self.hub.resolve(channel_id, session_id)
        if ses is None:
            return fmt_block(no_session_msg(session_id))
        path = ses.write_receipt()
        body = dict(ses.receipt())
        # display-only pointer; the receipt FILE itself stays byte-stable kernel output
        body["receipt_path"] = str(path)
        return fmt_block(body)

    def _verbs(self, channel_id: int, session_id: Optional[str], limit: int) -> str:
        ses = self.hub.resolve(channel_id, session_id)
        if ses is None:
            return fmt_block(no_session_msg(session_id))
        # the kernel CLI's own legality listing, unchanged:
        legal = [v for v in ses.dispatch.verbs()
                 if ses.dispatch.rows[v]["status"] == ses.session_status]
        return fmt_block({
            "ok": True,
            "session_status": ses.session_status,
            "legal_verbs": legal[: max(0, limit)],
            "total": len(legal),
        })

    def _remember(self, channel_id: int, formatted: str) -> None:
        """Point the channel at the freshly started session. The id is read from the
        kernel envelope line the formatter just produced -- no game knowledge."""
        for line in formatted.splitlines():
            stripped = line.strip()
            if stripped.startswith("session_id:"):
                self.hub.set(channel_id, stripped.split(":", 1)[1].strip())
                return

    # -- slash commands ---------------------------------------------------------------

    @app_commands.command(name="start", description="Start a bones session")
    @app_commands.describe(seed="RNG seed (default 0)",
                           world_boss="World-boss guard: DONE is refused forever")
    async def start(self, interaction: discord.Interaction,
                    seed: Optional[str] = None, world_boss: bool = False) -> None:
        def build(channel_id: int) -> str:
            text = self._start(seed, world_boss)
            self._remember(channel_id, text)
            return text
        await self._reply(interaction, build)

    @app_commands.command(name="move", description="One bones turn: a verb through the referee")
    @app_commands.describe(verb="OPCODE name to dispatch",
                           session="session id (defaults to this channel's active session)")
    async def move(self, interaction: discord.Interaction, verb: str,
                   session: Optional[str] = None) -> None:
        await self._reply(
            interaction,
            lambda ch: self._move(ch, verb, session),
        )

    @app_commands.command(name="status", description="Bones session status")
    @app_commands.describe(session="session id (defaults to this channel's active session)")
    async def status(self, interaction: discord.Interaction,
                     session: Optional[str] = None) -> None:
        await self._reply(
            interaction,
            lambda ch: self._status(ch, session),
        )

    @app_commands.command(name="receipt", description="wow_session.v1 receipt for a bones session")
    @app_commands.describe(session="session id (defaults to this channel's active session)")
    async def receipt(self, interaction: discord.Interaction,
                      session: Optional[str] = None) -> None:
        await self._reply(
            interaction,
            lambda ch: self._receipt(ch, session),
        )

    @app_commands.command(name="verbs", description="Legal verbs for the session's current status")
    @app_commands.describe(session="session id (defaults to this channel's active session)",
                           limit="max verbs listed (default 12)")
    async def verbs(self, interaction: discord.Interaction,
                    session: Optional[str] = None, limit: int = 12) -> None:
        await self._reply(
            interaction,
            lambda ch: self._verbs(ch, session, limit),
        )


# --- the client ----------------------------------------------------------------------

class BonesClient(discord.Client):
    """Minimal client: no privileged intents, guild-scoped sync on boot."""

    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.none())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        guild = discord.Object(id=GUILD_ID)
        synced = await self.tree.sync(guild=guild)
        names = sorted(c.name for c in synced)
        print(f"[bones-adapter] synced {len(synced)} guild command(s) {names} to guild {GUILD_ID}")

    async def on_ready(self) -> None:
        print(f"[bones-adapter] connected as {self.user}; /bones live in guild "
              f"{GUILD_ID} (NT-ACv2), answering in channel {CHANNEL_ID} (#game-c-overview)")


def build_bot() -> tuple[BonesClient, BonesGroup]:
    """Assemble client + slash group. Offline-safe: no token, no network."""
    client = BonesClient()
    group = BonesGroup(BonesHub())
    client.tree.add_command(group, guild=discord.Object(id=GUILD_ID))
    return client, group


# --- runtime token (process start, value never surfaces) -----------------------------

def load_token(env_file: Path = ENV_FILE) -> str:
    """Read DISCORD_BOT_TOKEN from the hermes env file at process start.

    The returned value goes only to client.run(). Errors name the file and the
    variable, never the value.
    """
    if not env_file.is_file():
        raise SystemExit(f"[bones-adapter] no env file at {env_file}; "
                         f"cannot read {TOKEN_VAR}")
    for raw in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip().removeprefix("export ").strip() == TOKEN_VAR:
            token = value.strip().strip('"').strip("'")
            if token:
                return token
            break
    raise SystemExit(f"[bones-adapter] {TOKEN_VAR} is not set in {env_file}")


# --- entrypoint -----------------------------------------------------------------------

def callback_of(cmd: Any) -> Callable[..., Any]:
    """The raw function behind a discord.py command object (or itself)."""
    return getattr(cmd, "callback", cmd)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="bones-adapter",
                                 description="thin /bones Discord adapter (formatting only)")
    ap.add_argument("--check", action="store_true",
                    help="dry-run: register the commands and print them; "
                         "no token read, no connect")
    args = ap.parse_args(argv)

    client, group = build_bot()

    if args.check:
        print("[bones-adapter] --check: dry-run (no token read, no connect)")
        print(f"[bones-adapter] guild {GUILD_ID} (NT-ACv2), "
              f"channel {CHANNEL_ID} (#game-c-overview)")
        for cmd in group.commands:
            params = ", ".join(
                p.name + ("" if p.required else " (opt)")
                for p in getattr(cmd, "parameters", [])
            )
            print(f"  /bones {cmd.name}  [{params}]  {cmd.description}")
        print(f"[bones-adapter] {len(group.commands)} subcommands registered; "
              f"connect skipped (--check)")
        return 0

    token = load_token()
    client.run(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
