> ## Documentation Index
> Fetch the complete documentation index at: https://docs.z.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Factory Droid

> Methods for Using the GLM Coding Plan in Factory Droid

Factory Droid is an enterprise-grade AI coding agent that lives in your terminal and handles end-to-end development workflows.

Works seamlessly with [Z.AI's GLM Coding Plan](https://z.ai/subscribe) for high-performance models at exceptional value.

## Step 1: Installing Factory Droid

**macOS / Linux:**

```bash theme={null}
curl -fsSL https://app.factory.ai/cli | sh
```

**Windows:**

```powershell theme={null}
irm https://app.factory.ai/cli/windows | iex
```

## Step 2: Configuring Z.AI GLM Models

### 1. Get Your Z.AI API Key

1. Visit the [Z.AI API Console](https://z.ai/manage-apikey/apikey-list)
2. Create an API key if you don't have one

### 2. Configure Custom Models

Factory Droid uses BYOK (Bring Your Own Key) to connect with Z.AI's GLM models.

**Configuration file location**

* macOS/Linux: `~/.factory/settings.json`
* Windows: `%USERPROFILE%\.factory\settings.json`

<Tip>
  Use either method below:\
  Remember to replace `your_api_key` with the API Key you obtained in the previous step.
</Tip>

Method A: Anthropic Protocol

```json theme={null}
{
  "customModels": [
    {
      "displayName": "GLM-4.7 [Z.AI Coding Plan] - Anthropic",
      "model": "glm-4.7",
      "baseUrl": "https://api.z.ai/api/anthropic",
      "apiKey": "your_api_key",
      "provider": "anthropic",
      "maxOutputTokens": 131072
    }
  ]
}
```

Method B: OpenAi Chat Completion Protocol

```json theme={null}
{
  "customModels": [
    {
      "displayName": "GLM-4.7 [Z.AI Coding Plan] - Openai",
      "model": "glm-4.7",
      "baseUrl": "https://api.z.ai/api/coding/paas/v4",
      "apiKey": "your_api_key",
      "provider": "generic-chat-completion-api",
      "maxOutputTokens": 131072
    }
  ]
}
```

**Important notes**

* GLM Coding Plan users must use the Coding API endpoint: `https://api.z.ai/api/coding/paas/v4`
* Standard plan users use the general API endpoint: `https://api.z.ai/api/paas/v4`
* Replace `your_api_key` with your actual API key
* API keys are stored locally and never uploaded to Factory servers

## Step 3: Start Using Factory Droid

### 1. Launch Droid

Navigate to your project directory and start droid:

```bash theme={null}
cd /path/to/your/project
droid
```

On first launch, you'll be prompted to sign in via your browser to connect to Factory's services.

### 2. Select Your Z.AI Model

Once droid is running, use the `/model` command to select your Z.AI GLM model:

```
/model
```

Your custom Z.AI models will appear in a separate "Custom models" section. Select the GLM model you configured.

### 3. Start Coding

Use droid for tasks like analyzing code, implementing features, fixing bugs, reviewing changes, and more.

## Key Features

**Specification Mode**

* Press **Shift+Tab** to activate
* Describe features in plain language
* Get automatic planning before implementation
* Approve plans before any code changes

**Auto-Run Mode**

* **Low**: Edits and read-only commands
* **Medium**: Reversible commands (package installs, builds, local git, etc.)
* **High**: All commands except explicitly dangerous ones
* Cycle modes with **Shift+Tab**

**IDE Integration**

* **VS Code/Cursor/Windsurf**: Auto-installs when you run `droid`
* **JetBrains**: Install plugin from marketplace
* Features: Interactive diffs, auto-shares current file/selection, quick launch

**AGENTS.md — Project Conventions**

Document your workflow at repo root:

```markdown theme={null}
# Build & Test
- Test: `npm test`
- Build: `npm run build`

# Conventions
- TypeScript strict mode
- 100-char line limit
- Tests required for features
```

Droid automatically follows your team's practices.

**Additional Features**

* Cost tracking with `/cost` command
* SOC-2 compliant with enterprise deployment options
* Integrations: Jira, Notion, Slack, GitHub
* MCP (Model Context Protocol) support
* Transparent review workflow for every change

## Resources

* **Documentation**: [docs.factory.ai](https://docs.factory.ai/cli/getting-started/overview)
* **BYOK Configuration**: [docs.factory.ai/cli/byok/overview](https://docs.factory.ai/cli/byok/overview)
* **Support**: [support@factory.ai](mailto:support@factory.ai)
