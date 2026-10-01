> ## Documentation Index
> Fetch the complete documentation index at: https://docs.z.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# GLM-ASR-2512

## <Icon icon="rectangle-list" iconType="solid" color="#ffffff" size={36} />   Overview

GLM-ASR-2512 is Z.AI's next-generation speech recognition model, enabling real-time conversion of speech into high-quality text. Whether for daily conversations, meeting minutes, work documents, or scenarios involving specialized terminology, it delivers precise recognition and conversion, significantly boosting input and recording efficiency. The model maintains industry-leading recognition performance across diverse scenarios and accents, achieving a Character Error Rate (CER) of just 0.0717. This delivers a fast and reliable voice input experience.

<CardGroup cols={3}>
  <Card title="Input Modality" icon="arrow-down-right" color="#ffffff">
    Audio / File
  </Card>

  <Card title="Output Modality" icon="arrow-down-left" color="#ffffff">
    Text
  </Card>

  <Card title="Upload Restrictions" icon="arrow-down-arrow-up" color="#ffffff">
    * Audio duration ≤ 30 seconds
    * File size ≤ 25 MB
  </Card>
</CardGroup>

## <Icon icon="list" iconType="solid" color="#ffffff" size={36} />   Usage

<AccordionGroup>
  <Accordion title="Real-time Meeting Minutes" defaultOpen="true">
    Transcribe online meetings instantly, automatically organizing structured summaries to significantly boost efficiency.
  </Accordion>

  <Accordion title="Customer Service Quality Assurance & Ticket Management" defaultOpen="true">
    High-precision transcription of support calls enhances QA efficiency and enables multi-scenario analysis.
  </Accordion>

  <Accordion title="Live Video Captioning" defaultOpen="true">
    Provides real-time synchronized subtitles for news broadcasts, educational courses, or video conferences with low latency and high accuracy.
  </Accordion>

  <Accordion title="Office Document Input" defaultOpen="true">
    Rapidly generate work documents, emails, and proposal drafts via voice input, dramatically accelerating content creation.
  </Accordion>

  <Accordion title="Multilingual Communication & Translation" defaultOpen="true">
    Supports cross-language speech comprehension for cross-border exchanges, online meetings, and educational settings.
  </Accordion>

  <Accordion title="Medical Record Entry" defaultOpen="true">
    Instantly recognizes extensive medical terminology, enabling doctors to dictate patient histories for swift electronic medical record generation.
  </Accordion>
</AccordionGroup>

## <Icon icon="bars-sort" iconType="solid" color="#ffffff" size={36} />   Resources

* [API Documentation](/api-reference/audio/audio-transcriptions): Learn how to call the API.

## <Icon icon="arrow-down-from-line" iconType="solid" color="#ffffff" size={36} />   Introducing GLM-ASR-2512

<Steps>
  <Step title="Product Advantages" titleSize="h3">
    * Precise Recognition: In the latest competitive evaluation, GLM-ASR-2512 achieved a Character Error Rate (CER) of just 0.0717, reaching internationally leading standards and matching the world's top speech recognition models.
    * Efficient Custom Dictionary: The model enables users to swiftly import specialized vocabulary, project codes (e.g., AutoGLM, Zhipu AI Input Method), and uncommon names/locations through simple configuration. Add once in settings to eliminate repetitive editing hassles.
    * Complex Scenario Advantages: Whether handling mixed Chinese-English expressions, command-based text, industry-specific terminology, long sentences, or colloquial speech, GLM-ASR-2512 consistently delivers high-quality transcriptions with overall performance significantly outperforming competitors.
  </Step>

  <Step title="Supported Languages" iconType="regular" stepNumber={2} titleSize="h3">
    GLM-ASR-2512 excels in multilingual and dialect processing, accurately transcribing major global languages and regional speech:

    * Chinese: Supports Mandarin, along with major dialects including Sichuanese, Cantonese, Min Nan, and Wu
    * English: Supports multiple accents such as American and British
    * Other supported languages: Dozens of globally used languages including French, German, Japanese, Korean, Spanish, Arabic, and more
  </Step>
</Steps>

## <Icon icon="rectangle-code" iconType="solid" color="#ffffff" size={36} />    Quick Start

The following is a full sample code to help you onboard `GLM-ASR-2512` with ease.

<Tabs>
  <Tab title="cURL">
    **Basic Call**

    ```bash theme={null}
    curl --request POST \
        --url https://api.z.ai/api/paas/v4/audio/transcriptions \
        --header 'Authorization: Bearer API_Key' \
        --header 'Content-Type: multipart/form-data' \
        --form model=glm-asr-2512 \
        --form stream=false \
        --form file=@example-file
    ```

    **Streaming Call**

    ```bash theme={null}
    curl --request POST \
        --url https://api.z.ai/api/paas/v4/audio/transcriptions \
        --header 'Authorization: Bearer API_Key' \
        --header 'Content-Type: multipart/form-data' \
        --form model=glm-asr-2512 \
        --form stream=true \
        --form file=@example-file
    ```
  </Tab>
</Tabs>
