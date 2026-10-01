"""Daily improve loop: scout → candidates → eval → promote (gated).

Files are truth under memory/improve/. No auto ollama pull by default.
Opt-in deep dive: improve --deep (research-pack + local worker, wall budget).

Spec (t33, 2026-09-25): `improve --status` is the seat surface for the
MagImproveDaily silent-disablement probe. status_summary() embeds
mag.doctor.check_scheduled_tasks() (t20's check, reused via import, no
duplicate schtasks call) and prints ONE WARNING line on stderr when the
task is not Ready. lifecycle.py prescribes the landed t73 executor
"python main.py improve-off --reason ... / improve-on" as the remediation
(aligned by t77, hint by t81), so deliberate disablement is a known
state: it must be announced at the seat, not only at doctor time.

Spec (B2-106, 2026-09-26): provider-health cadence. Lane state used to be
measured only during burn waves (B2-04 morning scoreboard vs the
afternoon mistral 429-zero-quota -> 403-wrong-default flip), so between
waves the estate guessed. The scout now owns the cadence: the FIRST
non-dry scout() that finds the cadence stale (state key
"last_provider_probe" older than configs/improve.yaml
provider_probe.cadence_days, default 7) runs mag.doctor
.check_provider_endpoints() under MAG_PROBE_REMOTE=1, the B2-04 deep
probe (ONE one-token ping per deduped (base_url, model, key) triple,
~15 pings on this estate, measured classes QUOTA-DEAD / AUTH-DEAD /
DEGRADED / FENCED / REMOTE-UNVERIFIED). The env opt-in is set for the
call and restored after; it never leaks into a plain shell. The run
lands a snapshot JSON under memory/improve/provider_health/<day>.json
and ONE improve candidate (kind=risk when alarm classes fire, kind=runtime
when all quiet, status=hold when quiet: a healthy week is evidence, not a
ticket). dry scout never probes; disabled config never probes. The
digest day is page-scrape-free, not probe-free: a due probe runs on the
digest path too, and the digest report note names the exception.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from config import CONFIGS_DIR, ROOT

SCHEMA = "improve_candidate.v1"
CFG_PATH = CONFIGS_DIR / "improve.yaml"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _day_str(dt: datetime | None = None) -> str:
    return (dt or _utc_now()).strftime("%Y-%m-%d")


def load_config() -> dict[str, Any]:
    if not CFG_PATH.is_file():
        # FAIL LOUD (gala wave5-repair config-hygiene lane, 2026-09-29): a
        # missing configs/improve.yaml used to read as {"enabled": False} and
        # the scout went dark with rc=0 (f-03 finding 5,
        # watch/inbox/burn_reset_20260927/flash50/f-03.md). Deliberate
        # disablement is the t73 executor's named act: improve-off writes the
        # marker logs/magimprove_intentional.flag (mag/lifecycle.py IMPROVE_
        # INTENTIONAL_FLAG) and never touches this file, so a missing config
        # is a broken install, not an off state. Name the path instead of
        # impersonating a sanctioned disabled state.
        raise FileNotFoundError(
            f"improve config missing: {CFG_PATH} (configs/improve.yaml is "
            "git-tracked; restore it from git, and route deliberate "
            "disablement through 'python main.py improve-off --reason ...')"
        )
    data = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8")) or {}
    data.setdefault("budgets", {})
    data.setdefault("sources", {})
    data.setdefault("paths", {})
    data.setdefault("rotation", {})
    data.setdefault("tier_a_always", [])
    data.setdefault("allowlists", {})
    data.setdefault("eval", {})
    data.setdefault("promote", {})
    data.setdefault("max_auto_pull_gb", 0)
    return data


def _paths(cfg: dict[str, Any]) -> dict[str, Path]:
    p = cfg.get("paths") or {}
    root = ROOT / (p.get("root") or "memory/improve")
    return {
        "root": root,
        "candidates": ROOT / (p.get("candidates") or "memory/improve/candidates.jsonl"),
        "daily": ROOT / (p.get("daily") or "memory/improve/daily"),
        "evals": ROOT / (p.get("evals") or "memory/improve/evals"),
        "playbook": ROOT / (p.get("playbook") or "memory/improve/playbook.md"),
        "state": ROOT / (p.get("state") or "memory/improve/state.json"),
    }


def ensure_dirs(cfg: dict[str, Any] | None = None) -> dict[str, Path]:
    cfg = cfg or load_config()
    paths = _paths(cfg)
    for k in ("root", "daily", "evals"):
        paths[k].mkdir(parents=True, exist_ok=True)
    paths["candidates"].parent.mkdir(parents=True, exist_ok=True)
    if not paths["playbook"].is_file():
        paths["playbook"].write_text(
            "# Mag improve playbook\n\n"
            "Practices auto-drafted from scout (review weekly).\n"
            "Model seat changes require `python main.py promote --apply <id>`.\n\n",
            encoding="utf-8",
        )
    return paths


def _load_state(paths: dict[str, Path]) -> dict[str, Any]:
    if paths["state"].is_file():
        try:
            return json.loads(paths["state"].read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(paths: dict[str, Path], state: dict[str, Any]) -> None:
    paths["state"].write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def _candidate_id(claim: str, url: str) -> str:
    h = hashlib.sha256(f"{claim}|{url}".encode()).hexdigest()[:12]
    return f"c-{h}"


def read_candidates(paths: dict[str, Path] | None = None, limit: int = 500) -> list[dict[str, Any]]:
    paths = paths or ensure_dirs()
    p = paths["candidates"]
    if not p.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows[-limit:]


def append_candidates(rows: list[dict[str, Any]], paths: dict[str, Path]) -> int:
    if not rows:
        return 0
    existing = {r.get("id") for r in read_candidates(paths, limit=5000)}
    n = 0
    with paths["candidates"].open("a", encoding="utf-8") as f:
        for r in rows:
            if r.get("id") in existing:
                continue
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            existing.add(r.get("id"))
            n += 1
    return n


def update_candidate_status(
    cid: str, status: str, note: str = "", extra: dict[str, Any] | None = None
) -> bool:
    """Rewrite ledger line for cid (small file OK)."""
    paths = ensure_dirs()
    rows = read_candidates(paths, limit=10000)
    found = False
    for r in rows:
        if r.get("id") == cid:
            r["status"] = status
            r["updated"] = _utc_now().isoformat()
            if note:
                r["note"] = note
            if extra:
                r.update(extra)
            found = True
    if not found:
        return False
    with paths["candidates"].open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return True


def _weekday_keys(cfg: dict[str, Any], dt: datetime | None = None) -> list[str]:
    dt = dt or _utc_now()
    # Monday=0
    wd = dt.weekday()
    rotation = cfg.get("rotation") or {}
    # yaml may load int keys as int
    day_keys = rotation.get(wd) or rotation.get(str(wd)) or []
    always = list(cfg.get("tier_a_always") or [])
    if "digest" in day_keys and len(day_keys) == 1:
        return ["digest", "mag_internal"]
    if "catchup" in day_keys:
        return list(dict.fromkeys(always + ["catchup"] + [k for k in day_keys if k != "catchup"]))
    return list(dict.fromkeys(always + list(day_keys)))


def _select_urls(cfg: dict[str, Any], source_keys: list[str]) -> list[dict[str, Any]]:
    """Return list of {source, url, kind_hint, feed?} up to budgets."""
    budgets = cfg.get("budgets") or {}
    max_urls = int(budgets.get("urls_per_day") or 10)
    sources = cfg.get("sources") or {}
    out: list[dict[str, Any]] = []
    for key in source_keys:
        src = sources.get(key) or {}
        if src.get("local_only"):
            continue
        kind = src.get("kind_hint") or "practice"
        for u in src.get("urls") or []:
            out.append({"source": key, "url": u, "kind_hint": kind})
        for feed in src.get("feeds") or []:
            out.append({"source": key, "url": feed, "kind_hint": kind, "is_feed": True})
    # named profiles on demand only if in allowlist and operator added — skip daily auto unless present
    for u in (cfg.get("allowlists") or {}).get("named_profiles") or []:
        out.append({"source": "named", "url": u, "kind_hint": "paper"})
    return out[:max_urls]


def _fetch_page(url: str) -> dict[str, Any]:
    from mag.research_pack import _fetch_url

    return _fetch_url(url, timeout=20.0)


def _parse_rss(text: str, max_items: int = 15) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    try:
        root = ET.fromstring(text)
    except Exception:
        return items
    # RSS 2.0 or Atom
    for item in root.iter():
        tag = item.tag.split("}")[-1].lower() if "}" in item.tag else item.tag.lower()
        if tag not in ("item", "entry"):
            continue
        title = ""
        link = ""
        summary = ""
        for child in item:
            ct = child.tag.split("}")[-1].lower() if "}" in child.tag else child.tag.lower()
            if ct == "title" and child.text:
                title = (child.text or "").strip()
            elif ct == "link":
                if child.text:
                    link = child.text.strip()
                elif child.get("href"):
                    link = child.get("href", "")
            elif ct in ("description", "summary", "content") and child.text:
                summary = re.sub(r"<[^>]+>", " ", child.text or "")
                summary = re.sub(r"\s+", " ", summary).strip()[:500]
        if title:
            items.append({"title": title, "link": link, "summary": summary})
        if len(items) >= max_items:
            break
    return items


_MODEL_RE = re.compile(
    r"\b(gemma[-\s]?4|qwen3(?:\.5)?|glm-?[45]|kimi[-\s]?k2|minimax|deepseek|llama[-\s]?4|"
    r"mistral|devstral|codestral|phi-?\d|nomic-embed)\b",
    re.I,
)
_PRACTICE_RE = re.compile(
    r"\b(best practice|eval harness|agent harness|multi-agent|tool call|memory|"
    r"context|observability|RAG|MCP|orchestrat|process reward|test-time|"
    r"continual learning|plan search|self-teach|skill bead|value function)\b",
    re.I,
)


def _local_feasible_guess(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(405b|480b|671b|1\.?1t|trillion)\b", t):
        return "false"
    if re.search(r"\b(7b|8b|9b|12b|13b|14b|27b|26b|31b|32b|35b|70b)\b", t):
        return "true"
    if "ollama" in t or "gguf" in t or "local" in t:
        return "unknown"
    return "unknown"


def _candidates_from_fetch(
    *,
    source: str,
    url: str,
    kind_hint: str,
    text: str,
    is_feed: bool,
    max_arxiv: int,
) -> list[dict[str, Any]]:
    day = _day_str()
    rows: list[dict[str, Any]] = []
    text = (text or "")[:60000]

    if is_feed or "arxiv.org" in url or url.endswith(".xml") or "rss" in url.lower():
        for it in _parse_rss(text, max_items=max_arxiv):
            claim = f"arXiv/rss: {it['title']}"
            link = it.get("link") or url
            cid = _candidate_id(claim, link)
            rows.append(
                {
                    "schema": SCHEMA,
                    "id": cid,
                    "date": day,
                    "kind": "paper",
                    "claim": claim,
                    "detail": it.get("summary") or "",
                    "source": source,
                    "source_urls": [link, url],
                    "local_feasible": "false",
                    "status": "new",
                    "created": _utc_now().isoformat(),
                }
            )
        return rows

    # Page scrape → one source candidate + keyword hits
    title_line = ""
    for ln in text.splitlines():
        ln = ln.strip()
        if len(ln) > 20:
            title_line = ln[:200]
            break
    host = urlparse(url).netloc
    base_claim = f"[{source}] {title_line or host}"
    rows.append(
        {
            "schema": SCHEMA,
            "id": _candidate_id(base_claim, url),
            "date": day,
            "kind": kind_hint,
            "claim": base_claim,
            "detail": text[:400].replace("\n", " "),
            "source": source,
            "source_urls": [url],
            "local_feasible": _local_feasible_guess(text[:2000]),
            "status": "new",
            "created": _utc_now().isoformat(),
        }
    )

    # Model name hits → separate model candidates
    seen_models: set[str] = set()
    for m in _MODEL_RE.findall(text[:15000]):
        key = m.lower().replace(" ", "")
        if key in seen_models:
            continue
        seen_models.add(key)
        claim = f"Model signal: {m} (via {host})"
        rows.append(
            {
                "schema": SCHEMA,
                "id": _candidate_id(claim, url + key),
                "date": day,
                "kind": "model",
                "claim": claim,
                "detail": f"Mentioned on {url}",
                "source": source,
                "source_urls": [url],
                "local_feasible": _local_feasible_guess(m + " " + text[:500]),
                # lessig bare model signal: architecture rejects noise at birth
                "status": "rejected",
                "note": "auto-reject bare Model signal (tesuji leaf required)",
                "created": _utc_now().isoformat(),
            }
        )
        if len(seen_models) >= 5:
            break

    if _PRACTICE_RE.search(text[:8000]) and kind_hint != "practice":
        claim = f"Practice signal on {host}: harness/eval/memory themes"
        rows.append(
            {
                "schema": SCHEMA,
                "id": _candidate_id(claim, url),
                "date": day,
                "kind": "practice",
                "claim": claim,
                "detail": text[:300].replace("\n", " "),
                "source": source,
                "source_urls": [url],
                "local_feasible": "true",
                "status": "new",
                "created": _utc_now().isoformat(),
            }
        )
    return rows


# B2-106 provider-health cadence. state key + config block shape; the
# cadence default mirrors the weekly review habit the playbook already
# names ("review weekly"), config wins.
_PROVIDER_PROBE_STATE_KEY = "last_provider_probe"
ATTENTION_PATH = ROOT / "memory" / "attention.md"  # B2-494 alarm surface
_PROVIDER_PROBE_DIRNAME = "provider_health"
_PROVIDER_PROBE_DEFAULT_CADENCE_DAYS = 7.0


def provider_probe_due(
    state: dict[str, Any] | None,
    cadence_days: float = _PROVIDER_PROBE_DEFAULT_CADENCE_DAYS,
    *,
    now: datetime | None = None,
) -> bool:
    """Cadence gate for the weekly deep provider probe (B2-106).

    Contract (pinned by tests/test_improve_provider_probe.py): due when the
    state key is missing, empty, or unparseable (a broken clock must not
    silence the probe forever: an unreadable ts re-arms the cadence), or
    when now - ts >= cadence_days. A fresh ts inside the window is not due.
    cadence_days <= 0 means always due (operator knob, not a footgun).
    """
    raw = ""
    try:
        raw = str((state or {}).get(_PROVIDER_PROBE_STATE_KEY) or "")
    except Exception:
        raw = ""
    if not raw:
        return True
    try:
        last = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    now_dt = now or _utc_now()
    return (now_dt - last).total_seconds() >= max(float(cadence_days), 0.0) * 86400.0


def run_provider_probe(
    cfg: dict[str, Any],
    paths: dict[str, Path],
    *,
    day: str | None = None,
    now: datetime | None = None,
    probe_fn: Any = None,
) -> dict[str, Any] | None:
    """Run the B2-04 deep provider probe when the cadence is stale (B2-106).

    Returns None when config disables it, the cadence is fresh, or the
    caller is only previewing (probe_fn injected without a run is still a
    run: tests inject probe_fn and drive the gate via state/config).
    On run: sets MAG_PROBE_REMOTE=1 for the duration and restores the
    prior value after (the env opt-in never leaks past this function),
    calls mag.doctor.check_provider_endpoints() (deep probe dedupes
    (base_url, model, key) triples itself: ~15 one-token pings, never
    per-lane fan-out), writes memory/improve/provider_health/<day>.json,
    appends ONE improve candidate, and stamps the state key. Alarm
    classes (DOWN / QUOTA-DEAD / AUTH-DEAD) make it kind=risk status=new;
    a quiet week is kind=runtime status=hold (evidence, not a ticket).
    """
    pcfg = cfg.get("provider_probe") or {}
    if pcfg.get("enabled") is False:
        return None
    cadence = float(pcfg.get("cadence_days") or _PROVIDER_PROBE_DEFAULT_CADENCE_DAYS)
    state = _load_state(paths)
    if not provider_probe_due(state, cadence, now=now):
        return None
    if probe_fn is None:
        from mag.doctor import check_provider_endpoints as probe_fn  # noqa: N813

    prior = os.environ.get("MAG_PROBE_REMOTE")
    try:
        os.environ["MAG_PROBE_REMOTE"] = "1"
        result = probe_fn()
    finally:
        if prior is None:
            os.environ.pop("MAG_PROBE_REMOTE", None)
        else:
            os.environ["MAG_PROBE_REMOTE"] = prior

    day = day or _day_str()
    statuses = dict(result.get("statuses") or {})
    issues = list(result.get("issues") or [])
    alarms = bool(issues) or not bool(result.get("ok"))
    worst_bits: list[str] = []
    for cls in ("DOWN", "QUOTA-DEAD", "AUTH-DEAD"):
        hit = sorted(p for p, s in statuses.items() if s == cls)
        if hit:
            worst_bits.append("%s %s" % (cls, ",".join(hit)))
    if not worst_bits:
        for cls in ("DEGRADED", "FENCED"):
            hit = sorted(p for p, s in statuses.items() if s == cls)
            if hit:
                worst_bits.append("%s %s" % (cls, ",".join(hit)))
    worst = "; ".join(worst_bits)
    claim = (
        "Provider probe (cadence %.0fd): %d probes, %d alarm issues, %d degraded, "
        "%d fenced" % (
            cadence,
            int(result.get("probes_run") or 0),
            len(issues),
            len(result.get("degraded") or []),
            len(result.get("fenced") or []),
        )
    ) + ("; " + worst if worst else "")
    detail = " ".join("%s=%s" % (p, s) for p, s in sorted(statuses.items()))
    row = {
        "schema": SCHEMA,
        "id": _candidate_id(claim, day + ":provider_probe"),
        "date": day,
        "kind": "risk" if alarms else "runtime",
        "claim": claim,
        "detail": detail[:600],
        "source": "mag_internal",
        "source_urls": ["memory/improve/%s/%s.json" % (_PROVIDER_PROBE_DIRNAME, day)],
        "local_feasible": "true",
        "status": "new" if alarms else "hold",
        "created": _utc_now().isoformat(),
    }

    out_dir = paths["root"] / _PROVIDER_PROBE_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)
    snap = out_dir / ("%s.json" % day)
    snap.write_text(
        json.dumps({"day": day, "ts": _utc_now().isoformat(), "result": result}, default=str, indent=2),
        encoding="utf-8",
    )
    try:
        snap_ref = str(snap.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        # Isolated callers (tests, alt roots): the absolute path is the honest ref.
        snap_ref = str(snap).replace("\\", "/")
    row["source_urls"] = [snap_ref]

    append_candidates([row], paths)
    # B2-494 (2026-09-26): the alarm surface. Alarm-class probe results no
    # longer stop at the candidates ledger: the run appends EXACTLY ONE
    # [priority] line to memory/attention.md naming the lane, the alarm
    # classes and the snapshot ref. Chosen path: attention.md (the doctor
    # issue surface stays silent here; two alarm mouths is the fan-out
    # disease). A quiet run writes nothing.
    if alarms:
        try:
            with ATTENTION_PATH.open("a", encoding="utf-8") as f:
                f.write("- [priority][probe-alarm] provider_probe %s (run %s) -> %s"
                        % (worst or ("issues:%d" % len(issues)), day, snap_ref) + "\n")
        except OSError:
            pass  # the probe result still lands; the surface write is best-effort
    state[_PROVIDER_PROBE_STATE_KEY] = _utc_now().isoformat()
    state["last_provider_probe_summary"] = {
        "day": day,
        "probes_run": int(result.get("probes_run") or 0),
        "alarms": len(issues),
        "degraded": len(result.get("degraded") or []),
        "fenced": len(result.get("fenced") or []),
        "snapshot": snap_ref,
    }
    _save_state(paths, state)
    return {"row": row, "result": result, "snapshot": str(snap)}


def _provider_probe_extra(
    provider_probe: dict[str, Any] | None,
    *,
    note: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Daily-report extra + scout return payload for the cadence probe (B2-106)."""
    out: dict[str, Any] = dict(extra or {})
    if note:
        out["note"] = note
    if provider_probe:
        res = provider_probe.get("result") or {}
        row = provider_probe.get("row") or {}
        out["provider_probe"] = {
            "probes_run": res.get("probes_run"),
            "alarms": len(res.get("issues") or []),
            "row_id": row.get("id"),
            "claim": (row.get("claim") or "")[:200],
            "snapshot": provider_probe.get("snapshot"),
        }
    return out


