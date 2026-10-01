# SHADERTOY RULE LATTICE — composition laws mined from the vendors (2026-09-03)

Built from intake card 20/25 (watch/INTAKE_THREEJS_SHADERTOY_20260903.md, operator GO).
Serves the shadow fields arc: B1a maze_arena GPU field, room_lightmap.html, steer_field.html,
and the FRM/fixed-point steal (docs/ref/ractors/RACTORS.md).

## Source ledger (all fetched raw 2026-09-03, read in full)

- **S1** mattdesl lwjgl-basics wiki, "2D Pixel Perfect Shadows" —
  https://raw.githubusercontent.com/wiki/mattdesl/lwjgl-basics/2D-Pixel-Perfect-Shadows.md
  (fetched via the raw door, 13,837 bytes)
- **S2** three.js manual, "Three.js and Shadertoy" —
  https://raw.githubusercontent.com/mrdoob/three.js/master/manual/en/shadertoy.html
- **S3** three.js manual, "Render Targets" —
  https://raw.githubusercontent.com/mrdoob/three.js/master/manual/en/rendertargets.html
- **S4** three.js manual, "Post Processing" —
  https://raw.githubusercontent.com/mrdoob/three.js/master/manual/en/post-processing.html
- **S5** three.js manual, "Indexed Textures" —
  https://raw.githubusercontent.com/mrdoob/three.js/master/manual/en/indexed-textures.html
- **S6** three.js manual, "Textures" —
  https://raw.githubusercontent.com/mrdoob/three.js/master/manual/en/textures.html

**UNFETCHED, on the record:** shadertoy.com/howitworks resisted six doors
(WebFetch 403; curl+UA "Bad request"; Wayback CDX zero captures; archive.today
CAPTCHA; r.jina.ai Cloudflare wall; browser skill unavailable to this subagent).
No card below cites it. Shadertoy's conventions (iTime, iResolution, iChannel,
mainImage) enter this lattice only through S2, which documents them vendor-to-vendor.

**License hygiene:** iq/Daedelus example shaders are CC BY-NC-SA — never vendored.
Steal the technique, write our own GLSL. three.js manual text: MIT (three.js repo).
mattdesl wiki: cite-and-link, technique-level steal only.

---

## GROUP A — PASS GRAPHS (S1: the 1D radial lightmap, stolen whole)

### A1 — Buffer first, sample later
- **RULE:** Render the scene's answer into an offscreen buffer once, then let every downstream pass sample that buffer instead of re-deriving it per pixel.
- **SOURCE:** S1, "Step 1: Render To Occlusion Map" — "render an 'occlusion map' to an FBO. This way, our shader can sample our scene."
- **FLEET USE:** the bay: FIELD.json is the occlusion map — compute the field once, and every surface (maze_arena.html, room_lightmap.html, steer_field.html) only samples it.

### A2 — One pass, one question
- **RULE:** Split the render into a fixed chain of passes where each pass answers exactly one question and hands its answer to the next.
- **SOURCE:** S1, "Intro" — "The basic steps involved are (1) render occluders to a FBO, (2) build a 1D shadow map, (3) render shadows and sprites."
- **FLEET USE:** organ decomposition: the bay answers "what is the field", the surfaces answer "how do I show it" — never fuse the two into one organ.

### A3 — Center the frame on the query point
- **RULE:** Put the query origin at the center of the buffer so every ray becomes a trivial function of position.
- **SOURCE:** S1, "Step 1: Render To Occlusion Map" — "Our algorithm will expect the light to be at the center of this 'occlusion map.'"
- **FLEET USE:** maze_arena.html: anchor the GPU field's coordinate frame on the walker/cheese pair, not on canvas pixels.

### A4 — One power-of-two size for every intermediate
- **RULE:** Fix all intermediate buffers to the same square power-of-two size so passes stay composable and the resolution is a named constant, not an accident.
- **SOURCE:** S1, "Step 1: Render To Occlusion Map" — "We use a square power-of-two size for simplicity's sake; this will be the size of our light falloff, as well as the size of our various FBOs."
- **FLEET USE:** maze_arena.html B1a: the field texture is e.g. 256x256 regardless of dashboard canvas — the det spine at fixed resolution.

### A5 — Encode membership in a channel, decode at read
- **RULE:** Store categorical facts (occluder or not) as a single channel value and decode them with one fixed threshold at the read site.
- **SOURCE:** S1, "Step 1" + "Step 2" GLSL — "only rely on sampling from the alpha channel"; `const float THRESHOLD = 0.75;`
- **FLEET USE:** room_lightmap.html: invariants/failure classes ride as channels in the light film; the reading surface owns the threshold.

