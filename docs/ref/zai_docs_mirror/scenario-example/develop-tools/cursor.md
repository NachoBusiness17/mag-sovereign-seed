> ## Documentation Index
> Fetch the complete documentation index at: https://docs.z.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Cursor

> Methods for using the GLM Coding Plan in Cursor

You can easily integrate the **GLM-4.7** model into **Cursor** that supports the **OpenAI API protocol**.

<Warning>
  Note: Custom configuration is only supported in Cursor Pro and higher versions \
  Using the GLM Coding Plan, you need to configure the dedicated Coding API [https://api.z.ai/api/coding/paas/v4](https://api.z.ai/api/coding/paas/v4) instead of the General API [https://api.z.ai/api/paas/v4](https://api.z.ai/api/paas/v4)
</Warning>

### 1. Install Cursor

Download and install Cursor from the official website.

### 2. Create a New Provider/Model

In Cursor, navigate to the "**Models**" section and click the "**Add Custom Model**".

![Description](https://cdn.bigmodel.cn/markdown/176032216013820251013-100735.jpeg?attname=20251013-100735.jpeg)

* Select the **OpenAI Protocol**.
* Configure the **OpenAI API Key** (obtained from the Z.AI).
* In **Override OpenAI Base URL**, replace the default URL with `https://api.z.ai/api/coding/paas/v4`.
* Enter the model you wish to use, such as `GLM-4.7`, `GLM-4.7` or `GLM-4.5-air`.
* Note: In Cursor, the model name must be entered in uppercase, such as `GLM-4.7`.

![Description](https://cdn.bigmodel.cn/markdown/176032218295020251013-100740.jpeg?attname=20251013-100740.jpeg)

### 3. Save and Switch Models

After configuration, save your settings and select the newly created **GLM-4.7 Provider** on the homepage.

### 4. Get Started

With this setup, you can begin using the **GLM-4.7** model for code generation, debugging, task analysis, and more.

![Description](https://cdn.bigmodel.cn/markdown/176032221518820251013-100745.jpeg?attname=20251013-100745.jpeg)
