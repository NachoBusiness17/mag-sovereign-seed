"""grounding_wave — the GROUND circuit's ledger (operator algebra: GROUND primitive).

A wave post = ONE ground-truth claim with a tri-state verdict + an evidence
pointer, hash-chained to the previous post. Append-only: corrections are new
posts that cite the old hash (delete-as-append). Doctrine rides the standing
wave; the grounding wave carries only what we can point at.

LAW CITATION: files not processes; chain-side append, nothing scheduled.

wave v4 (2026-09-16, stone 1 of the EPISTEMOLOGY ENGINE — design receipt
watch/inbox/wave_20260916/receipts/A2_EPISTEMOLOGY_ENGINE.md): an
evidence-ADMISSION boundary on top of the v3 truth-gate. RECORDED is no longer
the top of the ladder:

    RECORDED -> CORROBORATED -> CONTESTED -> VOID

  G1 STRUCTURAL — canonical versioned hash + prev chain, enforced at WRITE
     time (`_admit` gate runs inside the append lock on every verb): a row
     missing its hash or prev is REFUSED AT APPEND, never at verify. The
     row-122 bypass path (a 3-key fragment with no hash, prev != tip) is
     physically closed for every v4 writer.
  G2 BINDING — path-shaped evidence gets its sha256_12 recorded in the row AT
     POST TIME (`src_sha256_12`, bones-style re-derivable). verify re-hashes
     the bytes: identity, not mere existence. Evidence edited after the fact
     stops corroborating (EVIDENCE-MUTATED FAIL). `*_latest` mutable refs are
     refused for SUPPORTED (v3's warning became a gate). Dead path-shaped
     evidence is refused at post (EVIDENCE_DEAD) — same law v3 applied at
     verify, applied earlier.
  G3 WARRANT — a claim may carry `warrant`: a command that exits 0/1, hashed
     into the row. Witness rows run it and record `checks.g3_exit`. Strike S8
     law stands: a Claim whose Check is "the author agrees" is a notary, not
     knowledge. Software never auto-truths: CORROBORATED means the warrant
     exited 0 under two independent hands, not "true".
  DELETE-AS-APPEND — `void` buries a row under a cross-signed kind:"void" row
     naming the target's hash (`voids`) + a reason_code from the enum.
     `contest` holds a row at CONTESTED. `witness` is a separate appended row
     by a DIFFERENT seat (two-eyes law; the author never picks their own
     second eye). A void requires a named second seat at write time and only
     COUNTS once that seat's witness row is in the chain signing the void.
     Nothing is ever edited or deleted. NO AUTO-MIGRATION: legacy rows keep
     v1-v3 semantics; row 122 stays in history; only new rows carry v4 keys.

Reader law (v3 kept, extended): verify() reports LINKAGE over the physical
tape AND the ADMISSION summary (effective ledger = rows - voided, plus
VOIDED/pending/propagation). Readers quote the admission view, never bare
PASS. `view` prints the effective ledger with the ladder status per row.

Status ladder per row (admission semantics):
  RECORDED      G1 pass (append)
  CORROBORATED  >=2 witness rows, distinct seats, neither the author, checks pass
  CONTESTED     an effective kind:"contest" row targets it
  VOID          an effective (cross-signed) kind:"void" row targets it

Corroboration raises confidence, never grants permission; effects stay
switchboard-only.

CLI:
  python -m mag.grounding_wave post --claim "..." --verdict SUPPORTED \
      --evidence path-or-pointer [--note "..."] [--warrant "cmd"] [--dry]
  python -m mag.grounding_wave void --row <hash-prefix|#line> \
      --reason-code MALFORMED --reason "..." --witness <second-seat> [--dry]
  python -m mag.grounding_wave contest --row <hash-prefix|#line> \
      --reason "..." [--seat ...] [--dry]
  python -m mag.grounding_wave witness --row <hash-prefix> [--seat ...] [--dry]
  python -m mag.grounding_wave verify
  python -m mag.grounding_wave view
  python -m mag.grounding_wave render
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "watch" / "GROUNDING_WAVE.jsonl"
VIEW_MD = ROOT / "watch" / "GROUNDING_WAVE.md"
VIEW_STATIC = ROOT / "dashboard" / "static" / "grounding_wave.md"
GENESIS = "0" * 64
VERDICTS = ("SUPPORTED", "DISPUTED", "UNPROVEN")
LADDER = ("RECORDED", "CORROBORATED", "CONTESTED", "VOID")

# wave v2 (salon 20260906, astra catch): rows carry a `seat` (poster identity,
# hashed — attribution is provable, forks are attributable) and verify() audits
# EVIDENCE, not just linkage — a hash-valid post whose evidence path is dead
# FAILS the chain check. Hashing uses .get defaults so v1 rows stay valid.
#
# wave v3 (20260908, astra witness #5 + salon-audit catch): the FALSE-RECEIPT
# attack passed verify() with a fabricated SUPPORTED row (0/1 rejected) —
# linkage-PASS was being read as truth-PASS. Three teeth, forward-applied:
#   1. SUPPORTED requires a second witness (v3 rows); unwitnessed SUPPORTED is
#      auto-demoted to UNPROVEN with a demotion note (delete-as-append: a later
#      witnessed post upgrades it).
#   2. post() holds an append lock (concurrent writers were a named liability).
#   3. verify() reports LINKAGE-PASS (hashes+evidence) separately from the
#      admission audit (witnessed vs legacy-unwitnessed SUPPORTED rows) — no
#      reader may quote bare "PASS" again.
#
# wave v4 (20260916, A2 stone 1): see module docstring. Versioned key sets per
# row `kind`; .get defaults keep v1-v3 rows valid (no auto-migration).
_PATH_RE = re.compile(r"(?:[\w.-]+/)+[\w.-]+\.[\w]+")  # file-like paths only (ext required)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
LOCK = LEDGER.parent / "GROUNDING_WAVE.lock"

_V1_KEYS = ("prev", "ts", "claim", "verdict", "evidence", "note")
_V2_KEYS = ("prev", "ts", "claim", "verdict", "evidence", "note", "seat")
_V3_KEYS = ("prev", "ts", "claim", "verdict", "evidence", "note", "seat", "witness")

# v4 key sets, per row kind (A2 §5.1: versioned key set gains `kind` +
# `src_sha256_12` + kind-specific keys; hash excluded, canonical JSON).
_KIND_KEYS: dict[str, tuple[str, ...]] = {
    "claim": ("prev", "ts", "kind", "claim", "verdict", "evidence", "note",
              "seat", "witness", "src_sha256_12", "warrant"),
    "void": ("prev", "ts", "kind", "voids", "reason_code", "reason", "evidence",
             "seat", "witness"),
    "contest": ("prev", "ts", "kind", "contests", "reason", "evidence", "seat"),
    "witness": ("prev", "ts", "kind", "signs", "checks", "seat"),
}
_ACT_KINDS = ("void", "contest", "witness")

# void reason_code enum (A2 §2)
VOID_REASONS = ("MALFORMED", "FORGED", "EVIDENCE_DEAD", "EVIDENCE_MUTATED",
                "WARRANT_FAILED", "DUPLICATE", "SUPERSEDED", "CONTEST_SUSTAINED")

STALE_CONTEST_DAYS = 7  # closure counter (A2 §4.3)


class GateRefusal(Exception):
    """Typed admission refusal (A2 G1-G3). Never a crash: the caller gets a
    reason code. main() turns this into exit 2."""

    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(f"GATE-{code}: {detail}")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rows() -> list[dict[str, Any]]:
    if not LEDGER.is_file():
        return []
    out = []
    for ln in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if ln:
            out.append(json.loads(ln))
    return out


def _row_hash(row: dict[str, Any]) -> str:
    # Schema-versioned: v4 rows (kind present) hash under their per-kind key
    # set; v3 rows (witness, no kind) under the v3 key set; v2 rows add seat;
    # v1 rows are the founding six. Extra keys (e.g. ttl_s) ride OUTSIDE the
    # hashed set on purpose (wave_driver contract).
    if "kind" in row:
        keys = _KIND_KEYS.get(row.get("kind"), _KIND_KEYS["claim"])
    elif "witness" in row:
        keys = _V3_KEYS
    elif "seat" in row:
        keys = _V2_KEYS
    else:
        keys = _V1_KEYS
    core = json.dumps({k: row.get(k, "") for k in keys},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(core.encode("utf-8")).hexdigest()


class _AppendLock:
    """O_EXCL lockfile with stale-break (Windows-safe, no fcntl)."""

    def __init__(self, path: Path, timeout_s: float = 15.0, stale_s: float = 60.0):
        self.path, self.timeout_s, self.stale_s = path, timeout_s, stale_s
        self._fd: int | None = None

    def __enter__(self) -> "_AppendLock":
        import os as _os, time as _time
        deadline = _time.time() + self.timeout_s
        while True:
            try:
                self._fd = _os.open(self.path, _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
                return self
            except FileExistsError:
                try:
                    if _time.time() - self.path.stat().st_mtime > self.stale_s:
                        self.path.unlink(missing_ok=True)  # stale lock from a dead writer
                        continue
                except FileNotFoundError:
                    continue
                if _time.time() > deadline:
                    self._fd = None
                    return self  # degrade to lockless append rather than lose the post
                _time.sleep(0.25)

    def __exit__(self, *exc: Any) -> None:
        import os as _os
        if self._fd is not None:
            _os.close(self._fd)
            self.path.unlink(missing_ok=True)


# --------------------------------------------------------------------- G2 bits
def _src_path(tok: str) -> Path:
    p = Path(tok)
    return p if p.is_absolute() else ROOT / tok


def _bind_sources(evidence: str) -> dict[str, str]:
    """G2: record sha256_12 of every evidence token that resolves to a file,
    AT POST TIME (bones law: parsed, hashed, re-derivable)."""
    out: dict[str, str] = {}
    for tok in (evidence or "").split():
        tok = tok.strip().strip(",;")
        if not tok:
            continue
        try:
            cand = _src_path(tok)
            if cand.is_file():
                out[tok] = hashlib.sha256(cand.read_bytes()).hexdigest()[:12]
        except OSError:
            continue
    return out


def _src_ok(tok: str, h12: str) -> bool:
    try:
        cand = _src_path(tok)
        if not cand.is_file():
            return False
        return hashlib.sha256(cand.read_bytes()).hexdigest()[:12] == h12
    except OSError:
        return False


def _missing_tokens(evidence: str) -> list[str]:
    """Path-shaped evidence tokens that do not resolve (v4: refused at post;
    v3 checked the same law at verify). Absolute paths honored."""
    out = []
    for tok in sorted(set((evidence or "").split())):
        tok = tok.strip().strip(",;")
        if not tok or not _PATH_RE.search(tok):
            continue
        try:
            cand = _src_path(tok)
            if cand.exists():
                continue
            if not cand.is_absolute() and any(ROOT.glob(tok + "*")):
                continue  # prefix of a real sibling (e.g. .bak-suffixed snapshots)
        except Exception:  # noqa: BLE001 — malformed glob chars fall through
            pass
        out.append(tok)
    return out


# ------------------------------------------------------------- admission view
def _admission(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Effective-ledger computation (v4 reader law). Read-only: the physical
    tape is never mutated by admission — it is a VIEW over the bytes.

    Returns statuses per row index (1-based), effective/pending voids,
    contests, witnesses, and propagation flags (chain-visible descendants of
    VOID rows)."""
    def key(i: int, r: dict[str, Any]) -> str:
        return r.get("hash") or f"line:{i}"

    acts = [(i, r) for i, r in enumerate(rows, 1) if r.get("kind") in _ACT_KINDS]

    def cross_signed(v: dict[str, Any]) -> bool:
        return any(w.get("kind") == "witness" and w.get("signs") == v.get("hash")
                   and w.get("seat") == v.get("witness") for w in rows)

    # Fixed point: a void counts when cross-signed by its named second seat;
    # a voided void stops counting (void-of-void = reversal, same verb).
    effective: dict[str, dict[str, Any]] = {
        r["hash"]: r for _, r in acts
        if r.get("kind") == "void" and r.get("hash") and cross_signed(r)}
    while True:
        killed = {v.get("voids") for v in effective.values()}
        nxt = {h: r for h, r in effective.items() if h not in killed}
        if set(nxt) == set(effective):
            break
        effective = nxt
    killed = {v.get("voids") for v in effective.values()}
    voided_keys = set(killed)  # target keys (hashes + "line:N")
    voided_hashes = {k for k in voided_keys if isinstance(k, str) and _HEX64.match(k)}

    all_void_rows = {r["hash"]: r for _, r in acts
                     if r.get("kind") == "void" and r.get("hash")}
    pending_voids = {h: r for h, r in all_void_rows.items()
                     if h not in effective and h not in killed}

    contests: dict[str, list[dict[str, Any]]] = {}
    witnesses: dict[str, list[dict[str, Any]]] = {}
    for i, r in acts:
        if r.get("hash") and r["hash"] in voided_keys:
            continue  # a voided act stops counting
        if r.get("kind") == "contest":
            contests.setdefault(r.get("contests"), []).append(r)
        elif r.get("kind") == "witness":
            witnesses.setdefault(r.get("signs"), []).append(r)

    statuses: dict[int, str] = {}
    propagation: list[tuple[int, str]] = []
    for i, r in enumerate(rows, 1):
        k = r.get("kind")
        if k in _ACT_KINDS:
            if r.get("signs") in voided_hashes:
                propagation.append((i, "witness-of-void"))
            continue
        kk = key(i, r)
        if kk in voided_keys:
            statuses[i] = "VOID"
        elif kk in contests:
            statuses[i] = "CONTESTED"
        else:
            ws = [w for w in witnesses.get(r.get("hash"), [])
                  if w.get("seat") != r.get("seat")]
            seats = {w.get("seat") for w in ws}
            checks_ok = all(
                w.get("checks", {}).get("g1") is True
                and w.get("checks", {}).get("g2") is not False
                and w.get("checks", {}).get("g3_exit") in (None, 0)
                for w in ws)
            statuses[i] = ("CORROBORATED"
                           if r.get("hash") and len(seats) >= 2 and checks_ok
                           else "RECORDED")
        if r.get("prev") in voided_hashes:
            propagation.append((i, "child-of-void"))
    return {
        "statuses": statuses,
        "effective_voids": effective,
        "pending_voids": pending_voids,
        "voided_keys": voided_keys,
        "voided_hashes": voided_hashes,
        "contests": contests,
        "witnesses": witnesses,
        "propagation": propagation,
    }