def _mag_internal_candidates(day: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    smoke = ROOT / "logs" / "multi_smoke_latest.json"
    if smoke.is_file():
        try:
            data = json.loads(smoke.read_text(encoding="utf-8"))
            ok = data.get("ok")
            claim = f"Internal multi-smoke last: {'PASS' if ok else 'FAIL'}"
            rows.append(
                {
                    "schema": SCHEMA,
                    "id": _candidate_id(claim, str(smoke)),
                    "date": day,
                    "kind": "risk" if not ok else "runtime",
                    "claim": claim,
                    "detail": (data.get("verdict") or "")[:300],
                    "source": "mag_internal",
                    "source_urls": [str(smoke)],
                    "local_feasible": "true",
                    "status": "new" if not ok else "hold",
                    "created": _utc_now().isoformat(),
                }
            )
        except Exception as e:
            rows.append(
                {
                    "schema": SCHEMA,
                    "id": _candidate_id("smoke-read-err", str(e)),
                    "date": day,
                    "kind": "risk",
                    "claim": f"Could not read multi_smoke_latest: {e}",
                    "source": "mag_internal",
                    "source_urls": [],
                    "local_feasible": "true",
                    "status": "new",
                    "created": _utc_now().isoformat(),
                }
            )
    working = ROOT / "memory" / "working.md"
    if working.is_file():
        claim = "Review memory/working.md open loops (internal)"
        rows.append(
            {
                "schema": SCHEMA,
                "id": _candidate_id(claim, str(working)),
                "date": day,
                "kind": "practice",
                "claim": claim,
                "detail": working.read_text(encoding="utf-8", errors="replace")[:400],
                "source": "mag_internal",
                "source_urls": [str(working)],
                "local_feasible": "true",
                "status": "hold",
                "created": _utc_now().isoformat(),
            }
        )
    # IJL-v0: skill beads + dig pack are daily upgrade surface (not second ritual)
    skills_dir = ROOT / "memory" / "improve" / "pins" / "skills"
    n_skills = 0
    if skills_dir.is_dir():
        n_skills = len(list(skills_dir.glob("*.json")))
    claim_ijl = f"IJL skill beads on disk: n={n_skills}"
    rows.append(
        {
            "schema": SCHEMA,
            "id": _candidate_id(claim_ijl, str(skills_dir)),
            "date": day,
            "kind": "runtime" if n_skills else "practice",
            "claim": claim_ijl,
            "detail": (
                "Internal Judge Loop: successful graph runs FILE beads under "
                "memory/improve/pins/skills/; context-pack LOADs them. "
                + (
                    "Use one assigned dig/code goal this week to mint/refresh beads."
                    if n_skills < 3
                    else "Skim newest bead; reject thrash antiskills in weekly review."
                )
            ),
            "source": "mag_internal",
            "source_urls": [str(skills_dir)],
            "local_feasible": "true",
            "status": "new" if n_skills < 3 else "hold",
            "created": _utc_now().isoformat(),
        }
    )
    dig_pack = ROOT / "memory" / "research_packs" / "20260728_ssi_ilya_dig" / "REPORT.md"
    if dig_pack.is_file():
        claim_dig = "IJL/P0 dig pack still active — FEATURE_COMPOSE only, hypothesis quarantine"
        rows.append(
            {
                "schema": SCHEMA,
                "id": _candidate_id(claim_dig, str(dig_pack)),
                "date": day,
                "kind": "practice",
                "claim": claim_dig,
                "detail": (
                    "Do not promote SSI reverse-engineer. Steal open contracts only. "
                    "Leaf: evals/features/p0-sector-plansearch-gcrm-2026-07-28.md"
                ),
                "source": "mag_internal",
                "source_urls": [str(dig_pack)],
                "local_feasible": "true",
                "status": "hold",
                "created": _utc_now().isoformat(),
            }
        )
    # Behavioral-error awareness: mine behavioral leaves + decisions log +
    # seat crash log so the overseeing agent learns from recurring seat errors.
    rows.extend(_behavioral_candidates(day))
    rows.extend(_tesuji_shell_candidates(day))
    return rows


# B2-357 counting-contract constants for logs/seat_crashes.log. One guard
# stanza per crash: a "[<iso-utc>] stage=<stage>" line written by
# mag.agent_cli._log_seat_crash followed by the formatted traceback body.
_CRASH_STANZA_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2}T[^\]]*\]", re.MULTILINE)
_CRASH_MARKER_RE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_.]*: ?)?INJECTED-")
_CRASH_HEADER = "Traceback (most recent call last):"
# B2-372: the two sentences CPython prints between chained traceback
# sections; their count is how the census says "this entry was a chain".
_CRASH_CHAIN_MARKERS = (
    "During handling of the above exception",
    "The above exception was the direct cause",
)
# B2-383: counted only at column 0 (CPython prints each sentence on its own
# line between chained sections) and only in stanzas holding 2+ headers (a
# chain link needs two sections), so a body that merely QUOTES a sentence
# mid-message, after a type prefix, in an indented source echo, or alone on
# a multi-line message line never counts as a chain.
_CRASH_CHAIN_MARKER_RE = re.compile(
    "^(?:" + "|".join(re.escape(marker) for marker in _CRASH_CHAIN_MARKERS) + ")",
    re.MULTILINE,
)


