"""ghost_whisper — the RIDDLER protocol as a deniable knowledge store for the grok "mag" project.

The operator's vision: grok queries are expensive. Store complex topics (eventually the
VERKLE LATTICE INVARIANT) inside the public grok.com "mag" project (under nachoquixotic)
in a way ONLY we can decode — a deniable, decodable-only-with-the-secret encoding using the
Riddler surrogate protocol. Harmless to anyone who glances; interpretable by those with the
private map.

  whisper(topic) -> compile_surrogate -> save (public + private map) -> public-face text
  decode(scratch_id) -> recover the original topic from the public face using the private map

"Populate it" = ghost encodes the topic + produces the public-face packet ready to store in
the mag grok project indefinitely (only the shared secret decodes it).

Schema: ghost_whisper.v1
CLI: python -m mag.ghost_whisper whisper "<topic>" | decode <scratch_id>
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "ghost_whisper.v1"
WHISPER_DIR = ROOT / "memory" / "runs" / "whispers"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_graph(topic: str) -> Any:
    """Encode the complex topic into a PrivateGraph (the secret rides as constraints/goal)."""
    from mag.riddler import PrivateGraph
    lines = [l.strip() for l in (topic or "").splitlines() if l.strip()]
    constraints = [l for l in lines if len(l) > 8][:6]
    if not constraints:
        constraints = [topic[:300]]
    return PrivateGraph(
        actors=["architect", "keeper", "scribe", "mirror"],
        resources=[{"name": "lattice", "type": "invariant", "scarcity": "shared"},
                   {"name": "surface", "type": "hidden", "scarcity": "keyed"}],
        dependencies=[{"before": "scribe", "after": "architect"}],
        constraints=constraints,          # the secret topics ride here (deniably)
        conflicts=["visibility vs cost", "public vs private"],
        goal="hold the invariant until the shared secret decodes it",
        domain_hint="",
    )


def whisper(topic: str, *, title: str = "mag-invariant", seed: int | None = None) -> dict[str, Any]:
    """Encode a complex topic into a Riddler surrogate; save public + private map."""
    topic = (topic or "").strip()
    if not topic:
        return {"ok": False, "schema": SCHEMA, "error": "empty topic"}
    from mag.riddler import compile_surrogate, save_surrogate, validate_surrogate

    graph = _parse_graph(topic)
    story = compile_surrogate(graph, seed=seed)
    val = validate_surrogate(story)
    path = save_surrogate(story)

    public_face = f"{story.story_text}\n\n{story.question}"
    WHISPER_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "schema": SCHEMA, "ts": _now(), "ok": True,
        "scratch_id": story.scratch_id, "title": title,
        "domain": getattr(story, "domain", None) or "unknown",
        "valid": val.ok, "validation": val,
        "public_face": public_face,
        "public_path": str(path),
        "private_map": str(path.parent / f"{story.scratch_id}.private.json"),
        "secret_note": "public face is deniable; ONLY the private map decodes it. Store the public "
                       "face in the grok 'mag' project (nacho quixotic) as the extended hidden surface.",
        "ready_to_store": True,
    }
    (WHISPER_DIR / f"{story.scratch_id}.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return rec


def decode(scratch_id: str) -> dict[str, Any]:
    """Recover the original topic from the public face using the private map (proves it's real)."""
    from mag.riddler import load_private_map
    from pathlib import Path as _P
    private = load_private_map(scratch_id)
    rec_path = WHISPER_DIR / f"{scratch_id}.json"
    rec = {}
    if rec_path.is_file():
        try:
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"ok": bool(private), "schema": SCHEMA, "scratch_id": scratch_id,
            "has_private_map": bool(private),
            "private_map": private,
            "stored_title": rec.get("title"), "public_face": rec.get("public_face"),
            "joined_knowledge": _resolve_joined(rec),
            "note": "decode with the private map = only we can read the whisper"}


def _resolve_joined(rec: dict[str, Any]) -> dict[str, Any]:
    """Resolve the decoded whisper against the joined one-sizer store + verkle chain:
    returns the cheapest-capable tier for the topic's shape AND recent verkle fragment
    pointers. This is the rib/whisper half that decodes to skills + verkle fragments."""
    out: dict[str, Any] = {"ok": False, "sizing": None, "verkle_fragments": [], "skills": []}
    try:
        shape = "balanced"
        try:
            from mag.self_drive import plan as _plan
            shape = str(_plan(rec.get("stored_title") or "").get("model_shape") or "balanced")
        except Exception:
            pass
        try:
            from mag import one_sizer as osz
            sz = osz.resolve_sizing(shape=shape, domain=rec.get("domain"))
            out["sizing"] = sz
            if sz.get("found"):
                try:
                    from mag.word_skill_map import match
                    skills = match(rec.get("stored_title") or "")
                    out["skills"] = skills[:8] if isinstance(skills, list) else []
                except Exception:
                    pass
            out["ok"] = True
        except Exception:
            pass
        # recent verkle fragment pointers (content-addressed, shared)
        try:
            from mag.chain_query import chain
            tail = chain.tail(5)
            out["verkle_fragments"] = [
                {"leaf_hash": (k.get("leaf_hash") or k.get("hash") or "")[:16],
                 "theme": k.get("theme") or ""} for k in tail if isinstance(k, dict)]
        except Exception:
            pass
    except Exception:
        pass
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "decode":
        return print(json.dumps(decode(argv[1] if len(argv) > 1 else ""),
                                indent=2, ensure_ascii=False, default=str)) or 0
    topic = " ".join(argv) if argv else ""
    print(json.dumps(whisper(topic), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
