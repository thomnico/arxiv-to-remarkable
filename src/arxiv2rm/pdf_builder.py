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
from reportlab.lib import colors
from reportlab.lib.colors import lightgrey
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import Flowable

logger = logging.getLogger(__name__)


class BookmarkFlowable(Flowable):
    """Invisible flowable that adds a bookmark at the current position."""

    def __init__(self, title: str, level: int = 0, key: str = None):
        Flowable.__init__(self)
        self.title = title
        self.level = level
        self.key = key or title.replace(" ", "_")[:30]
        self.width = 0
        self.height = 0

    def draw(self):
        self.canv.bookmarkPage(self.key)
        self.canv.addOutlineEntry(self.title, self.key, level=self.level)


class AnchorFlowable(Flowable):
    """Invisible flowable that creates a named destination for internal links."""

    def __init__(self, name: str):
        Flowable.__init__(self)
        self.name = name
        self.width = 0
        self.height = 0

    def draw(self):
        self.canv.bookmarkPage(self.name)


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

    # Typography - improved for readability
    font_size: int = 14  # Default, options: 12, 14, 16, 18
    line_height_ratio: float = 1.6  # Increased line height for better readability
    paragraph_spacing: float = 12  # Increased space between paragraphs

    # Font family
    font_family: str = "OpenDyslexic"
    use_opendyslexic: bool = True

    # Image handling
    max_image_width_ratio: float = 0.9  # Max 90% of content width
    image_quality: int = 85

    # Notes zone at bottom of each page
    notes_zone_enabled: bool = True
    notes_zone_height: float = 80  # Height in points (~1.1 inch)


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
            # Register each font variant (TTF for reportlab compatibility)
            font_files = {
                "OpenDyslexic": "OpenDyslexic-Regular.ttf",
                "OpenDyslexic-Bold": "OpenDyslexic-Bold.ttf",
                "OpenDyslexic-Italic": "OpenDyslexic-Italic.ttf",
                "OpenDyslexic-BoldItalic": "OpenDyslexic-BoldItalic.ttf",
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

        # Normal paragraph - improved spacing for readability
        styles["Normal"] = ParagraphStyle(
            name="Normal",
            fontName=base_font,
            fontSize=font_size,
            leading=line_height,
            spaceBefore=4,  # Small space before each paragraph
            spaceAfter=self.config.paragraph_spacing,
            alignment=0,  # Left aligned
            firstLineIndent=0,  # No indent for cleaner look
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

        # Headings - improved spacing for visual hierarchy
        styles["Heading1"] = ParagraphStyle(
            name="Heading1",
            fontName=f"{base_font}-Bold" if self.config.use_opendyslexic else "Helvetica-Bold",
            fontSize=font_size + 4,
            leading=(font_size + 4) * 1.4,
            spaceBefore=24,  # More space before major headings
            spaceAfter=12,
            keepWithNext=True,
        )

        styles["Heading2"] = ParagraphStyle(
            name="Heading2",
            fontName=f"{base_font}-Bold" if self.config.use_opendyslexic else "Helvetica-Bold",
            fontSize=font_size + 2,
            leading=(font_size + 2) * 1.4,
            spaceBefore=20,
            spaceAfter=10,
            keepWithNext=True,
        )

        styles["Heading3"] = ParagraphStyle(
            name="Heading3",
            fontName=f"{base_font}-Bold" if self.config.use_opendyslexic else "Helvetica-Bold",
            fontSize=font_size,
            leading=font_size * 1.4,
            spaceBefore=16,
            spaceAfter=8,
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

        # Footnote/notes style
        styles["Footnote"] = ParagraphStyle(
            name="Footnote",
            fontName=base_font,
            fontSize=font_size - 3,
            leading=(font_size - 3) * 1.3,
            spaceBefore=2,
            spaceAfter=2,
            leftIndent=10,
        )

        # Reference style - smaller font with hanging indent for numbered references
        styles["Reference"] = ParagraphStyle(
            name="Reference",
            fontName=base_font,
            fontSize=font_size - 3,  # Smaller than body text
            leading=(font_size - 3) * 1.3,
            spaceBefore=2,
            spaceAfter=4,
            leftIndent=20,  # Hanging indent
            firstLineIndent=-20,  # Pull first line back for number
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

    def add_title_page(self, title: str, author: Optional[str] = None):
        """
        Add a title page to the document.

        Args:
            title: Document title
            author: Optional author name(s)
        """
        self.content.append(("title_page", (title, author)))

    def add_heading(self, text: str, level: int = 1):
        """
        Add a heading.

        Args:
            text: Heading text
            level: Heading level (1-3)
        """
        self.content.append(("heading", (text, level)))

    def add_chapter(self, title: str, content: str):
        """
        Add a chapter with title and content.

        Args:
            title: Chapter title
            content: Chapter text content
        """
        # Add chapter heading
        self.add_heading(title, level=1)
        # Add content paragraphs
        if content:
            paragraphs = content.split("\n\n")
            for para in paragraphs:
                para = para.strip()
                if para:
                    self.add_paragraph(para)

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
        anchor: Optional[str] = None,
    ):
        """
        Add an image.

        Args:
            image_path: Path to image file
            caption: Optional caption text
            max_width: Maximum width in points (default: content width * 0.9)
            anchor: Optional anchor name for internal links (e.g., "fig:model-arch")
        """
        self.content.append(("image", (image_path, caption, max_width, anchor)))

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

    def add_footnote(self, text: str):
        """
        Add a footnote/note at the bottom of the page.

        Args:
            text: Footnote text
        """
        text = self._clean_text(text)
        if text.strip():
            self.content.append(("footnote", text))

    def add_reference(self, text: str, number: Optional[int] = None):
        """
        Add a reference entry with smaller font and optional number.

        Args:
            text: Reference text
            number: Optional reference number (prepended as [N])
        """
        text = self._clean_text(text)
        if text.strip():
            if number is not None:
                text = f"[{number}] {text}"
            self.content.append(("reference", text))

    def add_table(
        self,
        data: List[List[str]],
        caption: Optional[str] = None,
        header_row: bool = True,
    ):
        """
        Add a table to the document.

        Args:
            data: 2D list of cell contents (rows x columns)
            caption: Optional table caption
            header_row: If True, style first row as header
        """
        if data:
            self.content.append(("table", (data, caption, header_row)))

    def _clean_text(self, text: str, preserve_newlines: bool = False) -> str:
        """
        Clean text for PDF rendering.

        - Normalize whitespace
        - Handle special characters
        - Escape XML entities for reportlab

        Args:
            text: Text to clean
            preserve_newlines: If True, convert newlines to <br/> for reportlab
        """
        if not text:
            return ""

        # Escape XML entities first (reportlab uses XML-style markup)
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")

        if preserve_newlines:
            # Replace newlines with <br/> tags for reportlab
            text = re.sub(r"\n+", "<br/>", text)
            # Normalize other whitespace
            text = re.sub(r"[ \t]+", " ", text)
        else:
            # Normalize all whitespace (including newlines) to single spaces
            text = re.sub(r"\s+", " ", text)

        text = text.strip()
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
        bookmark_counter = 0
        last_outline_level = -1  # Track last outline level to prevent skipping

        # Calculate content width
        content_width = self.config.page_width - self.config.margin_left - self.config.margin_right

        for content_type, content_data in self.content:
            if content_type == "title_page":
                # Add a dedicated title page
                title, author = content_data
                # Add bookmark for title
                bookmark_counter += 1
                bookmark_key = f"title_{bookmark_counter}"
                flowables.append(BookmarkFlowable(title[:50], level=0, key=bookmark_key))
                last_outline_level = 0
                # Add vertical space to center title
                flowables.append(Spacer(1, 100))
                # Title
                p = Paragraph(title, self._styles["Title"])
                flowables.append(p)
                # Author if provided
                if author:
                    flowables.append(Spacer(1, 24))
                    author_p = Paragraph(author, self._styles["Normal"])
                    flowables.append(author_p)
                # Page break after title page
                from reportlab.platypus import PageBreak

                flowables.append(PageBreak())

            elif content_type == "title":
                # Add bookmark for title
                bookmark_counter += 1
                bookmark_key = f"title_{bookmark_counter}"
                flowables.append(BookmarkFlowable(content_data[:50], level=0, key=bookmark_key))
                last_outline_level = 0
                p = Paragraph(content_data, self._styles["Title"])
                flowables.append(p)

            elif content_type == "heading":
                text, level = content_data
                # Add bookmark for heading
                bookmark_counter += 1
                bookmark_key = f"heading_{bookmark_counter}"
                # Level in outline: 0 = top level, 1 = sub, 2 = sub-sub
                outline_level = min(level - 1, 2)
                # Ensure we don't skip levels (reportlab requirement)
                if last_outline_level >= 0 and outline_level > last_outline_level + 1:
                    outline_level = last_outline_level + 1
                last_outline_level = outline_level
                flowables.append(BookmarkFlowable(text[:50], level=outline_level, key=bookmark_key))
                style_name = f"Heading{min(level, 3)}"
                p = Paragraph(text, self._styles[style_name])
                flowables.append(p)

            elif content_type == "paragraph":
                text, style_name = content_data
                style = self._styles.get(style_name, self._styles["Normal"])
                p = Paragraph(text, style)
                flowables.append(p)

            elif content_type == "image":
                # Unpack with optional anchor (for backwards compatibility)
                if len(content_data) == 4:
                    image_path, caption, max_width, anchor = content_data
                else:
                    image_path, caption, max_width = content_data
                    anchor = None

                # Add anchor for internal links if provided
                if anchor:
                    flowables.append(AnchorFlowable(anchor))

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

            elif content_type == "footnote":
                # Add separator line before first footnote group
                flowables.append(Spacer(1, 6))
                p = Paragraph(content_data, self._styles["Footnote"])
                flowables.append(p)

            elif content_type == "reference":
                # Reference entry with smaller font
                p = Paragraph(content_data, self._styles["Reference"])
                flowables.append(p)

            elif content_type == "anchor":
                # Named destination for internal links
                flowables.append(AnchorFlowable(content_data))

            elif content_type == "table":
                data, caption, header_row = content_data
                table_flowable = self._create_table_flowable(data, content_width, header_row)
                if table_flowable:
                    flowables.append(Spacer(1, 6))
                    flowables.append(table_flowable)
                    if caption:
                        cap = Paragraph(caption, self._styles["Caption"])
                        flowables.append(cap)
                    flowables.append(Spacer(1, 6))

        return flowables

    def _create_table_flowable(
        self,
        data: List[List[str]],
        content_width: float,
        header_row: bool = True,
    ) -> Optional[Table]:
        """
        Create a reportlab Table flowable with intelligent column sizing.

        Args:
            data: 2D list of cell contents
            content_width: Available content width
            header_row: Style first row as header

        Returns:
            Table flowable or None if data is empty
        """
        if not data or not data[0]:
            return None

        try:
            # Clean cell contents and wrap in Paragraph for text wrapping
            cleaned_data = []
            max_col_lengths = []  # Track max content length per column
            num_cols = len(data[0])

            # Initialize max lengths
            for _ in range(num_cols):
                max_col_lengths.append(0)

            # Create cell style for table
            cell_style = ParagraphStyle(
                name="TableCell",
                fontName=self._styles["Normal"].fontName,
                fontSize=self.config.font_size - 2,
                leading=(self.config.font_size - 2) * 1.3,
                spaceBefore=0,
                spaceAfter=0,
            )
            header_style = ParagraphStyle(
                name="TableHeader",
                fontName=f"{'OpenDyslexic' if self.config.use_opendyslexic else 'Helvetica'}-Bold",
                fontSize=self.config.font_size - 2,
                leading=(self.config.font_size - 2) * 1.3,
                spaceBefore=0,
                spaceAfter=0,
            )

            for row_idx, row in enumerate(data):
                cleaned_row = []
                for col_idx, cell in enumerate(row):
                    cell_text = self._clean_text(str(cell) if cell else "")
                    # Track max length for column width calculation
                    max_col_lengths[col_idx] = max(max_col_lengths[col_idx], len(cell_text))
                    # Use Paragraph for text wrapping
                    style = header_style if (header_row and row_idx == 0) else cell_style
                    cleaned_row.append(Paragraph(cell_text, style))
                cleaned_data.append(cleaned_row)

            # Calculate intelligent column widths based on content
            # For tables with many columns, we need to ensure minimum readable width
            total_chars = sum(max_col_lengths)

            # If too many columns for the page width, use simpler text rendering
            if num_cols > 12:
                # Too many columns - fall back to simpler layout
                # Use minimum viable width per column
                min_col_width = 28  # Just enough for a few chars
                col_widths = [min_col_width] * num_cols
            elif total_chars > 0:
                col_widths = []
                # Calculate approximate character width at font size
                char_width = (self.config.font_size - 2) * 0.6

                for length in max_col_lengths:
                    # Width based on content length, with minimum for readability
                    # At least 35pt to fit "0.95" comfortably
                    width = max(35, length * char_width + 8)  # +8 for padding
                    col_widths.append(width)

                # Check if total width exceeds content width
                total_width = sum(col_widths)
                if total_width > content_width:
                    # Scale down proportionally
                    scale = content_width / total_width
                    col_widths = [w * scale for w in col_widths]

                    # Ensure minimum readable width after scaling
                    min_readable = 30
                    col_widths = [max(min_readable, w) for w in col_widths]
            else:
                # Fall back to equal widths
                col_widths = [content_width / num_cols] * num_cols

            # Create table
            table = Table(cleaned_data, colWidths=col_widths)

            # Define table style with improved padding and borders
            style_commands = [
                # Grid - lighter for readability
                ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.7, 0.7, 0.7)),
                # Increased padding for readability
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                # Alignment
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]

            # Header row styling
            if header_row and len(cleaned_data) > 1:
                style_commands.extend(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
                        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.Color(0.5, 0.5, 0.5)),
                        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ]
                )

            # Alternating row colors for better readability
            for row_idx in range(1, len(cleaned_data)):
                if row_idx % 2 == 0:
                    style_commands.append(
                        ("BACKGROUND", (0, row_idx), (-1, row_idx), colors.Color(0.97, 0.97, 0.97))
                    )

            table.setStyle(TableStyle(style_commands))
            return table

        except Exception as e:
            logger.warning(f"Failed to create table flowable: {e}")
            return None

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

        # Calculate effective bottom margin (including notes zone)
        effective_bottom_margin = self.config.margin_bottom
        if self.config.notes_zone_enabled:
            effective_bottom_margin += self.config.notes_zone_height + 10  # +10 for separator

        # Create document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=(self.config.page_width, self.config.page_height),
            topMargin=self.config.margin_top,
            bottomMargin=effective_bottom_margin,
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

        # Build PDF with page callback for notes zone
        if self.config.notes_zone_enabled:
            doc.build(
                flowables,
                onFirstPage=self._draw_notes_zone,
                onLaterPages=self._draw_notes_zone,
            )
        else:
            doc.build(flowables)

        logger.info(f"PDF built: {output_path}")
        return output_path

    def _draw_notes_zone(self, canvas, doc):
        """
        Draw the 'My Notes' zone at the bottom of each page.

        Args:
            canvas: reportlab canvas object
            doc: document template
        """
        canvas.saveState()

        # Calculate notes zone position - place at absolute bottom of page
        zone_height = self.config.notes_zone_height
        zone_y = 10  # Small margin from absolute page bottom
        zone_width = self.config.page_width - self.config.margin_left - self.config.margin_right
        zone_x = self.config.margin_left

        # Draw separator line
        canvas.setStrokeColor(lightgrey)
        canvas.setLineWidth(0.5)
        line_y = zone_y + zone_height + 5
        canvas.line(zone_x, line_y, zone_x + zone_width, line_y)

        # Draw "My Notes" label
        base_font = "OpenDyslexic" if self.config.use_opendyslexic else "Helvetica"
        try:
            canvas.setFont(f"{base_font}-Italic", 9)
        except Exception:
            canvas.setFont("Helvetica-Oblique", 9)
        canvas.setFillColor(lightgrey)
        canvas.drawString(zone_x, zone_y + zone_height - 2, "My Notes:")

        # Draw light ruled lines for notes
        canvas.setStrokeColor(lightgrey)
        canvas.setLineWidth(0.25)
        line_spacing = 18  # Points between ruled lines
        num_lines = int((zone_height - 15) / line_spacing)

        for i in range(num_lines):
            y = zone_y + zone_height - 18 - (i * line_spacing)
            canvas.line(zone_x, y, zone_x + zone_width, y)

        canvas.restoreState()


