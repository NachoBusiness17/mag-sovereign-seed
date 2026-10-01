# Warm blade image — snapshot loop (OPERATOR-GO to spend)

Bind: `ollama/ollama:latest` (ssh6 proxy law), `blade_templates.json`, `boot_watcher.py` READY phase, `launch_vast.py` body shape.

## Why

Cold `ollama pull` on each rent is tens of minutes. Warm image = pull once, snapshot, next boots in minutes. Same idea as frozen RIB: pay the context tax once.

## Loop (files now; last step spends)

1. **Launch cheap box** — existing buyer/gates, `ollama/ollama:latest`, SSH. *Not this job.*
2. **Build/pull once** — on that box (or a local docker build when GO):
   ```
   docker build -f docker/Dockerfile.blade -t mag-blade-warm:latest .
   ```
   `docker/warm_preload.sh` reads the registry at **runtime** (`BLADE_TEMPLATES` or `/root/blade_templates.json` overlay). Adding a model to `state/vast/blade_templates.json` `models` (or `ollama pull` in onstart) does not require a Dockerfile edit; a **new snapshot** is needed to bake the weights.
3. **Vast snapshot as private image** — instance menu → Save as Template / create template from instance. **OPERATOR-GO: this spends** (storage + snapshot time). Do not run from a seat without the word.
4. **Registry `warm_image` field** — after snapshot, each eligible template row gains `"warm_image": "<private vast image or template_hash>"`. `blade_buyer.pick_template` already prefers `image`; next beat can prefer `warm_image` when set. Empty today.
5. **Next launches** use `warm_image` so onstart is nearly READY immediately. boot_watcher still requires `/root/status.json` `"phase":"READY"`.

## Status.json (boot_watcher)

Same as `blade_buyer` ONSTART / `boot_watcher.py` probe:

- `/root/status.json` (blade) or `/root/brain/status.json` (brain)
- JSON contains `"phase": "<boot|pull|READY>"`
- SUCCESS when `phase == READY`

## Forbidden without GO

`docker build`, `docker push`, vast snapshot, instance create, covenant edits.