def _live_claim(rows: list[dict[str, Any]], j: int, voided_keys: set[str]) -> bool:
    """Row j (1-based) is a claim-kind row that is hashed and not voided."""
    r = rows[j - 1]
    if r.get("kind") in _ACT_KINDS:
        return False
    h = r.get("hash")
    if not isinstance(h, str) or not _HEX64.match(h):
        return False
    return not (h in voided_keys or f"line:{j}" in voided_keys)


def _tip(rows: list[dict[str, Any]], adm: dict[str, Any]) -> tuple[str, int]:
    """Admission tip: hash of the last live claim row (acts, voided rows and
    hashless rows are transparent). Returns (hash, skipped_count) — the count
    feeds the §2 re-anchor note."""
    vk = adm["voided_keys"]
    skipped = 0
    for i in range(len(rows), 0, -1):
        if _live_claim(rows, i, vk):
            return rows[i - 1]["hash"], skipped
        skipped += 1
    # No live claim at all (every claim voided): extend the PHYSICAL tip so
    # the chain never collapses to GENESIS mid-tape — void-of-void reversals
    # can re-validate earlier rows, and a GENESIS prev there would strand them.
    if rows:
        h = rows[-1].get("hash")
        if isinstance(h, str) and _HEX64.match(h):
            return h, skipped
    return GENESIS, skipped


