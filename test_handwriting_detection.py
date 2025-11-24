#!/usr/bin/env python3
"""
Test handwriting detection on multiple images.
"""

import sys
from pathlib import Path

# Add src to path before imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from arxiv2rm.handwriting_detector import HandwritingDetector  # noqa: E402


def test_handwriting_detection():
    """Test detector on both handwritten and printed samples."""

    detector = HandwritingDetector()

    # Test handwritten samples
    print("=" * 60)
    print("TESTING HANDWRITTEN SAMPLES")
    print("=" * 60)

    handwritten_dir = Path("exemples/handwritten")
    if handwritten_dir.exists():
        for img_path in sorted(handwritten_dir.glob("*.png")):
            print(f"\n📝 Testing: {img_path.name}")
            result = detector.detect(img_path)

            status = "✅ HANDWRITTEN" if result["is_handwritten"] else "❌ PRINTED"
            print(f"   Result: {status}")
            print(f"   Confidence: {result['confidence']:.2%}")
            print(f"   Route to: {result['recommendation'].upper()} OCR")

            if result["reasons"]:
                print("   Reasons:")
                for reason in result["reasons"][:3]:
                    print(f"     • {reason}")

    # Test with simulated DeepSeek results
    print("\n" + "=" * 60)
    print("TESTING WITH SIMULATED DEEPSEEK CONFIDENCE SCORES")
    print("=" * 60)

    test_cases = [
        {
            "name": "Printed text (high confidence)",
            "confidence": 0.95,
            "text": "This is a clear printed document with well-formed characters.",
            "expected": False,
        },
        {
            "name": "Handwritten text (low confidence)",
            "confidence": 0.45,
            "text": "Emerg pre modofin cn: Pour ho Mriggend",
            "expected": True,
        },
        {
            "name": "Mixed quality (medium confidence)",
            "confidence": 0.78,
            "text": "Some printed text with occasional unclear sections",
            "expected": False,
        },
    ]

    if handwritten_dir.exists():
        test_img = next(handwritten_dir.glob("*.png"))

        for case in test_cases:
            print(f"\n📊 Scenario: {case['name']}")
            print(f"   DeepSeek confidence: {case['confidence']:.2%}")

            result = detector.detect(
                test_img, deepseek_confidence=case["confidence"], deepseek_text=case["text"]
            )

            expected_label = "HANDWRITTEN" if case["expected"] else "PRINTED"
            actual_label = "HANDWRITTEN" if result["is_handwritten"] else "PRINTED"
            match = "✅" if result["is_handwritten"] == case["expected"] else "❌"

            print(f"   Expected: {expected_label}")
            print(f"   Detected: {actual_label} {match}")
            print(f"   Overall confidence: {result['confidence']:.2%}")
            print(f"   Recommendation: {result['recommendation'].upper()} OCR")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(
        """
The handwriting detector uses multiple strategies:

1. 🎯 DeepSeek Confidence Score
   - Low confidence (<85%) → likely handwritten
   - High confidence (>85%) → likely printed

2. 📊 Text Quality Analysis
   - Fragmented words → poor OCR → handwritten
   - Gibberish patterns → poor OCR → handwritten

3. 🖼️  Image Analysis
   - Edge irregularity (Canny edge detection)
   - Stroke width variance
   - Text line straightness

4. 🤖 Automated Routing
   - Handwritten → Groq Vision API (high accuracy)
   - Printed → Local DeepSeek OCR (fast, free)

This enables:
✅ Cost optimization (use free local OCR when appropriate)
✅ Quality optimization (use Groq for handwriting)
✅ Fully automated pipeline (no manual intervention)
    """
    )


if __name__ == "__main__":
    test_handwriting_detection()
