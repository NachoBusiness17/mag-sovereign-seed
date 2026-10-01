# Steal map — Grok command interface → Mag agent

**Job:** Copy the *interaction contract*, not Grok’s binary.

## What Grok TUI owns (img reference)

| Affordance | Grok |
|------------|------|
| Compose | Bottom bar, multi-line |
| Send | Enter |
| Newline | Alt+Enter (we also take Shift+Enter) |
| Mode | Shift+Tab |
| Images | Paste → chip with format/size |
| Markdown | Tables, code, hierarchy |
| Tokens | Usage in chrome |
| Tools | Agent loop behind UI |

## Mag steal (implemented)

| Affordance | Mag target |
|------------|------------|
| **Primary UI** | Dashboard **Chat → Agent** (http://127.0.0.1:8765/) |
| Enter / Shift+Enter / Shift+Tab | `app.js` compose |
| Image paste / +file | `POST /api/v1/agent/upload` → `memory/agent_uploads/` + chip |
| Tool loop | `POST /api/v1/agent` → `mag/agent_cli.py` |
| Tables / code | `lightMd` + CSS |
| Quota line | `GET /api/v1/quota` deepseek row |
| CLI host | PowerShell / Windows Terminal (`launch_agent.cmd`) — **not** full Grok chrome |

## What we deliberately don’t steal yet

- Pixel vision into the model (path + metadata only until vision seat exists)
- Grok weekly limit / always-approve chrome
- Native desktop binary

## Operator path when Grok is empty

1. **Mag** shortcut → Chat → **Agent** · Seat DeepSeek  
2. Paste text (Enter send). Paste screenshot (chip attaches path).  
3. CLI only for headless/scripts: `mag.cmd agent --provider deepseek`
