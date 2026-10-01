"""gwap_payload -- GWAP agreement-as-anti-cheat payload, v0 + v1 (game-platform rung B3).

The noir GWAP design (watch/inbox/noir_gwap_steal_20260926/SUBSTRATE_DECISION_20260926.md)
makes AGREEMENT between independent authors both the anti-cheat and the product: a
Robber seals an intent record, a Cop files an independent incident report, a Witness
answers templated clues, and an optional Blocker (KissKissBan) tabooes the scene's most
common words so pre-agreed lazy answers stop paying. One matched incident becomes one
payload row in a hash-chained session ledger. That row IS the artifact.

WHAT THIS MODULE OWNS (v0 scope):
  schema mag_gwap_payload.v1 -- the paper schema {scene_id, intent_struct,
      report_struct, agreement_score, blocker_taboo_list, witness_clue_chain,
      verdict} EXTENDED with participants, consent, meter_credit, replay_tape_ref,
      a signature placeholder, created_utc, plus two v0 additions of our own:
      taboo_violations and collusion_fingerprint.
  agreement engine -- weighted Jaccard over canonicalized claim triples
      (subject, verb, object, qualifier). Role weights: robber/cop 1.0,
      witness 0.5, blocker 0.0 (blockers author no claims). The min/max weighted
      Jaccard reduces to plain Jaccard at equal weights.
  blocker -- the top-N most common words of a scene's prior claims (default N=5,
      ties broken alphabetically, no RNG) become taboo; any taboo token inside an
      intent or report verdicts the incident BLOCKED.
  verdict ladder -- BLOCKED (blocker precedence) over score >= 0.6 VERIFIED_AGREE,
      >= 0.3 CHALLENGE, else DISPUTE. v1: suspected_collusion demotes
      VERIFIED_AGREE to CHALLENGE (judgment owed before credit).
  collusion fingerprint -- identical claim ORDER between two DIFFERENT authors
      (minimum 2 claims: a single claim carries no order information) flags
      suspected_collusion, and v1 auto-downgrades the verdict (see ladder).
  session ledger -- append-only JSONL, one file per session under
      memory/runs/gwap/<session_id>.jsonl, rows {seq, ts_utc, payload, prev_sha256,
      row_sha256}, genesis prev = 64 zeros. The wow_player hash-chain house pattern
      (mag/wow_player.py): row hash covers the row minus its own hash field.

WHAT V1 ADDS (2026-09-29, pays v0-receipt debts 1, 3 and 6):
  ed25519 signatures (debt 3) -- real signatures via the `cryptography`
      package: author_keypair(seed) derives a deterministic keypair (the
      32-byte private seed is sha256 of the schema + secret seed, no RNG),
      sign_payload() seals a built payload, verify_signature() is the offline
      public check anyone can run against the pubkey riding in the row.
      HAS_CRYPTO flags the package's absence; signers fail closed, verifiers
      return False. The MUD connector (debt 6) lives in mag/gwap_mud.py.
  collusion auto-downgrade (debt 1) -- suspected_collusion demotes
      VERIFIED_AGREE to CHALLENGE. Amends v0 design decision 2 (which left
      the ladder untouched): rationale in the v1 receipt section.

LAWS: v0 is stdlib only; v1 adds exactly one dependency, the `cryptography`
package, used solely for ed25519. Still no RNG, no clock reads inside the
builders (every timestamp is injected, so identical inputs produce
byte-identical payloads). canonical() is the
only serialization this module speaks. verify reads the FILE, never cached rows.
Dicts over dataclasses: payloads ARE json rows; dicts keep the canonical round-trip
one layer thin.

RUN (demo: one clean-agreement session, one collusion session):
  python -m mag.gwap_payload
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Sequence

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# v1: the ONE dependency beyond stdlib. cryptography 49.0.0 verified present in
# the repo venv 2026-09-29; HAS_CRYPTO gates every signer/verifier so absence
# fails closed (signers raise NO_CRYPTO, verify_signature returns False).
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    HAS_CRYPTO = True
except Exception:  # pragma: no cover - absent package, exercised via skips
    HAS_CRYPTO = False

SCHEMA = "mag_gwap_payload.v1"
STORE = ROOT / "memory" / "runs" / "gwap"

_ZERO_HASH = "0" * 64

ROLES = ("robber", "cop", "witness", "blocker")
ROLE_WEIGHTS: dict[str, float] = {
    "robber": 1.0,
    "cop": 1.0,
    "witness": 0.5,
    "blocker": 0.0,
}

VERIFIED_AGREE = "VERIFIED_AGREE"
CHALLENGE = "CHALLENGE"
DISPUTE = "DISPUTE"
BLOCKED = "BLOCKED"
VERDICTS = (VERIFIED_AGREE, CHALLENGE, DISPUTE, BLOCKED)

VERIFIED_AGREE_MIN = 0.6
CHALLENGE_MIN = 0.3
SCORE_DECIMALS = 4
TABOO_SIZE = 5
MIN_COLLUSION_SEQ = 2

_CLAIM_KEYS = {"subject", "verb", "object", "qualifier"}
_CLAIM_REQUIRED = ("subject", "verb", "object")
_STRUCT_KEYS = {"author", "claims"}
_CLUE_KEYS = {"witness", "prompt", "answer", "claims"}
_PARTICIPANT_KEYS = {"anon_id", "role"}
_TAPE_KEYS = {"sha256", "engine_version"}
_ROW_KEYS = {"seq", "ts_utc", "payload", "prev_sha256", "row_sha256"}
_METER_KEYS = {"artifact_rarity", "byte_backed", "receipt_sha256"}
_PAYLOAD_KEYS = {
    "schema", "scene_id", "participants", "consent", "intent_struct",
    "report_struct", "witness_clue_chain", "agreement_score", "blocker_taboo_list",
    "taboo_violations", "verdict", "collusion_fingerprint", "meter_credit",
    "replay_tape_ref", "signature", "created_utc",
}

_WORD_RE = re.compile(r"[a-z0-9]+")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX32_RE = re.compile(r"^[0-9a-f]{64}$")   # 32 bytes: private seed, public key
_HEX64_RE = re.compile(r"^[0-9a-f]{128}$")  # 64 bytes: ed25519 signature
_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def canonical(obj: Any) -> str:
    """The only serialization this module speaks -- byte-stable by construction."""
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    """The ONE clock touch, used only by append()/demo defaults. Builders never call it."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def anon_id(seed: str) -> str:
    """Derived, deterministic, secret-free: the salt is the schema string itself."""
    return "gw-" + _sha256_hex(f"{SCHEMA}:{seed}")[:12]