def convert_pdf_to_remarkable(
    input_path: Path,
    output_path: Optional[Path] = None,
    font_size: int = 14,
    extract_formulas: bool = True,
) -> Path:
    """
    Convert a PDF to reMarkable-optimized format.

    This is the main entry point for PDF-to-PDF conversion.
    Uses PyMuPDF for text extraction (preserves word spacing) and
    extracts images from the source PDF.

    Args:
        input_path: Path to source PDF
        output_path: Path for output PDF (default: input_remarkable.pdf)
        font_size: Font size (12, 14, 16, or 18)
        extract_formulas: Whether to extract formulas as images

    Returns:
        Path to the generated PDF
    """
    import shutil
    import tempfile

    import fitz  # PyMuPDF

    from .pdf_parser import PDFParser

    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_stem(f"{input_path.stem}_remarkable")

    logger.info(f"Converting {input_path} to reMarkable format...")

    # Initialize parser and builder
    parser = PDFParser()
    config = PDFBuilderConfig(font_size=font_size)
    builder = PDFBuilder(config=config)

    # Create temp directory for images
    temp_dir = Path(tempfile.mkdtemp(prefix="arxiv2rm_"))

    try:
        # Open source PDF with PyMuPDF
        doc = fitz.open(input_path)

        # Extract metadata
        pdf_metadata = doc.metadata
        title = pdf_metadata.get("title", "") or input_path.stem
        author = pdf_metadata.get("author", "")

        builder.set_metadata(title=title, author=author)

        # Extract formula images if requested
        formula_regions = []
        if extract_formulas:
            logger.info("Extracting formula images...")
            formula_regions = parser.extract_matrix_formulas(input_path, temp_dir)
            logger.info(f"Extracted {len(formula_regions)} formula images")

        # Build lookup of formula regions by page
        formula_by_page: Dict[int, List[Dict]] = {}
        for region in formula_regions:
            page_num = region.get("page", 0)
            if page_num not in formula_by_page:
                formula_by_page[page_num] = []
            formula_by_page[page_num].append(region)

        # Extract all embedded images from PDF
        logger.info("Extracting images from PDF...")
        image_count = 0
        images_by_page: Dict[int, List[Path]] = {}

        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)

            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image:
                        image_bytes = base_image["image"]
                        image_ext = base_image.get("ext", "png")

                        # Save image
                        img_path = temp_dir / f"page{page_num + 1}_img{img_index + 1}.{image_ext}"
                        with open(img_path, "wb") as f:
                            f.write(image_bytes)

                        if page_num not in images_by_page:
                            images_by_page[page_num] = []
                        images_by_page[page_num].append(img_path)
                        image_count += 1
                except Exception as e:
                    logger.debug(f"Failed to extract image xref={xref}: {e}")

        logger.info(f"Extracted {image_count} images from PDF")

        # Process each page with PyMuPDF (preserves word spacing!)
        logger.info("Processing pages with PyMuPDF...")
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Get page height for footnote detection
            page_rect = page.rect
            page_height = page_rect.height

            # Get text blocks with structure info
            blocks = page.get_text("dict")["blocks"]

            # Collect text and detect structure
            page_content = _extract_page_structure(
                blocks, page_num, formula_by_page, temp_dir, page_height
            )

            # Add content to builder
            for item in page_content:
                item_type = item["type"]

                if item_type == "title":
                    builder.add_title(item["text"])
                elif item_type == "heading":
                    builder.add_heading(item["text"], level=item.get("level", 1))
                elif item_type == "paragraph":
                    builder.add_paragraph(item["text"])
                elif item_type == "abstract":
                    builder.add_abstract(item["text"])
                elif item_type == "formula":
                    formula_path = item.get("path")
                    if formula_path and Path(formula_path).exists():
                        builder.add_formula_image(Path(formula_path))
                elif item_type == "footnote":
                    builder.add_footnote(item["text"])

            # Add page images (after text content)
            if page_num in images_by_page:
                for img_path in images_by_page[page_num]:
                    # Skip very small images (likely icons)
                    try:
                        with Image.open(img_path) as img:
                            if img.width >= 100 and img.height >= 100:
                                builder.add_image(img_path)
                    except Exception as e:
                        logger.debug(f"Skipping image {img_path}: {e}")

            # Add page break spacer (except last page)
            if page_num < len(doc) - 1:
                builder.add_spacer(18)

        doc.close()

        # Build output PDF
        output_path = builder.build(output_path)
        logger.info(f"Conversion complete: {output_path}")
        return output_path

    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def _extract_page_structure(
    blocks: List[Dict],
    page_num: int,
    formula_by_page: Dict[int, List[Dict]],
    temp_dir: Path,
    page_height: float = 842,  # Default A4 height in points
) -> List[Dict]:
    """
    Extract structured content from PyMuPDF text blocks.

    Detects:
    - Titles (large font, first page)
    - Headings (numbered sections, keywords)
    - Abstract
    - Regular paragraphs
    - Formula placeholders
    - Footnotes (small text at bottom of page)

    Args:
        blocks: PyMuPDF text blocks
        page_num: Current page number (0-indexed)
        formula_by_page: Formula regions by page
        temp_dir: Temporary directory for formula images
        page_height: Page height in points for footnote detection

    Returns:
        List of content items with type and text
    """
    content = []
    footnotes = []  # Collect footnotes separately
    current_paragraph = []
    seen_abstract = False
    in_abstract = False

    # Footnote detection threshold: bottom 15% of page
    footnote_y_threshold = page_height * 0.85

    # Get formula regions for this page
    page_formulas = formula_by_page.get(page_num, [])

    for block in blocks:
        if block.get("type") != 0:  # Skip non-text blocks
            continue

        # Extract text from block
        block_text = ""
        max_font_size = 0
        is_bold = False

        for line in block.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                span_font = span.get("font", "")
                span_size = span.get("size", 12)

                line_text += span_text
                max_font_size = max(max_font_size, span_size)

                if "Bold" in span_font or "bold" in span_font:
                    is_bold = True

            if line_text.strip():
                block_text += line_text + " "

        block_text = block_text.strip()
        if not block_text:
            continue

        # Check if this block overlaps with a formula region
        block_bbox = block.get("bbox", (0, 0, 0, 0))
        block_y = block_bbox[1]  # Top y-coordinate of block

        # Detect footnotes: small font at bottom of page, or starts with number/symbol
        is_footnote = False
        if block_y > footnote_y_threshold:
            # Block is in bottom 15% of page
            if max_font_size < 10:  # Small font size
                is_footnote = True
            elif re.match(r"^\d+\s", block_text) or re.match(r"^[*†‡§]\s", block_text):
                # Starts with footnote marker (number or symbol)
                is_footnote = True

        if is_footnote:
            footnotes.append({"type": "footnote", "text": block_text})
            continue
        formula_matched = False
        for formula in page_formulas:
            formula_bbox = formula.get("bbox")
            if formula_bbox and _bboxes_overlap(block_bbox, tuple(formula_bbox)):
                # Insert formula image instead of text
                if current_paragraph:
                    para_text = " ".join(current_paragraph)
                    if para_text.strip():
                        content.append({"type": "paragraph", "text": para_text})
                    current_paragraph = []

                content.append({"type": "formula", "path": str(formula.get("img_path", ""))})
                formula_matched = True
                break

        if formula_matched:
            continue

        # Detect content type based on font size and patterns
        content_type = _detect_content_type(
            block_text, max_font_size, is_bold, page_num, seen_abstract
        )

        if content_type == "title":
            if current_paragraph:
                para_text = " ".join(current_paragraph)
                if para_text.strip():
                    content.append({"type": "paragraph", "text": para_text})
                current_paragraph = []
            content.append({"type": "title", "text": block_text})

        elif content_type == "heading":
            if current_paragraph:
                para_type = "abstract" if in_abstract else "paragraph"
                para_text = " ".join(current_paragraph)
                if para_text.strip():
                    content.append({"type": para_type, "text": para_text})
                current_paragraph = []
            in_abstract = False
            level = _get_heading_level(block_text)
            content.append({"type": "heading", "text": block_text, "level": level})

        elif content_type == "abstract_start":
            if current_paragraph:
                para_text = " ".join(current_paragraph)
                if para_text.strip():
                    content.append({"type": "paragraph", "text": para_text})
                current_paragraph = []
            seen_abstract = True
            in_abstract = True
            # Add "Abstract" as heading
            content.append({"type": "heading", "text": "Abstract", "level": 1})

        elif in_abstract:
            # Check if we should end abstract (new section starting)
            if _is_section_start(block_text):
                if current_paragraph:
                    para_text = " ".join(current_paragraph)
                    if para_text.strip():
                        content.append({"type": "abstract", "text": para_text})
                    current_paragraph = []
                in_abstract = False
                level = _get_heading_level(block_text)
                content.append({"type": "heading", "text": block_text, "level": level})
            else:
                current_paragraph.append(block_text)

        else:
            # Regular paragraph - accumulate text
            current_paragraph.append(block_text)

    # Flush remaining paragraph
    if current_paragraph:
        para_type = "abstract" if in_abstract else "paragraph"
        para_text = " ".join(current_paragraph)
        if para_text.strip():
            content.append({"type": para_type, "text": para_text})

    # Append footnotes at the end
    if footnotes:
        content.extend(footnotes)

    return content


