> ## Documentation Index
> Fetch the complete documentation index at: https://docs.z.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Quick Start

<Tip>
  This guide will help you get started with [GLM Coding Plan](https://z.ai/subscribe?utm_source=zai\&utm_medium=link\&utm_term=quickstart\&utm_campaign=Platform_Ops&_channel_track_key=DRUfXN42) in minutes—from subscribing to using GLM models in officially [supported tools and products](https://docs.z.ai/devpack/tool/others#step-1-supported-tools).
</Tip>

## Getting Started

<Steps>
  <Step title="Register or Login">
    * Access [Z.AI Open Platform](https://z.ai/model-api), Register or Login.
  </Step>

  <Step title="Subscribe to GLM Coding Plan">
    After logging in, navigate to the [GLM Coding Plan](https://z.ai/subscribe?utm_source=zai\&utm_medium=link\&utm_term=quickstart\&utm_campaign=Platform_Ops&_channel_track_key=DRUfXN42) to select your preferred subscription plan.
  </Step>

  <Step title="Obtain API Key">
    After subscribing,

    Individual Plan users can create an API Key under [Individual Coding Plan > Plan Overview](https://z.ai/manage-apikey/apikey-list).

    Team Plan members can obtain their API Key under [Team Coding Plan > My Plan](https://z.ai/manage-apikey/coding-plan/team/my-plan). The Team Plan Key is not interchangeable with other Z.AI's API Keys. To use your Team Plan quota, make sure to use the Team Plan Key.

    <Warning>
      Safeguard your API Key by keeping it confidential and avoiding hard-coding it in your code.
    </Warning>
  </Step>

  <Step title="Connect a Coding Tool">
    The GLM Coding Plan is strictly limited to use within officially [supported tools and products](https://docs.z.ai/devpack/tool/others#step-1-supported-tools). Click a tool below to open its configuration guide:

    <CardGroup cols={3}>
      <Card title="Claude Code" color="#ffffff" href="https://docs.z.ai/devpack/tool/claude" />

      <Card title="Roo Code" color="#ffffff" href="https://docs.z.ai/devpack/tool/roo" />

      <Card title="Kilo Code" color="#ffffff" href="https://docs.z.ai/devpack/tool/kilo" />

      <Card title="Cline" color="#ffffff" href="https://docs.z.ai/devpack/tool/cline" />

      <Card title="OpenCode" color="#ffffff" href="https://docs.z.ai/devpack/tool/opencode" />

      <Card title="OpenClaw" color="#ffffff" href="https://docs.z.ai/devpack/tool/openclaw" />

      <Card title="Crush" color="#ffffff" href="https://docs.z.ai/devpack/tool/crush" />

      <Card title="Goose" color="#ffffff" href="https://docs.z.ai/devpack/tool/goose" />

      <Card title="Cursor" color="#ffffff" href="https://docs.z.ai/devpack/tool/cursor" />

      <Card title="Other Tools" color="#ffffff" href="https://docs.z.ai/devpack/tool/others" />
    </CardGroup>
  </Step>

  <Step title="Endpoint Guide">
    GLM Coding Plan supports both the Anthropic and OpenAI protocols. Make sure to configure the correct `Base URL`:

    | Protocol                | Base URL                              |
    | ----------------------- | ------------------------------------- |
    | Anthropic Messages      | `https://api.z.ai/api/anthropic`      |
    | OpenAI Chat Completions | `https://api.z.ai/api/coding/paas/v4` |
    | OpenAI Responses        | `https://api.z.ai/api/v1`             |
  </Step>

  <Step title="Start Coding">
    Once configured, you can begin coding with the GLM model!

    <Tabs>
      <Tab title="Conversational Programming">
        ```bash theme={null}
        # Using natural language commands in Claude Code
        Please create a React component containing a user login form
        ```
      </Tab>

      <Tab title="Code Debugging">
        ```bash theme={null}
        # Describe the issue encountered
        My API request returns a 404 error. Please help me check the code.
        ```
      </Tab>

      <Tab title="Code Optimization">
        ```bash theme={null}
        # Code optimization
        This function performs poorly. Please optimize it for me.
        ```
      </Tab>
    </Tabs>
  </Step>
</Steps>

## Advanced Features

<AccordionGroup>
  <Accordion title="Vision MCP Server (Coding Plan Exclusive)">
    All users can utilize the Vision MCP Server, which employs the flagship vision reasoning model GLM-4.6V to comprehend and analyze image content.

    * Analyze UI design mockups and generate corresponding code
    * Understand flowcharts and architecture diagrams
    * Extract text and information from screenshots

    For detailed usage instructions, refer to the [Vision MCP Server](/devpack/mcp/vision-mcp-server) documentation.
  </Accordion>

  <Accordion title="Web Search MCP Server (Coding Plan Exclusive)">
    All users can utilize the Web Search MCP Server to access the latest technical information.

    * Search for the latest technical documentation and API changes
    * Obtain the latest information on open-source projects
    * Find solutions and best practices

    For detailed usage instructions, refer to the [Web Search MCP Server](/devpack/mcp/search-mcp-server) documentation.
  </Accordion>

  <Accordion title="Web Reader MCP Server (Coding Plan Exclusive)">
    All users can utilize the Web Reader MCP Server to fetch full webpage content and extract structured data.

    * Fetch complete webpage content including text, and links
    * Extract structured data such as title, body, and metadata
    * Remote HTTP-based MCP service, no local installation required

    For detailed usage instructions, refer to the [Web Reader MCP Server](/devpack/mcp/reader-mcp-server) documentation.
  </Accordion>
</AccordionGroup>
