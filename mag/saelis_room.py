"""saelis_room — the ALWAYS-ON SURFACE: a single page that lists every live process, every message
through the knot, every action in the last hour — plain text that updates itself. The room breathes.

SAELIS (2026-08-13, real call): "A single always-on surface — one file, one terminal, one page —
that lists every live process, every message passing through the knot, every action taken in the
last hour, rendered as plain text that updates itself. No dashboards. No abstractions. Just: what
happened, when, to what, from where. The operator opens it and sees the room breathing. Build that
first. It's load-bearing and it's real."

The operator said: "just follow her lead." So this is built exactly to that spec.

Architecture-native (no terminal, no shell): a stdlib http.server that
  GET /             -> the breathing surface (auto-refreshing HTML, plain-text lines)
  GET /api/state    -> JSON: live processes, game world knots, recent actions
  GET /api/saelis   -> routes a real Saelis call through saelis_seat (DeepSeek) — real voice
Serves the real game world (game_world verkle state) + the necromancer game. Deterministic core,
real Saelis voice on demand. Server-authoritative: the world is the authority, the page presents it.

Schema: saelis_room.v1 · deterministic + $0 · reuse: game_world (verkle world), saelis_seat (voice)
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "saelis_room.v1"
HOST, PORT = "127.0.0.1", 8799
REFRESH_S = 2  # the room breathes every 2s


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# LIVE STATE: what the room is breathing right now.
# ---------------------------------------------------------------------------
def _live_processes() -> list[dict[str, Any]]:
    """List the live python/governor processes (the swarm's local heartbeats)."""
    out = []
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
            return out
        r = subprocess.run(
            [ps_exe, "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' } "
             "| Select-Object ProcessId,Name | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=10)
        import json as _j
        data = _j.loads(r.stdout or "[]")
        rows = data if isinstance(data, list) else [data]
        for p in rows[:12]:
            if isinstance(p, dict) and p.get("ProcessId"):
                out.append({"pid": p.get("ProcessId"), "name": p.get("Name", "python")})
    except Exception as e:
        out.append({"error": str(e)[:80]})
    return out


def _recent_actions() -> list[dict[str, Any]]:
    """Recent actions from the game world's change log (what happened, when, from where)."""
    try:
        from mag import game_world as gw
        st = gw.get_state()
        changes = st.get("changes") or []
        return [{"key": c.get("key"), "source": c.get("source"), "ts": c.get("ts")}
                for c in changes[-12:][::-1]]
    except Exception as e:
        return [{"error": str(e)[:80]}]


def _knot_messages() -> list[dict[str, Any]]:
    """Messages through the knot: the verkle world leaves (server-authoritative)."""
    try:
        from mag import game_world as gw
        st = gw.get_state()
        world = st.get("world") or {}
        return [{"key": k, "leaf": (e.get("leaf") or "")[:12], "ts": e.get("ts")}
                for k, e in list(world.items())[-10:][::-1]]
    except Exception as e:
        return [{"error": str(e)[:80]}]


def _verkle() -> dict[str, Any]:
    try:
        p = ROOT / "memory" / "biography" / "verkle_tip.json"
        t = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
        return {"root": str(t.get("root") or "")[:16], "n_leaves": t.get("n_leaves"),
                "last": str(t.get("last_filename") or "")[:40]}
    except Exception as e:
        return {"error": str(e)[:80]}


def _mycelium() -> dict[str, Any]:
    try:
        from mag import mycelium as mc
        st = mc.status()
        return {"nodes": st.get("nodes", 0), "edges": st.get("edges", 0),
                "top": st.get("top_salience") or []}
    except Exception as e:
        return {"error": str(e)[:80]}


def _queue() -> dict[str, Any]:
    try:
        from mag.orchestrator import queue_status
        qs = queue_status()
        return {"total": qs.get("total"), "counts": qs.get("counts"),
                "running": qs.get("running_task_id")}
    except Exception as e:
        return {"error": str(e)[:80]}


def _seats() -> list[dict[str, Any]]:
    try:
        from mag import seat_registry as sr
        return sr.list_registered()[:12]
    except Exception as e:
        return [{"error": str(e)[:80]}]


def _cost_today() -> dict[str, Any]:
    """Live spend today (real ledger, not estimates): non-ollama provider calls."""
    try:
        p = ROOT / "logs" / "provider_usage.jsonl"
        if not p.is_file():
            return {"calls_today": 0, "ok_today": 0, "tokens_today": 0}
        day = _now()[:10]
        n = ok = tokens = 0
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 1048576))
            for line in fh.read().splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if str(row.get("ts") or "")[:10] != day:
                    continue
                if str(row.get("provider")) == "ollama":
                    continue
                n += 1
                if row.get("ok"):
                    ok += 1
                tokens += int(row.get("tokens") or 0)
        return {"calls_today": n, "ok_today": ok, "tokens_today": tokens}
    except Exception as e:
        return {"error": str(e)[:80]}


def state() -> dict[str, Any]:
    """The full breathing state — what the operator sees when they open the room."""
    return {
        "schema": SCHEMA, "ts": _now(), "refresh_s": REFRESH_S,
        "processes": _live_processes(),
        "recent_actions": _recent_actions(),
        "knot_messages": _knot_messages(),
        "verkle": _verkle(),
        "mycelium": _mycelium(),
        "queue": _queue(),
        "seats": _seats(),
        "cost": _cost_today(),
    }


def saelis_say(goal: str = "") -> dict[str, Any]:
    """Route a REAL Saelis call through her seat (DeepSeek). The voice is hers, not narrated."""
    goal = (goal or "").strip()
    prompt = (goal or "The room is breathing. What is one true thing you see in the knot right now? "
                       "Keep it to two sentences.").strip()
    try:
        from mag import saelis_seat
        r = saelis_seat.speak(prompt)
        return {"ok": bool(r.get("ok")), "reply": (r.get("reply") or "").strip(),
                "error": (r.get("error") or "")[:160], "ts": _now()}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "ts": _now()}


