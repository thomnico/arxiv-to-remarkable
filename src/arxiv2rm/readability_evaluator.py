"""
Readability Evaluator for PDF conversion quality assessment.

Renders PDF pages to images for visual comparison and quality assessment.
Designed to work with Claude Code CLI for AI-powered analysis.

Evaluates:
- Overall formatting quality and human readability
- Mathematical formula accuracy and rendering
- Table structure preservation
- Text spacing and alignment
- Layout consistency

Usage with Claude Code CLI:
    1. Run: arxiv2rm evaluate source.pdf output.pdf --render-only
    2. This creates comparison images in a temp directory
    3. Ask Claude Code to analyze the images using the Read tool

This agent helps identify conversion issues before uploading to reMarkable.
"""

import base64
import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """Quality level ratings for conversion evaluation."""

    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"  # 70-89%
    ACCEPTABLE = "acceptable"  # 50-69%
    POOR = "poor"  # 30-49%
    UNACCEPTABLE = "unacceptable"  # 0-29%

    @classmethod
    def from_score(cls, score: float) -> "QualityLevel":
        """Get quality level from numeric score (0-100)."""
        if score >= 90:
            return cls.EXCELLENT
        elif score >= 70:
            return cls.GOOD
        elif score >= 50:
            return cls.ACCEPTABLE
        elif score >= 30:
            return cls.POOR
        else:
            return cls.UNACCEPTABLE


@dataclass
class FormattingIssue:
    """Represents a formatting issue found during evaluation."""

    category: str  # "spacing", "alignment", "font", "layout", "math", "table"
    severity: str  # "critical", "major", "minor"
    description: str
    page_number: Optional[int] = None
    location: Optional[str] = None  # e.g., "top-left", "equation 3"
    suggestion: Optional[str] = None


@dataclass
class MathEvaluation:
    """Evaluation results for mathematical content."""

    total_formulas: int = 0
    correctly_rendered: int = 0
    issues: List[str] = field(default_factory=list)
    score: float = 100.0


@dataclass
class TableEvaluation:
    """Evaluation results for table content."""

    total_tables: int = 0
    correctly_rendered: int = 0
    issues: List[str] = field(default_factory=list)
    score: float = 100.0


@dataclass
class PageEvaluation:
    """Evaluation results for a single page."""

    page_number: int
    formatting_score: float  # 0-100
    readability_score: float  # 0-100
    math_score: float  # 0-100
    table_score: float  # 0-100
    issues: List[FormattingIssue] = field(default_factory=list)
    details: str = ""


@dataclass
class EvaluationResult:
    """Complete evaluation result for a document conversion."""

    # Source info
    source_path: Path
    output_path: Path

    # Overall scores (0-100)
    overall_score: float = 0.0
    formatting_score: float = 0.0
    readability_score: float = 0.0
    math_accuracy_score: float = 0.0
    table_accuracy_score: float = 0.0

    # Quality level
    quality_level: QualityLevel = QualityLevel.UNACCEPTABLE

    # Detailed results
    page_evaluations: List[PageEvaluation] = field(default_factory=list)
    math_evaluation: MathEvaluation = field(default_factory=MathEvaluation)
    table_evaluation: TableEvaluation = field(default_factory=TableEvaluation)
    issues: List[FormattingIssue] = field(default_factory=list)

    # Summary
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_path": str(self.source_path),
            "output_path": str(self.output_path),
            "overall_score": self.overall_score,
            "quality_level": self.quality_level.value,
            "scores": {
                "formatting": self.formatting_score,
                "readability": self.readability_score,
                "math_accuracy": self.math_accuracy_score,
                "table_accuracy": self.table_accuracy_score,
            },
            "issues_count": len(self.issues),
            "critical_issues": len([i for i in self.issues if i.severity == "critical"]),
            "summary": self.summary,
            "recommendations": self.recommendations,
        }