def crash_log_census(text: str) -> dict[str, int]:
    """Count seat crashes in logs/seat_crashes.log by ENTRY, not by substring.

    Contract (pinned by tests/test_improve_crash_scout.py, B2-357):
      - The log is a sequence of guard stanzas, each one
        "[<iso-utc>] stage=<stage>" line (mag.agent_cli._log_seat_crash)
        plus its traceback body; bytes before the first stanza are preamble.
      - blocks: total "Traceback (most recent call last):" headers inside
        stanza bodies (kept for continuity with the old "guard caught N
        total" phrasing).
      - entries: stanza bodies containing at least one header. ONE chained
        exception prints two headers inside one stanza and is ONE crash,
        so header counting booked it twice.
      - test: entries whose body has a line STARTING with an INJECTED-
        marker (bare, or "TypeName: INJECTED-...", the shape the guard-era
        tests wrote). The B2-86 annotation suffix rides inside marker lines
        after the message, so start-anchored matching still sees annotated
        markers, while an operator traceback that merely QUOTES the literal
        mid-message never reclassifies a real crash as test.
      - real: entries - test.
      - chains: total chain links over the same bodies blocks and entries
        count: lines STARTING at column 0 with one of the two exception-
        chain-marker sentences ("During handling of the above exception" /
        "The above exception was the direct cause"), counted only in
        stanzas holding at least two headers, one per chained join, so
        real=1 chains=1 names a wrap-and-reraise crash without opening the
        log (B2-372; the scout row detail carries chains=). B2-383: a body
        that merely QUOTES a marker sentence mid-message, after a type
        prefix, inside an indented source echo, or alone on a line of a
        multi-line message never counts, because CPython prints each
        sentence at column 0 between two sections and a chain link needs
        two headers.
    A body with headers but no stanza line still counts as one entry
    (defensive: never drop a real crash over a mangled stanza line).
    Cause: the old real = headers - INJECTED- string count turned one
    chained real crash quoting the marker into real=0 and one unquoted
    chained real crash into real=2 (probe:
    watch/inbox/burn_wave_20260926/B2_357_falsifier_probe.py; receipt
    watch/inbox/burn_wave_20260926/B2_357_scout_pin_20260926.md). The
    chains field exists because that entry-level census still could not SAY
    a crash was chained (falsifier and receipt:
    watch/inbox/burn_wave_20260926/B2_372_chain_census_20260926.md; red-run
    artifact watch/inbox/burn_wave_20260926/B2_372_red_run_20260926.txt).
    B2-383: the B2-372 chains count was itself a plain substring count, so
    an operator crash quoting a chain-marker sentence mid-message inflated
    chains with entries and real unchanged (red-run artifact and receipt:
    watch/inbox/burn_wave_20260926/B2_383_chain_quote_pin_20260926.md).
    B2-416 OUT-OF-SCOPE NOTE (2026-09-26): crash evidence that never passed
    through the _log_seat_crash writer seam is out of scope by decision, so
    stanza-less traceback bodies on disk are NOT owned by this census and
    this note is their registration. Sweep of watch/inbox on 2026-09-26:
    7 files / 16 "Traceback (most recent call last):" headers; 1 file / 6
    headers carry the "[<iso-utc>] stage=" stanza (in scope); 6 files /
    10 headers are stanza-less, of which 3 files / 5 headers are QUOTED
    text (QUEUE.md brief rows, B2_373 and B2_86 receipts) and 3 files /
    5 headers are real captured crash output from other writers
    (gala b2-stone2b.check.txt, t33.check.txt, dogfood-trajectory save.txt).
    Stronger gap, same decision: pytest-report-shaped crash evidence has no
    header at all, so even a stanza-less header sweep cannot see it
    (gala t39.check.txt carries 4 column-0 chain-marker sentences and 8
    PermissionError lines in E-line summary shape with zero headers).
    If a lane later wants these classes counted, that is a NEW writer or a
    NEW reader contract, not an edit here; this census stays
    stanza-scoped (receipt:
    watch/inbox/burn_wave_20260926/B2_416_stanza_census_20260926.md).
    """
    if not text:
        return {"blocks": 0, "entries": 0, "test": 0, "real": 0, "chains": 0}
    starts = [m.start() for m in _CRASH_STANZA_RE.finditer(text)]
    if not starts:
        bodies = [text]
    else:
        bounds = starts + [len(text)]
        bodies = [text[bounds[i]: bounds[i + 1]] for i in range(len(starts))]
    blocks = entries = test = chains = 0
    for body in bodies:
        if _CRASH_HEADER not in body:
            continue
        entries += 1
        blocks += body.count(_CRASH_HEADER)
        if body.count(_CRASH_HEADER) >= 2:
            # B2-418: between-headers placement. CPython prints each chain
            # sentence at column 0 BETWEEN two sections, so a real join line
            # sits strictly after the first and before the last header of the
            # stanza. A quoted sentence embedded in the FINAL exception
            # message lands after the last header and must not count (the
            # B2-383 column-0 rule alone still let a 2-header stanza with a
            # quoted marker in its tail message report a phantom second
            # link; fixture test_quoted_marker_at_end_of_two_header_stanza_
            # counts_one_join, red chains=2 before this fix).
            lines = body.splitlines()
            header_idx = [i for i, ln in enumerate(lines) if _CRASH_HEADER in ln]
            lo, hi = header_idx[0], header_idx[-1]
            chains += sum(
                1 for i in range(lo + 1, hi)
                if _CRASH_CHAIN_MARKER_RE.match(lines[i])
            )
        for line in body.splitlines()[1:]:
            if _CRASH_MARKER_RE.match(line):
                test += 1
                break
    return {
        "blocks": blocks,
        "entries": entries,
        "test": test,
        "real": entries - test,
        "chains": chains,
    }


# B2-374: the behavioral-events scout has always counted the tail of
# logs/behavioral_events.jsonl as the LAST 80 raw lines; pinned as a named
# constant so the window arithmetic is contract, not implication.
_BEHAVIORAL_TAIL = 80


def behavioral_events_census(text: str, window: int = _BEHAVIORAL_TAIL) -> dict[str, Any]:
    """Count behavioral events by ROW over the scout's tail window.

    Contract (pinned by tests/test_improve_behavioral_scout.py, B2-374):
      - text is a behavioral_events.jsonl dump; the window is the LAST
        `window` raw lines. Blank and unparseable lines consume window
        slots exactly as the pre-B2-374 scout did, so today's live
        census equals the old math's.
      - events: window lines whose json.loads succeeds AND that parse to
        a JSON object. ONE line is ONE row; nothing else becomes an
        event.
      - kinds: per counted row, str(row.get("kind") or "event"); the
        "kind" FIELD only. A detail, error, or any other field never
        adds to a count even when it quotes a counted kind literal.
      - samples: the first 5 counted rows as "kind:detail[:80]", kept
        for continuity with the old row detail.
    Cause: the old scout counted kinds with this same field rule but
    emitted the census tokens and the samples into ONE string, so a row
    whose detail quoted a counted kind literal (a digest row reading
    "tool_fail=12 collapse=3") printed phantom census tokens for kinds
    the census never counted, with no test able to tell census from
    prose inside the emitted line. The scout row detail now separates
    them on a " samples: " marker so the census section carries exactly
    the counted kinds (falsifier and receipt:
    watch/inbox/burn_wave_20260926/B2_374_behavioral_pin_20260926.md;
    pre-fix red run and probe output beside it). Delta on old math: one
    non-dict JSON row used to raise inside the block and the outer
    except silently dropped the WHOLE behavioral row; the census skips
    that row and keeps the rest (never drop real events over one
    mangled row, the B2-357 defensive stance).
    """
    lines = text.splitlines()[-window:] if window > 0 else []
    kinds: dict[str, int] = {}
    samples: list[str] = []
    events = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        events += 1
        k = str(ev.get("kind") or "event")
        kinds[k] = kinds.get(k, 0) + 1
        if len(samples) < 5:
            samples.append(f"{k}:{str(ev.get('detail') or '')[:80]}")
    return {"events": events, "kinds": kinds, "samples": samples}


