# Gemini Imagen 4 API Reference

## Available Models

| Model | ID | Use Case |
|-------|-----|----------|
| **Standard** | `imagen-4.0-generate-001` | Balanced quality and speed |
| **Ultra** | `imagen-4.0-ultra-generate-001` | Highest quality, slower |
| **Fast** | `imagen-4.0-fast-generate-001` | Quick generation, good quality |

**Note:** Imagen 3 has been deprecated.

## API Authentication

```python
from google import genai

client = genai.Client(api_key="YOUR_API_KEY")
```

## Basic Usage

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_API_KEY")

response = client.models.generate_images(
    model='imagen-4.0-generate-001',
    prompt='Robot holding a red skateboard',
    config=types.GenerateImagesConfig(
        number_of_images=4,
        aspect_ratio='1:1',
        image_size='1K',
        person_generation='allow_adult'
    )
)

# Access generated images
for idx, image in enumerate(response.generated_images):
    # image._image_bytes contains the PNG data
    with open(f'image_{idx}.png', 'wb') as f:
        f.write(image._image_bytes)
```

## Configuration Parameters

### GenerateImagesConfig

| Parameter | Type | Values | Default | Description |
|-----------|------|--------|---------|-------------|
| `number_of_images` | int | 1-4 | 4 | Number of images to generate |
| `aspect_ratio` | str | `'1:1'`, `'3:4'`, `'4:3'`, `'9:16'`, `'16:9'` | `'1:1'` | Image aspect ratio |
| `image_size` | str | `'1K'`, `'2K'` | `'1K'` | Resolution (not available for Fast model) |
| `person_generation` | str | `'dont_allow'`, `'allow_adult'`, `'allow_all'` | `'allow_adult'` | Person depiction control |

## Person Generation Settings

### dont_allow
Blocks all person depiction in generated images.

**Use case:** Abstract art, landscapes, products without human models

```python
config=types.GenerateImagesConfig(
    person_generation='dont_allow'
)
```

### allow_adult (Default)
Permits only adult figures in generated images.

**Available:** Globally
**Use case:** Professional content, general purpose

```python
config=types.GenerateImagesConfig(
    person_generation='allow_adult'
)
```

### allow_all
Enables both adult and child representations.

**Regional restriction:** NOT AVAILABLE in EU, UK, CH, MENA
**Use case:** Family content, diverse age representation (where permitted)

```python
config=types.GenerateImagesConfig(
    person_generation='allow_all'
)
```

**Important:** Attempting to use `allow_all` in restricted regions will raise an API error.

## Image Output

Generated images:
- Format: PNG
- Encoding: Base64 in API response
- Watermark: Automatic SynthID watermark applied by Google
- Access: `response.generated_images[idx]._image_bytes`

## Prompt Guidelines

### Requirements
- **Language:** English only
- **Max length:** 480 tokens
- **Format:** Natural language descriptions

### Best Practices

**Good prompts:**
```
"Professional product photo of a smartwatch on marble surface, studio lighting, high resolution"
"Cyberpunk character with neon jacket, Tokyo street background, cinematic lighting"
"Abstract gradient background, pastel colors, modern design"
```

**For text in images:**
- Keep text short (<25 characters)
- Iterate for better placement
- Be specific about font and style

**Quality improvements:**
- Add specific descriptors (camera type, lens, lighting)
- Reference art movements or styles
- Specify materials and textures
- Iterate and refine based on results

## Error Handling

### Common Errors

**API Key Invalid**
```
Error: API key not valid
```
**Solution:** Verify API key in Google AI Studio

**Quota Exceeded**
```
Error: Quota exceeded for quota metric...
```
**Solution:** Check usage limits in Google AI Studio dashboard

**Region Restriction**
```
Error: allow_all not available in your region
```
**Solution:** Use `allow_adult` instead

**Invalid Parameters**
```
Error: Invalid aspect_ratio value
```
**Solution:** Use one of: '1:1', '3:4', '4:3', '9:16', '16:9'

## Model Comparison

### Standard (imagen-4.0-generate-001)
- **Speed:** Moderate
- **Quality:** High
- **Resolution:** 1K, 2K
- **Use case:** General purpose, balanced quality/speed

### Ultra (imagen-4.0-ultra-generate-001)
- **Speed:** Slower
- **Quality:** Highest
- **Resolution:** 1K, 2K
- **Use case:** Premium content, maximum quality

### Fast (imagen-4.0-fast-generate-001)
- **Speed:** Fastest
- **Quality:** Good
- **Resolution:** 1K only
- **Use case:** Quick iterations, prototyping

## Rate Limits

Consult Google AI Studio dashboard for current rate limits:
- Requests per minute
- Requests per day
- Image generation quota

## SynthID Watermark

All generated images include an automatic **SynthID watermark**:
- Invisible to human eye
- Detectable by verification tools
- Cannot be removed or disabled
- Survives most image transformations

## Regional Availability

| Region | allow_adult | allow_all |
|--------|------------|-----------|
| **Global** | ✅ Yes | ✅ Yes |
| **EU** | ✅ Yes | ❌ No |
| **UK** | ✅ Yes | ❌ No |
| **Switzerland** | ✅ Yes | ❌ No |
| **MENA** | ✅ Yes | ❌ No |

## Code Examples

### Example 1: Multiple Aspect Ratios
```python
aspect_ratios = ['1:1', '16:9', '9:16']

for ratio in aspect_ratios:
    response = client.models.generate_images(
        model='imagen-4.0-generate-001',
        prompt='Modern office workspace, natural lighting',
        config=types.GenerateImagesConfig(
            number_of_images=2,
            aspect_ratio=ratio
        )
    )
    print(f"Generated {len(response.generated_images)} images in {ratio}")
```

### Example 2: Batch Generation
```python
prompts = [
    'Sunrise over mountains',
    'City skyline at night',
    'Abstract geometric patterns'
]

for idx, prompt in enumerate(prompts):
    response = client.models.generate_images(
        model='imagen-4.0-fast-generate-001',
        prompt=prompt,
        config=types.GenerateImagesConfig(number_of_images=1)
    )

    with open(f'batch_{idx}.png', 'wb') as f:
        f.write(response.generated_images[0]._image_bytes)
```

### Example 3: Error Handling
```python
try:
    response = client.models.generate_images(
        model='imagen-4.0-generate-001',
        prompt='Professional headshot',
        config=types.GenerateImagesConfig(
            person_generation='allow_adult',
            aspect_ratio='3:4',
            image_size='2K'
        )
    )
except Exception as e:
    if 'quota' in str(e).lower():
        print("⚠️  API quota exceeded")
    elif 'region' in str(e).lower():
        print("⚠️  Feature not available in your region")
    else:
        print(f"❌ Error: {e}")
```

## Links

- **API Documentation:** https://ai.google.dev/gemini-api/docs/imagen
- **Google AI Studio:** https://aistudio.google.com/
- **Python SDK:** `pip install google-genai`
- **Rate Limits:** Check Google AI Studio dashboard