def _reanchor_ok(rows: list[dict[str, Any]], i: int, p: Any, adm: dict[str, Any]) -> bool:
    """§2 re-anchor rule, reader side: row i's prev may point past a voided
    stretch. Valid iff every live claim row strictly between the referenced
    base and row i is voided/hashless (i.e. the stretch is fully buried)."""
    vk = adm["voided_keys"]
    if not isinstance(p, str):
        return False
    if p == GENESIS:
        m = 0
    else:
        m = next((j for j, r in enumerate(rows, 1) if r.get("hash") == p), 0)
        if not m:
            return False
    while m > 0 and not _live_claim(rows, m, vk):
        m -= 1
    for j in range(m + 1, i):
        if _live_claim(rows, j, vk):
            return False
    return True


# ------------------------------------------------------------------- G1 gate
def _admit(row: dict[str, Any], rows: list[dict[str, Any]],
           adm: dict[str, Any]) -> None:
    """v4 G1 STRUCTURAL gate — runs INSIDE the append lock on EVERY verb
    before a byte hits the tape. A row missing its hash or prev is refused at
    write, not at verify: the row-122 bypass path is physically impossible
    for any writer that goes through here."""
    h = row.get("hash")
    if not isinstance(h, str) or not _HEX64.match(h):
        raise GateRefusal("MALFORMED_ROW",
                          "row missing/short hash — refused at write (v4 G1; row-122 path closed)")
    if _row_hash(row) != h:
        raise GateRefusal("HASH_MISMATCH", "canonical hash does not recompute")
    p = row.get("prev")
    if not isinstance(p, str) or not _HEX64.match(p):
        raise GateRefusal("MALFORMED_ROW",
                          "row missing/short prev — refused at write (v4 G1)")
    tip, _ = _tip(rows, adm)
    if p != tip:
        raise GateRefusal("PREV_MISMATCH",
                          f"prev {p[:12]} != admission tip {tip[:12]}")
    kind = row.get("kind", "claim")
    if kind not in _KIND_KEYS:
        raise GateRefusal("MALFORMED_ROW", f"unknown row kind {kind!r}")
    if kind == "void":
        if row.get("reason_code") not in VOID_REASONS:
            raise GateRefusal("BAD_REASON_CODE",
                              f"reason_code must be one of {VOID_REASONS}")
        if not row.get("voids"):
            raise GateRefusal("MALFORMED_ROW", "void row needs a 'voids' target")
        w = str(row.get("witness", "")).strip()
        if not w or w == str(row.get("seat", "")).strip():
            raise GateRefusal("VOID_UNSIGNED",
                              "cross-signature required: --witness must name a "
                              "second seat different from --seat")
    elif kind == "witness":
        if not row.get("signs"):
            raise GateRefusal("MALFORMED_ROW", "witness row needs a 'signs' target")
    elif kind == "contest":
        if not row.get("contests"):
            raise GateRefusal("MALFORMED_ROW", "contest row needs a 'contests' target")
    else:  # claim
        if row.get("verdict") == "SUPPORTED" and not str(row.get("seat", "")).strip():
            raise GateRefusal("UNSUPPORTED_UNSEEDED",
                              "SUPPORTED without a seat is refused outright (v4 G1)")


