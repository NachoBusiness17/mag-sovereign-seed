# THE LAWS: 48h constitutional inventory (division B, laws lane, 2026-09-30)

Window: 2026-09-28 through 2026-09-30. Every law below is stated with its
founding incident receipt, its enforcement mechanism (file:line) or its honest
prose-only status, its falsifier, and the jacket it kills. Every quote and
citation was byte-verified this session by the battery in
`watch/inbox/gala_20260925/48h-synthesis/lanes/laws.check.txt` (run 2:
misses=0, exit 0; run 1 caught one quote of mine that spanned a wrapped line
and was corrected before run 2, the miss is preserved in the saved output).
No code under mag/ or tools/ was touched by this lane, so the
violation_ratchet step does not apply (nothing changed for it to check).

## The constitutional delta in one paragraph

Before this window the estate's laws mostly lived in prose (AGENTS.md, ribs,
receipts) and were enforced by seat memory, which the field verdict sw-10
proved does not work: agents cannot self-police. In 48 hours the governance
moved into the tool path. The seat's own conduct laws became PreToolUse/
PostToolUse hooks with exit codes (seat law gate rules 1-3), a class bug in
that enforcement was killed the same night (--no-register, dash-introduce
edge), and the deeper law under all of them was minted: a verdict without its
conditions is not a verdict (the one-bug law, B2-216 generalized from counts
to all instruments). Honest count: 9 of the 12 laws inventoried carry
code-side mechanisms; SPEND THE MONEY and the general form of the one-bug law
run on prose, and the no-env-dump persona line is prose backed by a code-side
redaction hook. The state that did not change: falsifiers are still named at
mint time, and every law still names the jacket it kills.

## The laws

### 1. THE ONE-BUG LAW (B2-216 generalized: verdicts carry their conditions)

- Incident: 2026-09-29 night. Operator: "now everywhere one bug, many
  jackets". Seven jackets one night, one bug: verdicts consumed without the
  conditions that produced them (report order trusted stable, in-repo verdict
  trusted out-of-repo, head's exit code read as the tool's, check side-effects
  minted for temp files, reasoning budget consumed inside a verdict).
  Receipts: commit 98071f556 (touched exactly one file, the rib addendum),
  incident receipts watch/inbox/ball3/driver-meter.md and commit 26eacaae7.
- Mechanism: the general law is PROSE in
  memory/rib/RIB_DRIVING_LADDER_20260928.md:53-76. Its named instances are
  exit-coded: --no-register (tools/workflow_gate.py:281,312), _rel_posix
  (tools/stealth_driver.py:460), hermetic suites (conftest.py:14-23),
  max_tokens 12000 (tools/corpus_lens_run.py:45). New instrument runs that
  cannot name instrument+exit, moment, and context assumptions are to be
  treated as unfired.
- Falsifier: the next cross-context verdict disagreement that takes TWO
  investigations to resolve to a named condition difference proves the law
  was ignored again (rib lines 75-76).
- Jacket killed: the verdict-without-conditions jacket, the seven-jacket class
  itself.

### 2. SPEND THE MONEY (DRIVING LADDER SPEND amendment)

- Incident: 2026-09-29, the operator's third strike on hoarding, verbatim
  force: "you literally have HERMES AND GROK 4.7 USE IT I WANT YOU TO SPEND
  MONEY". Receipt: rib addendum memory/rib/RIB_DRIVING_LADDER_20260928.md:39-51;
  codified in the AGENTS.md DRIVING LADDER bullet; supporting receipt
  watch/inbox/GROK47_LUNCHEON_INTEL_20260929.md (grok-4.7 funded, 13 models
  live-verified).
- Mechanism: PROSE-ONLY, honestly. No exit code. The check is the banking
  rule: every paid dispatch banks tokens in/out in its receipt.
- Falsifier: a night where zero paid calls landed while judgment-class work
  rode free lanes violates the addendum even if the free output was good.
- Jacket killed: the hoarding jacket (refusing to use what the estate holds,
  the 03:00Z drain bug in money form).

### 3. SEAT LAW GATE rule 1: bare python on PATH blocks

