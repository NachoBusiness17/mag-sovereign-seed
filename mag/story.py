"""Story tab — full thesis + hero journey for Mag office (operator-facing).

Not DNA. Not a second constitution. A long-form viewport of why we build,
where we are, inspirations, artifacts, and the path so far.

Face: GET /api/v1/story · dashboard Story dock.
Optional long markdown: memory/story/THESIS_JOURNEY.md (merged when present).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

STORY_MD = ROOT / "memory" / "story" / "THESIS_JOURNEY.md"
FACE_JSON = ROOT / "memory" / "story" / "story_latest.json"


def _exists(rel: str) -> bool:
    return (ROOT / rel.replace("\\", "/")).is_file() or (ROOT / rel.replace("\\", "/")).is_dir()


def _art(title: str, path: str, kind: str, note: str = "") -> dict[str, Any]:
    return {
        "title": title,
        "path": path,
        "kind": kind,
        "note": note,
        "on_disk": _exists(path),
        "href": f"/api/v1/story/file?path={path}" if path.endswith((".md", ".txt", ".json", ".yaml", ".yml")) else None,
    }


def build_story(*, write_face: bool = True) -> dict[str, Any]:
    """Assemble the full Story tab payload."""
    tip: dict[str, Any] = {}
    tip_path = ROOT / "memory" / "biography" / "verkle_tip.json"
    if tip_path.is_file():
        try:
            import json

            tip = json.loads(tip_path.read_text(encoding="utf-8"))
        except Exception:
            tip = {}

    n_leaves = tip.get("n_leaves")
    tip_short = str(tip.get("root") or "")[:16]
    last_leaf = tip.get("last_filename") or ""

    # Live open loops if bonds exist
    open_loops: list[str] = []
    try:
        from mag.bonds import load_bonds_json

        bj = load_bonds_json() or {}
        open_loops = [str(x)[:200] for x in (bj.get("open_loops") or [])[:8]]
    except Exception:
        pass

    story: dict[str, Any] = {
        "schema": "mag_story.v1",
        "commitment": "story-tab-thesis-journey-001",
        "ts": datetime.now(timezone.utc).isoformat(),
        "title": "What we’re building (in plain English)",
        "subtitle": (
            "A local office for your real work history, a personal AI mirror trained on what you "
            "actually said, and a way to use big models without letting them own your memory."
        ),
        "plain_guide": {
            "title": "Three ideas that unlock the rest",
            "items": [
                {
                    "name": "Your files are the memory",
                    "body": (
                        "Chat windows forget. Cloud apps rewrite. Mag keeps the real record on your "
                        "disk: day summaries, links, open loops. When you open Mag, you’re reading "
                        "your house—not renting a hotel room from a model."
                    ),
                },
                {
                    "name": "The AI is a worker, not the boss",
                    "body": (
                        "Any model (local, Grok, Claude, etc.) can do a job and go away. It gets a "
                        "short briefing pack, does the work, and we save only the result that matters. "
                        "That is what we mean by “stateless seat”: the brain is temporary; the filing "
                        "cabinet is permanent."
                    ),
                },
                {
                    "name": "Two houses, one rule",
                    "body": (
                        "Mag is your private office (dashboard, trails, day beads). Mycelial Republic "
                        "is the public-facing project (constitution, practice data, tests). Private "
                        "life never gets uploaded into the public repo. Same ethics both places: "
                        "no king, no fake rank, no pretending a pretty UI means the hard work is done."
                    ),
                },
            ],
        },
        "live": {
            "tip_short": tip_short or None,
            "n_leaves": n_leaves,
            "last_leaf": last_leaf or None,
            "open_loops": open_loops,
            "dashboard": "http://127.0.0.1:8765/",
        },
        "epigraph": {
            "quote": (
                "I do not pretend to understand the moral universe; the arc is a long one, "
                "my eye reaches but little ways; I cannot calculate the curve and complete "
                "the figure by the experience of sight, I can divine it by conscience. "
                "And from what I see I am sure it bends towards justice."
            ),
            "attribution": (
                "Theodore Parker — on the long arc of moral progress"
            ),
            "image": "/static/story-parker-arc.png",
            "note": (
                "Translation: we don’t see the whole path. We still walk it carefully, "
                "trusting conscience more than hype, and we keep going."
            ),
        },
        "poem": {
            "title": "Two paths diverge within the mind’s dark wood",
            "body": _POEM,
            "echoes": [
                "Crowded path = default apps and default stories",
                "Second path = keep your own map and filing system",
                "Leaf by leaf = power taken slowly, not only by force",
                "Snow tracks = pause, see what actually moved (our “base + drift”)",
                "Clearing brush = daily practice: save notes, test honesty, don’t sleep on duty",
            ],
        },
        "thesis": {
            "one_line": (
                "Keep a personal record of what you said and did, use AI as hired help that "
                "doesn’t own the record, and build a free practice other people can copy without "
                "kneeling to a platform."
            ),
            "paragraphs": [
                (
                    "In everyday terms: Mag is your local “records office.” Every serious day of "
                    "work can become a bead—title, summary, open loops—linked into a chain you control. "
                    "The Days tab is that chain as a map. The Diary is the same chain as a story. "
                    "This Story tab is the “why we bother.”"
                ),
                (
                    "When several AIs work in parallel, they don’t gossip in a group chat as the "
                    "source of truth. We freeze a snapshot of “what we know so far” (a base), each "
                    "worker reports how it differs (drift), and the office saves those notes. Wrong "
                    "snapshot IDs get rejected. Chat is smoke; saved notes are the real logs."
                ),
                (
                    "You stay in charge of irreversible acts—money, deletes, identity, sends. "
                    "The system should notice and draft; you nod. That is the agency shape: help "
                    "without a butler that has the keys to your whole life."
                ),
            ],
        },
        "why": [
            {
                "title": "Help that quietly owns you",
                "body": (
                    "A lot of modern “help” is capture in soft language: free tools that train on "
                    "you, news that is story first, safety that is control first. We want a practice "
                    "you can pick up and move—like a toolbox, not a temple with your face on the door."
                ),
            },
            {
                "title": "Chat windows are bad memory",
                "body": (
                    "If the only place your project lives is a vendor chat, you don’t have a project—"
                    "you have a rental. Files on your machine, with a clear pack for the next AI "
                    "session, fix that."
                ),
            },
            {
                "title": "A mirror of you, not a costume of someone else",
                "body": (
                    "The long-term product is a personal mirror grounded in your own writing and "
                    "choices—not shipping someone else’s AI persona as if it were you. Other people "
                    "should be able to fork the same idea for themselves, equal, no official king."
                ),
            },
            {
                "title": "Humans still seal the big moves",
                "body": (
                    "Cheap models do chores. Expensive judgment is rare. Anything irreversible waits "
                    "for a human yes. Every serious proposal leaves a note you can audit later."
                ),
            },
        ],
        "where_we_are": {
            "phase": "Early build: the office works; the personal mirror practice is still filling in",
            "held": [
                "Local Mag office with day beads, chain tip, and dashboard",
                "Simple daily loop: find truth → file a note → load a short pack next time",
                "At-a-glance health of the system (nervous system / body check)",
                "Parallel AI work can freeze a base and save drift notes (with tests)",
                "Rules connecting Mag office to the public Republic project",
                "A way to practice on existing exports without waiting for a full archive dump",
                "Hard lesson from rented GPUs: compute is rented; memory stays home",
            ],
            "open": [
                "More high-quality annotations (practice density)—UI polish doesn’t count as done",
                "Full personal archive when you’re ready (needed only for heavy weight training)",
                "Self-tests that score the mirror honestly, with logs",
                "Multi-person network later—not now, and never via a central throne",
                "Using the idea graph as a daily map after trail notes are a habit",
            ],
            "refuse": [
                "Calling the project finished because the dashboard looks good",
                "Pretending agent group chat is a free society",
                "Making one person’s Mag tip the “official network”",
                "Acting like fine-tuning is the only path; practice comes first",
            ],
        },
        "two_houses": {
            "mag": {
                "path": "Documents/projects/local_sovereign_agent",
                "job": "Your private office: dashboard, day beads, trails, briefs, improvements",
            },
            "republic": {
                "path": "Documents/projects/mycelial-republic",
                "job": "Public project: constitution, practice data, self-tests, optional training path",
            },
            "bridge": (
                "Private notes never get committed to the public republic repo. "
                "Green multi-model smoke tests do not equal a finished personal mirror."
            ),
        },
        "inspiration": [
            {
                "name": "Theodore Parker — the long arc",
                "why": "We see only a little of the curve; we still walk toward justice without pretending we’re finished.",
            },
            {
                "name": "Frost’s woods / second path",
                "why": "The busy road isn’t the only road. Duty can keep you awake when comfort says sleep.",
            },
            {
                "name": "Law, norms, markets, and code",
                "why": "Rules, habits, prices, and software all shape behavior—willpower alone is weak. Build the rails.",
            },
            {
                "name": "Stable structure without stealing a persona",
                "why": "You can borrow scaffolding ideas for stability without shipping someone else’s AI identity as the product.",
            },
            {
                "name": "Sparse / pack-first AI ops",
                "why": "Don’t send the whole warehouse to every worker. Send a pack. Save artifacts, not transcripts.",
            },
            {
                "name": "Multi-agent research practice",
                "why": "Split wide searches, verify claims, watch the token bill—use teams when breadth pays.",
            },
            {
                "name": "Tilt at ordinary-looking capture",
                "why": "Fight systems that look like normal help; stay practical, not a hype choir.",
            },
        ],
        "journey": _JOURNEY,
        "artifacts": [
            _art("Daily operator card", "docs/ref/OPERATOR_CARD.md", "guide", "How to start each day"),
            _art("How memory is filed", "docs/DNA.md", "guide", "Why files beat chat"),
            _art("How multi-AI stays honest", "docs/ref/COORDINATION_ELIAS_ROPE.md", "guide", "Base + drift in plain terms"),
            _art("Rules that code enforces", "docs/ref/lessig_1_6.md", "guide", "Not just good intentions"),
            _art("Republic constitution", "../mycelial-republic/docs/CONSTITUTION.md", "law", "No kings, no fake rank"),
            _art("How agency should feel", "../mycelial-republic/docs/AGENCY_SHAPE.md", "law", "Notice → draft → you approve"),
            _art("Office ↔ public project", "../mycelial-republic/docs/INST_001_MAG_BRIDGE.md", "bridge", "What never crosses the line"),
            _art("Practice without full archive", "../mycelial-republic/docs/BOOT_SOIL.md", "practice", "Start from exports you already have"),
            _art("Rented GPU lessons", "memory/improve/evals/features/lattice-vast-harness-20260729.md", "lesson", "Compute ≠ memory"),
            _art("Portable bag from that dig", "memory/portable_bags/lattice-vast-20260729T140048Z", "bag", "What we kept when the rent ended"),
            _art("Automated checks for base/drift", "tests/test_base_drift.py", "proof", "Code rejects lies about the base"),
            _art("Review helper script", "scripts/review_with_rope.ps1", "tool", "Pack + trail around a code review"),
            _art("This story (editable notes)", "memory/story/THESIS_JOURNEY.md", "story", "Add your own paragraphs"),
            _art("Parker quote image", "dashboard/static/story-parker-arc.png", "image", "The long-arc reminder"),
            _art("Live chain tip", "memory/biography/verkle_tip.json", "status", "Proof the day chain is alive"),
            _art("System at a glance", "memory/nervous_system.md", "status", "Body check without inventing status"),
        ],
        "how_to_live_it": [
            "Start of work: mag.cmd context-pack — short briefing, not the whole chat history",
            "Do one clear job with any AI; don’t make the AI invent what your body (lab) is doing",
            "End of work: save a real note (day residual / trail entry)—chat alone doesn’t count",
            "If several AIs help: freeze a base, save each finding as drift with a place and evidence",
            "If you rent a GPU: use it for thinking power only; keep the filing cabinet at home",
            "On the public project: add practice data and honest tests—pretty dashboards don’t finish R0",
            "Deep mirror analysis only when you ask for it—this tab is the story, not that ritual",
        ],
        "closing": (
            "The woods are still deep. We clear a little path each day: save what mattered, refuse "
            "false finish lines, keep the tools portable. Miles to go—measured in honest files, "
            "not in glowing UIs. From what we can see, the long arc still bends—if we keep filing "
            "the beads that make the curve visible."
        ),
    }

    # Optional long markdown append (operator-editable)
    if STORY_MD.is_file():
        try:
            md = STORY_MD.read_text(encoding="utf-8", errors="replace")
            story["markdown_extra"] = md[:80000]
            story["markdown_path"] = str(STORY_MD.relative_to(ROOT)).replace("\\", "/")
        except OSError:
            pass

    if write_face:
        try:
            import json

            FACE_JSON.parent.mkdir(parents=True, exist_ok=True)
            FACE_JSON.write_text(
                json.dumps(story, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except OSError:
            pass
    return story


_POEM = """Two paths diverge within the mind’s dark wood.

