"""
Tests for column detection and extraction in PDFs.

Tests cover:
- Single-column detection
- Two-column detection (IEEE, ACM format)
- Mixed layout handling (first page different)
- Text reordering for proper reading flow
- Integration with PDF parser
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from arxiv2rm.column_detector import (
    ColumnAwareExtractor,
    ColumnDetector,
    ColumnRegion,
    PageLayout,
    TextBlock,
)


class TestTextBlock:
    """Tests for TextBlock dataclass."""

    def test_text_block_properties(self):
        """Test computed properties of TextBlock."""
        block = TextBlock(x0=10, y0=20, x1=110, y1=70, text="Test")

        assert block.width == 100
        assert block.height == 50
        assert block.center_x == 60
        assert block.center_y == 45

    def test_text_block_with_font_info(self):
        """Test TextBlock with font metadata."""
        block = TextBlock(
            x0=0, y0=0, x1=100, y1=20, text="Bold Title", font_size=14.0, is_bold=True
        )

        assert block.font_size == 14.0
        assert block.is_bold is True


class TestColumnRegion:
    """Tests for ColumnRegion dataclass."""

    def test_column_region_properties(self):
        """Test computed properties of ColumnRegion."""
        region = ColumnRegion(x0=0, x1=300)

        assert region.width == 300
        assert region.center_x == 150

    def test_column_region_with_blocks(self):
        """Test ColumnRegion containing text blocks."""
        blocks = [
            TextBlock(x0=10, y0=10, x1=100, y1=30, text="Line 1"),
            TextBlock(x0=10, y0=40, x1=100, y1=60, text="Line 2"),
        ]
        region = ColumnRegion(x0=0, x1=120, blocks=blocks)

        assert len(region.blocks) == 2


class TestColumnDetector:
    """Tests for ColumnDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a ColumnDetector instance."""
        return ColumnDetector()

    def test_detector_initialization(self, detector):
        """Test default detector parameters."""
        assert detector.min_column_width_ratio == 0.25
        assert detector.gutter_threshold_ratio == 0.025
        assert detector.header_footer_margin_ratio == 0.1

    def test_custom_detector_parameters(self):
        """Test detector with custom parameters."""
        detector = ColumnDetector(
            min_column_width_ratio=0.3, gutter_threshold_ratio=0.08, header_footer_margin_ratio=0.15
        )

        assert detector.min_column_width_ratio == 0.3
        assert detector.gutter_threshold_ratio == 0.08
        assert detector.header_footer_margin_ratio == 0.15


class TestColumnDetectorWithMockPage:
    """Tests using mock PyMuPDF page objects."""

    @pytest.fixture
    def detector(self):
        return ColumnDetector()

    def _create_mock_page(self, width, height, blocks_data):
        """
        Create a mock fitz.Page with text blocks.

        Args:
            width: Page width
            height: Page height
            blocks_data: List of (x0, y0, x1, y1, text) tuples
        """
        page = MagicMock()
        page.rect = MagicMock()
        page.rect.width = width
        page.rect.height = height
        page.number = 0

        # Create mock text blocks
        blocks = []
        for x0, y0, x1, y1, text in blocks_data:
            block = {
                "type": 0,  # Text block
                "bbox": (x0, y0, x1, y1),
                "lines": [{"spans": [{"text": text, "size": 10.0, "font": "Times"}]}],
            }
            blocks.append(block)

        page.get_text.return_value = {"blocks": blocks}
        return page

    def test_detect_single_column(self, detector):
        """Test detection of single-column layout."""
        # Create page with single-column content
        # All blocks span from left (50) to right (550) of a 600px page
        blocks_data = [
            (50, 100, 550, 150, "Title"),
            (50, 200, 550, 300, "Paragraph 1"),
            (50, 350, 550, 450, "Paragraph 2"),
            (50, 500, 550, 600, "Paragraph 3"),
        ]
        page = self._create_mock_page(600, 800, blocks_data)

        layout = detector.detect_layout(page)

        assert layout.column_count == 1
        assert layout.page_num == 1

    def test_detect_two_columns(self, detector):
        """Test detection of two-column layout."""
        # Create page with two-column content
        # Left column: x=50-280, Right column: x=320-550
        # Gap (gutter) at x=280-320
        blocks_data = [
            # Left column
            (50, 100, 280, 200, "Left paragraph 1"),
            (50, 220, 280, 320, "Left paragraph 2"),
            (50, 340, 280, 440, "Left paragraph 3"),
            # Right column
            (320, 100, 550, 200, "Right paragraph 1"),
            (320, 220, 550, 320, "Right paragraph 2"),
            (320, 340, 550, 440, "Right paragraph 3"),
        ]
        page = self._create_mock_page(600, 800, blocks_data)

        layout = detector.detect_layout(page)

        assert layout.column_count == 2

    def test_detect_full_width_header(self, detector):
        """Test detection of full-width header (title)."""
        # Page with full-width title at top, then two columns
        blocks_data = [
            # Full-width header (in top 10% = 0-80px)
            (50, 20, 550, 60, "Paper Title - Full Width Header"),
            # Left column (after header)
            (50, 150, 280, 250, "Left column text"),
            # Right column
            (320, 150, 550, 250, "Right column text"),
        ]
        page = self._create_mock_page(600, 800, blocks_data)

        layout = detector.detect_layout(page)

        assert layout.has_full_width_header is True

    def test_detect_full_width_footer(self, detector):
        """Test detection of full-width footer (references section)."""
        # Page with two columns and full-width footer
        # Footer must span >60% of page width to be considered "full-width"
        blocks_data = [
            # Left column
            (50, 100, 280, 200, "Left text"),
            # Right column
            (320, 100, 550, 200, "Right text"),
            # Full-width footer (in bottom 10% = 720-800px)
            # Spans 400px = 67% of 600px page width
            (50, 750, 450, 780, "References: [1] Author et al."),
        ]
        page = self._create_mock_page(600, 800, blocks_data)

        layout = detector.detect_layout(page)

        assert layout.has_full_width_footer is True

    def test_empty_page(self, detector):
        """Test handling of empty page."""
        page = self._create_mock_page(600, 800, [])

        layout = detector.detect_layout(page)

        assert layout.column_count == 1
        assert layout.confidence == 0.0


class TestColumnAwareExtractor:
    """Tests for ColumnAwareExtractor class."""

    @pytest.fixture
    def extractor(self):
        return ColumnAwareExtractor()

    def test_extractor_initialization(self, extractor):
        """Test extractor has a detector."""
        assert extractor.detector is not None
        assert isinstance(extractor.detector, ColumnDetector)


class TestTextReordering:
    """Tests for text reordering in proper reading order."""

    def test_reorder_two_column_text(self):
        """Test that text is reordered: header -> left col -> right col -> footer."""
        extractor = ColumnAwareExtractor()

        # Create a mock layout
        header_blocks = [TextBlock(50, 20, 550, 60, "Title")]
        left_blocks = [
            TextBlock(50, 100, 280, 150, "Left 1"),
            TextBlock(50, 160, 280, 210, "Left 2"),
        ]
        right_blocks = [
            TextBlock(320, 100, 550, 150, "Right 1"),
            TextBlock(320, 160, 550, 210, "Right 2"),
        ]
        footer_blocks = [TextBlock(250, 750, 350, 780, "Page 1")]

        layout = PageLayout(
            page_num=1,
            width=600,
            height=800,
            column_count=2,
            columns=[
                ColumnRegion(x0=50, x1=280, blocks=left_blocks),
                ColumnRegion(x0=320, x1=550, blocks=right_blocks),
            ],
            confidence=0.9,
            has_full_width_header=True,
            has_full_width_footer=True,
            header_blocks=header_blocks,
            footer_blocks=footer_blocks,
        )

        text = extractor._reorder_text(layout)

        # Verify order: Title, Left 1, Left 2, Right 1, Right 2, Page 1
        lines = text.split("\n\n")
        assert lines[0] == "Title"
        assert lines[1] == "Left 1"
        assert lines[2] == "Left 2"
        assert lines[3] == "Right 1"
        assert lines[4] == "Right 2"
        assert lines[5] == "Page 1"


class TestGapDetection:
    """Tests for gap (gutter) detection between columns."""

    @pytest.fixture
    def detector(self):
        return ColumnDetector()

    def test_find_gaps_with_clear_gutter(self, detector):
        """Test finding gaps between column regions."""
        blocks = [
            TextBlock(50, 100, 280, 200, "Left"),
            TextBlock(320, 100, 550, 200, "Right"),
        ]

        gaps = detector._find_gaps(blocks, page_width=600, min_gap_width=30)

        assert len(gaps) == 1
        assert gaps[0][0] == 280  # Gap starts at right edge of left block
        assert gaps[0][1] == 320  # Gap ends at left edge of right block

    def test_no_gaps_in_single_column(self, detector):
        """Test no gaps found in single-column layout."""
        blocks = [
            TextBlock(50, 100, 550, 200, "Full width"),
            TextBlock(50, 220, 550, 320, "Full width 2"),
        ]

        gaps = detector._find_gaps(blocks, page_width=600, min_gap_width=30)

        assert len(gaps) == 0

    def test_small_gaps_ignored(self, detector):
        """Test that small gaps are ignored."""
        # Gap of only 20px (below 30px threshold)
        blocks = [
            TextBlock(50, 100, 280, 200, "Left"),
            TextBlock(300, 100, 550, 200, "Right"),  # 20px gap
        ]

        gaps = detector._find_gaps(blocks, page_width=600, min_gap_width=30)

        assert len(gaps) == 0


class TestIntegrationWithPDFParser:
    """Integration tests with PDF parser."""

    def test_pdf_parser_imports_column_detector(self):
        """Test that PDF parser can import column detector."""
        from arxiv2rm.pdf_parser import PDFParser

        parser = PDFParser(detect_columns=True)
        assert parser.column_extractor is not None
        assert parser.column_detector is not None

    def test_pdf_parser_without_column_detection(self):
        """Test PDF parser with column detection disabled."""
        from arxiv2rm.pdf_parser import PDFParser

        parser = PDFParser(detect_columns=False)
        assert parser.column_extractor is None
        assert parser.column_detector is None


class TestConfidenceScoring:
    """Tests for confidence scoring of column detection."""

    @pytest.fixture
    def detector(self):
        return ColumnDetector()

    def test_high_confidence_for_clear_columns(self, detector):
        """Test high confidence for clearly separated columns."""
        # Well-aligned blocks with similar column widths
        left_blocks = [
            TextBlock(50, 100, 280, 150, "L1"),
            TextBlock(50, 160, 280, 210, "L2"),
            TextBlock(50, 220, 280, 270, "L3"),
        ]
        right_blocks = [
            TextBlock(320, 100, 550, 150, "R1"),
            TextBlock(320, 160, 550, 210, "R2"),
            TextBlock(320, 220, 550, 270, "R3"),
        ]

        columns = [
            ColumnRegion(x0=50, x1=280, blocks=left_blocks),
            ColumnRegion(x0=320, x1=550, blocks=right_blocks),
        ]

        confidence = detector._calculate_confidence(
            left_blocks + right_blocks, columns, page_width=600
        )

        assert confidence >= 0.7

    def test_single_column_high_confidence(self, detector):
        """Test high confidence for single column."""
        blocks = [TextBlock(50, 100, 550, 200, "Text")]
        columns = [ColumnRegion(x0=50, x1=550, blocks=blocks)]

        confidence = detector._calculate_confidence(blocks, columns, page_width=600)

        assert confidence == 0.9


class TestEdgeCases:
    """Tests for edge cases and unusual layouts."""

    @pytest.fixture
    def detector(self):
        return ColumnDetector()

    def test_overlapping_blocks(self, detector):
        """Test handling of overlapping text blocks."""
        blocks = [
            TextBlock(50, 100, 350, 200, "Overlapping 1"),
            TextBlock(250, 100, 550, 200, "Overlapping 2"),
        ]

        # Should merge overlapping intervals
        gaps = detector._find_gaps(blocks, page_width=600, min_gap_width=30)
        assert len(gaps) == 0

    def test_very_narrow_column(self, detector):
        """Test handling of very narrow columns."""
        # Column width less than min_column_width_ratio
        blocks = [
            TextBlock(50, 100, 100, 200, "Narrow"),  # Only 50px wide
            TextBlock(450, 100, 550, 200, "Normal"),
        ]

        columns, confidence = detector._detect_columns(blocks, page_width=600)

        # Should handle gracefully
        assert len(columns) >= 1


# Marker for tests requiring actual PDF files
@pytest.mark.integration
class TestWithRealPDF:
    """Integration tests with real PDF files (requires test fixtures)."""

    @pytest.fixture
    def sample_pdf_dir(self):
        """Get path to sample PDFs directory."""
        return Path(__file__).parent / "fixtures" / "pdfs"

    def test_ieee_two_column_paper(self, sample_pdf_dir):
        """Test with IEEE format two-column paper."""
        pdf_path = sample_pdf_dir / "ieee_sample.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample IEEE PDF not available")

        extractor = ColumnAwareExtractor()
        analysis = extractor.analyze_document(pdf_path)

        assert analysis["dominant_layout"] == 2
        assert analysis["is_two_column"] is True

    def test_single_column_paper(self, sample_pdf_dir):
        """Test with single-column paper."""
        pdf_path = sample_pdf_dir / "single_column.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample single-column PDF not available")

        extractor = ColumnAwareExtractor()
        analysis = extractor.analyze_document(pdf_path)

        assert analysis["dominant_layout"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
