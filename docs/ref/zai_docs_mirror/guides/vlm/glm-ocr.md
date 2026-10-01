> ## Documentation Index
> Fetch the complete documentation index at: https://docs.z.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# GLM-OCR

## Overview

GLM-OCR is a lightweight professional OCR model with parameters as small as 0.9B, yet it achieves state-of-the-art performance across multiple capabilities. It sets a new benchmark for document parsing with its “small size and high accuracy.” Key features include:

* **Performance SOTA**: Scored 94.62 points to top OmniDocBench V1.5 and achieved current best performance across **multiple mainstream document understanding benchmarks** including tables and formulas at launch.
* **Optimized for Real-World Scenarios**: Delivers stable, leading accuracy in complex environments like code documentation, intricate tables, and stamp recognition. Maintains exceptional recognition precision even with complex layouts, diverse fonts, or mixed text-image content.
* **Efficient and Cost-Effective**: With just 0.9B parameters, supports VLLM and SGLang deployment, significantly reducing inference latency and computational overhead.

<CardGroup cols={3}>
  <Card title="Input Modality" icon="arrow-down-right" color="#ffffff">
    - PDF, images (JPG, PNG)
    - Single image ≤ 10MB, PDF ≤ 50MB
    - Maximum support: 100 pages
  </Card>

  <Card title="Output Modality" icon="arrow-down-left" color="#ffffff">
    Text / Image Links / MD Documents
  </Card>

  <Card title="Supported Language" icon="language" color="#ffffff">
    Support Chinese, English, French, Spanish, Russian, German, Japanese, Korean, etc.
  </Card>
</CardGroup>

<Tip>
  For detailed pricing information on GLM-OCR, please visit the [Pricing Page](/guides/overview/pricing).
</Tip>

## Usage

<AccordionGroup>
  <Accordion title="Text Recognition">
    Recognize text content from photos, screenshots, documents, and scans, supporting printed text, handwriting, and mathematical formulas. Applicable to diverse scenarios including education, research, and office work.
  </Accordion>

  <Accordion title="Table Recognition">
    Identify table structures and content, converting them into HTML-formatted sequences. Suitable for scenarios involving table data entry, conversion, and editing.
  </Accordion>

  <Accordion title="Information Structuring">
    Extract key information from various cards, certificates, receipts, and forms, outputting structured JSON data. Supports applications in banking, insurance, government services, legal, logistics, and other industries.
  </Accordion>

  <Accordion title="Retrieval-Augmented Generation (RAG)">
    Support high-volume document recognition and parsing with high accuracy and standardized output formats, providing a robust foundation for RAG.
  </Accordion>
</AccordionGroup>

## Resources

* [API Documentation](/api-reference/tools/layout-parsing): Learn how to call the API.

## Introducing GLM-OCR