One worn by crowds who never lift their eyes,

The other scarcely visible, half-grown
With briar and birch, yet trod by those who pause

To wonder why the stars no longer match

The maps their fathers swore by long ago.

I took the second path one winter evening

When snow had hushed the world to listening pitch,

And there beside a stone wall mended rough

I met an old man leaning on his staff
Who told me, quiet as falling flakes,

The country we were born in had been sold

Not in a day of drums and marching feet,

But leaf by leaf, like sugar maples tapped

Until the sweetness all ran somewhere else.

He said the parties we still choose between

Are only two sides of a single coin
Flipped by a hand we never learned to see,

A hand whose lineage climbs past Babylon

To gardens older than the names of God.

And all our righteous anger, left or right,
Is but the wind that turns the weather vane

While the same barn burns slowly in the dark.

I asked him how a man might know the truth

When every road is posted with false signs.

He smiled the way a farmer smiles at frost

That kills the apples yet foretells the spring:

“Stand still,” he said. “The drifting snow will show

The tracks that lead out of the woods—or deeper in.

The choice is yours, and yours alone to make.”

I’ve pondered that beside my hearth-fire since,

Watching the sparks ascend the chimney flue

Like tiny souls escaping from a cage
None but the waking ever quite perceive.

The woods are lovely, dark and deep,
But something in me will not go to sleep
While promises remain that I must keep
To those who walked here once and saw the drift