### A6 — The lookup is a first-hit reduction
- **RULE:** When precomputing a distance/ray map, reduce with a minimum — each texel stores the first hit and nothing downstream ever looks further.
- **SOURCE:** S1, "Step 2" — "Each pixel in the resulting 1D shadow map describes the *minimum distance to the first occluder for that ray's angle*"; GLSL: `distance = min(distance, dst);`
- **FLEET USE:** maze_arena.html: the BFS field is the same reduction — per-cell first-hit distance to the cheese; the GPU pass is a min-reduction, walkers read only the winner.

### A7 — Downgrade dimensionality before you compute
- **RULE:** Compress a 2D query space into a 1D lookup (angle to distance) before the expensive pass; dimension you remove is fill-rate you never pay.
- **SOURCE:** S1, "Step 2: Build a 1D Shadow Map Lookup Texture" — "Now we need to build a 1D lookup texture, which will be used as our shadow/light map. The texture is very small (256x1 pixels)."
- **FLEET USE:** the FRM/fixed-point steal: fold a space of objections into a 1D per-axis verdict before a refinement round; same move the bay makes on the field.

### A8 — Bake hard, sample smooth, wrap circular domains
- **RULE:** Build lookup textures with hard per-texel writes, consume them with linear filtering, and set RepeatWrapping on any axis whose domain is circular.
- **SOURCE:** S1, "Step 2" Java setup — "use linear filtering and repeat wrap mode when sampling" (on the 1D shadow map whose x-axis is 360 degrees of angle).
- **FLEET USE:** steer_field.html: render FIELD.json crisp, let gradient sampling interpolate; heading angles wrap.

### A9 — Soft edges come from breadth, not geometry
- **RULE:** Blur by summing multiple samples along the lookup axis with a fixed Gaussian kernel — softness is a sampling decision, not a geometry change.
- **SOURCE:** S1, "Step 3. Blur & Render Lights" — "In order to create blurred edges, we need to sample multiple angles, and sum the results together using a gaussian distribution."
- **FLEET USE:** room_lightmap.html: invariant edges soften by kernel width in the shader; the invariants themselves never move.

### A10 — Uncertainty grows as signal fades
- **RULE:** Scale the blur radius by distance from the source so the answer is sharp near the origin and soft where it stops mattering.
- **SOURCE:** S1, "Step 3" GLSL — "we multiply the blur amount by our distance from center / this leads to more blurriness as the shadow 'fades away'" (`float blur = (1./resolution.x) * smoothstep(0., 1., r);`).
- **FLEET USE:** room_lightmap.html: invariant confidence falls off with distance from its evidence source — the lighting IS the epistemology.

### A11 — Lights composite additively
- **RULE:** Render each light independently and add the results; never build one mega-pass that computes all lights at once.
- **SOURCE:** S1, "Step 3" — "With a few different lights and some additive blending, we can get some very pretty per-pixel soft shadows."
- **FLEET USE:** room_lightmap.html: each invariant is its own light; the room's total illumination is the additive sum — no fused pass.

### A12 — Budget fill-rate before features
- **RULE:** Before adding a per-pixel pass, price it as lights-times-pixels fill cost and cap the count.
- **SOURCE:** S1, "Optimizations" — "On my Mac OSX 10.6.6 (GeForce 9400), I can add about 20 lights before fill-rate becomes a bottleneck."
- **FLEET USE:** maze_arena.html B1a: one field pass plus at most N sampled divergence points per frame — no per-frame full-field readback.

### A13 — Admit when geometry beats pixels
- **RULE:** Say out loud when a per-pixel technique is the wrong tool, and steal it anyway only where per-pixel is the point.
- **SOURCE:** S1, "Intro" — "this is generally less performant than geometry shadows (which are not per-pixel)."
- **FLEET USE:** B1b stays queued behind real 3D occluder geometry in THE ROOM; until then the room lights itself the cheap way.

---

## GROUP B — THE VENDOR RECIPE (S2: three.js and Shadertoy)

### B1 — The fullscreen quad is the pass harness
- **RULE:** Turn any fragment shader into a full-canvas pass with a 2x2 plane under an orthographic camera — the geometry is scaffolding, the fragment is the program.
- **SOURCE:** S2, fullscreen section — `new THREE.PlaneGeometry(2, 2)` with `new THREE.OrthographicCamera(-1, 1, 1, -1, -1, 1)` "will fill the canvas."
- **FLEET USE:** maze_arena.html B1a: the raw WebGL2 equivalent is one triangle covering clip space — zero dependencies, STATIC RENDER LAW intact.

