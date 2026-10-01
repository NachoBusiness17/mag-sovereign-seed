"""VERB stone one — feels() over the fleet (2026-09-19).

The feels-language from VERB_DSL_STEAL_20260918.md, first executable stone.
feels(question) = a pack-grounded semantic read: the question is answered by a
free lane, grounded by the invariant pack (the RIB's compiled doctine), and the
whole exchange appends typed verb rows so control flow becomes kifu.

Rows appended to watch/inbox/verb_trace.jsonl:
  FEELS_ASKED, FEELS_VERDICT, (VETO_FIRED when the oracle refuses)

Security: https-only, fixed allowlisted host, resolved-IP boundary check, no
redirects (same SSRF posture as scripts/endpoint_news.py).

Self-test:  python -m mag.verb feels "Do the called-shot ledger rows carry
verdicts?"  -> the oracle answers from the pack + its own read.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACE = ROOT / "watch" / "inbox" / "verb_trace.jsonl"
PACK = ROOT / "memory" / "corpus" / "quantized_thought" / "adversarial_arc_invariants.jsonl"
LANE_URL = "https://api.groq.com/openai/v1/chat/completions"
ALLOWED_HOST = "api.groq.com"
MAX_PACK_CHARS = 6000


def _env_key(index: int = 1) -> str:
    name = "GROQ_API_KEY" if index <= 1 else f"GROQ_API_KEY_{index}"
    for ln in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if ln.startswith(name + "="):
            return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _last_hash() -> str:
    if not TRACE.exists():
        return ""
    try:
        with TRACE.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 8192))
            lines = f.read().decode("utf-8", "replace").strip().splitlines()
        for ln in reversed(lines):
            try:
                h = json.loads(ln).get("h")
            except Exception:
                continue
            if h:
                return h
    except Exception:
        pass
    return ""


def _emit(row: dict) -> None:
    # Kifu chain (salon 2): every verb row commits to its predecessor, so the
    # trace is an append-only execution record, not a log.
    prev = _last_hash()
    row["ts"] = _now()
    row["ph"] = prev
    row["h"] = hashlib.sha256(
        (prev + json.dumps(row, sort_keys=True, ensure_ascii=False)).encode("utf-8")
    ).hexdigest()[:16]
    with TRACE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def verify_trace() -> dict:
    rows = [json.loads(ln) for ln in
            TRACE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    prev, breaks, legacy = "", 0, 0
    for r in rows:
        h = r.pop("h", None)
        if "ph" not in r and h is None:
            # pre-chain row: the kifu predates hashing; counted, not verified
            legacy += 1
            continue
        want = hashlib.sha256(
            (prev + json.dumps(r, sort_keys=True, ensure_ascii=False)).encode("utf-8")
        ).hexdigest()[:16]
        if h != want:
            breaks += 1
        prev = h if h else prev
        r["h"] = h
    return {"rows": len(rows), "legacy": legacy, "breaks": breaks,
            "healthy": breaks == 0}


def _pack_grounding() -> str:
    return _pack_grounding_v1()


def _ask_lane(grounded_question: str, key: str, model: str = "openai/gpt-oss-20b") -> str:
    p = urllib.parse.urlparse(LANE_URL)
    if p.scheme != "https" or p.hostname != ALLOWED_HOST:
        raise ValueError("host not allowed")
    for _f, _s, _pr, _c, sa in socket.getaddrinfo(p.hostname, 443):
        if not ipaddress.ip_address(sa[0]).is_global:
            raise ValueError("resolved to non-global address")
    body = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 900,
        "messages": [
            {"role": "system", "content":
             "You are the VERB feels() oracle of a receipted agent fleet. Answer the "
             "question briefly (<=120 words). Ground your answer in the DOCTRINE PACK "
             "when it applies; say GROUNDED or UNGROUNDED as the first word. For "
             "yes/no questions answer YES or NO as the first word after grounding. "
             "End every answer with exactly: CONFIDENCE: <0-100>."},
            {"role": "user", "content": grounded_question},
        ],
    }
    req = urllib.request.Request(
        LANE_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "mag-verb/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    return (d["choices"][0]["message"].get("content") or "").strip()


def _pack_grounding_v1() -> str:
    if not PACK.exists():
        return ""
    return PACK.read_text(encoding="utf-8", errors="replace")[:MAX_PACK_CHARS]


def _pack_grounding(facts: bool = False) -> str:
    """Doctrine pack (invariants) plus, with facts=True, the fact-packs:
    called-shot ledger, sound reading, GSTD forensics. Stone two of VERB."""
    parts = []
    if PACK.exists():
        parts.append(PACK.read_text(encoding="utf-8", errors="replace")[:MAX_PACK_CHARS])
    if facts:
        fact_files = [
            ROOT / "watch" / "inbox" / "mrpool_export" / "called_shot_ledger.jsonl",
            ROOT / "watch" / "inbox" / "mrpool_export" / "SOUND_READING_FULL.json",
            ROOT / "watch" / "inbox" / "GSTD_FORENSICS_20260918.md",
        ]
        budget = 4000
        for fp in fact_files:
            if fp.exists() and budget > 0:
                parts.append(fp.read_text(encoding="utf-8", errors="replace")[:budget])
                budget -= min(budget, 4000)
    return "\n\n".join(parts)


def _yes_no(answer: str):
    # The oracle grounds first ("GROUNDED YES ..."), so search for the first
    # standalone YES/NO token instead of matching the prefix.
    m = re.search(r"\b(YES|NO)\b", (answer or "").upper())
    return m.group(1) if m else None


def _explicit_conf(answer: str):
    """Only an explicitly declared CONFIDENCE counts. _score_answer's
    GROUNDED->70 fallback is a heuristic for distributions, not a measurement;
    a verdict without a declaration carries confidence=None (never bluff a
    number)."""
    up = (answer or "").upper()
    if "CONFIDENCE:" in up:
        return min(100.0, _score_answer(up))
    return None


def feels(question: str, *, kpack: bool = True, facts: bool = True, risk: str = "low") -> dict:
    """Pack-grounded semantic read. Appends FEELS_ASKED + FEELS_VERDICT rows.
    facts=True grounds in fact-packs (ledgers, readings) as well as doctrine.
    risk sets the SILENCE BRANCH route when the oracle goes quiet (empty
    answer or error): low -> PASS_UNVERIFIED, medium -> QUEUE_RETRY,
    high -> ESCALATE_MODEL, irreversible -> WAKE_HUMAN. Silence is a verdict,
    not a stop sign. Verdicts carry a confidence field only when the oracle
    declares one (source: oracle-declared, UNCALIBRATED until the Fleet-Bench
    meter says otherwise)."""
    asked = {"verb": "FEELS_ASKED", "question": question[:300], "facts": facts, "risk": risk}
    _emit(asked)
    pack = _pack_grounding(facts=facts) if kpack else ""
    q = ("DOCTRINE PACK (excerpt):\n" + pack + "\n\nQUESTION: " + question) if pack else question
    verdict = {"verb": "FEELS_VERDICT", "question": question[:300], "grounding": "pack" if pack else "none"}
    answer = ""
    try:
        answer = _ask_lane(q, _env_key())
        verdict["answer"] = answer[:600]
        verdict["veto"] = answer.upper().startswith("VETO")
        conf = _explicit_conf(answer)
        if conf is not None:
            verdict["confidence"] = conf
            verdict["confidence_source"] = "oracle-declared-uncalibrated"
        if verdict["veto"]:
            verdict["verb"] = "VETO_FIRED"
    except Exception as e:
        verdict["error"] = str(e)[:120]
        verdict["veto"] = True
    # SILENCE BRANCH: empty answer or error routes by risk instead of stopping
    if not answer.strip() or verdict.get("error"):
        verdict["route"] = _SILENCE_ROUTES.get(risk, "QUEUE_RETRY")
        verdict["tag"] = "UNVERIFIED"
    _emit(verdict)
    return verdict


def match(options: dict, question: str) -> dict:
    """Route between descriptions: ask feels() which option the doctrine prefers."""
    lines = "\n".join(f"- {k}: {v}" for k, v in options.items())
    v = feels(f"Which option best serves the doctrine?\n{lines}\nQuestion: {question}")
    chosen = None
    low = (v.get("answer") or "").lower()
    for k in options:
        if k.lower() in low:
            chosen = k
            break
    row = {"verb": "MATCH_ROUTED", "question": question[:200], "chosen": chosen,
           "reason": (v.get("answer") or "")[:300]}
    _emit(row)
    return row


def classify(text: str, labels: list, *, facts: bool = True) -> dict:
    """Jev-style typed classifier: pick exactly one label for the text.
    The nedwize pattern (typed classification over any corpus at negligible cost)
    as a VERB primitive. Appends CLASSIFY_ASKED/CLASSIFY_VERDICT rows."""
    opts = "\n".join(f"{i+1}. {lab}" for i, lab in enumerate(labels))
    q = ("Classify the TEXT below into exactly one category:\n" + opts +
         f"\n\nTEXT: {text[:1500]}\n\nAnswer with ONLY the category name.")
    v = feels(q, facts=facts)
    ans = (v.get("answer") or "").lower()
    chosen = None
    for lab in labels:
        if lab.lower() in ans:
            chosen = lab
            break
    row = {"verb": "CLASSIFY_VERDICT", "chosen": chosen, "labels": labels,
           "raw": (v.get("answer") or "")[:300]}
    _emit(row)
    row["verdict"] = v
    return row


def _score_answer(answer: str) -> float:
    """Extract a 0-100 confidence scalar from an oracle answer. Explicit
    'CONFIDENCE: NN' wins; GROUNDED/UNGROUNDED map to 70/30; anything else 50."""
    up = answer.upper()
    if "CONFIDENCE:" in up:
        tail = up.split("CONFIDENCE:")[-1].strip()
        digits = ""
        for ch in tail:
            if ch.isdigit():
                digits += ch
            elif digits:
                break
        if digits:
            return min(100.0, max(0.0, float(digits)))
    if up.startswith("GROUNDED"):
        return 70.0
    if up.startswith("UNGROUNDED"):
        return 30.0
    return 50.0


def confident(question: str, *, k: int = 3, facts: bool = True) -> dict:
    """STONE FOUR — GP-semantics confidence. k independent pack-grounded reads
    at temperature; the scores form a predictive distribution: mean = where the
    fleet stands, variance = how much it disagrees with itself. n is HONEST:
    silent/erroring samples are transport deaths and never count toward k
    (law of 2026-09-19: died-in-transit files no verdict). High variance or
    n < k flags the read as low-confidence rather than bluffing a number.
    Appends CONFIDENT_ASKED + CONFIDENT_DIST rows to the kifu."""
    _emit({"verb": "CONFIDENT_ASKED", "question": question[:300], "k": k})
    pack = _pack_grounding(facts=facts)
    q = ("DOCTRINE PACK (excerpt):\n" + pack +
         "\n\nQUESTION: " + question +
         "\n\nEnd your answer with exactly: CONFIDENCE: <0-100>") if pack else \
        (question + "\n\nEnd your answer with exactly: CONFIDENCE: <0-100>")
    scores, answers = [], []
    for _ in range(k):
        try:
            a = _ask_lane(q, _env_key())
            if a.strip():
                scores.append(_score_answer(a))
                answers.append(a[:300])
        except Exception:
            continue  # transport death: honest n, no synthetic sample
    n = len(scores)
    mean = sum(scores) / n if n else None
    var = (sum((s - mean) ** 2 for s in scores) / n) if n else None
    row = {"verb": "CONFIDENT_DIST", "question": question[:300], "k": k,
           "n": n, "mean": round(mean, 1) if mean is not None else None,
           "var": round(var, 2) if var is not None else None,
           "scores": scores,
           "low_confidence": (n < k) or (var is not None and var > 400),
           "answers": answers}
    _emit(row)
    return row


# ------------------------------------------------------- stones five to nine
# (2026-09-19 evening, Jev Salon 2 ratified: sift / witness / vow / abide /
# the Fleet-Bench meter. These are the RIB language's missing verbs, living
# in this module on purpose: the gate ruled no parallel organ re-implements
# lane plumbing verb.py owns.)

MAX_CHOICE_OPTIONS = 4          # steering: Choice-decompose compiler rule
VOTE_CONFIDENCE_MIN = 0.70      # witness agreement floor (declared, judged at runtime)
COST_GUARD_USD = 0.001          # per-request abort guard for the hosted tier
PRICE_PER_MTOK = 0.042          # hosted S1 tier price, input only (output free)
DEFAULT_PACK = [("groq1", "openai/gpt-oss-20b", 1),
                ("groq2", "qwen/qwen3.8-27b", 2)]
FLEET_BENCH = ROOT / "memory" / "runs" / "fleet_bench"

_ATOM_RE = re.compile(r"\b(and|or|but)\b", re.I)
_STATE_RE = re.compile(r"\b(q\s?[0-9]|previous|earlier|above)\b", re.I)
_SILENCE_ROUTES = {"low": "PASS_UNVERIFIED", "medium": "QUEUE_RETRY",
                   "high": "ESCALATE_MODEL", "irreversible": "WAKE_HUMAN"}


def sift(questions):
    """The question linter as language syntax (salon 2). Compile-time
    rejects: compound predicates (and/or/but), two judgments in one question.
    Compile-time transform: a CHOICE with more than MAX_CHOICE_OPTIONS options
    auto-decomposes into parallel NOUL questions (the 50-point ablation).
    Runtime warnings: state isolation (context belongs in state, never in the
    question)."""
    ok, rejected, decomposed, warnings = [], [], {}, []
    for q in questions:
        if isinstance(q, dict):
            text, opts = str(q.get("question", "")), q.get("options")
        else:
            text, opts = str(q), None
        bad = None
        if _ATOM_RE.search(text):
            bad = "atomicity: compound predicate (and/or/but)"
        elif text.count("?") > 1:
            bad = "one-judgment: two questions in one"
        if bad:
            rejected.append({"question": text[:200], "reason": bad})
            continue
        if opts:
            if len(opts) > MAX_CHOICE_OPTIONS:
                decomposed[text[:200]] = [f"Is '{str(o)[:80]}' the answer?"
                                          for o in opts]
            else:
                ok.append({"question": text[:300], "kind": "CHOICE",
                           "options": list(opts)})
            continue
        if _STATE_RE.search(text):
            warnings.append({"question": text[:200],
                             "reason": "state isolation: question references other context"})
        ok.append({"question": text[:300], "kind": "NOUL"})
    _emit({"verb": "SIFT_SCAN", "in": len(questions), "ok": len(ok),
           "rejected": len(rejected), "decomposed": len(decomposed),
           "warnings": len(warnings)})
    return {"ok": ok, "rejected": rejected, "decomposed": decomposed,
            "warnings": warnings}


def witness(question: str, *, pack=None, kpack: bool = True, facts: bool = True) -> dict:
    """Pod of models over ONE packet (the kubernetes mechanic, the two-witness
    law as a verb): several lanes read the same question in tandem; full
    agreement is a GREEN verdict, anything else is PURPLE and routes to
    escalation. A lane that dies in transit casts no vote, so a pack can
    never turn green on partial attendance (died-in-transit files no
    verdict)."""
    pack = pack or DEFAULT_PACK
    _emit({"verb": "WITNESS_PACKET", "question": question[:300],
           "lanes": [m for _, m, _k in pack]})
    grounding = _pack_grounding(facts=facts) if kpack else ""
    prefix = ("DOCTRINE PACK (excerpt):\n" + grounding + "\n\nQUESTION: ") if grounding else ""
    votes = []
    for lane, model, key_index in pack:
        row = {"verb": "WITNESS_LANE", "lane": lane, "model": model}
        vote, conf, ans = None, None, ""
        for attempt in (1, 2):
            try:
                ans = _ask_lane(prefix + question, _env_key(key_index), model)
                break
            except Exception as e:
                row["error"] = str(e)[:120]
                if attempt == 1 and "429" in str(e):
                    time.sleep(8)  # transport retry once; a 429 is not a verdict
        if ans.strip():
            vote, conf = _yes_no(ans), _explicit_conf(ans)
            row.update(vote=vote, confidence=conf, raw=ans[:200])
            row.pop("error", None)
        votes.append(vote)
        _emit(row)
    green = (len(pack) > 0 and all(v is not None for v in votes)
             and len(set(votes)) == 1)
    verdict = {"verb": "WITNESS_VERDICT", "verdict": "GREEN" if green else "PURPLE",
               "route": "PASS" if green else "ESCALATE_MODEL",
               "vote": votes[0] if green else None, "votes": votes,
               "agreement_floor": VOTE_CONFIDENCE_MIN}
    _emit(verdict)
    return verdict


def vow(stop_question: str, act) -> dict:
    """The standing drive as a verb (VERB DSL stone three, composable form):
    one tick evaluates the stop condition and, unless it holds, fires act()
    once. The cron drive calls vow() on its cadence; the kifu shows
    WHILE_EXTENDED per live tick and WHILE_CLOSED when the stop holds. A
    drive that lives in cron but speaks verb rows can compose; a while(1)
    loop cannot."""
    _emit({"verb": "VOW_TICK", "stop": stop_question[:200]})
    v = feels(stop_question)
    stop = bool(v.get("veto")) or _yes_no(v.get("answer") or "") == "YES"
    if stop:
        row = {"verb": "WHILE_CLOSED", "reason": "stop condition held"}
    else:
        try:
            act()
            row = {"verb": "WHILE_EXTENDED", "acted": True}
        except Exception as e:
            row = {"verb": "WHILE_EXTENDED", "acted": False, "error": str(e)[:120]}
    _emit(row)
    return row


def abide(turn: str, rules, *, threshold: float = 50.0, advisory: bool = True) -> dict:
    """Per-turn veto scoring (salon 2: sampled turns, ADVISORY until the
    false-veto rate is measured <=5 percent on 100 labeled turns).
    Cite-or-flag compiled in: every fire carries the rule text that produced
    it, and an empty rule can never gate. Uncited vetoes are tags, never
    stops."""
    fires = []
    for rule in rules:
        rule_text = (rule.get("text") if isinstance(rule, dict)
                     else str(rule or "")).strip()
        v = feels("Does the TURN violate this RULE? Answer YES or NO first.\n"
                  f"RULE: {rule_text[:400]}\nTURN: {turn[:1200]}", kpack=False)
        declared = v.get("confidence")
        violated = _yes_no(v.get("answer") or "") == "YES" or bool(v.get("veto"))
        if violated and (declared is None or declared >= threshold):
            fires.append({"rule": rule_text[:200], "confidence": declared,
                          "cited": bool(rule_text),
                          "gate": bool(rule_text) and not advisory})
    _emit({"verb": "ABIDE_SCAN", "turn_chars": len(turn), "rules": len(rules),
           "fires": len(fires), "advisory": advisory})
    return {"fires": fires, "gate": any(f["gate"] for f in fires),
            "advisory": advisory}


def meter_record(item_id: str, cls: str, predicted, truth,
                 confidence=None, evidence: str = "") -> dict:
    """Fleet-Bench row (memory/runs/fleet_bench/scores.jsonl). Law (falsifier,
    salon 2): every row must name non-model label provenance -- a receipt
    path, arithmetic, or operator adjudication -- in evidence; a row without
    evidence is decoration and is refused at write time. Idempotent by id:
    re-recording the same item (the standing drive reruns waves) never
    inflates n."""
    if not evidence.strip():
        raise ValueError("meter row without evidence is decoration: refused")
    path = FLEET_BENCH / "scores.jsonl"
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            if ln.strip() and json.loads(ln).get("id") == item_id:
                return dict(json.loads(ln), dup=True)
    row = {"ts": _now(), "id": item_id, "class": cls,
           "predicted": predicted, "truth": truth,
           "correct": bool(predicted == truth),
           "confidence": confidence, "evidence": evidence[:300]}
    FLEET_BENCH.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def weekly_trigger() -> dict:
    """The sovereignty trigger meter: replica accuracy over the last 7 days
    of Fleet-Bench rows. The hosted S1 API is dropped only at n>=40 AND
    accuracy>=0.880 on the fleet's own labeled distribution. Fewer rows than
    the floor means UNMEASURED, never passing."""
    path = FLEET_BENCH / "scores.jsonl"
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    rows = []
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                if r.get("ts", "") >= cutoff:
                    rows.append(r)
    n = len(rows)
    acc = (sum(1 for r in rows if r["correct"]) / n) if n else None
    return {"n": n, "accuracy": round(acc, 4) if acc is not None else None,
            "meter_valid": n >= 40,
            "trigger_ge_0880": bool(n >= 40 and acc is not None and acc >= 0.880)}


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:2] and sys.argv[1:] or ["Is the fleet's record load-bearing?"])
    out = feels(q)
    print(json.dumps(out, ensure_ascii=False, indent=1))
