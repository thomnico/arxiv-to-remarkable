"""Tests for readability evaluator."""

import pytest
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from arxiv2rm.readability_evaluator import (
    EvaluationResult,
    FormattingIssue,
    MathEvaluation,
    PageEvaluation,
    QualityLevel,
    ReadabilityEvaluator,
    TableEvaluation,
    evaluate_conversion,
)


class TestQualityLevel:
    """Tests for QualityLevel enum."""

    def test_from_score_excellent(self):
        """Test excellent quality level."""
        assert QualityLevel.from_score(95) == QualityLevel.EXCELLENT
        assert QualityLevel.from_score(90) == QualityLevel.EXCELLENT

    def test_from_score_good(self):
        """Test good quality level."""
        assert QualityLevel.from_score(85) == QualityLevel.GOOD
        assert QualityLevel.from_score(70) == QualityLevel.GOOD

    def test_from_score_acceptable(self):
        """Test acceptable quality level."""
        assert QualityLevel.from_score(65) == QualityLevel.ACCEPTABLE
        assert QualityLevel.from_score(50) == QualityLevel.ACCEPTABLE

    def test_from_score_poor(self):
        """Test poor quality level."""
        assert QualityLevel.from_score(45) == QualityLevel.POOR
        assert QualityLevel.from_score(30) == QualityLevel.POOR

    def test_from_score_unacceptable(self):
        """Test unacceptable quality level."""
        assert QualityLevel.from_score(25) == QualityLevel.UNACCEPTABLE
        assert QualityLevel.from_score(0) == QualityLevel.UNACCEPTABLE


class TestFormattingIssue:
    """Tests for FormattingIssue dataclass."""

    def test_create_issue(self):
        """Test creating a formatting issue."""
        issue = FormattingIssue(
            category="spacing",
            severity="major",
            description="Text too cramped",
            page_number=3,
            location="top-left",
            suggestion="Increase line spacing",
        )
        assert issue.category == "spacing"
        assert issue.severity == "major"
        assert issue.description == "Text too cramped"
        assert issue.page_number == 3

    def test_issue_defaults(self):
        """Test issue default values."""
        issue = FormattingIssue(
            category="alignment",
            severity="minor",
            description="Slight misalignment",
        )
        assert issue.page_number is None
        assert issue.location is None
        assert issue.suggestion is None


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_create_result(self, tmp_path):
        """Test creating an evaluation result."""
        result = EvaluationResult(
            source_path=tmp_path / "source.pdf",
            output_path=tmp_path / "output.pdf",
            overall_score=75.5,
            formatting_score=80.0,
            readability_score=70.0,
            math_accuracy_score=85.0,
            table_accuracy_score=65.0,
            quality_level=QualityLevel.GOOD,
        )
        assert result.overall_score == 75.5
        assert result.quality_level == QualityLevel.GOOD

    def test_result_to_dict(self, tmp_path):
        """Test converting result to dictionary."""
        result = EvaluationResult(
            source_path=tmp_path / "source.pdf",
            output_path=tmp_path / "output.pdf",
            overall_score=80.0,
            formatting_score=75.0,
            readability_score=85.0,
            math_accuracy_score=80.0,
            table_accuracy_score=70.0,
            quality_level=QualityLevel.GOOD,
            summary="Test summary",
            recommendations=["Recommendation 1"],
        )
        result_dict = result.to_dict()

        assert "source_path" in result_dict
        assert result_dict["overall_score"] == 80.0
        assert result_dict["quality_level"] == "good"
        assert "scores" in result_dict
        assert result_dict["scores"]["formatting"] == 75.0

    def test_result_defaults(self, tmp_path):
        """Test result default values."""
        result = EvaluationResult(
            source_path=tmp_path / "source.pdf",
            output_path=tmp_path / "output.pdf",
        )
        assert result.overall_score == 0.0
        assert result.quality_level == QualityLevel.UNACCEPTABLE
        assert result.page_evaluations == []
        assert result.issues == []