def _find_row(rows: list[dict[str, Any]], spec: str) -> tuple[int, dict[str, Any]]:
    """Resolve a target: full hash, unique hash prefix (>=8), or '#N' (1-based
    tape line — the only way to address a hashless row like 122)."""
    spec = str(spec or "").strip()
    if spec.startswith("#"):
        try:
            n = int(spec[1:])
        except ValueError:
            raise GateRefusal("NOT_FOUND", f"bad line target {spec!r}") from None
        if not 1 <= n <= len(rows):
            raise GateRefusal("NOT_FOUND", f"line {n} out of range (1..{len(rows)})")
        return n, rows[n - 1]
    if len(spec) < 8:
        raise GateRefusal("NOT_FOUND", "hash prefix too short (min 8 chars)")
    hits = [(i, r) for i, r in enumerate(rows, 1)
            if isinstance(r.get("hash"), str) and r["hash"].startswith(spec)]
    if not hits:
        raise GateRefusal("NOT_FOUND", f"no row with hash prefix {spec[:12]}")
    if len(hits) > 1:
        raise GateRefusal("AMBIGUOUS", f"prefix {spec[:12]} matches {len(hits)} rows")
    return hits[0]


def _run_warrant(cmd: str, timeout_s: int = 60) -> int:
    """G3: run a warrant command, return its exit code (0/1 expected; -1 on
    failure to spawn/timeout). Warrants use forward slashes for paths (the
    canonical form, A2 §1: .venv/Scripts/python.exe -m mag.grounding_wave)."""
    try:
        argv = shlex.split(cmd, posix=True)
        proc = subprocess.run(argv, cwd=str(ROOT), capture_output=True,
                              text=True, timeout=timeout_s)
        return proc.returncode
    except Exception:  # noqa: BLE001 — a warrant that cannot run has failed
        return -1


def _append_locked(build: Any, dry: bool) -> tuple[dict[str, Any], bool]:
    """Shared append path: lock -> read rows -> admission -> build row via
    callback(rows, adm) -> G1 admit -> write. Returns (row, appended)."""
    with _AppendLock(LOCK):
        rows = _rows()
        adm = _admission(rows)
        row = build(rows, adm)
        _admit(row, rows, adm)
        if dry:
            return row, False
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row, True


def _new_row(base: dict[str, Any], rows: list[dict[str, Any]],
             adm: dict[str, Any], note_key: str | None = None) -> dict[str, Any]:
    """Fill prev (with §2 re-anchor note when the tip skips rows) + hash."""
    row = dict(base)
    prev, skipped = _tip(rows, adm)
    row["prev"] = prev
    if skipped and note_key and not str(row.get(note_key, "")).strip():
        row[note_key] = (f"[re-anchor: prev set past {skipped} act/voided/hashless "
                         f"row(s) (v4 §2)]")
    elif skipped and note_key:
        row[note_key] = str(row[note_key]) + (
            f" | [re-anchor: prev set past {skipped} act/voided/hashless row(s) (v4 §2)]")
    row["hash"] = _row_hash(row)
    return row


