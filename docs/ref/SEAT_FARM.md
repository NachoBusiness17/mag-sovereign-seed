# SEAT FARM — the dockerized desktop seats (2026-08-29, operator vision)

Operator: "in the future i'd like to run all these powershells and vs code in
tandem with you driving them kinda like autoclaw in a docker so my wife doesn't
have to fight you for the mouse."

## THE IDEA, STATED
Every interactive seat (grok CLI ×2, codex, deepseek-cli, future Claude/Mistral
CLIs) becomes a CONTAINER: the TUI runs headless inside Docker on a pseudo-
terminal; the driver writes stdin and reads the captured screen text. No
windows, no mouse, no desktop contention — the wife keeps the machine, the
seats run in tandem BY CONSTRUCTION, and driving them stops being computer-use
theater and becomes `docker exec`.

## WHY THE PIECES ALREADY EXIST
- **stdin-driver precedent**: mag/_codex_seat.py has driven codex by stdin since
  08-26 (Mimosa-approved). Generalize, don't invent.
- **Job interface is seat-agnostic already**: seat_contract.json resume_command
  (tonight's salon) — a containerized seat takes the SAME contract as a desktop
  seat. The farm changes the BODY wrapper, not the job law.
- **Compose precedent**: mag-worker compose service (bounded beats, no ports);
  AutoClaw runs plan-bound in the desktop lane today — the farm is its pattern
  applied to CLIs.
- **Auth handling law**: secrets mount read-only from host (~/.grok/auth.json,
  codex login, deepseek key via env), never baked into images, never echoed.

## ARCHITECTURE (three pieces)
1. `seat-<name>` compose services (no ports, restart=no — seats are invoked,
   not daemons): image = CLI + node/python runtime; volumes = auth (ro) +
   repo workdir mount; a PTY wrapper (tmux or a pipe pair) holds the session.
2. **Driver verb**: `docker exec -i seat-grok ./drive.sh "<prompt>"` — writes
   the prompt to the PTY, waits for the spinner to stop, returns new screen
   text. One script per CLI family (they differ in prompt cadence), one COMMON
   interface for me.
3. **Chain glue**: seat_contract resume_command gains a `driver:` field
   ("desktop" | "farm:seat-grok" | ...) so the same chain runs either lane.

## WHAT CHANGES FOR THIS SEAT
- Driving becomes Bash calls, not computer-use focus fights (the 08-28
  frontmost-pid mismatches never happen). Tandem = parallel docker execs.
- Eyes: text capture IS the screen for TUIs; browser-Use seats (computer-use
  work) stay desktop-lane until they too get container browsers.
- The 10-min tick can drive farm seats in beats without touching the desktop.

## PHASES
- P1 (first brick): containerize GROK only — smallest auth surface, proven CLI.
  Test: drive one build beat from this seat via docker exec, file receipt.
- P2: codex + deepseek-cli join (codex stdin driver ports directly; deepseek
  cli exits VS Code for headless). Driver verbs unified into mag/seat_farm.py.
- P3: chains run farm-side — cage N+1 fired by the resume_command's driver
  field; desktop keeps ZERO seats; wife undefeated.
- P4 (post-Rocinante): the farm gains a LOCAL model seat (5.3-flash Q4 via
  Ollama/llama.cpp on Rocinante) — a chain body with zero vendor in the loop.

## RISKS / HONEST NOTES
- Vendor ToS: same account, same usage, just headless — no new class of use;
  interactive re-auth (browser logins) stays an operator session by design.
- PTY scraping is per-CLI brittle (spinners, TUI redraws); the driver scripts
  are the maintenance surface — keep them tiny.
- Windows containers are the wrong tool: the farm runs LINUX containers and the
  CLIs run there fine (node-based CLIs are cross-platform) — verify in P1.
