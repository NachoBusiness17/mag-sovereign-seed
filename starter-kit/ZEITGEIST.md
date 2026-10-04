# THE ZEITGEIST

The framing for what this is, in plain words, for people who did not
watch it grow: a really complex mycelial network that maps people's
ideas to each other, with a whole lot of math.

## The mycelial picture (and the math under it)

A mycelial network has no center. Spores land, hyphae grow toward what
feeds them, nodes merge when they meet, and the network's shape IS its
memory of where the food was. This system is that, for ideas:

- SESSIONS are hyphae. Every conversation extends a strand.
- CLAIMS are nodes. A claim with evidence is a node with weight; a
  claim without evidence is a spore that has not germinated.
- AGREEMENT is anastomosis - when two independently grown strands reach
  the same node, they fuse, and the fusion is worth more than either
  strand alone (two independent samples agreeing on a nontrivial claim
  is the signal; one confident sample is noise).
- LAWS are sclerotia - the dense, hardened storage knots the network
  packs its lessons into so a cold season (a new machine, a new seat,
  a crash) cannot lose them.
- KITS are spores again. This package is a spore: it lands on a new
  machine, and everything above grows back from it.

## The whole lot of math (tiered honestly)

Tier labels per this kit's own rot rule: SHIPPED (computable with tools
in this box), SPECCED (the formula is stated and a deep-shelf organ
carries it, ARMORY.md Tier 2), or PATTERN (a design direction only -
nothing computes it yet). The 50-wide dogfood caught this section claiming
computation it did not ship; this is the honest version.

- AGREEMENT SCORES [SPECCED]: weighted Jaccard over claim triples
  (subject, verb, object): score = sum(min(a_t, b_t)) / sum(max(a_t,
  b_t)) over the union of triples t, weights 1.0 for both parties; plus a
  collusion fingerprint (identical claim ORDER between independent
  authors is suspect unless every qualifier binds a shared external
  record). The deep-shelf agreement engine computes exactly this.
- COMPRESSION PROGRESS [PATTERN]: a session's value = bytes(before) -
  bytes(after) under the same compressor, for the same knowledge.
  Interesting things are what still compress. Nothing in this box
  computes it yet.
- DIVERGENCE [SPECCED]: when a stored claim and the world disagree, the
  delta is measured, not argued: for text, the edit distance or hash
  difference between stored and observed. The delta is the frontier map.
- DECAY AND SUPERSESSION [SPECCED]: stored merit loses weight
  exponentially with disuse (w' = w * exp(-alpha * dt)); a superseded
  fact keeps its lineage (supersedes-link) instead of being edited, so
  the network can replay how it changed its mind. The pheromone-ledger
  deep-shelf shape carries it.
- PROPAGATION [PATTERN]: ideas flow along citation edges; centrality
  (fraction of shortest paths through a node) measures which ideas the
  network routes through. Nothing in this box computes it yet.

## What this is NOT

No mysticism, no movement, no names for insiders. Every metaphor above
is a pointer at a mechanism you can read in SUBSYSTEMS.md and run with
the tools in this kit - or see honestly tiered as not-yet-computable
here. If any of it ever explains itself in words you cannot map to a
file and a command, that part has rotted - file it as a finding and mint
the law.