def post(claim: str, verdict: str, evidence: str, note: str = "",
         seat: str = "zcode", witness: str = "", warrant: str = "",
         src_sha256_12: dict[str, str] | None = None, dry: bool = False) -> dict[str, Any]:
    """Post one claim row through the v4 admission gates (G1-G3)."""
    verdict = str(verdict).upper()
    if verdict not in VERDICTS:
        raise GateRefusal("BAD_VERDICT", f"verdict must be one of {VERDICTS}")
    if verdict == "SUPPORTED" and not str(seat).strip():
        raise GateRefusal("UNSUPPORTED_UNSEEDED",
                          "SUPPORTED requires a seat (v4 G1: refused, not demoted)")
    demoted = False
    note = str(note).strip()
    if verdict == "SUPPORTED" and not str(witness).strip():
        # v3 truth-gate: SUPPORTED is a TWO-SEAT verdict. An unwitnessed post
        # still lands (the record keeps moving) but lands as UNPROVEN.
        verdict = "UNPROVEN"
        demoted = True
        note = (note + " | " if note else "") + \
            "auto-demoted from SUPPORTED: no second witness (v3 truth-gate)"
    evidence = str(evidence).strip()
    if verdict == "SUPPORTED" and "_latest" in evidence:
        raise GateRefusal("EVIDENCE_MUTABLE",
                          "*_latest mutable evidence refused for SUPPORTED (v4 G2) "
                          "— snapshot under state/wave_evidence/")
    dead = _missing_tokens(evidence)
    if dead:
        raise GateRefusal("EVIDENCE_DEAD",
                          f"evidence path(s) do not resolve: {', '.join(dead)}")
    bindings = dict(src_sha256_12) if src_sha256_12 is not None else _bind_sources(evidence)
    warrant = str(warrant).strip()

    def build(rows: list[dict[str, Any]], adm: dict[str, Any]) -> dict[str, Any]:
        return _new_row({
            "ts": _now(), "kind": "claim", "claim": str(claim).strip(),
            "verdict": verdict, "evidence": evidence, "note": note,
            "seat": str(seat).strip(), "witness": str(witness).strip(),
            "src_sha256_12": bindings, "warrant": warrant,
        }, rows, adm, note_key="note")

    row, appended = _append_locked(build, dry)
    if not appended:
        print("DRY — would append:")
        print(json.dumps(row, ensure_ascii=False, indent=1))
        return row
    if demoted:
        print("TRUTH-GATE: SUPPORTED without second witness -> landed as UNPROVEN "
              "(re-post with --witness to upgrade)")
    elif "_latest" in evidence:
        print("WARN: evidence cites a *_latest file (mutable) — prefer an "
              "immutable snapshot under state/wave_evidence/")
    render()
    return row


def void(target: str, reason_code: str, reason: str, seat: str = "zcode",
         evidence: str = "", witness: str = "", dry: bool = False) -> dict[str, Any]:
    """Bury a row under a cross-signed kind:"void" row (delete-as-append).
    Cross-signature: --witness names a second seat (!= poster); the void only
    COUNTS once that seat's witness row is in the chain signing the void."""
    reason_code = str(reason_code).upper()
    if reason_code not in VOID_REASONS:
        raise GateRefusal("BAD_REASON_CODE", f"reason_code must be one of {VOID_REASONS}")
    wseat = str(witness).strip()
    if not wseat or wseat == str(seat).strip():
        raise GateRefusal("VOID_UNSIGNED",
                          "cross-signature required: --witness must name a second "
                          "seat different from --seat")

    def build(rows: list[dict[str, Any]], adm: dict[str, Any]) -> dict[str, Any]:
        n, t = _find_row(rows, target)
        key = t.get("hash") or f"line:{n}"
        if key in adm["voided_keys"]:
            raise GateRefusal("ALREADY_VOIDED",
                              f"target {str(key)[:12]} is already effectively voided")
        return _new_row({
            "ts": _now(), "kind": "void", "voids": key,
            "reason_code": reason_code, "reason": str(reason).strip(),
            "evidence": str(evidence).strip(), "seat": str(seat).strip(),
            "witness": wseat,
        }, rows, adm)

    row, appended = _append_locked(build, dry)
    if not appended:
        print("DRY — would append:")
        print(json.dumps(row, ensure_ascii=False, indent=1))
    else:
        render()
    return row


def contest(target: str, reason: str, seat: str = "zcode", evidence: str = "",
            dry: bool = False) -> dict[str, Any]:
    """Mark a row CONTESTED (kind:"contest"). Holds until an outside reader
    sustains it (-> void with CONTEST_SUSTAINED) or it is buried."""

    def build(rows: list[dict[str, Any]], adm: dict[str, Any]) -> dict[str, Any]:
        n, t = _find_row(rows, target)
        return _new_row({
            "ts": _now(), "kind": "contest", "contests": t.get("hash") or f"line:{n}",
            "reason": str(reason).strip(), "evidence": str(evidence).strip(),
            "seat": str(seat).strip(),
        }, rows, adm)

    row, appended = _append_locked(build, dry)
    if not appended:
        print("DRY — would append:")
        print(json.dumps(row, ensure_ascii=False, indent=1))
    else:
        render()
    return row


