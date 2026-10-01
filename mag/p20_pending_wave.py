#!/usr/bin/env python3
"""P20 PENDING WAVE — 20 lanes x glm-5.3-flash on the pending pile (2026-09-12, zcode seat).

Operator order: "launch 20 wide on pending shit." Verified recipe from the 09-12
Astra-vs-cheap arms: Lite key from container env, standard PAAS endpoint,
max_tokens>=8192 (thinking eats 2048 -> empty), ThreadPoolExecutor(4),
shared head for cross-lane cache hits, per-lane lens section.
Results print to stdout as one JSON blob after a ===P20JSON=== marker;
the host redirects that into memory/runs/. This script performs no file writes.
"""
import json, os, socket, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://api.z.ai/api/paas/v4/chat/completions"
MODEL = "glm-5.3-flash"

HOST_ALLOW = {"api.z.ai"}

def guarded_open(url):
    """Mimosa-shaped guard: allowlist host, resolve, require global IPs, no redirects."""
    from urllib.parse import urlparse
    p = urlparse(url)
    if p.scheme != "https" or p.hostname not in HOST_ALLOW:
        raise ValueError("host not allowed: %s" % p.hostname)
    import ipaddress
    for _fam, _typ, _proto, _canon, sa in socket.getaddrinfo(p.hostname, 443):
        if not ipaddress.ip_address(sa[0]).is_global:
            raise ValueError("non-global IP for %s" % p.hostname)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    return urllib.request.build_opener(NoRedirect)

SHARED_HEAD = """You are one lane of a 20-wide wave in the local_sovereign_agent fleet ("the mesh") — a file-first AI operation: signed chain of record, tri-state claims (Supported/Disputed/Unproven, evidence attached), one-builds-one-verifies, no seat is load-bearing. The operator (foste) runs it on a laptop + Docker cage today; a 4x Mac Studio M5 Ultra ("Rocinante") lands ~Oct 27. Key standing organs: hermes (CLI harness: cron/status/approvals/checkpoints), the verkle chain (signed history), watch/ cards, topic_index (1,040 cards), the organ table (fleet organs as addressable rows), Build 3.5 (evidence-and-enforcement layer: vault, ack/reaper, steer signing, lesson gate), wave drivers that fan work N-wide on cheap lanes.

HOUSE LAWS for your output: plain English, no purple prose, no moon-speak. Tri-state every factual claim you borrow. Be concrete: name files, name steps, give the falsifier (how we'd know you're wrong). Do not invent facts about outside projects beyond the context given; mark UNPROVEN where you extrapolate.

OUTPUT CONTRACT: markdown, 500-900 words max, exactly these sections:
## Verdict
(one line: what this item IS and whether it's worth doing)
## Body
(the work: design/table/plan/list — the actual deliverable)
## Next steps
(2-4 concrete steps, each starting with a verb, each cheap)
## Tri-state
(Supported / Disputed / Unproven — one line each on your key claims)
## File to
(one repo path where this should live)
"""