class GwapError(Exception):
    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        super().__init__(message or reason)


# -- claims ---------------------------------------------------------------------


def _norm_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise GwapError("CLAIM_SHAPE", f"{field} must be a string")
    folded = " ".join(value.lower().split())
    if not folded:
        raise GwapError("CLAIM_SHAPE", f"{field} must be non-empty")
    return folded


def normalize_claim(claim: Any) -> dict[str, str]:
    """A claim is exactly {subject, verb, object, qualifier}; qualifier defaults to
    "" so the same semantics always produce the same payload bytes."""
    if not isinstance(claim, dict) or not set(claim) <= _CLAIM_KEYS:
        raise GwapError("CLAIM_SHAPE", "claim keys must be a subset of triple fields")
    for field in _CLAIM_REQUIRED:
        if field not in claim:
            raise GwapError("CLAIM_SHAPE", f"claim is missing {field}")
    return {
        "subject": _norm_text(claim["subject"], "subject"),
        "verb": _norm_text(claim["verb"], "verb"),
        "object": _norm_text(claim["object"], "object"),
        "qualifier": _norm_text(claim.get("qualifier", ""), "qualifier")
        if str(claim.get("qualifier", "")).strip()
        else "",
    }


def claim_triple(claim: dict[str, Any]) -> tuple[str, str, str, str]:
    n = normalize_claim(claim)
    return (n["subject"], n["verb"], n["object"], n["qualifier"])


def claim_words(claim: dict[str, Any]) -> list[str]:
    n = normalize_claim(claim)
    text = " ".join(n[k] for k in ("subject", "verb", "object", "qualifier"))
    return _WORD_RE.findall(text)


