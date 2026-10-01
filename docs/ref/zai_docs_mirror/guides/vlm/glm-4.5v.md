> ## Documentation Index
> Fetch the complete documentation index at: https://docs.z.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# GLM-4.5V

## Overview

GLM-4.5V is Z.AI's new generation of visual reasoning models based on the MOE architecture. With a total of 106B parameters and 12B activation parameters, it achieves SOTA performance among open-source VLMs of the same level in various benchmark tests, covering common tasks such as image, video, document understanding, and GUI tasks.

<CardGroup cols={2}>
  <Card title="Price" icon="circle-dollar" color="#ffffff">
    * Input: \$0.6 per million tokens
    * Output: \$1.8 per million tokens
  </Card>

  <Card title="Input Modality" icon="arrow-down-right" color="#ffffff">
    Video / Image / Text / File
  </Card>

  <Card title="Output Modality" icon="arrow-down-left" color="#ffffff">
    Text
  </Card>

  <Card title="Maximum Output Tokens" icon="maximize" color="#ffffff">
    16K
  </Card>
</CardGroup>

## Usage

<AccordionGroup>
  <Accordion title="Web Page Coding">
    Analyze webpage screenshots or screen recording videos, understand layout and interaction logic, and generate complete and usable webpage code with one click.
  </Accordion>

  <Accordion title="Grounding">
    Precisely identify and locate target objects, suitable for practical scenarios such as security checks, quality inspections, content reviews, and remote sensing monitoring.
  </Accordion>

  <Accordion title="GUI Agent">
    Recognize and process screen images, support execution of commands like clicking and sliding, providing reliable support for intelligent agents to complete operational tasks.
  </Accordion>

  <Accordion title="Complex Long Document Interpretation">
    Deeply analyze complex documents spanning dozens of pages, support summarization, translation, chart extraction, and can propose insights based on content.
  </Accordion>

  <Accordion title="Image Recognition and Reasoning">
    Strong reasoning ability and rich world knowledge, capable of deducing background information of images without using search.
  </Accordion>

  <Accordion title="Video Understanding">
    Able to parse long video content and accurately infer the time, characters, events, and logical relationships within the video.
  </Accordion>

  <Accordion title="Subject Problem Solving">
    Can solve complex text-image combined problems, suitable for K12 educational scenarios for problem-solving and explanation.
  </Accordion>
</AccordionGroup>

## Resources

* [API Documentation](/api-reference/llm/chat-completion): Learn how to call the API.

## Introducing GLM-4.5V

