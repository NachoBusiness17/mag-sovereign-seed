"""ecosystem_surface — the ghost surface that shows the whole ecosystem, machine-readable.

The operator's idea (2026-08-10): "our ghost surface needs to show what our swarms are doing and
bring in the entire ecosystem we have access to in a machine readable format that allows instant
inference and handoffs of memory or placing rib files like qr codes so we can cut costs even
further within our system."

What this does:
  1. ecosystem()  — aggregate EVERYTHING (swarms, modules, steal/knowledge, ledgers, memlang
                    opcodes, cost, REST, cross-agent handoffs) into one machine-readable bundle.
                    Deterministic, $0, no LLM.
  2. rib()        — compress the ecosystem into a compact scannable RIB token (the "QR code"):
                    a short rib_id + a base64 payload + an optional QR PNG. Any agent/seat can
                    SCAN it and instantly infer ecosystem state WITHOUT re-deriving/re-fetching.
  3. scan()       — decode a RIB payload (or scan the live ecosystem) -> instant-inference summary
                    + memory-handoff pointers (memlang tokens). This is the cost cut: one scan
                    replaces a full re-derivation.
  4. qrcode()     — render the rib payload as a real QR PNG (data URI) if the `qrcode` lib is
                    available; otherwise the base64 payload IS the QR-like token.

Cost logic: every scan is local + deterministic ($0) and replaces the tokens/bytes you'd otherwise
spend re-deriving the same state. rib() reports the bytes it encodes so you can see the savings.

Schema: ecosystem_surface.v1
CLI: python -m mag.ecosystem_surface ecosystem | rib | scan [payload] | qrcode [payload]
REST: GET /api/v1/ecosystem · GET /api/v1/ecosystem/rib · GET /api/v1/ecosystem/scan
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "ecosystem_surface.v1"
RIB_DIR = ROOT / "memory" / "rib"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fingerprint(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str, ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:16]


# ────────────────────────────────────────────── collectors (each defensive, $0) ──
def _collect_swarms() -> dict[str, Any]:
    """What our swarms are doing: the swarm roster + per-agent health, plus live traces."""
    out: dict[str, Any] = {"roster": [], "summary": {}}
    try:
        from mag.swarm_health import AGENTS, swarm_health
        h = swarm_health() or {}
        out["summary"] = {k: h.get(k) for k in ("up", "degraded", "down", "total") if k in h}
        for name in AGENTS:
            try:
                from mag.swarm_health import probe_agent
                row = probe_agent(name) or {}
                out["roster"].append({
                    "name": name,
                    "up": bool(row.get("up")),
                    "staleness_s": row.get("staleness_s"),
                    "status": row.get("status"),
                })
            except Exception:
                out["roster"].append({"name": name, "up": None, "note": "probe unavailable"})
    except Exception as e:
        out["error"] = str(e)[:120]
    return out


def _collect_modules() -> list[str]:
    """The ecosystem inventory: every mag module we can call (the 'entire ecosystem we have')."""
    try:
        mag = ROOT / "mag"
        return sorted(p.stem for p in mag.glob("*.py") if not p.stem.startswith("_"))
    except Exception:
        return []


def _collect_steal() -> list[str]:
    """Steal/knowledge base (case law) available for instant inference."""
    try:
        d = ROOT / "memory" / "steal"
        return sorted(p.name for p in d.glob("*.md")) if d.is_dir() else []
    except Exception:
        return []


def _collect_ledgers() -> dict[str, Any]:
    """Ledgers = the machine's source of truth (activity + spend + case law)."""
    out: dict[str, Any] = {}
    try:
        sk = ROOT / "memory" / "improve" / "skill_ledger.jsonl"
        out["skill_ledger"] = sum(1 for _ in sk.open(encoding="utf-8", errors="replace")) if sk.is_file() else 0
    except Exception:
        out["skill_ledger"] = 0
    try:
        ev = ROOT / "logs" / "memory_events.jsonl"
        if ev.is_file():
            lines = [l for l in ev.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
            out["memory_events"] = len(lines)
            out["memory_events_tail"] = lines[-3:] if lines else []
    except Exception:
        pass
    return out


def _collect_handoffs() -> list[dict[str, Any]]:
    """Memory-handoff surface: recent cross-agent + memory-event activity (pointers, not bodies)."""
    out: list[dict[str, Any]] = []
    try:
        ev = ROOT / "logs" / "memory_events.jsonl"
        if ev.is_file():
            for line in ev.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                    out.append({"ts": r.get("ts"), "kind": r.get("event_kind"),
                                "seat": r.get("seat"), "refs": r.get("artifact_refs", [])})
                except Exception:
                    continue
    except Exception:
        pass
    return out


def _collect_cost() -> dict[str, Any]:
    """The cost/economy half (why scanning is the cost cut)."""
    out: dict[str, Any] = {}
    try:
        from mag.ghost_grok_dashboard import saved_vs_projected
        s = saved_vs_projected() or {}
        out["saved_vs_projected"] = s
    except Exception:
        pass
    return out


def _collect_opcodes() -> dict[str, int]:
    """memlang opcodes = the memory-handoff vocab (the QR-code vocabulary)."""
    try:
        from mag.memlang import OPCODES
        return dict(OPCODES)
    except Exception:
        return {}


def ecosystem() -> dict[str, Any]:
    """Aggregate the WHOLE ecosystem into one machine-readable bundle."""
    eco: dict[str, Any] = {
        "schema": SCHEMA,
        "ts": _now(),
        "swarms": _collect_swarms(),
        "modules": _collect_modules(),
        "steal": _collect_steal(),
        "ledgers": _collect_ledgers(),
        "handoffs": _collect_handoffs(),
        "cost": _collect_cost(),
        "opcodes": _collect_opcodes(),
        "n_modules": 0,
    }
    eco["n_modules"] = len(eco["modules"])
    eco["fingerprint"] = _fingerprint(eco)
    return eco


# ────────────────────────────────────────────── RIB (the QR-code) ──────────────
def _compact(eco: dict[str, Any]) -> dict[str, Any]:
    """The slimmed bundle actually encoded in the RIB — enough for instant inference + handoff."""
    sw = eco.get("swarms", {})
    return {
        "v": 1,
        "ts": eco.get("ts"),
        "fingerprint": eco.get("fingerprint"),
        "n_modules": eco.get("n_modules"),
        "swarms": {
            "summary": sw.get("summary", {}),
            "roster": [{"name": r.get("name"), "up": r.get("up"),
                        "status": r.get("status")} for r in sw.get("roster", [])],
        },
        "ledgers": eco.get("ledgers", {}),
        "n_steal": len(eco.get("steal", [])),
        "opcodes": eco.get("opcodes", {}),
    }


def _encode(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), default=str, ensure_ascii=True).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def _decode(payload_b64: str) -> dict[str, Any]:
    raw = zlib.decompress(base64.urlsafe_b64decode(payload_b64.encode("ascii")))
    return json.loads(raw.decode("utf-8"))


