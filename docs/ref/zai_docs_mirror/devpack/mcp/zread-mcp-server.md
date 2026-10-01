> ## Documentation Index
> Fetch the complete documentation index at: https://docs.z.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Zread MCP Server

The ZRead MCP Server is an exclusive Remote MCP Server developed by Z.AI for GLM Coding Plan users. Built on the Model Context Protocol (MCP) and powered by zread.ai, it provides access to open-source repository documentation, code structures, and file contents for MCP-compatible clients, including Claude Code and Cline.

## Features

<CardGroup cols={3}>
  <Card title="Documentation Search" icon="book">
    Search documentation, code, and comments in Github repositories
  </Card>

  <Card title="Repository Structure" icon="sitemap">
    Get the directory structure and file list of GitHub repositories to quickly master project layout
  </Card>

  <Card title="Code Reading" icon="code">
    Read the complete code content of specified files in GitHub repositories to deeply analyze implementation details
  </Card>
</CardGroup>

## Tools

This server implements the Model Context Protocol and works with any MCP-compatible client. Currently, it provides the following tools:

* **`search_doc`** — Search for knowledge documentation corresponding to the GitHub repository, quickly understanding repository knowledge, news, recent issues, PRs, and contributors.
* **`get_repo_structure`** — Get the directory structure and file list of the GitHub repository to understand project module splitting and directory organization.
* **`read_file`** — Read the complete code content of specified files in the GitHub repository to deeply analyze the implementation details of the file code.

## Example Scenarios

<AccordionGroup>
  <Accordion title="Quick Start with Open Source Libraries" defaultOpen>
    Quickly understand the core concepts, installation steps, and code organization of open source libraries by searching documentation and obtaining repository structures, accelerating the learning curve.
  </Accordion>

  <Accordion title="Issue Troubleshooting and History" defaultOpen>
    When encountering problems, search the repository's Issue and Commit history to find solutions or fix records for similar problems.
  </Accordion>

  <Accordion title="Deep Source Code Analysis">
    Directly read the code content of core files, analyze implementation logic, and assist in secondary development or Debugging.
  </Accordion>

  <Accordion title="Dependency Library Research">
    Before introducing a new dependency library, evaluate its activity, code quality, and maintenance status by viewing its repository structure and documentation.
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
    claude mcp add -s user -t http zread https://api.z.ai/api/mcp/zread/mcp --header "Authorization: Bearer your_api_key"
    ```

    **Manual configuration**

    Edit the Claude Code configuration file under your home directory, the MCP section of `.claude.json`:

    ```json theme={null}
    {
      "mcpServers": {
        "zread": {
          "type": "http",
          "url": "https://api.z.ai/api/mcp/zread/mcp",
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
        "zread": {
          "type": "streamableHttp",
          "url": "https://api.z.ai/api/mcp/zread/mcp",
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
        "zread": {
          "type": "sse",
          "url": "https://api.z.ai/api/mcp/zread/sse?Authorization=your_api_key"
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
            "zread": {
                "type": "remote",
                "url": "https://api.z.ai/api/mcp/zread/mcp",
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
            "zread": {
                "type": "http",
                "url": "https://api.z.ai/api/mcp/zread/mcp",
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

    Set Extension Name to `zread`, Type to `HTTP`, and use the following endpoint:

    ```
    https://api.z.ai/api/mcp/zread/mcp
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
        "zread": {
          "type": "streamable-http",
          "url": "https://api.z.ai/api/mcp/zread/mcp",
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

  <Accordion title="Repository access failed">
    **Issue:** Unable to search or read specified repository content

    **Solutions:**

    1. Confirm the repository exists and is open source (public)
    2. Check if the repository name is spelled correctly (owner/repo)
    3. Visit zread.ai to search if this open source repository is supported
  </Accordion>
</AccordionGroup>

## Resources

* [Model Context Protocol (MCP) Documentation](https://modelcontextprotocol.io/)
* [Claude Code MCP Configuration Guide](https://docs.anthropic.com/en/docs/claude-code/mcp)
* [MCP Usage Limits](/devpack/overview#usage-instruction)
* [GLM Coding Plan Overview](/devpack/overview)