LANES = [
 ("L01_opik_hermes_design", "CONTEXT: A 09-12 article (@_avichawla) describes an `opik-hermes` plugin + self-hosted Opik (Apache-2.0, localhost:5173): records each agent turn as root trace + spans (model: tokens/cost; tools: args/results); failed-run path = trace diagnosis -> proposed diff -> human approval -> sandboxed rerun -> regression test; an incident becomes reusable via 4 records (first divergent step, fault origin model/tool/config/code, correcting change, regression test). Limits: LLM judges are not ground truth, one passing rerun proves one case, learned artifacts need versioning. The fleet runs hermes TODAY.",
  "TASK: Write the integration design for opik-hermes + self-hosted Opik into our hermes install: docker-compose shape (loopback-only), config.yaml plugin block, how the failed-run approval path maps onto our existing hermes approvals flow, how regression tests slot into Build 3.5's lesson gate, and the span schema we'd want. Do NOT include install commands that hit the network; this is the design the install executes."),
 ("L02_width_decision_table", "CONTEXT: Google ran a 260-agent-systems test (44pg PDF, 09-12 card): CEO+Workers topology +80.8% over baseline; UNVERIFIED worker outputs amplify errors 17.2x; a hybrid 'supervisor+verify' topology gained +515% but at 515% overhead. Fleet mirror: the dozen-wide wave found 5 of 12 lanes passed a night test falsely (idle box = vacuous green), producing a 6-gate C1 checklist.",
  "TASK: Produce the DECISION TABLE for wave_driver width rules: rows = topology (solo, N-wide unverified, N-wide + 1 verifier, N-wide + verifier-every-k, supervisor+verify); columns = when to use, measured evidence (cite the numbers above as Supported), overhead cost, failure mode, falsifier. End with 3 standing rules for wave_driver."),
 ("L03_markitdown_binding", "CONTEXT: microsoft/markitdown converts almost any file (PDF, Office, images w/ OCR, audio) to Markdown and ships an MCP server. Fleet intake today: the vision pipeline (READ->FILTER->INTERPRET->CITE-GATE->RIGHTSIZE->JIT) handles links; PDFs like Google's 44pg 260-agent test still need a handler. markitdown was triaged 09-12 as the default PDF intake handler candidate.",
  "TASK: Write the binding plan: exactly where markitdown slots in the intake pipeline (before FILTER? at READ?), what its MCP server replaces vs adds, loopback-only deployment shape in our cage, fallback when it fails on a scanned PDF, and the acceptance test (which PDF in our corpus it must convert cleanly to pass)."),
 ("L04_understand_census_probe", "CONTEXT: Understand-Anything (Egonex-AI, 82.1k stars, MIT) builds a knowledge graph over a repo using tree-sitter (deterministic parsing) + LLM (semantic summaries) with a 5-agent pipeline. Fleet already has: topic_index.py (1,040 cards / 23 buckets), librarian.py (unregistered/dust audit), the organ table. Triaged 09-12 as a census-organ probe.",
  "TASK: Write the probe plan: what /understand-style indexing would ADD over topic_index+librarian (cross-file semantic edges the card index lacks), the minimal probe (one subdirectory, not the whole repo), output schema mapped to our 23 buckets, and the beat-default-or-die falsifier (what question it must answer that topic_index cannot, or it dies)."),
 ("L05_nine_principles_audit", "CONTEXT: @bibryam's 9 principles for real skills vs markdown essays: (1) metadata is the gate - description is the selection signal; (2) progressive disclosure - context is a shared budget; (3) process over prose - steps with exit criteria; (4) explain the why - reasons become rubrics; (5) anticipate the excuse - document and rebut the common shortcut; (6) code over inference - deterministic steps as scripts; (7) stay in scope; (8) skills decay - owners, review dates, versioning; (9) run before you ship - debug from observed transcripts. Fleet skills live in .agents/skills/ (e.g. operator-corrections with the ten laws) and the hermes skills zoo (hundreds of models/rows, 403-model census).",
  "TASK: Turn the 9 principles into a scored audit rubric (0-2 each, 18 points) with one-line evidence criteria per row, then apply it hypothetically to THREE fleet skill types: the operator-corrections skill, a typical hermes cron prompt, and the wave-card format. Flag which of the three scores worst and the single highest-leverage fix."),
 ("L06_gstack_bone_steal", "CONTEXT: gstack = Garry Tan's published Claude Code setup, ~23 opinionated tools (per a 09-12 list post). The zcode seat's stack: hermes CLI, wave drivers, verkle chain, organ table, ractor salons. Fleet law: SACRED COWS NOT LEGACY SHIT - steal the bones, name the reinterpretation. Details of the 23 tools are UNPROVEN (list post, not fetched).",
  "TASK: Write the bone-steal survey AS A METHOD (since tool details are unproven): the 6 categories a 23-tool seat setup almost certainly covers (context management, verification, git hygiene, memory, dispatch, reporting), what the fleet's existing bone is in each category, and the 3 categories where an outside tool most likely beats ours - each with what to look for when we actually fetch the repo, and a kill criterion."),
 ("L07_ten_repo_zoo_census", "CONTEXT: A 09-12 list post (@RoundtableSpace) named 10 repos for coding agents: gstack, context-mode, OpenCode, Superpowers (obra), Learn Claude Code, Ruflo, OpenCode Agents, Agent Skills (addyosmani), Paseo, MCP Servers collection. Top reply: 'Pin the commits. An unpinned MCP is a standing session you did not mean to grant.' Fleet organ-table format: one row per organ with beat-default-or-die falsifier. Repo details UNPROVEN (not fetched).",
  "TASK: Write the 10 rows as a zoo-census table: repo / claimed role (from the list, marked UNPROVEN) / fleet organ it maps to / what it must beat to earn a probe / pin-status requirement. Add the census law: CATALOG LISTING IS NOT SERVABLE (2 of 7 'free' rows in our model zoo were dead as listed)."),
 ("L08_pin_everywhere_law", "CONTEXT: Fleet supply-chain receipts: router threat-intel report (creds harvested from agent supply chains), canary triple in providers.yaml, steer signing + forged-steer canary (attack/detect pair, proven both ways), unpinned-MCP warning from a stranger (09-12): 'Pin the commits.' Fleet law style: short, imperative, with the falsifier attached.",
  "TASK: Draft the PIN-EVERYWHERE standing law as it would appear in the operator-corrections skill: the law in one sentence, 4-6 numbered clauses (MCP servers, pip/npm deps, model pins, skill versions, docker images), what counts as compliance, the escape hatch (how to run unpinned in a sandbox), and the falsifier. 150 words max for the law itself."),
 ("L09_stack_v1_distribution", "CONTEXT: docs/ref/STACK_V1.md is the fleet's full self-description (publish GO = operator's). 09-12 found Tons-of-Skills (DanKornas): a model-agnostic skills marketplace with PROVENANCE LABELS (canonical / generated adapters / first-party / upstream mirrors), browsable by job-to-be-done bundles, MIT scaffolding; also the Nous plugin catalog. Operator stance on publishing: 'people are gonna steal our stuff, we might as well push them forward.'",
  "TASK: Write the distribution plan for STACK_V1-derived artifacts: which 3 fleet artifacts are most publishable first (name them), what format each must become (skill vs card vs spec), which surface takes which (Tons of Skills vs Nous catalog vs plain GitHub), the provenance label each gets, and what must stay private (operator identity, keys, the chain's signed rows). No publishing happens without operator GO - this is the shelf plan."),
 ("L10_jtb_organ_bundles", "CONTEXT: The organ table (v1, 14 organs: hermes, grok, chain janitor, librarian, percolator, overseer, grounding wave, cite_gate, riddler, tesuji ledger, etc.) is indexed by ORGAN. Tons-of-Skills indexes by JOB-TO-BE-DONE bundles - what a person is trying to do, not what the thing is. Fleet surfaces: room.html, hermes CLI, watch/ cards.",
  "TASK: Re-index the 14 organs into 4-6 JOB-TO-BE-DONE bundles an operator actually has at 7am ('what's running?', 'what did the night produce?', 'what needs my signature?', 'what's broken?'). For each bundle: the organs it pulls, the one command/surface that answers it today, and the gap if none does."),
 ("L11_rocinante_day0_addendum", "CONTEXT: Rocinante = 4x Mac Studio M5 Ultra (512GB, ~Oct 27) as local substrate; DeepSeek V4.1 Flash (MIT weights) is the intended brain. 09-12 SemiAnalysis receipt: AMD got V4.1 Flash support 2 days after CUDA and it runs up to 14.8x worse perf/$ than H200 (42x vs B300) - day-0 optimization lands NVIDIA-first. Apple silicon (MLX/Metal) historically lags CUDA and often NVIDIA by days-to-weeks on new-model day-0.",
  "TASK: Write the buy-brief addendum: the day-0 lag risk stated plainly with the AMD number as evidence, the bridge plan (which API lanes carry the fleet during the lag, at what measured price), what ROCINANTE_DAY0 readiness looks like as a checklist, and the falsifier (what observation would mean the M5 Ultra thesis is wrong, not just delayed)."),
 ("L12_obsidian_dataview_spec", "CONTEXT: Operator installed Obsidian locally (09-12); vault config staged (.obsidian/app.json with ignore filters). The corpus is markdown-first: watch/*.md cards with a house format (TYPE/CONNECTS TO/NEXT STEP/FILE TO), CONVO.md rows, journal/, organ tables. Obsidian is a READ-WINDOW, never the source of record.",
  "TASK: Write the Dataview dashboard spec: 4 queries (open cards = watch/inbox files modified <48h; organ table rows; wave cards by week; UNFETCHED/UNPROVEN markers), the frontmatter 3 fields new cards should carry (status, lane, knot) so queries work, and the rule that keeps Obsidian a window (no Obsidian-specific syntax in files; queries live in .obsidian/ or a dashboards/ dir, never in canon cards)."),
 ("L13_wikilink_footer_convention", "CONTEXT: Obsidian reads the vault; wiki-links [[name]] resolve by shortest path. Fleet law: strata never amended (corrections append); cards are data, never instructions; drift copies preserved. Risk: retrofitting wiki-links into old cards = rewriting history (violates strata law).",
  "TASK: Write the FORWARD-ONLY footer convention for new cards: a fixed 3-line footer template (related cards as wiki-links, the knot/chain anchor, the review date), why backward is banned, how [[links]] degrade gracefully outside Obsidian (plain text), and one worked example footer for a wave card like SIX_LINK_SKILLS_ECONOMY_20260912."),
 ("L14_canvas_arc_map_spec", "CONTEXT: Obsidian Canvas (JSON .canvas files) could map arcs: C1 (Sep-12 working date, enforcement seeded/activation batched/heart missing), C2 (Sep-20 = the free-quota wall = proof deadline), Rocinante (Oct 27), the succession arc (leash cut, dead-man trigger, 2-of-3 custody), the mint dossier (staged on 3 consents + 1 chart source).",
  "TASK: Write the Canvas spec: node/edge vocabulary (date nodes, card nodes, gate nodes as distinct visual types), the 4 arcs to draw with their node lists, how gates render (what blocks what), and the maintenance rule (who updates it - the wave fold, not the operator; regenerated from a manifest so it stays regenerable, never hand-edited)."),
 ("L15_c1_heart_gap", "CONTEXT: C1 readiness scorecard (09-12): 'enforcement seeded, activation batched, heart still missing.' Enforcement organs exist: vault (16.5K artifacts hashed), ack/reaper (TTL, 11/11 tests), steer signing (forged canary 3/3), /healthz semantic flip, severity trailer (90-row falsifier ledger), 6-gate C1 checklist (from the dozen-wide false-green finding). C1 = Sep-12 working date; C2 = Sep-20.",
  "TASK: Name THE HEART: what single organ, if it existed, would make C1 alive instead of seeded? Candidates to weigh: the autonomous loop that runs the gates without the operator (hermes cron already arms jobs), the quorum steward, the lesson gate's enforcement teeth. Pick ONE, write its v0 spec (inputs, outputs, the one test it must pass before C1), and say explicitly what stays batched until C2."),
 ("L16_mint_consents_draft", "CONTEXT: MINT DOSSIER 9/9, execution staged: TZIP-21 draft + geometry frozen; fires when 3 consents + 1 chart source land. Known fix-list closures: journal JPG vaulted (sha 5943f119), chart license honest-UNPROVEN, 8-chair reconcile done, privacy clause added. Operator said 'mint it, we want friends, attributing good artists.'",
  "TASK: Draft the 3 consent requests as short texts (each <120 words, plain English, naming exactly what consent covers: e.g. attribution of borrowed artists' names/shapes in the tapestry geometry, the chart source license confirmation, the public-mint GO itself) and list 3 candidate chart-source strategies ranked by provenance cleanliness. NO sending - these are drafts for the operator to fire."),
 ("L17_sign_sheet_status", "CONTEXT: The sign sheet (09-12, 7 items, one screen): (1) salting cut, (2) canon extension, (3) succession Art 5 (pre-signed), (4) noth ethrium annex, (5) journal, (6) C1/C2 dates as amendable working dates, (7) Athena. Default-actuation law: recommendation executes in 48h unless vetoed; only 4 gates stay on the operator (spend GOs, KEYS, ONE STOP, publish GO).",
  "TASK: For each of the 7 sign-sheet items: what signing it actually requires (a word? a photo? a chain knot?), current state (Supported by what receipt / Unproven), and whether it can ride the 48h default-actuation window or genuinely needs the operator's hand. Output as a 7-row table plus the 2 items that most deserve his actual signature."),
 ("L18_provenance_tristate_map", "CONTEXT: Tons-of-Skills provenance labels: canonical (author's own), generated adapters, first-party packages, upstream mirrors. Fleet tri-state: Supported/Disputed/Unproven with evidence attached. Fleet also has: ponytail canon (CONFIRMED at a specific path), ractor receipts, chain knots as signed provenance, and the strata law (never amend, append corrections).",
  "TASK: Write the mapping: for each of the 4 marketplace labels, the fleet tri-state equivalent + what evidence upgrades it + how the chain expresses it (knot type / anchor). Then the inverse: how a fleet card's provenance would render as a marketplace label if STACK_V1 artifacts shipped there. Flag where the two schemes DISAGREE (e.g. is a verified mirror Supported or a lesser grade?)."),
 ("L19_day0_watch_percolator", "CONTEXT: The percolator compiles repeats into invariants (the wrongthink invariant map: every moderation flag = a free probe). The hum's law: receipts are training ore. 09-12 evidence: V4.1 Flash support landed CUDA-first (vLLM) with AMD +2 days; MLX/Metal typically later. Fleet needs to KNOW on day-0 when Rocinante-runnable support lands for any new model.",
  "TASK: Design the DAY-0 WATCH as a percolator probe: what signals it watches (vLLM/MLX release feeds, HF weight drops, the SemiAnalysis-type accounts), how repeats compile into the invariant ('new model -> CUDA -> others' is the pattern to detect), the hermes cron shape (read-and-file only, no egress beyond fetch), and the alert card format when a Rocinante-runnable port lands."),
 ("L20_opik_trajectory_reconcile", "CONTEXT: The trajectory lens: every built thing is PRODUCER/RECORD/COMPILER/DARK through the envelope {input, tool_result, output, reasoning, step_hash, timing}. Opik's span schema (per 09-12 article): root trace per run + spans with model calls (tokens/cost) and tool calls (args/results), plus incident records (first divergent step, fault origin, correcting change, regression test). The hum: receipts are training ore.",
  "TASK: Write the reconciliation: map Opik span fields onto the envelope fields one-to-one (table), name what Opik captures that the envelope lacks, what the envelope captures that Opik lacks, and the single schema change to the envelope that would make Opik traces FIRST-CLASS chain-able receipts (step_hash over spans?). End with the migration order (which existing wave emits Opik-shaped traces first)."),
]