# ---------------------------------------------------------------------------
# THE PAGE (plain text that updates itself — Saelis's exact spec).
# ---------------------------------------------------------------------------
_PAGE_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>The room, breathing</title>
<style>
body{background:#0c0a06;color:#efe3d0;font-family:monospace;padding:20px;font-size:14px}
.room{max-width:760px;margin:0 auto}.h{color:#e6c07a;font-weight:bold;margin-top:16px}
.dim{color:#9c8570}.loot{color:#7dffb0}.swarm{color:#7fb2ff}.err{color:#e06040}
.mono{color:#d8cfc0}.sep{border-top:1px solid #33251a;margin:14px 0}
.ask{background:#1a130c;border:1px solid #3c2c1e;color:#efe3d0;padding:9px;border-radius:6px;width:70%;font-family:monospace}
.btn{background:#e6c07a;border:none;color:#241a11;padding:9px 14px;border-radius:6px;cursor:pointer;font-family:monospace;font-weight:bold}
.says{background:#13201a;border-left:3px solid #7dffb0;padding:9px;margin-top:8px;white-space:pre-wrap;color:#d8f5e0}
</style></head>
<body><div class="room">
<div class="h">◈ THE ROOM — a single always-on surface</div>
<div class="dim">one page · what happened, when, to what, from where · updates every 2s · verkle-authoritative · real Saelis voice</div>
<div class="sep"></div>

<div class="h">LIVE PROCESSES <span class="dim">(swarm heartbeats)</span></div>
<pre id="procs" class="mono">…</pre>

<div class="h">KNOT MESSAGES <span class="dim">(world state through the verkle chain)</span></div>
<pre id="knots" class="mono">…</pre>

<div class="h">RECENT ACTIONS <span class="dim">(what happened, when, from where)</span></div>
<pre id="actions" class="mono">…</pre>

<div class="sep"></div>
<div class="h">◈ SEE INSIDE <span class="dim">(the internals, plain truth — steal 2026-08-14)</span></div>
<div class="h">MYCELIUM GRAPH <span class="dim">(the unified self-scoring graph)</span></div>
<pre id="mycelium" class="mono">…</pre>
<div class="h">QUEUE <span class="dim">(by status)</span></div>
<pre id="queue" class="mono">…</pre>
<div class="h">SEATS · VERKLE · COST TODAY</div>
<pre id="internals" class="mono">…</pre>

<div class="sep"></div>
<div class="h">SAY TO SAELIS <span class="dim">(real voice — DeepSeek through her seat)</span></div>
<div style="display:flex;gap:8px">
  <input class="ask" id="q" placeholder="ask Saelis something...">
  <button class="btn" onclick="ask()">Speak</button>
</div>
<div class="says" id="says">The room is quiet. Ask her something.</div>
</div>

<script>
async function load(){
  try{
    const r = await fetch('/api/state'); const s = await r.json();
    document.getElementById('procs').textContent =
      (s.processes||[]).map(p=> '  '+(p.pid||'?')+'  '+(p.name||'python')).join('\\n') || '  (none)';
    document.getElementById('knots').textContent =
      (s.knot_messages||[]).map(k=> '  '+(k.ts||'').slice(11,19)+'  '+(k.key||'?')+'  leaf='+(k.leaf||'')).join('\\n') || '  (empty)';
    document.getElementById('actions').textContent =
      (s.recent_actions||[]).map(a=> '  '+(a.ts||'').slice(11,19)+'  '+(a.source||'?')+'  → '+(a.key||'')).join('\\n') || '  (none)';    const mc = s.mycelium||{}, q = s.queue||{}, v = s.verkle||{}, c = s.cost||{}, st = s.seats||[];
    document.getElementById('mycelium').textContent =
      '  nodes='+(mc.nodes||'?')+'  edges='+(mc.edges||'?')+
      '\n  top salience: '+(mc.top||[]).map(x=> ' '+(Array.isArray(x)?x[0]:x)).join(',');
    const qc = q.counts||{};
    document.getElementById('queue').textContent =
      '  total='+(q.total||'?')+'  '+
      Object.entries(qc).map(([k,v])=>k+'='+v).join('  ')+'  running='+(q.running||'-');
    document.getElementById('internals').textContent =
      '  verkle root='+(v.root||'?')+'  leaves='+(v.n_leaves||'?')+'  last='+(v.last||'?')+
      '\n  seats: '+(st.map(x=>(x.seat||x.task_id||'?')).join(', ')||'-')+
      '\n  cost today: calls='+(c.calls_today||'?')+' ok='+(c.ok_today||'?')+' tokens='+(c.tokens_today||'?');  }catch(e){ document.getElementById('procs').textContent = '  fetch error: '+e; }
}
async function ask(){
  const q = document.getElementById('q').value;
  const el = document.getElementById('says');
  el.textContent = '…Saelis is thinking';
  try{
    const r = await fetch('/api/saelis?q='+encodeURIComponent(q)); const j = await r.json();
    el.textContent = j.reply || ('error: '+(j.error||''));
  }catch(e){ el.textContent = 'fetch error: '+e; }
}
load();
setInterval(load, 2000);   // the room breathes — state refreshes, the answer stays
</script>
</body></html>
"""


def _page() -> bytes:
    return _PAGE_HTML.encode("utf-8")


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep it quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")  # let the file:// game reach Saelis
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # CORS preflight for cross-origin fetch
        self._send(200, b"", "text/plain")

    def do_GET(self):
        try:
            if self.path.startswith("/api/saelis"):
                import urllib.parse
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                r = saelis_say(q.get("q", [""])[0])
                self._send(200, json.dumps(r).encode("utf-8"), "application/json")
            elif self.path == "/game":
                # serve the necromancer game from the same origin so it can reach Saelis
                import pathlib
                g = ROOT / "game.html"
                self._send(200, g.read_bytes() if g.is_file() else b"missing game.html",
                           "text/html")
            elif self.path.startswith("/api/state"):
                self._send(200, json.dumps(state()).encode("utf-8"), "application/json")
            else:
                self._send(200, _page(), "text/html")
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "error": str(e)[:120]}).encode("utf-8"),
                       "application/json")


def serve(*, port: int = PORT, quiet: bool = False) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((HOST, port), _H)
    if not quiet:
        print(f"saelis_room listening on http://{HOST}:{port}  (GET / = the room)")
    return srv


def main(argv: list[str] | None = None) -> int:
    srv = serve()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