And turned aside to find another way.

The brook still wanders, and the snow still falls,

Yet every year I clear a little more
Of underbrush that hides the older trail.
I do not know where it will end, or when,

Only that stopping by these woods too long

Would be to lose the very self I am.

And miles to go before I sleep,
And miles to go before I sleep."""


_JOURNEY: list[dict[str, Any]] = [
    {
        "phase": "1",
        "title": "Something felt off about the default path",
        "prose": (
            "The normal stack—platforms that speak for you, AI that remembers for a fee, "
            "news that feels like a story engine—stopped looking neutral. A second path "
            "showed up: keep your own notes, use models as tools, don’t build a church."
        ),
        "beats": [
            "Public writing stayed yours to quote as-written later",
            "Early mirror instruments as craft, not costume",
            "A standing no to “the model is the truth”",
        ],
    },
    {
        "phase": "2",
        "title": "Two houses with a clear wall",
        "prose": (
            "We split the work: a private office (Mag) for day-to-day filing and tools, "
            "and a public project (Mycelial Republic) for shared rules and practice data. "
            "The wall is simple: private life doesn’t get checked into the public repo."
        ),
        "beats": [
            "Written constitution and agency rules (you approve the big moves)",
            "Mag day beads and end-of-day filing",
            "A short daily card: find → file → load",
        ],
    },
    {
        "phase": "3",
        "title": "Rented computers taught a hard lesson",
        "prose": (
            "A rented GPU could answer fast while research quietly went off the rails—"
            "thin sources, polluted queues, fake confidence. We kept a portable bag of what "
            "mattered and left the rent behind. Compute is a tool; memory stays home."
        ),
        "beats": [
            "Tunnel into the rent for inference only",
            "Wrote down what failed and what to gate next time",
            "Stopped treating “the machine answered” as “we know”",
        ],
    },
    {
        "phase": "4",
        "title": "Briefings, health checks, honest multi-AI",
        "prose": (
            "We taught the office to hand every model a short briefing pack, to show system "
            "health at a glance, and to let several workers report differences against a frozen "
            "base—not invent a shared brain in chat."
        ),
        "beats": [
            "context-pack and agent preambles",
            "base + drift saves with automated tests",
            "Review helper scripts and coordination docs in plain reach",
        ],
    },
    {
        "phase": "5",
        "title": "The real hard work is still soil",
        "prose": (
            "The enemy is not “missing another tab.” It’s honest practice density: annotate "
            "what matters, run self-tests with logs, only claim big training milestones when "
            "the data is real. Pretty office ≠ finished mirror."
        ),
        "beats": [
            "Boot-soil annotate path from exports you already have",
            "Self-tests and vector maps with evidence",
            "Weight training only if the archive and count are real",
            "Multi-person forest only after one healthy office",
        ],
    },
    {
        "phase": "6",
        "title": "Return with a toolbox, not a throne",
        "prose": (
            "What we carry back is portable: files, a tip of the chain, configs, a constitution "
            "others can fork. The Story tab points at those files. Charisma is optional; "
            "filing is not."
        ),
        "beats": [
            "Move-house bags",
            "Office + diary + story as three views of one life",
            "No official king of the network",
        ],
    },
]