<Steps>
  <Step title="State-of-the-Art Performance, Precision in Action" stepNumber={1} titleSize="h3">
    Thanks to its proprietary CogViT visual encoder and deep scene optimization, GLM-OCR achieves “compact size, high accuracy.”

    With only 0.9B parameters, GLM-OCR achieved SOTA on the authoritative document parsing benchmark OmniDocBench V1.5 with a score of 94.6. It outperforms multiple specialized OCR models across four key domains—text, formula, table recognition, and information extraction—with performance approaching that of Gemini-3-Pro.

    ![Description](https://cdn.bigmodel.cn/markdown/1770048309140img_v3_02uh_d2a8a208-0969-4c06-9a14-fa1d6aa705dg.png?attname=img_v3_02uh_d2a8a208-0969-4c06-9a14-fa1d6aa705dg.png)

    Beyond public benchmarks, we conducted internal evaluations across six core real-world scenarios. Results show GLM-OCR delivers significant advantages across dimensions including code documentation, real-world tables, handwriting, multilingual text, seal recognition, and invoice extraction.

    ![Description](https://cdn.bigmodel.cn/markdown/1770048316118img_v3_02uh_c048a7e7-327c-4591-a620-b04113f6acfg.png?attname=img_v3_02uh_c048a7e7-327c-4591-a620-b04113f6acfg.png)
  </Step>

  <Step title="Faster, More Cost-Effective" stepNumber={2} titleSize="h3">
    For speed, we compared different OCR methods under identical hardware and testing conditions (single replica, single concurrency), evaluating their performance in parsing and exporting Markdown files from both image and PDF inputs. Results show GLM-OCR achieves a throughput of 1.86 pages/second for PDF documents and 0.67 images/second for images, significantly outperforming comparable models.

    ![Description](https://cdn.bigmodel.cn/markdown/1770038419131img_v3_02uh_8dd8ba6c-3ba0-4a13-9894-53700c931ffg.png?attname=img_v3_02uh_8dd8ba6c-3ba0-4a13-9894-53700c931ffg.png)

    Pricing is uniform for both API input and output, costing just \$0.03 per million tokens.
  </Step>
</Steps>

## Examples

<Tabs>
  <Tab title="Code Block Recognition">
    <CardGroup cols={2}>
      <Card title="Input" icon="arrow-down-right">
        ![Description](https://cdn.bigmodel.cn/markdown/1770035979049image.png?attname=image.png)
      </Card>

      <Card title="Output" icon="arrow-down-left">
        ![Description](https://cdn.bigmodel.cn/markdown/1770036049307image.png?attname=image.png)
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="Complex Chart Content Recognition">
    <CardGroup cols={2}>
      <Card title="Input" icon="arrow-down-right">
        ![Description](https://cdn.bigmodel.cn/markdown/1770036076806image.png?attname=image.png)
      </Card>

      <Card title="Output" icon="arrow-down-left">
        ![Description](https://cdn.bigmodel.cn/markdown/1770036127560image.png?attname=image.png)
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="Bill Recognition">
    <CardGroup cols={2}>
      <Card title="Input" icon="arrow-down-right">
        ![Description](https://cdn.bigmodel.cn/markdown/1770036142376image.png?attname=image.png)
      </Card>

      <Card title="Output" icon="arrow-down-left">
        ![Description](https://cdn.bigmodel.cn/markdown/1770036153340image.png?attname=image.png)
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="Handwriting Recognition">
    <CardGroup cols={2}>
      <Card title="Input" icon="arrow-down-right">
        ![Description](https://cdn.bigmodel.cn/markdown/1770036167626image.png?attname=image.png)
      </Card>

      <Card title="Output" icon="arrow-down-left">
        ![Description](https://cdn.bigmodel.cn/markdown/1770036178291image.png?attname=image.png)
      </Card>
    </CardGroup>
  </Tab>
</Tabs>

## Quick Start

<Tabs>
  <Tab title="cURL">
    ```bash theme={null}
    curl --location --request POST 'https://api.z.ai/api/paas/v4/layout_parsing' \
    --header 'Authorization: Bearer your-api-key' \
    --header 'Content-Type: application/json' \
    --data-raw '{
      "model": "glm-ocr",
      "file": "https://cdn.bigmodel.cn/static/logo/introduction.png"
    }'
    ```
  </Tab>

  <Tab title="Python">
    **Install SDK**

    ```bash theme={null}
    # Install the latest version
    pip install zai-sdk
    # Or specify a version
    pip install zai-sdk==0.2.3
    ```

    **Verify installation**

    ```python theme={null}
    import zai
    print(zai.__version__)
    ```

    **Basic Call**

    ```python theme={null}
    from zai import ZaiClient

    # Initialize client
    client = ZaiClient(api_key="your-api-key")

    image_url = "https://cdn.bigmodel.cn/static/logo/introduction.png"

    # Call layout parsing API
    response = client.layout_parsing.create(
        model="glm-ocr",
        file=image_url
    )

    # Output result
    print(response)
    ```
  </Tab>

  <Tab title="Java">
    **Install SDK**

    **Maven**

    ```xml theme={null}
    <dependency>
      <groupId>ai.z.openapi</groupId>
      <artifactId>zai-sdk</artifactId>
      <version>0.3.5</version>
    </dependency>
    ```

    **Gradle (Groovy)**

    ```groovy theme={null}
    implementation 'ai.z.openapi:zai-sdk:0.3.5'
    ```

    **Basic Call**

    ```java theme={null}
    import ai.z.openapi.ZaiClient;
    import ai.z.openapi.service.layoutparsing.LayoutParsingCreateParams;
    import ai.z.openapi.service.layoutparsing.LayoutParsingResponse;
    import ai.z.openapi.service.layoutparsing.LayoutParsingResult;

    public class LayoutParsing {
        public static void main(String[] args) {
            // Initialize client
            ZaiClient client = ZaiClient.builder()
                .ofZAI()
                .apiKey("your-api-key")
                .build();

            String model = "glm-ocr";
            String file = "https://cdn.bigmodel.cn/static/logo/introduction.png";

            // Create layout parsing request
            LayoutParsingCreateParams params = LayoutParsingCreateParams.builder()
                .model(model)
                .file(file)
                .build();

            // Send request
            LayoutParsingResponse response = client.layoutParsing().layoutParsing(params);

            // Handle response
            if (response.isSuccess()) {
                System.out.println("Parsing result: " + response.getData());
            } else {
                System.err.println("Error: " + response.getMsg());
            }
        }
    }
    ```
  </Tab>
</Tabs>
