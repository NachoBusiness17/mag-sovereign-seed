"""the_margin — statement-DAG harness, the Prove2Me grammar stolen whole.

B9 of THE MARGIN arc. Charter: watch/THE_MARGIN_20260906.md. Source grammar:
Prove2Me (arXiv:2608.28433, open) — a DAG of theorem statements as a shared
to-do list; statements split from proofs; an NL description kept per node;
agents work disjoint lemmas with guaranteed consistency; failed attempts STAY
in the graph (Anthropic's failed runs are 7% of the final FLT proof).

Fleet translation, what this file implements:
  - DAG of statement nodes (Lean 4 string + plain-English front matter each),
    persisted canonically at state/the_margin_dag.json.
  - append-only attempt log per node, ENFORCED AT SAVE TIME: an attempt can
    only ever be appended, never edited or removed, and a node that has
    attempts can never be dropped — house chain law, in code, not in prose.
  - deps with acyclicity check (it is a DAG, the check is the guarantee).
  - honest toolchain probe: PATH first, then the standard elan install dir,
    verbatim evidence for whatever it finds — ground truth, never intention.
  - kernel runner: `lake env lean` (or bare `lean`), output captured verbatim
    and hashed; no `sorry` means clean; the verdict recorded is the kernel's
    own output, quoted, never paraphrased.
  - an unstaged/uncompiled proof is UNPROVEN: the status enum carries
    `staged` and the harness refuses to print `proved` without a kernel hash.

Pilot (B9, THE THEOREM station): one statement, one seat, staged for scale —
see watch/THE_MARGIN_PILOT_20260906.md for the receipt.

Usage:
  python -m mag.the_margin init      # seed the pilot DAG (idempotent)
  python -m mag.the_margin show      # print the DAG
  python -m mag.the_margin next      # claimable nodes (deps proved, open)
  python -m mag.the_margin toolchain # ground-truth toolchain report
  python -m mag.the_margin check FILE [--cwd LAKE_ROOT]   # kernel run + log
  python -m mag.the_margin demo      # falsifiers F1-F5
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAG_PATH = ROOT / "state" / "the_margin_dag.json"
SCHEMA = "the_margin_dag_v1"

# Legal node statuses. `staged` = artifact written, kernel pending. A node is
# only ever `proved` with a kernel output hash on the proving attempt.
STATUSES = ("stated", "staged", "proved", "failed")
# mathlib-presence classes for a statement. ASSUMED-* is the honest fallback
# when no check ran; VERIFIED-* always carries a receipt (source or grep).
PRESENCE = ("VERIFIED-PRESENT", "VERIFIED-ABSENT", "ASSUMED-PRESENT",
            "ASSUMED-ABSENT")


class AppendOnlyViolation(RuntimeError):
    """Raised when a save would edit/remove an attempt or drop a node."""


# ------------------------------------------------------------------- dataclasses

@dataclass
class Attempt:
    ts: str            # ISO-8601 UTC, when the attempt was logged
    kind: str          # "state" | "kernel" | "toolchain" | ...
    outcome: str       # "ok" | "error" | "staged" | ...
    detail: str        # what happened, honestly
    artifact: str = ""     # path of the staged .lean artifact, if any
    kernel_hash: str = ""  # sha256 of verbatim kernel output, if kernel ran

    def to_doc(self) -> dict:
        return {"ts": self.ts, "kind": self.kind, "outcome": self.outcome,
                "detail": self.detail, "artifact": self.artifact,
                "kernel_hash": self.kernel_hash}

    @staticmethod
    def from_doc(d: dict) -> "Attempt":
        return Attempt(d["ts"], d["kind"], d["outcome"], d["detail"],
                       d.get("artifact", ""), d.get("kernel_hash", ""))


@dataclass
class Node:
    id: str
    statement: str        # formal Lean 4 theorem statement (no proof)
    nl_description: str   # plain-English front matter, the search/reuse surface
    status: str = "stated"
    deps: list[str] = field(default_factory=list)
    attempts: list[Attempt] = field(default_factory=list)
    mathlib_presence: str = "ASSUMED-ABSENT"  # one of PRESENCE
    mathlib_receipt: str = ""  # where the classification came from (or why not)
    pilot: bool = False

    def to_doc(self) -> dict:
        return {"id": self.id, "statement": self.statement,
                "nl_description": self.nl_description, "status": self.status,
                "deps": list(self.deps),
                "attempts": [a.to_doc() for a in self.attempts],
                "mathlib_presence": self.mathlib_presence,
                "mathlib_receipt": self.mathlib_receipt,
                "pilot": self.pilot}

    @staticmethod
    def from_doc(d: dict) -> "Node":
        return Node(d["id"], d["statement"], d["nl_description"],
                    d.get("status", "stated"), list(d.get("deps", [])),
                    [Attempt.from_doc(a) for a in d.get("attempts", [])],
                    d.get("mathlib_presence", "ASSUMED-ABSENT"),
                    d.get("mathlib_receipt", ""), bool(d.get("pilot", False)))


@dataclass
class Dag:
    nodes: dict[str, Node] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        if node.id in self.nodes:
            raise ValueError(f"node {node.id!r} already exists")
        if node.status not in STATUSES:
            raise ValueError(f"bad status {node.status!r}")
        self.nodes[node.id] = node

    def add_dep(self, node_id: str, dep_id: str) -> None:
        """DAG law: deps must keep the graph acyclic — this check IS the
        consistency guarantee the grammar promises disjoint workers."""
        for known in (node_id, dep_id):
            if known not in self.nodes:
                raise ValueError(f"unknown node {known!r}")
        if node_id == dep_id:
            raise ValueError("self-dep is a cycle")
        if _reaches(self.nodes, dep_id, node_id):
            raise ValueError(f"dep {dep_id!r} would make {node_id!r} cyclic")
        if dep_id not in self.nodes[node_id].deps:
            self.nodes[node_id].deps.append(dep_id)

    def claimable(self) -> list[Node]:
        """The shared to-do list, read: open nodes whose deps are all proved.
        Disjoint workers pull from here; consistency = deps proved first."""
        return [n for n in self.nodes.values() if n.status == "stated" and
                all(self.nodes[d].status == "proved" for d in n.deps)]

    def worst_kernel_status(self) -> str:
        """PENDING-RUNTIME iff some node has no clean kernel verdict and no
        honest failure — the honest global answer when no kernel has run."""
        for n in self.nodes.values():
            if n.status in ("proved", "failed"):
                continue
            return "PENDING-RUNTIME"
        return "RESOLVED"


def _reaches(nodes: dict[str, Node], src: str, dst: str) -> bool:
    seen, stack = set(), [src]
    while stack:
        cur = stack.pop()
        if cur == dst:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(nodes[cur].deps)
    return False


# ------------------------------------------------------------------ persistence
# Canonical form: sorted keys, fixed indent, UTF-8, trailing newline. Because
# serialization is canonical, load->save->load is byte-identical BY
# CONSTRUCTION — and F1 measures it anyway.

def dump(dag: Dag) -> str:
    doc = {"schema": SCHEMA,
           "nodes": {nid: dag.nodes[nid].to_doc() for nid in sorted(dag.nodes)}}
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def parse(text: str) -> Dag:
    doc = json.loads(text)
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"bad schema {doc.get('schema')!r}")
    return Dag({nid: Node.from_doc(d) for nid, d in doc["nodes"].items()})


def load(path: Path = DAG_PATH) -> Dag:
    return parse(path.read_text(encoding="utf-8"))


def save(dag: Dag, path: Path = DAG_PATH) -> None:
    """Append-only-guarded write: loads the on-disk state first and refuses
    any save that edits/removes attempts or drops a tried node. Failed
    attempts NEVER leave the graph — the guard is here, not in a promise."""
    if path.exists():
        old = load(path)
        for nid, old_node in old.nodes.items():
            new_node = dag.nodes.get(nid)
            if new_node is None:
                raise AppendOnlyViolation(
                    f"node {nid!r} would be dropped ({len(old_node.attempts)} "
                    "attempts would vanish — never)")
            k = len(old_node.attempts)
            if new_node.attempts[:k] != old_node.attempts:
                raise AppendOnlyViolation(
                    f"attempts of {nid!r} would be edited/removed — "
                    "append-only is enforced, not advisory")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(dag), encoding="utf-8", newline="\n")


def log_attempt(node_id: str, kind: str, outcome: str, detail: str,
                artifact: str = "", kernel_hash: str = "",
                path: Path = DAG_PATH) -> Attempt:
    """The one sanctioned way to add an attempt: load, append, save."""
    dag = load(path)
    att = Attempt(_now(), kind, outcome, detail, artifact, kernel_hash)
    dag.nodes[node_id].attempts.append(att)
    save(dag, path)
    return att


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------- toolchain
# Ground truth only: every claim below is backed by a verbatim probe result.
# Probe order: PATH first; if absent, the standard elan user install (the
# bootstrap lands there and fresh shells get it on PATH — the CURRENT process
# may predate that, which is itself reported, never smoothed over).

TOOL_NAMES = ("lean", "elan", "lake")


def _probe_one(tool: str) -> dict:
    out = {"tool": tool, "on_path": shutil.which(tool) is not None,
           "path": shutil.which(tool) or "", "version": "", "probe": "PATH"}
    exe = shutil.which(tool)
    if not exe:
        alt = Path.home() / ".elan" / "bin" / \
            (tool + (".exe" if os.name == "nt" else ""))
        if alt.is_file():
            out["path"], out["probe"] = str(alt), "~/.elan/bin (not on this " \
                "process's PATH; elan-installed)"
            exe = str(alt)
    if exe:
        try:
            r = subprocess.run([exe, "--version"], capture_output=True,
                               text=True, timeout=60)
            out["version"] = (r.stdout + r.stderr).strip()
            out["ok"] = r.returncode == 0
        except Exception as exc:  # noqa: BLE001 — the failure IS the finding
            out["version"], out["ok"] = f"PROBE FAILED: {exc}", False
    else:
        out["ok"] = False
        out["version"] = "NOT FOUND"
    return out


def toolchain_status() -> dict:
    probes = [_probe_one(t) for t in TOOL_NAMES]
    lean = next(p for p in probes if p["tool"] == "lean")
    return {"probes": probes, "kernel_available": bool(lean.get("ok")),
            "lean_path": lean["path"]}


# ---------------------------------------------------------------- kernel runner

def run_kernel(lean_file: Path, cwd: Path | None = None) -> dict:
    """Compile a .lean file. Uses `lake env lean` when a lake root is given
    (Mathlib oleans resolve that way), else bare `lean`. Output is captured
    VERBATIM and hashed — the verdict recorded downstream is this output."""
    tc = toolchain_status()
    lean = tc["lean_path"]
    if not tc["kernel_available"]:
        return {"ran": False, "blocker": "no lean executable found (PATH and "
                "~/.elan/bin probed)", "output": "", "returncode": None,
                "hash": ""}
    if cwd:
        cmd = ["lake", "env", "lean", str(lean_file)]
        lake = shutil.which("lake") or str(Path.home() / ".elan" / "bin" /
                                           ("lake.exe" if os.name == "nt"
                                            else "lake"))
        cmd[0] = lake
    else:
        cmd = [lean, str(lean_file)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800,
                           cwd=str(cwd) if cwd else None)
        out = (r.stdout or "") + (r.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return {"ran": False, "blocker": f"kernel invocation failed: {exc}",
                "output": "", "returncode": None, "hash": ""}
    clean = r.returncode == 0 and "error" not in out.lower() \
        and "sorry" not in out.lower()
    return {"ran": True, "returncode": r.returncode, "output": out,
            "clean": clean, "sorry": "sorry" in out.lower(),
            "hash": hashlib.sha256(out.encode("utf-8")).hexdigest()}


# ------------------------------------------------------------- pilot seed data
# Three candidates, small-but-nontrivial, statements as Lean 4 + Mathlib.
# Presence classes are set by the build session against the actual mathlib
# tree we compile against (grep receipts), never conflated with assumption.

CANDIDATES = [
    Node(
        id="margin-wilson",
        statement="theorem margin_wilson (p : ℕ) :\n   "
                  "    Nat.Prime p ↔ ((p - 1)! + 1) % p = 0",
        nl_description="Wilson's theorem: n > 1 is prime iff (n-1)! is "
                       "congruent to -1 modulo n. Classical canon; tests "
                       "factorial + modular arithmetic plumbing end to end.",
        deps=[], mathlib_presence="VERIFIED-PRESENT",
        mathlib_receipt="grep of mathlib4 @ 80cbd0498ab39e21d24d6730b3f932cec"
                        "672a702 (2026-09-06): Mathlib/NumberTheory/Wilson."
                        "lean — `ZMod.wilsons_lemma : ((p - 1)! : ZMod p) = "
                        "-1` + full Wilson file; see-also names `Nat.prime_"
                        "iff_fac_equiv_neg_one` (Mathlib/Data/ZMod/Factorial."
                        "lean:23). Our iff-in-%-form is a restatement."),
    Node(
        id="margin-primes-infinite",
        statement="theorem margin_infinitude_of_primes :\n   "
                  "    ∀ n : ℕ, ∃ p, n < p ∧ Nat.Prime p",
        nl_description="Infinitude of the primes, Euclid's factorial form: "
                       "any prime dividing (n+1)!+1 exceeds n. The brief's "
                       "preferred single-session pilot (~30 lines of Mathlib "
                       "exercise if the right lemmas exist).",
        deps=[], mathlib_presence="VERIFIED-PRESENT",
        mathlib_receipt="grep of mathlib4 @ 80cbd0498ab39e21d24d6730b3f932cec"
                        "672a702 (2026-09-06): Mathlib/Data/Nat/Prime/"
                        "Infinite.lean:33 `theorem exists_infinite_primes "
                        "(n : ℕ) : ∃ p, n ≤ p ∧ Prime p`. Pilot is a fleet-"
                        "namespace re-derivation (strict n < p form), "
                        "honestly labeled a re-proof — the artifact under "
                        "test is the pipeline, not novelty."),
    Node(
        id="margin-sum-two-squares",
        statement="theorem margin_sum_two_squares (p : ℕ) (hp : Nat.Prime p)\n"
                  "    (h : p % 4 = 1) : ∃ a b : ℕ, a * a + b * b = p",
        nl_description="Fermat's two-squares theorem, prime case: an odd "
                       "prime is a sum of two squares iff it is 1 mod 4. "
                       "Heavier machinery; staged as a candidate only.",
        deps=[], mathlib_presence="VERIFIED-PRESENT",
        mathlib_receipt="grep of mathlib4 @ 80cbd0498ab39e21d24d6730b3f932cec"
                        "672a702 (2026-09-06): Mathlib/NumberTheory/"
                        "SumTwoSquares.lean:35 `theorem Nat.Prime.sq_add_sq "
                        "{p : ℕ} [Fact p.Prime] (hp : p % 4 ≠ 3)` — prime "
                        "case is IN the library (full n-case built on it)."),
]

PILOT_ID = "margin-primes-infinite"


def seed(path: Path = DAG_PATH) -> Dag:
    """Idempotent seed: creates the DAG file with the three candidates; never
    overwrites an existing file (the graph only grows)."""
    if path.exists():
        return load(path)
    dag = Dag()
    for n in CANDIDATES:
        dag.add_node(Node.from_doc(n.to_doc()))  # deep copy
        if n.id == PILOT_ID:
            dag.nodes[n.id].pilot = True
    save(dag, path)
    return dag


# ------------------------------------------------------------------- falsifiers

def demo() -> bool:
    """F1-F5 over the REAL state file. Prints the falsifier table; a labeled
    failure is a valid outcome. No LLM, no writes to the real DAG."""
    ok = True
    dag = load()

    # F1: deterministic round-trip, byte-identical.
    b1 = dump(dag)
    b2 = dump(parse(b1))
    f1 = b1 == b2
    print(f"F1 round-trip byte-identical: {'PASS' if f1 else 'FAIL'} "
          f"({len(b1)}B, sha {hashlib.sha256(b1.encode()).hexdigest()[:12]})")
    ok &= f1

    # F2: append-only is enforced at save time (on a temp copy, never the real
    # file): removing an attempt must raise; appending must succeed.
    tmp = Path(str(DAG_PATH) + ".f2.tmp")
    tmp.unlink(missing_ok=True)  # probe runs on a copy, never the real file
    try:
        save(parse(b1), tmp)  # tmp mirrors the real state (guard needs an
        # existing on-disk state to defend — a save to nowhere guards nothing)
        mutated = parse(tmp.read_text(encoding="utf-8"))
        mutated.nodes[PILOT_ID].attempts = mutated.nodes[PILOT_ID].attempts[:-1]
        save(mutated, tmp)
        f2a = False
    except AppendOnlyViolation:
        f2a = True
    appended = parse(b1)
    appended.nodes[PILOT_ID].attempts.append(
        Attempt("1970-01-01T00:00:00Z", "kernel", "ok", "F2 probe append"))
    try:
        save(appended, tmp)
        f2b = parse(tmp.read_text(encoding="utf-8")).nodes[PILOT_ID] \
            .attempts[-1].detail == "F2 probe append"
    except AppendOnlyViolation:
        f2b = False
    finally:
        tmp.unlink(missing_ok=True)
    f2 = f2a and f2b
    print(f"F2 append-only enforced (edit/remove raises {f2a}, append "
          f"succeeds {f2b}): {'PASS' if f2 else 'FAIL'}")
    ok &= f2

    # F3: presence honestly classified — every node carries a PRESENCE class
    # and a receipt; VERIFIED always names its instrument.
    unclassified = [n.id for n in dag.nodes.values()
                    if n.mathlib_presence not in PRESENCE]
    unverified = [n.id for n in dag.nodes.values()
                  if n.mathlib_presence.startswith("VERIFIED") and
                  not n.mathlib_receipt.strip()]
    f3 = not unclassified and not unverified
    print(f"F3 presence classified w/ receipts: {'PASS' if f3 else 'FAIL'} "
          f"(unclassified {unclassified or 'none'}, "
          f"verified-without-receipt {unverified or 'none'})")
    ok &= f3

    # F4: toolchain status is ground truth — re-probe now and print evidence.
    tc = toolchain_status()
    f4 = True
    for p in tc["probes"]:
        print(f"F4 {p['tool']}: on_path={p['on_path']} probe={p['probe']} "
              f"-> {p['version'][:79]!r}")
        f4 &= (p["ok"] == bool(p["version"]) and
               p["ok"] != (p["version"] == "NOT FOUND"))
    print(f"F4 toolchain = PATH ground truth, evidence verbatim: "
          f"{'PASS' if f4 else 'FAIL'} — kernel_available="
          f"{tc['kernel_available']}")
    ok &= f4

    # F5: the verdict is the kernel's own, or the node says STAGED.
    pilot = dag.nodes[PILOT_ID]
    last = pilot.attempts[-1] if pilot.attempts else None
    if pilot.status == "proved":
        f5 = bool(last and last.kernel_hash)
        print(f"F5 proved w/ kernel hash {last.kernel_hash[:12] if last else ''}: "
              f"{'PASS' if f5 else 'FAIL'}")
    elif pilot.status == "staged":
        f5 = bool(last and last.outcome == "staged")
        print(f"F5 node STAGED (kernel pending), attempt logged: "
              f"{'PASS' if f5 else 'FAIL'}")
    else:
        f5 = bool(last)
        print(f"F5 node status {pilot.status!r} w/ logged attempt: "
              f"{'PASS' if f5 else 'FAIL'}")
    ok &= f5

    print(f"\nOVERALL: {'PASS' if ok else 'FAIL'} — statuses: "
          + ", ".join(f"{n.id}={n.status}" for n in dag.nodes.values()))
    return ok


# ------------------------------------------------------------------------ CLI

def _show(dag: Dag) -> None:
    print(f"statement-DAG — {len(dag.nodes)} nodes, "
          f"kernel_status={dag.worst_kernel_status()}")
    for n in dag.nodes.values():
        mark = " [PILOT]" if n.pilot else ""
        print(f"\n-- {n.id}{mark} :: {n.status} :: {n.mathlib_presence}")
        print(f"   nl: {n.nl_description}")
        print(f"   deps: {n.deps or 'none'}")
        for a in n.attempts:
            h = f" kh={a.kernel_hash[:12]}" if a.kernel_hash else ""
            print(f"   attempt {a.ts} [{a.kind}/{a.outcome}]{h}: "
                  f"{a.detail[:100]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "show", "next", "toolchain",
                                    "check", "demo"])
    ap.add_argument("file", nargs="?", default="")
    ap.add_argument("--cwd", default="", help="lake project root (mathlib)")
    ap.add_argument("--node", default=PILOT_ID)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    if args.cmd == "init":
        dag = seed()
        print(f"DAG at {DAG_PATH} — {len(dag.nodes)} nodes "
              f"({'seeded' if len(dag.nodes) == len(CANDIDATES) else 'existing'})")
        _show(dag)
    elif args.cmd == "show":
        _show(load())
    elif args.cmd == "next":
        todo = load().claimable()
        print(f"claimable now (deps proved, open): "
              f"{[n.id for n in todo] or 'none'}")
    elif args.cmd == "toolchain":
        tc = toolchain_status()
        for p in tc["probes"]:
            print(f"{p['tool']}: path={p['path'] or '-'} probe={p['probe']}\n"
                  f"  {p['version']}")
        print(f"kernel_available: {tc['kernel_available']}")
    elif args.cmd == "demo":
        sys.exit(0 if demo() else 1)
    elif args.cmd == "check":
        if not args.file:
            ap.error("check requires a .lean file")
        f = Path(args.file)
        if not f.is_absolute():
            f = ROOT / f
        res = run_kernel(f, Path(args.cwd) if args.cwd else None)
        if not res["ran"]:
            outcome, detail = "staged", f"BLOCKER: {res['blocker']}"
            print(f"KERNEL DID NOT RUN — {res['blocker']}\n"
                  f"**STATUS STAGED — UNPROVEN UNTIL A KERNEL RUNS IT**")
        else:
            print(f"kernel verdict (verbatim, rc={res['returncode']}, "
                  f"sha256 {res['hash'][:12]}):\n{res['output']}")
            if res["clean"]:
                outcome, detail = "ok", "kernel clean: rc=0, no error, no sorry"
            else:
                outcome = "error"
                detail = (f"kernel rejected: rc={res['returncode']}"
                          f"{' (sorry present)' if res['sorry'] else ''}")
        dag = load()
        node = dag.nodes[args.node]
        node.attempts.append(Attempt(_now(), "kernel", outcome, detail,
                                     artifact=str(f),
                                     kernel_hash=res.get("hash", "")))
        if res["ran"] and res["clean"]:
            node.status = "proved"
        elif res["ran"]:
            node.status = "failed"
        else:
            node.status = "staged"
        save(dag)
        print(f"node {args.node} -> {node.status} "
              f"(attempt #{len(node.attempts)} logged, append-only)")


if __name__ == "__main__":
    main()
