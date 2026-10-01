# gstdcoin GitHub org — local reference index

**Source:** [github.com/gstdcoin](https://github.com/gstdcoin?tab=repositories)  
**v5 plan:** `docs/ref/MAG_v5_GSTD_FOREST.md` — **piped for v5** test + implement  
**Local clones:** `reference/gstdcoin/` or `mine/raw/gstdcoin/` (gitignored — refresh with `scripts/pull_gstdcoin_repos.sh`)  
**Purpose:** inspiration + future Mag ↔ GSTD forest integration; **not** a v3/v4 dependency.

---

## Repos (6 public, pulled 2026-08-05)

| Repo | Local path | License | Last push (GitHub) | One-line |
|------|------------|---------|-------------------|----------|
| **ai** | `reference/gstdcoin/ai` | MIT | 2026-03-31 | DePIN inference, `gstd-mcp-server`, TON wallet hooks |
| **web** | `reference/gstdcoin/web` | MIT | 2026-03-31 | Next.js landing / marketing site |
| **A2A** | `reference/gstdcoin/A2A` | MIT | 2026-03-31 | Agent-to-agent protocol, MCP, Hive Memory, TON |
| **gstdbot** | `reference/gstdcoin/gstdbot` | Apache 2.0 | 2026-03-31 | Node OS — swarm agent, P2P, MCP client |
| **contracts** | `reference/gstdcoin/contracts` | MIT | 2026-03-31 | TON smart contracts (Tact) |
| **gstd-bridge** | `reference/gstdcoin/gstd-bridge` | MIT | 2026-03-31 | Cross-chain bridge (**README: deferred / not deployed**) |

---

## Mag relevance (future seats)

| gstd repo | Mag slot (when wired) |
|-----------|------------------------|
| **A2A** | Switchboard peer / optional remote seat; agent-to-agent handoff |
| **ai** | DePIN inference backend; `gstd-mcp-server` as tool provider |
| **gstdbot** | P2P swarm node; janitor/scut at network edge |
| **contracts** | On-chain identity / payment rails (no keys in git) |
| **gstd-bridge** | Read-only reference until deployed |
| **web** | Public face; not harness-internal |

See `docs/ZEITGEIST.md` — beads (this repo) + forest (mycelial-republic) + **GSTD network** as third house.

---

## Refresh clones

```bash
./scripts/pull_gstdcoin_repos.sh
```

Windows:

```cmd
scripts\pull_gstdcoin_repos.cmd
```

Shallow clone (`--depth 1`); re-run to `git pull` existing dirs.

---

## Do not commit

- `reference/gstdcoin/*` — full upstream trees stay local only
- Wallet keys, `.env`, TON mnemonics — never in Mag git