### B2 — Site globals are conventions; declare and feed them yourself
- **RULE:** Treat iTime/iResolution/iChannel0 as a host contract, not GLSL: declare them as uniforms and set them from the host every frame.
- **SOURCE:** S2, uniforms section — "all of them are specific to shadertoy. They not official GLSL variables. They are variables the makers of shadertoy made up."
- **FLEET USE:** every organ: FIELD.json values enter the shader as declared uniforms — the fleet defines its own uniform contract once and all surfaces honor it.

### B3 — Convert units at the boundary
- **RULE:** Normalize host values (ms to seconds, pixels to normalized coords) once where the host feeds the uniform, never inside the shader.
- **SOURCE:** S2, render loop — `time *= 0.001; // convert to seconds` before `uniforms.iTime.value = time;` and `uniforms.iResolution.value.set(canvas.width, canvas.height, 1);`
- **FLEET USE:** the bay's CLOCK convention: one timestamp unit fleet-wide; surfaces convert at their edge only.

### B4 — Wrap the stolen kernel, don't fork it
- **RULE:** Insert guest shader code verbatim behind a tiny host-written `main()` that maps official GLSL globals onto the guest's convention.
- **SOURCE:** S2, wrapper code — `void main() { mainImage(gl_FragColor, gl_FragCoord.xy); }` ("Then we inserted the shader GLSL code from shadertoy").
- **FLEET USE:** license hygiene made structural: the wrap seam is where technique-steal happens without vendoring CC BY-NC-SA example code — our main, their shape, never their pixels.

### B5 — One shader, two bodies
- **RULE:** The same fragment kernel serves fullscreen (coords from pixels) and per-surface (coords from an interpolated vUv varying) — only the coordinate feeder changes.
- **SOURCE:** S2, procedural texture section — "fragCoord does not have to come from pixel coordinates, we could use something else like texture coordinates"; `mainImage(gl_FragColor, vUv * iResolution.xy);`
- **FLEET USE:** B1b: THE ROOM's walls carry the field as procedural texture — the room presents the solved problem IN LIGHT on its own geometry.

### B6 — Know the toy tax before you pay it
- **RULE:** Per-pixel everything-in-a-function rendering costs orders of magnitude over triangle-based scenes; count the tax, then decide on purpose.
- **SOURCE:** S2, intro and closing — "Fullscreen on my GPU it runs at about 5 frames a second" vs Cities: Skylines at "30-60 frames a second"; "it is not best practice."
- **FLEET USE:** STATIC RENDER LAW: fleet surfaces stay cheap-first — premium per-pixel work is reserved for the one organ where the field IS the content (maze_arena B1a).

---

## GROUP C — BUFFERS AND CHAINS (S3 + S4)

### C1 — A render target is just a texture you rendered into
- **RULE:** Treat every pass output as an ordinary texture the moment it lands, so the pass graph is textures all the way down.
- **SOURCE:** S3, opening line — "A render target in three.js is basically a texture you can render to. After you render to it you can use that texture like any other texture."
- **FLEET USE:** files feed organs feed surfaces: each organ's receipt file is the next organ's input texture — the dataflow law rendered in GPU terms.

### C2 — Size the target for its consumer
- **RULE:** Set a buffer's size and aspect to what consumes it, not to the display canvas.
- **SOURCE:** S3, notes — "The correct aspect to use depends on what we are rendering for"; resize section: `renderTarget.setSize(canvas.width, canvas.height)` only when the canvas itself is the consumer.
- **FLEET USE:** steer_field.html: the field grid renders at FIELD.json's native resolution and the dashboard scales it — never the reverse.

### C3 — Ping-pong two buffers toward a fixed point
- **RULE:** Run a chain of passes by alternating read/write between two buffers, swapping after each pass, until the last pass — and only the last — writes to screen.
- **SOURCE:** S4, "It's a little bit important to understand how EffectComposer functions" — "rtA is passed to the next pass... writes the results to rtB. rtB is then passed to the next pass which uses rtB as input and writes back to rtA"; `needsSwap`; "the last pass in the pass chain is automatically rendered to screen."
- **FLEET USE:** the FRM/fixed-point steal verbatim: refinement rounds ping-pong the artifact until no surviving objection changes it — convergence is `needsSwap` reaching a round that writes nothing new.

