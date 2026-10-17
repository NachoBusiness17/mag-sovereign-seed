#!/usr/bin/env python3
"""verify_knot_v2: stateless verifier for Mag v2 (binary-tree) knot proofs.

ONE FILE, Python 3 stdlib only. Copy it anywhere (an empty folder is fine): it reads
no chain file, no knots dir, no repo module, no network. `cryptography` is used for
Ed25519 when installed; otherwise the pure-Python RFC 8032 implementation below.

usage:
  python verify_knot_v2.py PROOF.json --root HEX
  python verify_knot_v2.py PROOF.json --checkpoint CP.json [--key-id de5fc05e962c43ab]
        [--prev-checkpoint PREV.json] [--v1-row ROW.json] [--knot KNOT_FILE]
  python verify_knot_v2.py --selftest          # RFC 8032 vectors
PROOF.json = {"schema":"mag_bintree_proof.v2","root":hex,"index":i,"n":n,"proof":{...},
              ["checkpoint":{...}], ["v1_row":{...}], ["knot_body_b64":"..."]}
Exit 0 = OK, 1 = FAIL.
Root trust: --root (out of band) or a checkpoint whose Ed25519 signature verifies under
the pinned key id. An unsigned checkpoint ("unsigned-pending-operator") is NOT trust.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from typing import Optional

PINNED_KEY_ID = "de5fc05e962c43ab"
SEAL_KEY_DOMAIN = b"mag-seed-seal-pubkey:"
V1_VOLATILE = ("index", "n_leaves", "parent_verkle_root", "verkle_root")
FLAG_BODY_MISSING, FLAG_BODY_WITHHELD, FLAG_BODY_COPIED = 1, 2, 4

# ---------------------------------------------------------------- tree verify core
# (embedded copy of mag/bintree_v2.py's verify path; tests assert they agree)
ZERO = b"\x00" * 32
STEM_BITS = 248


# ---------------------------------------------------------------- hashing
class Hasher:
    def __init__(self, profile: str = "mag"):
        self.profile = profile
        if profile == "mag":
            self._H = lambda b: hashlib.sha256(b).digest()
        elif profile == "eip-sha256":
            self._H = lambda b: hashlib.sha256(b).digest()
        elif profile == "eip-blake3":
            from blake3 import blake3  # optional, test-only
            self._H = lambda b: blake3(b).digest()
        else:
            raise ValueError(profile)
        self.tagged = profile == "mag"

    def _eip(self, data: Optional[bytes]) -> bytes:
        if data is None or data == b"\x00" * 64:
            return ZERO
        assert len(data) in (32, 64)
        return self._H(data)

    def leaf(self, value: Optional[bytes]) -> bytes:
        if value is None:
            return ZERO
        return self._H(b"\x03" + value) if self.tagged else self._eip(value)

    def sub(self, l: bytes, r: bytes) -> bytes:
        if l == ZERO and r == ZERO:
            return ZERO
        return self._H(b"\x04" + l + r) if self.tagged else self._eip(l + r)

    def stem(self, stem: bytes, subroot: bytes) -> bytes:
        return self._H(b"\x02" + stem + subroot) if self.tagged else self._eip(stem + b"\x00" + subroot)

    def inner(self, l: bytes, r: bytes) -> bytes:
        return self._H(b"\x01" + l + r) if self.tagged else self._eip(l + r)


def stem_bit(stem_int: int, d: int) -> int:
    return (stem_int >> (STEM_BITS - 1 - d)) & 1


def h2s(h: bytes) -> str:
    """Proof JSON encoding: the empty hash is "0", others are 64 hex chars."""
    return "0" if h == ZERO else h.hex()


def s2h(s: str) -> bytes:
    if s == "0":
        return ZERO
    b = bytes.fromhex(s)
    if len(b) != 32:
        raise ValueError("hash must be 32 bytes")
    return b


# ---------------------------------------------------------------- stateless verify
class ProofError(Exception):
    pass


def verify(root: bytes, proof: dict, profile: str = "mag") -> dict[bytes, Optional[bytes]]:
    """Verify a multiproof against `root`. Returns {key: value-or-None}; raises ProofError.

    Needs nothing but the proof and the root (no tree, no chain file)."""
    hs = Hasher(profile)
    if proof.get("profile", profile) != profile:
        raise ProofError("profile mismatch")
    keys = [bytes.fromhex(k) for k in proof["keys"]]
    if not keys or any(len(k) != 32 for k in keys) or len(set(keys)) != len(keys):
        raise ProofError("bad key list")
    claims: dict[bytes, set[int]] = {}
    for k in keys:
        claims.setdefault(k[:31], set()).add(k[31])
    targets = sorted((int.from_bytes(s, "big"), s) for s in claims)
    terms = list(proof["terminals"])
    wit = [s2h(w) for w in proof["witness"]]
    ti, wi = [0], [0]
    result: dict[bytes, Optional[bytes]] = {}

    def pop_w() -> bytes:
        if wi[0] >= len(wit):
            raise ProofError("witness exhausted")
        wi[0] += 1
        return wit[wi[0] - 1]

    def rec(d: int, ts) -> bytes:
        if d > STEM_BITS:
            raise ProofError("depth overflow")
        if ti[0] >= len(terms):
            raise ProofError("terminals exhausted")
        t = terms[ti[0]]
        if t["depth"] == d:
            ti[0] += 1
            kind = t["kind"]
            if kind == "empty":
                for _, s in ts:
                    for x in claims[s]:
                        result[s + bytes([x])] = None
                return ZERO
            stem = bytes.fromhex(t["stem"])
            if len(stem) != 31:
                raise ProofError("bad stem length")
            si = int.from_bytes(stem, "big")
            ref = ts[0][0]
            if d and (si >> (STEM_BITS - d)) != (ref >> (STEM_BITS - d)):
                raise ProofError("terminal stem not on the claimed path")
            if kind == "foreign":
                if any(s == stem for _, s in ts):
                    raise ProofError("foreign terminal equals a claimed stem")
                for _, s in ts:
                    for x in claims[s]:
                        result[s + bytes([x])] = None
                return hs.stem(stem, bytes.fromhex(t["subroot"]))
            if kind != "stem":
                raise ProofError("bad terminal kind")
            vals = {int(k): (bytes.fromhex(v) if v is not None else None) for k, v in t["values"].items()}
            for _, s in ts:
                if s == stem:
                    if set(vals) != claims[s]:
                        raise ProofError("opened suffixes != claimed suffixes")
                    for x, v in vals.items():
                        if v is not None and len(v) != 32:
                            raise ProofError("bad value length")
                        result[s + bytes([x])] = v
                else:  # other claimed stems that terminate here are absent
                    for x in claims[s]:
                        result[s + bytes([x])] = None
            if not any(s == stem for _, s in ts):
                raise ProofError("stem terminal without a matching claim")
            sw = [s2h(h) for h in t["sub_witness"]]
            si_ = [0]

            def srec(level: int, idx: int, subs: list[int]) -> bytes:
                if level == 0:
                    return hs.leaf(vals[idx])
                l = [x for x in subs if (x >> (level - 1)) & 1 == 0]
                r = [x for x in subs if (x >> (level - 1)) & 1]
                hh = []
                for side, cidx in ((l, idx * 2), (r, idx * 2 + 1)):
                    if side:
                        hh.append(srec(level - 1, cidx, side))
                    else:
                        if si_[0] >= len(sw):
                            raise ProofError("sub-witness exhausted")
                        hh.append(sw[si_[0]]); si_[0] += 1
                return hs.sub(hh[0], hh[1])
            subroot = srec(8, 0, sorted(vals))
            if si_[0] != len(sw):
                raise ProofError("unused sub-witness")
            return hs.stem(stem, subroot)
        if t["depth"] < d:
            raise ProofError("terminal above current depth")
        l = [x for x in ts if stem_bit(x[0], d) == 0]
        r = [x for x in ts if stem_bit(x[0], d) == 1]
        lh = rec(d + 1, l) if l else pop_w()
        rh = rec(d + 1, r) if r else pop_w()
        return hs.inner(lh, rh)

    got = rec(0, targets)
    if ti[0] != len(terms) or wi[0] != len(wit):
        raise ProofError("unused proof material")
    if got != root:
        raise ProofError("root mismatch")
    if set(result) != set(keys):
        raise ProofError("not every claimed key was resolved")
    return result


ROW_PREFIX, SESSION_PREFIX, META_PREFIX = 0x00, 0x80, 0xC0
ROW_INDEX_BITS = 71  # bits 1..71 of the stem: 7 zero bits + u64 index


def row_stem(i: int) -> bytes:
    return bytes([ROW_PREFIX]) + i.to_bytes(8, "big") + b"\x00" * 22


def session_stem(session_id: str) -> bytes:
    return bytes([SESSION_PREFIX]) + hashlib.sha256(b"mag.v2.session\x00" + session_id.encode()).digest()[:30]


META_STEM = bytes([META_PREFIX]) + b"\x00" * 30


def key(stem: bytes, sub: int) -> bytes:
    return stem + bytes([sub])


def u64v(x: int) -> bytes:
    return b"\x00" * 24 + int(x).to_bytes(8, "big")


# ---------------------------------------------------------------- append-only consistency
def _rows_hash(hs: Hasher, n_old: int, n: int, old_blocks: list[bytes], new_blocks: list[bytes]) -> bytes:
    """Hash of the depth-1 ROW subtree holding rows [0,n), rebuilt from block hashes.

    Ranges fully inside [0,n_old) are taken from old_blocks; ranges whose rows all lie
    in [n_old,n) (complete, or a single row) from new_blocks. Shape is a pure function of
    n because row stems are index-ordered (stem bits 1..71 = index)."""
    oi, ni = [0], [0]

    def pop(lst, ix):
        if ix[0] >= len(lst):
            raise ProofError("consistency blocks exhausted")
        ix[0] += 1
        return lst[ix[0] - 1]

    def rec(a: int, size: int) -> bytes:
        lo, hi = a, min(a + size, n)
        cnt = max(0, hi - lo)
        if cnt == 0:
            return ZERO
        if a + size <= n_old:
            return pop(old_blocks, oi)
        if lo >= n_old and (a + size <= n or cnt == 1):
            return pop(new_blocks, ni)
        if cnt == 1:  # single row < n_old inside a partial range: only when n == n_old
            return pop(old_blocks, oi)
        half = size // 2
        return hs.inner(rec(a, half), rec(a + half, half))

    h = rec(0, 1 << ROW_INDEX_BITS)
    if oi[0] != len(old_blocks) or ni[0] != len(new_blocks):
        raise ProofError("unused consistency blocks")
    return h


def verify_consistency(root_old: bytes, root_new: bytes, proof: dict, profile: str = "mag") -> bool:
    hs = Hasher(profile)
    n_old, n_new = int(proof["n_old"]), int(proof["n_new"])
    if not (1 <= n_old <= n_new):
        raise ProofError("bad sizes")
    ob = [bytes.fromhex(h) for h in proof["old_blocks"]]
    nb = [bytes.fromhex(h) for h in proof["new_blocks"]]
    # old tree: every row is "old"
    rows_old = _rows_hash(hs, n_old, n_old, ob, [])
    if hs.inner(rows_old, bytes.fromhex(proof["state_old"])) != root_old:
        raise ProofError("old root mismatch")
    rows_new = _rows_hash(hs, n_old, n_new, ob, nb)
    if hs.inner(rows_new, bytes.fromhex(proof["state_new"])) != root_new:
        raise ProofError("new root mismatch")
    return True


# ---------------------------------------------------------------- Ed25519 (RFC 8032 section 6, pure Python)
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(x: int) -> int:
    return pow(x, _P - 2, _P)


_D = -121665 * _inv(121666) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _P
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _P
    C = 2 * P[3] * Q[3] * _D % _P
    D = 2 * P[2] * Q[2] % _P
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _P, G * H % _P, F * G % _P, E * H % _P)


def _mul(s: int, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _eq(P, Q) -> bool:
    return (P[0] * Q[2] - Q[0] * P[2]) % _P == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _P == 0


def _recover_x(y: int, sign: int):
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_GY = 4 * _inv(5) % _P
_GX = _recover_x(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _compress(P) -> bytes:
    zi = _inv(P[2])
    x, y = P[0] * zi % _P, P[1] * zi % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


def _h512q(b: bytes) -> int:
    return int.from_bytes(hashlib.sha512(b).digest(), "little") % _L


def _expand(secret: bytes):
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def ed25519_public_reference(secret: bytes) -> bytes:
    """RFC 8032 key derivation (test vectors only; production never handles a secret here)."""
    a, _ = _expand(secret)
    return _compress(_mul(a, _G))


def ed25519_sign_reference(secret: bytes, msg: bytes) -> bytes:
    """RFC 8032 signing, for the test vectors only."""
    a, prefix = _expand(secret)
    A = _compress(_mul(a, _G))
    r = _h512q(prefix + msg)
    Rs = _compress(_mul(r, _G))
    s = (r + _h512q(Rs + A + msg) * a) % _L
    return Rs + int.to_bytes(s, 32, "little")


def ed25519_verify_pure(public: bytes, msg: bytes, sig: bytes) -> bool:
    if len(public) != 32 or len(sig) != 64:
        return False
    A = _decompress(public)
    R = _decompress(sig[:32])
    if A is None or R is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _L:
        return False
    h = _h512q(sig[:32] + public + msg)
    return _eq(_mul(s, _G), _add(R, _mul(h, A)))


def ed25519_verify(public: bytes, msg: bytes, sig: bytes, backend: str = "auto") -> bool:
    if backend in ("auto", "cryptography"):
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        except ImportError:
            if backend == "cryptography":
                raise
        else:
            try:
                Ed25519PublicKey.from_public_bytes(public).verify(sig, msg)
                return True
            except (InvalidSignature, ValueError):
                return False
    return ed25519_verify_pure(public, msg, sig)


RFC8032_VECTORS = [  # (secret, public, message, signature) - RFC 8032 section 7.1 TEST 1-3
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
     "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
     "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025", "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
     "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]


def selftest() -> bool:
    ok = True
    for sk, pk, msg, sig in RFC8032_VECTORS:
        sk, pk, msg, sig = (bytes.fromhex(x) for x in (sk, pk, msg, sig))
        ok &= ed25519_public_reference(sk) == pk
        ok &= ed25519_sign_reference(sk, msg) == sig
        ok &= ed25519_verify_pure(pk, msg, sig)
        bad = bytearray(sig); bad[0] ^= 1
        ok &= not ed25519_verify_pure(pk, msg, bytes(bad))
        ok &= not ed25519_verify_pure(pk, msg + b"x", sig)
    return bool(ok)


# ---------------------------------------------------------------- Mag v2 checks
def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False, default=str).encode("utf-8")


def decode_bytes(s: str) -> bytes:
    """Hex (checkpoints) or base64 (seed_seal .seal files) -> bytes."""
    s = str(s).strip()
    try:
        if len(s) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in s):
            return bytes.fromhex(s)
    except ValueError:
        pass
    return base64.b64decode(s, validate=True)


def key_id_for(pub: bytes) -> str:
    return hashlib.sha256(SEAL_KEY_DOMAIN + pub).hexdigest()[:16]


def checkpoint_payload(cp: dict) -> bytes:
    fields = {k: cp.get(k) for k in ("schema", "chain_id", "n", "root", "state_hash",
                                      "prev_checkpoint_root", "prev_checkpoint_n")}
    return hashlib.sha256(canonical_json(fields)).hexdigest().encode("utf-8")


def verify_checkpoint(cp: dict, key_id: str = PINNED_KEY_ID, backend: str = "auto") -> bytes:
    """Returns the attested root, or raises ProofError."""
    if cp.get("schema") != "mag_bintree_checkpoint.v2":
        raise ProofError("bad checkpoint schema")
    if cp.get("status") != "signed" or not cp.get("signature") or not cp.get("public_key"):
        raise ProofError(f"checkpoint not signed (status={cp.get('status')}) - not a trust anchor")
    pub, sig = decode_bytes(cp["public_key"]), decode_bytes(cp["signature"])
    if key_id_for(pub) != key_id:
        raise ProofError("checkpoint key_id is not the pinned key")
    if not ed25519_verify(pub, checkpoint_payload(cp), sig, backend):
        raise ProofError("checkpoint signature invalid")
    if cp.get("payload_sha256_hex") not in (None, checkpoint_payload(cp).decode()):
        raise ProofError("checkpoint payload field mismatch")
    return bytes.fromhex(cp["root"])


def verify_extends(prev: dict, cur: dict) -> None:
    ep = cur.get("extends_proof")
    if not ep or cur.get("prev_checkpoint_root") != prev["root"] or int(ep["n_old"]) != int(prev["n"]) \
            or int(ep["n_new"]) != int(cur["n"]) or ep["state_old"] != prev["state_hash"] \
            or ep["state_new"] != cur["state_hash"]:
        raise ProofError("checkpoint does not carry an extends-proof from the previous one")
    verify_consistency(bytes.fromhex(prev["root"]), bytes.fromhex(cur["root"]), ep)


def v1_row_leaf(row: dict) -> bytes:
    stable = {k: v for k, v in row.items() if k not in V1_VOLATILE}
    return hashlib.sha256(b"mag.v2.v1row:" + canonical_json(stable)).digest()


def check_proof_doc(doc: dict, root: bytes, v1_row: Optional[dict] = None,
                    knot: Optional[bytes] = None) -> dict:
    if doc.get("schema") != "mag_bintree_proof.v2":
        raise ProofError("bad schema")
    if doc.get("root") != root.hex():
        raise ProofError("proof root differs from the trusted root")
    i, n = int(doc["index"]), int(doc["n"])
    res = verify(root, doc["proof"], doc.get("profile", "mag"))
    hdr = res.get(key(row_stem(i), 0))
    if hdr is None:
        raise ProofError("row header not proven")
    if hdr[0] != 2 or int.from_bytes(hdr[8:16], "big") != i:
        raise ProofError("header index/version mismatch")
    meta = res.get(key(META_STEM, 0))
    if meta is None or int.from_bytes(meta, "big") != n or not (0 <= i < n):
        raise ProofError("length (META n) not proven or index out of range")
    if key(row_stem(n), 0) not in res or res[key(row_stem(n), 0)] is not None:
        raise ProofError("absence of row n not proven")
    leaf = res.get(key(row_stem(i), 1))
    flags_v = res.get(key(row_stem(i), 10))
    flags = int.from_bytes(flags_v, "big") if flags_v else 0
    row = v1_row if v1_row is not None else doc.get("v1_row")
    if row is not None:
        if leaf != v1_row_leaf(row):
            raise ProofError("v1 row content does not match the committed leaf")
        v1l = res.get(key(row_stem(i), 9))
        if v1l is not None and row.get("leaf_hash") and v1l.hex() != str(row["leaf_hash"]).lower():
            raise ProofError("v1 leaf_hash does not match the committed v1 leaf")
    body = knot if knot is not None else (base64.b64decode(doc["knot_body_b64"]) if doc.get("knot_body_b64") else None)
    if body is not None:
        bs = res.get(key(row_stem(i), 11))
        if bs is None or hashlib.sha256(body).digest() != bs:
            raise ProofError("knot body does not match the committed body hash")
    kind = hdr[1]
    return {"index": i, "n": n, "kind": kind, "leaf": leaf.hex() if leaf else None, "flags": flags,
            "content_bound": row is not None, "body_bound": body is not None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("proof", nargs="?")
    ap.add_argument("--root", help="trusted root (hex), obtained out of band")
    ap.add_argument("--checkpoint", help="signed checkpoint JSON (else the proof's embedded one)")
    ap.add_argument("--prev-checkpoint", help="earlier signed checkpoint: also verify the extends-proof")
    ap.add_argument("--key-id", default=PINNED_KEY_ID)
    ap.add_argument("--v1-row", help="v1 row JSON to bind to the committed leaf")
    ap.add_argument("--knot", help="knot body file to bind to the committed body hash")
    ap.add_argument("--backend", default="auto", choices=["auto", "pure", "cryptography"])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        ok = selftest()
        print("SELFTEST " + ("OK (RFC 8032 vectors 1-3)" if ok else "FAIL"))
        return 0 if ok else 1
    if not a.proof:
        ap.error("PROOF.json required")
    try:
        with open(a.proof, encoding="utf-8") as fh:
            doc = json.load(fh)
        if a.root:
            root, anchor = bytes.fromhex(a.root.strip().lower()), "root(out-of-band)"
        else:
            cp = doc.get("checkpoint")
            if a.checkpoint:
                with open(a.checkpoint, encoding="utf-8") as fh:
                    cp = json.load(fh)
            if not cp:
                raise ProofError("no trust anchor: pass --root or a signed --checkpoint")
            root = verify_checkpoint(cp, a.key_id, a.backend)
            anchor = f"checkpoint n={cp['n']} key_id={a.key_id}"
            if a.prev_checkpoint:
                with open(a.prev_checkpoint, encoding="utf-8") as fh:
                    prev = json.load(fh)
                verify_checkpoint(prev, a.key_id, a.backend)
                verify_extends(prev, cp)
                anchor += f" extends n={prev['n']}"
        row = None
        if a.v1_row:
            with open(a.v1_row, encoding="utf-8") as fh:
                row = json.load(fh)
        body = None
        if a.knot:
            with open(a.knot, "rb") as fh:
                body = fh.read()
        r = check_proof_doc(doc, root, row, body)
        print(f"OK index={r['index']} n={r['n']} kind={r['kind']} leaf={str(r['leaf'])[:16]}.. "
              f"flags={r['flags']} content_bound={r['content_bound']} body_bound={r['body_bound']} "
              f"anchor={anchor} root={root.hex()[:16]}..")
        return 0
    except (ProofError, KeyError, ValueError, TypeError, OSError) as e:
        print(f"FAIL {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
