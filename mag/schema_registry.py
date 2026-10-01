"""schema_registry — apply the system's versioning discipline ("steal previous versioning")
to the modules built in the 2026-08-10 session, everywhere.

Steals agent_state.py's versioned-packs-on-a-chain pattern:
  - Each module self-describes: SCHEMA = "<name>.vN".
  - Mutable state is CONTENT-ADDRESSED and APPEND-ONLY: LATEST is the viewport, versions/ is
    history, amend = new version (never erase). Each commit carries content_commit + parent_commit
    + merkle root over leaves.
  - LATEST is read-first for compatibility; old readers of a flat file still work.

This module:
  1. MANIFEST — every session module (name, schema, version, purpose, state_file, writable).
  2. versions() — the live, queryable version manifest (reads each module's SCHEMA).
  3. checkpoint(kind, payload) — content-addressed versioned write (LATEST + versions/<commit>).
  4. history(kind) — list the append-only version history for a state kind.
  5. REST: GET /api/v1/schemas — enumerate the whole registry for the seat.

Schema: schema_registry.v1 · deterministic · $0.
CLI: python -m mag.schema_registry versions | checkpoint <kind> "<json>" | history <kind> | status
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
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

SCHEMA = "schema_registry.v1"
STATE_ROOT = ROOT / "memory" / "registry_state"

# Every module built this session: self-describing schema + where it writes state.
MANIFEST: list[dict[str, Any]] = [
    {"name": "ai_landscape", "module": "mag.ai_landscape", "schema": "ai_landscape.v1",
     "purpose": "ghost AI-expert registry (bleeding-edge -> our modules + delta)",
     "state_file": None, "writable": False},
    {"name": "ecosystem_surface", "module": "mag.ecosystem_surface", "schema": "ecosystem_surface.v1",
     "purpose": "whole-ecosystem machine-readable RIB bundle + scan (QR-like)",
     "state_file": "memory/rib", "writable": False},
    {"name": "whisper_image", "module": "mag.whisper_image", "schema": "whisper_image.v1",
     "purpose": "LSB image steganography for the whisper protocol (keyed/deniable)",
     "state_file": "memory/runs/whisper_images", "writable": True},
    {"name": "archetype_image", "module": "mag.archetype_image", "schema": "archetype_image.v1",
     "purpose": "Jungian-archetype research artifacts (lens-enhanced, invariant by seed)",
     "state_file": "memory/runs/archetype_art", "writable": True},
    {"name": "knowledge_graph", "module": "mag.knowledge_graph", "schema": "knowledge_graph.v2",
     "purpose": "accurate source-backed knowledge graph + auto-consult (GraphRAG/Mem0/Letta)",
     "state_file": "memory/knowledge_graph", "writable": True},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _leaf_hash(obj: dict[str, Any]) -> str:
    return _h(b"reg_leaf:" + json.dumps(obj, sort_keys=True, default=str).encode("utf-8"))


def _merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return _h(b"reg_empty")
    layer = list(leaves)
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i + 1] if i + 1 < len(layer) else left
            nxt.append(_h(b"reg_node:" + left.encode() + b":" + right.encode()))
        layer = nxt
    return layer[0]


def _read_schema(module: str) -> str | None:
    """Read the module's own SCHEMA constant (self-describing) — the source of truth."""
    try:
        m = __import__(module, fromlist=["SCHEMA"])
        return str(getattr(m, "SCHEMA", "") or "") or None
    except Exception:
        return None


def versions() -> dict[str, Any]:
    """The live version manifest — schema read from each module, fallback to MANIFEST."""
    out = []
    for row in MANIFEST:
        live = _read_schema(row["module"])
        version = (live or row["schema"]).split(".v")[-1] if "." in (live or row["schema"]) else "?"
        out.append({"name": row["name"], "module": row["module"],
                    "schema": live or row["schema"], "version": version,
                    "purpose": row["purpose"], "writable": row["writable"],
                    "state_file": row["state_file"]})
    return {"schema": SCHEMA, "ts": _now(), "ok": True, "modules": out}


