> ## Documentation Index
> Fetch the complete documentation index at: https://docs.z.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# CogView-4

## Overview

CogView-4 is Z.AI’s first open-source text-to-image model. It has comprehensive improvements in semantic understanding, image generation quality, and the ability to generate both English and Chinese text. It supports bilingual input of any length in Chinese and English and can generate images of any resolution within a specified range.

<CardGroup cols={3}>
  <Card title="Price" icon="circle-dollar" color="#ffffff">
    \$0.01 / image
  </Card>

  <Card title="Input Modality" icon="arrow-down-right" color="#ffffff">
    Text
  </Card>

  <Card title="Output Modality" icon="arrow-down-left" color="#ffffff">
    Image
  </Card>
</CardGroup>

## Usage

<AccordionGroup>
  <Accordion title="Food & Beverage Promotion">
    Generates visually appealing, detailed, and realistic food images based on dish names, ingredient characteristics, and style requirements, incorporating creative text elements. Suitable for menu design, food delivery platform displays, and offline posters.
  </Accordion>

  <Accordion title="E-commerce Product Images">
    Quickly generates high-resolution product display images based on product features and selling points, adding bilingual promotional text as needed. Fits the image requirements for different product pages and campaign visuals on e-commerce platforms.
  </Accordion>

  <Accordion title="Game Asset Creation">
    Produces high-resolution, detailed character illustrations and concept art based on game worldviews and character settings, meeting the needs of multi-resolution production.
  </Accordion>

  <Accordion title="Educational Material Illustrations">
    Analyzes teaching text content and automatically generates matching illustrations and scene images, adapted to the layout and resolution requirements of various educational materials, enhancing the visualization of knowledge.
  </Accordion>

  <Accordion title="Cultural & Tourism Promotion">
    Generates promotional images in different sizes based on cultural and tourism themes, skillfully combining text with region-specific visual elements to increase the appeal of cultural and tourism marketing.
  </Accordion>
</AccordionGroup>

## Resources

* [API Documentation](/api-reference/image/generate-image): Learn how to call the API.

## Introducting CogView-4