def _normalize_struct(struct: Any, field: str) -> dict[str, Any]:
    if not isinstance(struct, dict) or set(struct) != _STRUCT_KEYS:
        raise GwapError(
            "STRUCT_SHAPE", f"{field} must be exactly {{author, claims}}"
        )
    author = struct["author"]
    if not isinstance(author, str) or not author.strip():
        raise GwapError("STRUCT_SHAPE", f"{field}.author must be a non-empty string")
    if not isinstance(struct["claims"], list):
        raise GwapError("STRUCT_SHAPE", f"{field}.claims must be a list")
    return {
        "author": author.strip(),
        "claims": [normalize_claim(c) for c in struct["claims"]],
    }


def _claims_of(struct: Any) -> list[dict[str, str]]:
    """Scoring helper: accept a struct dict or a bare claim list."""
    if isinstance(struct, list):
        return [normalize_claim(c) for c in struct]
    return _normalize_struct(struct, "claims_struct")["claims"]


def normalize_witness_chain(chain: Any) -> list[dict[str, Any]]:
    if not isinstance(chain, (list, tuple)):
        raise GwapError("CLUE_SHAPE", "witness_clue_chain must be a list")
    out: list[dict[str, Any]] = []
    for item in chain:
        if not isinstance(item, dict) or not set(item) <= _CLUE_KEYS:
            raise GwapError(
                "CLUE_SHAPE",
                "clue keys must be a subset of {witness, prompt, answer, claims}",
            )
        for field in ("witness", "prompt", "answer"):
            if field not in item:
                raise GwapError("CLUE_SHAPE", f"clue is missing {field}")
        claims = item.get("claims", [])
        if not isinstance(claims, list):
            raise GwapError("CLUE_SHAPE", "clue.claims must be a list")
        out.append(
            {
                "witness": _norm_text(item["witness"], "witness"),
                "prompt": _norm_text(item["prompt"], "prompt"),
                "answer": _norm_text(item["answer"], "answer"),
                "claims": [normalize_claim(c) for c in claims],
            }
        )
    return out


# -- blocker (KissKissBan) -------------------------------------------------------


def build_taboo_list(
    prior_claims: Iterable[dict[str, Any]], n: int = TABOO_SIZE
) -> list[str]:
    """Top-n most common words across a scene's prior claims. Ties break
    alphabetically ((-count, word) sort): deterministic, no RNG, no stoplist --
    a stoplist and stemming are v1 debt."""
    counts: dict[str, int] = {}
    for claim in prior_claims:
        for word in claim_words(claim):
            counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [word for word, _ in ranked[: max(0, n)]]


def check_taboos(
    claims: Iterable[dict[str, Any]], taboo_list: Sequence[str]
) -> list[str]:
    """Taboo words (as tokens) used by these claims, sorted alphabetically.
    Token-level match: 'vault' does not fire on 'vaulted' (stemming is v1 debt)."""
    taboo = {t.lower().strip() for t in taboo_list if str(t).strip()}
    used: set[str] = set()
    for claim in claims:
        used.update(claim_words(claim))
    return sorted(used & taboo)


# -- agreement engine ------------------------------------------------------------


def _add_weights(
    vec: dict[tuple[str, str, str, str], float],
    claims: Iterable[dict[str, Any]],
    weight: float,
) -> None:
    """Side vector update: a triple's side weight is the MAX of its authors'
    weights on that side, so repeating one claim inside a side adds nothing
    (stuffing is worthless before the score is even computed)."""
    for claim in claims:
        triple = claim_triple(claim)
        if weight > vec.get(triple, 0.0):
            vec[triple] = weight


def agreement_score(
    intent_struct: Any,
    report_struct: Any,
    witness_clue_chain: Any = (),
) -> float:
    """Weighted Jaccard over canonicalized claim triples.

    Side A = robber claims (weight 1.0). Side B = cop claims (weight 1.0) updated
    with witness clue claims (weight 0.5, max-folded into side B). Score =
    sum(min(a, b)) / sum(max(a, b)) over the union of triples, rounded to
    SCORE_DECIMALS. Equal weights reduce this to plain Jaccard. Empty union
    scores 0.0: no evidence, no agreement.
    """
    chain = normalize_witness_chain(witness_clue_chain)
    side_a: dict[tuple[str, str, str, str], float] = {}
    _add_weights(side_a, _claims_of(intent_struct), ROLE_WEIGHTS["robber"])
    side_b: dict[tuple[str, str, str, str], float] = {}
    _add_weights(side_b, _claims_of(report_struct), ROLE_WEIGHTS["cop"])
    for clue in chain:
        _add_weights(side_b, clue["claims"], ROLE_WEIGHTS["witness"])

    triples = set(side_a) | set(side_b)
    if not triples:
        return 0.0
    inter = sum(min(side_a.get(t, 0.0), side_b.get(t, 0.0)) for t in triples)
    union = sum(max(side_a.get(t, 0.0), side_b.get(t, 0.0)) for t in triples)
    if union <= 0.0:
        return 0.0
    return round(inter / union, SCORE_DECIMALS)


