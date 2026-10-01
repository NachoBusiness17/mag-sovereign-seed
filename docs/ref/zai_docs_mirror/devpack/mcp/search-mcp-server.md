> ## Documentation Index
> Fetch the complete documentation index at: https://docs.z.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Web Search MCP Server

The Web Search MCP Server is an exclusive Remote MCP Server developed by Z.AI for GLM Coding Plan users. Built on the Model Context Protocol (MCP), it connects to search capabilities to provide web search and real-time information retrieval for MCP-compatible clients, including Claude Code and Cline.

## Features

<CardGroup cols={3}>
  <Card title="Web Search" icon="globe">
    Supports comprehensive web search to retrieve the latest web information and resources
  </Card>

  <Card title="Real-time Information" icon="clock">
    Retrieves real-time updated information including news, stock prices, weather, and more
  </Card>

  <Card title="Remote Service" icon="link">
    HTTP protocol-based remote MCP service, no local installation required
  </Card>
</CardGroup>

## Supported Tools

This server implements the Model Context Protocol and can be used with any MCP-compatible client. Currently provides the following tools:

* **`webSearchPrime`** - Search web information, returning results including page titles, URLs, summaries, site names, site icons, and more.

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
    **One-click Installation Command**

    Be sure to replace `your_api_key` with the API Key you obtained.

    ```bash theme={null}
    claude mcp add -s user -t http web-search-prime https://api.z.ai/api/mcp/web_search_prime/mcp --header "Authorization: Bearer your_api_key"
    ```

    **Manual Configuration**

    Edit Claude Code's configuration file `.claude.json` in the user directory, MCP section:

    ```json theme={null}
    {
      "mcpServers": {
        "web-search-prime": {
          "type": "http",
          "url": "https://api.z.ai/api/mcp/web_search_prime/mcp",
          "headers": {
            "Authorization": "Bearer your_api_key"
          }
        }
      }
    }
    ```
  </Tab>

  <Tab title="Cline (VS Code)">
    Add MCP server configuration in Cline extension settings:

    Be sure to replace `your_api_key` with the API Key you obtained.

    ```json theme={null}
    {
      "mcpServers": {
        "web-search-prime": {
          "type": "streamableHttp",
          "url": "https://api.z.ai/api/mcp/web_search_prime/mcp",
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
        "web-search-prime": {
          "type": "sse",
          "url": "https://api.z.ai/api/mcp/web_search_prime/sse?Authorization=your_api_key"
        }
      }
    }
    ```
  </Tab>

  <Tab title="OpenCode">
    Add MCP server configuration in OpenCode settings:

    Refer [OpenCode MCP Doc](https://opencode.ai/docs/mcp-servers)

    Be sure to replace `your_api_key` with the API Key you obtained.

    ```json theme={null}
    {
        "$schema": "https://opencode.ai/config.json",
        "mcp": {
            "web-search-prime": {
                "type": "remote",
                "url": "https://api.z.ai/api/mcp/web_search_prime/mcp",
                "headers": {
                    "Authorization": "Bearer your_api_key"
                }
            }
        }
    }
    ```
  </Tab>

  <Tab title="Crush">
    Add MCP server configuration in Crush settings:

    Be sure to replace `your_api_key` with the API Key you obtained.

    ```json theme={null}
    {
        "$schema": "https://charm.land/crush.json",
        "mcp": {
            "web-search-prime": {
                "type": "http",
                "url": "https://api.z.ai/api/mcp/web_search_prime/mcp",
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

    Add MCP server configuration in Goose settings:

    Click `Extensions` -> `Add custom extension`

    Set `Extension Name` is `web-search-prime`，`Type` switch `HTTP`，`Endpoint` as follow：

    ```
    https://api.z.ai/api/mcp/web_search_prime/mcp
    ```

    Set Request Headers Add `Authorization` : `your_api_key`

    Finally, click `Add Extension` at the bottom. Remember to replace your\_api\_key with the API Key you obtained in the previous step.
  </Tab>

  <Tab title="Roo Code, Kilo Code and Other MCP Clients">
    For Roo Code, Kilo Code and other clients that support MCP protocol, use the following general configuration:

    Be sure to replace `your_api_key` with the API Key you obtained.

    ```json theme={null}
    {
      "mcpServers": {
        "web-search-prime": {
          "type": "streamable-http",
          "url": "https://api.z.ai/api/mcp/web_search_prime/mcp",
          "headers": {
            "Authorization": "Bearer your_api_key"
          }
        }
      }
    }
    ```
  </Tab>
</Tabs>

## Usage Example

Through the previous step of installing the Search MCP server to the client, you can directly use MCP in your Coding client.\
You can directly use search functionality in conversations:

* "Help me search for the latest AI technology developments"
* "Find best practices for Python asynchronous programming"

## Troubleshooting

<AccordionGroup>
  <Accordion title="Invalid API Key">
    **Issue:** Receiving invalid api key error

    **Solutions:**

    1. Confirm the api key is correctly copied
    2. Check if the api key is activated
    3. Confirm the api key has sufficient balance
    4. Check if the Authorization header format is correct
  </Accordion>

  <Accordion title="Connection Timeout">
    **Issue:** MCP server connection timeout

    **Solutions:**

    1. Check network connection
    2. Confirm firewall settings
    3. Verify the server URL is correct
    4. Increase timeout settings
  </Accordion>

  <Accordion title="Empty Search Results">
    **Issue:** Search returns empty results

    **Solutions:**

    1. Try using different search keywords
    2. Check if the search query is too specific
    3. Confirm network connection is normal
    4. Contact technical support for assistance
  </Accordion>
</AccordionGroup>

## Related Resources

* [Model Context Protocol (MCP) Official Documentation](https://modelcontextprotocol.io/)
* [Claude Code MCP Configuration Guide](https://docs.anthropic.com/en/docs/claude-code/mcp)
* [MCP Usage Limits](/devpack/overview#usage-instruction)
* [GLM Coding Plan Overview](/devpack/overview)