def witness(target: str, seat: str = "zcode", dry: bool = False,
            timeout_s: int = 60) -> dict[str, Any]:
    """Append a kind:"witness" row signing a prior row's hash. The witness seat
    MUST differ from the signed row's seat (two-eyes law). Records what the
    witness actually checked: g1 (hash recomputes), g2 (evidence re-hash vs
    src_sha256_12), g3_exit (warrant command exit code, run by THIS hand)."""

    def build(rows: list[dict[str, Any]], adm: dict[str, Any]) -> dict[str, Any]:
        n, t = _find_row(rows, target)
        if not t.get("hash"):
            raise GateRefusal("MALFORMED_ROW",
                              f"cannot witness a hashless row (line {n}) — "
                              "use void --row #line for those")
        if str(seat).strip() and str(seat).strip() == str(t.get("seat", "")).strip():
            raise GateRefusal("SELF_SIGNED",
                              f"witness seat must differ from the signed row's "
                              f"seat ({t.get('seat')!r}) — the author never "
                              "picks their own second eye")
        g1 = _row_hash(t) == t.get("hash")
        srcs = t.get("src_sha256_12") or {}
        g2 = all(_src_ok(tok, h12) for tok, h12 in sorted(srcs.items())) if srcs else None
        g3 = _run_warrant(t["warrant"], timeout_s) if t.get("warrant") else None
        return _new_row({
            "ts": _now(), "kind": "witness", "signs": t["hash"],
            "checks": {"g1": g1, "g2": g2, "g3_exit": g3},
            "seat": str(seat).strip(),
        }, rows, adm)

    row, appended = _append_locked(build, dry)
    if not appended:
        print("DRY — would append:")
        print(json.dumps(row, ensure_ascii=False, indent=1))
    else:
        print(f"WITNESS checks: g1={row['checks']['g1']} g2={row['checks']['g2']} "
              f"g3_exit={row['checks']['g3_exit']}")
        render()
    return row


# ------------------------------------------------------------------- auditing
def _evidence_missing(rows: list[dict[str, Any]],
                      skip: set[int] | None = None) -> list[tuple[int, str]]:
    """Repo-relative slash-paths in evidence that do not resolve (v2 audit).

    A token also counts as resolved if it is a PREFIX of an existing path
    (timestamped/suffixed backups like .bak-row27-20260906 are one family).
    v4: voided rows are contained — their dead evidence no longer fails the
    chain (EVIDENCE_DEAD is a void reason)."""
    skip = skip or set()
    missing: list[tuple[int, str]] = []
    for i, row in enumerate(rows, 1):
        if i in skip:
            continue
        # v4 rows bound to absolute paths: the v3 regex strips drive letters,
        # so exempt regex tokens that are suffixes of an existing absolute
        # binding (liveness AND identity are audited by the G2 check instead).
        abs_bound = [t for t in (row.get("src_sha256_12") or {})
                     if Path(t).is_absolute() and _src_path(t).is_file()]
        for tok in sorted(set(_PATH_RE.findall(row.get("evidence", "")))):
            if any(bound.endswith(tok) or tok.endswith(bound) for bound in abs_bound):
                continue
            p = ROOT / tok
            if p.exists():
                continue
            try:
                if any(ROOT.glob(tok + "*")):
                    continue  # prefix of a real sibling (e.g. .bak-suffixed snapshots)
            except Exception:  # noqa: BLE001 — malformed glob chars fall through to missing
                pass
            missing.append((i, tok))
    return missing


def _evidence_mutated(rows: list[dict[str, Any]],
                      skip: set[int] | None = None) -> list[tuple[int, str, str, str]]:
    """v4 G2 identity audit: re-hash every bound source; a mismatch means the
    evidence was edited after the fact (EVIDENCE_MUTATED)."""
    skip = skip or set()
    out: list[tuple[int, str, str, str]] = []
    for i, row in enumerate(rows, 1):
        if i in skip:
            continue
        for tok, h12 in sorted((row.get("src_sha256_12") or {}).items()):
            cand = _src_path(tok)
            if not cand.is_file():
                out.append((i, tok, h12, "DEAD"))
            else:
                try:
                    actual = hashlib.sha256(cand.read_bytes()).hexdigest()[:12]
                except OSError:
                    actual = "UNREADABLE"
                if actual != h12:
                    out.append((i, tok, h12, actual))
    return out