# -- collusion fingerprint --------------------------------------------------------


def collusion_fingerprint(intent_struct: Any, report_struct: Any) -> dict[str, Any]:
    """v0 fingerprint: independent authors rarely order identical claims
    identically. Fires only when (a) the two authors differ, (b) both sides hold
    at least MIN_COLLUSION_SEQ claims (one claim has no order information), and
    (c) the canonical triple sequences are exactly equal. Shuffles never fire."""
    intent = _normalize_struct(intent_struct, "intent_struct")
    report = _normalize_struct(report_struct, "report_struct")
    seq_a = [claim_triple(c) for c in intent["claims"]]
    seq_b = [claim_triple(c) for c in report["claims"]]
    n = min(len(seq_a), len(seq_b))

    if intent["author"] == report["author"]:
        return {
            "suspected_collusion": False,
            "compared_claims": n,
            "evidence": "same author id on both structs (not independent)",
        }
    if n < MIN_COLLUSION_SEQ:
        return {
            "suspected_collusion": False,
            "compared_claims": n,
            "evidence": "below 2 claims there is no order information",
        }
    if seq_a != seq_b:
        return {
            "suspected_collusion": False,
            "compared_claims": n,
            "evidence": "claim orders differ",
        }
    return {
        "suspected_collusion": True,
        "compared_claims": n,
        "evidence": (
            f"identical order of {len(seq_a)} claims between independent "
            f"authors {intent['author']} and {report['author']}"
        ),
    }


# -- verdicts ---------------------------------------------------------------------


def decide_verdict(
    score: float,
    taboo_violations: Sequence[str] = (),
    suspected_collusion: bool = False,
) -> str:
    """BLOCKED outranks the score ladder (a blocked round is blocked, whatever
    the authors agree on). Boundaries: 0.6 and 0.3 are inclusive lower edges.
    v1 auto-downgrade: suspected_collusion demotes VERIFIED_AGREE to CHALLENGE
    (judgment owed before credit); BLOCKED precedence, the band edges, and
    every other verdict are untouched. The third argument defaults False, so
    every v0 two-argument call keeps its exact v0 behavior."""
    if list(taboo_violations):
        return BLOCKED
    if score >= VERIFIED_AGREE_MIN:
        return CHALLENGE if suspected_collusion else VERIFIED_AGREE
    if score >= CHALLENGE_MIN:
        return CHALLENGE
    return DISPUTE


def default_artifact_rarity(verdict: str, suspected_collusion: bool) -> str:
    """Deterministic rarity of the artifact the round mints. A verified clean
    agreement is the product (r); a collusion-tainted one is discounted.
    v1: since the downgrade sends collusion rows to CHALLENGE, the taint now
    lands on the CHALLENGE band (tainted instead of uncommon) so a judge-owed
    row can never bank as a clean uncommon. Blocked rounds mint nothing."""
    if verdict == BLOCKED:
        return "void"
    if verdict == VERIFIED_AGREE:
        return "tainted" if suspected_collusion else "rare"
    if verdict == CHALLENGE:
        return "tainted" if suspected_collusion else "uncommon"
    return "common"


# -- payload assembly -------------------------------------------------------------


def _require(condition: bool, reason: str, message: str) -> None:
    if not condition:
        raise GwapError(reason, message)