def checkpoint(kind: str, payload: Any, *, label: str = "") -> dict[str, Any]:
    """CONTENT-ADDRESSED, APPEND-ONLY versioned write (agent_state steal): LATEST + versions/<c>.
    Amend = new version, never erase. Returns the commit."""
    kind = kind.replace("\\", "/").replace("/", "_")
    d = STATE_ROOT / kind
    d.mkdir(parents=True, exist_ok=True)
    vers = d / "versions"
    vers.mkdir(parents=True, exist_ok=True)
    latest_path = d / "LATEST.json"
    parent_commit = ""
    if latest_path.is_file():
        try:
            parent_commit = str(json.loads(latest_path.read_text(encoding="utf-8")).get("content_commit") or "")
        except Exception:
            pass
    content = {"kind": kind, "label": label, "payload": payload}
    content_commit = _h(b"reg_content:" + json.dumps(content, sort_keys=True, default=str).encode("utf-8"))
    # merkle over prior leaves + this commit (append-only integrity)
    leaves: list[str] = []
    if vers.is_dir():
        leaves = [p.stem for p in vers.glob("*.json")][-256:]
    leaves.append(content_commit)
    merkle = _merkle_root(leaves)
    rec = {"content_commit": content_commit, "parent_commit": parent_commit,
           "merkle_root": merkle, "ts": _now(), "label": label, "payload": payload}
    (vers / f"{content_commit}.json").write_text(json.dumps(rec, ensure_ascii=False, default=str), encoding="utf-8")
    latest_path.write_text(json.dumps(rec, ensure_ascii=False, default=str), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "kind": kind, "content_commit": content_commit,
            "parent_commit": parent_commit, "merkle_root": merkle, "n_versions": len(leaves)}


def history(kind: str) -> dict[str, Any]:
    """The append-only version history for a state kind."""
    kind = kind.replace("\\", "/").replace("/", "_")
    d = STATE_ROOT / kind / "versions"
    rows = []
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            try:
                rows.append(json.loads(p.read_text(encoding="utf-8", errors="replace")))
            except Exception:
                continue
    return {"ok": True, "schema": SCHEMA, "kind": kind, "count": len(rows),
            "versions": rows[-20:]}


def status() -> dict[str, Any]:
    v = versions()
    return {"ok": True, "schema": SCHEMA, "n_modules": len(v["modules"]),
            "schemas": [m["schema"] for m in v["modules"]]}


# ─────────────────────────────────────────────── STATELESS versioning (the steal) ──
# You don't version a stateless PROCESS (it's disposable) — you version the IMMUTABLE,
# CONTENT-ADDRESSED artifacts it emits, and you make any version deterministically REPRODUCIBLE
# from recorded inputs. Stolen from:
#   Git      — immutable objects + a stable pointer (LATEST/HEAD) to dereference.
#   Nix      — hermetic: version id = hash(inputs[+seed]); same inputs -> same artifact, any pod.
#   Docker   — reference-counted GC: prune unreferenced/old immutable versions (cost control).
#   verkle   — root-hash / content-addressing: any reader verifies a version from its id alone.

def hermetic_id(kind: str, inputs: Any) -> str:
    """Nix-style deterministic version id = hash(canonical inputs). Same inputs -> same id, so any
    stateless pod reproduces the same artifact. Record the inputs; reproduction is free."""
    raw = json.dumps({"kind": kind, "inputs": inputs}, sort_keys=True, default=str).encode("utf-8")
    return _h(b"hermetic:" + raw)


def commit_stateless(kind: str, inputs: Any, *, seed: Any = None, label: str = "") -> dict[str, Any]:
    """Immutable, content-addressed, reproducible commit for a STATELESS pod. No process state —
    the artifact is keyed by hermetic_id(inputs[+seed]), so any pod (or a future one) can reproduce
    it deterministically. First write wins (amend = a new id, never mutate)."""
    kind = kind.replace("\\", "/").replace("/", "_")
    id_ = hermetic_id(kind, inputs)
    d = STATE_ROOT / kind
    art = d / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    artifact = {"kind": kind, "id": id_, "inputs": inputs, "seed": seed,
                "label": label, "ts": _now()}
    art_f = art / f"{id_}.json"
    if not art_f.is_file():  # immutable: first write wins
        art_f.write_text(json.dumps(artifact, ensure_ascii=False, default=str), encoding="utf-8")
    hist_f = d / "history.jsonl"
    with hist_f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(artifact, ensure_ascii=False, default=str) + "\n")
    return {"ok": True, "schema": SCHEMA, "kind": kind, "id": id_, "immutable": True,
            "reproducible": "same inputs -> same id -> same artifact, from any stateless pod",
            "seed": seed}


