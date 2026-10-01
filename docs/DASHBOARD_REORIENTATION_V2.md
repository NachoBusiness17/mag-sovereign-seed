# MAG dashboard reorientation v2 — from system internals to personal operations

## Product thesis

The dashboard is not a museum of Mag subsystems. It is the legible personal interface to a progressively trained local agent that understands the operator's projects and can summon stronger dungeon masters to teach, advise, evaluate, or rescue it.

Every visible object must answer one of five questions:

1. **What is happening?**
2. **Why does it matter to me?**
3. **What needs my decision?**
4. **What can Mag do next?**
5. **What evidence supports this interpretation?**

Internal names such as Verkle, canvas, pulse, improve, token flow, and behavioral router may remain as secondary vocabulary, but the first reading must be ordinary language.

## New destination model

| Destination | Human question | Absorbs current pages |
| --- | --- | --- |
| **Home** | What matters now, and what should I do? | Overview + useful Pulse + economics alert |
| **Projects** | What are we building, where are we, and what remains? | Ideas + Brief + open loops + roadmap + scrum |
| **History** | How did we get here and what did we learn? | Timeline + Diary + Story + Verkle evidence |
| **Run** | What do I want done, who is doing it, and can I intervene? | Behavioral router + Workers + Models + Canvases + useful Shell |
| **Library** | What research, skills, prompts, and external systems can Mag use? | Research shelf + Tesuji + skills + prompt lessons |
| **System** | Is Mag healthy, economical, learning, and safe? | Services + Improve + Token flow + Live files |

## Required semantics

### Home

No button wall and no hidden technical drawer. Show: one attention statement, active work, latest verified outcome, next recommended action, and one command entry. Evidence links drill into the canonical destination.

### Projects

The core object is a project brief with thesis, current sprint, roadmap, completed outcomes, open needs, blockers, research, decisions, and evidence knots. Views such as needs-work, open-loop, shelf, and everything become filters over the same project graph—not separate concepts competing for meaning.

### History

Story is the readability lens for the whole area. Every workday, session, turn, worker run, and knot gets a generated plain-English interpretation plus source certainty. The 3D lattice is an optional spatial lens with persistent legend, camera controls, pinned reading, and “discuss this evidence” action. Hover never replaces the legend or the pinned state.

### Run

Rename behavioral router in the primary UI to **Direct Mag**. Show the operator request, Mag's interpretation, remembered context, chosen task class, model benchmark/right-size decision, summoned dungeon master if any, current executor, verification, cost, and stop boundary. Workers and models are subordinate views of the active run. Canvas means shared artifact; Shell means expert/raw control and must explain that boundary.

### Library

Each research object states: what it is, source, freshness, reliability, what Mag learned, which project it informs, which skill or decision it changed, and what remains unverified. Tesuji records positive discoveries; failures record remedies. Both can become evaluated skills.

### System

Start with a sentence: “Mag can/cannot operate because…”. Services show dependency and effect, not component inventory. Improve shows candidates and evidence before promotion. Economics shows cost per verified outcome and model right-sizing—not token trivia. Live files becomes provenance/freshness diagnostics.

## Progressive local coding curriculum

Local is not permanently a janitor. Each coding task class has a ladder:

```text
frontier dungeon master demonstrates or authors skill
  -> eval case and bounded examples are filed
  -> local model attempts in a sandbox
  -> speed, correctness, retries, cost, and artifact quality are scored
  -> repeated passes promote that task class to local default
  -> failures summon a teacher and revise the skill
  -> periodic smaller-model probes search for a cheaper inheritor
```

The dashboard must surface this as a capability matrix: task class, current owning model, pass rate, median time, cost, last failure, teacher, skill version, and next graduation gate.

## Implementation order

1. Comprehension defects: Overview, Pulse, reading height, persistent 3D legend.
2. Projects: unify Ideas/Brief/roadmap/scrum/open loops.
3. Run: explain Direct Mag and subordinate workers/models/artifacts.
4. History: generated interpretations, persistent camera/key, evidence discussion.
5. Library: explicit research semantics and project/skill linkage.
6. System: dependency-first health, learned-behavior promotion, outcome economics.
7. Tablet/private remote control after authenticated action envelopes.