def build_payload(
    *,
    scene_id: str,
    intent_struct: dict[str, Any],
    report_struct: dict[str, Any],
    participants: list[dict[str, Any]],
    consent: bool,
    created_utc: str,
    replay_tape_ref: dict[str, Any],
    witness_clue_chain: Any = (),
    taboo_list: Sequence[str] = (),
) -> dict[str, Any]:
    """Assemble one mag_gwap_payload.v1 dict. Pure: every timestamp and tape ref
    is injected, so identical arguments produce byte-identical payloads.

    meter_credit.receipt_sha256 hashes the canonical payload BODY (every field
    except meter_credit): the credit is earned by exactly these bytes, quotable
    outside the ledger. byte_backed is True because the payload only becomes
    real once a hash-chained ledger row carries it.
    """
    _require(
        isinstance(scene_id, str) and scene_id.strip(),
        "BAD_SCENE", "scene_id must be a non-empty string",
    )
    _require(type(consent) is bool, "BAD_CONSENT", "consent must be a bool")
    _require(
        isinstance(created_utc, str) and bool(_UTC_RE.match(created_utc)),
        "BAD_TS", "created_utc must be an ISO-8601 UTC timestamp string",
    )
    _require(
        isinstance(replay_tape_ref, dict)
        and set(replay_tape_ref) == _TAPE_KEYS
        and isinstance(replay_tape_ref["engine_version"], str)
        and replay_tape_ref["engine_version"].strip()
        and isinstance(replay_tape_ref["sha256"], str)
        and bool(_SHA256_RE.match(replay_tape_ref["sha256"])),
        "BAD_TAPE",
        "replay_tape_ref must be {sha256: 64-hex, engine_version: str}",
    )

    _require(isinstance(participants, list), "BAD_PARTICIPANTS",
             "participants must be a list")
    roles: dict[str, str] = {}
    for p in participants:
        _require(
            isinstance(p, dict) and set(p) == _PARTICIPANT_KEYS,
            "BAD_PARTICIPANTS",
            "each participant is exactly {anon_id, role}",
        )
        _require(
            isinstance(p["anon_id"], str) and p["anon_id"].strip(),
            "BAD_PARTICIPANTS", "anon_id must be a non-empty string",
        )
        _require(p["role"] in ROLES, "BAD_PARTICIPANTS",
                 f"role must be one of {ROLES}")
        _require(p["anon_id"] not in roles, "BAD_PARTICIPANTS",
                 f"duplicate participant {p['anon_id']}")
        roles[p["anon_id"]] = p["role"]

    intent = _normalize_struct(intent_struct, "intent_struct")
    report = _normalize_struct(report_struct, "report_struct")
    chain = normalize_witness_chain(witness_clue_chain)

    _require(roles.get(intent["author"]) == "robber", "ROLE_WIRING",
             "intent_struct.author must be a declared robber")
    _require(roles.get(report["author"]) == "cop", "ROLE_WIRING",
             "report_struct.author must be a declared cop")
    for clue in chain:
        _require(roles.get(clue["witness"]) == "witness", "ROLE_WIRING",
                 f"witness {clue['witness']} must be a declared witness")

    taboo = [str(t).lower().strip() for t in taboo_list if str(t).strip()]
    violations = sorted(
        set(check_taboos(intent["claims"], taboo))
        | set(check_taboos(report["claims"], taboo))
    )

    score = agreement_score(intent, report, chain)
    fingerprint = collusion_fingerprint(intent, report)
    verdict = decide_verdict(score, violations, fingerprint["suspected_collusion"])

    body = {
        "schema": SCHEMA,
        "scene_id": scene_id,
        "participants": deepcopy(participants),
        "consent": consent,
        "intent_struct": intent,
        "report_struct": report,
        "witness_clue_chain": chain,
        "agreement_score": score,
        "blocker_taboo_list": taboo,
        "taboo_violations": violations,
        "verdict": verdict,
        "collusion_fingerprint": fingerprint,
        "replay_tape_ref": deepcopy(replay_tape_ref),
        "signature": {"scheme": "unsigned-v0", "signed_by": []},
        "created_utc": created_utc,
    }
    receipt = _sha256_hex(canonical(body))
    body["meter_credit"] = {
        "artifact_rarity": default_artifact_rarity(
            verdict, fingerprint["suspected_collusion"]
        ),
        "byte_backed": True,
        "receipt_sha256": receipt,
    }
    return body


# -- signatures (v1) ----------------------------------------------------------------

SIG_ALGO = "ed25519-v1"
SIG_BLOCK_KEYS = {"algo", "pubkey", "sig", "signed_by"}