def verify() -> tuple[bool, str]:
    """v4 reader law: LINKAGE over the physical tape AND the ADMISSION
    summary. Contained defects (rows buried by an effective cross-signed void)
    are reported, not failed; uncontained defects FAIL exactly as v3 did."""
    rows = _rows()
    adm = _admission(rows)
    vk = adm["voided_keys"]
    prev = GENESIS
    notes: list[str] = []
    for i, row in enumerate(rows, 1):
        h = row.get("hash")
        contained = (h in vk) if isinstance(h, str) else (f"line:{i}" in vk)
        if not isinstance(h, str) or not _HEX64.match(h):
            if contained:
                notes.append(f"row {i}: hashless defect contained by void")
                continue
            return False, (f"row {i}: MALFORMED_ROW (missing/short hash — v4 "
                           f"refuses this at write; contain it: void --row #{i} "
                           "--reason-code MALFORMED)")
        if _row_hash(row) != h:
            return False, f"row {i}: hash mismatch (row edited in place)"
        p = row.get("prev")
        if p != prev:
            if contained:
                notes.append(f"row {i}: prev defect contained by void")
            elif _reanchor_ok(rows, i, p, adm):
                notes.append(f"row {i}: re-anchored past voided stretch")
            else:
                return False, f"row {i}: prev-hash mismatch (chain broken)"
        prev = h if isinstance(h, str) else prev
    skip = {i for i, r in enumerate(rows, 1)
            if (r.get("hash") in vk if isinstance(r.get("hash"), str)
                else f"line:{i}" in vk)}
    dead = _evidence_missing(rows, skip)
    mutated = _evidence_mutated(rows, skip)
    witnessed = sum(1 for r in rows
                    if r.get("verdict") == "SUPPORTED" and r.get("witness"))
    legacy_unwitnessed = sum(1 for r in rows
                             if r.get("verdict") == "SUPPORTED" and not r.get("witness"))
    msg = (f"LINKAGE-PASS: {len(rows)} posts intact, tip={prev[:12]} | "
           f"truth-gate: {witnessed} witnessed SUPPORTED, "
           f"{legacy_unwitnessed} legacy-unwitnessed")
    if notes:
        msg += " | " + "; ".join(notes[:6])
    st = adm["statuses"]
    msg += (" | ADMISSION: "
            f"{sum(1 for v in st.values() if v == 'VOID')} voided, "
            f"{sum(1 for v in st.values() if v == 'CONTESTED')} contested, "
            f"{sum(1 for v in st.values() if v == 'CORROBORATED')} corroborated, "
            f"{len(adm['pending_voids'])} pending voids, "
            f"{len(adm['propagation'])} propagation-flagged")
    if dead:
        msg += (" | EVIDENCE-MISSING " +
                ", ".join(f"row {i}:{tok}" for i, tok in dead[:6]))
        return False, msg
    if mutated:
        msg += (" | EVIDENCE-MUTATED " +
                ", ".join(f"row {i}:{tok}({want}!={got})"
                          for i, tok, want, got in mutated[:6]))
        return False, msg
    return True, msg


# --------------------------------------------------------------------- views
def render() -> str:
    rows = _rows()
    adm = _admission(rows)
    lines = ["# GROUNDING WAVE", "",
             "GROUND circuit ledger — one verified claim per post, hash-chained,",
             "tri-state only. Ladder (v4): RECORDED -> CORROBORATED -> CONTESTED",
             "-> VOID. Newer posts below. Ledger: `watch/GROUNDING_WAVE.jsonl`.", ""]
    for i, row in reversed(list(enumerate(rows, 1))):
        kind = row.get("kind", "claim")
        if kind in _ACT_KINDS:
            label = kind.upper()
            if kind == "void":
                body = f"voids `{str(row.get('voids', ''))[:12]}` ({row.get('reason_code')})"
            elif kind == "witness":
                c = row.get("checks", {})
                body = f"signs `{str(row.get('signs', ''))[:12]}` g1={c.get('g1')} g2={c.get('g2')} g3_exit={c.get('g3_exit')}"
            else:
                body = f"contests `{str(row.get('contests', ''))[:12]}`"
            lines.append(f"## {row.get('ts', '')} — {label} — {row.get('seat', 'v1-era')} [{adm['statuses'].get(i, '')}]")
            lines.append(f"- **act:** {body}")
        else:
            lines.append(f"## {row.get('ts', '')} — {row.get('verdict', 'UNLABELLED')} — {row.get('seat', 'v1-era')} [{adm['statuses'].get(i, 'RECORDED')}]")
            lines.append(f"- **claim:** {row.get('claim', '')}")
            lines.append(f"- **evidence:** {row.get('evidence', '')}")
            if row.get("note"):
                lines.append(f"- **note:** {row['note']}")
        lines.append(f"- hash `{str(row.get('hash', ''))[:12]}` ← prev `{str(row.get('prev', ''))[:12]}`")
        lines.append("")
    md = "\n".join(lines)
    VIEW_MD.write_text(md, encoding="utf-8")
    VIEW_STATIC.parent.mkdir(parents=True, exist_ok=True)
    VIEW_STATIC.write_text(md, encoding="utf-8")
    return md


