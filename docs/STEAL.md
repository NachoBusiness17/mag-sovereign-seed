# STEAL — External-Op Automation Pattern
**Source lesson:** the "send the packet over GitHub" op (embassy-aos publish)
**Steal target:** how to turn any *system-imperative local/external op* that keeps
leaking to manual terminal into a first-class, gated, tested framework path.
**Origin modules:** `mag/extension_deploy.py` (the precedent) → `mag/embassy_deliver.py`
(the proof it generalizes).

---

## The rule this encodes (from /memories/routing.md)
> System-imperative local ops (deploy, publish, restart, git, ship) have NO queue/REST
> path today, so they leak to terminal and trigger allow-prompts. **The fix is to BUILD
> that path** (module + REST + CLI + tests + gates + learn), not to keep hand-running them.

`embassy_deliver` is the second instance of this pattern. `extension_deploy` was the
first. Treat it as a template and reach for it the moment you hear yourself about to
run a `git`/`gh`/`publish`/`deploy` command by hand.

---

## The 5-part shape (reusable template)

```python
# mag/<op>.py
def <op>_safety_check(...) -> dict   # GATE 1: block on REAL bad values (secrets), never on prose words
def <op>_precondition_check(...)     # GATE 2: block on unfinished inputs (placeholders, missing fields)
def <op>_assemble(dry=True) -> dict  # build the artifact (git init/add/commit, files, zip)
def <op>_publish(dry=True) -> dict   # the external action; gated on creds; DRY BY DEFAULT
def learn(outcome, dry) -> dict      # fold to Verkle witness + skill_ledger decision (tesuji-everywhere)
def main(argv=None) -> int           # `python -m mag.<op>` + CLI subcommand in main.py
```

### Gating rules (the part that earns trust)
1. **Gate on real values, not words.** A publish-safety gate must block on actual
   secret *fingerprints* (`sk-…`, `ghp_…`, `AKIA…`, `Bearer …`, `-----BEGIN PRIVATE KEY`),
   NOT on the word "secret" appearing in prose. OPSEC docs legitimately *name* the gates;
   word-hits are advisory, real secrets are fatal. (We hit this exact false-positive and
   fixed it — don't rebuild it.)
2. **Dry-run by default.** `--live` is opt-in. Every gated step reports what it *would*
   do before anything touches the outside world.
3. **Credentials are presence-only.** Check `env`/`which`, never read or print the token
   value. If creds are absent → return a clear, operator-only reason (e.g. "install gh +
   `gh auth login`"). One-time auth is never the framework's job.
4. **Gate catches the real blocker before ship.** Our dry-run caught 5 unfilled `⟨ ⟩`
   placeholders in §6 that a manual push would have published. That's the dogfood win:
   the gate protects the operator from their own unfinished input.

### Wiring (all three surfaces)
- **CLI:** `sub.add_parser("<op>", ...)` + `if args.cmd == "<op>": from mag.<op> import main; return main([...])`
- **REST:** `h_<op>(params, body) -> (int, dict)` thin twin (imports the module, calls
  the function) + register `("GET"/"POST", f"/api/v1/<op>", h_<op>)` in `ROUTES`.
- **Queue tag:** tag a `spawn_task` goal so the drainer can execute it async when the
  op is async-able.

### Tests (deterministic, no external side effects)
- safety gate passes on clean / blocks on a planted real secret
- precondition gate blocks on unresolved marker / passes when filled
- assemble dry never inits git
- publish dry takes no external action
- Run with the project venv: `.\.venv\Scripts\python.exe -m pytest ...`

---

## The GitHub-publish specifics (stolen for this case)
- **Repo creation:** `gh repo create <name> --public --source=. --push` (create + push in one).
- **Existing remote:** `git remote -v` → if present, `git push -u origin HEAD`.
- **Token path:** `GITHUB_TOKEN` / `GH_TOKEN` env, presence-checked only.
- **License culture:** match the partner's license (AdventureNLearn ships CC0 → we ship CC0).
- **Deliverable hygiene:** pure-stdlib module (no deps) so the recipient runs it with
  plain `python -m pytest tests/ -q`. Zero-dependency = zero-friction fork.

---

## Candidate ops to automate next with this template
| Op | Surface | Notes |
|----|---------|-------|
| Git commit/push of a sub-project | git | the `assemble` + `publish` half already fits |
| Publish a doc/pack to a repo | git/gh | reuse safety+placeholder gates |
| Deploy dashboard/extension | local | already have `extension_deploy` |
| Post/steer to an external surface | REST/API | gate on real secrets first |
| Ship a research pack | git | same 5-part shape |

## Design law (the why)
- **Tesuji-everywhere:** every gated op measures its outcome (Verkle) and folds a
  decision (skill_ledger), so each automation gets smarter / the failure modes get known.
- **Bytes not vibes:** the gate is a deterministic check, not an LLM judge.
- **Never ask permission for framework ops; never hand-run a local-imperative op that
  has a path — build the path once, reuse it forever.**