def author_keypair(seed: str) -> tuple[str, str]:
    """Deterministic (private_hex, public_hex) author keypair from a SECRET
    seed: the 32-byte Ed25519 private seed is sha256(SCHEMA + ":" + seed).
    Deterministic on purpose -- the no-RNG law and byte-reproducible tests
    both want the same seed to always yield the same identity. The seed is a
    SECRET: derive it from the operator keychain, never from a public id
    (anon_id is public by design and must not be a key)."""
    _require(HAS_CRYPTO, "NO_CRYPTO",
             "the cryptography package is not installed in this venv")
    _require(isinstance(seed, str) and seed.strip(), "BAD_SEED",
             "seed must be a non-empty string")
    priv_bytes = hashlib.sha256(
        f"{SCHEMA}:ed25519:{seed}".encode("utf-8")
    ).digest()
    priv = Ed25519PrivateKey.from_private_bytes(priv_bytes)
    pub_hex = priv.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw
    ).hex()
    return priv_bytes.hex(), pub_hex


def sign_payload(
    payload: dict[str, Any], author: str, private_hex: str
) -> dict[str, Any]:
    """Return a SIGNED deep copy of a built payload (the input is never
    mutated). The signature block {algo, pubkey, sig, signed_by} replaces the
    unsigned-v0 placeholder.

    What the signature commits to: canonical(payload minus its own signature
    field). Everything else rides in the signed bytes -- claims, score,
    verdict, AND meter_credit with its receipt -- so no post-signing byte
    change anywhere in the payload survives verify_signature(). A signature
    cannot contain itself, hence the single exclusion. The excluded signature
    field is still bound the other way: meter_credit.receipt_sha256 is the
    build-time receipt (the v0 law, computed over the body as built) and the
    signature commits to that receipt, so receipt + signature jointly
    identify every byte of the row.

    The signer must be a declared participant (same wiring law as the
    claims). Ed25519 is deterministic (RFC 8032): re-signing identical bytes
    yields the identical signature."""
    _require(HAS_CRYPTO, "NO_CRYPTO",
             "the cryptography package is not installed in this venv")
    _require(
        isinstance(payload, dict) and payload.get("schema") == SCHEMA,
        "BAD_SCHEMA", "only mag_gwap_payload.v1 payloads are signed",
    )
    _require(isinstance(author, str) and author.strip(), "SIGNATURE",
             "author must be a non-empty string")
    _require(
        any(
            isinstance(p, dict) and p.get("anon_id") == author
            for p in payload.get("participants", [])
        ),
        "SIGNATURE", f"author {author!r} is not a declared participant",
    )
    _require(
        isinstance(private_hex, str) and bool(_HEX32_RE.match(private_hex)),
        "BAD_KEY", "private_hex must be 64 hex chars (a 32-byte ed25519 seed)",
    )
    core = {k: v for k, v in deepcopy(payload).items() if k != "signature"}
    message = canonical(core).encode("utf-8")
    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_hex))
    pub_hex = priv.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw
    ).hex()
    sig_hex = priv.sign(message).hex()
    signed = deepcopy(payload)
    signed["signature"] = {
        "algo": SIG_ALGO,
        "pubkey": pub_hex,
        "sig": sig_hex,
        "signed_by": [author],
    }
    return signed


def verify_signature(payload: Any) -> bool:
    """The PUBLIC offline check: the pubkey rides in the signature block and
    the signed bytes are canonical(payload minus signature), so anyone holding
    the json row (ledger file, screenshot, quote) can verify without a
    network, a keychain, or this venv's config. False (never raises) on: wrong
    shape, unsigned-v0 payloads, malformed hex, a swapped pubkey, a mutated
    signature, or any post-signing byte change elsewhere in the payload."""
    if not HAS_CRYPTO or not isinstance(payload, dict):
        return False
    block = payload.get("signature")
    if not isinstance(block, dict) or set(block) != SIG_BLOCK_KEYS:
        return False
    if block["algo"] != SIG_ALGO:
        return False
    if not isinstance(block["pubkey"], str) or not _HEX32_RE.match(block["pubkey"]):
        return False
    if not isinstance(block["sig"], str) or not _HEX64_RE.match(block["sig"]):
        return False
    if not isinstance(block["signed_by"], list) or not block["signed_by"]:
        return False
    core = {k: v for k, v in payload.items() if k != "signature"}
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(block["pubkey"]))
        pub.verify(bytes.fromhex(block["sig"]), canonical(core).encode("utf-8"))
    except Exception:
        return False
    return True


# -- session ledger ---------------------------------------------------------------