def _detect_content_type(
    text: str,
    font_size: float,
    is_bold: bool,
    page_num: int,
    seen_abstract: bool,
) -> str:
    """Detect the type of content based on text and formatting."""
    text_lower = text.lower().strip()

    # Title: large font on first page, short text
    if page_num == 0 and font_size >= 16 and len(text) < 200:
        return "title"

    # Abstract marker
    if text_lower in ["abstract", "summary"] or text_lower.startswith("abstract:"):
        return "abstract_start"

    # Section headings
    if _is_section_start(text):
        return "heading"

    # Large bold text is likely a heading
    if is_bold and font_size >= 12 and len(text) < 100:
        heading_keywords = [
            "introduction",
            "background",
            "methods",
            "methodology",
            "results",
            "discussion",
            "conclusion",
            "references",
            "acknowledgment",
            "appendix",
            "related work",
        ]
        if any(text_lower.startswith(kw) for kw in heading_keywords):
            return "heading"

    return "paragraph"


def _is_section_start(text: str) -> bool:
    """Check if text is a section heading."""
    text = text.strip()

    # Numbered sections: "1. Introduction", "1.1 Background"
    if re.match(r"^\d+(\.\d+)*\.?\s+[A-Z]", text):
        return True

    # Keyword headings
    heading_keywords = [
        "introduction",
        "background",
        "methods",
        "methodology",
        "materials and methods",
        "results",
        "discussion",
        "conclusions",
        "conclusion",
        "references",
        "bibliography",
        "acknowledgments",
        "acknowledgements",
        "appendix",
        "related work",
        "literature review",
        "experimental",
        "data and methods",
        "study design",
        "participants",
        "procedure",
        "measures",
        "analysis",
        "findings",
        "implications",
        "limitations",
        "future work",
    ]

    text_lower = text.lower()
    for keyword in heading_keywords:
        if text_lower == keyword or text_lower.startswith(keyword + ":"):
            return True
        # Also match numbered versions like "1. Introduction"
        if re.match(rf"^\d+\.?\s*{keyword}$", text_lower, re.IGNORECASE):
            return True

    return False


