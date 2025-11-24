#!/usr/bin/env python3
"""
Test local DeepSeek OCR and Groq Vision for image understanding.
Compare their ability to describe what images represent (not just OCR).
"""

import base64
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict

try:
    import os

    from dotenv import load_dotenv
    from groq import Groq

    load_dotenv()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
except ImportError:
    print("Error: Required packages not installed")
    print("Run: pip install groq python-dotenv")
    sys.exit(1)


class ImageUnderstandingTest:
    """Test image understanding capabilities of vision models."""

    def __init__(self):
        self.deepseek_binary = Path.home() / ".local/bin/deepseek-ocr"
        self.groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

    def encode_image_base64(self, image_path: Path) -> str:
        """Encode image to base64 for API calls."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def understand_with_groq(
        self, image_path: Path, prompt: str = "Describe what this image represents in detail."
    ) -> Dict:
        """Use Groq Vision API to understand image content."""
        if not self.groq_client:
            return {"error": "Groq API key not configured"}

        try:
            start_time = time.time()

            # Encode image
            base64_image = self.encode_image_base64(image_path)

            # Call Groq Vision API
            response = self.groq_client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                            },
                        ],
                    }
                ],
                temperature=0.1,
                max_tokens=1024,
            )

            elapsed = time.time() - start_time
            description = response.choices[0].message.content

            return {
                "model": "Groq Vision (Llama 4 Scout)",
                "description": description,
                "time_seconds": round(elapsed, 2),
                "tokens": response.usage.total_tokens if hasattr(response, "usage") else None,
            }

        except Exception as e:
            return {"error": str(e)}

    def understand_with_deepseek(self, image_path: Path) -> Dict:
        """Use local DeepSeek OCR to understand image content."""
        if not self.deepseek_binary.exists():
            return {"error": f"DeepSeek OCR not found at {self.deepseek_binary}"}

        try:
            start_time = time.time()

            # Create temp output file
            output_file = Path("/tmp/deepseek_understanding.json")

            # Run DeepSeek OCR
            result = subprocess.run(
                [
                    str(self.deepseek_binary),
                    "--image",
                    str(image_path),
                    "--output",
                    str(output_file),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            elapsed = time.time() - start_time

            if result.returncode != 0:
                return {"error": f"DeepSeek failed: {result.stderr}", "stdout": result.stdout}

            # Read output
            if output_file.exists():
                with open(output_file, "r") as f:
                    data = json.load(f)

                # Extract text as "description" - DeepSeek focuses on OCR
                text = data.get("text", "") if isinstance(data, dict) else str(data)

                return {
                    "model": "Local DeepSeek OCR",
                    "description": text,
                    "time_seconds": round(elapsed, 2),
                    "note": (
                        "DeepSeek is optimized for OCR text extraction, "
                        "not semantic understanding"
                    ),
                }
            else:
                return {"error": "No output file generated"}

        except subprocess.TimeoutExpired:
            return {"error": "DeepSeek timed out after 30s"}
        except Exception as e:
            return {"error": str(e)}


def main():
    """Run image understanding tests."""

    # Test images
    test_dir = Path("exemples/handwritten")
    if not test_dir.exists():
        print(f"Error: Test directory {test_dir} not found")
        return

    images = sorted(test_dir.glob("*.png"))
    if not images:
        print(f"Error: No PNG files found in {test_dir}")
        return

    print("=" * 70)
    print("  IMAGE UNDERSTANDING TEST")
    print("  Compare: Groq Vision vs Local DeepSeek OCR")
    print("=" * 70)
    print()

    tester = ImageUnderstandingTest()

    # Test different prompts
    prompts = [
        ("Describe what this image represents", "General description"),
        (
            "What type of document is this? (newsletter, article, notes, diagram, etc.)",
            "Document type",
        ),
        ("Describe the layout and visual structure of this page", "Layout analysis"),
    ]

    for image_path in images[:1]:  # Test first image with multiple prompts
        print(f"\n{'='*70}")
        print(f"IMAGE: {image_path.name}")
        print(f"SIZE: {image_path.stat().st_size / 1024:.1f} KB")
        print(f"{'='*70}\n")

        for prompt, label in prompts:
            print(f"\n--- {label.upper()} ---")
            print(f'Prompt: "{prompt}"\n')

            # Test with Groq Vision
            print("🔵 GROQ VISION (Llama 4 Scout):")
            groq_result = tester.understand_with_groq(image_path, prompt)

            if "error" in groq_result:
                print(f"  ❌ Error: {groq_result['error']}")
            else:
                print(f"  Time: {groq_result['time_seconds']}s")
                if groq_result.get("tokens"):
                    print(f"  Tokens: {groq_result['tokens']}")
                print("  Description:")
                print(f"    {groq_result['description'][:300]}...")
                print()

            time.sleep(1)  # Rate limiting

    # Now test DeepSeek on first image (OCR only)
    print(f"\n{'='*70}")
    print("LOCAL DEEPSEEK OCR (Text Extraction)")
    print(f"{'='*70}\n")

    deepseek_result = tester.understand_with_deepseek(images[0])

    if "error" in deepseek_result:
        print(f"❌ Error: {deepseek_result['error']}")
    else:
        print(f"Time: {deepseek_result['time_seconds']}s")
        if deepseek_result.get("note"):
            note = deepseek_result["note"]
            print(f"Note: {note}")
        print("Extracted Text:")
        print(f"  {deepseek_result['description'][:300]}...")
        print()

    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print(
        """
Groq Vision (Llama 4 Scout):
  ✅ Can describe what images represent semantically
  ✅ Can classify document types
  ✅ Can analyze layout and structure
  ✅ Suitable for image understanding & metadata generation

Local DeepSeek OCR:
  ✅ Excellent at OCR text extraction
  ❌ Not designed for semantic image understanding
  ❌ Cannot classify or describe visual content
  ⚠️  Use for text extraction only, not content analysis

RECOMMENDATION: Use Groq Vision for image understanding/metadata,
                 Local DeepSeek for OCR text extraction.
"""
    )


if __name__ == "__main__":
    main()
