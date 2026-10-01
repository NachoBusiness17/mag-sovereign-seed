# Verkle and the dashboard: intent, history, and honest next design

**As of:** 2026-08-06  
**Purpose:** Make portable, evidence-backed context artifacts that can be handed to agents, while keeping their continuity and relationships visually understandable.

## The core object

A **Verkle knot** is the handoff object. It is a physical file-backed packet representing the underlying workday/session data: source artifact, operator intent, relevant transcript or residual, commitments, relationships, and plain-language meaning. An agent should be able to receive a knot instead of a whole chat history and still know what happened, why it matters, and where to verify it.

The **Verkle lattice** is not the object being handed off. It is the visual and relational index of knots. The torus-knot geometry gives each artifact a recognizable physical identity; the evidence fields make it operational rather than ornamental.

## What Mag was trying to build

The original object was not a decorative graph. It was a durable memory instrument:

1. A work session becomes a residual dossier and one living leaf.
2. The leaf content receives a SHA-256 commitment.
3. Session leaves are combined into a Merkle-style root on local disk.
4. The current root, chain rows, and leaf files let Mag reload history and audit mismatches.
5. A visual layer makes the otherwise invisible continuity explorable as days, themes, turns, runs, and commitments.

The deeper product intent is “one cold vertex”: conversations and model weights are replaceable; filed artifacts and their provenance are the portable memory.

## How the dashboard evolved

| Stage | Intended job | What remains |
|---|---|---|
| Early Verkle map | Make the current history tip and prior steps visible | Legacy Overview and Lattice/History panels |
| Diary and Story | Explain the journey in human language, not hashes | Rich Story renderer and structured Diary API, formerly separate windows |
| Tapestry | Put days and their relationships into one spatial worklog | 3D helix, day beads, turns, runs, documents |
| Torus-knot visual pass (`a44b718`) | Give continuity leaves a distinctive, beautiful topology | Cyan torus-knot anchors and temperature grammar |
| Dashboard consolidation | Reduce redundant pages by folding history into Days | Timeline survived; Diary, Pulse, and Story were embedded through fragile aliases |

The consolidation had the right destination but the wrong seam. The Days buttons were wired from Desk initialization. Diary displayed a structured API as if it were plain text. Story rendered into an old hidden window and copied the markup, losing behavior. “Arc” also hid the familiar “Story so far” name.

## Three objects currently called a lattice

| Object | Real guarantee | Storage | Dashboard role |
|---|---|---|---|
| Session commitment chain | Detectable content commitment when tip, chain, and leaves are audited together | `memory/biography/verkle_tip.json`, `verkle_chain.jsonl`, `knots/` | Cyan continuity anchors |
| Topic/evidence lattice | Queryable operational relationships; not part of the session tip | `memory/lattice/nodes.jsonl`, `edges.jsonl` | History/plan and agent lookup |
| Tapestry scene | A derived visualization pack | generated from residual registry, timeline, runs, and tip | Days 3D canvas |

Mag calls the first a “Verkle-style” or “Merkle–Verkle hybrid,” but the implementation is a binary SHA-256 Merkle root rebuilt over session leaf hashes. It does not implement a cryptographic Verkle tree, polynomial commitments, KZG, IPA proofs, or membership witnesses. The public “story root” is also explicitly a narrative fidelity key, not the disk tip. The interface must never merge those claims.

## What is now repaired

- Days owns its own navigation lifecycle; it no longer depends on visiting Desk first.
- Diary renders the structured filed narrative as readable chapters.
- Pulse remains the recent-change lens sourced from Chronicle.
- “Story so far” is restored by name and retains its rich thesis, journey, artifacts, and file actions.
- “Proof lattice” is renamed **Continuity chain**, with an explicit non-cryptographic explanation.
- The chain-tip description now says it must be audited to detect drift or gaps; merely drawing a node is not proof.

## Better target: one history, four lenses

Days should be the single continuity home:

1. **Timeline** — spatial evidence map: when work happened and how filed objects connect.
2. **Diary** — chronological human narrative reconstructed from residuals.
3. **Pulse** — recent change, open loops, warnings, and current attention.
4. **Story so far** — durable thesis, phases, reasons, artifacts, and honest unresolved tensions.

All four should eventually share one selected day and one evidence drawer. Selecting a bead, diary entry, pulse event, or story artifact should reveal the same fields: source path, leaf hash, parent/root at filing, current audit status, relationships, and the plain-language “what / where / why.”

## Next high-value build

Add a small continuity-health strip above the 3D scene:

- committed session leaves versus rendered chain anchors;
- audit state: clean, warning, missing file, orphan residual, or root mismatch;
- current tip short hash and last audit time;
- legend separating committed history, inferred relationships, and ordinary visual grouping.

Then make each cyan anchor selectable. Its inspector should show the exact leaf and chain row rather than temperature metaphors alone. This keeps the visual magic while making it operationally useful for restore, diagnosis, and autonomous coding handoffs.

## Evidence consulted

- `docs/ref/TAPESTRY_VERKLE_VISUAL.md`
- `docs/ref/strike_origin.md`
- `docs/DNA.md`
- `docs/HOW_TO_MAG_DASHBOARD.md`
- `docs/ref/run_trail_lattice.md`
- `mag/verkle_knot.py`
- `mag/verkle_audit.py`
- `mag/tapestry.py`
- `mag/tapestry_visual.py`
- dashboard history including commit `a44b718` (“Days tapestry: Steiniger temp shapes + Verkle torus-knot lattice”)