<Steps>
  <Step title="Open-Source Multimodal SOTA" titleSize="h3">
    GLM-4.5V, based on Z.AI's flagship GLM-4.5-Air, continues the iterative upgrade of the GLM-4.1V-Thinking technology route, achieving comprehensive performance at the same level as open-source SOTA models in 42 public visual multimodal benchmarks, covering common tasks such as image, video, document understanding, and GUI tasks.

    ![Description](https://cdn.bigmodel.cn/markdown/1754969019359glm-4.5v-16.jpeg?attname=glm-4.5v-16.jpeg)
  </Step>

  <Step title="Support Thinking and Non-Thinking" stepNumber={2} titleSize="h3">
    GLM-4.5V introduces a new "Thinking Mode" switch, allowing users to freely switch between quick response and deep reasoning, flexibly balancing processing speed and output quality according to task requirements.
  </Step>
</Steps>

## Examples

<Tabs>
  <Tab title="Web Page Coding">
    <CardGroup cols={2}>
      <Card title="Prompt" icon="arrow-down-right">
        ![Description](https://cdn.bigmodel.cn/markdown/1754969059126glm-4.5v-17.png?attname=glm-4.5v-17.png)

        Please generate a high - quality UI interface using CSS and HTML based on the webpage I provided.
      </Card>

      <Card title="Display" icon="arrow-down-left">
        Screenshot of the rendered web page:

        ![Description](https://cdn.bigmodel.cn/markdown/1754969077749glm-4.5v-18.png?attname=glm-4.5v-18.png)
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="GUI Agent">
    <CardGroup cols={2}>
      <Card title="Prompt" icon="arrow-down-right">
        ![Description](https://cdn.bigmodel.cn/markdown/1754968632215glm-4.5v-6.png?attname=glm-4.5v-6.png)

        Modify the data in the first row on slide 4 to "89", "21", "900" and "None"
      </Card>

      <Card title="Display" icon="arrow-down-left">
        Modification result:

        ![Description](https://cdn.bigmodel.cn/markdown/1754968746754glm-4.5v-7.png?attname=glm-4.5v-7.png)
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="Chart Conversion">
    <CardGroup cols={2}>
      <Card title="Prompt" icon="arrow-down-right">
        ![Description](https://cdn.bigmodel.cn/markdown/1754968758489glm-4.5v-8.png?attname=glm-4.5v-8.png)

        Convert the table in the image to Markdown format
      </Card>

      <Card title="Display" icon="arrow-down-left">
        Rendered result：

        ![Description](https://cdn.bigmodel.cn/markdown/1754968768530glm-4.5v-9.png?attname=glm-4.5v-9.png)
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="Grounding">
    <CardGroup cols={2}>
      <Card title="Prompt" icon="arrow-down-right">
        ![Description](https://cdn.bigmodel.cn/markdown/1754968795362glm-4.5v-12.png?attname=glm-4.5v-12.png)

        Tell me the position of the couple in the picture. The short-haired guy is wearing a pink top and blue shorts, and the girl is in a cyan dress. Answer in \[x1,y1,x2,y2] format.
      </Card>

      <Card title="Display" icon="arrow-down-left">
        ```
        The position of the couple in the
        picture, where the short-haired 
        guy is wearing a pink top and blue
        shorts, and the girl is in a cyan 
        dress, is [835,626,931,883].
        ```

        Rendered result：

        ![Description](https://cdn.bigmodel.cn/markdown/1754968823292glm-4.5v-13.png?attname=glm-4.5v-13.png)
      </Card>
    </CardGroup>
  </Tab>
</Tabs>

## Quick Start

<Tabs>
  <Tab title="cURL">
    **Basic Call**

    ```bash theme={null}
    curl --location 'https://api.z.ai/api/paas/v4/chat/completions' \
    --header 'Authorization: Bearer YOUR_API_KEY' \
    --header 'Accept-Language: en-US,en' \
    --header 'Content-Type: application/json' \
    --data '{
    "model": "glm-4.5v",
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://cloudcovert-1305175928.cos.ap-guangzhou.myqcloud.com/%E5%9B%BE%E7%89%87grounding.PNG"
                    }
                },
                {
                    "type": "text",
                    "text": "Where is the second bottle of beer from the right on the table?  Provide coordinates in [[xmin,ymin,xmax,ymax]] format"
                }
            ]
        }
    ],
    "thinking": {
        "type":"enabled"
    }
    }'
    ```

    **Streaming Call**

    ```bash theme={null}
    curl --location 'https://api.z.ai/api/paas/v4/chat/completions' \
    --header 'Authorization: Bearer YOUR_API_KEY' \
    --header 'Accept-Language: en-US,en' \
    --header 'Content-Type: application/json' \
    --data '{
    "model": "glm-4.5v",
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://cloudcovert-1305175928.cos.ap-guangzhou.myqcloud.com/%E5%9B%BE%E7%89%87grounding.PNG"
                    }
                },
                {
                    "type": "text",
                    "text": "Where is the second bottle of beer from the right on the table?  Provide coordinates in [[xmin,ymin,xmax,ymax]] format"
                }
            ]
        }
    ],
    "thinking": {
        "type":"enabled"
    },
    "stream": true
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

    client = ZaiClient(api_key="")  # Enter your own APIKey
    response = client.chat.completions.create(
        model="glm-4.5v",  # Enter the name of the model you want to call
        messages=[
            {
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://cloudcovert-1305175928.cos.ap-guangzhou.myqcloud.com/%E5%9B%BE%E7%89%87grounding.PNG"
                        }
                    },
                    {
                        "type": "text",
                        "text": "Where is the second bottle of beer from the right on the table?  Provide coordinates in [[xmin,ymin,xmax,ymax]] format"
                    }
                ],
                "role": "user"
            }
        ],
        thinking={
            "type":"enabled"
        }
    )
    print(response.choices[0].message)
    ```

    **Streaming Call**

    ```python theme={null}
    from zai import ZaiClient

    client = ZaiClient(api_key="")  # Enter your own APIKey
    response = client.chat.completions.create(
        model="glm-4.5v",  # Enter the name of the model you want to call
        messages=[
            {
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://cloudcovert-1305175928.cos.ap-guangzhou.myqcloud.com/%E5%9B%BE%E7%89%87grounding.PNG"
                        }
                    },
                    {
                        "type": "text",
                        "text": "Where is the second bottle of beer from the right on the table?  Provide coordinates in [[xmin,ymin,xmax,ymax]] format"
                    }
                ],
                "role": "user"
            }
        ],
        thinking={
            "type":"enabled"
        },
        stream=True
    )

    for chunk in response:
        if chunk.choices[0].delta.reasoning_content:
            print(chunk.choices[0].delta.reasoning_content, end='', flush=True)

        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end='', flush=True)
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
    import ai.z.openapi.service.model.*;
    import ai.z.openapi.core.Constants;
    import java.util.Arrays;

    public class GLM45VExample {
        public static void main(String[] args) {
            String apiKey = ""; // Enter your own APIKey
            ZaiClient client = ZaiClient.builder().ofZAI()
                .apiKey(apiKey)
                .build();

            ChatCompletionCreateParams request = ChatCompletionCreateParams.builder()
                .model("glm-4.5v")
                .messages(Arrays.asList(
                    ChatMessage.builder()
                        .role(ChatMessageRole.USER.value())
                        .content(Arrays.asList(
                            MessageContent.builder()
                                .type("text")
                                .text("Where is the second bottle of beer from the right on the table?  Provide coordinates in [[xmin,ymin,xmax,ymax]] format")
                                .build(),
                            MessageContent.builder()
                                .type("image_url")
                                .imageUrl(ImageUrl.builder()
                                    .url("https://cloudcovert-1305175928.cos.ap-guangzhou.myqcloud.com/%E5%9B%BE%E7%89%87grounding.PNG")
                                    .build())
                                .build()))
                        .build()))
                .thinking(ChatThinking.builder()
                    .type("enabled")
                    .build())
                .build();

            ChatCompletionResponse response = client.chat().createChatCompletion(request);

            if (response.isSuccess()) {
                Object reply = response.getData().getChoices().get(0).getMessage();
                System.out.println(reply);
            } else {
                System.err.println("Error: " + response.getMsg());
            }
        }
    }
    ```

    **Streaming Call**

    ```java theme={null}
    import ai.z.openapi.ZaiClient;
    import ai.z.openapi.service.model.*;
    import ai.z.openapi.core.Constants;
    import java.util.Arrays;

    public class GLM45VStreamExample {
        public static void main(String[] args) {
            String apiKey = ""; // Enter your own APIKey
            ZaiClient client = ZaiClient.builder().ofZAI()
                .apiKey(apiKey)
                .build();

            ChatCompletionCreateParams request = ChatCompletionCreateParams.builder()
                .model("glm-4.5v")
                .messages(Arrays.asList(
                    ChatMessage.builder()
                        .role(ChatMessageRole.USER.value())
                        .content(Arrays.asList(
                            MessageContent.builder()
                                .type("text")
                                .text("Where is the second bottle of beer from the right on the table?  Provide coordinates in [[xmin,ymin,xmax,ymax]] format")
                                .build(),
                            MessageContent.builder()
                                .type("image_url")
                                .imageUrl(ImageUrl.builder()
                                    .url("https://cloudcovert-1305175928.cos.ap-guangzhou.myqcloud.com/%E5%9B%BE%E7%89%87grounding.PNG")
                                    .build())
                                .build()))
                        .build()))
                .thinking(ChatThinking.builder()
                    .type("enabled")
                    .build())
                .stream(true)
                .build();

            ChatCompletionResponse response = client.chat().createChatCompletion(request);

            if (response.isSuccess()) {
                response.getFlowable().subscribe(
                    // Process streaming message data
                    data -> {
                        if (data.getChoices() != null && !data.getChoices().isEmpty()) {
                            Delta delta = data.getChoices().get(0).getDelta();
                            System.out.print(delta + "\n");
                        }},
                    // Process streaming response error
                    error -> System.err.println("\nStream error: " + error.getMessage()),
                    // Process streaming response completion event
                    () -> System.out.println("\nStreaming response completed")
                );
            } else {
                System.err.println("Error: " + response.getMsg());
            }
        }
    }
    ```
  </Tab>
</Tabs>