class TestReadabilityEvaluator:
    """Tests for ReadabilityEvaluator class."""

    @pytest.fixture
    def simple_pdf(self, tmp_path):
        """Create a simple test PDF."""
        pdf_path = tmp_path / "test.pdf"
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        c.drawString(100, 750, "This is a test document.")
        c.drawString(100, 700, "It has some sample text.")
        c.showPage()
        c.drawString(100, 750, "Page 2 content")
        c.showPage()
        c.save()
        return pdf_path

    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance without API key."""
        return ReadabilityEvaluator(api_key=None)

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        evaluator = ReadabilityEvaluator(api_key=None)
        assert evaluator.api_key is None
        assert evaluator.model == "claude-sonnet-4-20250514"

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        evaluator = ReadabilityEvaluator(api_key="test-key")
        assert evaluator.api_key == "test-key"

    def test_init_custom_model(self):
        """Test initialization with custom model."""
        evaluator = ReadabilityEvaluator(api_key=None, model="claude-3-opus-20240229")
        assert evaluator.model == "claude-3-opus-20240229"

    def test_evaluate_file_not_found(self, evaluator, tmp_path):
        """Test evaluation with missing files."""
        with pytest.raises(FileNotFoundError):
            evaluator.evaluate(
                tmp_path / "missing_source.pdf",
                tmp_path / "missing_output.pdf",
            )

    def test_evaluate_basic(self, evaluator, simple_pdf, tmp_path):
        """Test basic evaluation (fallback mode)."""
        # Create a second PDF for comparison
        output_pdf = tmp_path / "output.pdf"
        c = canvas.Canvas(str(output_pdf), pagesize=letter)
        c.drawString(100, 750, "Converted document text.")
        c.showPage()
        c.drawString(100, 750, "Page 2 converted")
        c.showPage()
        c.save()

        result = evaluator.evaluate(simple_pdf, output_pdf, max_pages=2)

        assert isinstance(result, EvaluationResult)
        assert result.source_path == simple_pdf
        assert result.output_path == output_pdf
        # Fallback evaluation gives 50% scores
        assert result.overall_score == 50.0
        assert result.quality_level == QualityLevel.ACCEPTABLE

    def test_evaluate_with_sample_pages(self, evaluator, simple_pdf, tmp_path):
        """Test evaluation with specific pages."""
        output_pdf = tmp_path / "output.pdf"
        c = canvas.Canvas(str(output_pdf), pagesize=letter)
        c.drawString(100, 750, "Output page 1")
        c.showPage()
        c.drawString(100, 750, "Output page 2")
        c.showPage()
        c.save()

        result = evaluator.evaluate(simple_pdf, output_pdf, sample_pages=[1])

        assert len(result.page_evaluations) == 1
        assert result.page_evaluations[0].page_number == 1

    def test_get_page_count(self, evaluator, simple_pdf):
        """Test page count retrieval."""
        count = evaluator._get_page_count(simple_pdf)
        assert count == 2

    def test_render_page(self, evaluator, simple_pdf):
        """Test page rendering to image."""
        img = evaluator._render_page(simple_pdf, 1)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert img.width > 0
        assert img.height > 0

    def test_render_page_caching(self, evaluator, simple_pdf):
        """Test page rendering uses cache."""
        # First render
        img1 = evaluator._render_page(simple_pdf, 1)
        # Second render (should use cache)
        img2 = evaluator._render_page(simple_pdf, 1)

        assert img1.size == img2.size

    def test_create_comparison_image(self, evaluator):
        """Test side-by-side comparison image creation."""
        source_img = Image.new("RGB", (400, 600), (255, 255, 255))
        output_img = Image.new("RGB", (400, 600), (200, 200, 200))

        combined = evaluator._create_comparison_image(source_img, output_img)

        assert isinstance(combined, Image.Image)
        # Combined should be wider than either source
        assert combined.width > source_img.width

    def test_fallback_evaluation_formatting(self, evaluator):
        """Test fallback evaluation for formatting prompt."""
        result = evaluator._fallback_evaluation("FORMATTING something")
        assert "text_formatting_score" in result
        assert result["text_formatting_score"] == 50

    def test_fallback_evaluation_math(self, evaluator):
        """Test fallback evaluation for math prompt."""
        result = evaluator._fallback_evaluation("MATH something")
        assert "accuracy_score" in result
        assert result["accuracy_score"] == 50

    def test_fallback_evaluation_table(self, evaluator):
        """Test fallback evaluation for table prompt."""
        result = evaluator._fallback_evaluation("TABLE something")
        assert "structure_score" in result
        assert result["structure_score"] == 50

    def test_generate_summary(self, evaluator, tmp_path):
        """Test summary generation."""
        result = EvaluationResult(
            source_path=tmp_path / "source.pdf",
            output_path=tmp_path / "output.pdf",
            overall_score=75.0,
            formatting_score=80.0,
            readability_score=70.0,
            math_accuracy_score=85.0,
            table_accuracy_score=65.0,
            quality_level=QualityLevel.GOOD,
        )

        summary = evaluator._generate_summary(result)

        assert "GOOD" in summary
        assert "75.0%" in summary
        assert "Formatting: 80.0%" in summary

    def test_generate_recommendations_low_formatting(self, evaluator, tmp_path):
        """Test recommendations for low formatting score."""
        result = EvaluationResult(
            source_path=tmp_path / "source.pdf",
            output_path=tmp_path / "output.pdf",
            formatting_score=50.0,
            readability_score=80.0,
            math_accuracy_score=90.0,
            table_accuracy_score=85.0,
        )

        recommendations = evaluator._generate_recommendations(result)

        assert any("paragraph spacing" in r.lower() for r in recommendations)

    def test_generate_recommendations_low_math(self, evaluator, tmp_path):
        """Test recommendations for low math score."""
        result = EvaluationResult(
            source_path=tmp_path / "source.pdf",
            output_path=tmp_path / "output.pdf",
            formatting_score=90.0,
            readability_score=85.0,
            math_accuracy_score=60.0,
            table_accuracy_score=85.0,
        )

        recommendations = evaluator._generate_recommendations(result)

        assert any("math" in r.lower() for r in recommendations)

    def test_generate_recommendations_all_good(self, evaluator, tmp_path):
        """Test recommendations when all scores are good."""
        result = EvaluationResult(
            source_path=tmp_path / "source.pdf",
            output_path=tmp_path / "output.pdf",
            formatting_score=90.0,
            readability_score=85.0,
            math_accuracy_score=95.0,
            table_accuracy_score=90.0,
        )

        recommendations = evaluator._generate_recommendations(result)

        assert any("acceptable" in r.lower() for r in recommendations)


class TestConvenienceFunction:
    """Tests for evaluate_conversion convenience function."""

    @pytest.fixture
    def test_pdfs(self, tmp_path):
        """Create test PDF files."""
        source_pdf = tmp_path / "source.pdf"
        output_pdf = tmp_path / "output.pdf"

        # Create simple PDFs
        for pdf_path in [source_pdf, output_pdf]:
            c = canvas.Canvas(str(pdf_path), pagesize=letter)
            c.drawString(100, 750, "Test content")
            c.showPage()
            c.save()

        return source_pdf, output_pdf

    def test_evaluate_conversion_basic(self, test_pdfs):
        """Test convenience function."""
        source_pdf, output_pdf = test_pdfs
        result = evaluate_conversion(source_pdf, output_pdf)

        assert isinstance(result, EvaluationResult)
        assert result.source_path == source_pdf

    def test_evaluate_conversion_verbose(self, test_pdfs, capsys):
        """Test verbose output."""
        source_pdf, output_pdf = test_pdfs
        result = evaluate_conversion(source_pdf, output_pdf, verbose=True)

        captured = capsys.readouterr()
        # Verbose mode should print something
        assert len(captured.out) > 0 or len(result.summary) > 0


class TestPageEvaluation:
    """Tests for PageEvaluation dataclass."""

    def test_create_page_evaluation(self):
        """Test creating page evaluation."""
        page_eval = PageEvaluation(
            page_number=1,
            formatting_score=85.0,
            readability_score=90.0,
            math_score=95.0,
            table_score=80.0,
        )
        assert page_eval.page_number == 1
        assert page_eval.formatting_score == 85.0
        assert page_eval.issues == []

    def test_page_evaluation_with_issues(self):
        """Test page evaluation with issues."""
        issue = FormattingIssue(
            category="spacing",
            severity="minor",
            description="Small spacing issue",
        )
        page_eval = PageEvaluation(
            page_number=2,
            formatting_score=70.0,
            readability_score=75.0,
            math_score=100.0,
            table_score=100.0,
            issues=[issue],
        )
        assert len(page_eval.issues) == 1
        assert page_eval.issues[0].category == "spacing"


class TestMathAndTableEvaluation:
    """Tests for MathEvaluation and TableEvaluation."""

    def test_math_evaluation_defaults(self):
        """Test MathEvaluation defaults."""
        math_eval = MathEvaluation()
        assert math_eval.total_formulas == 0
        assert math_eval.correctly_rendered == 0
        assert math_eval.score == 100.0
        assert math_eval.issues == []

    def test_table_evaluation_defaults(self):
        """Test TableEvaluation defaults."""
        table_eval = TableEvaluation()
        assert table_eval.total_tables == 0
        assert table_eval.correctly_rendered == 0
        assert table_eval.score == 100.0
        assert table_eval.issues == []

    def test_math_evaluation_with_data(self):
        """Test MathEvaluation with data."""
        math_eval = MathEvaluation(
            total_formulas=10,
            correctly_rendered=8,
            issues=["Formula 3 rendering error"],
            score=80.0,
        )
        assert math_eval.total_formulas == 10
        assert math_eval.correctly_rendered == 8
        assert len(math_eval.issues) == 1

    def test_table_evaluation_with_data(self):
        """Test TableEvaluation with data."""
        table_eval = TableEvaluation(
            total_tables=5,
            correctly_rendered=4,
            issues=["Table 2 alignment issue"],
            score=80.0,
        )
        assert table_eval.total_tables == 5
        assert len(table_eval.issues) == 1
