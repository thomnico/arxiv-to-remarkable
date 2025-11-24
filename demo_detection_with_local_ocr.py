#!/usr/bin/env python3
"""
Demo: Handwriting Detection with Local DeepSeek OCR Integration

Shows how the detection system works with local OCR confidence scores.
"""

import sys
from pathlib import Path

# Add src to path before imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from arxiv2rm.handwriting_detector import HandwritingDetector  # noqa: E402


def simulate_local_deepseek_ocr(image_path: Path) -> dict:
    """
    Simulate local DeepSeek OCR result.

    In real implementation, this would call:
    /tmp/deepseek-ocr.rs/target/release/deepseek-ocr-cli
    """
    # For handwritten images, local OCR would produce:
    # - Low confidence (<0.85)
    # - Fragmented/gibberish text

    if "handwritten" in str(image_path).lower():
        return {
            "text": "Emerg pre modofin cn: Pour ho Mriggend s at dickens mo Rohn",
            "confidence": 0.42,  # Low confidence = poor OCR
            "time": 0.5,
            "engine": "deepseek-ocr.rs (local)",
        }
    else:
        # Printed text would produce high confidence
        return {
            "text": "This is a clear printed document with well-formed characters.",
            "confidence": 0.96,  # High confidence = good OCR
            "time": 0.3,
            "engine": "deepseek-ocr.rs (local)",
        }


def simulate_groq_ocr(image_path: Path) -> dict:
    """Simulate Groq Vision API OCR result."""
    return {
        "text": "Encore une newsletter cyber?\nPour les dirigeants et décideurs non techniques",
        "confidence": 0.95,  # Always high quality
        "time": 1.2,
        "cost": 0.04,
        "engine": "Groq Vision (Llama 4 Scout)",
    }


def demo_workflow(image_path: Path):
    """Demonstrate the complete detection and routing workflow."""

    print(f"\n{'='*70}")
    print(f"🔍 ANALYZING: {image_path.name}")
    print(f"{'='*70}")

    detector = HandwritingDetector(confidence_threshold=0.85)

    # STAGE 1: Quick pre-check (without OCR)
    print("\n📊 STAGE 1: Quick Heuristics (Image Analysis)")
    print("-" * 70)

    pre_check = detector.detect(image_path)

    print("Image-based detection:")
    print(f"  Edge density:      {pre_check['scores']['edge_density']:.2f}")
    print(f"  Stroke variance:   {pre_check['scores']['stroke_variance']:.2f}")
    print(f"  Line straightness: {pre_check['scores']['line_straightness']:.2f}")
    prelim = "HANDWRITTEN" if pre_check["is_handwritten"] else "PRINTED"
    print(f"\n  → Preliminary: {prelim}")
    print(f"  → Confidence: {pre_check['confidence']:.2%}")

    # STAGE 2: Try local OCR (if not clearly handwritten)
    print(f"\n{'='*70}")
    print("🖥️  STAGE 2: Local DeepSeek OCR")
    print("-" * 70)

    if pre_check["confidence"] > 0.9 and pre_check["is_handwritten"]:
        print("⏭️  SKIPPED - Image analysis very confident this is handwritten")
        print("   → Routing directly to Groq Vision API")
        final_decision = "groq"
        final_reason = "Pre-check confidence > 90%"
    else:
        print("▶️  RUNNING - Trying local OCR first...")
        local_result = simulate_local_deepseek_ocr(image_path)

        print("\nLocal OCR Result:")
        print(f"  Engine:     {local_result['engine']}")
        print(f"  Time:       {local_result['time']:.2f}s")
        print(f"  Confidence: {local_result['confidence']:.2%}")
        print(f"  Text (preview): {local_result['text'][:60]}...")

        # STAGE 3: Analyze confidence with all factors
        print(f"\n{'='*70}")
        print("🤖 STAGE 3: Confidence Analysis (All Factors)")
        print("-" * 70)

        full_detection = detector.detect(
            image_path,
            deepseek_confidence=local_result["confidence"],
            deepseek_text=local_result["text"],
        )

        print("\nCombined Analysis:")
        print(f"  DeepSeek confidence: {local_result['confidence']:.2%} (weight: 3×)")
        if full_detection["scores"]["text_quality"]:
            qual = full_detection["scores"]["text_quality"]
            print(f"  Text quality score:  {qual:.2f}")
        print(f"  Image features:      Avg {pre_check['confidence']:.2f}")

        print(f"\n  Final Score: {full_detection['confidence']:.2%}")
        decision = "HANDWRITTEN" if full_detection["is_handwritten"] else "PRINTED"
        print(f"  Decision: {decision}")

        if full_detection["is_handwritten"]:
            final_decision = "groq"
            final_reason = f"Low confidence ({local_result['confidence']:.2%} < 85%)"
        else:
            final_decision = "local"
            final_reason = f"High confidence ({local_result['confidence']:.2%} ≥ 85%)"

    # STAGE 4: Final routing decision
    print(f"\n{'='*70}")
    print("🎯 FINAL DECISION")
    print("-" * 70)

    if final_decision == "groq":
        print("\n✅ ROUTE TO: Groq Vision API")
        print(f"   Reason: {final_reason}")
        print("   Cost: ~$0.04")
        print("   Expected accuracy: 85-90%")

        print("\n   Simulating Groq API call...")
        groq_result = simulate_groq_ocr(image_path)
        print(f"   ✓ Complete in {groq_result['time']:.2f}s")
        print(f"   ✓ Text extracted: {len(groq_result['text'])} chars")
        print("\n   Final text (preview):")
        print(f"   {groq_result['text'][:100]}...")

    else:
        print("\n✅ ROUTE TO: Local DeepSeek OCR")
        print(f"   Reason: {final_reason}")
        print("   Cost: $0 (free)")
        print("   Expected accuracy: 97%")
        print("\n   Using local result (already extracted)")

    print(f"\n{'='*70}\n")


