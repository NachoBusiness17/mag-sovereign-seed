# Z.AI DOCS MIRROR — INDEX

> **Provenance:** mirrored from https://docs.z.ai (the official Z.AI developer documentation site, Mintlify-hosted).
> **Mirror date:** 2026-09-04 (llms-full.txt vendor Last-Modified 2026-09-03T21:55:58Z).
> **Doors used:** (1) https://docs.z.ai/llms-full.txt — EXISTS, 647,819 bytes, whole-docs capture (the 90% door confirmed); (2) https://docs.z.ai/llms.txt — index, 68 pages; (3) sitemap.xml — 67 URLs; (4) per-page `.md` raw-markdown endpoints — every page fetched via curl as raw markdown.
> **License note:** vendor docs mirrored for internal fleet use only. Copyright z.ai. Do not republish, redistribute, or feed to external parties; internal reference shelf per the wall-ledger law.

**Coverage:** 86/86 pages mirrored (100% fetch rate; 85 pages with full vendor content; 1 documented gap: `api-reference/rate-limit.md` — page moved vendor-side to the z.ai console docs, HTML-only). Plus `openapi.json` (valid, 14 endpoint paths) and the raw door captures in `_raw/`.

Index completeness finding (2026-09-04): the vendor's own maps are INCOMPLETE. `scenario-example/*` (6 pages) appears in NEITHER llms.txt NOR sitemap.xml, and 12 model-guide pages (retired GLM generations glm-4.5/4.6/4.7/5/5.1, glm-4-32b, VLMs glm-4.5v/4.6v/autoglm-phone, image glm-image/cogview-4, video cogvideox-3) are linked by live pages but absent from both indexes — found via link-graph closure + live probing. Anything not listed here is Unproven to exist.

---

## guides/

