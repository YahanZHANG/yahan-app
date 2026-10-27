
import base64
import os
from pathlib import Path

import requests


# =========================================================
# OpenAI API key
# =========================================================

API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()

if not API_KEY:
    raise SystemExit(
        "OPENAI_API_KEY が設定されていません。"
    )


# =========================================================
# One-image experiment
# =========================================================

SPOT_NAME = "Arosa"

PROMPT = f"""
Create a beautiful editorial travel illustration
inspired by {SPOT_NAME}, Switzerland.

Scene:
- Scenic Swiss Alpine village atmosphere
- Beautiful mountain scenery
- Alpine lake and forest atmosphere
- Soft natural daylight
- Inviting, calm, premium travel-magazine style
- Realistic painterly illustration
- Elegant and sophisticated composition

Important:
- This is an illustrative travel image,
  not a documentary photograph.
- Do not claim to depict an exact real-world view.
- Do not invent specific named landmarks or signage.
- No text, no typography, no watermark.
"""


# =========================================================
# Generate image
# =========================================================

response = requests.post(
    "https://api.openai.com/v1/images/generations",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "gpt-image-2.5-flare",
        "prompt": PROMPT,
        "size": "1536x1024",
        "quality": "low",
        "output_format": "webp",
    },
    timeout=240,
)


# =========================================================
# Handle API errors
# =========================================================

if not response.ok:

    try:
        error = response.json().get("error", {})
        message = error.get(
            "message",
            "Unknown API error",
        )

    except ValueError:
        message = response.text[:300]

    raise RuntimeError(
        f"Image API error {response.status_code}: {message}"
    )


# =========================================================
# Decode image
# =========================================================

data = response.json()

image_b64 = data["data"][0]["b64_json"]


# =========================================================
# Save image
# =========================================================

output_dir = Path("tourist_image_tests")

output_dir.mkdir(
    exist_ok=True,
)

output_path = output_dir / "arosa_ai.webp"

output_path.write_bytes(
    base64.b64decode(image_b64)
)


# =========================================================
# Done
# =========================================================

print("Image generated successfully!")
print("Saved to:", output_path.resolve())
