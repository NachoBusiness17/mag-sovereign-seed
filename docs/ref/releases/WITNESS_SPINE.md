# Witness spine — version boundaries (operator)

**Commitment:** `mag-witness-spine-001`  
**Job:** Link public X posts to Mag version arc — v1 Grok origin → v2 repo → v3 planning  
**Honesty:** Posts are **activation / witness**, not private soil. Ingest text with `research-pack` when needed for pack.

**Full history:** `docs/ref/strike_origin.md`

---

## Operator version map

| Version | Meaning | Where it lives |
|---------|---------|----------------|
| **v1** | Grok/X era that **spawned** the project | X + strike skill |
| **v2** | **This repo** in `projects/` — database + harness | `local_sovereign_agent` |
| **v3** | **Planning** — what agents are building next | branches, RUN sheet |
| **v4** | Mold — process before volume | planning docs |
| **v5** | Pipe — GSTD, Vast train, XRPL seats | planning docs |

---

## Posts linked by operator (2026-08-05)

| # | URL | Post ID | Version tie |
|---|-----|---------|-------------|
| 1 | [status/2028342347361141030](https://x.com/NachoQuixotic/status/2028342347361141030) | `2028342347361141030` | **v1 genesis** — Fool napkin seed (2026-03-02) |
| 2 | [status/2066827806923792465](https://x.com/NachoQuixotic/status/2066827806923792465?s=20) | `2066827806923792465` | v1→v2 bridge — ingest for summary |
| 3 | [status/2071315275354390775](https://x.com/NachoQuixotic/status/2071315275354390775?s=20) | `2071315275354390775` | Product-shape witness (marble / leaf era) |
| 4 | [status/2083551644239683672](https://x.com/NachoQuixotic/status/2083551644239683672?s=20) | `2083551644239683672` | **Toward v3** — latest arc |

---

## Ingest (when you want text on disk)

```powershell
mag.cmd research-pack --ask "Witness post for Mag version spine" --url "https://x.com/NachoQuixotic/status/2083551644239683672"
```

Tag ingest row: `witness`, `release`, `v3`

---

## Behavioral memory

When a witness post marks a version boundary:

```powershell
python main.py release record --version v3 --gate witness_filed --ok --note "2083551644239683672 ingested"
```

---

*Registry: [VERSION_REGISTRY.md](VERSION_REGISTRY.md)*
