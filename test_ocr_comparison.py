#!/usr/bin/env python3
"""
OCR Comparison Test Script
Compares Groq DeepSeek OCR vs Local OCR (Tesseract) on handwritten notes.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    import base64

    from groq import Groq

    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️  Groq library not available. Install with: pip install groq")

try:
    import pytesseract
    from PIL import Image

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("⚠️  Tesseract not available. Install with: pip install pytesseract pillow")


class OCRComparison:
    """Compare different OCR engines on handwritten text."""

    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key or os.environ.get("GROQ_API_KEY")
        self.groq_client = None

        if self.groq_api_key and GROQ_AVAILABLE:
            self.groq_client = Groq(api_key=self.groq_api_key)

    def encode_image_base64(self, image_path: Path) -> str:
        """Encode image to base64 for API calls."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def ocr_groq_deepseek(self, image_path: Path) -> Dict:
        """
        Run OCR using Groq's DeepSeek Vision API.

        Returns dict with:
        - text: extracted text
        - time: processing time in seconds
        - error: error message if failed
        """
        if not self.groq_client:
            return {"text": "", "time": 0, "error": "Groq client not initialized"}

        start_time = time.time()

        try:
            # Read and encode image
            image_data = self.encode_image_base64(image_path)

            # Call Groq Vision API with Llama Vision model
            # Try Llama 4 Scout first, fallback to Llama 3.2 Vision
            models_to_try = [
                "meta-llama/llama-4-scout-17b-16e-instruct",
                "llama-3.2-90b-vision-preview",
                "llama-3.2-11b-vision-preview",
            ]

            response = None
            last_error = None

            for model in models_to_try:
                try:
                    response = self.groq_client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": (
                                            "Extract all text from this image. "
                                            "Transcribe exactly what you see, "
                                            "preserving line breaks and formatting. "
                                            "Focus on accuracy. This is handwritten text."
                                        ),
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/png;base64,{image_data}"},
                                    },
                                ],
                            }
                        ],
                        temperature=0.1,
                        max_tokens=2000,
                    )
                    break  # Success, exit loop
                except Exception as e:
                    last_error = str(e)
                    continue

            if response is None:
                raise Exception(f"All models failed. Last error: {last_error}")

            elapsed = time.time() - start_time
            text = response.choices[0].message.content

            return {
                "text": text,
                "time": elapsed,
                "error": None,
                "tokens": response.usage.total_tokens if hasattr(response, "usage") else None,
            }

        except Exception as e:
            elapsed = time.time() - start_time
            return {"text": "", "time": elapsed, "error": str(e)}

    def ocr_tesseract(self, image_path: Path) -> Dict:
        """
        Run OCR using Tesseract (local baseline).

        Returns dict with:
        - text: extracted text
        - time: processing time in seconds
        - error: error message if failed
        """
        if not TESSERACT_AVAILABLE:
            return {"text": "", "time": 0, "error": "Tesseract not available"}

        start_time = time.time()

        try:
            img = Image.open(image_path)

            # Run Tesseract with handwriting-friendly settings
            custom_config = r"--oem 3 --psm 6"  # PSM 6 = Assume uniform block of text
            text = pytesseract.image_to_string(img, config=custom_config)

            elapsed = time.time() - start_time

            return {"text": text, "time": elapsed, "error": None}

        except Exception as e:
            elapsed = time.time() - start_time
            return {"text": "", "time": elapsed, "error": str(e)}

    def compare_on_file(self, image_path: Path) -> Dict:
        """Run all available OCR engines on a single file."""
        print(f"\n{'='*60}")
        print(f"Processing: {image_path.name}")
        print(f"{'='*60}")

        results = {
            "file": str(image_path),
            "file_size_kb": image_path.stat().st_size / 1024,
            "ocr_results": {},
        }

        # Test Groq DeepSeek
        if self.groq_client:
            print("\n🤖 Testing Groq DeepSeek OCR...")
            groq_result = self.ocr_groq_deepseek(image_path)
            results["ocr_results"]["groq_deepseek"] = groq_result

            if groq_result["error"]:
                print(f"   ❌ Error: {groq_result['error']}")
            else:
                print(f"   ✅ Success in {groq_result['time']:.2f}s")
                print(f"   📝 Text length: {len(groq_result['text'])} chars")
                if groq_result.get("tokens"):
                    print(f"   🎫 Tokens used: {groq_result['tokens']}")
        else:
            print("\n⚠️  Groq DeepSeek OCR not available")

        # Test Tesseract
        if TESSERACT_AVAILABLE:
            print("\n🔤 Testing Tesseract OCR...")
            tess_result = self.ocr_tesseract(image_path)
            results["ocr_results"]["tesseract"] = tess_result

            if tess_result["error"]:
                print(f"   ❌ Error: {tess_result['error']}")
            else:
                print(f"   ✅ Success in {tess_result['time']:.2f}s")
                print(f"   📝 Text length: {len(tess_result['text'])} chars")
        else:
            print("\n⚠️  Tesseract OCR not available")

        return results

    def display_comparison(self, results: Dict):
        """Display side-by-side comparison of OCR results."""
        print(f"\n{'='*60}")
        print("TEXT COMPARISON")
        print(f"{'='*60}")

        ocr_results = results["ocr_results"]

        for engine, data in ocr_results.items():
            if data["error"]:
                continue

            print(f"\n{'─'*60}")
            print(f"🔹 {engine.upper()}")
            print(f"{'─'*60}")
            print(data["text"][:500])  # First 500 chars
            if len(data["text"]) > 500:
                print(f"\n... (truncated, total: {len(data['text'])} chars)")

    def save_results(self, all_results: List[Dict], output_path: Path):
        """Save results to JSON file."""
        with open(output_path, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\n💾 Results saved to: {output_path}")


def main():
    """Main test function."""
    print("🔬 OCR COMPARISON TEST")
    print("=" * 60)

    # Initialize comparison
    comparison = OCRComparison()

    # Check what's available
    print("\n📋 Available OCR Engines:")
    if comparison.groq_client:
        print("   ✅ Groq DeepSeek Vision")
    else:
        print("   ❌ Groq DeepSeek Vision (API key missing)")

    if TESSERACT_AVAILABLE:
        print("   ✅ Tesseract (local)")
    else:
        print("   ❌ Tesseract (not installed)")

    # Find test images
    test_dir = Path("exemples/handwritten")
    if not test_dir.exists():
        print(f"\n❌ Test directory not found: {test_dir}")
        return

    image_files = list(test_dir.glob("*.png")) + list(test_dir.glob("*.jpg"))
    if not image_files:
        print(f"\n❌ No images found in {test_dir}")
        return

    print(f"\n📁 Found {len(image_files)} test image(s)")

    # Run comparison on all files
    all_results = []
    for img_path in sorted(image_files):
        result = comparison.compare_on_file(img_path)
        all_results.append(result)
        comparison.display_comparison(result)

    # Save results
    output_path = Path("ocr_comparison_results.json")
    comparison.save_results(all_results, output_path)

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)

    for result in all_results:
        print(f"\n{Path(result['file']).name}:")
        for engine, data in result["ocr_results"].items():
            if data["error"]:
                print(f"  {engine}: ❌ {data['error']}")
            else:
                print(f"  {engine}: ✅ {data['time']:.2f}s, {len(data['text'])} chars")


if __name__ == "__main__":
    main()
