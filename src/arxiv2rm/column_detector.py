"""
Column Layout Detector for PDF documents.

Detects and handles multi-column layouts common in scientific papers:
- Single column (standard documents)
- Two columns (IEEE, ACM papers)
- Three columns (rare, some conference papers)

Uses text block analysis to detect column boundaries and reorder
text for proper reading flow (left column first, then right column).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, stdev
from typing import List, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    """Represents a text block with position and content."""

    x0: float  # Left boundary
    y0: float  # Top boundary
    x1: float  # Right boundary
    y1: float  # Bottom boundary
    text: str
    font_size: float = 0.0
    is_bold: bool = False

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class ColumnRegion:
    """Represents a detected column region."""

    x0: float
    x1: float
    blocks: List[TextBlock] = field(default_factory=list)

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class PageLayout:
    """Layout analysis result for a single page."""

    page_num: int
    width: float
    height: float
    column_count: int
    columns: List[ColumnRegion]
    confidence: float  # 0.0 to 1.0
    has_full_width_header: bool = False
    has_full_width_footer: bool = False
    header_blocks: List[TextBlock] = field(default_factory=list)
    footer_blocks: List[TextBlock] = field(default_factory=list)


class ColumnDetector:
    """
    Detects column layouts in PDF pages.

    Algorithm:
    1. Extract all text blocks with positions
    2. Analyze x-coordinate distribution of block centers
    3. Detect gaps (gutters) between columns
    4. Classify as 1, 2, or 3 columns based on gap analysis
    5. Handle full-width headers/footers (title, abstract, page numbers)
    """

    def __init__(
        self,
        min_column_width_ratio: float = 0.25,
        gutter_threshold_ratio: float = 0.05,
        header_footer_margin_ratio: float = 0.1,
    ):
        """
        Initialize column detector.

        Args:
            min_column_width_ratio: Minimum column width as ratio of page width
            gutter_threshold_ratio: Minimum gutter width as ratio of page width
            header_footer_margin_ratio: Margin for header/footer detection
        """
        self.min_column_width_ratio = min_column_width_ratio
        self.gutter_threshold_ratio = gutter_threshold_ratio
        self.header_footer_margin_ratio = header_footer_margin_ratio

    def detect_layout(self, page: fitz.Page) -> PageLayout:
        """
        Detect column layout for a single page.

        Args:
            page: PyMuPDF page object

        Returns:
            PageLayout with detected columns and metadata
        """
        page_width = page.rect.width
        page_height = page.rect.height

        # Extract text blocks
        blocks = self._extract_text_blocks(page)

        if not blocks:
            # Empty page - assume single column
            return PageLayout(
                page_num=page.number + 1,
                width=page_width,
                height=page_height,
                column_count=1,
                columns=[ColumnRegion(x0=0, x1=page_width)],
                confidence=0.0,
            )

        # Separate header/footer blocks from body content
        header_margin = page_height * self.header_footer_margin_ratio
        footer_margin = page_height * (1 - self.header_footer_margin_ratio)

        header_blocks = [b for b in blocks if b.y1 < header_margin]
        footer_blocks = [b for b in blocks if b.y0 > footer_margin]
        body_blocks = [b for b in blocks if header_margin <= b.center_y <= footer_margin]

        # Detect columns from body blocks only
        columns, confidence = self._detect_columns(body_blocks, page_width)

        # Check for full-width header/footer
        has_full_width_header = self._has_full_width_content(header_blocks, page_width)
        has_full_width_footer = self._has_full_width_content(footer_blocks, page_width)

        return PageLayout(
            page_num=page.number + 1,
            width=page_width,
            height=page_height,
            column_count=len(columns),
            columns=columns,
            confidence=confidence,
            has_full_width_header=has_full_width_header,
            has_full_width_footer=has_full_width_footer,
            header_blocks=header_blocks,
            footer_blocks=footer_blocks,
        )

    def _extract_text_blocks(self, page: fitz.Page) -> List[TextBlock]:
        """Extract text blocks with position and font information."""
        blocks = []
        dict_data = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in dict_data.get("blocks", []):
            if block.get("type") != 0:  # Skip non-text blocks (images)
                continue

            bbox = block.get("bbox", (0, 0, 0, 0))
            text_parts = []
            font_sizes = []
            has_bold = False

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text_parts.append(span.get("text", ""))
                    font_sizes.append(span.get("size", 0))
                    if "bold" in span.get("font", "").lower():
                        has_bold = True

            text = " ".join(text_parts).strip()
            if not text:
                continue

            avg_font_size = mean(font_sizes) if font_sizes else 0

            blocks.append(
                TextBlock(
                    x0=bbox[0],
                    y0=bbox[1],
                    x1=bbox[2],
                    y1=bbox[3],
                    text=text,
                    font_size=avg_font_size,
                    is_bold=has_bold,
                )
            )

        return blocks

    def _detect_columns(
        self, blocks: List[TextBlock], page_width: float
    ) -> Tuple[List[ColumnRegion], float]:
        """
        Detect column boundaries from text blocks.

        Returns:
            Tuple of (columns, confidence)
        """
        if not blocks:
            return [ColumnRegion(x0=0, x1=page_width)], 0.0

        # Get x-coordinates of block boundaries
        left_edges = sorted([b.x0 for b in blocks])
        right_edges = sorted([b.x1 for b in blocks])

        # Find potential column boundaries using gap analysis
        min_gutter_width = page_width * self.gutter_threshold_ratio

        # Analyze gaps in the middle region of the page
        mid_region_start = page_width * 0.2
        mid_region_end = page_width * 0.8

        # Find significant gaps (potential gutters)
        gaps = self._find_gaps(blocks, page_width, min_gutter_width)

        # Filter gaps to those in the middle region
        central_gaps = [g for g in gaps if mid_region_start < g[0] < mid_region_end]

        if not central_gaps:
            # No significant gaps - single column
            columns = [
                ColumnRegion(
                    x0=min(left_edges),
                    x1=max(right_edges),
                    blocks=blocks,
                )
            ]
            confidence = self._calculate_confidence(blocks, columns, page_width)
            return columns, confidence

        # Sort gaps by position
        central_gaps.sort(key=lambda g: g[0])

        if len(central_gaps) == 1:
            # Two columns
            gap_start, gap_end = central_gaps[0]
            gap_center = (gap_start + gap_end) / 2

            left_blocks = [b for b in blocks if b.center_x < gap_center]
            right_blocks = [b for b in blocks if b.center_x >= gap_center]

            columns = [
                ColumnRegion(
                    x0=min([b.x0 for b in left_blocks]) if left_blocks else 0,
                    x1=gap_start,
                    blocks=left_blocks,
                ),
                ColumnRegion(
                    x0=gap_end,
                    x1=max([b.x1 for b in right_blocks]) if right_blocks else page_width,
                    blocks=right_blocks,
                ),
            ]
        elif len(central_gaps) >= 2:
            # Three or more columns - use first two gaps
            gap1_start, gap1_end = central_gaps[0]
            gap2_start, gap2_end = central_gaps[1]

            gap1_center = (gap1_start + gap1_end) / 2
            gap2_center = (gap2_start + gap2_end) / 2

            left_blocks = [b for b in blocks if b.center_x < gap1_center]
            middle_blocks = [b for b in blocks if gap1_center <= b.center_x < gap2_center]
            right_blocks = [b for b in blocks if b.center_x >= gap2_center]

            columns = [
                ColumnRegion(
                    x0=min([b.x0 for b in left_blocks]) if left_blocks else 0,
                    x1=gap1_start,
                    blocks=left_blocks,
                ),
                ColumnRegion(
                    x0=gap1_end,
                    x1=gap2_start,
                    blocks=middle_blocks,
                ),
                ColumnRegion(
                    x0=gap2_end,
                    x1=max([b.x1 for b in right_blocks]) if right_blocks else page_width,
                    blocks=right_blocks,
                ),
            ]
        else:
            # Fallback to single column
            columns = [ColumnRegion(x0=min(left_edges), x1=max(right_edges), blocks=blocks)]

        # Filter out empty columns
        columns = [c for c in columns if c.blocks]

        if not columns:
            columns = [ColumnRegion(x0=0, x1=page_width, blocks=blocks)]

        confidence = self._calculate_confidence(blocks, columns, page_width)
        return columns, confidence

    def _find_gaps(
        self, blocks: List[TextBlock], page_width: float, min_gap_width: float
    ) -> List[Tuple[float, float]]:
        """
        Find significant horizontal gaps between text blocks.

        Returns:
            List of (gap_start, gap_end) tuples
        """
        if not blocks:
            return []

        # Create coverage map using intervals
        intervals = [(b.x0, b.x1) for b in blocks]
        intervals.sort()

        # Merge overlapping intervals
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        # Find gaps between merged intervals
        gaps = []
        for i in range(len(merged) - 1):
            gap_start = merged[i][1]
            gap_end = merged[i + 1][0]
            gap_width = gap_end - gap_start

            if gap_width >= min_gap_width:
                gaps.append((gap_start, gap_end))

        return gaps

    def _has_full_width_content(self, blocks: List[TextBlock], page_width: float) -> bool:
        """Check if blocks span most of the page width (full-width header/footer)."""
        if not blocks:
            return False

        # Check if any block spans >60% of page width
        for block in blocks:
            if block.width > page_width * 0.6:
                return True

        return False

    def _calculate_confidence(
        self, blocks: List[TextBlock], columns: List[ColumnRegion], page_width: float
    ) -> float:
        """
        Calculate confidence score for column detection.

        Higher confidence when:
        - Columns have similar widths
        - Blocks align well within columns
        - Clear separation between columns
        """
        if len(columns) <= 1:
            return 0.9  # High confidence for single column

        # Check column width consistency
        widths = [c.width for c in columns]
        if len(widths) > 1 and stdev(widths) < mean(widths) * 0.3:
            width_score = 0.9
        else:
            width_score = 0.6

        # Check block alignment within columns
        alignment_scores = []
        for column in columns:
            if not column.blocks:
                continue
            left_edges = [b.x0 for b in column.blocks]
            if len(left_edges) > 1:
                edge_variance = stdev(left_edges)
                alignment_scores.append(1.0 if edge_variance < page_width * 0.05 else 0.7)

        alignment_score = mean(alignment_scores) if alignment_scores else 0.5

        # Combined confidence
        return (width_score + alignment_score) / 2


class ColumnAwareExtractor:
    """
    Extracts text from PDFs respecting column layout.

    Reorders text blocks to follow reading order:
    1. Full-width header (title, abstract)
    2. Left column (top to bottom)
    3. Right column (top to bottom)
    4. Full-width footer (references, page numbers)
    """

    def __init__(self):
        self.detector = ColumnDetector()

    def extract_text(self, pdf_path: Path) -> List[dict]:
        """
        Extract text from PDF with column-aware ordering.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of page dicts with:
            - page_num: Page number (1-indexed)
            - text: Reordered text content
            - layout: PageLayout metadata
            - column_count: Number of detected columns
        """
        logger.info(f"Extracting text with column detection: {pdf_path}")

        doc = fitz.open(pdf_path)
        pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            layout = self.detector.detect_layout(page)

            # Reorder text based on detected layout
            ordered_text = self._reorder_text(layout)

            pages.append(
                {
                    "page_num": page_num + 1,
                    "text": ordered_text,
                    "layout": layout,
                    "column_count": layout.column_count,
                    "confidence": layout.confidence,
                }
            )

            logger.debug(
                f"Page {page_num + 1}: {layout.column_count} columns "
                f"(confidence: {layout.confidence:.2f})"
            )

        doc.close()

        # Log summary
        column_counts = [p["column_count"] for p in pages]
        avg_columns = mean(column_counts) if column_counts else 1
        logger.info(
            f"Extracted {len(pages)} pages, "
            f"avg columns: {avg_columns:.1f}, "
            f"2-column pages: {sum(1 for c in column_counts if c == 2)}"
        )

        return pages

    def _reorder_text(self, layout: PageLayout) -> str:
        """
        Reorder text blocks for proper reading order.

        Order:
        1. Header blocks (full-width, top)
        2. Column blocks (left to right, top to bottom within each)
        3. Footer blocks (full-width, bottom)
        """
        text_parts = []

        # 1. Header (full-width content at top)
        if layout.header_blocks:
            header_sorted = sorted(layout.header_blocks, key=lambda b: (b.y0, b.x0))
            for block in header_sorted:
                text_parts.append(block.text)

        # 2. Body columns (left to right)
        for column in layout.columns:
            # Sort blocks within column by y-position (top to bottom)
            column_sorted = sorted(column.blocks, key=lambda b: (b.y0, b.x0))
            for block in column_sorted:
                text_parts.append(block.text)

        # 3. Footer (full-width content at bottom)
        if layout.footer_blocks:
            footer_sorted = sorted(layout.footer_blocks, key=lambda b: (b.y0, b.x0))
            for block in footer_sorted:
                text_parts.append(block.text)

        return "\n\n".join(text_parts)

    def analyze_document(self, pdf_path: Path) -> dict:
        """
        Analyze entire document for column layout patterns.

        Returns:
            Dict with:
            - dominant_layout: Most common column count
            - pages_by_layout: Count of pages per column count
            - mixed_layout: True if document has varying layouts
            - first_page_special: True if first page differs (title page)
        """
        doc = fitz.open(pdf_path)
        layouts = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            layout = self.detector.detect_layout(page)
            layouts.append(layout.column_count)

        doc.close()

        if not layouts:
            return {
                "dominant_layout": 1,
                "pages_by_layout": {1: 0},
                "mixed_layout": False,
                "first_page_special": False,
            }

        # Count pages by column count
        pages_by_layout = {}
        for count in layouts:
            pages_by_layout[count] = pages_by_layout.get(count, 0) + 1

        # Find dominant layout (most common)
        dominant_layout = max(pages_by_layout, key=pages_by_layout.get)

        # Check if first page is different (common for title pages)
        first_page_special = len(layouts) > 1 and layouts[0] != dominant_layout

        # Check for mixed layouts
        mixed_layout = len(pages_by_layout) > 1

        return {
            "dominant_layout": dominant_layout,
            "pages_by_layout": pages_by_layout,
            "mixed_layout": mixed_layout,
            "first_page_special": first_page_special,
        }


# Convenience function
def extract_columns_from_pdf(pdf_path: Path) -> List[dict]:
    """
    Extract text from PDF with automatic column detection.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of page dicts with reordered text
    """
    extractor = ColumnAwareExtractor()
    return extractor.extract_text(pdf_path)


# Example usage
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1])
        if pdf_path.exists():
            extractor = ColumnAwareExtractor()

            # Analyze document
            analysis = extractor.analyze_document(pdf_path)
            print("\nDocument Analysis:")
            print(f"  Dominant layout: {analysis['dominant_layout']} column(s)")
            print(f"  Pages by layout: {analysis['pages_by_layout']}")
            print(f"  Mixed layout: {analysis['mixed_layout']}")
            print(f"  First page special: {analysis['first_page_special']}")

            # Extract text
            pages = extractor.extract_text(pdf_path)
            print(f"\nExtracted {len(pages)} pages")

            # Show first page preview
            if pages:
                print("\n--- Page 1 Preview ---")
                print(pages[0]["text"][:500])
                print("...")
        else:
            print(f"File not found: {pdf_path}")
    else:
        print("Usage: python column_detector.py <pdf_path>")