def _behavioral_candidates(day: str) -> list[dict[str, Any]]:
    """Mine behavioral-analysis leaves + decisions log + seat crash log so the
    overseeing agent learns from recurring seat errors (steering, collapse,
    crash-guard, repack silence, etc.).

    Sources:
      - memory/improve/daily/*-behavioral.md  (themes T1..Tn, root causes, avoids)
      - memory/decisions_log.jsonl            (steer case law incl. operator complaints)
      - logs/seat_crashes.log                 (seat crash traces)
    Each becomes an improve_candidate (kind=risk) that the scout/eval/promote
    pipeline ranks automatically.
    """
    rows: list[dict[str, Any]] = []

    # 1) Behavioral-analysis leaves (memory/improve/daily/*-behavioral.md)
    daily_dir = ROOT / "memory" / "improve" / "daily"
    if daily_dir.is_dir():
        for leaf in sorted(daily_dir.glob("*-behavioral.md")):
            try:
                text = leaf.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # Extract theme headers (## T1 — ...) and their root-cause lines
            themes: list[str] = []
            for m in re.finditer(r"^#{2,3}\s+(T\d+)\s*[—\-–]\s*(.+)$", text, re.M):
                themes.append(f"{m.group(1)}: {m.group(2).strip()}")
            if not themes:
                continue
            claim = f"Behavioral leaf {leaf.stem}: {len(themes)} recurring seat-error themes"
            detail = "; ".join(themes[:6])
            rows.append(
                {
                    "schema": SCHEMA,
                    "id": _candidate_id(claim, str(leaf)),
                    "date": day,
                    "kind": "risk",
                    "claim": claim,
                    "detail": detail[:600],
                    "source": "mag_internal",
                    "source_urls": [str(leaf)],
                    "local_feasible": "true",
                    "status": "new",
                    "created": _utc_now().isoformat(),
                }
            )

    # 2) Decisions log (steer case law — operator complaints + outcomes)
    dec_log = ROOT / "memory" / "decisions_log.jsonl"
    if dec_log.is_file():
        steer_entries: list[str] = []
        try:
            for line in dec_log.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                # Operator-visible complaints / steer inputs that indicate a failure
                ctx = (d.get("context") or "") + " " + (d.get("steer_input") or "")
                low = ctx.lower()
                if any(k in low for k in ("doesn't work", "doesn't work", "not working",
                                           "doesn't respond", "chugging", "broken",
                                           "can't", "cannot", "failed", "error",
                                           "doesn't work at all", "ing doesn't work")):
                    steer_entries.append(
                        f"{d.get('timestamp', '')}: {ctx[:200]} -> {d.get('outcome', '')[:200]}"
                    )
        except Exception:
            pass
        if steer_entries:
            claim = f"Decisions log: {len(steer_entries)} operator-visible failure steers"
            rows.append(
                {
                    "schema": SCHEMA,
                    "id": _candidate_id(claim, str(dec_log)),
                    "date": day,
                    "kind": "risk",
                    "claim": claim,
                    "detail": "; ".join(steer_entries[:5])[:600],
                    "source": "mag_internal",
                    "source_urls": [str(dec_log)],
                    "local_feasible": "true",
                    "status": "new",
                    "created": _utc_now().isoformat(),
                }
            )

    # 3) Seat crash log (tracebacks, crash-guard caught, learn from them).
    crash_log = ROOT / "logs" / "seat_crashes.log"
    if crash_log.is_file():
        try:
            crash_text = crash_log.read_text(encoding="utf-8", errors="replace")
        except Exception:
            crash_text = ""
        # B2-357: entry-level census (contract on crash_log_census above);
        # the old headers-minus-INJECTED- string count booked a chained
        # crash's two headers twice and silently reclassified a real crash
        # whose message quotes the INJECTED- literal mid-line. B2-372: the
        # detail names chains= so a wrap-and-reraise class is visible
        # without opening the log.
        census = crash_log_census(crash_text)
        blocks, n_test, real = census["blocks"], census["test"], census["real"]
        if blocks:
            claim = (
                f"Seat crash log: real={real} crash entries "
                f"(census blocks={blocks} test={n_test} real={real}; "
                f"guard caught {blocks} total)"
            )
            rows.append(
                {
                    "schema": SCHEMA,
                    "id": _candidate_id(claim, str(crash_log)),
                    "date": day,
                    "kind": "risk",
                    "claim": claim,
                    "detail": (
                        f"census blocks={blocks} test={n_test} real={real} "
                        f"entries={census['entries']} chains={census['chains']}. "
                        "Guard holding; review newest traceback for recurrence."
                    ),
                    "source": "mag_internal",
                    "source_urls": [str(crash_log)],
                    "local_feasible": "true",
                    "status": "new" if real else "hold",
                    "created": _utc_now().isoformat(),
                }
            )

    # 4) Live behavioral events (tool_fail, collapse, degenerate etc. from
    # the operator_inbox feed). B2-374: row-level census (contract on
    # behavioral_events_census above); the old emission poured the census
    # kind tokens and the free-form samples into one string, so a row
    # whose detail quoted a counted kind literal printed phantom census
    # tokens for kinds never counted, and one non-dict JSON row silently
    # dropped the whole row via the outer except.
    ev_path = ROOT / "logs" / "behavioral_events.jsonl"
    if ev_path.is_file():
        try:
            ev_text = ev_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            ev_text = ""
        census = behavioral_events_census(ev_text)
        events = census["events"]
        if events:
            kinds = census["kinds"]
            # FIX 2026-09-26 (B2-420, spec-first relabel). CAUSE: the claim
            # hardcoded "{events} recent seat errors" while the pinned census
            # counts EVERY tail row kind; the live tail-80 was 70 pro_fire +
            # 5 cloud_handoff + 5 improve_cycle (pure lifecycle) yet the row
            # claimed 80 seat errors, and the promote pipeline read it as a
            # risk signal. EVIDENCE: the falsifier state in
            # watch/inbox/burn_wave_20260926/B2_420_census_seat_errors_20260926.md.
            # FIX: kinds are classified error-vs-lifecycle by marker (error,
            # fail, crash, exception, case-insensitive, on the kind FIELD the
            # pinned census counts); the "seat errors" number is now the
            # error-kind count, the full census naming stays in claim and
            # detail, and a zero-error tail demotes the row kind from "risk"
            # to "census" so lifecycle chatter stops flagging risk.
            error_kinds = {
                k: v for k, v in kinds.items()
                if any(m in k.lower() for m in ("error", "fail", "crash", "exception"))
            }
            error_events = sum(error_kinds.values())
            claim = (
                f"Behavioral events log: {error_events} recent seat errors "
                f"of {events} behavioral rows (census events={events} "
                f"error_kind_events={error_events} kinds={len(kinds)})"
            )
            rows.append(
                {
                    "schema": SCHEMA,
                    "id": _candidate_id(claim, str(ev_path)),
                    "date": day,
                    "kind": "risk" if error_events else "census",
                    "claim": claim,
                    "detail": (
                        f"census events={events} error_kind_events={error_events} "
                        f"error_kinds={sorted(error_kinds)} kinds={len(kinds)} "
                        + " ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
                        + " samples: "
                        + "; ".join(census["samples"])
                    ),
                    "source": "mag_internal",
                    "source_urls": [str(ev_path)],
                    "local_feasible": "true",
                    "status": "new",
                    "created": _utc_now().isoformat(),
                }
            )

    # 5) Failure KB recurring signatures (deduped tool/collapse patterns)
    try:
        from mag.failure_kb import recurring_patterns

        for rec in recurring_patterns(min_count=3)[:5]:
            cnt = int(rec.get("count") or 0)
            tool_s = str(rec.get("tool") or "?")
            claim = f"FKB recurring: {tool_s} ×{cnt} ({rec.get('sig', '')[:20]})"
            rows.append(
                {
                    "schema": SCHEMA,
                    "id": _candidate_id(claim, str(rec.get("sig") or "")),
                    "date": day,
                    "kind": "risk",
                    "claim": claim,
                    "detail": (
                        f"error={str(rec.get('error_sample') or '')[:80]}; "
                        f"detail={str(rec.get('detail_sample') or '')[:80]}; "
                        f"remedy={rec.get('remedy_id') or 'none'}"
                    ),
                    "source": "mag_internal",
                    "source_urls": ["memory/failure_kb/signatures.json"],
                    "local_feasible": "true",
                    "status": "new",
                    "created": _utc_now().isoformat(),
                }
            )
    except Exception:
        pass

    return rows


def _tesuji_shell_candidates(day: str) -> list[dict[str, Any]]:
    """Mine tesuji-shell leaves + live log — emergent wins compete with error themes."""
    rows: list[dict[str, Any]] = []

    daily_dir = ROOT / "memory" / "improve" / "daily"
    if daily_dir.is_dir():
        for leaf in sorted(daily_dir.glob("*-tesuji-shells.md")):
            try:
                text = leaf.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            wins: list[str] = []
            for m in re.finditer(r"^#{2,3}\s+(W\d+)\s*[—\-–]\s*(.+)$", text, re.M):
                wins.append(f"{m.group(1)}: {m.group(2).strip()}")
            if not wins or (len(wins) == 1 and wins[0].startswith("W0:")):
                continue
            claim = f"Tesuji shells leaf {leaf.stem}: {len(wins)} emergent wins"
            detail = "; ".join(wins[:6])
            rows.append(
                {
                    "schema": SCHEMA,
                    "id": _candidate_id(claim, str(leaf)),
                    "date": day,
                    "kind": "tesuji",
                    "claim": claim,
                    "detail": detail[:600],
                    "source": "mag_internal",
                    "source_urls": [str(leaf)],
                    "local_feasible": "true",
                    "status": "new",
                    "created": _utc_now().isoformat(),
                }
            )

    shells_path = ROOT / "logs" / "tesuji_shells.jsonl"
    if shells_path.is_file():
        try:
            samples: list[str] = []
            maps: dict[str, int] = {}
            for line in shells_path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]:
                if not line.strip():
                    continue
                try:
                    sh = json.loads(line)
                except json.JSONDecodeError:
                    continue
                mt = str(sh.get("maps_to") or "")
                if mt:
                    maps[mt] = maps.get(mt, 0) + 1
                if len(samples) < 4:
                    samples.append(str(sh.get("what") or "")[:80])
            if samples:
                claim = f"Tesuji shells log: {len(samples)}+ recent emergent wins"
                map_s = "; ".join(f"{k}×{v}" for k, v in sorted(maps.items(), key=lambda x: -x[1])[:4])
                rows.append(
                    {
                        "schema": SCHEMA,
                        "id": _candidate_id(claim, str(shells_path)),
                        "date": day,
                        "kind": "tesuji",
                        "claim": claim,
                        "detail": (" · ".join(samples) + (f" · maps: {map_s}" if map_s else ""))[:600],
                        "source": "mag_internal",
                        "source_urls": [str(shells_path)],
                        "local_feasible": "true",
                        "status": "new",
                        "created": _utc_now().isoformat(),
                    }
                )
        except Exception:
            pass

    return rows


def scout(*, dry: bool = False) -> dict[str, Any]:
    cfg = load_config()
    if not cfg.get("enabled", True):
        return {"ok": False, "error": "improve disabled in configs/improve.yaml"}
    paths = ensure_dirs(cfg)
    day = _day_str()
    behavioral_leaf = None
    tesuji_leaf = None
    if not dry:
        try:
            from mag.behavioral_synth import synthesize_behavioral_leaf

            behavioral_leaf = synthesize_behavioral_leaf(day)
        except Exception:
            behavioral_leaf = None
        try:
            from mag.tesuji_shell import synthesize_tesuji_shell_leaf

            tesuji_leaf = synthesize_tesuji_shell_leaf(day)
        except Exception:
            tesuji_leaf = None
    keys = _weekday_keys(cfg)
    budgets = cfg.get("budgets") or {}
    max_cand = int(budgets.get("candidates_per_day") or 25)
    max_arxiv = int(budgets.get("arxiv_abstracts") or 15)

    # B2-106 provider-health cadence: the first non-dry scout that finds the
    # cadence stale measures lane state (~15 one-token pings, deduped).
    # dry scout never probes. Digest day is page-scrape-free, not probe-free.
    provider_probe = None
    if not dry:
        provider_probe = run_provider_probe(cfg, paths, day=day)

    if "digest" in keys and keys == ["digest", "mag_internal"] or keys == ["digest"]:
        # Sunday-style: internal only
        rows = _mag_internal_candidates(day)
        land_rows = rows[:max_cand]
        if provider_probe:
            land_rows.append(provider_probe["row"])
        written = 0 if dry else append_candidates(land_rows, paths)
        report = _write_daily_report(
            paths,
            day,
            phase="scout-digest",
            source_keys=keys,
            fetches=[],
            candidates_added=written,
            candidates_sample=land_rows[:8],
            extra=_provider_probe_extra(provider_probe, note="Digest day — no outbound scrape"),
        )
        return {
            "ok": True,
            "day": day,
            "mode": "digest",
            "source_keys": keys,
            "candidates_added": written,
            "provider_probe": _provider_probe_extra(provider_probe).get("provider_probe"),
            "report": str(report),
        }

    targets = _select_urls(cfg, keys)
    fetches: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []

    # Always internal snapshot
    all_rows.extend(_mag_internal_candidates(day))
    if provider_probe:
        all_rows.append(provider_probe["row"])

    if "catchup" in keys:
        # Re-list sources that previously failed
        state = _load_state(paths)
        for fail_url in (state.get("failed_urls") or [])[:5]:
            targets.append(
                {"source": "catchup", "url": fail_url, "kind_hint": "risk", "is_feed": False}
            )

    failed: list[str] = []
    for t in targets:
        url = t["url"]
        is_feed = bool(t.get("is_feed"))
        if dry:
            fetches.append({"url": url, "source": t["source"], "dry": True})
            continue
        res = _fetch_page(url)
        ok = bool(res.get("ok"))
        text = res.get("text") or ""
        fetches.append(
            {
                "url": url,
                "source": t["source"],
                "ok": ok,
                "status_code": res.get("status_code"),
                "chars": len(text),
                "error": res.get("error"),
            }
        )
        if not ok or not text.strip():
            failed.append(url)
            continue
        all_rows.extend(
            _candidates_from_fetch(
                source=t["source"],
                url=url,
                kind_hint=t.get("kind_hint") or "practice",
                text=text,
                is_feed=is_feed or "rss.arxiv" in url,
                max_arxiv=max_arxiv,
            )
        )

    # Cap
    all_rows = all_rows[:max_cand]
    # B2-106: the probe row rides past the cap; health evidence is not a
    # scrape candidate to be budgeted away.
    if provider_probe and not any(r is provider_probe["row"] for r in all_rows):
        all_rows.append(provider_probe["row"])
    written = 0 if dry else append_candidates(all_rows, paths)

    # Mine arXiv the same way we steal: route novel arXiv findings through the ONE primitive
    # (route_novel -> swarm) so frontier seats mine them, dedupe by anchor, and fold. Always-on.
    if not dry and any(
        "arxiv" in str(t.get("source") or "") or "arxiv.org" in str(t.get("url") or "")
        for t in targets
    ):
        try:
            from mag import arxiv_mine

            arxiv_mine.route_candidates(all_rows, max_papers=max_arxiv)
        except Exception:
            pass

    # Promote practices draft
    promo = cfg.get("promote") or {}
    if not dry and promo.get("auto_append_practices_to_playbook", True):
        _append_practices_to_playbook(paths, [r for r in all_rows if r.get("kind") == "practice"])

    state = _load_state(paths)
    state["last_scout"] = _utc_now().isoformat()
    state["last_day"] = day
    state["failed_urls"] = failed[-20:]
    state["last_source_keys"] = keys
    if not dry:
        _save_state(paths, state)

    report = _write_daily_report(
        paths,
        day,
        phase="scout",
        source_keys=keys,
        fetches=fetches,
        candidates_added=written,
        candidates_sample=all_rows[:12],
        extra=_provider_probe_extra(provider_probe, extra={"failed_urls": failed} if failed else None),
    )
    return {
        "ok": True,
        "day": day,
        "mode": "scout",
        "source_keys": keys,
        "urls_tried": len(fetches),
        "fetches_ok": sum(1 for f in fetches if f.get("ok")),
        "candidates_added": written,
        "failed": failed,
        "provider_probe": _provider_probe_extra(provider_probe).get("provider_probe"),
        "report": str(report),
        "dry": dry,
    }


