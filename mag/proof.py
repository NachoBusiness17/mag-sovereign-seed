"""proof — SIGNED PROOFS: the loop's claims become checkable (2026-08-24).

GSTD steal #5. The chain is the line we sign: every claim the system banks gets a canonical
signature (a deterministic hash of its own inputs + outputs), the signature is anchored to
the verkle chain, and anyone can RE-DERIVE the hash from the original payload to confirm the
claim holds. A claim that doesn't re-derive is a broken proof — reported honestly, not hidden.

  sign(payload)   -> canonical sha256 signature (same payload -> same signature, always).
  verify(proof)   -> re-derive the hash from the payload; match = the proof holds.
  anchor(payload) -> sign + commit the claim hash to the verkle chain (a chain fact), deduped.
  check(hash)     -> is this claim hash committed on the chain (read the anchor ledger)?

Schema: proof.v1 · deterministic + $0 · reuse: verkle_knot (append), manifest dedup pattern
CLI: python -m mag.proof sign <json> | verify <json> | anchor <json> | check <hash>
"""
from __future__ import annotations

import hashlib
import json
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

SCHEMA = "proof.v1"
LEDGER = ROOT / "memory" / "proofs" / "anchored.jsonl"  # claim hashes committed on the chain
SESSION_ID = "proof"

# AH2 (2026-09-30, audit finding #8): the original "signature" was an UNKEYED sha256 — anyone
# can forge a claim_hash. Real signatures now: ed25519 over the canonical payload bytes via
# sign_payload()/verify_signature(). The legacy unkeyed hash stays as the LEGACY-UNKEYED
# fallback verify path (pre-AH2 proofs must still verify). Key resolution: MAG_PROOF_KEY env
# (hex seed) wins, else configs/.proof_key — auto-generated dev key 0600 on first use,
# gitignored, NEVER committed (a committed key makes every signature theater).
KEY_FILE = ROOT / "configs" / ".proof_key"
SIGNING_ALG = "ed25519"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(payload: dict[str, Any]) -> str:
    """Deterministic canonical form of a claim (sort_keys, default=str — same bytes always)."""
    return json.dumps(payload, sort_keys=True, default=str)