def _row_hash(row: dict[str, Any]) -> str:
    payload = {key: row[key] for key in ("seq", "ts_utc", "payload", "prev_sha256")}
    return _sha256_hex(canonical(payload))


def verify_chain_file(path: Path | str) -> tuple[bool, int | None]:
    """Tamper detection over the FILE bytes: (ok, first_bad_row) with a 1-based
    row number, None when ok. Catches, in order per row: unparseable line, wrong
    key set, seq not matching position, prev_sha256 not linking to the previous
    row's row_sha256 (genesis = 64 zeros), row_sha256 not matching a recompute."""
    path = Path(path)
    if not path.exists():
        return True, None
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    prev = _ZERO_HASH
    for i, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except ValueError:
            return False, i
        if not isinstance(row, dict) or set(row) != _ROW_KEYS:
            return False, i
        if type(row["seq"]) is not int or row["seq"] != i:
            return False, i
        if row["prev_sha256"] != prev:
            return False, i
        if row["row_sha256"] != _row_hash(row):
            return False, i
        prev = row["row_sha256"]
    return True, None


class SessionLedger:
    """Append-only JSONL ledger, one file per session. Construction fails closed
    on a chain that does not verify; append() refuses to extend anything it
    cannot verify first. Rows are never edited or removed by this class."""

    def __init__(self, session_id: str, store: Path | str | None = None) -> None:
        _require(
            isinstance(session_id, str)
            and bool(_SESSION_ID_RE.match(session_id)),
            "BAD_SESSION_ID",
            "session_id must match [A-Za-z0-9][A-Za-z0-9._-]{0,63}",
        )
        self.session_id = session_id
        self.store = Path(store) if store is not None else STORE
        self.path = self.store / f"{session_id}.jsonl"
        self._rows: list[dict[str, Any]] = []
        if self.path.exists():
            self._rows = self._read_rows()

    def _read_rows(self) -> list[dict[str, Any]]:
        ok, bad = verify_chain_file(self.path)
        if not ok:
            raise GwapError(
                "BROKEN_CHAIN",
                f"{self.path.name} fails verification at row {bad}",
            )
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    @property
    def rows(self) -> list[dict[str, Any]]:
        return deepcopy(self._rows)

    def verify_chain(self) -> tuple[bool, int | None]:
        """Reads the file, not the cached rows: truth is the bytes on disk."""
        return verify_chain_file(self.path)

    def append(
        self, payload: dict[str, Any], ts_utc: str | None = None
    ) -> dict[str, Any]:
        _require(
            isinstance(payload, dict) and payload.get("schema") == SCHEMA,
            "BAD_SCHEMA", "rows carry mag_gwap_payload.v1 payloads only",
        )
        ok, bad = self.verify_chain()
        _require(ok, "BROKEN_CHAIN",
                 f"refusing to extend a broken chain (first bad row {bad})")
        ts = utc_now_iso() if ts_utc is None else ts_utc
        _require(
            bool(_UTC_RE.match(ts)), "BAD_TS",
            "ts_utc must be an ISO-8601 UTC timestamp string",
        )
        seq = len(self._rows) + 1
        prev = self._rows[-1]["row_sha256"] if self._rows else _ZERO_HASH
        row: dict[str, Any] = {
            "seq": seq,
            "ts_utc": ts,
            "payload": deepcopy(payload),
            "prev_sha256": prev,
        }
        row["row_sha256"] = _row_hash(row)
        self.store.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical(row) + "\n")
        self._rows.append(row)
        return deepcopy(row)


# -- demo ---------------------------------------------------------------------------


