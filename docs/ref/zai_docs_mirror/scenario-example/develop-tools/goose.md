> ## Documentation Index
> Fetch the complete documentation index at: https://docs.z.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Goose

> Methods for Using the GLM Coding Plan in Goose

Goose is an AI agent tool that supports local or desktop environments and offers a CLI interface. It integrates with multiple models and connects to external tools and APIs via the MCP protocol to automate engineering tasks such as code generation, debugging, testing, and deployment.

Goose is delivering a more stable and efficient functional experience with the [GLM Coding Plan](https://z.ai/subscribe?utm_source=zai\&utm_medium=link\&utm_term=devpack-integration\&utm_campaign=Platform_Ops&_channel_track_key=w3mNdY8g).

<Warning>
  For users who have used the service before 2025-12-22: \
  The default model has been upgraded to GLM-4.7. Please update your config accordingly.
</Warning>

## Step 1: Installing Goose Desktop

1. Visit the official Goose documentation: [Goose Quickstart](https://block.github.io/goose/docs/quickstart/).
2. Choose the installer for your operating system and complete the setup for Goose Desktop.

## Step 2: Creating a New Provider

1. Open the Goose Desktop application and navigate to the main interface.
2. Locate and click **“Create New Provider”** in the left-hand menu (as shown in the figure).
3. Follow the prompts to enter the required information and complete the new Provider creation.

![Description](https://cdn.bigmodel.cn/markdown/1758091325715goose-1.jpeg?attname=goose-1.jpeg)

## Step 3: Select Anthropic Compatible and Configure

1. During Provider Setup, select the **Anthropic Compatible**.
2. Complete the following required configurations:

* **Base URL**: `https://api.z.ai/api/anthropic`
* **API Key**: Your Z.ai API key
* **Model**: Select `GLM-4.7`(standard, complex tasks) or `GLM-4.5-air`(lightweight, faster response) based on your requirements.

3. Save your settings to complete the configuration.

![Description](https://cdn.bigmodel.cn/markdown/1759307955720image.png?attname=image.png)

## Step 4: Switching Models

1. After configuration, return to the Goose desktop main interface.
2. Locate and click "**Switch Models**" at the bottom of the main interface.
3. Select the newly created Provider from the dropdown list.
4. Verify the new Provider has successfully switched to the current model.

![Description](https://cdn.bigmodel.cn/markdown/1758091346221goose-3.jpeg?attname=goose-3.jpeg)

## Step 5: Start Using Goose with GLM

1. Once the provider is active, you can start interacting with Goose powered by GLM-4.7.
2. Enter your request, and Goose will automatically invoke the GLM-4.7 model based on your configuration to generate a response.

![Description](https://cdn.bigmodel.cn/markdown/1758091350444goose-4.jpeg?attname=goose-4.jpeg)

## Step 6: Vision Search Reader MCP

Refer to the [Vision MCP Server](/devpack/mcp/vision-mcp-server) , [Search MCP Server](/devpack/mcp/search-mcp-server) and [Web Reader MCP Server](/devpack/mcp/reader-mcp-server) documentation; once configured, you can use them in Goose.
