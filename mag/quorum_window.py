"""quorum_window — the 24h fleet-wide vision audit as an organ (2026-09-07).

Operator GO on watch/QUORUM_OF_MINDS_20260907.md: all ractors audit the vision and
add their own to it. Cold boot. Self-steal. Stepped like the 72. TRUE quorum, not
Kabuki. This is the "smallest build": a sibling organ beside lane_salon (lane_salon
itself is UNTOUCHED — the Sep-7 board is armed and live machinery doesn't get edited
mid-window). Reuses: models.providers.chat_provider (free lanes only, $0),
docs/ref/ractors chair briefs (the binding), mag.cite_gate (BUILD stamps before the
vote). Elder + ponytail design rulings are baked in:

  - quorum denominator = chairs that returned P1, never the manifest (ponytail)
  - p4 self-vote exclusion (B2-205): an addition's author chair ABSTAINs on its own addition — excluded from that addition's tally and denominator (the p3 fold already carries the author; lens B2_60 D1 judge independence)
  - P2 named-counterparty tri-state; refusal legal; null diff = ABSENT (elder+ponytail)
  - P3 fold is mechanical: conductor dedupes, editorializes never (elder)
  - phase gates are FILE-EXISTENCE, not wall-clock (ponytail); h24 ceiling is the
    timekeeper's job at the window level, not a per-call trust assumption
  - atomic writes everywhere (temp + os.replace) — half-written testimony must not
    poison the fold silently (ponytail)
  - accepted additions stay CANDIDATE: sealing into state/world/GOALS.md needs the
    door/add/v1 PoW door and is operator-promoted, never auto-merged (constitution)

Schema: quorum_window.v1 · $0 free lanes · two-strike bail per chair per phase.
CLI:
  python -m mag.quorum_window t0    [--date 20260907] [--order seed|reverse]
  python -m mag.quorum_window p1|p2|p3|p4 [--date ...] [--order ...]
  python -m mag.quorum_window run   [--date ...] [--order ...]   # all phases in order
  python -m mag.quorum_window compare --date 20260907            # seed vs rotation
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "quorum_window.v1"
RACTORS = ROOT / "docs" / "ref" / "ractors"
GOALS = ROOT / "state" / "world" / "GOALS.md"
CONSTITUTION = ROOT / "CONSTITUTION.md"
RECEIPTS = ROOT / "watch" / "salon_receipts"
# Free lanes only ($0 law). Fallback order spreads load across providers.
FREE_LANES: list[tuple[str, str | None]] = [
    ("groq", None),
    ("nvidia", "deepseek-ai/deepseek-v4-flash-0731"),
    ("cerebras", "gpt-oss-120b"),
    ("openrouter", "openrouter/auto"),
]
# B2-133 DORMANT GATE (2026-09-26): a provider declared dormant in configs/providers.yaml
# never carries a chair (mag/doctor.py:607: dormant is a declared state). B2-36 set
# cerebras dormant (card-gated 30-day trial, chat 402 no-credit); the same gate catches
# nvidia (dormant per B2-61, 410 EOL). Operator GO flips the flag and the lane returns,
# no code edit. Receipt: watch/inbox/burn_wave_20260926/B2_133_cerebras_purge_20260926.md
from mag.dormant import dormant_ids as _dormant_provider_ids

FREE_LANES = [l for l in FREE_LANES if l[0] not in _dormant_provider_ids()]
CHAIR_EXCLUDE = {"RACTORS"}  # the manifest is not a chair

P1_TEMPLATE = """## RISKS
- R1: <risk to the five goals, with a file-path evidence pointer>
- R2: <risk>
- R3: <risk>
## ADDITION
[TAG: BUILD] or [TAG: NOTE] <your OWN addition to the vision — one paragraph, file-path evidence>
## CONFIDENCE
<integer 1-5>"""

P2_TEMPLATE = """COUNTER: <NAME of the one chair you engage>
VERDICT: AGREE-WITH-EVIDENCE | DISPUTE-WITH-EVIDENCE | REFUSAL-WITH-GROUND
BODY: <max 250 words, file-path evidence>"""

P4_TEMPLATE = """VOTE: A<n> YES — <max 20 words, optional>
VOTE: A<n> NO-WITH-OBJECTION — <the objection, max 25 words>"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dir(date: str, order: str) -> Path:
    name = f"quorum_{date}" if order == "seed" else f"quorum_{date}_{order}"
    return ROOT / "memory" / "runs" / "salons" / name


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _receipt(date: str, row: dict) -> None:
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "schema": SCHEMA, **row}
    with (RECEIPTS / f"quorum_{date}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def _chairs(order: str) -> list[tuple[str, Path]]:
    """(NAME, path) pairs — paths kept so case-sensitive filesystems (Rocinante) resolve."""
    pairs = sorted((p.stem.upper(), p) for p in RACTORS.glob("*.md") if p.stem.upper() not in CHAIR_EXCLUDE)
    return pairs if order == "seed" else list(reversed(pairs))


def _brief(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _chat(system: str, user: str, max_tokens: int, date: str, phase: str, chair: str) -> dict:
    """Free-lane fallback chain, two-strike bail, honest down-reporting."""
    from models.providers import reload_providers, chat_provider
    last_err = ""
    for provider, model in FREE_LANES:
        for strike in (1, 2):
            try:
                reload_providers()
                kw = {"tier": "T2", "max_tokens": max_tokens}
                if model:
                    kw["model"] = model
                r = chat_provider(provider, system=system, user=user, **kw)
                text = (r.get("text") or "").strip()
                if r.get("ok") and text:
                    _receipt(date, {"phase": phase, "chair": chair, "lane": provider, "ok": True, "chars": len(text)})
                    time.sleep(3)
                    return {"ok": True, "text": text, "lane": provider}
                last_err = (r.get("error") or "empty")[:120]
            except Exception as e:  # noqa: BLE001
                last_err = f"unreachable: {str(e)[:110]}"
            time.sleep(2)
    _receipt(date, {"phase": phase, "chair": chair, "ok": False, "error": f"two-strike bail: {last_err}"})
    return {"ok": False, "text": "", "lane": "down", "error": last_err}


def _brief_by_name(name: str) -> str:
    for n, p in _chairs("seed"):
        if n == name.upper():
            return p.read_text(encoding="utf-8", errors="replace")
    return ""


def _vision_pack() -> str:
    return (GOALS.read_text(encoding="utf-8", errors="replace") + "\n---\n" +
            CONSTITUTION.read_text(encoding="utf-8", errors="replace"))


# ---------------------------------------------------------------- phases

def t0(date: str, order: str) -> dict:
    d = _dir(date, order)
    pairs = _chairs(order)
    chairs = [n for n, _ in pairs]
    h = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]  # noqa: E731
    try:
        v = subprocess.run([sys.executable, str(ROOT / "state" / "world" / "door_verifier.py"), "jsonl"],
                           capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        verifier = (v.stdout + v.stderr).strip()[:400] or "silent exit"
    except Exception as e:  # noqa: BLE001
        verifier = f"verifier unreachable: {str(e)[:120]}"
    lines = [
        "# T0 FREEZE — quorum window", "",
        f"- opened: {_now()}  order: {order}  schema: {SCHEMA}",
        f"- roster ({len(chairs)}): {', '.join(chairs)}  (Fermat excluded: send rights provisional, operator-gated)",
        f"- goals sha256[:16]: {h(GOALS)} · constitution sha256[:16]: {h(CONSTITUTION)}",
        f"- door_verifier jsonl: {verifier}",
        "",
        "## THE RULE (fixed before any votes — elder+ponytail fold)",
        "1. Denominator = chairs that returned a parseable P1. Never the manifest.",
        "2. An ADDITION passes with >= 2/3 YES of the denominator AND every objection logged in the dissent log.",
        "3. P2 response must name a counterchair and differ from own P1 (token Jaccard <= 0.85); else ABSENT, vote void.",
        "4. Refusal (REFUSAL-WITH-GROUND) is a legal P2 verdict. Silence is not.",
        "5. BUILD additions pass cite_gate before the vote; uncited BUILD = flagged UNPROVEN, never silently dropped.",
        "6. Accepted additions land as CANDIDATE knots. GOALS.md sealing needs the door PoW + operator promotion.",
        "7. Window ceiling h24: late = absent; unmet items auto-roll. Phase gates are file-existence, not clocks.",
        "",
        "Falsifiers: rotation rerun (different seat order) must reproduce risk-cluster structure +/-1;",
        "null-diff count must be ZERO (any null diff = Kabuki tell, logged).",
    ]
    _atomic(d / "00_T0_FREEZE.md", "\n".join(lines) + "\n")
    _receipt(date, {"phase": "t0", "order": order, "chairs": chairs})
    return {"ok": True, "dir": str(d), "chairs": chairs}


def p1(date: str, order: str) -> dict:
    d = _dir(date, order)
    if not (d / "00_T0_FREEZE.md").exists():
        return {"ok": False, "error": "T0 freeze missing — run t0 first"}
    rubric = ("You audit the fleet's sealed vision below. Return EXACTLY this markdown template, nothing else:\n"
              + P1_TEMPLATE + "\nConstraints: max 400 words total. Evidence = real file paths. "
              "BUILD = changes what the fleet builds; NOTE = judgment only. Name your crop: end RISKS "
              "with '- CROP: <what your lens cannot see>'.")
    out = {}
    for chair, cpath in _chairs(order):
        path = d / "p1" / f"{chair}.md"
        if path.exists():
            out[chair] = "cached"
            continue
        system = (f"You are {chair}, a ractor chair of the local_sovereign_agent fleet. Your brief below is "
                  "your binding (lens, laws, signature question). Counsel, do not climb. Tri-state, evidence "
                  "attached, meet the bytes.\n\n" + _brief(cpath))
        vision = "THE SEALED VISION + CONSTITUTION:\n\n" + _vision_pack() + "\n\n" + rubric
        r = _chat(system, vision, 900, date, "p1", chair)
        strike2 = False
        if r["ok"] and not _parse_p1(r["text"]):
            # strike 2: one format re-ask — raw kept either way, never silently dropped
            r2 = _chat(system, "FORMAT VIOLATION: your previous answer missed required sections. "
                               "Return EXACTLY the template, complete (RISKS, ADDITION, CONFIDENCE):\n\n"
                               + vision, 1100, date, "p1", chair)
            if r2["ok"] and _parse_p1(r2["text"]):
                r, strike2 = r2, True
        if r["ok"]:
            raw = f"---\nchair: {chair}\nlane: {r['lane']}\nts: {_now()}\n"
            if strike2:
                raw += "strike: 2\n"
            raw += "---\n\n" + r["text"] + "\n"
            if _parse_p1(r["text"]):
                _atomic(path, raw)
                out[chair] = "ok" + ("(strike2)" if strike2 else "")
            else:
                _atomic(d / "p1" / f"{chair}.unparsed.md", raw)
                out[chair] = "ABSENT-FORMAT (raw kept as .unparsed.md, out of denominator)"
        else:
            out[chair] = f"ABSENT ({r.get('error', 'down')[:80]})"
    return {"ok": any(str(v).startswith("ok") for v in out.values()), "p1": out}


_P1_SEC = {"risks": re.compile(r"##\s*RISKS(.*?)(?=##\s*ADDITION|\Z)", re.S | re.I),
           "addition": re.compile(r"##\s*ADDITION(.*?)(?=##\s*CONFIDENCE|\Z)", re.S | re.I),
           "confidence": re.compile(r"##\s*CONFIDENCE\s*\n?\s*(\d)", re.I)}
_TAG = re.compile(r"\[TAG:\s*(BUILD|NOTE)\]", re.I)


def _parse_p1(text: str) -> dict | None:
    """Parseable = RISKS + ADDITION (the substantive deliverables). TAG defaults NOTE;
    CONFIDENCE optional (0 = not returned) — free lanes drop trailing sections."""
    m_r, m_a = _P1_SEC["risks"].search(text), _P1_SEC["addition"].search(text)
    if not (m_r and m_a):
        return None
    tag_m = _TAG.search(m_a.group(1))
    m_c = _P1_SEC["confidence"].search(text)
    return {"risks": m_r.group(1).strip(), "addition": m_a.group(1).strip(),
            "tag": (tag_m.group(1).upper() if tag_m else "NOTE"),
            "confidence": int(m_c.group(1)) if m_c else 0}


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", s.lower()) if len(t) > 3}


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def p2(date: str, order: str) -> dict:
    d = _dir(date, order)
    p1s = {p.stem: p.read_text(encoding="utf-8", errors="replace") for p in sorted((d / "p1").glob("*.md"))}
    if len(p1s) < 2:
        return {"ok": False, "error": "need >=2 P1 testimonies"}
    pool = "\n\n===\n\n".join(f"### {k}\n{v.split('---', 2)[-1].strip()}" for k, v in p1s.items())
    _atomic(d / "pooled.md", f"# POOLED P1 TESTIMONY ({len(p1s)} chairs, named — provenance kept)\n\n{pool}")
    out = {}
    for chair, own in p1s.items():
        path = d / "p2" / f"{chair}.md"
        if path.exists():
            out[chair] = "cached"
            continue
        system = (f"You are {chair}, ractor chair (brief is your binding).\n\n" + _brief_by_name(chair))
        user = ("Cross-examination round. Every other chair's cold-boot testimony follows. Engage ONE named "
                "counterchair. Refusal is legal (REFUSAL-WITH-GROUND); silence and generic pool references "
                "are not — an unnamed response is void. Return EXACTLY:\n" + P2_TEMPLATE +
                "\n\n=== POOLED TESTIMONY ===\n\n" + pool + "\n\n=== YOUR OWN P1 ===\n\n" + own)
        r = _chat(system, user, 700, date, "p2", chair)
        if r["ok"]:
            _atomic(path, f"---\nchair: {chair}\nlane: {r['lane']}\nts: {_now()}\n---\n\n" + r["text"] + "\n")
            out[chair] = "ok"
        else:
            out[chair] = f"ABSENT ({r.get('error', 'down')[:80]})"
    return {"ok": True, "p2": out}


def _null_diffs(d: Path, p1s: dict[str, str]) -> list[str]:
    nulls = []
    for p in sorted((d / "p2").glob("*.md")):
        name = p.stem
        body = p.read_text(encoding="utf-8", errors="replace")
        counter = re.search(r"COUNTER:\s*([A-Z_]+)", body)
        verdict = re.search(r"VERDICT:\s*(AGREE-WITH-EVIDENCE|DISPUTE-WITH-EVIDENCE|REFUSAL-WITH-GROUND)", body)
        if not (counter and verdict):
            nulls.append(f"{name}: malformed/unnamed response")
        elif counter.group(1).capitalize() == name.capitalize():
            nulls.append(f"{name}: countered self")
        elif _jaccard(_tokens(body), _tokens(p1s.get(name, ""))) > 0.85:
            nulls.append(f"{name}: response identical to own P1 (null diff)")
    return nulls


def _cluster_count(risk_lines: list[str]) -> int:
    toks = [_tokens(l) for l in risk_lines]
    clusters: list[list[int]] = []
    for i, t in enumerate(toks):
        for c in clusters:
            if any(_jaccard(t, toks[j]) >= 0.35 for j in c):
                c.append(i)
                break
        else:
            clusters.append([i])
    return len(clusters)


def p3(date: str, order: str) -> dict:
    d = _dir(date, order)
    p1s = {p.stem: p.read_text(encoding="utf-8", errors="replace") for p in sorted((d / "p1").glob("*.md"))}
    if not p1s:
        return {"ok": False, "error": "no P1 testimonies"}
    nulls = _null_diffs(d, p1s) if (d / "pooled.md").exists() else ["p2 not run — fold on P1 only"]
    parsed = {k: v for k, v in ((k, _parse_p1(v)) for k, v in p1s.items()) if v}
    risk_lines: list[tuple[str, str]] = []
    for chair, pa in parsed.items():
        for ln in pa["risks"].splitlines():
            ln = ln.strip()
            if ln.startswith("-") and len(ln) > 12:
                risk_lines.append((chair, ln))
    n_clusters = _cluster_count([t for _, t in risk_lines])
    adds = []
    for i, (chair, pa) in enumerate(sorted(parsed.items()), 1):
        adds.append({"id": f"A{i}", "chair": chair, "tag": pa["tag"], "text": pa["addition"]})
    fold = ["# MECHANICAL FOLD — conductor dedupes, editorializes never", "",
            f"- P1 returners: {len(p1s)} · parsed: {len(parsed)} · risk lines: {len(risk_lines)} · risk clusters: {n_clusters}",
            f"- NULL-DIFF COUNT: {len([n for n in nulls if 'p2 not run' not in n])} (must be 0; list below)",
            f"- null-diff log: {nulls if nulls else 'clean'}", "",
            "## ADDITIONS ON THE TABLE"]
    for a in adds:
        fold.append(f"- **{a['id']}** [{a['tag']}] ({a['chair']}): {a['text']}")
    fold += ["", "## DISSENT LOG (nothing dropped silently)"]
    dis = []
    for p in sorted((d / "p2").glob("*.md")):
        body = p.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"VERDICT:\s*(DISPUTE-WITH-EVIDENCE|REFUSAL-WITH-GROUND)", body)
        if m:
            dis.append(f"- {p.stem}: {m.group(1)} — {body.split('BODY:', 1)[-1].strip()[:400]}")
    fold += (dis or ["- (none filed)"])
    _atomic(d / "FOLD.md", "\n".join(fold) + "\n")
    # cite-gate BEFORE rightsize/the vote: stamp the fold card itself
    cite = ""
    try:
        cg = subprocess.run([sys.executable, "-m", "mag.cite_gate", "check", str(d / "FOLD.md"), "--json"],
                            capture_output=True, text=True, timeout=120, cwd=str(ROOT))
        cite = (cg.stdout or cg.stderr).strip()[:600]
    except Exception as e:  # noqa: BLE001
        cite = f"cite_gate unreachable: {str(e)[:120]}"
    with (d / "FOLD.md").open("a", encoding="utf-8") as f:
        f.write(f"\n## CITE-GATE STAMP\n```\n{cite}\n```\n")
    _receipt(date, {"phase": "p3", "clusters": n_clusters, "additions": len(adds), "null_diffs": len(nulls)})
    return {"ok": True, "clusters": n_clusters, "additions": adds, "null_diffs": nulls}


def p4(date: str, order: str) -> dict:
    d = _dir(date, order)
    fold = d / "FOLD.md"
    if not fold.exists():
        return {"ok": False, "error": "FOLD.md missing"}
    p1s = [p.stem for p in sorted((d / "p1").glob("*.md"))
           if "unparsed" not in p.name and _parse_p1(p.read_text(encoding="utf-8", errors="replace"))]
    fold_text = fold.read_text(encoding="utf-8", errors="replace")
    add_block = fold_text.split("## DISSENT LOG")[0]
    add_ids = sorted(set(re.findall(r"\*\*(A\d+)\*\*", add_block)))
    if not add_ids:
        return {"ok": False, "error": "no additions found in fold"}
    # B2-205 (2026-09-26): additions carry their author chair in the fold header
    # ("- **A1** [NOTE] (BAUDRILLARD): ..."). The author's own vote is an ABSTAIN:
    # excluded from its addition's tally AND its denominator (the p3 fold already
    # carries the author's testimony, so the self-vote double-counts one voice).
    add_author: dict[str, str] = {}
    for m in re.finditer(r"\*\*(A\d+)\*\*\s*\[[^\]]*\]\s*\(([^)\n]+)\)", add_block):
        add_author.setdefault(m.group(1), m.group(2).strip())
    votes: dict[str, dict[str, str]] = {}
    for chair in p1s:
        path = d / "p4" / f"{chair}.md"
        if path.exists():
            raw = path.read_text(encoding="utf-8", errors="replace")
        else:
            system = f"You are {chair}, ractor chair. You already testified in P1; now you vote."
            # compact ballot: id + tag + first line only — full prose already in FOLD.md;
            # long prompts make reasoning lanes burn the token budget and return empty content
            ballot = "\n".join((re.search(rf"^- \*\*{aid}\*\*.*$", add_block, re.M) or [aid])[0][:240]
                               for aid in add_ids)
            user = ("Quorum call. Vote each addition. Return EXACTLY one line per addition:\n" + P4_TEMPLATE +
                    "\n\nBALLOT:\n" + ballot)
            r = _chat(system, user, 1200, date, "p4", chair)
            if not r["ok"]:
                votes[chair] = {}
                continue
            _atomic(path, f"---\nchair: {chair}\nts: {_now()}\n---\n\n" + r["text"] + "\n")
            raw = r["text"]
        votes[chair] = {m.group(1): m.group(2) for m in
                        (re.search(r"VOTE:\s*(A\d+)\s+(YES|NO-WITH-OBJECTION)", ln) for ln in raw.splitlines())
                        if m}
    denom = len(p1s)
    need = math.ceil(2 * denom / 3)
    lines = ["# QUORUM CALL — verdict", "", f"- denominator (P1 returners): {denom} · pass needs >= {need} YES",
             "- rule: >=2/3 YES of the eligible set AND every objection logged (below) · additions land as CANDIDATE knots",
             "- B2-205 rule: an addition's author chair ABSTAINs on it — excluded from its tally and its denominator", ""]
    result = {}
    for aid in add_ids:
        author = add_author.get(aid)
        eligible = [c for c in p1s if c != author]
        yes = [c for c, v in votes.items() if v.get(aid) == "YES" and c != author]
        no = [c for c, v in votes.items() if v.get(aid) == "NO-WITH-OBJECTION" and c != author]
        denom_a = len(eligible)
        need_a = math.ceil(2 * denom_a / 3)
        abstain = author if author in p1s else None
        passed = len(yes) >= need_a
        result[aid] = {"yes": len(yes), "no": len(no), "passed": passed,
                       "denominator": denom_a, "need": need_a,
                       "author_abstain": abstain or ""}
        lines.append(f"- {aid}: {'PASSED → CANDIDATE' if passed else 'NOT PASSED'} "
                     f"(YES {len(yes)}/{denom_a}, need >= {need_a}, NO {len(no)})"
                     + (f" · author {author} ABSTAIN" if abstain else "")
                     + f" · yes: {','.join(yes) or '-'} · no: {','.join(no) or '-'}")
    lines += ["", "## OBJECTIONS (the dissent log)", ""]
    for p in sorted((d / "p4").glob("*.md")):
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "NO-WITH-OBJECTION" in ln:
                lines.append(f"- {p.stem}: {ln.strip()[:300]}")
    _atomic(d / "VERDICT.md", "\n".join(lines) + "\n")
    _receipt(date, {"phase": "p4", "denominator": denom, "result": result})
    return {"ok": True, "denominator": denom, "result": result}


def compare(date: str) -> dict:
    base, rot = _dir(date, "seed"), _dir(date, "reverse")

    # structure = cluster count of pooled P1 risk lines
    def pooled_clusters(d: Path) -> int | None:
        lines = []
        for p in sorted((d / "p1").glob("*.md")):
            pa = _parse_p1(p.read_text(encoding="utf-8", errors="replace"))
            if pa:
                lines += [l.strip() for l in pa["risks"].splitlines()
                          if l.strip().startswith("-") and len(l) > 12]
        return _cluster_count(lines) if lines else None
    a, b = pooled_clusters(base), pooled_clusters(rot)
    ok = a is not None and b is not None and abs(a - b) <= 1
    verdict = (f"rotation compare: seed clusters={a} rotation clusters={b} -> "
               + ("STRUCTURE INVARIANT (+/-1) — organ class CONFIRMED" if ok else
                  "STRUCTURE DRIFT — falsifier FIRED: it's a toolbox, log on the chain"))
    (base / "ROTATION_COMPARE.md").write_text(verdict + "\n", encoding="utf-8")
    _receipt(date, {"phase": "rotation_compare", "seed": a, "rotation": b, "invariant": ok})
    return {"ok": ok, "seed": a, "rotation": b, "verdict": verdict}


def main() -> None:
    ap = argparse.ArgumentParser(prog="quorum_window")
    ap.add_argument("phase", choices=["t0", "p1", "p2", "p3", "p4", "run", "compare"])
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y%m%d"))
    ap.add_argument("--order", default="seed", choices=["seed", "reverse"])
    args = ap.parse_args()
    if args.phase == "compare":
        print(json.dumps(compare(args.date), default=str))
        return
    steps = {"run": ["t0", "p1", "p2", "p3", "p4"]}.get(args.phase, [args.phase])
    for s in steps:
        r = {"t0": t0, "p1": p1, "p2": p2, "p3": p3, "p4": p4}[s](args.date, args.order)
        print(f"[{s}] " + json.dumps(r, default=str)[:900])


if __name__ == "__main__":
    main()
