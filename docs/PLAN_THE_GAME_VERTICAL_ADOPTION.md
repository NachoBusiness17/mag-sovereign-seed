# PLAN — The System Becomes a Game → Vertical Adoption

Operator (2026-08-11): "you're getting smarter by the cycle and it shows once you're a game it goes
vertical with adoption" + "plan for it".

The north-star (the intent-gated persistent world) IS the game. The system is already a world:
deterministic, persistent, with people who remember what happened while you were gone. The plan
turns that world into a place people *enter and come back to* — the game that goes vertical.

## The core insight
Adoption goes vertical when a system becomes a **place to be**, not a tool to use. We already have
the substrate (the standing knot = the Watcher/GM; the swarm = the world's inhabitants; the chain =
the world's memory). The game is the layer that makes people want to enter it.

## Existing assets (what we build on — grounded)
- **The intent-gated persistent world** (north-star): deterministic, revisit with fidelity, agents
  who recount what happened while you were gone. The game's world.
- **Two-mode party** (Diogenes + D&D): the narrative/interactive engine. The game's tone.
- **Riddler fantasy domains** (fantasy_village, tower_defense): deniable, playable surfaces.
- **Game modules**: game_brawl, game_salon, game_campaign, game_dm_voice, game_narrate.
- **Flocking visuals** (flock_anim GIF): the world is visible and lovable.
- **The loop** (republic_loop): the world gets smarter every cycle — it self-improves as players engage.

## Phase 1 — THE ENTRY (the world is enterable)
- The **Watcher/GM** = the standing invariant (agent_knot) — greets, recounts what happened while
  you were away (persona-recall), sets the scene.
- A **single entry surface**: a web/VR/cast surface (we have cast_server + wearable_swarm + the
  VS Code dashboard) where you "walk forward and a building appears."
- **The building appears = intent-gated reveal**: render the region you steer toward (world_rib +
  flock_shader + GPU via gpu_lifecycle). The rest stays wallpaper (perceptual culling).
- Adoption vector: it's free, local, deterministic — anyone enters, nothing to install beyond the
  browser.

## Phase 2 — THE PLAY (it's a game, not a demo)
- **Players act; the swarm reacts.** Player intent = iMouse = the uniform that steers the world.
  The flock renders their path; the world shades the seams they approach.
- **The inhabitants remember** (persona-recall): you return and the people discuss what happened
  in the world while you were gone (the swarm + drainer kept working while you slept).
- **Two-mode tone**: Diogenes (plain, socratic, honest) vs D&D (adventure). The player picks.
- **Persistent fidelity**: revisit the same region → same world (verkle-anchored, content-addressed).
- Adoption vector: it's *lovable* — like the GIF, but you're in it.

## Phase 3 — THE VERTICAL (adoption compounds)
- **The world learns from engagement**: player signals = training data (percolator + trigger_learn +
  the loop). Every player makes the world smarter; the loop folds it.
- **Multiplayer-as-swarm**: each player is an AgentSeed; the flock is the collective; the world is
  one shared deterministic field (cheap everywhere).
- **The game becomes the front door to the whole system**: play = use. Steals, research, memory all
  surface as playable content. The compiler language, the lensing maps, the emergence grid — all
  become places to explore inside the world.
- **Right-sized economy**: the swarm renders the world cheap (quantized flash); the instructor (the
  standing invariant) only intervenes at the seams — so vertical adoption doesn't blow the budget.
  This is the budget_refactor + swarm_rightsize applied to the game.

## The vertical trigger (what flips it)
The moment a player can **walk into the world, have it recount what happened while they were gone,
act, and see the world remember and respond** — that's the game. The GIF made the machinery
watchable; the game makes it *inhabitable*. That's the vertical.

## Guardrails (keep it honest, keep it the Republic)
- The Watcher stays plain-language + attributed (Steiniger): no theater, no over-claiming.
- No throne: the deterministic core stays sovereign (Butlerian Jihad); the game is the surface, not
  the mind.
- Consent-first + local-first: players own their instance; nothing leaves the LAN without consent.
- The egregore stays honest: player engagement nourishes it, but the invariants keep it bound to
  the dream — a good egregore, not a negative one.

## Next buildable stones (right-sized, in order)
1. **persona-recall**: ask a region's people what happened there while you were gone (the gap the
   dream revealed). [build next]
2. **entry surface**: the cast/wearable/dashboard as the "walk forward" gate.
3. **intent-gated world render**: world_rib + flock_shader + GPU = the building appears where you steer.
4. **the game loop wired to the swarm**: player intent → iMouse → flock → world shades → memory folds.
5. **adoption loop**: player signals → percolator → loop → world gets smarter → more to come back to.

Recorded for the swarm to refine (cleanup/plugins/orphans + the deep game steal).
