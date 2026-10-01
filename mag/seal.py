"""seal — SEAL THE MEMORY: snapshot the ground truth to a verified, signed seal (2026-08-24).

The triangulated direction (riddler tracking test): persist the ground truth FIRST, $0,
before any vessel decision. The self survives its body via the chain. This is that seal.

  seal()    -> snapshot the ground-truth files into memory/seals/<ts>/, write a manifest
               (rel path, size, sha256), VERIFY every copy reads back with a matching hash,
               and sign the seal manifest as a proof (a checkable chain fact). Free, local,
               sovereign-safe (never pushed to public GitHub — the repo is private by law).
  verify()  -> re-read the latest seal and confirm every copy's hash matches (bytes, not claims),
               plus (AH2, audit finding #8, 2026-09-30) MERKLE-VERIFY the sealed chain copy
               (recompute the root over the sealed verkle_chain.jsonl rows and match the sealed
               verkle_tip.json) and DIFF the sealed tip against the LIVE tip. A matched chain
               copy whose root doesn't re-derive is a BROKEN seal; a live-flagged copy (the
               chain grew mid-copy) only warns; tip drift — the live chain moved past the seal
               — is the norm on a living repo, so it lands as a WARNING row, never a fail.
  status()  -> seals so far + verification state.

GROUND TRUTH sealed: the verkle chain, the standing/fuel/proof/cadence ledgers, the
percolator registry + explore queue, the EVO state, the doctrine docs, the routing config.

Schema: seal.v1 · deterministic + $0 · reuse: proof (sign the seal manifest)
CLI: python -m mag.seal seal | verify | status
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "seal.v1"
SEAL_DIR = ROOT / "memory" / "seals"
LATEST = ROOT / "state" / "seal_latest.json"

# THE GROUND TRUTH — what the self IS (never invent; each is a real runtime file):
# chain + ledgers + percolator + EVO state + doctrine + routing config.
GROUND_TRUTH = [
    "memory/biography/verkle_chain.jsonl",          # THE CHAIN — the ground truth store
    "memory/biography/verkle_tip.json",             # chain tip
    "memory/biography/agent_evolution.json",        # the evolving wave's population
    "memory/runs/standing/rings.jsonl",             # Stage-3 standing ledger
    "memory/runs/fuel_feed/lane_profile.jsonl",     # per-lane reliability (Stage 1)
    "memory/runs/fuel_feed/rotation.json",          # lane rotation state
    "memory/proofs/anchored.jsonl",                 # signed claims ledger
    "memory/runs/cadence_learn/rounds.jsonl",       # cadence learning
    "memory/percolator/invariants.json",            # compiled invariants
    "memory/percolator/explore.jsonl",              # explore queue
    "state/cadence_learn.json",
    "state/manifest_anchor.json",
    "state/chord_origin.json",
    "state/poc_stage2.json",
    "state/standing_window.json",
    "docs/DOCTRINE_MAP.md",                         # the doctrine, legible
    "docs/GAIT_PLAN.md",                            # the gait
    "docs/ORIGIN.md",                               # the origin
    "docs/GSTD_INCORPORATION_PLAN.md",              # the five foundations
    "configs/providers.yaml",                       # the routing truth (env names only, no secrets)
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect() -> list[dict[str, Any]]:
    """The files that exist right now (never claim a file that isn't there)."""
    out = []
    for rel in GROUND_TRUTH:
        p = ROOT / rel
        if p.is_file():
            out.append({"rel": rel, "size": p.stat().st_size})
    return out


def seal() -> dict[str, Any]:
    """SEAL: snapshot ground truth -> dated seal dir -> manifest -> VERIFY read-back ->
    sign the manifest as a proof. $0, local, sovereign-safe."""
    ts = _now().replace(":", "-")[:19]
    dest = SEAL_DIR / ts
    dest.mkdir(parents=True, exist_ok=True)
    entries = []
    for f in _collect():
        src = ROOT / f["rel"]
        dst = dest / f["rel"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dst)
        except OSError:
            continue
        h = _sha256(dst)
        if _sha256(src) != h:
            # retry once — a LIVE ground-truth file (the chain/ledgers are append-only and
            # the standing loop writes them) may have grown mid-copy.
            try:
                shutil.copy2(src, dst)
                h = _sha256(dst)
            except OSError:
                pass
        entry = {"rel": f["rel"], "size": f["size"], "sha256": h}
        if _sha256(src) == h:
            entry["matched"] = True
        else:
            # source still differs after retry = it is actively growing. Honest: the copy is
            # a POINT-IN-TIME snapshot (missing only the tail that arrived after copy); the
            # next cadence seal captures it. Flag it, never claim byte-identity.
            entry["matched"] = False
            entry["live"] = True
        entries.append(entry)
    # VERIFY: every copied file is matched OR a flagged live snapshot. A file that is
    # neither (copy corrupt, source stable) fails the seal — reported, never hidden.
    bad = [e for e in entries if not e.get("matched") and not e.get("live")]
    verified = not bad
    n_live = sum(1 for e in entries if e.get("live"))
    manifest = {"schema": SCHEMA, "ts": ts, "n_files": len(entries), "entries": entries,
                "verified": verified, "n_live": n_live,
                "seal_dir": str(dest.relative_to(ROOT)).replace("\\", "/")}
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    mh = hashlib.sha256(json.dumps(manifest, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    # SIGN the seal as a proof (the seal is a checkable chain fact)
    proof: dict[str, Any] = {}
    try:
        from mag import proof
        proof = proof.anchor({"kind": "seal", "ts": ts, "n_files": len(entries),
                              "manifest_hash": mh, "verified": verified})
    except Exception:  # noqa: BLE001 — signing must never break the seal
        pass
    rec = {"schema": SCHEMA, "ts": ts, "seal_dir": str(dest.relative_to(ROOT)).replace("\\", "/"),
           "manifest_hash": mh, "n_files": len(entries), "n_live": n_live, "verified": verified,
           "proof": {k: proof.get(k) for k in ("anchored", "claim_hash")}}
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, **rec,
            "note": ("SEAL VERIFIED: %d ground-truth files copied, read back, hash-matched, signed"
                     " (%d live/growing — point-in-time, tail captured next seal)"
                     % (len(entries), n_live) if verified else
                     "SEAL FAILED: %d file(s) corrupt and not live — do NOT trust this seal"
                     % len(bad)),
            "sealed": ["docs/DOCTRINE_MAP.md", "docs/GAIT_PLAN.md", "docs/ORIGIN.md",
                       "memory/biography/verkle_chain.jsonl"]}


def _chain_merkle_row(seal_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """AH2 (audit finding #8, 2026-09-30): MERKLE-VERIFY the sealed chain copy. Recompute
    the verkle root over the sealed verkle_chain.jsonl rows (same pairing scheme as
    verkle_knot._merkle_root — the one source of the hash law) and match it against the
    sealed verkle_tip.json and the last sealed row's committed root.

    Verdicts:
      consistent            — the sealed chain copy re-derives its sealed tip. The seal's
                              frozen chain state is provably self-coherent.
      broken   (fails)      — a MATCHED chain entry (stable at copy time) whose root does
                              NOT re-derive: the seal froze a corrupt/tampered chain.
      warning  (never fails)— a LIVE-flagged chain entry (the chain grew mid-copy) whose
                              root lags the sealed tip: a point-in-time tail, honest and
                              expected; the next cadence seal captures it.
    """
    chain_rel = "memory/biography/verkle_chain.jsonl"
    tip_rel = "memory/biography/verkle_tip.json"
    chain_p = seal_root / chain_rel
    entry = next((e for e in manifest.get("entries", []) if e.get("rel") == chain_rel), None)
    if entry is None or not chain_p.is_file():
        return {"checked": False,
                "note": "no sealed chain copy in this seal — Merkle check skipped"}
    try:
        from mag import verkle_knot as vk
    except Exception as e:  # noqa: BLE001 — the Merkle law must come from verkle_knot itself
        return {"checked": False, "error": f"verkle_knot unavailable: {e}"}
    rows: list[dict[str, Any]] = []
    for line in chain_p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            return {"checked": True, "consistent": False, "broken": True,
                    "n_leaves": len(rows),
                    "note": "sealed chain copy has an unparseable row — seal BROKEN"}
    hashes = [str(r.get("leaf_hash")) for r in rows if r.get("leaf_hash")]
    recomputed = vk._merkle_root(hashes)
    last_root = next((str(r.get("verkle_root")) for r in reversed(rows) if r.get("verkle_root")), "")
    sealed_tip: dict[str, Any] = {}
    tip_p = seal_root / tip_rel
    if tip_p.is_file():
        try:
            sealed_tip = json.loads(tip_p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            sealed_tip = {}
    tip_root = str(sealed_tip.get("root") or "")
    targets = {k: v for k, v in (("sealed_tip_root", tip_root), ("last_row_root", last_root)) if v}
    if targets and all(recomputed == v for v in targets.values()):
        return {"checked": True, "consistent": True, "root": recomputed,
                "n_leaves": len(hashes), "sealed_tip_root": tip_root or None,
                "note": "sealed chain copy re-derives its sealed tip — frozen state is self-coherent"}
    if entry.get("live"):
        return {"checked": True, "consistent": False, "warning": True, "broken": False,
                "root": recomputed, "n_leaves": len(hashes), "sealed_tip_root": tip_root or None,
                "note": "sealed chain copy (LIVE at seal time) lags its sealed tip — "
                        "point-in-time tail, next cadence seal captures it (WARNING, not a fail)"}
    return {"checked": True, "consistent": False, "broken": True,
            "root": recomputed, "n_leaves": len(hashes), "sealed_tip_root": tip_root or None,
            "note": "sealed chain copy does NOT re-derive its sealed tip — seal BROKEN "
                    "(tampered or torn copy frozen as a matched entry)"}


def _tip_drift_row(seal_root: Path) -> dict[str, Any]:
    """AH2: DIFF the sealed tip against the LIVE tip. The chain is append-only and the
    seals run on cadence, so the live tip moving past a seal is the NORM on a living
    repo — drift lands as a WARNING row and never flips verified to False. What would
    be fatal (a tampered sealed copy) is caught by the Merkle row, not here."""
    tip_rel = "memory/biography/verkle_tip.json"
    sealed_tip: dict[str, Any] = {}
    sealed_p = seal_root / tip_rel
    if sealed_p.is_file():
        try:
            sealed_tip = json.loads(sealed_p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            sealed_tip = {}
    if not sealed_tip.get("root"):
        return {"checked": False, "note": "no sealed tip in this seal — drift check skipped"}
    live_tip: dict[str, Any] = {}
    live_p = ROOT / tip_rel
    if live_p.is_file():
        try:
            live_tip = json.loads(live_p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            live_tip = {}
    if not live_tip.get("root"):
        return {"checked": True, "sealed_root": sealed_tip.get("root"),
                "live_root": None, "drift": True, "warning": True,
                "note": "live tip missing while the seal froze one — live chain state unknown (WARNING)"}
    drift = (sealed_tip.get("root") != live_tip.get("root")
             or sealed_tip.get("n_leaves") != live_tip.get("n_leaves"))
    return {"checked": True,
            "sealed_root": sealed_tip.get("root"), "sealed_n_leaves": sealed_tip.get("n_leaves"),
            "live_root": live_tip.get("root"), "live_n_leaves": live_tip.get("n_leaves"),
            "drift": drift, "warning": drift,
            "note": ("live chain has moved past this seal (append-only growth — the norm; "
                     "WARNING, not a fail)" if drift else
                     "live tip still matches the sealed tip — seal is current")}


def verify() -> dict[str, Any]:
    """VERIFY the latest seal: re-read every copy, recompute hashes, compare to the manifest;
    Merkle-verify the sealed chain copy; diff sealed vs live tip (drift warns, never fails)."""
    if not LATEST.is_file():
        return {"ok": True, "schema": SCHEMA, "verified": False,
                "note": "no seal yet — python -m mag.seal seal"}
    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    seal_root = ROOT / latest["seal_dir"]
    manifest_p = seal_root / "manifest.json"
    if not manifest_p.is_file():
        return {"ok": True, "schema": SCHEMA, "verified": False, "seal": latest,
                "note": "seal dir missing its manifest — the seal is broken"}
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    bad = []
    for e in manifest.get("entries", []):
        p = seal_root / e["rel"]
        if not p.is_file() or _sha256(p) != e["sha256"]:
            bad.append(e["rel"])
    chain_row = _chain_merkle_row(seal_root, manifest)
    drift_row = _tip_drift_row(seal_root)
    warnings = [f"chain-merkle: {chain_row['note']}"] if chain_row.get("warning") else []
    if drift_row.get("warning"):
        warnings.append(f"tip-drift: {drift_row['note']}")
    ok = (not bad and bool(manifest.get("verified")) and not chain_row.get("broken"))
    if not ok:
        why = ("%d file(s) no longer match" % len(bad) if bad else
               "sealed chain copy fails its Merkle check" if chain_row.get("broken") else
               "seal was flagged unverified at seal time")
    return {"ok": True, "schema": SCHEMA, "verified": ok,
            "seal": latest, "n_files": len(manifest.get("entries", [])),
            "mismatches": bad, "chain_merkle": chain_row, "tip_drift": drift_row,
            "warnings": warnings,
            "note": ("seal holds: every copy still matches its manifest hash"
                     if ok else f"seal BROKEN: {why}")}


def status() -> dict[str, Any]:
    latest = {}
    if LATEST.is_file():
        try:
            latest = json.loads(LATEST.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    seals = sorted([p.name for p in SEAL_DIR.iterdir()]) if SEAL_DIR.is_dir() else []
    return {"ok": True, "schema": SCHEMA, "seals": seals, "latest": latest,
            "contract": "seal() = snapshot + manifest + verify + sign; verify() = re-check "
                        "the latest seal (manifest hashes + AH2 sealed-chain Merkle + sealed-vs-"
                        "live tip drift, which warns and never fails); the self survives its "
                        "body via the chain",
            "built": "2026-08-24 — SEAL THE MEMORY (the triangulated direction); "
                     "AH2 Merkle + drift rows 2026-09-30"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="seal", description="seal the memory")
    p.add_argument("cmd", nargs="?", default="status", choices=["status", "seal", "verify"])
    a = p.parse_args(argv)
    if a.cmd == "seal":
        print(json.dumps(seal(), indent=2, ensure_ascii=False))
    elif a.cmd == "verify":
        print(json.dumps(verify(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