def main():
    """Run demo on all handwritten examples."""

    print("\n" + "=" * 70)
    print("🔬 HANDWRITING DETECTION & ROUTING DEMO")
    print("   With Local DeepSeek OCR Integration")
    print("=" * 70)

    # Demo on handwritten samples
    handwritten_dir = Path("exemples/handwritten")

    if not handwritten_dir.exists():
        print("\n❌ Error: exemples/handwritten/ not found")
        return

    image_files = list(handwritten_dir.glob("*.png"))

    if not image_files:
        print("\n❌ Error: No images found")
        return

    print(f"\n📁 Found {len(image_files)} test image(s)")

    # Demo on first image (detailed)
    print("\n" + "🎬 DETAILED WALKTHROUGH".center(70, "="))
    demo_workflow(image_files[0])

    # Quick summary for remaining images
    if len(image_files) > 1:
        print("\n" + "📊 QUICK SUMMARY (Remaining Images)".center(70, "="))

        detector = HandwritingDetector()

        for img_path in image_files[1:]:
            # Simulate local OCR
            local_result = simulate_local_deepseek_ocr(img_path)

            # Get detection with confidence
            detection = detector.detect(
                img_path,
                deepseek_confidence=local_result["confidence"],
                deepseek_text=local_result["text"],
            )

            print(f"\n{img_path.name}:")
            print(f"  Local OCR confidence: {local_result['confidence']:.2%}")
            print(
                f"  → Decision: {'Retry with GROQ' if detection['is_handwritten'] else 'Use LOCAL'}"
            )
            print(f"  → Cost: {'$0.04' if detection['is_handwritten'] else '$0'}")

    # Summary statistics
    print("\n" + "=" * 70)
    print("💡 KEY INSIGHTS")
    print("=" * 70)

    print(
        """
1. **Pre-check (Stage 1)**: Image analysis detects obvious cases
   - Very confident (>90%) → Skip local OCR, go direct to Groq
   - Saves time on clearly handwritten images

2. **Local OCR (Stage 2)**: Try free local processing first
   - Works great for printed text (97% accuracy, free)
   - Produces low confidence (<85%) on handwriting

3. **Confidence Analysis (Stage 3)**: Multi-factor decision
   - DeepSeek confidence score (3× weight)
   - Text quality analysis (fragmentation, gibberish)
   - Image features (edges, strokes, lines)

4. **Smart Routing (Stage 4)**: Optimal engine selection
   - Low confidence → Groq ($0.04, 85-90% accuracy)
   - High confidence → Local ($0, 97% accuracy)

5. **Cost Optimization**: 75% savings on mixed documents
   - Printed pages: Free local processing
   - Handwritten: Premium Groq API only when needed
"""
    )

    print("\n" + "=" * 70)
    print("📚 LEARN MORE")
    print("=" * 70)
    print(
        """
- Full Documentation: docs/automated_ocr_routing.md
- Detection Module:   src/arxiv2rm/handwriting_detector.py
- OCR Comparison:     test_ocr_comparison.py
- Technical Analysis: analyze_ocr_failure.md
"""
    )


if __name__ == "__main__":
    main()