def _demo() -> None:
    ts = utc_now_iso()

    # Prior-round claims from earlier scenes in this session: the Blocker bans
    # their most common words (pure frequency, no stoplist in v0), so this
    # round's authors must describe differently. Counts by design: crowbar 4,
    # stairwell 4, then mask / robber / whistle 3 each, everything else 1 --
    # top-5 = [crowbar, stairwell, mask, robber, whistle].
    prior_corpus = [
        {"subject": "robber", "verb": "took", "object": "stairwell route"},
        {"subject": "crowbar", "verb": "scratched", "object": "stairwell door"},
        {"subject": "robber", "verb": "pried", "object": "stairwell frame"},
        {"subject": "crowbar", "verb": "marked", "object": "mask locker"},
        {"subject": "whistle", "verb": "opened", "object": "mask locker"},
        {"subject": "whistle", "verb": "echoed", "object": "past mask rack"},
        {"subject": "crowbar", "verb": "rang", "object": "off whistle pipe"},
        {"subject": "robber", "verb": "stashed", "object": "crowbar under stairwell"},
    ]
    taboo = build_taboo_list(prior_corpus)

    robber = anon_id("demo-robber-20260929")
    cop = anon_id("demo-cop-20260929")
    witness = anon_id("demo-witness-20260929")
    participants = [
        {"anon_id": robber, "role": "robber"},
        {"anon_id": cop, "role": "cop"},
        {"anon_id": witness, "role": "witness"},
    ]
    tape = {
        "sha256": _sha256_hex("demo replay tape: rung B3, 2026-09-29"),
        "engine_version": "mud-presence-v0",
    }

    def claim(s: str, v: str, o: str, q: str = "") -> dict[str, str]:
        return {"subject": s, "verb": v, "object": o, "qualifier": q}

    # Session 1: clean agreement. Cop reconstructs 2 of 3 intent claims and the
    # witness corroborates the third at half weight. Orders differ (no collusion).
    # None of the claims use a tabooed word (subject "intruder", not "robber").
    intent_claims = [
        claim("intruder", "cut", "junction power", "at the breaker"),
        claim("crew", "drilled", "deposit boxes", "night wing"),
        claim("getaway driver", "idled", "dock side", "engine off"),
    ]
    report_claims = [
        claim("intruder", "cut", "junction power", "at the breaker"),
        claim("getaway driver", "idled", "dock side", "engine off"),
        claim("responders", "sealed", "night wing"),
    ]
    clue = [{
        "witness": witness,
        "prompt": "What did the crew open?",
        "answer": "the deposit boxes in the night wing",
        "claims": [claim("crew", "drilled", "deposit boxes", "night wing")],
    }]
    clean = build_payload(
        scene_id="scene-midtown-042",
        intent_struct={"author": robber, "claims": intent_claims},
        report_struct={"author": cop, "claims": report_claims},
        participants=participants,
        consent=True,
        created_utc=ts,
        replay_tape_ref=tape,
        witness_clue_chain=clue,
        taboo_list=taboo,
    )

    # Session 2: collusion. The cop copies the robber's claims verbatim, order
    # included: score 1.0 but the order fingerprint fires and v1 downgrades the
    # verdict to CHALLENGE (judgment owed before credit).
    copied = build_payload(
        scene_id="scene-docks-007",
        intent_struct={"author": robber, "claims": deepcopy(intent_claims)},
        report_struct={"author": cop, "claims": deepcopy(intent_claims)},
        participants=participants,
        consent=True,
        created_utc=ts,
        replay_tape_ref=tape,
        taboo_list=taboo,
    )

    # v1: the robber seals the clean payload with an ed25519 author key before
    # it enters the ledger; anyone can re-verify the row offline afterwards.
    if HAS_CRYPTO:
        priv_hex, _pub_hex = author_keypair("demo-robber-key-20260929")
        clean = sign_payload(clean, robber, priv_hex)

    for label, payload, session_id in (
        ("clean agreement", clean, "b3-demo-clean-20260929"),
        ("collusion copy", copied, "b3-demo-collusion-20260929"),
    ):
        ledger = SessionLedger(session_id)
        ledger.append(payload, ts_utc=ts)
        ok, bad = ledger.verify_chain()
        print(f"[{label}] session={session_id}")
        print(f"  taboo list        : {payload['blocker_taboo_list']}")
        print(f"  agreement_score   : {payload['agreement_score']}")
        print(f"  verdict           : {payload['verdict']}")
        print(f"  suspected_collusion: "
              f"{payload['collusion_fingerprint']['suspected_collusion']}")
        print(f"  artifact_rarity   : "
              f"{payload['meter_credit']['artifact_rarity']}")
        print(f"  signature verify  : {verify_signature(payload)}")
        print(f"  ledger verify     : ok={ok} first_bad_row={bad}")
        print(f"  file              : {ledger.path}")
    print("chain tip note: v1 downgrades a collusion-flagged VERIFIED_AGREE to")
    print("CHALLENGE; the judge queue that consumes those rows is still owed.")


if __name__ == "__main__":
    _demo()
