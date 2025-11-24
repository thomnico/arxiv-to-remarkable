#!/bin/bash
# CLI Examples - ArXiv-to-reMarkable Image Understanding

echo "=================================================================="
echo "  ArXiv-to-reMarkable - Image Understanding Examples"
echo "=================================================================="
echo ""

# Example 1: Detect handwriting in images
echo "📝 Example 1: Detect handwriting"
echo "Command: python -m arxiv2rm.cli_detect detect exemples/handwritten/*.png"
echo ""
python -m arxiv2rm.cli_detect detect exemples/handwritten/*.png
echo ""

# Example 2: Estimate OCR costs
echo "=================================================================="
echo "💰 Example 2: Estimate OCR costs"
echo "Command: python -m arxiv2rm.cli_detect estimate exemples/handwritten/*.png"
echo ""
python -m arxiv2rm.cli_detect estimate exemples/handwritten/*.png
echo ""

# Example 3: Detailed analysis
echo "=================================================================="
echo "🔍 Example 3: Detailed analysis of single image"
echo "Command: python -m arxiv2rm.cli_detect analyze 'exemples/handwritten/Newsletter - page 1.png'"
echo ""
python -m arxiv2rm.cli_detect analyze "exemples/handwritten/Newsletter - page 1.png"
echo ""

# Example 4: Image understanding (NEW)
echo "=================================================================="
echo "🖼️  Example 4: Image understanding (Groq Vision)"
echo "Command: python test_image_understanding.py"
echo ""
echo "This demonstrates:"
echo "  • Describing what images represent"
echo "  • Classifying document types"
echo "  • Analyzing layout and structure"
echo "  • Generating metadata for EXIF"
echo ""
echo "Run manually: python test_image_understanding.py"
echo ""

echo "=================================================================="
echo "📚 Documentation"
echo "=================================================================="
echo ""
echo "• Handwriting Detection: docs/automated_ocr_routing.md"
echo "• Image Understanding: IMAGE_UNDERSTANDING_DEMO.md"
echo "• Installation Guide: INSTALL.md"
echo "• Production Status: PRODUCTION_READY.md"
echo ""
echo "=================================================================="