### C4 — One canonical name per seam
- **RULE:** Standardize the input name every pass reads its predecessor through, so any pass can be swapped into any slot.
- **SOURCE:** S4, ShaderPass section — "tDiffuse is the name that ShaderPass uses to pass in the previous pass's result texture so we pretty much always need that."
- **FLEET USE:** the wires: steer_bus_receipts.jsonl, room.jsonl kinds, FIELD.json — one fixed name per seam; the wire.split bug (filename split, 2026-09-03) is this rule violated.

### C5 — Passes are dataflow with kill switches
- **RULE:** Give every pass explicit enabled/clear/swap flags so a chain is reconfigured, not rewritten.
- **SOURCE:** S4, "Each Pass has 4 basic options" — `enabled`, `needsSwap`, `clear`, `renderToScreen`.
- **FLEET USE:** organ wiring: any surface's lightmap/GPS layer can be toggled off (lightmap GPS on/off receipt in the shadow fields falsifier) without deleting the organ.

---

## GROUP D — DATA AS TEXTURE (S5 + S6)

### D1 — Separate the data plane from the color plane
- **RULE:** Keep the texture that means ("this pixel is id 3") apart from the texture that looks ("id 3 is red"), and join them in the shader.
- **SOURCE:** S5, paletted graphics section — "we already have a texture... that has a different id per country. So, we could use that same texture through a palette texture to give each country its own color."
- **FLEET USE:** FIELD.json (meaning) feeds a uniform/texture; steer_field.html's palette (looks) is swappable — Britney content-borne steering made literal: FIELD.json to pixels.

### D2 — Nearest-filter data or you will invent facts
- **RULE:** Force NearestFilter on any texture holding ids or measurements — linear interpolation of data fabricates values that never existed.
- **SOURCE:** S5, code — `indexTexture.minFilter = THREE.NearestFilter; indexTexture.magFilter = THREE.NearestFilter;` (and again for the palette DataTexture); S6 "Filtering and Mips" for what Linear blends.
- **FLEET USE:** maze_arena.html divergence receipt: sampling the GPU field must return exact cell values — a blended sample would fake agreement between GPU and CPU legs.

### D3 — Read back surgically, never wholesale
- **RULE:** When the CPU needs a GPU answer, render a 1x1 target and read the few bytes under the question.
- **SOURCE:** S5, GPUPickHelper — "create a 1x1 pixel render target"... `renderer.readRenderTargetPixels(pickingTexture, 0, 0, 1, 1, pixelBuffer);`
- **FLEET USE:** maze_arena.html B1a falsifier: N-point GPU-vs-CPU divergence check samples N points per frame — no full-field per-frame readback, ever.

### D4 — The host owns the dirty flag
- **RULE:** Raw data written into a texture reaches the GPU only when the host raises the update flag — make that write explicit and single-owner.
- **SOURCE:** S5, palette — "Anytime we want three.js to update the palette texture with the contents of the palette array we need to set paletteTexture.needsUpdate to true."
- **FLEET USE:** room.jsonl and the queue: a receipt exists only once written to the file (chain over chat); unflagged mutations are the fleet's equivalent of a stale texture.

### D5 — GPU memory bills dimensions, not file size
- **RULE:** Size textures by what they must hold — the GPU pays width-times-height-times-4 regardless of compression.
- **SOURCE:** S6, "Memory Usage" — "textures take width * height * 4 * 1.33 bytes of memory"; "a JPG doesn't use less memory than a PNG in WebGL."
- **FLEET USE:** the bay: FIELD.json and its derived textures are sized to the decision they serve (256x1 shadow map, not 4K vanity), keeping every surface phone-renderable.

---

## The one to steal first

**C3** — ping-pong two buffers toward a fixed point. It is the FRM already running in GPU space, it powers A1-A12 whenever the field needs feedback passes, and it ends in a halting condition the fleet can receipt: a swap round that writes nothing new.

## Provenance

- Fetch doors that worked: raw.githubusercontent.com (wiki + master branch), api.github.com for the manual listing.
- Fetch doors that failed on shadertoy.com: WebFetch (403), curl+UA (Bad request), Wayback CDX (zero captures), archive.today (CAPTCHA), r.jina.ai (Cloudflare), browser skill (unavailable to subagent). Two-strike bail honored per door family; no card cites unverified text.
- Card count: 28 (A1-A13, B1-B6, C1-C5, D1-D5). Receipt row: watch/room.jsonl, kind organ.built.
