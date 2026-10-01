# MESH PIPELINE v0 — image → .glb → dungeon surfaces (2026-09-03)

Fleet build from intake card `watch/INTAKE_MESH_BAKER_20260903.md` (score 20/25 BUILD NOW).
Provenance: herbst (@hybridherbst) / needle.tools — mesh-baker, image-to-3D locally in the
browser, running Microsoft's TRELLIS entirely on the visitor's GPU. Post fetched 2026-09-03
~00:15Z (93.2K views, 1,968 likes, 2,661 bookmarks — bookmarks > likes, the practitioner
save-signal). Demo: https://mesh-baker.needle.tools

## The pipeline

```
image  ──►  mesh-baker.needle.tools   ──►  .glb  ──►  dashboard/static/mesh_gallery.html  ──►  dungeon surfaces
            (external free bakery,          (the        (zero-fetch drop-zone, inline
             runs on the VISITOR's GPU       bake)       GLB parser + raw WebGL, room
             via TRELLIS, 1–3 min)                       aesthetic, turntable + wireframe)
```

The fleet bakes nothing; it curates. The bakery is the author's free public tool and the
compute is the visitor's own GPU — $0 per mesh, no vendor account, no API key.

1. Operator picks a source image (screenshot, render, photo).
2. Browser open → mesh-baker.needle.tools → drop image → wait 1–3 min → download .glb.
3. Open `dashboard/static/mesh_gallery.html` (any static server or file://) → drop the .glb.
4. Read the calibrator panel: triangles, vertices, bbox, band (LOW/MID/HIGH).
5. Meshes that pass the band check graduate into the dungeon surfaces (room_game,
   maze_arena lineage) as curated assets.

## TRELLIS LICENSE CHECK — TODO (tri-state, open)

- **Unproven**: TRELLIS (Microsoft, image-to-3D) repo license and commercial terms were
  NOT fetched at intake. Before any mesh baked from the bakery is used beyond personal /
  fleet-internal surfaces, someone must: (a) find the TRELLIS repo, (b) read its license
  (MIT? non-commercial?), (c) check needle.tools' own terms for the hosted bakery, and
  (d) record the verdict here with the license file link. Until then: bake for the room,
  do not ship baked meshes as product.
- **Supported**: the post + demo site exist and were fetched via mirror; engagement
  numbers are at-fetch snapshots.
- **Disputed**: none.

## THE DECIMATION LAW (the calibrator's chair)

**High-poly in, silhouette kept, low-poly out.**

TRELLIS bakes dense — that is its job. The dungeon cannot render dense. The gallery's
calibrator panel is the law made visible:

- band LOW (< 50k tris): dungeon-ready as baked
- band MID (50k–300k): keep it, decimate later — the silhouette survives decimation,
  interior density does not
- band HIGH (> 300k): decimate BEFORE dungeon use; a mesh that enters the dungeon dense
  taxes every frame it appears in

v0 of the gallery measures; it does not decimate. The decimator itself is a later organ
(the vram_hologram arc, operator 2026-08-12: "high-poly to low-poly as an engine").

## ROCINANTE TIE

Browser-local inference is the serving substrate's little brother: a page that COMPUTES
on the visitor's machine without a server is the same law as a Mac Studio cluster serving
inference without the cloud. When ROCINANTE lands (4x Mac Studio M5 Ultra, Oct 27), the
M5s run the bigger baker — full TRELLIS or successor models, batch, overnight — and the
browser gallery stays the curation and calibration surface. Zero-fetch doctrine holds at
both scales: surfaces that compute without servers, files that carry the state.

## The gallery surface (what v0 does)

`dashboard/static/mesh_gallery.html` — single file, zero network at load AND at render
time. No CDN, no three.js: the GLB/glTF parser and the renderer are inline (raw WebGL 1).

- drop .glb (or .gltf + its .bin in the same drag; data-URI buffers supported)
- inline parser: GLB container → JSON + BIN chunks, buffer views (strided ok), accessors,
  node TRS/matrix hierarchy, world-space bbox; computes flat normals when the bake has none
- render: dark-field room aesthetic (#030806, cyan rim light), turntable, orbit + zoom,
  wireframe toggle (W, accent-cyan lines over dark fill), floor grid (G), reset (R)
- calibrator readout: triangles, vertices, mesh/primitive counts, parse ms, file size,
  bbox X·Y·Z, normals provenance, LOW/MID/HIGH band
- honest refusals: draco/meshopt compression, sparse accessors, non-TRIANGLES modes —
  named in the status line, never silently faked

## Verification receipt (2026-09-03)

- 15/15 parser assertions pass in a node harness (synthetic GLB with node transform,
  .gltf with data-URI buffer, strided bufferView, draco refusal, external .bin resolution).
- Full inline script passes `node --check`.
- **Unproven**: the WebGL render itself was NOT eye-verified (no browser in the build
  lane). First human to open the file is the render verifier.

---

# MOTION — text → skeleton animation → .glb (2026-09-04)

Fleet build from intake card `watch/INTAKE_KIMODO_CPP_20260904.md` (20/25 BUILD NOW,
operator GO). Organ: `kimodo.cpp` (localai-org, Apache-2.0) — GGML/C++ port of NVIDIA
Kimodo text-to-motion. First natural-language→animation clip generated on this box.

## The motion pipeline (measured, 2026-09-04)

```
"walk forward and wave"
  ──► kmd-generate (kimodo.cpp, CPU, in container kimodo-build)
  ──► root_positions.f32 + local_rotations_xyzw.f32   (120 frames, 30 joints, 4s @ 30fps)
  ──► scripts/export_glb.py        ──► kimodo_walk_wave.glb        (animated skinned GLB)
  ──► watch/organs/kimodo/export_strip.py ──► kimodo_walk_wave_strip.glb (static pose strip)
  ──► dashboard/static/ (beside mesh_gallery.html, drag-drop to view)
```

Load path: `dashboard/static/kimodo_walk_wave.glb` and
`dashboard/static/kimodo_walk_wave_strip.glb` — drop either onto
`dashboard/static/mesh_gallery.html` (or the same path served over HTTP). Raw
buffers + prompt + provenance: `watch/organs/kimodo/clip_20260904/`.

## LICENSE GUARD (verified, both levels)

- **Pinned checkpoint: Kimodo-SOMA-RP-v1.1-GGML** (HF `LocalAI-io`), 1.13 GB F32 GGUF —
  **NVIDIA Open Model License, commercial use permitted** (model card states the
  conversion "grants no additional rights" and remains under the Open Model License).
- Text bundle `Llama-3-Kimodo-GGML`: Meta Llama 3 Community License + MIT LLM2Vec
  adapters — reviewed before download.
- **FORBIDDEN (card law, held)**: the SMPL-X RP v1 checkpoint — NVIDIA Internal
  Scientific R&D license, NON-COMMERCIAL, derivative redistribution prohibited. It is
  deliberately absent from the download installer. Never pulled, never will be from a
  fleet lane.
- Download integrity: the repo's `download_gguf_weights.sh` verified manifest format
  `kimodo-gguf-manifest-v1` + per-file SHA-256 for both bundles before use.

## Measured facts (this box, 2026-09-04)

- Build: Ubuntu 24.04 container (`kimodo-build`), GCC 13, CMake 3.28 + Ninja,
  CPU-only (`-DKIMODO_BUILD_TESTS=OFF -DKIMODO_ENABLE_VULKAN=OFF`). 87/87 targets,
  zero errors. Native Windows toolchain absent on this box (no cmake/MSVC/gcc on PATH,
  no VS install) — Docker was the sanctioned lane, not a workaround.
- Generation: 120 frames, 25 DDIM steps, seed 42, prompt "walk forward and wave" →
  **8m17s wall** on 16 cores (~87 CPU-min; ~1350% CPU, ~17 GB RAM for the F32
  Llama-3-based text encoder + diffusion). The clip: root travels **6.21 m along +z**
  (1.55 m/s walk), hip height oscillates 0.91–1.01 m (gait bob), right-arm joint
  deviation swings up to 104° (the wave). All 3600 quats unit-norm — non-degenerate.
- Verification: both GLBs parsed clean (0 warnings) through the gallery's own inline
  PURE PARSER extracted into a node harness — animated: 360 tris / 31 anim channels /
  1 skin; strip: 2088 tris spanning the walk path z −0.52→6.47.

## Honest state (what the gallery shows vs what the file holds)

- `kimodo_walk_wave.glb` holds the REAL animated skinned rig (glTF 2.0 animation, 31
  channels, skin + inverse bind matrices). Gallery v0 renders **static geometry only** —
  it shows this file's bind pose (a standing bone-figure, 360 tris). The motion is in
  the file, not yet on that surface.
- `kimodo_walk_wave_strip.glb` is the v0-visible projection: 12 real poses sampled from
  the clip, baked into one static mesh (onion-skin strip, vertex colors gold→cyan =
  time). Every vertex comes from the generated clip — nothing hand-animated.
- Gallery animation playback (skinning + sampler interpolation in the raw-WebGL
  renderer) is the next organ; until then the strip is how the dungeon sees motion.
- No retarget to a Mixamo-style external rig was needed for this artifact: SOMA's
  30-joint control skeleton IS the exported rig. Retarget to other glb rigs remains
  **Unproven** (not attempted this session — that was the >1-session kill line, and it
  was not crossed).

## Regeneration

`docker start kimodo-build` (weights persist inside: ~16 GB GGUF, manifest-verified),
then `docker exec kimodo-build /kimodo/build/kmd-generate /kimodo/models/kimodo-soma-rp-v1.1-f32.gguf
/kimodo/generated/llm2vec-text-bundle PROMPT.txt 120 25 42 /kimodo/output_motion`,
copy the two .f32 files out, re-run the two exporters. If the container is ever
deleted, rebuild is: clone + `scripts/download_gguf_weights.sh --model soma-rp-v1.1`.

