"""Orchestrator noise compaction for the session chain (card verkle99).

Spec: watch/inbox/ractor_panel_20260926/verkle99.final.md, landed with this
module (build discipline: spec before behavior change).

Folds chain rows whose session evidence is ALREADY GONE: orchestrator noise
sessions (`mag-agent-orc-*`, dominant_theme null, zero theme vector) whose
knot file is absent (the dangling definition chain_guard uses,
mag/chain_guard.py:72), into ONE counter leaf carrying the migration
anchor (pre-fold root + leaf count, archive sha256, Merkle root over every
folded leaf hash). Rows whose knot still exists are KEPT and REPORTED
(plan()["keep"]): deleting live evidence is a separate operator decision,
never a rider on this pass (the fossil-99 law: no silent partial coverage).
Placement precedent: mag/usage_digest.py (sibling writer importing the
chain's own private primitives).

LANDING GATE: this module ships plan-only: apply(execute=False) writes
NOTHING, no CLI flag is wired here. `--compact --execute` may be wired only
AFTER operator GO on Q-001 (roam verdict "needs-operator" stands) and with
tests/test_verkle_compaction.py (landed with this module) green.

V2 GUARD (2026-09-30, VERKLE_V2_DECISION.md §4 precondition 1): both plan()
and apply() READ chain_mode and refuse under v2 with exit 2 — compaction is
a chain rewriter and v2 rows are canonical append-only history; the fold is
a history destroyer until compaction learns v2 semantics (the same mirror
guard verkle_knot.consolidate already carries).
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

from mag import verkle_knot as vk

BIO = ROOT / "memory" / "biography"

NOISE_PREFIX = "mag-agent-orc-"
COUNTER_SESSION_ID = "mag-agent-orc-noise-counter-v1"
COUNTER_SCHEMA = "verkle_counter_leaf.v1"
COUNTER_TYPE = "orchestrator_noise_counter_leaf"
FOLDED_BY = "mag.verkle_compaction.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


V2_REFUSAL_REASON = (
    "chain_mode=v2: multiple rows per session are canonical append-only history "
    "(AH19 append-leaves, (session_id, session_seq) leaves that never unlink); "
    "compaction rewrites the chain dropping fold candidates and would destroy "
    "that history — refusing with exit 2 until compaction learns v2 semantics "
    "(mirror of verkle_knot.consolidate's v2 guard)"
)


def _v2_refusal() -> dict[str, Any] | None:
    """The v2 guard (VERKLE_V2_DECISION.md §2.1 / §4 precondition 1, 2026-09-30).

    Cause: this module REWRITES the chain dropping fold candidates — under
    chain_mode=v2 those rows are canonical history, so the fold is a history
    destroyer. Evidence it is fixed on: tests/test_verkle_compaction.py
    test_plan_and_apply_refuse_v2 (zero writes, exit 2, both entry points).
    Refusal carries the estate's hard-block exit code 2 (ratchet/census-patrol
    grammar: exit 2 = cannot run, never a soft skip) so any future CLI wrapper
    can pass it straight through.
    """
    if vk.chain_mode() != vk.CHAIN_MODE_V2:
        return None
    return {
        "ok": False,
        "refused": True,
        "exit": 2,
        "reason": V2_REFUSAL_REASON,
        "error": V2_REFUSAL_REASON,
        "chain_mode": vk.CHAIN_MODE_V2,
        "changed": False,
        "execute": False,
    }


def _in_noise_class(row: dict[str, Any]) -> bool:
    """Class membership: predicates 1-3 only (no dangling clause)."""
    if not str(row.get("session_id") or "").startswith(NOISE_PREFIX):
        return False
    if row.get("dominant_theme") is not None:
        return False
    v = row.get("theme_vector_normalized") or []
    if v and any(float(x) != 0.0 for x in v):
        return False
    return True


def is_fold_candidate(row: dict[str, Any], *, knots: Path | None = None) -> bool:
    """The deterministic fold predicate (byte-checked, order fixed): the noise
    class (orchestrator prefix per mag/tapestry.py:367-370 segmentation, null
    theme, zero theme energy) AND the knot file named by `filename` absent
    (evidence already gone). The truthy-filename requirement makes the counter
    itself immune: its filename is null, so it can never re-match
    (idempotence by shape).
    """
    knots = knots if knots is not None else vk.KNOTS
    fn = row.get("filename")
    return _in_noise_class(row) and bool(fn) and not (knots / str(fn)).is_file()


def plan(*, rows: list[dict[str, Any]] | None = None, knots: Path | None = None) -> dict[str, Any]:
    """Read-only fold plan over the current chain. Writes nothing.

    Reports BOTH dispositions of the noise class so partial coverage is
    visible, never silent: fold (knot gone) and keep_live_knot (knot still
    present, kept because its evidence is live).

    V2 REFUSAL: under chain_mode=v2 the plan itself is incoherent (its fold
    can never legally run), so plan() refuses with exit 2 before reading.
    """
    refusal = _v2_refusal()
    if refusal is not None:
        return refusal
    knots = knots if knots is not None else vk.KNOTS
    rows = rows if rows is not None else vk._load_chain_rows()
    hashes = [str(r.get("leaf_hash")) for r in rows if r.get("leaf_hash")]

    cand_idx = [i for i, r in enumerate(rows) if is_fold_candidate(r, knots=knots)]
    cand = [rows[i] for i in cand_idx]
    keep_live = [r for r in rows if _in_noise_class(r) and not is_fold_candidate(r, knots=knots)]

    folded_root = vk._merkle_root([str(r["leaf_hash"]) for r in cand]) if cand else None
    folded_list_sha = (
        hashlib.sha256("\n".join(str(r["leaf_hash"]) for r in cand).encode("utf-8")).hexdigest()
        if cand else None
    )
    pre_fold_root = vk._merkle_root(hashes) if hashes else None

    would_counter_hash = None
    would_root = pre_fold_root
    would_n = len(hashes)
    if cand:
        counter = _build_counter(
            cand, cand_idx, pre_fold_root=pre_fold_root or "", pre_fold_n=len(hashes),
            archived_chain_sha256="",  # not archived in plan mode; hash excludes it below
        )
        would_counter_hash = counter["leaf_hash"]
        kept_hashes = [h for i, h in enumerate(hashes) if i not in set(cand_idx)]
        kept_hashes[cand_idx[0]:cand_idx[0]] = [would_counter_hash]
        would_root = vk._merkle_root(kept_hashes)
        would_n = len(kept_hashes)

    return {
        "schema": "verkle_compaction_plan.v1",
        "ts": _now(),
        "n_rows": len(rows),
        "noise_class_total": len(cand) + len(keep_live),
        "fold": {
            "count": len(cand),
            "distinct_sessions": len({str(r.get("session_id")) for r in cand}),
            "flagged_evidence_lost": sum(1 for r in cand if r.get("evidence_lost")),
            "first_ts": str(cand[0].get("ts")) if cand else None,
            "last_ts": str(cand[-1].get("ts")) if cand else None,
        },
        "keep": {
            "count_live_knot": len(keep_live),
            "rationale": (
                "noise-class rows whose knot file is still present: evidence is live, "
                "not ballast; folding them is a second operator-gated decision "
                "(archive the knot files first), never a rider on pass 1"
            ),
        },
        "would_be_counter_leaf_hash": would_counter_hash,
        "would_be_counter_leaf_hash_note": (
            "computed with archived_chain_sha256=None: the plan-time hash; the "
            "execute-time counter hash differs because it embeds the real archive sha"
        ),
        "would_be_counter_session_id": COUNTER_SESSION_ID if cand else None,
        "would_be_root": would_root,
        "would_be_n_leaves": would_n,
        "folded_root_witness": folded_root,
        "folded_leaf_hashes_sha256": folded_list_sha,
        "pre_fold_root": pre_fold_root,
        "archive_root_dir": str((vk.CHAIN.parent / "compaction_archive")),
        "execute": False,
    }


def _build_counter(cand: list[dict[str, Any]], cand_idx: list[int], *,
                   pre_fold_root: str, pre_fold_n: int,
                   archived_chain_sha256: str) -> dict[str, Any]:
    """The counter leaf: a first-class leaf under the same _leaf_hash scheme."""
    folded_hashes = [str(r["leaf_hash"]) for r in cand]
    folded_root = vk._merkle_root(folded_hashes)
    folded_list_sha = hashlib.sha256("\n".join(folded_hashes).encode("utf-8")).hexdigest()
    now = _now()
    # ZERO-WIDTH window (start == end == first candidate's start_minute).
    # Cause: folded noise rows carry inherited zero-width minutes scattered
    # across weeks (live 2026-09-27: first start 2026-08-10T21:19Z, last end
    # 2026-09-11T23:23Z), so stitching cand[0].start -> cand[-1].end posed a
    # 32-DAY session window; the cache_map time-window join then re-attributed
    # 29,360 remote calls to "unmapped" (unmapped 913 -> 30,237 in the probe).
    # A tombstone must not pose as a session window; zero-width keeps only the
    # one minute the first noise row already occupied pre-fold. Evidence:
    # revise_verkle99_consumers_out.txt + the landed regression test
    # test_cache_map_theme_attribution_is_fold_invariant.
    tombstone_minute = cand[0].get("start_minute")
    counter: dict[str, Any] = {
        "ts": now,
        "type": COUNTER_TYPE,
        "schema": COUNTER_SCHEMA,
        "session_id": COUNTER_SESSION_ID,
        "filename": None,  # chain_guard's dangling check only counts truthy filenames (mag/chain_guard.py:72)
        "start_minute": tombstone_minute,
        "end_minute": tombstone_minute,
        "dominant_theme": None,
        "theme_vector_normalized": None,
        "tension_index": None,
        "dossier_commit": None,
        "amended": False,
        "count": len(cand),
        "session_prefix": NOISE_PREFIX,
        "folded_root": folded_root,
        "folded_leaf_hashes_sha256": folded_list_sha,
        "first_index": cand_idx[0],
        "last_index": cand_idx[-1],
        "first_ts": cand[0].get("ts"),
        "last_ts": cand[-1].get("ts"),
        "first_start_minute": cand[0].get("start_minute"),
        "last_end_minute": cand[-1].get("end_minute"),
        "pre_fold_root": pre_fold_root,
        "pre_fold_n_leaves": pre_fold_n,
        "archived_chain_sha256": archived_chain_sha256 or None,
        "folded_at": now,
        "folded_by": FOLDED_BY,
    }
    counter["leaf_hash"] = vk._leaf_hash(dict(counter))
    return counter


def apply(
    *,
    execute: bool = False,
    mark_guard: bool = True,
) -> dict[str, Any]:
    """Plan by default; with execute=True run the full migration under verkle_lock.

    Order (every step uses the estate's own primitives):
    v2 refusal (exit 2) -> preflight _verify_chain_consistent (refuse on
    fail) -> backup-first archive (chain+tip, sha256 recorded) -> fold
    (remove candidates, insert counter at the first candidate's position)
    -> _rewrite_chain (LF byte law built in) -> _write_tip_atomic ->
    evolution trim (consolidate precedent, mag/verkle_knot.py:379-397) ->
    chain_guard re-mark -> post-verify.
    """
    refusal = _v2_refusal()
    if refusal is not None:
        return refusal
    the_plan = plan()
    if not execute:
        return {"ok": True, "changed": False, "execute": False, "plan": the_plan}

    with vk.verkle_lock(timeout=60):
        ok, why = vk._verify_chain_consistent()
        if not ok:
            return {"ok": False, "refused": True, "error": f"preflight refused: {why}"}

        orig_bytes = vk.CHAIN.read_bytes()
        orig_rows = vk._load_chain_rows()
        orig_hashes = [str(r.get("leaf_hash")) for r in orig_rows if r.get("leaf_hash")]
        pre_fold_root = vk._merkle_root(orig_hashes)

        cand_idx = [i for i, r in enumerate(orig_rows) if is_fold_candidate(r)]
        if not cand_idx:
            return {"ok": True, "changed": False, "execute": True,
                    "reason": "0 fold candidates; nothing to do", "n_rows": len(orig_rows)}

        cand = [orig_rows[i] for i in cand_idx]

        # backup-first (mag/_flag_dangling_20260925.py:34-39 law): the pre-fold
        # chain is archived byte-exact BEFORE any write, sha256 recorded in the
        # counter leaf so the live chain carries the pointer to its own past.
        arch_root = vk.CHAIN.parent / "compaction_archive"
        arch_dir = arch_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        arch_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vk.CHAIN, arch_dir / "verkle_chain.jsonl")
        shutil.copy2(vk.TIP, arch_dir / "verkle_tip.json")
        arch_sha = hashlib.sha256((arch_dir / "verkle_chain.jsonl").read_bytes()).hexdigest()

        counter = _build_counter(
            cand, cand_idx, pre_fold_root=pre_fold_root, pre_fold_n=len(orig_hashes),
            archived_chain_sha256=arch_sha,
        )
        kept = [r for i, r in enumerate(orig_rows) if i not in set(cand_idx)]
        insert_at = min(cand_idx[0], len(kept))
        kept[insert_at:insert_at] = [counter]

        new_hashes = vk._rewrite_chain(kept)
        new_root = vk._merkle_root(new_hashes)
        tip = {
            "schema": "verkle_tip.v1",
            "root": new_root,
            "n_leaves": len(new_hashes),
            "last_filename": kept[-1].get("filename"),
            "last_leaf_hash": new_hashes[-1],
            "last_session_id": kept[-1].get("session_id"),
            "updated_minute": kept[-1].get("end_minute") or kept[-1].get("start_minute"),
            "note": (
                f"Noise compaction v1: folded {len(cand)} orchestrator noise leaves into 1 "
                f"counter leaf; pre_fold_root {pre_fold_root[:16]}; archive sha256 {arch_sha[:16]}"
            ),
        }
        vk._write_tip_atomic(tip)

        # evolution series: drop folded sids (consolidate precedent). A skip is
        # REPORTED in the result, never silent (the ratchet's except-pass law).
        evo_trim: dict[str, Any] = {"attempted": False}
        if vk.EVOLUTION.is_file():
            evo_trim["attempted"] = True
            try:
                evo = json.loads(vk.EVOLUTION.read_text(encoding="utf-8"))
                folded_sids = {str(r.get("session_id")) for r in cand}
                series = [s for s in (evo.get("series") or [])
                          if str(s.get("session_id")) not in folded_sids]
                for i, s in enumerate(series):
                    s["index"] = i
                evo["series"] = series
                evo["n_leaves"] = len(series)
                evo["verkle_root"] = new_root
                vk.EVOLUTION.write_text(json.dumps(evo, indent=2), encoding="utf-8")
                evo_trim["dropped"] = len(folded_sids)
                evo_trim["series_after"] = len(series)
            except (json.JSONDecodeError, OSError) as exc:
                evo_trim["skipped"] = f"{type(exc).__name__}: {exc}"

        # re-mark the canary with post-fold truth (the marker was already
        # stale pre-fold; the fold re-marks it, never hides the regression)
        guard_mark = None
        if mark_guard:
            from mag import chain_guard

            new_rows = vk._load_chain_rows()
            flagged_after = sum(1 for r in new_rows if r.get("evidence_lost"))
            guard_mark = chain_guard.mark(
                expected=flagged_after, root=new_root,
                note=(f"noise compaction v1 folded {len(cand)} -> 1 counter; "
                      f"pre_fold_root {pre_fold_root[:16]}; archive sha {arch_sha[:16]}"),
                by=FOLDED_BY,
            )

    # post-verify (outside the lock, read-only)
    ok2, why2 = vk._verify_chain_consistent()
    new_rows = vk._load_chain_rows()
    counter_index = next(
        (i for i, r in enumerate(new_rows) if r.get("session_id") == COUNTER_SESSION_ID), None
    )
    proof = vk.prove(counter_index) if counter_index is not None else {}
    anchor = verify_archive_anchor(arch_dir)

    return {
        "ok": bool(ok2 and proof.get("verified") and anchor.get("root_match")),
        "changed": True, "execute": True, "preflight": {"ok": ok, "why": why},
        "folded": len(cand), "folded_indexes": cand_idx, "kept_rows": len(new_rows),
        "bytes_before": len(orig_bytes), "bytes_after": len(vk.CHAIN.read_bytes()),
        "pre_fold_root": pre_fold_root, "new_root": new_root,
        "counter_leaf_hash": counter["leaf_hash"], "counter_index": counter_index,
        "archive_dir": str(arch_dir), "archived_chain_sha256": arch_sha,
        "post_verify": {"ok": ok2, "why": why2},
        "prove_counter": {k: proof.get(k) for k in ("verified", "index", "n_leaves", "root")},
        "archive_anchor": anchor, "evolution_trim": evo_trim, "guard_mark": guard_mark,
    }


def prove_archived_leaf(archive_dir: Path, folded_index: int) -> dict[str, Any]:
    """Prove ONE folded leaf against the archived pre-fold chain via vk.prove.

    The card's forever-provable claim, executable: swaps vk.CHAIN to the
    archive (restored in finally), runs the estate's own prover at the folded
    row's ORIGINAL index, and checks the proof's root equals both the archive
    root and the pre_fold_root the live counter leaf commits to.
    """
    archive_dir = Path(archive_dir)
    chain_file = archive_dir / "verkle_chain.jsonl"
    old_chain = vk.CHAIN
    proof: dict[str, Any] = {}
    try:
        vk.CHAIN = chain_file
        proof = vk.prove(folded_index)
    finally:
        vk.CHAIN = old_chain
    arch_rows = [json.loads(l) for l in chain_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    arch_hashes = [str(r.get("leaf_hash")) for r in arch_rows if r.get("leaf_hash")]
    return {
        "ok": bool(proof.get("verified")),
        "index": proof.get("index"),
        "verified": proof.get("verified"),
        "leaf_hash": proof.get("leaf_hash"),
        "proof_root": proof.get("root"),
        "archived_root": vk._merkle_root(arch_hashes),
        "archived_chain_sha256": hashlib.sha256(chain_file.read_bytes()).hexdigest(),
        "root_matches_archive": proof.get("root") == vk._merkle_root(arch_hashes),
        "leaf_hash_is_archived_row": (
            folded_index < len(arch_hashes) and arch_hashes[folded_index] == proof.get("leaf_hash")
        ),
    }


def verify_archive_anchor(archive_dir: Path) -> dict[str, Any]:
    """Recompute the archive's root + sha256 and match the live counter leaf.

    The folded-root witness is recomputed the same way the fold computed it:
    re-run the predicate over the ARCHIVE rows (the pre-fold chain) and take
    their leaf hashes in chain order.
    """
    archive_dir = Path(archive_dir)
    chain_file = archive_dir / "verkle_chain.jsonl"
    arch_rows = [json.loads(l) for l in chain_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    arch_hashes = [str(r.get("leaf_hash")) for r in arch_rows if r.get("leaf_hash")]
    arch_root = vk._merkle_root(arch_hashes)
    arch_sha = hashlib.sha256(chain_file.read_bytes()).hexdigest()
    folded = [r for r in arch_rows if is_fold_candidate(r)]
    folded_root_recomputed = vk._merkle_root([str(r["leaf_hash"]) for r in folded]) if folded else None
    counter = next(
        (r for r in vk._load_chain_rows() if r.get("session_id") == COUNTER_SESSION_ID), None
    )
    if counter is None:
        return {"ok": False, "error": "counter leaf not found in live chain",
                "archived_root": arch_root, "archived_chain_sha256": arch_sha}
    return {
        "ok": (arch_root == counter.get("pre_fold_root")
               and arch_sha == counter.get("archived_chain_sha256")
               and folded_root_recomputed == counter.get("folded_root")),
        "archived_root": arch_root,
        "counter_pre_fold_root": counter.get("pre_fold_root"),
        "root_match": arch_root == counter.get("pre_fold_root"),
        "archived_chain_sha256": arch_sha,
        "counter_archived_chain_sha256": counter.get("archived_chain_sha256"),
        "sha_match": arch_sha == counter.get("archived_chain_sha256"),
        "folded_root_recomputed": folded_root_recomputed,
        "counter_folded_root": counter.get("folded_root"),
        "folded_root_match": folded_root_recomputed == counter.get("folded_root"),
        "folded_count_recomputed": len(folded),
        "counter_count": counter.get("count"),
    }
