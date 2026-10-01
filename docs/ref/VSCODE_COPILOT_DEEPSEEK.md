# VS Code Copilot + DeepSeek V4 (Mag IDE seat)

**Commitment:** `vscode-copilot-deepseek-001`  
**As-of:** 2026-08-07  
**Extension:** [Vizards/deepseek-v4-for-copilot](https://github.com/Vizards/deepseek-v4-for-copilot) (`Vizards.deepseek-v4-for-copilot`)  
**Seat card:** `vscode_copilot_deepseek` in `configs/seat_playbook.yaml`  
**Parent:** `MAG_SEAT_INTELLIGENCE.md` · Mag provider `deepseek` in `configs/providers.yaml`

**One job:** Use DeepSeek V4 **inside** GitHub Copilot Chat (agent, tools, skills) with the **same** API identity Mag already uses — without inventing a second model stack.

---

## What this seat is / is not

| | |
|--|--|
| **Is** | Interactive IDE seat: Copilot UI + BYOK DeepSeek V4 Flash/Pro |
| **Is** | Same endpoint models as Mag (`deepseek-v4-flash`, `deepseek-v4-pro`) |
| **Is not** | Headless orchestrator drain (`v3_deepseek_run`, `agent --provider deepseek`) |
| **Is not** | Cursor seat (separate: `cursor_ide` / `cursor_cloud_agent`) |
| **Is not** | Continuity DNA — chat stays disposable; FILE trail/handoff |

---

## Prerequisites

1. VS Code **≥ 1.116** (extension needs Copilot Chat provider APIs; may break on bumps).
2. GitHub Copilot (Free/Pro/Enterprise) signed in — Chat is built-in; you do not need marketplace Copilot Chat install.
3. Extension: `Vizards.deepseek-v4-for-copilot` (workspace recommends it via `.vscode/extensions.json`).
4. DeepSeek API key — same family as Mag `DEEPSEEK_API_KEY` / overmind chain. **Never** put the key in `settings.json`.

---

## One-time setup

```text
1. Open Mag folder in VS Code
2. Install recommended extension if prompted (or: code --install-extension Vizards.deepseek-v4-for-copilot)
3. Command Palette → DeepSeek: Set API Key → paste key (OS keychain / SecretStorage)
4. Copilot Chat → model picker → DeepSeek V4 Flash or DeepSeek V4 Pro
5. Optional: DeepSeek: Configure Vision Proxy (images → another Copilot vision model → text to DeepSeek)
```

Settings already aligned with Mag (user + workspace):

| Setting | Value |
|---------|--------|
| `deepseek-copilot.baseUrl` | `https://api.deepseek.com` |
| `deepseek-copilot.modelIdOverrides` | flash/pro → official ids |
| `deepseek-copilot.debugMode` | `minimal` |
| `deepseek-copilot.experimental.stabilizeToolList` | `false` (leave off unless tool list thrash) |

Thinking effort is **per model in the picker**, not Mag `providers.yaml`.

---

## Route law (when to pick this seat)

| Job | Seat |
|-----|------|
| Headless build / queue drain / improve worker | **`deepseek_api`** — Mag agent |
| Interactive multi-file edit inside VS Code Copilot | **`vscode_copilot_deepseek`** |
| Cursor-native agent / cloud run | **`cursor_*`** |
| Plan / steal / scarce judgment | **`grok_tui`** |
| Scut / local | **`ollama_*`** |

**Default Mag router unchanged:** frozen BUILD → Mag DeepSeek agent. This seat is for when you are already in VS Code and want Copilot agent UX on DeepSeek billing.

---

## Mag vs Copilot thinking defaults

| Path | Thinking |
|------|----------|
| Mag `providers.yaml` | `disable_thinking: true` (avoids empty content on small budgets) |
| Copilot picker | Flash: none/low/high/max · Pro: none/high/max — pick for task |

Do not assume the two paths share reasoning settings. Prefer **Flash + none/low** for cheap iteration; **Pro + high/max** for hard agent turns.

---

## After work

- FILE outcomes: trail, handoff JSON, or `memory/working` — not “it’s in Copilot history.”
- Cost: DeepSeek bill (BYOK) + Copilot subscription for the UI/tools shell.
- Breaks after VS Code upgrade: open extension issues; temporarily fall back to Mag `agent --provider deepseek`.

---

## Smoke checklist

- [ ] Extension shows in Extensions list
- [ ] API key set via command (not settings dump)
- [ ] Model picker lists DeepSeek V4 Flash and Pro
- [ ] One agent turn edits a file under Mag workspace
- [ ] Mag `doctor` / DeepSeek key still green for headless path
