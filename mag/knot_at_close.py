"""knot_at_close — the bridge: ended CLI-db sessions get knotted into the verkle chain.

W1 finding (2026-09-06, memory/runs/batch5_20260906/ORPHAN_LEDGER_20260906.md): chain
knots index the cage stream, not the CLI session db — 51/65 24h sessions ended with no
chain row. CURRENT.md critique: "knot-at-close bridge owed." This organ IS the bridge.

Modes:
  (default)  REPORT — read-only: list ended (>GRACE_H) sessions with no chain row.
  --backfill — BACKUP chain + knots dir first (backup-first law), build minimal honest
             dossiers from the db (read-only sqlite), append each via
             verkle_knot.append_verkle_knot under its single-writer lock, verify the
             chain after, write a receipt to watch/KNOT_AT_CLOSE_<date>.json.

Honesty: themes are NOT fabricated — dominant_theme is the backfilled title slug and
the theme vector is zeros (unmeasured), carried inside the signed leaf so no later
reader mistakes backfill for measurement. Provenance rides in chord.framework_root
(the STRIKE_ROOT) + chord.commitment_hash (marker string). Secrets are redacted from
excerpts. The db opens mode=ro, always.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mag import verkle_knot as vk  # noqa: E402

DB = Path.home() / ".zcode" / "cli" / "db" / "db.sqlite"
GRACE_H = 2.0
REDACT = re.compile(r"(sk-[A-Za-z0-9_-]{8,}|[A-Za-z0-9_-]*key[=: ][A-Za-z0-9_-]{12,})", re.I)


def _iso_min(epoch_ms: int) -> tuple[str, str, str]:
    d = dt.datetime.fromtimestamp(epoch_ms / 1000, tz=dt.timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M"), str(int(d.timestamp() // 60)), d.strftime("%Y-%m-%d")


def _slug(title: str | None) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "untitled").lower()).strip("-")
    return ("backfill-" + s[:38]) if s else "backfill-untitled"


def _seed_session(session_id: str) -> str | None:
    """ARC-SEED HOOK (salon verdict 09-07, watch/ARC_SEED_DEFAULT_SALON_20260907.md):
    compile the recovery seed for a closed session — read-only on the rollout,
    idempotent (arc-root-addressed filenames), silent-fail (a missing rollout
    never blocks the close). Returns the arc root, or None."""
    try:
        from mag import arc_seed as ar
        rollout = Path.home() / ".zcode" / "cli" / "rollout" / f"model-io-sess_{session_id}.jsonl"
        if not rollout.is_file():
            return None
        turns = ar.parse_rollout(rollout)
        if not turns:
            return None
        a = ar.anatomy(turns)
        root = a.get("arc_root") or "noroot"
        ar.OUT.mkdir(parents=True, exist_ok=True)
        (ar.OUT / f"arc_chain_{session_id[:13]}_{root}.json").write_text(
            json.dumps({"schema": "arc_seed.v1", "session": session_id, "anatomy": a,
                        "turns": turns}, indent=1, default=str), encoding="utf-8")
        (ar.OUT / f"arc_seed_{session_id[:13]}_{root}.md").write_text(
            ar.seed_skeleton(turns, session_id), encoding="utf-8")
        return root
    except Exception:  # noqa: BLE001 — seed, not break
        return None


def _worldline_seed_hook(session_id: str) -> None:
    """W1 DEATH RITE v2 (watch/WORLDLINE_SEED_20260907.md): after the knot, emit
    THE WORLDLINE SEED for the closing session. Fail-open: any failure prints one
    warning line and never blocks the close."""
    try:
        from mag import worldline_seed as ws
        ws.emit(session_id)
    except Exception as exc:  # noqa: BLE001 — a seed never blocks a close
        print(f"  worldline-seed WARN emit failed for {session_id[:8]}: {str(exc)[:120]}")


def _chain_session_ids() -> set[str]:
    out: set[str] = set()
    if vk.CHAIN.is_file():
        for line in vk.CHAIN.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                sid = json.loads(line).get("session_id")
            except Exception:
                continue
            if sid:
                out.add(str(sid).replace("sess_", "").strip())
    return out


def _db_rows(conn: sqlite3.Connection, cutoff_ms: int) -> list[dict]:
    rows: list[dict] = []
    cur = conn.execute(
        "SELECT id, title, time_created, time_updated FROM session "
        "WHERE time_updated < ? ORDER BY time_updated ASC",
        (cutoff_ms,),
    )
    for sid, title, tc, tu in cur.fetchall():
        if tc is None or tu is None:
            continue  # untimeable rows are not knotable honestly
        n_msgs = 0
        first_user = ""
        try:
            n_msgs = conn.execute("SELECT COUNT(*) FROM message WHERE session_id = ?", (sid,)).fetchone()[0]
            r = conn.execute(
                "SELECT content FROM message WHERE session_id = ? AND is_sidechain = 0 "
                "ORDER BY time_created ASC LIMIT 1",
                (sid,),
            ).fetchone()
            if r and r[0]:
                first_user = REDACT.sub("[redacted]", str(r[0]))[:160]
        except sqlite3.OperationalError:
            pass
        rows.append(
            {
                "session_id": str(sid).replace("sess_", "").strip(),
                "title": title or "",
                "created_ms": int(tc),
                "updated_ms": int(tu),
                "n_msgs": int(n_msgs),
                "first_user_excerpt": first_user,
            }
        )
    return rows


def _dossier(r: dict) -> dict:
    c_iso, c_um, c_date = _iso_min(r["created_ms"])
    u_iso, u_um, _ = _iso_min(r["updated_ms"])
    body = json.dumps(
        {
            "title": r["title"],
            "n_msgs": r["n_msgs"],
            "first": r["first_user_excerpt"],
            "window": [r["created_ms"], r["updated_ms"]],
        },
        sort_keys=True,
    )
    n_basis = len(vk.THEME_BASIS)
    return {
        "session_id": r["session_id"],
        "title": r["title"],
        "time": {
            "created_at": {"iso_minute": c_iso, "unix_minute": c_um, "date": c_date},
            "updated_at": {"iso_minute": u_iso, "unix_minute": u_um, "date": c_date},
        },
        "scalar_knot": {
            "duration_minutes": round((r["updated_ms"] - r["created_ms"]) / 60000.0, 1),
            "theme_vector": {
                "dominant": _slug(r["title"]),
                "basis": list(vk.THEME_BASIS),
                "raw": [0.0] * n_basis,
                "normalized": [0.0] * n_basis,
            },
            "tension_index": None,
            "residual_weight": None,
            "Q_proxy": None,
            "gap_proxy": None,
            "lambda2_proxy": None,
            "dirichlet_energy_proxy": None,
        },
        "content_commit": {"hex": hashlib.sha256(body.encode()).hexdigest()[:16]},
        "chord": {
            "commitment_hash": "knot_at_close_backfill.v1",
            "framework_root": "e11937d605a89b022d137cceae495f5c521dbbff35cd60e23189e53172cb66b5",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="backup + append knots (default: report only)")
    ap.add_argument("--seed-sweep", action="store_true",
                    help="compile recovery seeds for ended sessions (night-shift backfill pass; no chain writes)")
    ap.add_argument("--limit", type=int, default=0, help="cap appends this run")
    ap.add_argument("--skip-knot-backup", action="store_true",
                    help="trust an existing chain .bak and skip the knots-dir tar (appends never modify existing knot files)")
    args = ap.parse_args()

    if not DB.is_file():
        print(f"NO DB at {DB}")
        return 2
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    cutoff_ms = int((dt.datetime.now(dt.timezone.utc).timestamp() - GRACE_H * 3600) * 1000)
    have = _chain_session_ids()
    rows = [r for r in _db_rows(conn, cutoff_ms) if r["session_id"] not in have]
    conn.close()

    print(f"chain rows with session ids: {len(have)}")
    print(f"ended >{GRACE_H}h with no chain row: {len(rows)}")
    for r in rows[:15]:
        print(f"  {r['session_id'][:8]} {dt.datetime.fromtimestamp(r['updated_ms']/1000, dt.timezone.utc):%m-%d %H:%M}Z {r['n_msgs']:>4} msgs  {r['title'][:60]}")
    if len(rows) > 15:
        print(f"  ... +{len(rows) - 15} more")

    if args.seed_sweep:
        seeded, skipped = 0, 0
        for r in rows:
            root = _seed_session(r["session_id"])
            if root:
                seeded += 1
                print(f"  seed {r['session_id'][:8]} -> {root}")
            else:
                skipped += 1
        print(f"SEED SWEEP: {seeded} seeded, {skipped} skipped (no rollout or already seeded)")
        return 0

    if not args.backfill:
        print("REPORT ONLY (pass --backfill to close them)")
        return 0

    # backup-first
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    chain_bak = vk.CHAIN.with_suffix(".jsonl.bak-orphanlane-" + stamp)
    shutil.copy2(vk.CHAIN, chain_bak)
    knots_bak: Path | None = None
    if not args.skip_knot_backup:
        knots_bak = vk.KNOTS.with_name("knots.bak-orphanlane-" + stamp + ".tar")
        import tarfile

        with tarfile.open(knots_bak, "w") as tf:
            for f in vk.KNOTS.glob("*.knot.json"):
                tf.add(f, arcname=f.name)
    n_before = sum(1 for _ in vk.CHAIN.open(encoding="utf-8"))
    print(f"BACKUP: {chain_bak.name} + {knots_bak.name if knots_bak else 'skipped (chain .bak is the backup)'} ({n_before} chain rows)")

    todo = rows[: args.limit] if args.limit else rows
    ok, failed = 0, []
    for r in todo:
        try:
            res = vk.append_verkle_knot(_dossier(r))
            ok += 1
            _seed_session(r["session_id"])  # arc-seed hook: recovery seed rides the knot (silent-fail)
            _worldline_seed_hook(r["session_id"])  # W1 death rite v2: worldline seed (fail-open)
        except Exception as exc:  # noqa: BLE001
            failed.append({"session_id": r["session_id"], "error": str(exc)[:200]})
    n_after = sum(1 for _ in vk.CHAIN.open(encoding="utf-8"))

    # verify: prove the tip
    try:
        proof = vk.prove(None)
        v_ok = bool(proof.get("ok", proof.get("valid", True)))
    except Exception as exc:  # noqa: BLE001
        proof, v_ok = {"error": str(exc)[:200]}, False

    receipt = {
        "schema": "knot_at_close.v1",
        "when": stamp,
        "backfilled": ok,
        "failed": failed,
        "chain_rows": [n_before, n_after],
        "backup_chain": str(chain_bak),
        "backup_knots": str(knots_bak),
        "tip_proof_ok": v_ok,
        "tip_proof": {k: proof.get(k) for k in ("index", "root", "leaf_hash") if k in proof},
        "standard": f"ended >{GRACE_H}h, no chain row; themes unmeasured=zeros; secrets redacted; db read-only",
    }
    out = ROOT / "watch" / f"KNOT_AT_CLOSE_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("backfilled", "failed", "chain_rows", "tip_proof_ok")}, indent=2))
    print(f"receipt: {out.name}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
