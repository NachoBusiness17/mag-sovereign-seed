# How to Boot This Machine

*A plain rebuild guide. Written so a competent stranger can stand this system up from the
code + the seal + the keys. No internal vocabulary required.*

---

## What you need (the rebuild kit)

1. **The code** — this repository, as-is. It is the actual specification.
2. **The seal** — `memory/seals/` (a verified, signed snapshot of the memory: the chain, the
   ledgers, the doctrine). Without it the machine boots with an empty memory — a body with
   no self.
3. **The keys** — `.env` (one line per provider API key). Without it the machine has no fuel
   and can't answer anything.

The machine is Python 3.11+. Everything else is re-derivable from the repo.

## 1. Local boot (one machine)

```powershell
# create the virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# make your .env from the example, fill in keys
Copy-Item .env.example .env

# the self: if you have a seal, put memory/seals/ back in place
# (the verkle chain lives at memory/biography/verkle_chain.jsonl)

# boot the REST backend (FastAPI)
python main.py api --host 127.0.0.1 --port 8001

# boot the dashboard surface (port 8765)
python main.py dash --port 8765

# run one tick of the loop (or a full standing window)
python -m mag.chord_circuit ring
python -m mag.standing run --window 360
```

Health check: `GET http://127.0.0.1:8765/api/v1/health` returns 200.

## 2. Container boot (Docker)

The `Dockerfile` builds the whole stack in a cage: `MAG_CONTAINER=1`, ports 8765 + 8000,
entrypoint `scripts/container/entrypoint.sh`. It needs the same three things mounted in:
`memory/` (the self), `.env` (the fuel), `state/`.

```bash
docker build -t mag-sovereign:local .
docker run -p 8765:8765 -p 8001:8000 \
  -v "$PWD/memory:/app/memory" -v "$PWD/.env:/app/.env" \
  mag-sovereign:local
```

## 3. Kubernetes boot (the always-on shape)

The manifests are in `deploy/k8s/` — a complete stack:

| Manifest | What it is |
|---|---|
| `00-namespace.yaml` | the namespace |
| `mag-deployment.yaml` | the main pod (dashboard + backend, port 8765) |
| `mag-service.yaml` | exposes it |
| `mag-configmap.yaml` / `mag-secret.yaml` | config + keys (the fuel lives here in a cluster) |
| `mag-pvc.yaml` | the shared disk where `memory/` lives (the self survives pod restarts) |
| `mag-cronjob.yaml` / `mag-swarm-cronjob.yaml` | the periodic loops |
| `ollama.yaml`, `redis.yaml` | local model + coordination services |

Apply in order: namespace → configmap/secret → pvc → deployment/service → cronjobs.

```bash
kubectl apply -f deploy/k8s/
```

## 4. Where the self lives (what to back up and restore)

| Path | What it is | Restore rule |
|---|---|---|
| `memory/biography/verkle_chain.jsonl` | the chain — the identity, every decision | restore from the seal |
| `memory/seals/` | verified snapshots of everything above | the rebuild kit's core |
| `memory/percolator/` | the saved knowledge (invariants + explore queue) | restore with the seal |
| `memory/rib/` | the doctrine entries | in the repo |
| `state/` | small pointers (seal latest, manifests, window state) | re-derivable |
| `.env` | all provider keys | you must supply these; never commit |

## 5. First-run sequence (the honest order)

1. Put the seal in place → the memory returns (chain, ledgers, doctrine).
2. Put `.env` in place → the fuel returns.
3. `python -m mag.seal verify` → confirm the restored self is intact (hashes match).
4. `python -m mag.persona_key baseline` → confirm the operator key is calibrated.
5. `python -m mag.standing run --window 360` → the loop stands; it seals on cadence.

## The catch (honest)

- **No seal, no self.** The code alone is an empty body. The chain is the identity, and the
  chain is in `memory/` — which is why the seal is the load-bearing artifact.
- **No keys, no fuel.** `.env` is the only secret store; it is never committed and never
  pushed anywhere.
- **This repo is sovereign-private.** Nothing here is pushed to public GitHub by design.
  If you clone it, keep it private.
- **The two REST ports are the whole surface.** Everything else is internal machinery; a
  stranger only needs `:8001` (API) and `:8765` (dashboard) to operate it.