<Steps>
  <Step title="Achieved SOTA Performance at Release" titleSize="h3">
    DPG-Bench (Dense Prompt Graph Benchmark) is a benchmark for evaluating text-to-image generation models, focusing on the model’s performance in complex semantic alignment and instruction following.

    At the time of release, CogView-4 ranked first overall in the DPG-Bench benchmark test, achieving SOTA performance among open-source text-to-image models.

    ![Description](https://cdn.bigmodel.cn/markdown/1749449849627DPG-Bench.png?attname=DPG-Bench.png)
  </Step>

  <Step title="Better Chinese Understanding and Generation" iconType="regular" stepNumber={2} titleSize="h3">
    Technically, CogView-4 replaced the English-only T5 encoder with the bilingual GLM-4 encoder and trained the model using bilingual image-text data, enabling the model to handle bilingual prompts.

    CogView-4 supports Chinese and English prompts and is especially good at understanding and following Chinese prompts, greatly lowering the prompt threshold for users. It is the first open-source text-to-image model capable of generating Chinese characters in the images, making it particularly suitable for creative needs in advertising, short videos, and other fields.
  </Step>

  <Step title="Any Resolution and Any-Length Prompts" iconType="regular" stepNumber={3} titleSize="h3">
    CogView-4 implements a mixed training paradigm of text descriptions (captions) of any length and images of any resolution. The model supports input prompts of any length and can generate images at any resolution within the supported range. This not only provides users with more creative freedom but also improves training efficiency.
  </Step>
</Steps>

## Examples

<Tabs>
  <Tab title="Food & Beverage Promotion">
    <CardGroup cols={2}>
      <Card title="Prompt" icon="arrow-down-right">
        Close-up, commercial food photography, intense indoor lighting, extreme detail. A Christmas dinner table, a corner of the table where a long-haired orange tabby cat leans its head close to a plate, greedily sniffing the festive feast with an expression of pure delight. The table features roast chicken, plants, salad, champagne, and gold-rimmed porcelain tea sets. Afternoon sunlight bathes the cat's profile in golden light, casting a soft glow over both the food and its fur. A Christmas tree adorns the background. The image emphasizes the texture of the food and the cat's coat, featuring strong lighting and a warm, festive Christmas atmosphere.
      </Card>

      <Card title="Display" icon="arrow-down-left">
        <img src="https://mintcdn.com/zhipu-32152247/aOvZujLeW4WS84Ft/resource/cogview-1.png?fit=max&auto=format&n=aOvZujLeW4WS84Ft&q=85&s=6e96f8a615cfdd325a7abb4369d6396c" alt="Description" width="1728" height="2304" data-path="resource/cogview-1.png" />
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="E-commerce Product Images">
    <CardGroup cols={2}>
      <Card title="Prompt" icon="arrow-down-right">
        Two opaque, non-reflective white milk tea cups are adorned with intricate golden patterns of varying sizes. The designs feature Christmas motifs, including reindeer and pine trees, set against a warm red background and twinkling holiday lights. Displayed within a miniature snow scene, they are illuminated by natural light.
      </Card>

      <Card title="Display" icon="arrow-down-left">
        <img src="https://mintcdn.com/zhipu-32152247/aOvZujLeW4WS84Ft/resource/cogview-2.png?fit=max&auto=format&n=aOvZujLeW4WS84Ft&q=85&s=e7b595d49b108120be3ceb86d55f17ab" alt="Description" width="880" height="1168" data-path="resource/cogview-2.png" />
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="Game Asset Creation">
    <CardGroup cols={2}>
      <Card title="Prompt" icon="arrow-down-right">
        Cyberpunk samurai with a glowing katana and a robotic arm, standing in a neon-lit alley in Tokyo, rain reflecting on the wet pavement, Blade Runner aesthetic, cinematic, highly detailed, volumetric lighting -- ar 2:3.
      </Card>

      <Card title="Display" icon="arrow-down-left">
        <img src="https://mintcdn.com/zhipu-32152247/aOvZujLeW4WS84Ft/resource/cogview-3.png?fit=max&auto=format&n=aOvZujLeW4WS84Ft&q=85&s=a0afa1d589085bd9ce87d148be38a55f" alt="Description" width="2048" height="2048" data-path="resource/cogview-3.png" />
      </Card>
    </CardGroup>
  </Tab>

  <Tab title="Cultural & Tourism Promotion">
    <CardGroup cols={2}>
      <Card title="Prompt" icon="arrow-down-right">
        The dazzling nightscape of Victoria Harbour in Hong Kong employs double exposure techniques to seamlessly blend the bustling city skyline with spectacular fireworks. Multiple fireworks burst across the night sky, forming a massive heart shape perfectly superimposed at the center of the frame. The fireworks display a kaleidoscope of colors—gold, red, blue, and purple intertwine, illuminating the entire night sky. City lights twinkle in the background, with skyscraper silhouettes clearly visible. Neon lights along the streets accentuate the city's vibrant energy. The entire scene exudes a dreamlike and romantic atmosphere, immersing the viewer in the dazzling nightscape of Hong Kong.
      </Card>

      <Card title="Display" icon="arrow-down-left">
        <img src="https://mintcdn.com/zhipu-32152247/aOvZujLeW4WS84Ft/resource/cogview-4.png?fit=max&auto=format&n=aOvZujLeW4WS84Ft&q=85&s=d2148db796d13648704782164136b699" alt="Description" width="864" height="1152" data-path="resource/cogview-4.png" />
      </Card>
    </CardGroup>
  </Tab>
</Tabs>

## Quick Start

<Tabs>
  <Tab title="cURL">
    ```
    curl --request POST \
    --url https://api.z.ai/api/paas/v4/images/generations \
    --header 'Authorization: Bearer <token>' \
    --header 'Content-Type: application/json' \
    --data '{
        "model": "cogView-4-250304",
        "prompt": "A cute little kitten sitting on a sunny windowsill, with the background of blue sky and white clouds.",
        "size": "1024x1024"
    }'
    ```
  </Tab>

  <Tab title="Python">
    **Install SDK**

    ```bash theme={null}
    # Install latest version
    pip install zai-sdk

    # Or specify version
    pip install zai-sdk==0.2.3
    ```

    **Verify Installation**

    ```python theme={null}
    import zai
    print(zai.__version__)
    ```

    **Call Example**

    ```python theme={null}
    from zai import ZaiClient
    client = ZaiClient(api_key="your-api-key")
    response = client.images.generations(
    model="cogView-4-250304",
    prompt="A cute little kitten sitting on a sunny windowsill, with the background of blue sky and white clouds.",
    )
    print(response.data[0].url)
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

    **Call Example**

    ```java theme={null}
    import ai.z.openapi.ZaiClient;
    import ai.z.openapi.core.Constants;
    import ai.z.openapi.service.image.CreateImageRequest;
    import ai.z.openapi.service.image.ImageResponse;

    public class CogView4Example {
    public static void main(String[] args) {
    ZaiClient client = ZaiClient.builder().ofZAI().apiKey("YOUR_API_KEY").build();
    // Create image generation request
    CreateImageRequest request = CreateImageRequest.builder()
    .model(Constants.ModelCogView4250304)
    .prompt("A cute little kitten sitting on a sunny windowsill, with the background of blue sky and white clouds.")
    .size("1024x1024")
    .build();
    ImageResponse response = client.images().createImage(request);
    System.out.println(response.getData());
    }
    }
    ```
  </Tab>
</Tabs>

<Tip>
  Please note that the output of the CogView-4 model is an image URL. You will need to download the image using this URL.
</Tip>