def _get_heading_level(text: str) -> int:
    """Determine heading level from text."""
    text = text.strip()

    # Count dots in number prefix: "1." = level 1, "1.1" = level 2, "1.1.1" = level 3
    match = re.match(r"^(\d+(?:\.\d+)*)", text)
    if match:
        num_parts = match.group(1).count(".") + 1
        return min(num_parts, 3)

    return 1  # Default to level 1


def _bboxes_overlap(bbox1: tuple, bbox2: tuple, margin: float = 10.0) -> bool:
    """Check if two bounding boxes overlap."""
    x0_1, y0_1, x1_1, y1_1 = bbox1
    x0_2, y0_2, x1_2, y1_2 = bbox2

    # Expand bbox2 by margin
    x0_2 -= margin
    y0_2 -= margin
    x1_2 += margin
    y1_2 += margin

    # Check for no overlap conditions
    if x1_1 < x0_2 or x0_1 > x1_2:
        return False
    if y1_1 < y0_2 or y0_1 > y1_2:
        return False

    return True


def convert_latex_to_remarkable(
    latex_dir: Path,
    main_tex_file: Path,
    output_path: Optional[Path] = None,
    font_size: int = 14,
    title: Optional[str] = None,
    authors: Optional[List[str]] = None,
    render_tables_as_images: bool = True,
    render_math_as_images: bool = True,
) -> Path:
    """
    Convert LaTeX source to reMarkable-optimized PDF.

    Uses LaTeXProcessor to extract structure from .tex files and
    PDFBuilder to generate reMarkable PDF with TOC, notes zone, etc.

    Args:
        latex_dir: Directory containing LaTeX source files
        main_tex_file: Path to main .tex file
        output_path: Path for output PDF (default: latex_dir/../output.pdf)
        font_size: Font size (12, 14, 16, or 18)
        render_tables_as_images: If True, render tables as images using pdflatex
        render_math_as_images: If True, render display math as images using pdflatex
        title: Override title (default: extracted from LaTeX)
        authors: Override authors (default: extracted from LaTeX)

    Returns:
        Path to the generated PDF
    """
    import tempfile

    from .latex_processor import LaTeXProcessor
    from .math_renderer import MathFormula, MathRenderer
    from .table_renderer import TableRenderer

    latex_dir = Path(latex_dir)
    main_tex_file = Path(main_tex_file)

    if output_path is None:
        output_path = latex_dir.parent / "remarkable_output.pdf"

    logger.info(f"Converting LaTeX to reMarkable format: {main_tex_file}")

    # Parse LaTeX document
    processor = LaTeXProcessor(latex_dir, main_tex_file)
    doc = processor.process()

    # Create temp directory for rendered images
    temp_dir = Path(tempfile.mkdtemp(prefix="arxiv2rm_latex_"))

    # Initialize table renderer if needed
    table_renderer = None
    table_images: Dict[str, Path] = {}  # label -> image path
    if render_tables_as_images and doc.tables:
        table_renderer = TableRenderer(cache_dir=temp_dir / "table_cache")

        # Render all tables as images
        for tab in doc.tables:
            if tab.content and tab.label:
                output_img = temp_dir / f"table_{tab.number}.png"
                rendered = table_renderer.render(tab, output_img)
                if rendered:
                    table_images[tab.label] = rendered
                    logger.info(f"Rendered table {tab.number} ({tab.label}) as image")

    # Initialize math renderer and render display math as images
    # Use content hash as key for matching markers in text
    import hashlib

    math_images: Dict[str, Path] = {}  # content_hash -> image path
    if render_math_as_images and doc.math_formulas:
        math_renderer = MathRenderer(cache_dir=temp_dir / "math_cache")
        display_formulas = [f for f in doc.math_formulas if f.is_display]
        logger.info(f"Rendering {len(display_formulas)} display math formulas...")

        for formula in display_formulas:
            # Generate hash from latex code (same as in _clean_latex_content)
            content_hash = hashlib.md5(formula.latex_code.encode()).hexdigest()[:8]
            output_img = temp_dir / f"math_{content_hash}.png"

            # Convert latex_processor.MathFormula to math_renderer.MathFormula
            renderer_formula = MathFormula(
                latex_code=formula.latex_code,
                is_display=formula.is_display,
                formula_id=formula.formula_id,
            )
            rendered = math_renderer.render(renderer_formula, output_img)
            if rendered:
                math_images[content_hash] = rendered
                logger.debug(f"Rendered math {content_hash}: {formula.latex_code[:30]}...")

    # Initialize builder
    config = PDFBuilderConfig(font_size=font_size)
    builder = PDFBuilder(config=config)

    # Set metadata
    doc_title = title or doc.title or main_tex_file.stem
    doc_authors = authors or doc.authors
    builder.set_metadata(
        title=doc_title,
        author=", ".join(doc_authors) if doc_authors else "",
    )

    # Add title
    builder.add_title(doc_title)

    # Add authors if present
    if doc_authors:
        author_text = ", ".join(doc_authors)
        builder.add_paragraph(author_text, style="Abstract")
        builder.add_spacer(12)

    # Add abstract if present
    if doc.abstract:
        builder.add_heading("Abstract", level=1)
        builder.add_abstract(doc.abstract)
        builder.add_spacer(12)

    # Build label-to-figure/table map for reference resolution
    label_to_figure = {fig.label: fig for fig in doc.figures if fig.label}
    label_to_table = {tab.label: tab for tab in doc.tables if tab.label}

    # Track which figures/tables have been inserted
    inserted_figures = set()
    inserted_tables = set()

    # Add sections
    for section in doc.sections:
        # Add section heading
        builder.add_heading(section.title, level=section.level)

        # Add section content
        if section.content:
            # Convert reference markers to clickable links
            content = section.content

            # Replace <<<REF:fig:label>>> with clickable link
            def make_fig_link(match):
                label = match.group(1)
                fig = label_to_figure.get(f"fig:{label}")
                if fig:
                    # Use <link> tag for internal PDF link
                    return (
                        f'<link destination="fig:{label}" color="blue">Figure {fig.number}</link>'
                    )
                return "Figure"

            def make_tab_link(match):
                label = match.group(1)
                tab = label_to_table.get(f"tab:{label}")
                if tab:
                    return f'<link destination="tab:{label}" color="blue">Table {tab.number}</link>'
                return "Table"

            content = re.sub(r"<<<REF:fig:([^>]+)>>>", make_fig_link, content)
            content = re.sub(r"<<<REF:tab:([^>]+)>>>", make_tab_link, content)
            content = re.sub(r"<<<REF:[^>]+>>>", "", content)

            # Split content into paragraphs, handling display math markers
            paragraphs = content.split("\n\n")
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # Check if this is a display math marker
                math_match = re.match(r"<<<DISPLAY_MATH:([a-f0-9]+)>>>", para)
                if math_match:
                    content_hash = math_match.group(1)
                    if content_hash in math_images:
                        # Insert the rendered math formula image
                        builder.add_formula_image(math_images[content_hash])
                        logger.debug(f"Inserted math formula image: {content_hash}")
                    else:
                        # Fallback: show placeholder if math rendering failed
                        builder.add_paragraph("[equation]")
                        logger.warning(f"Math image not found for hash: {content_hash}")
                else:
                    # Regular paragraph - but may contain inline math markers
                    # Clean up any remaining math markers in text
                    para = re.sub(r"<<<DISPLAY_MATH:[a-f0-9]+>>>", "[equation]", para)
                    builder.add_paragraph(para)

        # Insert figures referenced in this section
        for ref_label in section.figure_refs:
            if ref_label in label_to_figure and ref_label not in inserted_figures:
                fig = label_to_figure[ref_label]
                if fig.image_path:
                    # Resolve image path
                    img_path = processor._resolve_image_path(fig.image_path)
                    if img_path and img_path.exists():
                        caption = f"Figure {fig.number}"
                        if fig.caption:
                            caption += f": {fig.caption}"
                        # Add anchor for internal links
                        builder.add_image(img_path, caption=caption, anchor=ref_label)
                        inserted_figures.add(ref_label)
                        logger.debug(f"Inserted figure {fig.number}: {ref_label}")

        # Insert tables referenced in this section
        for ref_label in section.table_refs:
            if ref_label in label_to_table and ref_label not in inserted_tables:
                tab = label_to_table[ref_label]
                caption = f"Table {tab.number}"
                if tab.caption:
                    caption += f": {tab.caption}"

                # Check if we have a rendered image for this table
                if ref_label in table_images:
                    img_path = table_images[ref_label]
                    if img_path.exists():
                        # Add anchor for internal links
                        builder.add_image(img_path, caption=caption, anchor=ref_label)
                        inserted_tables.add(ref_label)
                        logger.debug(f"Inserted table {tab.number} as image: {ref_label}")
                        continue

                # Fallback: render table as structured text (with anchor)
                builder.content.append(("anchor", ref_label))  # Add anchor before table
                builder.add_heading(caption, level=3)
                if tab.content:
                    # Simple table rendering: extract cell contents
                    table_html = LaTeXProcessor.tabular_to_html(tab.content)
                    # Strip HTML tags for plain text
                    table_text = re.sub(r"<[^>]+>", " ", table_html)
                    table_text = re.sub(r"\s+", " ", table_text).strip()
                    if table_text:
                        builder.add_paragraph(table_text, style="Normal")

                inserted_tables.add(ref_label)
                logger.debug(f"Inserted table {tab.number} as text: {ref_label}")

    # Add any remaining figures not referenced in sections
    for fig in doc.figures:
        if fig.label and fig.label not in inserted_figures:
            if fig.image_path:
                img_path = processor._resolve_image_path(fig.image_path)
                if img_path and img_path.exists():
                    caption = f"Figure {fig.number}"
                    if fig.caption:
                        caption += f": {fig.caption}"
                    # Include anchor for potential links
                    builder.add_image(img_path, caption=caption, anchor=fig.label)
                    logger.debug(f"Inserted unreferenced figure {fig.number}")

    # Add any remaining tables not referenced in sections
    for tab in doc.tables:
        if tab.label and tab.label not in inserted_tables:
            caption = f"Table {tab.number}"
            if tab.caption:
                caption += f": {tab.caption}"

            # Check if we have a rendered image for this table
            if tab.label in table_images:
                img_path = table_images[tab.label]
                if img_path.exists():
                    # Include anchor for potential links
                    builder.add_image(img_path, caption=caption, anchor=tab.label)
                    logger.debug(f"Inserted unreferenced table {tab.number} as image")
                    continue

            # Fallback: add table as text (with anchor)
            builder.content.append(("anchor", tab.label))
            builder.add_heading(caption, level=3)
            if tab.content:
                table_html = LaTeXProcessor.tabular_to_html(tab.content)
                table_text = re.sub(r"<[^>]+>", " ", table_html)
                table_text = re.sub(r"\s+", " ", table_text).strip()
                if table_text:
                    builder.add_paragraph(table_text, style="Normal")
            logger.debug(f"Inserted unreferenced table {tab.number} as text")

    # Build output PDF
    output_path = builder.build(output_path)
    logger.info(f"LaTeX conversion complete: {output_path}")
    return output_path


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