def _mirror_lens_gate_enabled() -> bool:
    raw = os.environ.get("MAG_MIRROR_LENS_GATE", "").strip().lower()
    if not raw:
        return True
    return raw in ("1", "true", "yes", "on")


def _mentions_local_fork(blob: str) -> bool:
    if any(t in blob for t in ("local-first", "local first", "ollama")):
        return True
    if re.search(r"without\s+fork", blob):
        return False
    return bool(re.search(r"\bfork\b", blob))


def _mirror_lens_verdict(candidate: dict[str, Any]) -> tuple[str, str]:
    if not _mirror_lens_gate_enabled():
        return "pass", "mirror lens gate disabled"
    claim = str(candidate.get("claim") or "")
    detail = str(candidate.get("detail") or "")
    tags = {str(t).lower() for t in (candidate.get("tags") or [])}
    blob = f"{claim} {detail}".lower()
    for pat in (r"single oracle", r"remote-only", r"remote only", r"hide(s)? (the )?cost", r"greenwash"):
        if re.search(pat, blob):
            return "reject", f"mirror lens: blocked ({pat})"
    if re.search(r"route all.*(through|via).*(oracle|cloud|api)", blob):
        return "reject", "mirror lens: single-oracle dependency"
    if any(re.search(p, blob) for p in (r"cloud-only", r"cloud only", r"hosted saas")):
        if not _mentions_local_fork(blob):
            return "hold", "mirror lens: cloud without local fork"
    if tags & {"verkle", "sovereign_mirror", "refusal", "rope"}:
        return "pass", "mirror lens: starved theme tags; no block"
    if any(t in blob for t in ("local-first", "conflict-scan", "verkle", "vigilance")):
        return "pass", "mirror lens: aligns with operator rules; no block"
    return "pass", "mirror lens: no block"


def _log_mirror_lens_event(candidate: dict[str, Any], verdict: str, reason: str) -> None:
    if verdict == "pass":
        return
    log_path = ROOT / "memory" / "improve" / "mirror_lens.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": _utc_now().isoformat(),
        "id": candidate.get("id"),
        "verdict": verdict,
        "reason": reason,
        "claim": (candidate.get("claim") or "")[:200],
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _append_practices_to_playbook(paths: dict[str, Path], practices: list[dict[str, Any]]) -> None:
    if not practices:
        return
    pb = paths["playbook"]
    existing = pb.read_text(encoding="utf-8") if pb.is_file() else ""
    lines = [f"\n## Scout drafts — {_day_str()}\n"]
    for r in practices[:10]:
        claim = r.get("claim") or ""
        if claim in existing:
            continue
        verdict, reason = _mirror_lens_verdict(r)
        if verdict in ("reject", "hold"):
            _log_mirror_lens_event(r, verdict, reason)
            continue
        urls = ", ".join(r.get("source_urls") or [])
        lines.append(f"- [{r.get('id')}] {claim}  \n  sources: {urls}\n")
    if len(lines) > 1:
        with pb.open("a", encoding="utf-8") as f:
            f.write("".join(lines))


def _write_daily_report(
    paths: dict[str, Path],
    day: str,
    *,
    phase: str,
    source_keys: list[str],
    fetches: list[dict[str, Any]],
    candidates_added: int,
    candidates_sample: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
    eval_result: dict[str, Any] | None = None,
) -> Path:
    paths["daily"].mkdir(parents=True, exist_ok=True)
    path = paths["daily"] / f"{day}.md"
    prev = path.read_text(encoding="utf-8") if path.is_file() else ""
    block = [
        f"\n## {phase} — {_utc_now().isoformat()}\n",
        f"- source_keys: `{', '.join(source_keys)}`\n",
        f"- candidates_added: **{candidates_added}**\n",
        f"- urls: {len(fetches)} (ok={sum(1 for f in fetches if f.get('ok'))})\n",
    ]
    if extra:
        block.append(f"- extra: `{json.dumps(extra, default=str)[:500]}`\n")
    if fetches:
        block.append("\n### Fetches\n")
        for f in fetches[:15]:
            st = "ok" if f.get("ok") or f.get("dry") else "fail"
            block.append(f"- [{st}] {f.get('source')}: {f.get('url')}\n")
    if candidates_sample:
        block.append("\n### Candidate sample\n")
        for c in candidates_sample:
            block.append(
                f"- `{c.get('id')}` **{c.get('kind')}** — {c.get('claim')}\n"
            )
    if eval_result:
        block.append("\n### Eval\n")
        block.append(f"- multi_smoke_ok: **{eval_result.get('multi_smoke_ok')}**\n")
        if eval_result.get("verdict"):
            block.append(f"- verdict: {eval_result.get('verdict')}\n")
    header = f"# Mag improve daily — {day}\n\n_Evidence trail for scout → eval → promote._\n"
    body = (prev if prev.startswith("#") else header + prev) + "".join(block)
    if not prev:
        body = header + "".join(block)
    path.write_text(body, encoding="utf-8")
    # also latest pointer
    latest = paths["root"] / "latest.md"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def run_eval() -> dict[str, Any]:
    cfg = load_config()
    paths = ensure_dirs(cfg)
    day = _day_str()
    eval_cfg = cfg.get("eval") or {}
    result: dict[str, Any] = {
        "ok": True,
        "day": day,
        "multi_smoke_ok": None,
        "verdict": "",
        "steps": [],
    }

    if eval_cfg.get("run_multi_smoke", True):
        try:
            from models.multi_smoke import run_multi_smoke

            smoke = run_multi_smoke()
            result["multi_smoke_ok"] = bool(smoke.get("ok"))
            result["verdict"] = smoke.get("verdict") or ""
            result["steps"].append({"id": "multi_smoke", "ok": smoke.get("ok")})
            if not smoke.get("ok"):
                result["ok"] = False
        except Exception as e:
            result["ok"] = False
            result["multi_smoke_ok"] = False
            result["verdict"] = f"multi_smoke error: {e}"
            result["steps"].append({"id": "multi_smoke", "ok": False, "error": str(e)})

    # Mark model candidates that are already in ollama inventory as queued
    try:
        from models.registry import inventory

        inv = inventory()
        present = set()
        for m in inv.get("models") or inv.get("present") or []:
            if isinstance(m, str):
                present.add(m.lower())
            elif isinstance(m, dict):
                present.add(str(m.get("name") or m.get("model") or "").lower())
        # inventory shape may be models_available list
        for k, v in (inv or {}).items():
            if isinstance(v, list) and k in ("available", "models", "present", "ollama"):
                for m in v:
                    present.add(str(m).lower() if not isinstance(m, dict) else str(m.get("name", "")).lower())
        if isinstance(inv.get("by_role"), dict):
            for v in inv["by_role"].values():
                present.add(str(v).lower())
    except Exception:
        present = set()

    # Write eval artifact
    eval_path = paths["evals"] / f"{day}.json"
    payload = {
        "day": day,
        "ts": _utc_now().isoformat(),
        "result": result,
        "max_auto_pull_gb": cfg.get("max_auto_pull_gb", 0),
        "ollama_present_sample": list(present)[:20],
    }
    eval_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    result["eval_path"] = str(eval_path)

    _write_daily_report(
        paths,
        day,
        phase="eval",
        source_keys=["eval"],
        fetches=[],
        candidates_added=0,
        candidates_sample=[],
        eval_result=result,
    )

    state = _load_state(paths)
    state["last_eval"] = _utc_now().isoformat()
    state["last_eval_ok"] = result.get("ok")
    _save_state(paths, state)
    return result


def _score_candidate(r: dict[str, Any]) -> float:
    """Higher = more worth a field-brief ticket. Heuristic only."""
    score = 0.0
    kind = str(r.get("kind") or "").lower()
    status = str(r.get("status") or "new").lower()
    claim = str(r.get("claim") or "")
    detail = str(r.get("detail") or "")
    source = str(r.get("source") or "").lower()
    feasible = str(r.get("local_feasible") or "").lower()

    if status in ("promoted", "rejected", "applied"):
        return -100.0
    if status == "hold":
        score += 2.0
    if status == "new":
        score += 3.0

    kind_w = {
        "practice": 8.0,
        "runtime": 7.0,
        "paper": 6.5,
        "risk": 6.0,
        "tesuji": 7.5,  # model_tesuji leaf → transferable practice
        "price": 3.0,
        "model": 2.0,
    }
    score += kind_w.get(kind, 1.0)

    if feasible == "true":
        score += 5.0
    elif feasible == "false":
        score -= 4.0

    if source in ("mag_internal", "arxiv"):
        score += 3.0
    if source in ("github", "huggingface"):
        score += 1.0

    # Prefer harness / memory / agent themes for Mag
    blob = (claim + " " + detail).lower()
    for term, w in (
        ("memory", 2.5),
        ("harness", 2.5),
        ("agent", 1.5),
        ("eval", 1.5),
        ("tesuji", 2.5),
        ("trail integrity", 2.0),
        ("reasoning_content", 1.5),
        ("vllm", 1.0),
        ("ollama", 1.0),
        ("llama.cpp", 1.0),
        ("open loop", 2.0),
        ("multi-smoke", 2.0),
        # IJL / P0 open contracts (process value, plan diversity, skill distill)
        ("skill bead", 2.5),
        ("process reward", 2.0),
        ("test-time", 2.0),
        ("test time", 2.0),
        ("continual learning", 2.0),
        ("plan search", 2.0),
        ("plansearch", 2.0),
        ("self-teach", 1.5),
        ("self teach", 1.5),
        ("value function", 1.5),
        ("short-circuit", 1.5),
        ("distributionally robust", 1.5),
    ):
        if term in blob:
            score += w

    # Noise: bare "Model signal: X" without more context
    if kind == "model" and claim.lower().startswith("model signal:"):
        score -= 1.5
    # Tesuji leaves (model_tesuji.v1) beat bare model shopping
    if "evals/models/" in blob or "model tesuji" in blob:
        score += 3.0
    if "evals/features/" in blob or "feature compose" in blob or "mag-self-compose" in blob:
        score += 4.0
    if "related_runs" in blob or "seat purity" in blob or "trail integrity" in blob:
        score += 2.0
    if any(
        t in blob
        for t in (
            "openclaw",
            "memory.md",
            "harness",
            "dreaming",
            "progress.txt",
            "verkle",
            "own your memory",
            "prompt is not",
            "long-running",
        )
    ):
        score += 2.0
    # Truncated page-title dumps
    if claim.count("Skip to content") or "Toggle navigation" in claim:
        score -= 5.0

    verdict, reason = _mirror_lens_verdict(r)
    if verdict == "reject":
        return -100.0
    if verdict == "hold":
        score -= 6.0
        _log_mirror_lens_event(r, verdict, reason)
    elif any(t in blob for t in ("local-first", "conflict-scan", "verkle", "vigilance")):
        score += 2.0

    return score


def rank_candidates_for_brief(
    rows: list[dict[str, Any]] | None = None,
    *,
    top_n: int = 12,
    statuses: list[str] | None = None,
) -> list[dict[str, Any]]:
    statuses = [s.lower() for s in (statuses or ["new", "hold"])]
    rows = rows if rows is not None else read_candidates(limit=5000)
    # de-dupe by id, keep last
    by_id: dict[str, dict[str, Any]] = {}
    for r in rows:
        cid = str(r.get("id") or "")
        if cid:
            by_id[cid] = r
    scored: list[tuple[float, dict[str, Any]]] = []
    for r in by_id.values():
        st = str(r.get("status") or "new").lower()
        if st not in statuses:
            continue
        scored.append((_score_candidate(r), r))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, Any]] = []
    for sc, r in scored[:top_n]:
        item = dict(r)
        item["_score"] = round(sc, 2)
        out.append(item)
    return out


