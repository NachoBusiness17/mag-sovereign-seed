# MAG dashboard information architecture

## What the dashboard is for

The dashboard is the operator-facing memory and control surface for MAG. It should answer, in order:

1. What matters right now?
2. What have the system and operator actually done?
3. What work is forming or ready?
4. What should the agent do next, and how much authority does it have?
5. What system detail is needed when something is wrong?

The governing rule recovered from the earlier dashboard design is: **summary first, files second, spectacle never first**. The operator should understand the screen in about five seconds, then reveal depth as needed.

## Recovered history and intent

This structure was reconstructed from the dashboard design reference, dashboard usage guide, diary/residual history, Verkle/Tapestry implementation, and the dashboard's Git history.

- The original Ideas OS emphasized capturing and developing directions.
- The Office iteration simplified the product around plain-language status and Ideas.
- Days and the Tapestry/Verkle lattice added longitudinal memory: sessions, artifacts, prompts, and continuity across time.
- Story so far added an interpretive narrative rather than another raw event feed.
- The Desk prototype tested a shared behavioral-routing surface for local and remote agents.
- Repeated operator feedback asked for interpretation over telemetry, fewer competing tabs, truthful provenance, readable hierarchy, and the operator's actual words to remain visible.

The Verkle knot is a physical, portable context artifact that can be handed to an agent. It represents underlying session/residual data, its source, commitments, and useful relationships without requiring the receiving agent to inherit the entire conversation. The lattice is the visual index of those knots: it makes their continuity and relationships inspectable. Selecting a knot must lead back to evidence. Missing or orphaned material must be reported honestly rather than visually implied.

## Semantic navigation

The dashboard has two persistent rows. The first row selects an information group. The second row exposes the views inside that group.

| Group | Primary question | Views |
| --- | --- | --- |
| Today | What matters now? | Overview, Pulse |
| History | How did we get here? | Timeline, Diary, Story so far, Verkle knots |
| Work | What are we shaping? | Ideas, Brief, Research shelf |
| Agent | What should act next? | Behavioral router, Workers, Models, Canvases, Shell |
| System | What is running underneath? | Services, Improve, Token flow, Live files |

### Today

Overview is the five-second surface: been, now, and going. Pulse is the short factual event stream. It belongs here because it answers recency, not history.

### History

Timeline is chronological evidence. Diary contains filed narrative. Story so far is the readable synthesis. Continuity is the Verkle lattice and must preserve evidence links and provenance. These are different levels of the same question, not four unrelated applications.

### Work

Ideas holds the active working set. Brief turns direction into a bounded piece of work. Research shelf holds material that may inform work but has not yet earned promotion into the active set.

### Agent

Behavioral router is the normal control surface. The operator supplies intent and constraints; the router chooses a lane and launches or queues work according to authority. Workers, Models, and Canvases are supporting views. Prototype handoff controls remain subordinate rather than competing with the main interaction.

### System

Services, improvement machinery, token flow, and live files are diagnostic depth. They remain available, but they are not the first thing an operator must parse.

## Interaction rules

- One page owns one question; adjacent pages must not repeat the same payload with different decoration.
- Navigation remains visible and full-width. A group never collapses into an unexplained icon rail.
- Direct links restore both the correct group and the correct view.
- Labels use operator language; implementation nouns appear only in deeper details.
- Every historical claim can lead to its source artifact, prompt, session, or residual.
- Visualizations explain relationships. They do not replace plain-language meaning.
- The router asks for approval only when authority, risk, cost, or ambiguity crosses the configured boundary.
- Empty and incomplete history is shown honestly, including orphan residuals and missing links.

## What is intentionally demoted

Raw telemetry, duplicate status cards, experimental controls, and file-level instruments are not deleted. They live behind their semantic owner or inside System depth. This preserves the project's research value without forcing the operator to understand the prototype's internal anatomy before using it.