- Incident: 2026-09-29 18:57, commit 185965898, operator: "I keep fucking
  watching you ignore laws - how do others fix it". The seat had run bare
  python on PATH all night (the Hermes-misresolution class that broke
  stealth_driver's selffeed, which the seat ran while fixing it in others).
- Mechanism: tools/seat_law_gate.py:37 (BARE_PY regex), :76-83 (exit 2 with
  the AGENTS.md citation), registered PreToolUse on Bash|Write|Edit at
  C:/Users/ESTATE_USER/.zcode/cli/config.json:50. Fail-open on internal error
  (seat_law_gate.py:26-27,114-115): a broken gate never blocks the fleet.
- Falsifier: a Bash tool call invoking bare `python` that returns exit 0
  through the gate means the hook is dead or unregistered.
- Jacket killed: the agents-cannot-self-police jacket (the working laws are
  exactly the ones with exit codes in the tool path).

### 4. SEAT LAW GATE rule 2: no em/en-dash in authored watch/inbox content

- Incident: 2026-09-29 18:57, same commit 185965898 (which also normalized the
  elder-consult receipt's 5 em-dashes).
- Mechanism: tools/seat_law_gate.py:38 (DASHES regex U+2013/U+2014), :84-107
  (exit 2 on introduced dash), same hook registration (config.json:50).
- Falsifier: an authored watch/inbox file containing a fresh em-dash that
  lands without exit 2 means the dash rule regressed.
- Jacket killed: the AI-tell jacket (the em-dash as machine-prose fingerprint
  in the estate record).

### 5. SEAT LAW GATE rule 3: workflow scripts gated at the tool path

- Incident: 2026-09-29 19:39, commit 9a912c32e, operator sarcasm accepted as a
  work order: "no hook exists, best hand it off to the human" is the exact
  reflex the seat exists to kill. The seat had amended a workflow script twice
  without ever running the gate.
- Mechanism: tools/seat_law_gate.py:43-65 (gate_workflow_content: temp payload
  through tools/workflow_gate.py before landing) + :108-112 (PreToolUse Write
  of *.dwf.ts blocks RED with failing gate names); tools/seat_law_postgate.py
  :30-45 (PostToolUse Edit runs the gate on the whole file after partial edits
  and prints the verdict into the seat's feedback), registered at
  config.json:84. PostToolUse cannot block; it witnesses.
- Falsifier: a Write of a *.dwf.ts whose payload fails workflow_gate landing
  with exit 0 means the pre-landing gate is dead.
- Jacket killed: the no-hook-on-AmendWorkflow escape hatch jacket (the
  submit-time artifact, the script content, was always hookable).

### 6. --no-register: payload gate-checks are verdicts, not ledger facts

- Incident: 2026-09-29 20:04, commit 26eacaae7 ("BUG KILL", operator: "now
  everywhere one bug man"). Every payload gate-check called workflow_gate
  check, which registers a REGISTRY row on every run, so every workflow-script
  Write minted a junk row pointing at a %TEMP% file that died milliseconds
  later: 4 live seatlaw_* rows confirmed. They stay per append-only law
  (battery J1 confirms they are still in memory/workflows/REGISTRY.jsonl).
- Mechanism: tools/workflow_gate.py:281-286 (flag definition with the cause in
  its help text) and :312-314 (early return, exit contract untouched: 2 if
  failed else 0); caller tools/seat_law_gate.py:50 passes it.
- Falsifier: any hook payload gate-check that appends a row to
  memory/workflows/REGISTRY.jsonl means the flag stopped being passed.
- Jacket killed: the append-only-ledger pollution jacket (a check mistaking
  itself for a landed fact).

### 7. Dash-introduce edge: only NEWLY-INTRODUCED dashes block

- Incident: 2026-09-29 20:04, same commit 26eacaae7, fixed while in there: the
  rule-2 scan false-blocked full-content re-saves of files carrying historical
  dashes (quoted sources, older house prose). Battery at mint time: historical
  re-save 0 blocks, new dash 2, edit-fragment dash 2, LAW-12 scenario suite
  7/7 green after the gate change.
- Mechanism: tools/seat_law_gate.py:89-102 (an Edit fragment is always new
  ink; a full Write is judged against the file on disk by dash count).
- Falsifier: either edge reappearing: a historically-dashed file blocked on
  re-save, or a Write introducing a new dash that passes.
- Jacket killed: the false-positive jacket (lawful re-saves blocked, gate
  taught to be routed around).

### 8. Hermetic-basetemp law: suites hermetic to basetemp location, code correct out-of-repo

- Incident: the 09-29 wave5 suite-burn ran pytest with basetemp OUTSIDE the
  repo (suite-burn-w5-full-basetemp-r3) and failed 5 gate/dead-hand tests with
  "not in the subpath of" ValueErrors that the default in-repo basetemp
  (conftest.py:14) had masked. The ball3 driver-meter lane rooted four
  failures to the relative_to-out-of-repo class. Receipts:
  watch/inbox/gala_20260925/wave5-repair/lanes/suite-burn.check.txt and
  watch/inbox/ball3/driver-meter.md (root causes 2-4, stash reproduction as
  byte proof).
- Mechanism: conftest.py:14-23 (default per-pid in-repo basetemp, pre-created
  after the 2026-08-09 56-failure audit) PLUS the class fixed at root:
  tools/stealth_driver.py:460 (_rel_posix), mag/agent_state.py:177
  (_display_path), tools/violation_ratchet.py:307-310 and
  tools/config_seal.py:119-122 (display-path try/except to absolute; seal
  bytes and exit codes unchanged).
- Falsifier: a suite with basetemp outside the repo failing on relative_to
  while the identical suite passes in-repo (the wave5 shape) means the class
  fix regressed in some new file.
- Jacket killed: the intermittent-failure jacket (in-repo mask hiding a
  context defect; "the test passed, which is why it looked intermittent across
  runs", driver-meter.md:58-59).

### 9. Ordered-reports determinism: concurrent phases dispatch on a stable sort

- Incident: 2026-09-29 with the ball drivers; "report order trusted stable"
  named one of the seven jackets: concurrent lane phases consumed target order
  as given, so report order was an accident of arrival.
- Mechanism: .zcode/workflow-drafts/Ball3-suite-green.dwf.ts:101-104 and
  tonight's .zcode/workflow-drafts/Burn-48h-synthesis.dwf.ts:103-104: stable
  sort by the explicit division ORDER map (B:0, A:1, C:2), "control flow only
  - never ask text". Honest status: control-flow determinism inside the
  driver script, no exit code of its own.
- Falsifier: two runs of the same driver with the same lanes dispatching in
  different orders, or a lane whose ask text was altered by the sort.
- Jacket killed: the report-order-trusted-stable jacket.

### 10. Census denominator law B2-216 (lineage into the one-bug law)

- Incident: 2026-09-26, census 1,837 collected differenced against executed
  sums 1,776/1,782 from different moments and instruments. Receipt:
  watch/inbox/burn_wave_20260926/B2_216_collect_delta_20260926.md. Generalized
  2026-09-29 by commit 98071f556 from counts to ALL instruments (law 1 above
  is its general form).
- Mechanism: AGENTS.md clippy census bullet (name instrument, moment, and
  delta before comparing counts); carrier shape law B2-249 enforced fail-closed
  exit 2 by tools/census_drift_patrol.py parse_carrier; the 7-day-stale +
  file-growth WARN patrol (B2-215); the opt-in --collect deep check (B2-244);
  the daily MagCensusPatrolDaily 08:30 task (B2-246).
- Falsifier: a receipt differencing two counts taken at different moments into
  a delta without naming the instruments proves the law is being ignored.
- Jacket killed: the constant-census jacket (the retired 1,341 hand-copied
  headline rode 12 days stale with 31 files grown and no gate noticed).

### 11. MINIMAL-EXPOSURE LAW: scripts load only whitelisted env vars, never full .env

- Incident: 2026-09-30 12:47, commit 76e29cd0b, operator catch ("wont that
  leak our keys"): run_mate.ps1 loaded full .env, and opencode snapshots shell
  env, putting 46 live values where they had no business. Born from the
  steps.jsonl leak lineage (commit 662dc739e purged the history under operator
  GO; commit 03738963e wired the fail-closed precommit_secret_check).
- Mechanism: scripts/run_mate.ps1:61-68: sources ONLY the 2 whitelisted vars
  the opencode config references (ZAI_API_KEY, ZAI_API_KEY_2, z.ai keys into
  z.ai tooling = normal auth).
- Falsifier: any scheduled or scripted process holding live env values beyond
  its named consumers means the whitelist was bypassed.
- Jacket killed: the env-transparency jacket (convenience env loading as a key
  exfiltration channel).

### 12. No-env-dump law: mates never dump environment into transcripts

- Incident: 2026-09-30, commit f4e2c247f ("config seal re-sealed: mates.yaml
  no-env-dump law"), riding 76e29cd0b: mates NEVER dump env (env, set,
  printenv, echo on API-key-shaped names) into transcripts or receipts.
  Law born from the steps.jsonl leak.
- Mechanism: persona contract prose at configs/mates.yaml:17-19, backed by
  code: the trajectory hook redacts live env values pre-write (commit
  76e29cd0b) and the fail-closed precommit_secret_check guards tracked files
  (commit 03738963e). The persona line itself is prose-only.
- Falsifier: a mate transcript or receipt containing an env dump with live
  values that survives the trajectory hook redaction means both the persona
  line and the hook failed.
- Jacket killed: the transcript-as-leak jacket (a mate's honest debug output
  laundering live keys into the record).

## Checks run this ask

- Finish-line byte battery (every quote and file:line citation above, 33 grep
  checks + 2 file-exists + 8 commit-existence checks): run 2, misses=0,
  exit 0. Raw output: watch/inbox/gala_20260925/48h-synthesis/lanes/
  laws.check.txt (run 1 with its 1 miss is preserved at the top of the file).
- Lane JSON parses: .venv/Scripts/python.exe -m json.tool on lanes/laws.json,
  exit 0, evidence line appended to laws.check.txt.
- violation_ratchet: NOT RUN, and not owed: this lane edited only
  watch/inbox/ records, no code under mag/ or tools/.
- Live fire of the seat law gate: not separately re-proven this session; the
  hook registration bytes (config.json:50,84) and rule bytes are
  battery-verified above. A live refusal was not triggered by this lane
  because the lane authored dash-free, venv-only content.

## Lane artifacts

- Lane JSON: watch/inbox/gala_20260925/48h-synthesis/lanes/laws.json
- Check output: watch/inbox/gala_20260925/48h-synthesis/lanes/laws.check.txt
- This receipt: watch/inbox/48h_synth/laws.md