def _heuristic_field_brief(
    day: str,
    ranked: list[dict[str, Any]],
    *,
    max_tickets: int = 5,
    eval_ok: bool | None = None,
) -> str:
    tickets = ranked[:max_tickets]
    models = [r for r in ranked if str(r.get("kind") or "").lower() == "model"][:8]
    noise = [r for r in ranked if _score_candidate(r) < 2.0][:5]

    # Common knowledge: module/compose health (game: reduce hidden thrash)
    compose_line = "compose-status: n/a"
    try:
        from mag.modules import compose_status

        cs = compose_status()
        rt = cs.get("runtime") or {}
        compose_line = (
            f"compose-status: ok={cs.get('ok')} modules={cs.get('n_modules')} "
            f"missing={cs.get('n_missing_paths')} "
            f"related_runs={rt.get('related_runs_n')} "
            f"active_run=`{rt.get('active_run')}` "
            f"tesuji_leaves={rt.get('model_tesuji_leaves')}/"
            f"feature_leaves={rt.get('feature_compose_leaves')}"
        )
    except Exception as e:
        compose_line = f"compose-status: error {e}"

    # IJL daily surface: skill beads are the upgrade residue of process-value runs
    ijl_line = "ijl: skills=0 (no beads yet — run one assigned graph goal)"
    try:
        skills_dir = ROOT / "memory" / "improve" / "pins" / "skills"
        n = len(list(skills_dir.glob("*.json"))) if skills_dir.is_dir() else 0
        newest = ""
        if skills_dir.is_dir():
            metas = sorted(skills_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if metas:
                newest = metas[0].stem
        ijl_line = f"ijl: skills={n}" + (f" · newest=`{newest}`" if newest else "")
    except Exception as e:
        ijl_line = f"ijl: error {e}"

    lines = [
        f"# Mag field brief — {day}",
        "",
        "_Synthesis of improve candidates. Local-first. Promote only what you will run._",
        "",
        f"- generated: `{_utc_now().isoformat()}`",
        f"- candidates_ranked: **{len(ranked)}**",
        f"- multi_smoke: **{eval_ok if eval_ok is not None else 'n/a'}**",
        f"- {compose_line}",
        f"- {ijl_line}",
        f"- elevate: paste this file only into Grok under `[priority]` — not full chat",
        "",
        "## Top tickets (do these)",
        "",
    ]
    if not tickets:
        lines.append("_No open candidates to ticket. Run `improve --once` or check promote queue._")
        lines.append("")
    for i, r in enumerate(tickets, 1):
        urls = ", ".join((r.get("source_urls") or [])[:2])
        lines.append(
            f"{i}. **`{r.get('id')}`** [{r.get('kind')}] score={r.get('_score')}  \n"
            f"   {r.get('claim')}  \n"
            f"   feasible=`{r.get('local_feasible')}` · src=`{r.get('source')}`  \n"
            f"   urls: {urls or '—'}"
        )
        lines.append("")

    lines.extend(
        [
            "## Watch (models — do not auto-pull)",
            "",
        ]
    )
    if not models:
        lines.append("_No model signals in top rank._")
        lines.append("")
    else:
        for r in models:
            lines.append(
                f"- `{r.get('id')}` {r.get('claim')} (score={r.get('_score')})"
            )
        lines.append("")
        lines.append(
            "_Seat changes need `python main.py promote --apply <id>` + manual `lanes.yaml`._"
        )
        lines.append("")

    lines.extend(["## Skip / low signal", ""])
    if not noise:
        lines.append("_None flagged in this cut._")
        lines.append("")
    else:
        for r in noise:
            lines.append(f"- `{r.get('id')}` — {str(r.get('claim') or '')[:120]}")
        lines.append("")

    # One Mag move
    move = "Re-run improve --status and promote at most one practice you will follow this week."
    if tickets:
        top = tickets[0]
        if str(top.get("kind")) == "practice" and str(top.get("local_feasible")) == "true":
            move = (
                f"Deep-dive ticket `{top.get('id')}`: "
                f"`python main.py research-pack --ask \"{str(top.get('claim') or '')[:80]}\" "
                f"--url \"{(top.get('source_urls') or ['https://example.com'])[0]}\" --run`"
            )
        elif str(top.get("kind")) == "runtime":
            move = f"Read release notes for `{top.get('id')}` then smoke local stack (`multi-smoke`)."
        else:
            move = f"Decide hold/reject for `{top.get('id')}` — do not shop models blindly."

    lines.extend(
        [
            "## One Mag move this week",
            "",
            move,
            "",
            "## Commands",
            "",
            "```text",
            "python main.py improve --status",
            "python main.py improve --synthesize   # re-run brief only",
            "python main.py improve --deep --minutes 60   # opt-in dig (local worker)",
            "python main.py promote --apply c-…",
            "python main.py promote --reject c-… --reason noise",
            "python main.py context-pack           # before [priority] Grok",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _llm_polish_brief(heuristic_md: str, ranked: list[dict[str, Any]], role: str) -> str | None:
    """Optional local LLM polish. Returns None on failure (caller keeps heuristic)."""
    try:
        from llm import chat
    except Exception:
        return None
    catalog = []
    for r in ranked[:12]:
        catalog.append(
            {
                "id": r.get("id"),
                "kind": r.get("kind"),
                "score": r.get("_score"),
                "claim": str(r.get("claim") or "")[:200],
                "feasible": r.get("local_feasible"),
                "source": r.get("source"),
            }
        )
    system = (
        "You are Mag field synthesizer (local). Output markdown only. "
        "No flattery. Max 40 lines. Keep all candidate ids that matter. "
        "Prefer practices/runtimes over model shopping. "
        "Sections required: Top tickets, Watch (models), Skip, One Mag move."
    )
    user = (
        "Polish this field brief for an operator building a local Mag harness. "
        "Keep truth; cut noise; one concrete next command.\n\n"
        f"HEURISTIC DRAFT:\n{heuristic_md[:6000]}\n\n"
        f"CATALOG JSON:\n{json.dumps(catalog, ensure_ascii=False)[:4000]}"
    )
    try:
        raw = chat(role, system, user, temperature=0.15, strict=False)
        text = (raw or "").strip()
        if len(text) < 80:
            return None
        # Guard: polished prose must keep the ranked candidate ids (artifact > transcript).
        ids = [r.get("id") for r in ranked[:5] if r.get("id")]
        if ids and not all(i in text for i in ids):
            return None
        # Ensure title line
        if not text.lstrip().startswith("#"):
            text = f"# Mag field brief — {_day_str()}\n\n" + text
        return text
    except Exception:
        return None


def synthesize_field_brief(
    *,
    use_llm: bool | None = None,
    dry: bool = False,
) -> dict[str, Any]:
    """
    Rank open candidates → field brief markdown.
    Writes memory/improve/field_brief.md + daily synthesis block + latest.md = field brief.
    """
    cfg = load_config()
    paths = ensure_dirs(cfg)
    day = _day_str()
    syn = cfg.get("synthesis") or {}
    if not syn.get("enabled", True) and use_llm is None:
        return {"ok": False, "error": "synthesis disabled in configs/improve.yaml"}

    top_n = int(syn.get("top_n") or 12)
    max_tickets = int(syn.get("max_tickets") or 5)
    statuses = list(syn.get("statuses") or ["new", "hold"])
    role = str(syn.get("role") or "clerk")
    do_llm = syn.get("use_llm", True) if use_llm is None else bool(use_llm)

    ranked = rank_candidates_for_brief(top_n=top_n, statuses=statuses)
    state = _load_state(paths)
    eval_ok = state.get("last_eval_ok")

    heuristic = _heuristic_field_brief(day, ranked, max_tickets=max_tickets, eval_ok=eval_ok)
    body = heuristic
    llm_used = False
    if do_llm and not dry:
        polished = _llm_polish_brief(heuristic, ranked, role=role)
        if polished:
            body = polished
            llm_used = True

    field_path = paths["root"] / "field_brief.md"
    day_field = paths["daily"] / f"{day}-field.md"

    result: dict[str, Any] = {
        "ok": True,
        "day": day,
        "ranked": len(ranked),
        "top_ids": [r.get("id") for r in ranked[:max_tickets]],
        "llm_used": llm_used,
        "role": role if llm_used else None,
        "dry": dry,
        "field_brief": str(field_path),
        "day_field": str(day_field),
    }

    if dry:
        result["preview"] = body[:2000]
        return result

    field_path.write_text(body, encoding="utf-8")
    day_field.write_text(body, encoding="utf-8")
    # latest.md for Grok / dashboard: the brief, not the full evidence dump
    (paths["root"] / "latest.md").write_text(body, encoding="utf-8")

    # Append short pointer into daily evidence trail
    _write_daily_report(
        paths,
        day,
        phase="synthesis",
        source_keys=["synthesis"],
        fetches=[],
        candidates_added=0,
        candidates_sample=ranked[:max_tickets],
        extra={
            "field_brief": str(field_path),
            "llm_used": llm_used,
            "top_ids": result["top_ids"],
        },
    )
    # _write_daily_report overwrites latest with full daily — restore field brief as latest
    (paths["root"] / "latest.md").write_text(body, encoding="utf-8")

    state["last_synthesis"] = _utc_now().isoformat()
    state["last_field_brief"] = str(field_path)
    state["last_synthesis_top"] = result["top_ids"]
    _save_state(paths, state)

    result["chars"] = len(body)
    return result


def deepseek_rank_top(
    *,
    top_n: int = 5,
    dry: bool = False,
) -> dict[str, Any]:
    """DeepSeek workhorse: verdict promote|hold|reject on ranked new/hold candidates.

    Writes memory/improve/pins/deepseek_routing.jsonl + pins/deepseek_rank_latest.md
    Does not auto-promote (human gate).
    """
    cfg = load_config()
    paths = ensure_dirs(cfg)
    ranked = rank_candidates_for_brief(top_n=top_n, statuses=["new", "hold"])
    if not ranked:
        return {"ok": False, "error": "no candidates", "ranked": 0}

    pack_rows = []
    for r in ranked[:top_n]:
        pack_rows.append(
            {
                "id": r.get("id"),
                "kind": r.get("kind"),
                "status": r.get("status"),
                "title": (r.get("title") or r.get("claim") or "")[:200],
                "claim": (r.get("claim") or "")[:300],
                "score": r.get("score") or r.get("rank_score"),
            }
        )

    if dry:
        return {"ok": True, "dry": True, "candidates": pack_rows}

    system = (
        "You are Mag DeepSeek self-improve seat (workhorse). "
        "For each candidate output ONLY a JSON array of objects: "
        '[{"id":"...","verdict":"promote|hold|reject","confidence":0.0-1.0,'
        '"reason":"one sentence","next_action":"one concrete Mag path or command"}]. '
        "Prefer hold over promote unless clearly shippable on local Mag. "
        "Reject noise/risk without a path. No markdown outside JSON."
    )
    user = "Candidates:\n" + json.dumps(pack_rows, indent=2)

    try:
        from models.providers import chat_provider

        res = chat_provider(
            "deepseek",
            system,
            user,
            tier="T2",
            max_tokens=900,
            temperature=0.2,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "candidates": pack_rows}

    raw = str(res.get("text") or res.get("content") or "") if res.get("ok") else ""
    verdicts: list[dict[str, Any]] = []
    if res.get("ok") and raw:
        import re as _re

        m = _re.search(r"\[[\s\S]*\]", raw)
        if m:
            try:
                arr = json.loads(m.group(0))
                if isinstance(arr, list):
                    for item in arr:
                        if isinstance(item, dict) and item.get("id"):
                            verdicts.append(
                                {
                                    "id": item.get("id"),
                                    "verdict": str(item.get("verdict") or "hold").lower(),
                                    "confidence": item.get("confidence"),
                                    "reason": str(item.get("reason") or "")[:300],
                                    "next_action": str(item.get("next_action") or "")[:200],
                                }
                            )
            except Exception:
                pass

    pins = paths["root"] / "pins"
    pins.mkdir(parents=True, exist_ok=True)
    jpath = pins / "deepseek_routing.jsonl"
    md_path = pins / "deepseek_rank_latest.md"
    ts = _utc_now().isoformat()
    with jpath.open("a", encoding="utf-8") as fh:
        for v in verdicts:
            row = {"ts": ts, "source": "deepseek_rank_top", "model": res.get("model"), **v}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    lines = [
        f"# DeepSeek self-improve rank — {ts[:10]}",
        "",
        f"model: `{res.get('model')}` · candidates: {len(pack_rows)} · verdicts: {len(verdicts)}",
        "",
        "| id | verdict | conf | reason | next |",
        "|----|---------|------|--------|------|",
    ]
    for v in verdicts:
        lines.append(
            f"| `{v.get('id')}` | **{v.get('verdict')}** | {v.get('confidence')} | "
            f"{(v.get('reason') or '')[:80]} | {(v.get('next_action') or '')[:60]} |"
        )
    if not verdicts:
        lines.append("")
        lines.append("No parseable JSON verdicts. Raw tail:")
        lines.append("```")
        lines.append(raw[:1500] if raw else str(res.get("error") or "empty")[:500])
        lines.append("```")
    lines.append("")
    lines.append("Human gate: `python main.py promote --apply <id>` or `--reject <id>`.")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    state = _load_state(paths)
    state["last_deepseek_rank"] = ts
    state["last_deepseek_rank_n"] = len(verdicts)
    _save_state(paths, state)

    try:
        from mag.training_events import emit

        emit(
            "improve_cycle",
            action={"kind": "deepseek_rank_top", "n": len(verdicts)},
            outcome={"path": str(md_path.relative_to(ROOT)).replace("\\", "/")},
            pattern_tags=["improve", "deepseek", "self_improve"],
            tier_max="T2",
        )
    except Exception:
        pass

    return {
        "ok": bool(res.get("ok")) and bool(verdicts),
        "schema": "mag_deepseek_rank.v1",
        "model": res.get("model"),
        "candidates": pack_rows,
        "verdicts": verdicts,
        "jsonl": str(jpath),
        "latest_md": str(md_path),
        "raw_ok": bool(res.get("ok")),
        "error": None if res.get("ok") else str(res.get("error") or "")[:200],
    }


def improve_once(
    *,
    scout_only: bool = False,
    eval_only: bool = False,
    dry: bool = False,
    synthesize_only: bool = False,
) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": True, "phases": {}}
    if synthesize_only:
        syn = synthesize_field_brief(dry=dry)
        out["phases"]["synthesis"] = syn
        if not syn.get("ok"):
            out["ok"] = False
        out["day"] = _day_str()
        paths = ensure_dirs()
        out["field_brief"] = str(paths["root"] / "field_brief.md")
        out["latest_report"] = str(paths["root"] / "latest.md")
        out["candidates"] = str(paths["candidates"])
        return out

    if not eval_only:
        s = scout(dry=dry)
        out["phases"]["scout"] = s
        if not s.get("ok"):
            out["ok"] = False
    if not scout_only and not dry:
        e = run_eval()
        out["phases"]["eval"] = e
        if not e.get("ok"):
            out["ok"] = False
        # Q-002 (2026-09-28): the deterministic auto-promote gate runs after
        # eval in the daily loop. Eligibility is a pure predicate
        # (local_feasible true + kind practice|tesuji + age >= 48h + status
        # new|hold, fail-closed on unparseable age); apply reuses
        # promote_apply so the mirror-lens gate and playbook append keep a
        # single promote writer. Receipt:
        # watch/inbox/burn_reset_20260927/queue/Q-002.md
        from tools.auto_promote import run as auto_promote_run

        ap = auto_promote_run(dry=False)
        out["phases"]["auto_promote"] = ap
        if not ap.get("ok"):
            out["ok"] = False
    # Field brief after scout/eval (or after scout-only if we still want a brief)
    if not dry:
        syn_cfg = (load_config().get("synthesis") or {})
        if syn_cfg.get("enabled", True):
            syn = synthesize_field_brief(dry=False)
            out["phases"]["synthesis"] = syn
            if not syn.get("ok"):
                out["ok"] = False
    out["day"] = _day_str()
    paths = ensure_dirs()
    out["latest_report"] = str(paths["root"] / "latest.md")
    out["field_brief"] = str(paths["root"] / "field_brief.md")
    out["candidates"] = str(paths["candidates"])
    return out


def _split_ticket_sources(urls: list[Any]) -> tuple[list[str], list[Path]]:
    """Split candidate source_urls into http(s) URLs and existing local paths."""
    http: list[str] = []
    local: list[Path] = []
    for u in urls or []:
        s = str(u or "").strip()
        if not s:
            continue
        if s.startswith("http://") or s.startswith("https://"):
            http.append(s)
            continue
        p = Path(s)
        if p.is_file():
            local.append(p)
    return http, local


def _local_excerpts(paths: list[Path], *, max_chars: int = 6000) -> str:
    chunks: list[str] = []
    budget = max_chars
    for p in paths:
        if budget <= 0:
            break
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            chunks.append(f"[unreadable {p}: {e}]")
            continue
        take = text[:budget]
        chunks.append(f"### local file: {p}\n\n{take}")
        budget -= len(take)
    return "\n\n".join(chunks)


def deep_dive(
    *,
    minutes: int | None = None,
    max_tickets: int | None = None,
    dry: bool = False,
) -> dict[str, Any]:
    """
    Opt-in hour-class dig from ranked field tickets.

    For each eligible practice/runtime ticket: research-pack (scrape) + local
    Ollama worker answer. Writes memory/improve/deep/*. No auto-promote.
    Wall-clock budget only — stops mid-queue when time is up.
    """
    cfg = load_config()
    paths = ensure_dirs(cfg)
    dd = cfg.get("deep_dive") or {}
    if not dd.get("enabled", True):
        return {"ok": False, "error": "deep_dive disabled in configs/improve.yaml"}

    wall_min = int(minutes if minutes is not None else dd.get("default_minutes") or 60)
    wall_min = max(1, min(wall_min, 180))  # hard cap 3h
    n_tickets = int(max_tickets if max_tickets is not None else dd.get("max_tickets") or 4)
    n_tickets = max(1, min(n_tickets, 12))
    min_score = float(dd.get("min_score") or 12)
    kinds = {str(k).lower() for k in (dd.get("kinds") or ["practice", "runtime", "paper", "risk"])}
    statuses = list(dd.get("statuses") or ["new", "hold"])
    role = str(dd.get("role") or "worker")
    run_local = bool(dd.get("run_local", True))
    auto_promote = bool(dd.get("auto_promote", False))

    ranked = rank_candidates_for_brief(top_n=max(n_tickets * 3, 12), statuses=statuses)
    queue: list[dict[str, Any]] = []
    for r in ranked:
        if len(queue) >= n_tickets:
            break
        kind = str(r.get("kind") or "").lower()
        if kind not in kinds:
            continue
        if float(r.get("_score") or 0) < min_score:
            continue
        http_urls, local_paths = _split_ticket_sources(list(r.get("source_urls") or []))
        if dd.get("require_http_or_local", True) and not http_urls and not local_paths:
            continue
        item = dict(r)
        item["_http"] = http_urls
        item["_local"] = [str(p) for p in local_paths]
        queue.append(item)

    day = _day_str()
    ts = _utc_now().strftime("%Y%m%dT%H%M%SZ")
    deep_root = paths["root"] / "deep"
    sess_dir = deep_root / f"{day}_{ts}"
    deep_root.mkdir(parents=True, exist_ok=True)

    out: dict[str, Any] = {
        "ok": True,
        "mode": "deep_dive",
        "day": day,
        "minutes_budget": wall_min,
        "max_tickets": n_tickets,
        "role": role,
        "run_local": run_local,
        "auto_promote": auto_promote,
        "dry": dry,
        "queued": [
            {
                "id": q.get("id"),
                "kind": q.get("kind"),
                "score": q.get("_score"),
                "claim": (q.get("claim") or "")[:100],
                "http": q.get("_http"),
                "local": q.get("_local"),
            }
            for q in queue
        ],
        "digs": [],
        "skipped": [],
        "session_dir": str(sess_dir),
    }

    if not queue:
        out["ok"] = False
        out["error"] = "no eligible tickets (need ranked practice/runtime with URLs or local paths)"
        return out

    if dry:
        out["hint"] = f"Would dig {len(queue)} tickets for up to {wall_min}m with role={role}"
        return out

    sess_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    deadline = t0 + wall_min * 60.0

    from mag.research_pack import build_research_pack, load_pack

    for q in queue:
        remaining = deadline - time.monotonic()
        if remaining <= 30:
            out["skipped"].append(
                {"id": q.get("id"), "reason": "wall_clock_exhausted", "remaining_s": round(remaining, 1)}
            )
            continue

        cid = str(q.get("id") or "")
        claim = str(q.get("claim") or "").strip()
        http_urls: list[str] = list(q.get("_http") or [])
        local_paths = [Path(p) for p in (q.get("_local") or [])]
        local_blob = _local_excerpts(local_paths)

        focus_extra = ""
        focus_md = paths["root"] / "blast" / "FOCUS.md"
        if focus_md.is_file():
            try:
                focus_extra = focus_md.read_text(encoding="utf-8", errors="replace")[:1500]
            except Exception:
                focus_extra = ""
        ask = (
            f"Deep-dive Mag improve ticket {cid} ({q.get('kind')}).\n"
            f"Claim: {claim}\n"
            f"Detail: {str(q.get('detail') or '')[:800]}\n\n"
            + (f"Operator focus (steer dig):\n{focus_extra}\n\n" if focus_extra else "")
            + "Job: extract portable contracts for Mag (trail / residual / pack-first / "
            "promote-gate / skill beads). Not product worship. "
            "List: (1) what is actually claimed, (2) what Mag can steal as practice, "
            "(3) what to refuse, (4) one concrete local next move under 30 minutes.\n"
        )
        if local_blob:
            ask += f"\n--- local artifacts already on disk ---\n{local_blob[:5000]}\n"

        dig: dict[str, Any] = {
            "id": cid,
            "claim": claim[:160],
            "started": _utc_now().isoformat(),
            "http": http_urls,
            "local": [str(p) for p in local_paths],
            "remaining_s_at_start": round(remaining, 1),
        }

        try:
            built = build_research_pack(
                ask,
                urls=http_urls[:6],
                success_criteria=[
                    "Cite source URLs for every non-obvious claim.",
                    "Separate Mag-stealable practice from hype.",
                    "Name gaps / uncertainty honestly.",
                    "End with one local Mag next move (command or file path).",
                ],
                constraints=[
                    "Public/T2 only.",
                    "Do not recommend auto-pulling model weights.",
                    "Do not invent Mag CLI flags that do not exist.",
                    "Prefer contracts over brand names.",
                ],
                title=f"deep-{cid}",
                elevate_to="local",
            )
            dig["pack"] = {
                "ok": built.get("ok"),
                "id": built.get("id"),
                "json": built.get("json"),
                "pdf": built.get("pdf"),
                "error": built.get("error"),
            }
            if not built.get("ok"):
                dig["ok"] = False
                dig["error"] = built.get("error") or "pack build failed"
                out["digs"].append(dig)
                continue

            pack = load_pack(built.get("json"))
            if run_local:
                # Local-only: do not fall through to remote (research_pack run_pack does).
                # Deep dig is meant for Ollama worker over the pack prompt.
                from mag.research_pack import _pack_to_prompt, score_fidelity, PACKS
                from llm import chat as llm_chat

                prompt = _pack_to_prompt(pack)
                system = (pack.get("for_lesser_models") or {}).get("system") or (
                    "Execute the research pack. Cite sources. Meet criteria."
                )
                ans_text = ""
                local_err = None
                try:
                    ans_text = llm_chat(role, system, prompt[:14000], temperature=0.2)
                except Exception as e:
                    local_err = str(e)

                fidelity = score_fidelity(ans_text, pack) if ans_text else {}
                pack_id = str(pack.get("id") or built.get("id") or "pack")
                ans_path = PACKS / f"{pack_id}.answer.local.md"
                if ans_text:
                    ans_path.write_text(
                        f"# Answer (local deep-dive role={role})\n\n{ans_text}\n\n"
                        f"## Fidelity scorecard\n\n{json.dumps(fidelity, indent=2)}\n",
                        encoding="utf-8",
                    )

                dig["run"] = {
                    "ok": bool(ans_text),
                    "seat": "local",
                    "provider": "ollama",
                    "model": role,
                    "answer_path": str(ans_path) if ans_text else None,
                    "fidelity": fidelity,
                    "local_error": local_err,
                    "hint": (
                        "Local worker answered from pack."
                        if ans_text
                        else f"Local failed: {local_err}"
                    ),
                }
                dig["ok"] = bool(ans_text)
                dig["answer_chars"] = len(ans_text or "")
                ticket_md = sess_dir / f"{cid}.md"
                ticket_md.write_text(
                    f"# Deep dig `{cid}`\n\n"
                    f"- claim: {claim}\n"
                    f"- score: {q.get('_score')}\n"
                    f"- pack: `{built.get('id')}`\n"
                    f"- role: `{role}` (Ollama local-only)\n"
                    f"- started: {dig['started']}\n\n"
                    f"## URLs\n\n"
                    + ("\n".join(f"- {u}" for u in http_urls) or "_none_")
                    + "\n\n## Answer\n\n"
                    + (ans_text or f"(no answer)\n\nerror: {local_err}")
                    + "\n\n## Fidelity\n\n```json\n"
                    + json.dumps(fidelity or {}, indent=2)
                    + "\n```\n",
                    encoding="utf-8",
                )
                dig["ticket_report"] = str(ticket_md)
                if not dig["ok"] and local_err:
                    dig["error"] = local_err
            else:
                dig["ok"] = True
                dig["run"] = {"ok": True, "seat": "pack_only", "hint": "run_local=false"}
        except Exception as e:
            dig["ok"] = False
            dig["error"] = str(e)

        dig["elapsed_s"] = round(time.monotonic() - t0, 1)
        dig["finished"] = _utc_now().isoformat()
        out["digs"].append(dig)

        # Stop early if Ollama is clearly down — no point burning the hour
        err = str(dig.get("error") or dig.get("run", {}).get("local_error") or "").lower()
        hard_down = any(
            x in err
            for x in (
                "connection refused",
                "forcibly closed",
                "failed to connect",
                "10054",
                "no such model",
                "model not found",
                "not found",
            )
        )
        if not dig.get("ok") and hard_down:
            out["aborted"] = (dig.get("error") or err)[:300]
            break

    elapsed = time.monotonic() - t0
    ok_n = sum(1 for d in out["digs"] if d.get("ok"))
    out["elapsed_s"] = round(elapsed, 1)
    out["elapsed_min"] = round(elapsed / 60.0, 2)
    out["ok_digs"] = ok_n
    out["ok"] = ok_n > 0

    # Session rollup
    lines = [
        f"# Mag improve deep dive — {day}",
        "",
        f"- session: `{sess_dir.name}`",
        f"- budget_min: **{wall_min}** · elapsed_min: **{out['elapsed_min']}**",
        f"- digs_ok: **{ok_n}** / {len(out['digs'])} · skipped: {len(out['skipped'])}",
        f"- role: `{role}` · auto_promote: **{auto_promote}**",
        f"- finished: `{_utc_now().isoformat()}`",
        "",
        "_Human gate still required. Promote only practices you will run._",
        "",
        "## Digs",
        "",
    ]
    for d in out["digs"]:
        lines.append(
            f"### `{d.get('id')}` — {'OK' if d.get('ok') else 'FAIL'}\n"
            f"- claim: {d.get('claim')}\n"
            f"- report: `{d.get('ticket_report') or 'n/a'}`\n"
            f"- pack: `{((d.get('pack') or {}).get('id'))}`\n"
            f"- answer_chars: {d.get('answer_chars')}\n"
            f"- error: {d.get('error') or ((d.get('run') or {}).get('local_error')) or '—'}\n"
        )
    if out["skipped"]:
        lines.extend(["## Skipped (budget)", ""])
        for s in out["skipped"]:
            lines.append(f"- `{s.get('id')}` — {s.get('reason')}")
        lines.append("")
    lines.extend(
        [
            "## Next",
            "",
            "```text",
            "python main.py improve --status",
            "python main.py promote --apply c-…   # only if dig earned it",
            "python main.py context-pack           # before [priority] Grok",
            "```",
            "",
            f"Open session dir: `{sess_dir}`",
            "",
        ]
    )
    if out.get("aborted"):
        lines.insert(8, f"- **aborted early:** `{out['aborted'][:200]}`")
        out["ok"] = ok_n > 0

    report_body = "\n".join(lines)
    session_report = sess_dir / "REPORT.md"
    latest_deep = deep_root / "latest.md"
    session_report.write_text(report_body, encoding="utf-8")
    latest_deep.write_text(report_body, encoding="utf-8")
    # Machine index
    (sess_dir / "result.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    (deep_root / "latest.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )

    out["report"] = str(session_report)
    out["latest"] = str(latest_deep)

    state = _load_state(paths)
    state["last_deep_dive"] = _utc_now().isoformat()
    state["last_deep_ok"] = out.get("ok")
    state["last_deep_report"] = str(session_report)
    state["last_deep_ok_digs"] = ok_n
    _save_state(paths, state)

    # Never auto-promote even if config is mis-set true — double hard stop
    if auto_promote:
        out["promote_note"] = "auto_promote ignored in v1 (human gate only)"

    return out


def _scheduled_task_surface() -> dict[str, Any]:
    """t33: run the doctor's silent-disablement probe for the seat surface.

    Reuses mag.doctor.check_scheduled_tasks (t20) via import; the schtasks
    subprocess lives only there. Non-Windows and Ready pass through ok=True,
    so the WARNING in status_summary fires only on a genuinely not-Ready task.
    """
    from mag.doctor import check_scheduled_tasks

    return check_scheduled_tasks()


def _scenario_citation_liveness(
    cards_dir: str = str(ROOT / "configs" / "workflow_gate_scenarios"),
    registry_path: str | None = None,
) -> dict[str, Any]:
    """B2-452 (2026-09-26): scenario-card citation liveness on a recurring
    surface. The seven gate cards validate their cited_fail_row (ts, digest)
    against memory/workflows/REGISTRY.jsonl only inside the gate's
    --scenarios run, which fires only when tools/workflow_gate.py itself
    changes, so a registry rewrite/prune/renumber can orphan a card with no
    surface naming it. This check names orphans on every improve --status
    read. Citation liveness only (each card's cited FAIL row still exists):
    the full fixture replay stays in the gate. Read-only; parameters
    injectable so the falsifier can run against sandboxed copies."""
    import glob as _glob
    import json as _json

    reg_path = registry_path or str(
        ROOT / "memory" / "workflows" / "REGISTRY.jsonl")
    index: dict[tuple[str, str], dict[str, Any]] = {}
    if os.path.exists(reg_path):
        with open(reg_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = _json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    index[(row.get("ts"), row.get("digest"))] = row
    cards = sorted(_glob.glob(str(Path(cards_dir) / "*.card.json")))
    orphaned: list[str] = []
    checked = 0
    for card_path in cards:
        try:
            card = _json.loads(Path(card_path).read_text(encoding="utf-8"))
        except Exception:
            orphaned.append(f"{Path(card_path).name}: unreadable card")
            continue
        checked += 1
        cited = card.get("cited_fail_row") or {}
        row = index.get((cited.get("ts"), cited.get("digest")))
        if row is None:
            orphaned.append(f"{Path(card_path).name}: cited FAIL row "
                            f"(ts={cited.get('ts')}, digest={str(cited.get('digest'))[:12]}..) "
                            "not in REGISTRY")
        elif row.get("verdict") != "FAIL":
            orphaned.append(f"{Path(card_path).name}: cited row verdict "
                            f"{row.get('verdict')}, not FAIL")
    return {
        "ok": not orphaned,
        "cards_checked": checked,
        "orphaned": orphaned,
        "registry": reg_path,
    }


def status_summary(limit: int = 15) -> dict[str, Any]:
    cfg = load_config()
    paths = ensure_dirs(cfg)
    rows = read_candidates(paths, limit=2000)
    by_status: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for r in rows:
        st = str(r.get("status") or "new")
        by_status[st] = by_status.get(st, 0) + 1
        k = str(r.get("kind") or "?")
        by_kind[k] = by_kind.get(k, 0) + 1
    state = _load_state(paths)
    recent = rows[-limit:]
    recent.reverse()
    field_brief = paths["root"] / "field_brief.md"
    deep_latest = paths["root"] / "deep" / "latest.md"
    sched = _scheduled_task_surface()
    if not sched.get("ok"):
        issues = sched.get("issues") or ["scheduled task not Ready"]
        print("WARNING: " + " | ".join(str(i) for i in issues), file=sys.stderr)
    try:
        from mag.failure_kb import verify as fkb_verify
    except Exception:
        def fkb_verify():
            return {"ok": None, "violations": None}
    return {
        "ok": True,
        "total_candidates": len(rows),
        "by_status": by_status,
        "by_kind": by_kind,
        "state": state,
        "source_keys_today": _weekday_keys(cfg),
        "max_auto_pull_gb": cfg.get("max_auto_pull_gb", 0),
        "field_brief": str(field_brief) if field_brief.is_file() else None,
        "deep_latest": str(deep_latest) if deep_latest.is_file() else None,
        "scheduled_task": sched,
        # B2-493 (2026-09-26): the provider-probe cadence surfaces here so the
        # seat can tell armed from silently stale (the t33 silent-disablement
        # disease in a new costume). due comes from provider_probe_due; no
        # network call, state bytes only.
        "provider_probe": {
            "last": str((state or {}).get(_PROVIDER_PROBE_STATE_KEY) or ""),
            "cadence_days": _PROVIDER_PROBE_DEFAULT_CADENCE_DAYS,
            "due": provider_probe_due(state),
        },
        # B2-361 (2026-09-26): the failure-knowledge-base index-vs-log recount
        # rides on every status read (recurring surface per the owning brief),
        # so a mutated/clobbered signatures.json is named here, not only at
        # the next gate edit. Read-only; violations detail via
        # python -m mag.failure_kb verify.
        "failure_kb": (lambda v: {
            "ok": v.get("ok"),
            "violations": v.get("violations"),
        })(fkb_verify()),
        # B2-452 (2026-09-26): scenario-card citation liveness on a recurring
        # surface (see _scenario_citation_liveness); detail via
        # tools/workflow_gate.py check --scenarios.
        "workflow_scenarios": _scenario_citation_liveness(),
        "paths": {k: str(v) for k, v in paths.items()},
        "recent": [
            {
                "id": r.get("id"),
                "kind": r.get("kind"),
                "status": r.get("status"),
                "claim": (r.get("claim") or "")[:120],
                "local_feasible": r.get("local_feasible"),
            }
            for r in recent
        ],
        "playbook": str(paths["playbook"]),
        "latest_daily": str(paths["root"] / "latest.md"),
    }


def promote_apply(
    cid: str, *, force_model: bool = False, note: str | None = None
) -> dict[str, Any]:
    """Human gate: mark promoted; model seats never auto-write lanes unless force_model + future.

    Q-002 (2026-09-28): optional ``note`` kwarg lets the deterministic
    auto-promote gate (tools/auto_promote.py) stamp its own provenance instead
    of recording "Promoted by operator" for a promotion no operator made.
    """
    cfg = load_config()
    paths = ensure_dirs(cfg)
    rows = {r.get("id"): r for r in read_candidates(paths, limit=10000)}
    row = rows.get(cid)
    if not row:
        return {"ok": False, "error": f"unknown candidate {cid}"}
    verdict, reason = _mirror_lens_verdict(row)
    if verdict in ("reject", "hold"):
        _log_mirror_lens_event(row, verdict, reason)
        return {"ok": False, "error": reason, "id": cid, "mirror_lens": verdict}
    kind = row.get("kind")
    promo = cfg.get("promote") or {}

    if kind == "model" and not promo.get("auto_apply_model_seats") and not force_model:
        # Record intent only — do not edit lanes.yaml
        ok = update_candidate_status(
            cid,
            "promoted",
            note="Human promoted claim; model seat NOT auto-applied (edit lanes.yaml manually or use --force-model later)",
        )
        return {
            "ok": ok,
            "id": cid,
            "kind": kind,
            "action": "status_promoted_no_lanes_edit",
            "hint": "Set worker/clerk in configs/lanes.yaml after local smoke of the new tag.",
        }

    if kind == "practice":
        update_candidate_status(cid, "promoted", note=note or "Practice accepted")
        pb = paths["playbook"]
        with pb.open("a", encoding="utf-8") as f:
            f.write(
                f"\n### Promoted {cid} ({_day_str()})\n"
                f"- {row.get('claim')}\n"
                f"- sources: {', '.join(row.get('source_urls') or [])}\n"
            )
        return {"ok": True, "id": cid, "kind": kind, "action": "playbook_promoted"}

    update_candidate_status(cid, "promoted", note=note or "Promoted by operator")
    try:
        from mag.training_events import emit

        emit(
            "promote_gate",
            join={"candidate_id": cid},
            input_data={"claim": (row.get("claim") or "")[:200], "kind": kind},
            action={"verdict": "promoted", "force_model": force_model},
            outcome={"ok": True},
            pattern_tags=[f"kind_{kind}"],
        )
    except Exception:
        pass
    return {"ok": True, "id": cid, "kind": kind, "action": "status_promoted"}


def promote_reject(cid: str, reason: str = "") -> dict[str, Any]:
    ok = update_candidate_status(cid, "rejected", note=reason or "rejected by operator")
    try:
        from mag.training_events import emit

        emit(
            "promote_gate",
            join={"candidate_id": cid},
            input_data={"reason": (reason or "")[:200]},
            action={"verdict": "rejected"},
            outcome={"ok": ok},
            pattern_tags=["reject"],
        )
    except Exception:
        pass
    return {"ok": ok, "id": cid, "status": "rejected"}