class ReadabilityEvaluator:
    """
    Evaluates PDF conversion quality using Claude Vision API.

    Compares source PDF pages with converted output to assess:
    - Formatting preservation
    - Human readability on e-ink displays
    - Mathematical formula accuracy
    - Table structure preservation

    Usage:
        evaluator = ReadabilityEvaluator(api_key="your-api-key")
        result = evaluator.evaluate("source.pdf", "output.pdf")
        print(f"Quality: {result.quality_level.value} ({result.overall_score:.1f}%)")
    """

    # Evaluation prompts for Claude Vision
    FORMATTING_PROMPT = """Analyze these two PDF page images side by side.

LEFT IMAGE: Original source PDF
RIGHT IMAGE: Converted/reformatted PDF

Evaluate the conversion quality focusing on FORMATTING and READABILITY:

1. TEXT FORMATTING (0-100):
   - Is text properly spaced (not cramped or too spread)?
   - Are paragraphs well-separated?
   - Is line height comfortable for reading?
   - Are fonts clear and readable?

2. LAYOUT PRESERVATION (0-100):
   - Is the document structure maintained?
   - Are headings/sections properly formatted?
   - Is the hierarchy clear?

3. VISUAL READABILITY (0-100):
   - Would this be comfortable to read on an e-ink display?
   - Is there good contrast?
   - Is the text size appropriate?

Respond in JSON format:
{
    "text_formatting_score": <0-100>,
    "layout_score": <0-100>,
    "readability_score": <0-100>,
    "issues": [
        {"category": "spacing|alignment|font|layout", "severity": "critical|major|minor",
         "description": "..."}
    ],
    "overall_impression": "brief summary"
}"""

    MATH_PROMPT = """Analyze these two PDF page images for MATHEMATICAL CONTENT accuracy.

LEFT IMAGE: Original source PDF
RIGHT IMAGE: Converted/reformatted PDF

Focus on mathematical formulas, equations, and symbols:

1. FORMULA ACCURACY (0-100):
   - Are all mathematical symbols correctly rendered?
   - Are equations properly formatted (fractions, superscripts, subscripts)?
   - Are Greek letters and special symbols correct?

2. FORMULA POSITIONING (0-100):
   - Are inline equations properly aligned with text?
   - Are display equations centered appropriately?
   - Is spacing around equations correct?

3. FORMULA COMPLETENESS (0-100):
   - Are all formulas from the source present?
   - Are any parts cut off or missing?

Count any mathematical content you see in both images.

Respond in JSON format:
{
    "formula_count_source": <number>,
    "formula_count_output": <number>,
    "accuracy_score": <0-100>,
    "positioning_score": <0-100>,
    "completeness_score": <0-100>,
    "issues": [
        {"formula_id": "optional", "problem": "description of issue"}
    ],
    "summary": "brief summary of math rendering quality"
}"""

    TABLE_PROMPT = """Analyze these two PDF page images for TABLE content accuracy.

LEFT IMAGE: Original source PDF
RIGHT IMAGE: Converted/reformatted PDF

Focus on tables, their structure, and data:

1. STRUCTURE PRESERVATION (0-100):
   - Are table borders/gridlines correct?
   - Is the column/row structure maintained?
   - Are merged cells handled correctly?

2. DATA ACCURACY (0-100):
   - Is all text content from tables preserved?
   - Are numbers and values correct?
   - Is alignment within cells correct?

3. READABILITY (0-100):
   - Are tables easy to read in the converted version?
   - Is spacing adequate?
   - Would this work well on an e-ink display?

Count any tables you see in both images.

Respond in JSON format:
{
    "table_count_source": <number>,
    "table_count_output": <number>,
    "structure_score": <0-100>,
    "data_score": <0-100>,
    "readability_score": <0-100>,
    "issues": [
        {"table_id": "optional", "problem": "description of issue"}
    ],
    "summary": "brief summary of table rendering quality"
}"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize the readability evaluator.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Claude model to use for evaluation
            cache_dir: Directory to cache rendered page images
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning(
                "No Anthropic API key provided. " "Set ANTHROPIC_API_KEY or pass api_key parameter."
            )

        self.model = model
        self.cache_dir = cache_dir or Path(tempfile.gettempdir()) / "arxiv2rm_eval_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ReadabilityEvaluator initialized (model: {model})")

    def evaluate(
        self,
        source_path: Path,
        output_path: Path,
        sample_pages: Optional[List[int]] = None,
        max_pages: int = 5,
    ) -> EvaluationResult:
        """
        Evaluate conversion quality by comparing source and output PDFs.

        Args:
            source_path: Path to original source PDF
            output_path: Path to converted output PDF
            sample_pages: Specific page numbers to evaluate (1-indexed)
            max_pages: Maximum number of pages to evaluate if sample_pages not specified

        Returns:
            EvaluationResult with detailed quality assessment
        """
        source_path = Path(source_path)
        output_path = Path(output_path)

        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        if not output_path.exists():
            raise FileNotFoundError(f"Output file not found: {output_path}")

        logger.info(f"Evaluating conversion: {source_path.name} -> {output_path.name}")

        result = EvaluationResult(
            source_path=source_path,
            output_path=output_path,
        )

        # Determine pages to evaluate
        source_pages = self._get_page_count(source_path)
        output_pages = self._get_page_count(output_path)

        if sample_pages:
            pages_to_evaluate = [p for p in sample_pages if p <= min(source_pages, output_pages)]
        else:
            # Sample first, middle, and last pages plus some random
            total_pages = min(source_pages, output_pages)
            if total_pages <= max_pages:
                pages_to_evaluate = list(range(1, total_pages + 1))
            else:
                # Strategic sampling: first, last, and evenly spaced middle pages
                pages_to_evaluate = [1]
                if total_pages > 2:
                    step = (total_pages - 1) // (max_pages - 1)
                    for i in range(1, max_pages - 1):
                        pages_to_evaluate.append(1 + i * step)
                pages_to_evaluate.append(total_pages)
                pages_to_evaluate = sorted(set(pages_to_evaluate))[:max_pages]

        logger.info(f"Evaluating pages: {pages_to_evaluate}")

        # Evaluate each page
        for page_num in pages_to_evaluate:
            page_eval = self._evaluate_page(source_path, output_path, page_num)
            result.page_evaluations.append(page_eval)
            result.issues.extend(page_eval.issues)

        # Calculate aggregate scores
        if result.page_evaluations:
            result.formatting_score = sum(
                p.formatting_score for p in result.page_evaluations
            ) / len(result.page_evaluations)
            result.readability_score = sum(
                p.readability_score for p in result.page_evaluations
            ) / len(result.page_evaluations)
            result.math_accuracy_score = sum(p.math_score for p in result.page_evaluations) / len(
                result.page_evaluations
            )
            result.table_accuracy_score = sum(p.table_score for p in result.page_evaluations) / len(
                result.page_evaluations
            )

            # Overall score (weighted average)
            result.overall_score = (
                result.formatting_score * 0.3
                + result.readability_score * 0.3
                + result.math_accuracy_score * 0.25
                + result.table_accuracy_score * 0.15
            )

        result.quality_level = QualityLevel.from_score(result.overall_score)

        # Generate summary and recommendations
        result.summary = self._generate_summary(result)
        result.recommendations = self._generate_recommendations(result)

        logger.info(
            f"Evaluation complete: {result.quality_level.value} " f"({result.overall_score:.1f}%)"
        )

        return result

    def _evaluate_page(
        self,
        source_path: Path,
        output_path: Path,
        page_num: int,
    ) -> PageEvaluation:
        """
        Evaluate a single page comparison.

        Args:
            source_path: Source PDF path
            output_path: Output PDF path
            page_num: Page number to evaluate (1-indexed)

        Returns:
            PageEvaluation with scores and issues
        """
        logger.debug(f"Evaluating page {page_num}")

        page_eval = PageEvaluation(
            page_number=page_num,
            formatting_score=50.0,
            readability_score=50.0,
            math_score=100.0,
            table_score=100.0,
        )

        try:
            # Render pages to images
            source_image = self._render_page(source_path, page_num)
            output_image = self._render_page(output_path, page_num)

            # Create side-by-side comparison image
            comparison_image = self._create_comparison_image(source_image, output_image)

            # Evaluate formatting and readability
            formatting_result = self._call_vision_api(comparison_image, self.FORMATTING_PROMPT)
            if formatting_result:
                page_eval.formatting_score = (
                    formatting_result.get("text_formatting_score", 50)
                    + formatting_result.get("layout_score", 50)
                ) / 2
                page_eval.readability_score = formatting_result.get("readability_score", 50)

                for issue_data in formatting_result.get("issues", []):
                    page_eval.issues.append(
                        FormattingIssue(
                            category=issue_data.get("category", "unknown"),
                            severity=issue_data.get("severity", "minor"),
                            description=issue_data.get("description", ""),
                            page_number=page_num,
                        )
                    )

            # Evaluate math content
            math_result = self._call_vision_api(comparison_image, self.MATH_PROMPT)
            if math_result:
                math_scores = [
                    math_result.get("accuracy_score", 100),
                    math_result.get("positioning_score", 100),
                    math_result.get("completeness_score", 100),
                ]
                page_eval.math_score = sum(math_scores) / len(math_scores)

                for issue_data in math_result.get("issues", []):
                    page_eval.issues.append(
                        FormattingIssue(
                            category="math",
                            severity="major",
                            description=issue_data.get("problem", ""),
                            page_number=page_num,
                            location=issue_data.get("formula_id"),
                        )
                    )

            # Evaluate table content
            table_result = self._call_vision_api(comparison_image, self.TABLE_PROMPT)
            if table_result:
                table_scores = [
                    table_result.get("structure_score", 100),
                    table_result.get("data_score", 100),
                    table_result.get("readability_score", 100),
                ]
                page_eval.table_score = sum(table_scores) / len(table_scores)

                for issue_data in table_result.get("issues", []):
                    page_eval.issues.append(
                        FormattingIssue(
                            category="table",
                            severity="major",
                            description=issue_data.get("problem", ""),
                            page_number=page_num,
                            location=issue_data.get("table_id"),
                        )
                    )

        except Exception as e:
            logger.error(f"Error evaluating page {page_num}: {e}")
            page_eval.details = f"Evaluation error: {e}"

        return page_eval

    def _render_page(self, pdf_path: Path, page_num: int, dpi: int = 150) -> Image.Image:
        """
        Render a PDF page to image.

        Args:
            pdf_path: PDF file path
            page_num: Page number (1-indexed)
            dpi: Resolution for rendering

        Returns:
            PIL Image of the rendered page
        """
        # Generate cache key
        cache_key = hashlib.md5(
            f"{pdf_path}:{page_num}:{dpi}:{pdf_path.stat().st_mtime}".encode()
        ).hexdigest()
        cache_file = self.cache_dir / f"page_{cache_key}.png"

        if cache_file.exists():
            return Image.open(cache_file)

        # Render page with PyMuPDF
        doc = fitz.open(pdf_path)
        page = doc[page_num - 1]  # 0-indexed

        # Calculate zoom for target DPI
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        # Render to pixmap
        pix = page.get_pixmap(matrix=matrix)

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        doc.close()

        # Cache the result
        img.save(cache_file, "PNG")

        return img

    def _create_comparison_image(
        self,
        source_image: Image.Image,
        output_image: Image.Image,
    ) -> Image.Image:
        """
        Create a side-by-side comparison image.

        Args:
            source_image: Original PDF page image
            output_image: Converted PDF page image

        Returns:
            Combined side-by-side image
        """
        # Resize to same height for comparison
        max_height = max(source_image.height, output_image.height)
        max_width = 800  # Limit width for API

        # Scale source
        source_ratio = min(max_width / source_image.width, max_height / source_image.height)
        source_scaled = source_image.resize(
            (int(source_image.width * source_ratio), int(source_image.height * source_ratio)),
            Image.Resampling.LANCZOS,
        )

        # Scale output
        output_ratio = min(max_width / output_image.width, max_height / output_image.height)
        output_scaled = output_image.resize(
            (int(output_image.width * output_ratio), int(output_image.height * output_ratio)),
            Image.Resampling.LANCZOS,
        )

        # Create combined image
        combined_width = source_scaled.width + output_scaled.width + 20  # 20px gap
        combined_height = max(source_scaled.height, output_scaled.height)

        combined = Image.new("RGB", (combined_width, combined_height), (255, 255, 255))
        combined.paste(source_scaled, (0, 0))
        combined.paste(output_scaled, (source_scaled.width + 20, 0))

        return combined

    def _call_vision_api(self, image: Image.Image, prompt: str) -> Optional[Dict]:
        """
        Call Claude Vision API with image and prompt.

        Args:
            image: PIL Image to analyze
            prompt: Evaluation prompt

        Returns:
            Parsed JSON response or None if failed
        """
        if not self.api_key:
            logger.warning("No API key - using fallback evaluation")
            return self._fallback_evaluation(prompt)

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)

            # Convert image to base64
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            # Call API
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )

            # Parse JSON response
            response_text = response.content[0].text

            # Extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)

        except ImportError:
            logger.warning("anthropic package not installed - using fallback evaluation")
            return self._fallback_evaluation(prompt)
        except Exception as e:
            logger.error(f"Vision API call failed: {e}")

        return None

    def _fallback_evaluation(self, prompt: str) -> Dict:
        """
        Provide fallback evaluation when API is unavailable.

        Returns conservative default scores.
        """
        if "FORMATTING" in prompt:
            return {
                "text_formatting_score": 50,
                "layout_score": 50,
                "readability_score": 50,
                "issues": [],
                "overall_impression": "Unable to evaluate - API unavailable",
            }
        elif "MATH" in prompt:
            return {
                "formula_count_source": 0,
                "formula_count_output": 0,
                "accuracy_score": 50,
                "positioning_score": 50,
                "completeness_score": 50,
                "issues": [],
                "summary": "Unable to evaluate - API unavailable",
            }
        elif "TABLE" in prompt:
            return {
                "table_count_source": 0,
                "table_count_output": 0,
                "structure_score": 50,
                "data_score": 50,
                "readability_score": 50,
                "issues": [],
                "summary": "Unable to evaluate - API unavailable",
            }
        return {}

    def _get_page_count(self, pdf_path: Path) -> int:
        """Get number of pages in PDF."""
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count

    def _generate_summary(self, result: EvaluationResult) -> str:
        """Generate human-readable summary of evaluation."""
        quality = result.quality_level.value.upper()
        score = result.overall_score

        critical_issues = len([i for i in result.issues if i.severity == "critical"])
        major_issues = len([i for i in result.issues if i.severity == "major"])

        summary = f"Conversion Quality: {quality} ({score:.1f}%)\n\n"
        summary += f"• Formatting: {result.formatting_score:.1f}%\n"
        summary += f"• Readability: {result.readability_score:.1f}%\n"
        summary += f"• Math Accuracy: {result.math_accuracy_score:.1f}%\n"
        summary += f"• Table Accuracy: {result.table_accuracy_score:.1f}%\n\n"

        if critical_issues > 0 or major_issues > 0:
            summary += f"Issues Found: {critical_issues} critical, {major_issues} major\n"

        return summary

    def _generate_recommendations(self, result: EvaluationResult) -> List[str]:
        """Generate recommendations based on evaluation results."""
        recommendations = []

        if result.formatting_score < 70:
            recommendations.append(
                "Consider adjusting paragraph spacing and line height for better formatting"
            )

        if result.readability_score < 70:
            recommendations.append(
                "Review font size and contrast settings for e-ink display optimization"
            )

        if result.math_accuracy_score < 80:
            recommendations.append(
                "Check math formula rendering - some equations may need manual review"
            )

        if result.table_accuracy_score < 80:
            recommendations.append(
                "Table formatting needs attention - verify structure preservation"
            )

        # Add specific issue-based recommendations
        categories = {}
        for issue in result.issues:
            if issue.category not in categories:
                categories[issue.category] = 0
            categories[issue.category] += 1

        if categories.get("spacing", 0) > 2:
            recommendations.append("Multiple spacing issues detected - review text flow settings")

        if categories.get("math", 0) > 2:
            recommendations.append(
                "Multiple math rendering issues - consider using higher DPI for formulas"
            )

        if not recommendations:
            recommendations.append("Conversion quality is acceptable - no major changes needed")

        return recommendations


def evaluate_conversion(
    source_path: Path,
    output_path: Path,
    api_key: Optional[str] = None,
    verbose: bool = False,
) -> EvaluationResult:
    """
    Convenience function to evaluate a PDF conversion.

    Args:
        source_path: Path to original PDF
        output_path: Path to converted PDF
        api_key: Anthropic API key (optional)
        verbose: Print detailed results

    Returns:
        EvaluationResult with quality assessment
    """
    evaluator = ReadabilityEvaluator(api_key=api_key)
    result = evaluator.evaluate(source_path, output_path)

    if verbose:
        print(result.summary)
        if result.recommendations:
            print("\nRecommendations:")
            for rec in result.recommendations:
                print(f"  • {rec}")

    return result


# Example usage and testing
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) >= 3:
        source = Path(sys.argv[1])
        output = Path(sys.argv[2])

        print(f"Evaluating: {source} -> {output}")
        result = evaluate_conversion(source, output, verbose=True)
        print(f"\nOverall Score: {result.overall_score:.1f}%")
        print(f"Quality Level: {result.quality_level.value}")
    else:
        print("Usage: python readability_evaluator.py <source.pdf> <output.pdf>")
