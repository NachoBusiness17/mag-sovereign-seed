# MAG dashboard deep dive — operating contract

**As of:** 2026-08-06  
**Audience:** operator on desktop or tablet  
**Primary question:** What needs attention, what is running, what did it produce, and what may Mag safely do next?

## Live QA baseline

All 17 routed views activate from a direct URL and produced no browser console errors. At a 1024×768 tablet viewport there was no horizontal page overflow. Before the tablet pass, 19 of 27 visible behavioral-router controls were below a comfortable 40–44 px touch height. Coarse-pointer styles now raise interactive controls to 44 px and collapse multi-column work surfaces.

The dashboard is still medium-low maturity: routing works, but several views are thin placeholders while Timeline and Story are too dense. The next refinement is semantic consolidation and progressive disclosure, not new top-level tabs.

## Page-by-page contract

| View | Operator decision | Authoritative source | Keep / merge / change |
| --- | --- | --- | --- |
| Overview | Is Mag healthy, and what needs me now? | nervous snapshot, latest day, queue, gates | Keep. Limit to attention, active run, latest outcome, next safe action. |
| Pulse | What changed recently? | bounded event stream | Merge daily trend and alerts here; no duplicate prose from Overview. |
| Timeline | Which workday or session should I inspect? | biography registry + knots | Keep as searchable index. Default to recent/exception rows; virtualize the long list. |
| Diary | What happened in human narrative form? | filed day summaries | Keep, but make it a reading view with date filter and source links. |
| Story so far | What durable arc has emerged? | curated project synthesis | Keep as a periodically rebuilt narrative, not a live telemetry dump. |
| Verkle knots | Which bounded evidence packet can I inspect or hand off? | `mag.verkle-knot/v1` artifacts | Keep. Lead with list/filter; open the 3D lattice only as an optional relationship explorer. |
| Ideas | What deserves attention or routing? | idea graph | Keep as triage: needs work, next action, evidence, owner. |
| Brief | What context should the next agent receive? | current brief / selected knot | Merge into Ideas and Router as a reusable side drawer; remove as a thin standalone destination. |
| Research shelf | What external evidence is available and trustworthy? | ingest catalog | Keep as filterable sources with freshness, provenance, and “used by” links. |
| Behavioral router | What outcome do I want, what will Mag do, and where will it stop? | goal, route policy, queue, canvas | Make the primary action surface. One goal composer, one live run, one evidence/result rail. Advanced lane chatter collapses. |
| Workers | Is anything running, stuck, waiting, or expensive? | orchestrator tasks + queue | Keep. Exception-first table with pause, steer, stop, inspect; no duplicated model catalog. |
| Models | Which seat is available, capable, private, and economical? | provider registry, probes, cost ledger | Merge into Workers as a “Seats” subview. Emphasize capability, tier ceiling, health, observed cost/value. |
| Canvases | Which shared artifact is being edited? | viewport manifests | Merge into Router as artifacts/evidence drawer unless multiple canvases are active. |
| Services | Can Mag operate safely? | health probes, scheduler, supervisor | Keep as system runbook. Show dependency flow, failures first, and last checked time. |
| Improve | Which behavior candidate is ready to score or promote? | training events, evals, promotion queue | Keep; separate automatic evidence filing from human promotion clearly. |
| Token flow | Are we buying useful outcomes cheaply? | cost ledger + provider usage | Merge into Overview economics and Workers details. Use cost per successful leaf, estimate miss, and local share. |
| Live files | Which artifacts changed and are they stale? | bounded watched-file registry | Merge into Services/diagnostics. Never show an unbounded filesystem browser by default. |

## Target information architecture

Five stable top-level groups remain, but most groups need only two or three destinations:

1. **Today:** Command (overview + pulse + economics), Attention.
2. **History:** Days (timeline + diary), Story, Knots.
3. **Work:** Ideas, Research.
4. **Operate:** Router, Runs (workers + seats), Artifacts.
5. **System:** Health (services + live files), Learn (improve + evals).

Tabs answer distinct operator questions. Secondary detail becomes drawers, filters, or drill-downs. A datum has one canonical home and may appear elsewhere only as a short linked summary.

## Patterns to steal

- **Grafana:** every dashboard answers a question; hierarchy and directed drill-down beat dashboard sprawl; refresh only as fast as the source changes; version the dashboard definition.
- **Home Assistant:** responsive section layouts, explicit tablet-friendly views, glanceable state plus direct action.
- **OpenHands:** client/server separation, persistent isolated workspaces, event streaming, and the same control contract for local or remote execution.
- **Open WebUI:** installable PWA shell and a model-agnostic tool surface. Do not copy its broad in-process plugin trust model into Mag.
- **VS Code remote agents:** browser as a lightweight session client while execution remains on the host; authenticated tunnel is mandatory, especially when approvals are relaxed.

## Tablet operations architecture

```text
tablet PWA
  -> authenticated private tunnel (Tailscale Serve or VS Code tunnel)
    -> MAG dashboard remains bound to 127.0.0.1
      -> read API: status, costs, evidence, logs
      -> action API: route, pause, steer, stop
        -> policy gate + idempotency key + audit trail
          -> local orchestrator and coding seats
```

Do not expose port 8765 directly to the LAN or internet. The current server has state-changing endpoints and permissive local CORS, so remote write access needs a separate security pass: authenticated identity, read/write capability split, CSRF/origin checks, short-lived action tokens, confirmation tiers, rate limits, and an immutable action receipt.

## Build sequence

1. Finish touch/PWA shell and responsive view QA.
2. Add a read-only remote mode and `/api/v1/ops-summary` compact payload.
3. Add authenticated action envelopes for route/pause/steer/stop.
4. Put localhost behind private HTTPS tunnel; test from tablet.
5. Consolidate thin pages according to the contract above.
6. Add browser regression checks for every route at desktop and tablet breakpoints.
7. Instrument view use, action success, stale-data rate, and time-to-attention; use those signals for weekly dashboard pruning.