def fire(lane):
    lane_id, context, task = lane
    prompt = SHARED_HEAD + "\n## CONTEXT\n" + context + "\n\n## TASK\n" + task + "\n"
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 12288,
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(
        BASE, data=payload, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + os.environ["ZAI_API_KEY_Lite"]})
    t0 = time.time()
    try:
        resp = guarded_open(BASE).open(req, timeout=300)
        body = json.loads(resp.read().decode())
        text = body["choices"][0]["message"]["content"] or ""
        usage = body.get("usage", {})
        return lane_id, text, usage, time.time() - t0, None
    except Exception as e:
        return lane_id, "", {}, time.time() - t0, str(e)[:300]

def main():
    if not os.environ.get("ZAI_API_KEY_Lite"):
        raise SystemExit("ZAI_API_KEY_Lite not in container env")
    results, spend, texts = [], {"completion": 0, "cached": 0}, {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fire, lane): lane[0] for lane in LANES}
        for fut in as_completed(futs):
            lane_id, text, usage, dt, err = fut.result()
            comp = usage.get("completion_tokens", 0)
            cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
            spend["completion"] += comp
            spend["cached"] += cached
            status = "OK" if text else "FAIL: " + (err or "empty")
            print(f"{lane_id}: {status} {dt:.0f}s out={len(text)}ch ctok={comp} cached={cached}", flush=True)
            if text:
                texts[lane_id] = text
            results.append({"lane": lane_id, "ok": bool(text), "dt": round(dt),
                            "completion_tokens": comp, "cached": cached, "err": err})
    ok = sum(1 for r in results if r["ok"])
    print(f"DONE {ok}/{len(results)} lanes, {spend['completion']} completion tokens, {spend['cached']} cached", flush=True)
    print("===P20JSON===")
    print(json.dumps({"model": MODEL, "lanes": results, "texts": texts}, ensure_ascii=False))

if __name__ == "__main__":
    main()