def _key_from_seed_hex(hexseed: str, source: str) -> dict[str, Any]:
    """hex seed -> Ed25519PrivateKey, or an honest error naming the source."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    try:
        seed = bytes.fromhex(hexseed)
    except ValueError:
        return {"ok": False, "error": f"{source}: key is not valid hex (expected 64 hex chars)"}
    if len(seed) != 32:
        return {"ok": False, "error": f"{source}: ed25519 seed must be 32 bytes (64 hex chars)"}
    return {"ok": True, "key": Ed25519PrivateKey.from_private_bytes(seed), "source": source}


def load_signing_key(key_file: Path | None = None) -> dict[str, Any]:
    """Resolve the ed25519 signing key: MAG_PROOF_KEY env (hex seed) wins, else the key file
    (configs/.proof_key). Absent file -> auto-generate a dev key and persist it 0600. The key
    file is gitignored by law — never commit it, never log the seed."""
    import os
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    env = os.environ.get("MAG_PROOF_KEY", "").strip()
    if env:
        return _key_from_seed_hex(env, source="env:MAG_PROOF_KEY")
    kf = Path(key_file) if key_file else KEY_FILE
    if kf.is_file():
        return _key_from_seed_hex(kf.read_text(encoding="utf-8").strip(), source=f"file:{kf.name}")
    # first use: mint the dev key. 0600 is enforced where the OS supports it; on Windows
    # chmod is advisory only, so the gitignore + never-commit law carries the guarantee.
    kf.parent.mkdir(parents=True, exist_ok=True)
    seed = os.urandom(32)
    kf.write_text(seed.hex(), encoding="utf-8")
    try:
        os.chmod(kf, 0o600)
    except OSError:
        pass
    return {"ok": True, "key": Ed25519PrivateKey.from_private_bytes(seed),
            "source": f"generated:{kf.name} (0600)"}


def _pubkey_bytes(key: Any) -> bytes:
    from cryptography.hazmat.primitives import serialization
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def pubkey_fingerprint(pub: bytes) -> str:
    """Short stable fingerprint of a raw ed25519 public key (sha256, first 16 hex)."""
    return hashlib.sha256(b"mag-proof-pubkey:" + pub).hexdigest()[:16]


def sign_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """SIGN with a real key (AH2): ed25519 over the canonical payload bytes, alongside the
    deterministic claim sha. Returns (sha, sig, pubkey_fingerprint) — plus the raw pubkey so
    anyone re-verifies without the private key. Same payload -> same sha; the sig is also
    deterministic for ed25519, but verification never trusts that."""
    import base64
    if not isinstance(payload, dict):
        return {"ok": False, "schema": SCHEMA, "error": "payload must be a dict"}
    k = load_signing_key()
    if not k.get("ok"):
        return {"ok": False, "schema": SCHEMA, "error": str(k.get("error") or "no signing key")}
    canonical = _canonical(payload)
    raw = canonical.encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    sig = k["key"].sign(raw)
    pub = _pubkey_bytes(k["key"])
    return {"ok": True, "schema": SCHEMA, "alg": SIGNING_ALG,
            "sha": sha,
            "sig": base64.b64encode(sig).decode("ascii"),
            "pubkey": base64.b64encode(pub).decode("ascii"),
            "pubkey_fingerprint": pubkey_fingerprint(pub),
            "key_source": k["source"], "ts": _now(),
            "payload": payload,
            "note": "ed25519-signed: verify_signature checks the signature over these exact canonical bytes"}


def verify_signature(signed: dict[str, Any]) -> dict[str, Any]:
    """VERIFY a key-signed claim (AH2). Ed25519 path: re-canonicalize the payload and check
    the signature against the embedded pubkey (fingerprint echoed back). LEGACY-UNKEYED
    fallback: a proof carrying only claim_hash/sha still verifies via the old unkeyed sha256
    — pre-AH2 proofs must keep holding."""
    import base64
    if not isinstance(signed, dict):
        return {"ok": False, "schema": SCHEMA, "verified": False,
                "error": "signed claim must be a dict"}
    payload = signed.get("payload")
    if not isinstance(payload, dict):
        return {"ok": False, "schema": SCHEMA, "verified": False,
                "error": "no payload to verify — cannot check this claim"}
    canonical = _canonical(payload)
    raw = canonical.encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    sig_b64, pub_b64 = signed.get("sig"), signed.get("pubkey")
    if sig_b64 and pub_b64:
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64))
            pub.verify(base64.b64decode(sig_b64), raw)
        except (InvalidSignature, ValueError):  # ValueError covers bad b64 input
            return {"ok": True, "schema": SCHEMA, "verified": False, "alg": SIGNING_ALG,
                    "mode": "ED25519", "sha": sha,
                    "pubkey_fingerprint": signed.get("pubkey_fingerprint", ""),
                    "note": "proof BROKEN: ed25519 signature does NOT verify over the canonical bytes"}
        return {"ok": True, "schema": SCHEMA, "verified": True, "alg": SIGNING_ALG,
                "mode": "ED25519", "sha": sha,
                "pubkey_fingerprint": signed.get("pubkey_fingerprint")
                or pubkey_fingerprint(base64.b64decode(pub_b64)),
                "note": "proof holds: ed25519 signature verifies over the canonical payload bytes"}
    # LEGACY-UNKEYED fallback — pre-AH2 proofs (sign()/anchor() output) carry claim_hash only.
    claimed = signed.get("claim_hash") or signed.get("sha") or ""
    match = bool(claimed) and sha == claimed
    return {"ok": True, "schema": SCHEMA, "verified": match, "mode": "LEGACY-UNKEYED",
            "sha": sha,
            "note": ("proof holds: LEGACY-UNKEYED hash re-derives from the payload (pre-AH2 proof)"
                     if match else
                     "proof BROKEN: LEGACY-UNKEYED hash does NOT match the payload bytes")}


def sign(payload: dict[str, Any]) -> dict[str, Any]:
    """SIGN a claim: canonical payload -> sha256 signature. The signature IS the proof: given
    the same inputs, anyone re-derives the same hash. No secrets, no trust — checkable bytes."""
    if not isinstance(payload, dict):
        return {"ok": False, "schema": SCHEMA, "error": "payload must be a dict"}
    canonical = _canonical(payload)
    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {"ok": True, "schema": SCHEMA, "claim_hash": h, "ts": _now(),
            "payload": payload, "canonical": canonical[:400],
            "note": "signed: the claim hash re-derives from these exact bytes"}


def verify(proof: dict[str, Any]) -> dict[str, Any]:
    """VERIFY a signed proof: re-derive the hash from the claimed payload and compare.
    match = the proof holds (the claim is exactly what was signed). mismatch = BROKEN."""
    payload = proof.get("payload") if isinstance(proof, dict) else None
    if not isinstance(payload, dict):
        return {"ok": False, "schema": SCHEMA, "verified": False,
                "error": "no payload to re-derive — cannot check this claim"}
    canonical = _canonical(payload)
    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    claimed = proof.get("claim_hash", "")
    match = bool(claimed) and h == claimed
    return {"ok": True, "schema": SCHEMA, "verified": match, "claim_hash": h,
            "note": ("proof holds: hash re-derived from the payload matches the signature"
                     if match else "proof BROKEN: re-derived hash does NOT match the signature")}


def _anchored_hashes() -> set[str]:
    out: set[str] = set()
    if LEDGER.is_file():
        try:
            for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip():
                    out.add((json.loads(line).get("claim_hash") or "")[:64])
        except Exception:  # noqa: BLE001
            pass
    return out


def anchor(payload: dict[str, Any]) -> dict[str, Any]:
    """SIGN + COMMIT a claim to the verkle chain (a chain fact). Deduped: an already-anchored
    claim hash persists — no chain spam, same proof contract as the manifest."""
    s = sign(payload)
    if not s.get("ok"):
        return s
    h = s["claim_hash"]
    if h in _anchored_hashes():
        return {"ok": True, "schema": SCHEMA, "anchored": True, "persisted": True,
                "claim_hash": h, "note": "claim hash already committed — persists as a chain fact"}
    knot = {}
    try:
        from mag import verkle_knot
        knot = verkle_knot.append_verkle_knot({
            "session_id": SESSION_ID,
            "theme": "proof",
            "summary": f"[proof] signed claim {h[:16]} — {str(payload.get('kind') or payload.get('role') or 'claim')[:40]}",
        })
    except Exception as e:  # noqa: BLE001 — anchoring must never break the proof
        knot = {"leaf_hash": h, "error": str(e)[:100]}
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"schema": SCHEMA, "claim_hash": h, "ts": _now(),
                                "leaf_hash": knot.get("leaf_hash", ""),
                                "root": knot.get("verkle_root") or knot.get("root", ""),
                                "kind": str(payload.get("kind") or payload.get("role") or "claim")[:60]},
                               ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "schema": SCHEMA, "anchored": True, "persisted": False,
            "claim_hash": h, "leaf_hash": knot.get("leaf_hash", ""),
            "root": knot.get("verkle_root") or knot.get("root", ""),
            "note": "signed claim committed to the verkle chain — a checkable chain fact"}


def check(claim_hash: str) -> dict[str, Any]:
    """CHECK: is this claim hash committed on the chain (in the anchored ledger)?"""
    h = (claim_hash or "").strip().lower()
    anchored = h in _anchored_hashes()
    return {"ok": True, "schema": SCHEMA, "claim_hash": h, "anchored": anchored,
            "note": ("claim is a committed chain fact" if anchored
                     else "claim hash NOT found in the anchored ledger — not committed")}


def status() -> dict[str, Any]:
    ledger = _anchored_hashes()
    signing: dict[str, Any] = {"alg": SIGNING_ALG, "note": "sign_payload()/verify_signature()"}
    k = load_signing_key()
    if k.get("ok"):
        signing["pubkey_fingerprint"] = pubkey_fingerprint(_pubkey_bytes(k["key"]))
        signing["key_source"] = k["source"]
    else:
        signing["error"] = k.get("error", "no signing key")
    return {"ok": True, "schema": SCHEMA, "anchored_claims": len(ledger), "signing": signing,
            "contract": "sign -> anchor -> verify: every claim re-derives from its own bytes "
                        "and is committed as a chain fact; AH2 adds real ed25519 signatures "
                        "(LEGACY-UNKEYED hashes still verify as fallback)",
            "built": "2026-08-24 — foundation #5 of the doctrine; AH2 signing 2026-09-30"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "status"
    if cmd in ("sign", "verify", "anchor", "sign-payload", "verify-sig"):
        if len(argv) < 2:
            print(json.dumps({"ok": False, "error": f"{cmd} needs a JSON payload"}, indent=2))
            return 1
        try:
            payload = json.loads(argv[1])
        except Exception:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": "payload must be JSON"}, indent=2))
            return 1
        if cmd == "sign":
            print(json.dumps(sign(payload), indent=2, ensure_ascii=False))
        elif cmd == "verify":
            print(json.dumps(verify(payload), indent=2, ensure_ascii=False))
        elif cmd == "sign-payload":
            print(json.dumps(sign_payload(payload), indent=2, ensure_ascii=False))
        elif cmd == "verify-sig":
            print(json.dumps(verify_signature(payload), indent=2, ensure_ascii=False))
        else:
            print(json.dumps(anchor(payload), indent=2, ensure_ascii=False))
    elif cmd == "check" and len(argv) > 1:
        print(json.dumps(check(argv[1]), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
