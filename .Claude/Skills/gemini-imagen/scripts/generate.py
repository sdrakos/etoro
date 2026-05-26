#!/usr/bin/env python3
"""
Gemini Imagen 4 Image Generation Script
Generate high-quality images using Google's Imagen 4 API
"""

import os
import sys
import io
import argparse
import base64
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add proactive directory to path for config import
skill_dir = Path(__file__).resolve().parent.parent
proactive_dir = skill_dir.parent.parent.parent / "proactive"
sys.path.insert(0, str(proactive_dir))

from core.config import load_config

try:
    from google import genai
    from google.genai import types
    from PIL import Image
    import io
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Install: pip install google-genai pillow")
    sys.exit(1)


# Model mapping
MODELS = {
    'standard': 'imagen-4.0-generate-001',
    'ultra': 'imagen-4.0-ultra-generate-001',
    'fast': 'imagen-4.0-fast-generate-001'
}

# Valid aspect ratios
ASPECT_RATIOS = ['1:1', '3:4', '4:3', '9:16', '16:9']

# Person generation options
PERSON_GENERATION = ['dont_allow', 'allow_adult', 'allow_all']


def generate_images(
    prompt: str,
    model: str = 'standard',
    count: int = 4,
    aspect_ratio: str = '1:1',
    size: str = '1K',
    person_generation: str = 'allow_adult',
    output_dir: str = './generated_images/'
) -> list[str]:
    """
    Generate images using Gemini Imagen 4 API

    Args:
        prompt: Text description for image generation (English only)
        model: Model tier (standard/ultra/fast)
        count: Number of images (1-4)
        aspect_ratio: Image aspect ratio (1:1, 3:4, 4:3, 9:16, 16:9)
        size: Image size (1K, 2K) - only for standard/ultra
        person_generation: Person depiction control (dont_allow, allow_adult, allow_all)
        output_dir: Directory to save generated images

    Returns:
        List of saved image paths
    """
    # Load config
    cfg = load_config()
    api_key = cfg.get('google_api_key')

    # Fallback: try loading directly from YAML if config loader returns empty
    if not api_key:
        try:
            import yaml
            config_path = proactive_dir / "config.yaml"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    yaml_cfg = yaml.safe_load(f) or {}
                    api_key = yaml_cfg.get('google_api_key') or yaml_cfg.get('gemini_api_key')
        except Exception:
            pass

    if not api_key:
        raise ValueError("❌ google_api_key not found in config.yaml")

    # Initialize client
    client = genai.Client(api_key=api_key)

    # Get model ID
    model_id = MODELS.get(model, MODELS['standard'])

    # Validate inputs
    if count < 1 or count > 4:
        raise ValueError("count must be between 1 and 4")

    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError(f"aspect_ratio must be one of {ASPECT_RATIOS}")

    if person_generation not in PERSON_GENERATION:
        raise ValueError(f"person_generation must be one of {PERSON_GENERATION}")

    if size not in ['1K', '2K']:
        raise ValueError("size must be 1K or 2K")

    # Fast model doesn't support 2K
    if model == 'fast' and size == '2K':
        print("⚠️  Warning: Fast model doesn't support 2K, using 1K instead")
        size = '1K'

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\n🎨 Generating {count} image(s) with Imagen 4 ({model})...")
    print(f"📝 Prompt: {prompt}")
    print(f"⚙️  Settings: {aspect_ratio} | {size} | person_generation={person_generation}")

    # Build config
    config_params = {
        'number_of_images': count,
        'aspect_ratio': aspect_ratio,
        'person_generation': person_generation
    }

    # Add imageSize only for standard/ultra (not available for fast)
    if model != 'fast':
        config_params['image_size'] = size

    try:
        # Generate images
        response = client.models.generate_images(
            model=model_id,
            prompt=prompt,
            config=types.GenerateImagesConfig(**config_params)
        )

        # Save images
        saved_paths = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for idx, image in enumerate(response.generated_images):
            # Save image
            filename = f"{timestamp}_{idx+1}.png"
            filepath = output_path / filename

            # Write image data using the .image attribute
            # The .image attribute is likely a types.Image object with save() method
            try:
                image_obj = image.image
                # The types.Image object has a save method that takes only filepath
                image_obj.save(filepath)
                saved_paths.append(str(filepath))
                print(f"✅ Saved: {filepath}")
            except Exception as e:
                # Try alternative: convert to PIL Image if it's bytes
                try:
                    if isinstance(image_obj, bytes):
                        pil_image = Image.open(io.BytesIO(image_obj))
                        pil_image.save(filepath, 'PNG')
                        saved_paths.append(str(filepath))
                        print(f"✅ Saved: {filepath}")
                    else:
                        raise ValueError(f"Could not save image: {e}. Image type: {type(image_obj)}")
                except Exception as e2:
                    raise ValueError(f"Could not save image: {e}, {e2}")

        print(f"\n🎉 Successfully generated {len(saved_paths)} image(s)!")
        return saved_paths

    except Exception as e:
        print(f"\n❌ Error generating images: {e}")

        # Provide helpful error messages
        if "API key" in str(e):
            print("💡 Check your google_api_key in config.yaml")
        elif "allow_all" in str(e).lower():
            print("💡 'allow_all' is not available in EU/UK/CH/MENA regions")
            print("   Use 'allow_adult' instead")
        elif "quota" in str(e).lower():
            print("💡 API quota exceeded. Check Google AI Studio dashboard")

        raise


def main():
    parser = argparse.ArgumentParser(
        description='Generate images using Google Gemini Imagen 4 API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic generation
  python generate.py "Robot holding a red skateboard"

  # With options
  python generate.py "Sunset over mountains" --count 4 --aspect-ratio 16:9

  # Ultra quality with 2K resolution
  python generate.py "Futuristic city" --model ultra --size 2K

  # Allow all person types (where available)
  python generate.py "Family picnic" --person-generation allow_all

  # Fast generation
  python generate.py "Abstract art" --model fast
        """
    )

    parser.add_argument(
        'prompt',
        type=str,
        help='Text prompt for image generation (English only)'
    )

    parser.add_argument(
        '--model',
        type=str,
        choices=['standard', 'ultra', 'fast'],
        default='standard',
        help='Model tier (default: standard)'
    )

    parser.add_argument(
        '--count',
        type=int,
        default=4,
        choices=range(1, 5),
        metavar='1-4',
        help='Number of images to generate (default: 4)'
    )

    parser.add_argument(
        '--aspect-ratio',
        type=str,
        default='1:1',
        choices=ASPECT_RATIOS,
        help='Image aspect ratio (default: 1:1)'
    )

    parser.add_argument(
        '--size',
        type=str,
        default='1K',
        choices=['1K', '2K'],
        help='Image resolution (default: 1K) - only for standard/ultra'
    )

    parser.add_argument(
        '--person-generation',
        type=str,
        default='allow_adult',
        choices=PERSON_GENERATION,
        help='Person depiction control (default: allow_adult)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default='./generated_images/',
        help='Output directory (default: ./generated_images/)'
    )

    args = parser.parse_args()

    # Generate images
    try:
        saved_paths = generate_images(
            prompt=args.prompt,
            model=args.model,
            count=args.count,
            aspect_ratio=args.aspect_ratio,
            size=args.size,
            person_generation=args.person_generation,
            output_dir=args.output
        )

        print("\n📂 Generated images:")
        for path in saved_paths:
            print(f"   {path}")

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()