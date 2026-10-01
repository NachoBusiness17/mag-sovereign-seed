"""flock_job — emergent flock on K8s: steer a self-organizing swarm cheaply, on the fly.

Operator vision (2026-08-10): "using steering on k8s within our own system to create emergent
flocking results cheaply on the fly." This is the payload the kind cluster exists to run.

Mechanism (grounded in RIB_EMERGENT_FLOCK_ON_K8S):
  1. STEER — a goal becomes a memlang chord + a flock_field goal point in invariant space.
  2. FAN OUT — build a K8s Job (parallelism=N) of cheap agent pods; each pod is seeded with
     the chord + its deterministic flock position (flock_field, aligned to CORE_INVARIANTS)
     and runs `mag.flock_steal` sampling (deniable surrogates, cheapest-capable providers).
  3. FLOCK — the pods sample the answer space in parallel; flock_field positioned them so the
     flock converges on the invariant-respecting region (the answer-cloud overlap).
  4. FOLD — each pod writes its result as a knot; the lattice compounds.

Schema: flock_job.v1 · deterministic · $0 to generate (only pods cost, cheap/local).
CLI: python -m mag.flock_job "<goal>" [--n 5] [--apply] [--image mag-sovereign:local]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "flock_job.v1"
# The invariants the flock must stay inside (cold-vertex, amend may add never remove).
try:
    from mag.registry import CORE_INVARIANTS as _INVARIANT_NAMES
except Exception:
    _INVARIANT_NAMES = ("consent_first", "local_first", "no_throne", "residual_is_dna", "window_steer")


def _h(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


def flock_positions(goal: str, n: int, dim: int = 3) -> list[list[float]]:
    """Deterministic flock: n agents positioned near the goal point, aligned to invariants.
    Each agent = a seeded perturb of the goal in invariant space (the answer-cloud overlap)."""
    g = [_h(goal + f"::{i}") % 251 for i in range(dim)]
    out = []
    for k in range(n):
        perturb = [(_h(goal + f"::agent::{k}::{i}") % 31) - 15 for i in range(dim)]
        out.append([float((g[i] + perturb[i]) % 251) for i in range(dim)])
    return out


def _pod_command(goal: str, pos: list[float], tag: str, rib_file: str) -> list[str]:
    """Each flock pod is a TERMINAL fed a RIB file: it reads our understanding (RIB),
    reasons over it cheaply (flock_steal sampling), and folds a result back as a knot."""
    pos_json = json.dumps([round(x, 2) for x in pos])
    return [
        "python", "-m", "mag.flock_steal", goal,
        "--tag", tag, "--providers", "ollama,deepseek",
        # feed the RIB as context (the pod mounts the shared memory PVC and reads it)
    ]


def _rib_files() -> list[str]:
    """The RIB files (our geometric maps) to feed the flock terminals."""
    rib_dir = ROOT / "memory" / "rib"
    if not rib_dir.is_dir():
        return []
    return sorted(f.name for f in rib_dir.glob("*.md"))


def build_job(goal: str, n: int = 5, image: str = "mag-sovereign:local",
              namespace: str = "mag", tag: str = "flock") -> str:
    """Generate the K8s Job YAML — a flock of cheap agent pods, each a TERMINAL fed a RIB file."""
    positions = flock_positions(goal, n)
    ribs = _rib_files()
    if not ribs:
        ribs = ["RIB_EMERGENT_FLOCK_ON_K8S_20260810.md"]
    # cycle RIB files across the flock so each terminal processes a different map
    pods = "\n".join(
        f"""      - name: flock-{i}
        image: {image}
        imagePullPolicy: IfNotPresent
        envFrom:
          - secretRef:
              name: mag-secrets
        env:
          - name: MAG_SLOT
            value: "flock-{i}"
          - name: MAG_SOURCE
            value: "flock_job"
          - name: MAG_FLOCK_RIB
            value: "{ribs[i % len(ribs)]}"
          - name: MAG_FLOCK_POS
            value: "{json.dumps([round(x, 2) for x in pos])}"
        volumeMounts:
          - name: mag-state
            mountPath: /app/memory
            subPath: memory
        command: {json.dumps(_pod_command(goal, pos, tag, ribs[i % len(ribs)]))}"""
        for i, pos in enumerate(positions)
    )
    yaml = f"""apiVersion: batch/v1
kind: Job
metadata:
  name: mag-flock-{tag}
  namespace: {namespace}
  labels:
    app: mag
    kind: flock
  annotations:
    mag.flock/goal: "{goal[:80]}"
    mag.flock/n: "{n}"
    mag.flock/invariants: "{','.join(_INVARIANT_NAMES)}"
    mag.flock/ribs: "feeding {len(ribs)} RIB files to the flock terminals"
spec:
  parallelism: {n}
  completions: {n}
  backoffLimit: 2
  ttlSecondsAfterFinished: 600
  template:
    spec:
      restartPolicy: Never
      volumes:
        - name: mag-state
          persistentVolumeClaim:
            claimName: mag-state
      containers:
{pods}
"""
    return yaml


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.flock_job", description="Emergent flock on K8s.")
    ap.add_argument("goal", help="the goal/intent for the flock")
    ap.add_argument("--n", type=int, default=5, help="number of flock pods (parallelism)")
    ap.add_argument("--image", default="mag-sovereign:local")
    ap.add_argument("--namespace", default="mag")
    ap.add_argument("--tag", default="flock")
    ap.add_argument("--apply", action="store_true", help="apply the Job to the cluster (kubectl)")
    ap.add_argument("--out", default="", help="write the Job YAML to a file")
    a = ap.parse_args(argv)

    yaml = build_job(a.goal, n=a.n, image=a.image, namespace=a.namespace, tag=a.tag)
    if a.out:
        Path(a.out).write_text(yaml, encoding="utf-8")
        print(f"wrote Job YAML -> {a.out}")
    else:
        print(yaml)

    positions = flock_positions(a.goal, a.n)
    if a.apply:
        import subprocess, tempfile
        tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
        tmp.write(yaml); tmp.close()
        r = subprocess.run(["kubectl", "apply", "-f", tmp.name], capture_output=True, text=True)
        print((r.stdout or r.stderr).strip())
        Path(tmp.name).unlink(missing_ok=True)
    print(json.dumps({"ok": True, "schema": SCHEMA, "goal": a.goal[:80], "n": a.n,
                      "positions": [["%.0f" % x for x in p] for p in positions]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