def view() -> str:
    """Effective ledger (v4): the ladder status per row, acts, and propagation.
    Readers quote THIS, never bare PASS."""
    rows = _rows()
    adm = _admission(rows)
    lines = ["# GROUNDING WAVE — ADMISSION VIEW (v4)", "",
             "LADDER: RECORDED -> CORROBORATED -> CONTESTED -> VOID",
             "Readers quote this view, never bare linkage-PASS.",
             "Ledger: `watch/GROUNDING_WAVE.jsonl`.", "",
             "## effective ledger", ""]
    for i, r in enumerate(rows, 1):
        if r.get("kind") in _ACT_KINDS:
            continue
        st = adm["statuses"].get(i, "RECORDED")
        lines.append(f"#{i} {r.get('ts', '')} [{st}] "
                     f"({str(r.get('verdict', '?')).upper()}) "
                     f"seat={r.get('seat') or 'v1-era'} — "
                     f"{str(r.get('claim', ''))[:110]} `{str(r.get('hash', ''))[:12]}`")
    lines += ["", "## witnesses", ""]
    any_w = False
    for h, ws in sorted(adm["witnesses"].items()):
        for w in ws:
            any_w = True
            c = w.get("checks", {})
            lines.append(f"- {w.get('ts')} seat={w.get('seat')} signs `{str(h)[:12]}` "
                         f"g1={c.get('g1')} g2={c.get('g2')} g3_exit={c.get('g3_exit')} "
                         f"`{str(w.get('hash'))[:12]}`")
    if not any_w:
        lines.append("- (none)")
    lines += ["", "## voids", ""]
    if adm["effective_voids"]:
        for h, v in sorted(adm["effective_voids"].items()):
            lines.append(f"- VOID `{h[:12]}` reason_code={v.get('reason_code')} — "
                         f"{v.get('reason')} [cross-signed by {v.get('witness')}]")
    else:
        lines.append("- (none effective)")
    for h, v in sorted(adm["pending_voids"].items()):
        lines.append(f"- PENDING `{h[:12]}` reason_code={v.get('reason_code')} — "
                     f"awaiting witness row from seat {v.get('witness')!r}")
    lines += ["", "## contests", ""]
    if adm["contests"]:
        now = datetime.now(timezone.utc)
        for tkey, cs in sorted(adm["contests"].items()):
            for c in cs:
                stale = False
                try:
                    ts = datetime.strptime(c.get("ts", ""), "%Y-%m-%dT%H:%M:%SZ") \
                        .replace(tzinfo=timezone.utc)
                    stale = (now - ts).days >= STALE_CONTEST_DAYS
                except ValueError:
                    pass
                sustained = adm["statuses"].get(
                    next((j for j, r in enumerate(rows, 1)
                          if (r.get("hash") or f"line:{j}") == tkey), 0)) == "VOID"
                mark = "SUSTAINED" if sustained else ("STALE(>7d)" if stale else "pending")
                lines.append(f"- on `{str(tkey)[:12]}` by {c.get('seat')} [{mark}] — "
                             f"{c.get('reason')} `{str(c.get('hash'))[:12]}`")
    else:
        lines.append("- (none pending)")
    lines += ["", "## propagation (chain-visible descendants of VOID)", ""]
    if adm["propagation"]:
        for i, why in adm["propagation"]:
            lines.append(f"- row #{i} ({why}) — {rows[i - 1].get('ts', '')}")
    else:
        lines.append("- (none)")
    return "\n".join(lines) + "\n"


def resolve_ground_state(state_a: dict[str, Any], state_b: dict[str, Any], timestamp: str) -> dict[str, Any]:
    """Resolves conflicting ground states based on a deterministic strategy.

    For now, this is a placeholder. A robust strategy would involve:
    1. Prioritizing states with a second witness for 'SUPPORTED' verdicts.
    2. Considering the timestamp for recency in cases of 'UNPROVEN' or 'DISPUTED' states.
    3. A pre-defined hierarchy of 'seat' identities if necessary.
    """
    # Simple placeholder: if one is witnessed SUPPORTED, it wins. Otherwise, the newer one wins.
    if state_a.get("verdict") == "SUPPORTED" and state_a.get("witness"):
        return state_a
    if state_b.get("verdict") == "SUPPORTED" and state_b.get("witness"):
        return state_b

    # If neither is witnessed SUPPORTED, take the newer one
    if state_a.get("ts", "") > state_b.get("ts", ""):
        return state_a
    return state_b


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["post", "verify", "render", "view",
                                    "void", "contest", "witness"])
    ap.add_argument("--claim", default="")
    ap.add_argument("--verdict", default="SUPPORTED")
    ap.add_argument("--evidence", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--seat", default="zcode")
    ap.add_argument("--witness", default="",
                    help="second witness identity (required for SUPPORTED; "
                         "for void: the second seat whose signature counts)")
    ap.add_argument("--warrant", default="",
                    help="command that exits 0/1, hashed into the row (G3)")
    ap.add_argument("--row", default="",
                    help="target row: hash prefix or #N (1-based tape line)")
    ap.add_argument("--reason-code", default="", dest="reason_code",
                    help="one of " + "|".join(VOID_REASONS))
    ap.add_argument("--reason", default="")
    ap.add_argument("--dry", action="store_true",
                    help="show the row that would be appended; write nothing")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    try:
        if args.cmd == "post":
            row = post(args.claim, args.verdict, args.evidence, args.note,
                       args.seat, args.witness, args.warrant, dry=args.dry)
            ok, msg = verify()
            print(f"POSTED #{row['hash'][:12]} ({row.get('verdict')}) — {msg}")
        elif args.cmd == "void":
            row = void(args.row, args.reason_code, args.reason, args.seat,
                       args.evidence, args.witness, dry=args.dry)
            if not args.dry:
                ok, msg = verify()
                print(f"VOID POSTED #{row['hash'][:12]} (voids {str(row.get('voids'))[:12]}) — {msg}")
        elif args.cmd == "contest":
            row = contest(args.row, args.reason, args.seat, args.evidence, dry=args.dry)
            if not args.dry:
                ok, msg = verify()
                print(f"CONTEST POSTED #{row['hash'][:12]} — {msg}")
        elif args.cmd == "witness":
            row = witness(args.row, args.seat, dry=args.dry)
            if not args.dry:
                ok, msg = verify()
                print(f"WITNESS POSTED #{row['hash'][:12]} (signs {str(row.get('signs'))[:12]}) — {msg}")
        elif args.cmd == "verify":
            ok, msg = verify()
            print(("PASS " if ok else "FAIL ") + msg)
            sys.exit(0 if ok else 1)
        elif args.cmd == "view":
            print(view())
        elif args.cmd == "render":
            render()
            print(f"rendered {VIEW_MD.name} + {VIEW_STATIC.name}")
    except GateRefusal as e:
        print(f"REFUSED {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