- `guides/overview/concept-param.md` — Core Parameters — When interacting with models, you can control the model's output by adjusting different parameters to meet the (10575 bytes) [source](https://docs.z.ai/guides/overview/concept-param)
- `guides/overview/migrate-to-glm-new.md` — Migrate to GLM-5.3 — This guide explains how to migrate your calls from GLM-5.2 or other earlier models to our latest flagship mode (7641 bytes) [source](https://docs.z.ai/guides/overview/migrate-to-glm-new)
- `guides/overview/overview.md` — Overview — Z.AI offers a variety of models and agents to meet the needs of different scenarios. Choosing the right model  (13160 bytes) [source](https://docs.z.ai/guides/overview/overview)
- `guides/overview/pricing.md` — Pricing — | Model | Input | Cached Input | Cached Input Storage | Output | (3704 bytes) [source](https://docs.z.ai/guides/overview/pricing)
- `guides/overview/quick-start.md` — Quick Start — Tired of limits? GLM Coding Plan — monthly access to world-class models, compatible with top coding tools like (11309 bytes) [source](https://docs.z.ai/guides/overview/quick-start)
- `guides/llm/glm-4-32b-0414-128k.md` — GLM-4-32B-0414-128K — GLM-4-32B-0414-128K is a highly cost-effective foundation language model. It can efficiently perform complex t (11697 bytes) [source](https://docs.z.ai/guides/llm/glm-4-32b-0414-128k)
- `guides/llm/glm-4.5.md` — GLM-4.5 — GLM-4.5 and GLM-4.5-Air are Z.AI's models, purpose-built as foundational models for agent-oriented application (27634 bytes) [source](https://docs.z.ai/guides/llm/glm-4.5)
- `guides/llm/glm-4.6.md` — GLM-4.6 — GLM-4.6 achieves comprehensive enhancements across multiple domains, including real-world coding, long-context (15540 bytes) [source](https://docs.z.ai/guides/llm/glm-4.6)
- `guides/llm/glm-4.7.md` — GLM-4.7 — Tired of limits? Get premium performance at a fraction of the cost, fully compatible with top coding tools lik (25488 bytes) [source](https://docs.z.ai/guides/llm/glm-4.7)
- `guides/llm/glm-5.1.md` — GLM-5.1 — **GLM-5.1** is Z.AI’s latest flagship model, designed for **long-horizon tasks**. It can work continuously and (19347 bytes) [source](https://docs.z.ai/guides/llm/glm-5.1)
- `guides/llm/glm-5.2.md` — GLM-5.2 — **GLM-5.2** is a flagship model built for the era of long-horizon tasks. With truly usable 1M-token context, i (25293 bytes) [source](https://docs.z.ai/guides/llm/glm-5.2)
- `guides/llm/glm-5.3.md` — GLM-5.3 — GLM-5.3 is now available to all GLM Coding Plan users, with 50% better coding performance! [**Subscribe now**] (23446 bytes) [source](https://docs.z.ai/guides/llm/glm-5.3)
- `guides/llm/glm-5.md` — GLM-5 — Tired of limits? GLM-5 access is currently available for GLM Coding Plan **Pro and Max** — monthly access to w (19040 bytes) [source](https://docs.z.ai/guides/llm/glm-5)
- `guides/vlm/autoglm-phone-multilingual.md` — AutoGLM-Phone-Multilingual — AutoGLM-Phone-Multilingual is a mobile intelligent assistant framework built on vision-language models. It und (7190 bytes) [source](https://docs.z.ai/guides/vlm/autoglm-phone-multilingual)
- `guides/vlm/glm-4.5v.md` — GLM-4.5V — GLM-4.5V is Z.AI's new generation of visual reasoning models based on the MOE architecture. With a total of 10 (15693 bytes) [source](https://docs.z.ai/guides/vlm/glm-4.5v)
- `guides/vlm/glm-4.6v.md` — GLM-4.6V — GLM-4.6V series are Z.ai's iterations in a multimodal large language model. GLM-4.6V scales its context window (41342 bytes) [source](https://docs.z.ai/guides/vlm/glm-4.6v)
- `guides/vlm/glm-5.3-flash.md` — GLM-5.3-Flash — GLM-5.3-Flash is now fully available on the [GLM Coding Plan](https://z.ai/subscribe). With native multimodal  (23575 bytes) [source](https://docs.z.ai/guides/vlm/glm-5.3-flash)
- `guides/vlm/glm-ocr.md` — GLM-OCR — GLM-OCR is a lightweight professional OCR model with parameters as small as 0.9B, yet it achieves state-of-the (9382 bytes) [source](https://docs.z.ai/guides/vlm/glm-ocr)
- `guides/audio/glm-asr-2512.md` — GLM-ASR-2512 — GLM-ASR-2512 is Z.AI's next-generation speech recognition model, enabling real-time conversion of speech into  (5283 bytes) [source](https://docs.z.ai/guides/audio/glm-asr-2512)
- `guides/image/cogview-4.md` — CogView-4 — CogView-4 is Z.AI’s first open-source text-to-image model. It has comprehensive improvements in semantic under (10521 bytes) [source](https://docs.z.ai/guides/image/cogview-4)
- `guides/image/glm-image.md` — GLM-Image — GLM-Image is Z.AI's new flagship image generation model, which adopts an original hybrid architecture of "auto (15806 bytes) [source](https://docs.z.ai/guides/image/glm-image)
- `guides/capabilities/cache.md` — Context Caching — Context caching functionality significantly reduces token consumption and response latency by caching repeated (17788 bytes) [source](https://docs.z.ai/guides/capabilities/cache)
- `guides/capabilities/function-calling.md` — Function Calling — Function Calling allows AI models to call external functions and APIs, greatly expanding the capability bounda (18911 bytes) [source](https://docs.z.ai/guides/capabilities/function-calling)
- `guides/capabilities/stream-tool.md` — Tool Streaming Output — Stream Tool Call is a unique feature of Z.ai's latest model, allowing real-time access to reasoning processes, (5370 bytes) [source](https://docs.z.ai/guides/capabilities/stream-tool)
- `guides/capabilities/streaming.md` — Streaming Messages — Streaming Messages allow real-time content retrieval while the model generates responses, without waiting for  (4781 bytes) [source](https://docs.z.ai/guides/capabilities/streaming)
- `guides/capabilities/struct-output.md` — Structured Output — Structured output (JSON mode) ensures that AI returns JSON data conforming to predefined formats, providing re (33913 bytes) [source](https://docs.z.ai/guides/capabilities/struct-output)
- `guides/capabilities/thinking-mode.md` — Thinking Mode — GLM offers multiple thinking modes for different scenarios. The sections below explain how to enable each mode (6890 bytes) [source](https://docs.z.ai/guides/capabilities/thinking-mode)
- `guides/capabilities/thinking.md` — Deep Thinking — Deep Thinking is an advanced reasoning feature that enables Chain of Thought mechanisms, allowing the model to (11848 bytes) [source](https://docs.z.ai/guides/capabilities/thinking)
- `guides/tools/stream-tool.md` — Stream Tool Call — Stream Tool Call is a unique feature of Z.ai's latest GLM-4.6 model, allowing real-time access to reasoning pr (5444 bytes) [source](https://docs.z.ai/guides/tools/stream-tool)
- `guides/tools/web-search.md` — Web Search — Z.AI provides developers with a full suite of AI search tools, covering three core services: **basic search (W (50693 bytes) [source](https://docs.z.ai/guides/tools/web-search)
- `guides/develop/http/introduction.md` — HTTP API Calls — Z.AI provides standard HTTP API interfaces that support multiple programming languages and development environ (10110 bytes) [source](https://docs.z.ai/guides/develop/http/introduction)
- `guides/develop/java/introduction.md` — Official Java SDK — Z.AI Java SDK is the official Java development toolkit provided by Z.AI, offering Java developers convenient a (14873 bytes) [source](https://docs.z.ai/guides/develop/java/introduction)
- `guides/develop/langchain/introduction.md` — LangChain Integration — LangChain is a framework for developing applications powered by language models. Z.AI's integration with LangC (8376 bytes) [source](https://docs.z.ai/guides/develop/langchain/introduction)
- `guides/develop/openai/python.md` — OpenAI Python SDK — Z.AI provides interfaces compatible with OpenAI API, which means you can use existing OpenAI SDK code and seam (11410 bytes) [source](https://docs.z.ai/guides/develop/openai/python)
- `guides/develop/python/introduction.md` — Official Python SDK — Z.AI Python SDK is the official Python development toolkit provided by Z.AI, offering Python developers conven (14652 bytes) [source](https://docs.z.ai/guides/develop/python/introduction)
- `guides/agents/slide.md` — GLM Slide/Poster Agent(beta) — GLM Slide/Poster Agent is an intelligent creation agent built for working people and creators. Powered by the  (4543 bytes) [source](https://docs.z.ai/guides/agents/slide)
- `guides/agents/translation.md` — Translation Agent — An AI-powered translation agent designed for multilingual communication and content localization, supporting a (13219 bytes) [source](https://docs.z.ai/guides/agents/translation)
- `guides/agents/video-template.md` — Video Effect Template Agent — Includes three popular special effects video templates: french\_kiss, bodyshake, and sexy\_me. Users can uploa (7339 bytes) [source](https://docs.z.ai/guides/agents/video-template)

## api-reference/

- `api-reference/agents/agent-conversation.md` — Conversation History — ````yaml POST /v1/agents/conversation (5279 bytes) [source](https://docs.z.ai/api-reference/agents/agent-conversation)
- `api-reference/agents/agent.md` — Agent Chat — Popular Special Effects Videos: Popular special effects videos are intelligent templates launched based on tre (26208 bytes) [source](https://docs.z.ai/api-reference/agents/agent)
- `api-reference/agents/file-upload.md` — File Upload — * Files retained for 180 days (3871 bytes) [source](https://docs.z.ai/api-reference/agents/file-upload)
- `api-reference/agents/get-async-result.md` — Retrieve Result — ````yaml POST /v1/agents/async-result (4496 bytes) [source](https://docs.z.ai/api-reference/agents/get-async-result)
- `api-reference/api-code.md` — Errors — When calling the API, the response code consists of two parts: the outer layer is the HTTP status code, and th (11753 bytes) [source](https://docs.z.ai/api-reference/api-code)
- `api-reference/audio/audio-transcriptions.md` — Audio Transcriptions — ````yaml POST /paas/v4/audio/transcriptions (6362 bytes) [source](https://docs.z.ai/api-reference/audio/audio-transcriptions)
- `api-reference/image/generate-image-async.md` — Generate Image(Async) — ````yaml POST /paas/v4/async/images/generations (5104 bytes) [source](https://docs.z.ai/api-reference/image/generate-image-async)
- `api-reference/image/generate-image.md` — Generate Image — ````yaml POST /paas/v4/images/generations (6414 bytes) [source](https://docs.z.ai/api-reference/image/generate-image)
- `api-reference/image/get-image-status.md` — Retrieve Result — ````yaml GET /paas/v4/async-result/{id} (4452 bytes) [source](https://docs.z.ai/api-reference/image/get-image-status)
- `api-reference/introduction.md` — Introduction — The API reference describes the RESTful APIs you can use to interact with the Z.AI platform. (8452 bytes) [source](https://docs.z.ai/api-reference/introduction)
- `api-reference/llm/chat-completion.md` — Chat Completion — ````yaml POST /paas/v4/chat/completions (44133 bytes) [source](https://docs.z.ai/api-reference/llm/chat-completion)
- `api-reference/rate-limit.md` — Rate Limits [GAP — page moved vendor-side] **[GAP]** (799 bytes) [source](https://docs.z.ai/api-reference/rate-limit (307 on 2026-09-04))
- `api-reference/tools/layout-parsing.md` — Layout Parsing — ````yaml POST /paas/v4/layout_parsing (8240 bytes) [source](https://docs.z.ai/api-reference/tools/layout-parsing)
- `api-reference/tools/tokenizer.md` — Tokenizer — ````yaml POST /paas/v4/tokenizer (13451 bytes) [source](https://docs.z.ai/api-reference/tools/tokenizer)
- `api-reference/tools/web-reader.md` — Web Reader — ````yaml POST /paas/v4/reader (5911 bytes) [source](https://docs.z.ai/api-reference/tools/web-reader)
- `api-reference/tools/web-search.md` — Web Search — ````yaml POST /paas/v4/web_search (6300 bytes) [source](https://docs.z.ai/api-reference/tools/web-search)
- `api-reference/video/generate-video.md` — Generate Video(Async) — ````yaml POST /paas/v4/videos/generations (9243 bytes) [source](https://docs.z.ai/api-reference/video/generate-video)
- `api-reference/video/get-video-status.md` — Retrieve Result — ````yaml GET /paas/v4/async-result/{id} (4452 bytes) [source](https://docs.z.ai/api-reference/video/get-video-status)

## devpack/

- `devpack/credit-campaign-rules.md` — Invite Friends, Get Credits — Please read and fully understand all the rules below before participating in the campaign. Participation const (10273 bytes) [source](https://docs.z.ai/devpack/credit-campaign-rules)
- `devpack/extension/coding-tool-helper.md` — Coding Tool Helper — **One-Click Install Assistant** <br /> (6708 bytes) [source](https://docs.z.ai/devpack/extension/coding-tool-helper)
- `devpack/faq.md` — FAQ — **Q: Which models are supported by GLM Coding Plan? How can I switch between them?** (8845 bytes) [source](https://docs.z.ai/devpack/faq)
- `devpack/latest-model.md` — How to Switch Models — **GLM-5.3 & GLM-5.3-Flash Now Live** <br /> (6257 bytes) [source](https://docs.z.ai/devpack/latest-model)
- `devpack/mcp/reader-mcp-server.md` — Web Reader MCP Server — The Web Reader MCP Server is an exclusive Remote MCP Server developed by Z.AI for GLM Coding Plan users. Built (8098 bytes) [source](https://docs.z.ai/devpack/mcp/reader-mcp-server)
- `devpack/mcp/search-mcp-server.md` — Web Search MCP Server — The Web Search MCP Server is an exclusive Remote MCP Server developed by Z.AI for GLM Coding Plan users. Built (7107 bytes) [source](https://docs.z.ai/devpack/mcp/search-mcp-server)
- `devpack/mcp/vision-mcp-server.md` — Vision MCP Server — The Visual Understanding MCP Server is an exclusive Local MCP Server developed by Z.AI for GLM Coding Plan use (9835 bytes) [source](https://docs.z.ai/devpack/mcp/vision-mcp-server)
- `devpack/mcp/zread-mcp-server.md` — Zread MCP Server — The ZRead MCP Server is an exclusive Remote MCP Server developed by Z.AI for GLM Coding Plan users. Built on t (8104 bytes) [source](https://docs.z.ai/devpack/mcp/zread-mcp-server)
- `devpack/notice/event-glm-5.3-flash.md` — GLM-5.3-Flash Usage Campaign — To thank our users for their continued support, GLM Coding Plan is launching an **Usage Campaign** for GLM-5.3 (1530 bytes) [source](https://docs.z.ai/devpack/notice/event-glm-5.3-flash)
- `devpack/notice/usage-revision.md` — Plan Update Announcement — * Publication date: July 30, 2026 (10368 bytes) [source](https://docs.z.ai/devpack/notice/usage-revision)
- `devpack/overview.md` — Overview — **GLM-5.3-Flash Usage Campaign** is here: During the campaign period, daily from 23:00 to 09:00 the following  (8565 bytes) [source](https://docs.z.ai/devpack/overview)
- `devpack/quick-start.md` — Quick Start — This guide will help you get started with [GLM Coding Plan](https://z.ai/subscribe?utm_source=zai\&utm_medium= (5670 bytes) [source](https://docs.z.ai/devpack/quick-start)
- `devpack/resources/best-practice.md` — Best Practice — As foundation models continue to improve, AI coding tools are evolving from simple code-completion assistants  (19849 bytes) [source](https://docs.z.ai/devpack/resources/best-practice)
- `devpack/resources/memory-mechanism.md` — Memory-mechanism — Memory enables a coding agent to retain context across tasks and sessions, reducing repeated input and improvi (20083 bytes) [source](https://docs.z.ai/devpack/resources/memory-mechanism)
- `devpack/teamplan.md` — Team Plan Benefits — GLM Coding Team Plan is a self-service subscription for enterprises and development teams. Building on the ind (10883 bytes) [source](https://docs.z.ai/devpack/teamplan)
- `devpack/tool/others.md` — Tool Integration — The GLM Coding Plan is limited to use within the following officially supported tools and product environments (5981 bytes) [source](https://docs.z.ai/devpack/tool/others)
- `devpack/transition.md` — Legacy Plan Migration Notice — * Publication date: April 21, 2026 (5999 bytes) [source](https://docs.z.ai/devpack/transition)
- `devpack/usage-policy.md` — Usage Policy — The GLM Coding Plan is a subscription package designed specifically for AI-powered coding. (3785 bytes) [source](https://docs.z.ai/devpack/usage-policy)

## scenario-example/

- `scenario-example/develop-tools/claude.md` — Claude Code — Claude Code is an agentic coding tool that lives in your terminal, understands your codebase, and helps you co (9355 bytes) [source](https://docs.z.ai/scenario-example/develop-tools/claude)
- `scenario-example/develop-tools/cline.md` — Cline — Cline is a powerful VS Code plugin that lets you use AI models directly in your editor for code generation, fi (3173 bytes) [source](https://docs.z.ai/scenario-example/develop-tools/cline)
- `scenario-example/develop-tools/cursor.md` — Cursor — You can easily integrate the **GLM-4.7** model into **Cursor** that supports the **OpenAI API protocol**. (1864 bytes) [source](https://docs.z.ai/scenario-example/develop-tools/cursor)
- `scenario-example/develop-tools/droid.md` — Factory Droid — Factory Droid is an enterprise-grade AI coding agent that lives in your terminal and handles end-to-end develo (4398 bytes) [source](https://docs.z.ai/scenario-example/develop-tools/droid)
- `scenario-example/develop-tools/goose.md` — Goose — Goose is an AI agent tool that supports local or desktop environments and offers a CLI interface. It integrate (3135 bytes) [source](https://docs.z.ai/scenario-example/develop-tools/goose)
- `scenario-example/develop-tools/opencode.md` — Open Code — OpenCode is a powerful AI coding agent that can be configured to use Z.AI's GLM models. (5660 bytes) [source](https://docs.z.ai/scenario-example/develop-tools/opencode)

## release-notes/

- `release-notes/new-released.md` — New Released — <Update label="2026-08-26" description=" GLM-5.3-Flash"> (9513 bytes) [source](https://docs.z.ai/release-notes/new-released)

## help/

- `help/faq.md` — FAQ — The caching mechanism is currently undergoing open beta testing. Therefore, the underlying logic of the cachin (1737 bytes) [source](https://docs.z.ai/help/faq)

## legal-agreement/

- `legal-agreement/privacy-policy.md` — Privacy Policy — **Last Update:** September 29, 2025 (29172 bytes) [source](https://docs.z.ai/legal-agreement/privacy-policy)
- `legal-agreement/subscription-terms.md` — Subscriptions, Fees, and Payment — * Access to certain Z.ai services or features may require payment. Applicable fees are listed on the **Z.ai**, (8875 bytes) [source](https://docs.z.ai/legal-agreement/subscription-terms)
- `legal-agreement/terms-of-use.md` — Terms of Use — **Last Update:** April 14, 2026 (53492 bytes) [source](https://docs.z.ai/legal-agreement/terms-of-use)

## guides/

- `guides/video/cogvideox-3.md` — CogVideoX-3 — CogVideoX-3 features new frame generation capabilities that significantly improve image stability and clarity. (12440 bytes) [source](https://docs.z.ai/guides/video/cogvideox-3)

## openapi.json

- `openapi.json` — vendor machine-readable API spec (14 paths: chat completion, images, video, audio, agents, tools) [source](https://docs.z.ai/openapi.json)

## _raw/ (door captures)

- `_raw/llms_index.txt` — llms.txt index capture (68 links)
- `_raw/llms_full.txt` — llms-full.txt whole-docs capture (647,819 bytes)
- `_raw/sitemap.xml` + `_raw/sitemap_urls.txt` — sitemap ground truth (67 URLs)
- `_raw/fetch_log.txt` — per-page HTTP status + byte log for the 2026-09-04 crawl
- `_raw/crawl_urls.txt` — the exact 75-URL crawl manifest

## Known gaps (tri-state)

- `api-reference/rate-limit` — **Disputed availability**: docs.z.ai 307-redirects to https://z.ai/manage-apikey/rate-limits (HTML console docs, no .md door). Stub + pointer recorded in-mirror; endpoint-level rate numbers UNPROVEN until that page is mined. Concurrency-by-tier table IS captured at `devpack/usage-policy.md`.
- No 404s, no wall hits on any other page.
