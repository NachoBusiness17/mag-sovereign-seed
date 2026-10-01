# VERB GENOME LIBRARY — the fleet's verbs as prompt genomes
*L0 contract = shared cached prefix (byte-stable). Each verb = a pack over it (stable structure + dynamic target tail).
Cache farming applied to our own operations: repeat invocations hit the prefix; only the target varies.*

| genome | id | status |
|---|---|---|
| L0_contract.md | fleet/l0@v1 | frozen — the constitution for verb runs |
| steal.md | fleet/steal@v1 | LIVE (demo 09-02) |
| self_steal.md | fleet/self_steal@v1 | LIVE |
| (queued) probe / fold / verify / dispatch / sign / wash | — | packs owed |

Genome record fields: prompt_genome_id · lineage · cache_contract · INPUTS · EXECUTION PROTOCOL · REQUIRED SECTIONS · QUALITY CONSTRAINTS.
Laws: byte-stable prefixes (no timestamps in the contract); targets ride the tail; every run files artifact + receipt.