def resolve(kind: str, pointer: str = "latest") -> dict[str, Any]:
    """STATELESS READER: dereference a version pointer (a hermetic id OR 'latest') to the immutable
    artifact. No session needed — fetch by hash/pointer from shared state."""
    kind = kind.replace("\\", "/").replace("/", "_")
    art = STATE_ROOT / kind / "artifacts"
    if pointer and pointer != "latest":
        p = art / f"{pointer}.json"
        if p.is_file():
            return {"ok": True, "kind": kind, "id": pointer,
                    "artifact": json.loads(p.read_text(encoding="utf-8", errors="replace"))}
        return {"ok": False, "error": "artifact not found", "kind": kind, "id": pointer}
    hist_f = STATE_ROOT / kind / "history.jsonl"
    last = None
    if hist_f.is_file():
        for line in hist_f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    last = json.loads(line)
                except Exception:
                    pass
    if not last:
        return {"ok": False, "error": "no versions", "kind": kind}
    return {"ok": True, "kind": kind, "id": last["id"], "artifact": last}


def gc(kind: str, *, keep_n: int = 10, keep_ids: list[str] | None = None) -> dict[str, Any]:
    """DOCKER-STYLE reference-counted reaping: prune old/unreferenced immutable versions for cost
    control. Keeps the newest keep_n unique ids + any keep_ids; artifacts are immutable so removing
    a history row is safe (and a pod can always reproduce it from recorded inputs)."""
    kind = kind.replace("\\", "/").replace("/", "_")
    hist_f = STATE_ROOT / kind / "history.jsonl"
    rows: list[dict[str, Any]] = []
    if hist_f.is_file():
        for line in hist_f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    keep: set[str] = set(keep_ids or [])
    seen: list[str] = []
    for r in reversed(rows):
        if r.get("id") not in seen:
            seen.append(r.get("id"))
        if len(seen) >= keep_n:
            break
    keep |= set(seen)
    kept_rows = [r for r in rows if r.get("id") in keep]
    pruned = len(rows) - len(kept_rows)
    hist_f.write_text(
        "".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in kept_rows),
        encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "kind": kind, "kept": len({r.get("id") for r in kept_rows}),
            "pruned": pruned, "history_rows": len(kept_rows)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="schema_registry", description="versioning discipline for session modules")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("versions")
    c = sub.add_parser("checkpoint"); c.add_argument("kind"); c.add_argument("json_payload")
    h = sub.add_parser("history"); h.add_argument("kind")
    sub.add_parser("status")
    her = sub.add_parser("hermetic"); her.add_argument("kind"); her.add_argument("json_inputs")
    com = sub.add_parser("commit"); com.add_argument("kind"); com.add_argument("json_inputs"); com.add_argument("--seed", default=None)
    res = sub.add_parser("resolve"); res.add_argument("kind"); res.add_argument("pointer", nargs="?", default="latest")
    gc = sub.add_parser("gc"); gc.add_argument("kind"); gc.add_argument("--keep", type=int, default=10)
    a = p.parse_args(argv)
    if a.cmd == "versions":
        print(json.dumps(versions(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "checkpoint":
        try:
            pl = json.loads(a.json_payload)
        except Exception:
            pl = a.json_payload
        print(json.dumps(checkpoint(a.kind, pl), indent=2, ensure_ascii=False))
    elif a.cmd == "history":
        print(json.dumps(history(a.kind), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    elif a.cmd == "hermetic":
        try:
            inp = json.loads(a.json_inputs)
        except Exception:
            inp = a.json_inputs
        print(json.dumps({"id": hermetic_id(a.kind, inp)}, indent=2, ensure_ascii=False))
    elif a.cmd == "commit":
        try:
            inp = json.loads(a.json_inputs)
        except Exception:
            inp = a.json_inputs
        print(json.dumps(commit_stateless(a.kind, inp, seed=a.seed), indent=2, ensure_ascii=False))
    elif a.cmd == "resolve":
        print(json.dumps(resolve(a.kind, a.pointer), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "gc":
        print(json.dumps(gc(a.kind, keep_n=a.keep), indent=2, ensure_ascii=False))
    else:
        p.print_help(); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
