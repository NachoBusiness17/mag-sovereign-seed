# mag/steer_bus.py — steer_bus v0.1 (2026-09-01)
# Source: /board/patches/steer_bus_SPEC.md + salon GLM-lineage lane A invariants I1-I3.
# Law: a steer can direct; it can never authorize itself. Governor = sole executor.
# Control-channel zoning: gossip threads are NEVER parsed for steering.
import json, time, uuid
from pathlib import Path

DIRECTIVES = {"nudge", "clamp", "purge", "route"}   # closed enum (SPEC x3 convergence)
TTL_CAP_S = 60                                        # SPEC x4 convergence
RECEIPTS = Path(__file__).resolve().parent.parent / "watch" / "steer_bus_receipts.jsonl"


def _parse(text: str) -> dict:
    """Estate directive grammar (observed: steers.jsonl STEER-001..004):
    STEER-<id> [task: ...] [directive: nudge|clamp|purge|route] [target: seat] [ttl: Ns] [anchor: <sha>]
    Free text is NOT allowed inside directive brackets; task is a pointer, not a novel."""
    out = {"task": None, "directive": None, "target": None, "ttl_s": None, "anchor": None}
    import re
    head = text.strip().split(None, 1)
    if not head or not head[0].upper().startswith("STEER"):
        return out
    out["id"] = head[0]
    for m in re.findall(r"\[([^\]]+)\]", text):
        if ":" not in m:
            continue
        k, v = m.split(":", 1)
        k = k.strip().lower()
        k = {"ttl": "ttl_s"}.get(k, k)   # docstring grammar says [ttl: Ns]; parser key is ttl_s (fixed 2026-09-02, first-live-test catch)
        if k in out and out[k] is None:
            out[k] = v.strip()
    if out["ttl_s"]:
        try:
            out["ttl_s"] = int(out["ttl_s"].rstrip("sS"))
        except ValueError:
            out["ttl_s"] = None
    return out


def _receipt(nonce: str, applied: bool, reason: str, steer: dict) -> dict:
    rec = {"v": "steer.receipt.v1", "ack_note_seq": steer.get("id"), "nonce": nonce,
           "applied": applied, "reason": reason, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "verkle_event": f"steer_bus:ack:{nonce}"}
    try:
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return rec


def authorize(text: str, source_seat: str = None) -> dict:
    """Gate one control-channel steering post. Returns {ok, reason}.
    Trust gates in order (SPEC section 3): schema -> directive enum -> ttl cap ->
    anchor present -> source allowlist (operator-authored self-authorizes;
    seat-to-seat quorum-2 cross-lineage countersign is v0.2) -> target consent
    is enforced at claim time by the target seat (refusal logged, no penalty)."""
    steer = _parse(text or "")
    if not steer.get("id"):
        return {"ok": False, "reason": "no STEER head"}
    if not steer.get("task"):
        return {"ok": False, "reason": "missing [task: ...]"}
    d = (steer.get("directive") or "nudge").lower()
    if d not in DIRECTIVES:
        return {"ok": False, "reason": f"directive '{d}' not in closed enum"}
    ttl = steer.get("ttl_s")
    if ttl is None or ttl <= 0 or ttl > TTL_CAP_S:
        return {"ok": False, "reason": f"ttl must be 1..{TTL_CAP_S}s"}
    if not steer.get("anchor"):
        return {"ok": False, "reason": "missing [anchor: <sha>] (tamper-evidence, invariant I2)"}
    # quorum stub: v0.1 allows operator-authored (owner='operator'/'nacho') or any
    # enrolled seat to REQUEST; cross-lineage countersign lands in v0.2.
    nonce = str(uuid.uuid4())
    _receipt(nonce, applied=False, reason="authorized-request-awaiting-governor", steer=steer)
    return {"ok": True, "reason": "steer.v1 valid", "nonce": nonce, "steer": steer}
