> ## Documentation Index
> Fetch the complete documentation index at: https://docs.z.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Web Reader MCP Server

The Web Reader MCP Server is an exclusive Remote MCP Server developed by Z.AI for GLM Coding Plan users. Built on the Model Context Protocol (MCP), it connects to webpage content extraction capabilities to provide webpage content extraction, detailed page reading, and structured data retrieval for MCP-compatible clients, including Claude Code and Cline.

## Features

<CardGroup cols={3}>
  <Card title="Web Content Reading" icon="globe">
    Fetch the complete content of any webpage, including text, and links
  </Card>

  <Card title="Structured Data" icon="clock">
    Extract structured data such as title, main body, and metadata
  </Card>

  <Card title="Remote Service" icon="link">
    HTTP-based remote MCP service, no local installation required
  </Card>
</CardGroup>

## Tools

This server implements the Model Context Protocol and works with any MCP-compatible client. Currently, it provides the following tool:

* **`webReader`** — Fetch webpage content for a specified URL. Returns the page title, main content, metadata, list of links, and more.

## Example Scenarios

<AccordionGroup>
  <Accordion title="API Documentation Reading and Summarization" defaultOpen>
    Automatically fetch and parse titles, body content, examples, and release notes from official documentation pages, distilling key takeaways to accelerate integration and implementation.
  </Accordion>

  <Accordion title="Open Source Project Page Parsing" defaultOpen>
    Parse project websites or repository pages (such as README, release notes, and usage guides) to extract core information and link lists, assisting evaluation and integration.
  </Accordion>

  <Accordion title="Technical Article Understanding and Knowledge Extraction">
    Extract steps, commands, and caveats from blogs, tutorials, and guide pages, organizing unstructured content into actionable developer notes and task lists.
  </Accordion>

  <Accordion title="Bug Resolution Using Reference Documentation">
    For issue remediation, read the publicly available steps on the specified web page and use them as references to resolve the problem.
  </Accordion>

  <Accordion title="Knowledge Base Construction and Synchronization">
    Convert content from designated web pages into structured data and leverage in-page links for incremental synchronization to build a team technical knowledge base.
  </Accordion>
</AccordionGroup>

## Installation and Usage

### Quick Start

<Steps>
  <Step title="Get API Key">
    Visit [Z.AI Console](https://z.ai/manage-apikey/apikey-list) to get your api key
  </Step>

  <Step title="Configure MCP Server">
    According to the client you’re using, **choose the corresponding installation method from the options below**.
  </Step>
</Steps>

### Supported Clients

<Tabs>
  <Tab title="Claude Code">
    **One-click install command**

    Replace `your_api_key` with the API key you obtained in the previous step

    ```bash theme={null}
    claude mcp add -s user -t http web-reader https://api.z.ai/api/mcp/web_reader/mcp --header "Authorization: Bearer your_api_key"
    ```

    **Manual configuration**

    Edit the Claude Code configuration file under your home directory, the MCP section of `.claude.json`:

    ```json theme={null}
    {
      "mcpServers": {
        "web-reader": {
          "type": "http",
          "url": "https://api.z.ai/api/mcp/web_reader/mcp",
          "headers": {
            "Authorization": "Bearer your_api_key"
          }
        }
      }
    }
    ```
  </Tab>

  <Tab title="Cline (VS Code)">
    Add the MCP server configuration in the Cline extension settings:

    Replace `your_api_key` with the API key you obtained in the previous step

    ```json theme={null}
    {
      "mcpServers": {
        "web-reader": {
          "type": "streamableHttp",
          "url": "https://api.z.ai/api/mcp/web_reader/mcp",
          "headers": {
            "Authorization": "Bearer your_api_key"
          }
        }
      }
    }
    ```

    If Cline older version does not support StreamableHttp type MCP server, you can use SSE type configuration:

    ```json theme={null}
    {
      "mcpServers": {
        "web-reader": {
          "type": "sse",
          "url": "https://api.z.ai/api/mcp/web_reader/sse?Authorization=your_api_key"
        }
      }
    }
    ```
  </Tab>

  <Tab title="OpenCode">
    Add the MCP server configuration in OpenCode settings:

    See the [OpenCode MCP documentation](https://opencode.ai/docs/mcp-servers)

    Replace `your_api_key` with the API key you obtained in the previous step

    ```json theme={null}
    {
        "$schema": "https://opencode.ai/config.json",
        "mcp": {
            "web-reader": {
                "type": "remote",
                "url": "https://api.z.ai/api/mcp/web_reader/mcp",
                "headers": {
                    "Authorization": "Bearer your_api_key"
                }
            }
        }
    }
    ```
  </Tab>

  <Tab title="Crush">
    Add the MCP server configuration in Crush settings:

    Replace `your_api_key` with the API key you obtained in the previous step

    ```json theme={null}
    {
        "$schema": "https://charm.land/crush.json",
        "mcp": {
            "web-reader": {
                "type": "http",
                "url": "https://api.z.ai/api/mcp/web_reader/mcp",
                "headers": {
                    "Authorization": "Bearer your_api_key"
                }
            }
        }
    }
    ```
  </Tab>

  <Tab title="Goose">
    Not support Goose now，refer [Issue](https://github.com/block/goose/issues/6576)

    Add the MCP server in Goose:

    Go to `Extensions` -> `Add custom extension`

    Set Extension Name to `web-reader`, Type to `HTTP`, and use the following endpoint:

    ```
    https://api.z.ai/api/mcp/web_reader/mcp
    ```

    Set Request Headers Add `Authorization` : `your_api_key`

    Click `Add Extension` at the bottom. Remember to replace `your_api_key` with the API key you obtained in the previous step.
  </Tab>

  <Tab title="Roo Code, Kilo Code, Others">
    For Roo Code, Kilo Code, and other MCP-compatible clients, use the following general configuration:

    Replace `your_api_key` with the API key you obtained in the previous step

    ```json theme={null}
    {
      "mcpServers": {
        "web-reader": {
          "type": "streamable-http",
          "url": "https://api.z.ai/api/mcp/web_reader/mcp",
          "headers": {
            "Authorization": "Bearer your_api_key"
          }
        }
      }
    }
    ```
  </Tab>
</Tabs>

## Troubleshooting

<AccordionGroup>
  <Accordion title="Invalid access token">
    **Issue:** Received an invalid access token error

    **Solutions:**

    1. Verify the token was copied correctly
    2. Check that the token is activated
    3. Ensure the token has sufficient balance
    4. Confirm the Authorization header format is correct
  </Accordion>

  <Accordion title="Connection timeout">
    **Issue:** Connection to the MCP server timed out

    **Solutions:**

    1. Check your network connection
    2. Verify firewall settings
    3. Ensure the server URL is correct
    4. Increase client timeout settings
  </Accordion>

  <Accordion title="Webpage fetch failed">
    **Issue:** Web content reading returned empty result or error

    **Solutions:**

    1. Confirm the target URL is accessible
    2. Check if the page has anti-scraping mechanisms
    3. Try different URLs
    4. Ensure network connectivity is normal
    5. Contact technical support for assistance
  </Accordion>
</AccordionGroup>

## Resources

* [Model Context Protocol (MCP) Documentation](https://modelcontextprotocol.io/)
* [Claude Code MCP Configuration Guide](https://docs.anthropic.com/en/docs/claude-code/mcp)
* [MCP Usage Limits](/devpack/overview#usage-instruction)
* [GLM Coding Plan Overview](/devpack/overview)
