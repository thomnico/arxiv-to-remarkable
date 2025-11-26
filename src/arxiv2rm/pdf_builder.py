"""
PDF Builder for reMarkable e-ink tablets.

Generates optimized PDF output with:
- OpenDyslexic font for enhanced readability
- Configurable font size (12-18pt)
- Page size optimized for reMarkable 1 (1404x1872px)
- Formula images preserved from source PDF
- Proper text flow with glyph-level spacing control

See ADR-002 for rationale: EPUB output had critical rendering issues
on reMarkable (blank pages, missing word spaces).
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

logger = logging.getLogger(__name__)


# reMarkable 1 display specifications
# 10.3" E Ink display, 1872×1404 pixels (portrait), 226 DPI
REMARKABLE_WIDTH_PX = 1404
REMARKABLE_HEIGHT_PX = 1872
REMARKABLE_DPI = 226

# Convert pixels to points (72 points per inch)
REMARKABLE_WIDTH_PT = REMARKABLE_WIDTH_PX * 72 / REMARKABLE_DPI  # ~447 points
REMARKABLE_HEIGHT_PT = REMARKABLE_HEIGHT_PX * 72 / REMARKABLE_DPI  # ~596 points

# Page size tuple for reportlab
REMARKABLE_PAGE_SIZE = (REMARKABLE_WIDTH_PT, REMARKABLE_HEIGHT_PT)


@dataclass
class PDFBuilderConfig:
    """Configuration for PDF generation."""

    # Page dimensions (reMarkable 1 optimized)
    page_width: float = REMARKABLE_WIDTH_PT
    page_height: float = REMARKABLE_HEIGHT_PT

    # Margins (1 inch = 72 points for annotation space)
    margin_top: float = 54  # 0.75 inch
    margin_bottom: float = 54
    margin_left: float = 54
    margin_right: float = 54

    # Typography
    font_size: int = 14  # Default, options: 12, 14, 16, 18
    line_height_ratio: float = 1.5  # Line height as ratio of font size
    paragraph_spacing: float = 6  # Space between paragraphs in points

    # Font family
    font_family: str = "OpenDyslexic"
    use_opendyslexic: bool = True

    # Image handling
    max_image_width_ratio: float = 0.9  # Max 90% of content width
    image_quality: int = 85


@dataclass
class PDFMetadata:
    """PDF document metadata."""

    title: str = "Untitled Document"
    author: str = ""
    subject: str = ""
    keywords: List[str] = field(default_factory=list)
    creator: str = "arxiv2rm"


class PDFBuilder:
    """
    Builds optimized PDF files for reMarkable e-ink display.

    Uses reportlab for PDF generation with:
    - OpenDyslexic font embedding
    - Configurable font size
    - reMarkable-optimized page dimensions
    - Formula images from source PDF
    """

    def __init__(
        self,
        config: Optional[PDFBuilderConfig] = None,
        metadata: Optional[PDFMetadata] = None,
    ):
        """
        Initialize PDF builder.

        Args:
            config: PDF generation configuration
            metadata: Document metadata
        """
        self.config = config or PDFBuilderConfig()
        self.metadata = metadata or PDFMetadata()

        # Content storage
        self.content: List[Tuple[str, any]] = []  # (type, content) pairs

        # Font registration
        self._fonts_registered = False
        self._register_fonts()

        # Create styles
        self._styles = self._create_styles()

    def _register_fonts(self):
        """Register OpenDyslexic fonts with reportlab."""
        if self._fonts_registered:
            return

        # Find font directory
        fonts_dir = Path(__file__).parent / "fonts"

        if not fonts_dir.exists():
            logger.warning(f"Fonts directory not found: {fonts_dir}")
            self.config.use_opendyslexic = False
            return

        try:
            # Register each font variant
            font_files = {
                "OpenDyslexic": "OpenDyslexic-Regular.otf",
                "OpenDyslexic-Bold": "OpenDyslexic-Bold.otf",
                "OpenDyslexic-Italic": "OpenDyslexic-Italic.otf",
                "OpenDyslexic-BoldItalic": "OpenDyslexic-BoldItalic.otf",
            }

            for font_name, font_file in font_files.items():
                font_path = fonts_dir / font_file
                if font_path.exists():
                    pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                    logger.debug(f"Registered font: {font_name}")
                else:
                    logger.warning(f"Font file not found: {font_path}")

            # Register font family for bold/italic mapping
            pdfmetrics.registerFontFamily(
                "OpenDyslexic",
                normal="OpenDyslexic",
                bold="OpenDyslexic-Bold",
                italic="OpenDyslexic-Italic",
                boldItalic="OpenDyslexic-BoldItalic",
            )

            self._fonts_registered = True
            logger.info("OpenDyslexic fonts registered successfully")

        except Exception as e:
            logger.warning(f"Failed to register OpenDyslexic fonts: {e}")
            self.config.use_opendyslexic = False

    def _create_styles(self) -> Dict[str, ParagraphStyle]:
        """Create paragraph styles for the document."""
        base_font = "OpenDyslexic" if self.config.use_opendyslexic else "Helvetica"
        font_size = self.config.font_size
        line_height = font_size * self.config.line_height_ratio

        styles = {}

        # Normal paragraph
        styles["Normal"] = ParagraphStyle(
            name="Normal",
            fontName=base_font,
            fontSize=font_size,
            leading=line_height,
            spaceBefore=0,
            spaceAfter=self.config.paragraph_spacing,
            alignment=0,  # Left aligned
        )

        # Title
        styles["Title"] = ParagraphStyle(
            name="Title",
            fontName=f"{base_font}-Bold" if self.config.use_opendyslexic else "Helvetica-Bold",
            fontSize=font_size + 8,
            leading=(font_size + 8) * 1.3,
            spaceBefore=0,
            spaceAfter=12,
            alignment=1,  # Center
        )

        # Headings
        styles["Heading1"] = ParagraphStyle(
            name="Heading1",
            fontName=f"{base_font}-Bold" if self.config.use_opendyslexic else "Helvetica-Bold",
            fontSize=font_size + 4,
            leading=(font_size + 4) * 1.3,
            spaceBefore=18,
            spaceAfter=8,
            keepWithNext=True,
        )

        styles["Heading2"] = ParagraphStyle(
            name="Heading2",
            fontName=f"{base_font}-Bold" if self.config.use_opendyslexic else "Helvetica-Bold",
            fontSize=font_size + 2,
            leading=(font_size + 2) * 1.3,
            spaceBefore=14,
            spaceAfter=6,
            keepWithNext=True,
        )

        styles["Heading3"] = ParagraphStyle(
            name="Heading3",
            fontName=f"{base_font}-Bold" if self.config.use_opendyslexic else "Helvetica-Bold",
            fontSize=font_size,
            leading=font_size * 1.3,
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        )

        # Abstract
        styles["Abstract"] = ParagraphStyle(
            name="Abstract",
            fontName=f"{base_font}-Italic" if self.config.use_opendyslexic else "Helvetica-Oblique",
            fontSize=font_size - 1,
            leading=(font_size - 1) * self.config.line_height_ratio,
            spaceBefore=6,
            spaceAfter=6,
            leftIndent=20,
            rightIndent=20,
        )

        # Caption
        styles["Caption"] = ParagraphStyle(
            name="Caption",
            fontName=f"{base_font}-Italic" if self.config.use_opendyslexic else "Helvetica-Oblique",
            fontSize=font_size - 2,
            leading=(font_size - 2) * 1.4,
            spaceBefore=4,
            spaceAfter=8,
            alignment=1,  # Center
        )

        return styles

    def set_metadata(
        self,
        title: Optional[str] = None,
        author: Optional[str] = None,
        subject: Optional[str] = None,
        keywords: Optional[List[str]] = None,
    ):
        """Set document metadata."""
        if title:
            self.metadata.title = title
        if author:
            self.metadata.author = author
        if subject:
            self.metadata.subject = subject
        if keywords:
            self.metadata.keywords = keywords

    def add_title(self, title: str):
        """Add document title."""
        self.content.append(("title", title))

    def add_heading(self, text: str, level: int = 1):
        """
        Add a heading.

        Args:
            text: Heading text
            level: Heading level (1-3)
        """
        self.content.append(("heading", (text, level)))

    def add_paragraph(self, text: str, style: str = "Normal"):
        """
        Add a paragraph of text.

        Args:
            text: Paragraph text
            style: Style name to apply
        """
        # Clean text for PDF
        text = self._clean_text(text)
        if text.strip():
            self.content.append(("paragraph", (text, style)))

    def add_abstract(self, text: str):
        """Add abstract section."""
        self.content.append(("paragraph", (text, "Abstract")))

    def add_image(
        self,
        image_path: Path,
        caption: Optional[str] = None,
        max_width: Optional[float] = None,
    ):
        """
        Add an image.

        Args:
            image_path: Path to image file
            caption: Optional caption text
            max_width: Maximum width in points (default: content width * 0.9)
        """
        self.content.append(("image", (image_path, caption, max_width)))

    def add_formula_image(self, image_path: Path, caption: Optional[str] = None):
        """
        Add a formula image extracted from source PDF.

        Args:
            image_path: Path to formula image
            caption: Optional caption
        """
        self.content.append(("formula", (image_path, caption)))

    def add_spacer(self, height: float = 12):
        """Add vertical space."""
        self.content.append(("spacer", height))

    def _clean_text(self, text: str) -> str:
        """
        Clean text for PDF rendering.

        - Normalize whitespace
        - Handle special characters
        - Escape XML entities for reportlab
        """
        if not text:
            return ""

        # Normalize whitespace (preserve single spaces)
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        # Escape XML entities (reportlab uses XML-style markup)
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")

        return text

    def _detect_heading_level(self, text: str) -> Optional[int]:
        """Detect if text is a heading and its level."""
        text = text.strip()

        # Section patterns
        if re.match(r"^\d+\.\s+[A-Z]", text):  # "1. Introduction"
            return 1
        if re.match(r"^\d+\.\d+\s+[A-Z]", text):  # "1.1 Background"
            return 2
        if re.match(r"^\d+\.\d+\.\d+\s+[A-Z]", text):  # "1.1.1 Details"
            return 3

        # Keywords
        heading_keywords = [
            "abstract",
            "introduction",
            "background",
            "methods",
            "methodology",
            "results",
            "discussion",
            "conclusion",
            "conclusions",
            "references",
            "acknowledgments",
            "acknowledgements",
            "appendix",
        ]
        if text.lower() in heading_keywords:
            return 1

        return None

    def _build_flowables(self) -> List:
        """Convert content to reportlab flowables."""
        flowables = []

        # Calculate content width
        content_width = self.config.page_width - self.config.margin_left - self.config.margin_right

        for content_type, content_data in self.content:
            if content_type == "title":
                p = Paragraph(content_data, self._styles["Title"])
                flowables.append(p)

            elif content_type == "heading":
                text, level = content_data
                style_name = f"Heading{min(level, 3)}"
                p = Paragraph(text, self._styles[style_name])
                flowables.append(p)

            elif content_type == "paragraph":
                text, style_name = content_data
                style = self._styles.get(style_name, self._styles["Normal"])
                p = Paragraph(text, style)
                flowables.append(p)

            elif content_type == "image":
                image_path, caption, max_width = content_data
                img = self._create_image_flowable(image_path, content_width, max_width)
                if img:
                    flowables.append(img)
                    if caption:
                        cap = Paragraph(caption, self._styles["Caption"])
                        flowables.append(cap)

            elif content_type == "formula":
                image_path, caption = content_data
                # Formula images should be centered and not too large
                img = self._create_image_flowable(
                    image_path,
                    content_width,
                    max_width=content_width * 0.8,
                )
                if img:
                    flowables.append(Spacer(1, 6))
                    flowables.append(img)
                    if caption:
                        cap = Paragraph(caption, self._styles["Caption"])
                        flowables.append(cap)
                    flowables.append(Spacer(1, 6))

            elif content_type == "spacer":
                flowables.append(Spacer(1, content_data))

        return flowables

    def _create_image_flowable(
        self,
        image_path: Path,
        content_width: float,
        max_width: Optional[float] = None,
    ) -> Optional[RLImage]:
        """
        Create a reportlab Image flowable.

        Args:
            image_path: Path to image file
            content_width: Available content width
            max_width: Maximum width constraint

        Returns:
            RLImage flowable or None if image can't be loaded
        """
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                logger.warning(f"Image not found: {image_path}")
                return None

            # Get image dimensions
            with Image.open(image_path) as img:
                orig_width, orig_height = img.size

            # Calculate display size
            if max_width is None:
                max_width = content_width * self.config.max_image_width_ratio

            # Scale to fit within max_width while maintaining aspect ratio
            scale = min(1.0, max_width / orig_width)
            display_width = orig_width * scale
            display_height = orig_height * scale

            # Also constrain height to reasonable max (half page height)
            max_height = (
                self.config.page_height - self.config.margin_top - self.config.margin_bottom
            ) * 0.5
            if display_height > max_height:
                scale = max_height / display_height
                display_width *= scale
                display_height = max_height

            return RLImage(
                str(image_path),
                width=display_width,
                height=display_height,
                hAlign="CENTER",
            )

        except Exception as e:
            logger.warning(f"Failed to create image flowable: {e}")
            return None

    def build(self, output_path: Path) -> Path:
        """
        Build the PDF document.

        Args:
            output_path: Path to save the PDF

        Returns:
            Path to the generated PDF
        """
        output_path = Path(output_path)

        # Create document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=(self.config.page_width, self.config.page_height),
            topMargin=self.config.margin_top,
            bottomMargin=self.config.margin_bottom,
            leftMargin=self.config.margin_left,
            rightMargin=self.config.margin_right,
            title=self.metadata.title,
            author=self.metadata.author,
            subject=self.metadata.subject,
            creator=self.metadata.creator,
        )

        # Build flowables
        flowables = self._build_flowables()

        if not flowables:
            logger.warning("No content to build PDF")
            # Create empty document with just a title
            flowables = [Paragraph("Empty Document", self._styles["Title"])]

        # Build PDF
        doc.build(flowables)

        logger.info(f"PDF built: {output_path}")
        return output_path


def convert_pdf_to_remarkable(
    input_path: Path,
    output_path: Optional[Path] = None,
    font_size: int = 14,
    extract_formulas: bool = True,
) -> Path:
    """
    Convert a PDF to reMarkable-optimized format.

    This is the main entry point for PDF-to-PDF conversion.

    Args:
        input_path: Path to source PDF
        output_path: Path for output PDF (default: input_remarkable.pdf)
        font_size: Font size (12, 14, 16, or 18)
        extract_formulas: Whether to extract formulas as images

    Returns:
        Path to the generated PDF
    """
    from .pdf_parser import PDFParser

    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_stem(f"{input_path.stem}_remarkable")

    logger.info(f"Converting {input_path} to reMarkable format...")

    # Initialize parser and builder
    parser = PDFParser()
    config = PDFBuilderConfig(font_size=font_size)
    builder = PDFBuilder(config=config)

    # Create temp directory for formula images
    import tempfile

    temp_dir = Path(tempfile.mkdtemp(prefix="arxiv2rm_"))

    try:
        # Extract formula images if requested
        formula_regions = []
        if extract_formulas:
            logger.info("Extracting formula images...")
            formula_regions = parser.extract_matrix_formulas(input_path, temp_dir)
            logger.info(f"Extracted {len(formula_regions)} formula images")

        # Parse PDF with formula exclusions
        logger.info("Parsing PDF content...")
        result = parser.parse(
            input_path,
            output_dir=temp_dir,
            exclude_regions=formula_regions if formula_regions else None,
        )

        # Extract metadata
        analysis = result.get("analysis", {})
        metadata = analysis.get("metadata", {})
        builder.set_metadata(
            title=metadata.get("title", input_path.stem),
            author=metadata.get("author", ""),
        )

        # Add title if found
        if metadata.get("title"):
            builder.add_title(metadata["title"])

        # Process pages
        pages = result.get("pages", [])
        for page_data in pages:
            text = page_data.get("text", "")

            # Check for formula placeholders and insert images
            if "[FORMULA_IMAGE:" in text:
                # Split text around formula placeholders
                parts = re.split(r"\[FORMULA_IMAGE:([^:]+):page\d+\]", text)
                for i, part in enumerate(parts):
                    if i % 2 == 0:
                        # Regular text
                        if part.strip():
                            _add_text_content(builder, part)
                    else:
                        # Formula image filename
                        formula_path = temp_dir / part
                        if formula_path.exists():
                            builder.add_formula_image(formula_path)
            else:
                # No formulas, add text directly
                if text.strip():
                    _add_text_content(builder, text)

        # Build output PDF
        output_path = builder.build(output_path)
        logger.info(f"Conversion complete: {output_path}")
        return output_path

    finally:
        # Cleanup temp directory
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def _add_text_content(builder: PDFBuilder, text: str):
    """
    Add text content to builder, detecting structure.

    Args:
        builder: PDFBuilder instance
        text: Text content to add
    """
    # Split into paragraphs
    paragraphs = re.split(r"\n\s*\n", text)

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Detect headings
        heading_level = builder._detect_heading_level(para)
        if heading_level:
            builder.add_heading(para, level=heading_level)
        else:
            # Regular paragraph
            builder.add_paragraph(para)


# CLI integration helper
def main():
    """Command-line interface for PDF conversion."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m arxiv2rm.pdf_builder <input.pdf> [output.pdf]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    logging.basicConfig(level=logging.INFO)
    convert_pdf_to_remarkable(input_path, output_path)


if __name__ == "__main__":
    main()