def rib(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compress the ecosystem into a scannable RIB token (the QR code). $0, deterministic."""
    eco = payload if payload is not None else ecosystem()
    comp = _compact(eco)
    enc = _encode(comp)
    return {
        "schema": "ecosystem_surface.rib.v1",
        "ok": True,
        "ts": _now(),
        "rib_id": _fingerprint(comp),
        "fingerprint": comp.get("fingerprint"),
        "payload": enc,           # the scannable token (compact base64)
        "payload_bytes": len(enc),
        "raw_bytes": len(json.dumps(comp, separators=(",", ":"), default=str)),
        "compression_ratio": round(
            len(enc) / max(1, len(json.dumps(comp, separators=(",", ":"), default=str))), 3
        ),
        "note": "scan this payload -> instant inference + memory handoffs, $0, no re-derivation.",
    }


def scan(payload_b64: str | None = None) -> dict[str, Any]:
    """Scan a RIB payload (or the live ecosystem) -> instant-inference + handoff pointers.

    This is the cost cut: one local deterministic decode replaces re-deriving/re-fetching the
    whole ecosystem. Output shape is stable so any agent/seat can consume it directly.
    """
    eco: dict[str, Any]
    source = "rib"
    if payload_b64:
        try:
            eco = _decode(payload_b64)
            source = "rib-decode"
        except Exception as e:
            return {"ok": False, "error": f"bad rib payload: {str(e)[:120]}", "payload": payload_b64[:64]}
    else:
        eco = _compact(ecosystem())

    sw = eco.get("swarms", {})
    up = [r.get("name") for r in sw.get("roster", []) if r.get("up")]
    down = [r.get("name") for r in sw.get("roster", []) if r.get("up") is False]

    # Instant-inference summary — compact, ready to hand to an agent as context.
    inference = {
        "fingerprint": eco.get("fingerprint"),
        "swarms": f"{len(up)} up ({', '.join(up) or 'none'})"
                  + (f"; {len(down)} down ({', '.join(down)})" if down else ""),
        "n_modules": eco.get("n_modules"),
        "n_steal": eco.get("n_steal"),
        "ledgers": eco.get("ledgers", {}),
        "opcodes_known": sorted(eco.get("opcodes", {})),
    }

    # Memory-handoff pointers — memlang tokens for each subsystem (the QR handoff).
    handoffs: dict[str, Any] = {}
    try:
        from mag.memlang import compile_token
        for action in ("handoff_build", "rib_elevate", "research_pack", "steer"):
            t = compile_token(action, f"ecosystem-rib {eco.get('fingerprint')}",
                              {"rib_id": eco.get("fingerprint"), "source": source})
            handoffs[action] = {"opcode": t.get("opcode"), "anchor": (t.get("anchor_hex") or "")[:12],
                                "token_len": t.get("token_len"), "ok": bool(t.get("ok"))}
    except Exception as e:
        handoffs["error"] = str(e)[:120]

    return {
        "schema": "ecosystem_surface.scan.v1",
        "ok": True,
        "ts": _now(),
        "source": source,
        "cost": {"local": True, "llm": False, "note": "$0 deterministic decode — replaces re-derivation"},
        "inference": inference,
        "handoffs": handoffs,
    }


def qrcode(payload_b64: str | None = None) -> dict[str, Any]:
    """Render the RIB payload as a real QR PNG data-URI if `qrcode` is installed; else return the
    base64 token itself (which IS the QR-like scannable token). Deterministic, $0."""
    enc = payload_b64 or rib()["payload"]
    try:
        import qrcode
        from io import BytesIO
        img = qrcode.make(enc)
        buf = BytesIO()
        img.save(buf, format="PNG")
        data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        return {"ok": True, "rib_payload": enc, "png_data_uri": data_uri, "format": "png",
                "note": "scan with any QR reader / or feed rib_payload to /api/v1/ecosystem/scan"}
    except Exception:
        return {"ok": True, "rib_payload": enc, "png_data_uri": None, "format": "token",
                "note": "qrcode lib not installed — the base64 payload is the scannable QR-like RIB token"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ecosystem_surface", description="ghost's ecosystem surface (machine-readable)")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("ecosystem")
    sub.add_parser("rib")
    p_s = sub.add_parser("scan")
    p_s.add_argument("payload", nargs="?", default=None)
    p_q = sub.add_parser("qrcode")
    p_q.add_argument("payload", nargs="?", default=None)
    a = p.parse_args(argv)
    if a.cmd == "ecosystem":
        print(json.dumps(ecosystem(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "rib":
        print(json.dumps(rib(), indent=2, ensure_ascii=False))
    elif a.cmd == "scan":
        print(json.dumps(scan(a.payload), indent=2, ensure_ascii=False))
    elif a.cmd == "qrcode":
        out = qrcode(a.payload)
        out.pop("png_data_uri", None)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        p.print_help()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
