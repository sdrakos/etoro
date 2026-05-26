---
name: gemini-imagen
description: >-
  Generate images using Google Gemini Imagen 4 API
---

---
name: gemini-imagen
description: >-
  Generate high-quality images using Google Gemini Imagen 4 API with text-to-image capabilities,
  aspect ratio control, and person generation settings (allow_all, allow_adult, dont_allow)
---

## Purpose
Generate images using Google's **Imagen 4** models via the Gemini API. Supports:
- Text-to-image generation from English prompts
- Multiple image variants (1-4 images)
- Aspect ratio control (1:1, 3:4, 4:3, 9:16, 16:9)
- Image size selection (1K, 2K)
- Person generation control (allow_all, allow_adult, dont_allow)
- Three model tiers: Standard, Ultra, Fast

## Prerequisites
- **Packages:** `pip install google-genai pillow`
- **API Key:** Google AI Studio API key in config.yaml (`google_api_key`)
- **Model Access:** Imagen 4 access enabled in Google AI Studio

## Configuration
The Google API key is stored in `config.yaml`:
```yaml
google_api_key: "YOUR_GOOGLE_AI_STUDIO_KEY"
```

Load it in Python:
```python
from core.config import load_config
cfg = load_config()
api_key = cfg["google_api_key"]
```

## Usage

### Basic Image Generation
```bash
python ".Claude/Skills/gemini-imagen/scripts/generate.py" "Robot holding a red skateboard"
```

### With Options
```bash
# Generate 4 images in 16:9 aspect ratio
python ".Claude/Skills/gemini-imagen/scripts/generate.py" "Sunset over mountains" --count 4 --aspect-ratio 16:9

# Use Ultra model with 2K resolution
python ".Claude/Skills/gemini-imagen/scripts/generate.py" "Futuristic city" --model ultra --size 2K

# Allow all person types (adults + children) where available
python ".Claude/Skills/gemini-imagen/scripts/generate.py" "Family picnic" --person-generation allow_all

# Fast model for quick results
python ".Claude/Skills/gemini-imagen/scripts/generate.py" "Abstract art" --model fast
```

### Advanced Usage
```bash
# Custom output directory
python ".Claude/Skills/gemini-imagen/scripts/generate.py" "Space station" --output ./my_images/

# Specific aspect ratio + person control
python ".Claude/Skills/gemini-imagen/scripts/generate.py" "Portrait of a scientist" --aspect-ratio 3:4 --person-generation allow_adult
```

## Scripts
- `scripts/generate.py` — Main image generation script with CLI interface

## Models
| Model | ID | Use Case |
|-------|-----|----------|
| **Standard** | `imagen-4.0-generate-001` | Balanced quality and speed |
| **Ultra** | `imagen-4.0-ultra-generate-001` | Highest quality, slower |
| **Fast** | `imagen-4.0-fast-generate-001` | Quick generation, good quality |

## Parameters
| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--count` | 1-4 | 4 | Number of images to generate |
| `--aspect-ratio` | 1:1, 3:4, 4:3, 9:16, 16:9 | 1:1 | Image aspect ratio |
| `--size` | 1K, 2K | 1K | Image resolution (Standard/Ultra only) |
| `--model` | standard, ultra, fast | standard | Model tier |
| `--person-generation` | allow_all, allow_adult, dont_allow | allow_adult | Person depiction control |
| `--output` | path | ./generated_images/ | Output directory |

## Person Generation Settings
| Value | Behavior | Regional Restriction |
|-------|----------|---------------------|
| `dont_allow` | No people in images | None |
| `allow_adult` | Adults only (default) | None |
| `allow_all` | Adults + children | **NOT AVAILABLE** in EU, UK, CH, MENA |

## Output
- Images saved as PNG files in the output directory
- Automatic SynthID watermark applied by Google
- Filenames: `{timestamp}_{index}.png`
- Base64-decoded from API response

## Best Practices
1. **Prompts:** Use English only, keep under 480 tokens
2. **Text in Images:** For text overlays, keep prompts short (<25 chars) and iterate
3. **Quality:** Use descriptive prompts with specific details (lighting, camera type, art style)
4. **Iteration:** Refine prompts based on initial results
5. **Regional Compliance:** Use `allow_adult` in EU/UK/CH/MENA regions

## Examples

### Example 1: Product Photography
```bash
python ".Claude/Skills/gemini-imagen/scripts/generate.py" "Professional product photo of a smartwatch on marble surface, studio lighting, high resolution" --model ultra --size 2K --aspect-ratio 1:1
```

### Example 2: Social Media Content
```bash
python ".Claude/Skills/gemini-imagen/scripts/generate.py" "Motivational quote background, abstract gradient, modern design" --aspect-ratio 9:16 --count 3
```

### Example 3: Character Design
```bash
python ".Claude/Skills/gemini-imagen/scripts/generate.py" "Cyberpunk character with neon jacket, Tokyo street background, cinematic lighting" --person-generation allow_adult --model ultra
```

## Limitations
- English prompts only
- Max 480 tokens per prompt
- Regional restrictions on `allow_all` person generation
- 2K size only available for Standard and Ultra models
- All images include SynthID watermark

## Troubleshooting
| Issue | Solution |
|-------|----------|
| API key error | Check `google_api_key` in config.yaml |
| `allow_all` blocked | Use `allow_adult` in EU/UK/CH/MENA |
| Model not found | Verify Imagen 4 access in Google AI Studio |
| Import errors | Run `pip install google-genai pillow` |
