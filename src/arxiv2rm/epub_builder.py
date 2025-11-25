"""
EPUB Builder for reMarkable-optimized ebooks.

Creates EPUB 3.0 files optimized for reMarkable e-ink display:
- Semantic HTML structure (h1, h2, p, figure)
- OpenDyslexic font embedding
- E-ink optimized CSS (high contrast, good line spacing)
- Image optimization (grayscale, contrast enhancement)
- Table of Contents generation
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ebooklib import epub

logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """Represents a chapter or section in the document."""

    title: str
    content: str  # HTML content
    level: int = 1  # Heading level (1=chapter, 2=section, etc.)
    images: List[Path] = field(default_factory=list)
    file_name: Optional[str] = None

    def __post_init__(self):
        if not self.file_name:
            # Generate safe filename from title
            safe_title = re.sub(r"[^\w\s-]", "", self.title.lower())
            safe_title = re.sub(r"[-\s]+", "-", safe_title).strip("-")
            self.file_name = f"{safe_title[:50]}.xhtml"


@dataclass
class DocumentMetadata:
    """Metadata for the EPUB document."""

    title: str
    authors: List[str] = field(default_factory=list)
    abstract: Optional[str] = None
    language: str = "en"
    publisher: Optional[str] = None
    date: Optional[str] = None
    identifier: Optional[str] = None
    source_url: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.identifier:
            self.identifier = f"urn:uuid:{uuid.uuid4()}"
        if not self.date:
            self.date = datetime.now().strftime("%Y-%m-%d")


# PUA (Private Use Area) to Unicode mapping for LaTeX/CM fonts
# These characters from CMEX10, CMSY10, etc. use non-standard code points
PUA_UNICODE_MAP = {
    # CMEX10 bracket pieces (used for large delimiters)
    0xF8EE: "⎡",  # Left square bracket upper corner
    0xF8EF: "⎣",  # Left square bracket lower corner
    0xF8F0: "⎡",  # Alternative upper left
    0xF8F1: "⎢",  # Left bracket extension
    0xF8F9: "⎤",  # Right square bracket upper corner
    0xF8FA: "⎦",  # Right square bracket lower corner
    0xF8FB: "⎤",  # Alternative upper right
    0xF8FC: "⎥",  # Right bracket extension
    # Curly bracket pieces
    0xF8F3: "⎧",  # Left curly bracket upper
    0xF8F4: "⎨",  # Left curly bracket middle
    0xF8F5: "⎩",  # Left curly bracket lower
    0xF8FE: "⎫",  # Right curly bracket upper
    0xF8FD: "⎬",  # Right curly bracket middle
    0xF8F6: "⎭",  # Right curly bracket lower
    # CMSY10 symbols
    0xF8E6: "∑",  # Summation
    0xF8E7: "∏",  # Product
    0xF8FF: "→",  # Arrow (Apple PUA)
    # Parenthesis pieces
    0xF8EB: "⎛",  # Left paren upper
    0xF8EC: "⎜",  # Left paren extension
    0xF8ED: "⎝",  # Left paren lower
    0xF8F7: "⎞",  # Right paren upper
    0xF8F8: "⎟",  # Right paren extension
    0xF8F2: "⎠",  # Right paren lower
}


def normalize_pua_characters(text: str) -> str:
    """
    Convert PUA (Private Use Area) characters to standard Unicode equivalents.

    LaTeX fonts like CMEX10, CMSY10 use non-standard code points in the
    PUA range (U+E000-U+F8FF). These don't render in standard fonts.
    This function maps them to equivalent Unicode characters.

    Args:
        text: Input text possibly containing PUA characters

    Returns:
        Text with PUA characters replaced by Unicode equivalents
    """
    result = []
    for char in text:
        code = ord(char)
        if code in PUA_UNICODE_MAP:
            result.append(PUA_UNICODE_MAP[code])
        elif 0xE000 <= code <= 0xF8FF:
            # Unknown PUA character - replace with placeholder
            result.append("□")  # Using box as visual indicator
        else:
            result.append(char)
    return "".join(result)


# CSS for reMarkable e-ink display
REMARKABLE_CSS = """
/* reMarkable E-ink Optimized Stylesheet */

/* OpenDyslexic Font Embedding */
@font-face {
    font-family: 'OpenDyslexic';
    src: url('fonts/OpenDyslexic-Regular.otf') format('opentype');
    font-weight: normal;
    font-style: normal;
}

@font-face {
    font-family: 'OpenDyslexic';
    src: url('fonts/OpenDyslexic-Bold.otf') format('opentype');
    font-weight: bold;
    font-style: normal;
}

@font-face {
    font-family: 'OpenDyslexic';
    src: url('fonts/OpenDyslexic-Italic.otf') format('opentype');
    font-weight: normal;
    font-style: italic;
}

@font-face {
    font-family: 'OpenDyslexic';
    src: url('fonts/OpenDyslexic-BoldItalic.otf') format('opentype');
    font-weight: bold;
    font-style: italic;
}

body {
    font-family: 'OpenDyslexic', Georgia, 'Times New Roman', serif;
    font-size: 1em;
    line-height: 1.4;  /* Compact but readable on e-ink */
    margin: 0.8em;
    padding: 0;
    color: #000000;
    background-color: #ffffff;
    text-align: justify;
    hyphens: auto;
}

/* Math content - use standard fonts for proper symbol rendering */
/* Note: OpenDyslexic lacks many math symbols, so we fall back to system fonts */
/* The order prioritizes fonts with good Unicode math coverage */
.math, .formula, .equation {
    font-family: 'Times New Roman', 'Georgia', 'DejaVu Serif', 'Liberation Serif',
                 'Noto Serif', 'STIX Two Text', serif;
    font-style: normal;
}

/* Inline math spans */
span.math-inline {
    font-family: 'Times New Roman', 'Georgia', 'DejaVu Serif', 'Liberation Serif',
                 'Noto Serif', 'STIX Two Text', serif;
}

/* Headings - compact */
h1 {
    font-size: 1.4em;
    font-weight: bold;
    margin-top: 0.8em;
    margin-bottom: 0.3em;
    text-align: left;
    page-break-after: avoid;
}

h2 {
    font-size: 1.2em;
    font-weight: bold;
    margin-top: 0.6em;
    margin-bottom: 0.2em;
    text-align: left;
    page-break-after: avoid;
}

h3 {
    font-size: 1.1em;
    font-weight: bold;
    margin-top: 0.5em;
    margin-bottom: 0.2em;
    text-align: left;
}

/* Paragraphs - compact spacing */
p {
    margin-top: 0.4em;
    margin-bottom: 0.4em;
    text-indent: 1.5em;  /* Traditional indent for paragraph flow */
}

p:first-of-type {
    text-indent: 0;
    margin-top: 0;
}

/* Paragraph breaks - minimal */
.para-break {
    height: 0.3em;
    display: block;
}

/* Figures and images */
figure {
    margin: 1em 0;
    padding: 0;
    text-align: center;
    page-break-inside: avoid;
}

figure img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0 auto;
}

figcaption {
    font-size: 0.9em;
    font-style: italic;
    margin-top: 0.5em;
    text-align: center;
    color: #333333;
}

/* Formula images extracted from PDF */
.formula-figure {
    margin: 0.5em 0;
    text-align: center;
}

.formula-img {
    max-width: 100%;
    height: auto;
}

/* Code blocks */
pre, code {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.9em;
}

pre {
    margin: 0.5em 0;
    white-space: pre-wrap;
}

/* Lists */
ul, ol {
    margin: 0.5em 0;
    padding-left: 2em;
}

li {
    margin-bottom: 0.3em;
}

/* Blockquotes (for abstract) */
blockquote {
    margin: 0.5em 1em;
    font-style: italic;
}

/* Tables */
table {
    border-collapse: collapse;
    margin: 1em 0;
    width: 100%;
}

th, td {
    border: 1px solid #333333;
    padding: 0.5em;
    text-align: left;
}

th {
    background-color: #f0f0f0;
    font-weight: bold;
}

/* Links */
a {
    color: #000000;
    text-decoration: underline;
}

/* Title page */
.title-page {
    text-align: center;
    margin-top: 30%;
}

.title-page h1 {
    font-size: 2em;
    margin-bottom: 0.5em;
}

.title-page .authors {
    font-size: 1.2em;
    margin-top: 1em;
}

.title-page .date {
    font-size: 1em;
    margin-top: 2em;
    color: #666666;
}

/* Abstract */
.abstract {
    margin: 2em 1em;
}

.abstract h2 {
    font-size: 1.2em;
}

/* Chapter breaks */
.chapter {
    margin-top: 1em;
}

/* Notes zone - hidden on reMarkable to avoid blank pages */
.notes-zone {
    display: none;
}

/* Page section */
.page-section {
    margin-bottom: 0.5em;
}

/* Inline figures (placed within content flow) */
.inline-figure {
    margin: 0.5em auto;
}

/* Citations/References styling */
.citation {
    margin-left: 2em;
    text-indent: -2em;  /* Hanging indent for citations */
    margin-bottom: 0.8em;
    font-size: 0.95em;
    line-height: 1.5;
}

/* Table content (monospace for alignment - fallback) */
.table-content {
    font-family: monospace;
    font-size: 0.85em;
    white-space: pre-wrap;
    margin: 0.3em 0;
}

/* Data tables (structured HTML tables) */
.data-table {
    border-collapse: collapse;
    margin: 0.5em 0;
    font-size: 0.9em;
}

.data-table caption {
    font-size: 0.85em;
    font-style: italic;
}

.data-table th,
.data-table td {
    border: 1px solid #333333;
    padding: 0.2em 0.4em;
}

.data-table th {
    font-weight: bold;
}

.data-table td:first-child {
    text-align: left;
    font-weight: bold;
}

/* Subsubsection headings */
h4 {
    font-size: 1.05em;
    font-weight: bold;
    margin-top: 0.4em;
    margin-bottom: 0.2em;
}
"""


class EPUBBuilder:
    """
    Builds EPUB files optimized for reMarkable e-ink display.

    Usage:
        builder = EPUBBuilder()
        builder.set_metadata(title="Paper Title", authors=["Author Name"])
        builder.add_chapter("Introduction", "<p>Content...</p>")
        builder.add_chapter("Methods", "<p>More content...</p>")
        builder.build("output.epub")
    """

    def __init__(self, css: Optional[str] = None, embed_fonts: bool = True):
        """
        Initialize EPUB builder.

        Args:
            css: Custom CSS (uses REMARKABLE_CSS by default)
            embed_fonts: Whether to embed OpenDyslexic fonts (default: True)
        """
        self.book = epub.EpubBook()
        self.css = css or REMARKABLE_CSS
        self.chapters: List[epub.EpubHtml] = []
        self.images: Dict[str, epub.EpubImage] = {}
        self.metadata: Optional[DocumentMetadata] = None
        self._chapter_counter = 0
        self._embed_fonts = embed_fonts

        # Create CSS item upfront so chapters can reference it
        self._css_item = epub.EpubItem(
            uid="style",
            file_name="style.css",
            media_type="text/css",
            content=self.css.encode("utf-8"),
        )
        self.book.add_item(self._css_item)

        # Embed OpenDyslexic fonts
        if self._embed_fonts:
            self._add_fonts()

    def _add_fonts(self) -> None:
        """Embed OpenDyslexic font files in the EPUB."""
        font_files = [
            ("OpenDyslexic-Regular.otf", "normal", "normal"),
            ("OpenDyslexic-Bold.otf", "bold", "normal"),
            ("OpenDyslexic-Italic.otf", "normal", "italic"),
            ("OpenDyslexic-BoldItalic.otf", "bold", "italic"),
        ]

        # Try to find fonts in package resources
        try:
            # Python 3.9+ style
            fonts_package = resources.files("arxiv2rm") / "fonts"
            for font_name, weight, style in font_files:
                font_path = fonts_package / font_name
                if hasattr(font_path, "read_bytes"):
                    font_data = font_path.read_bytes()
                else:
                    # Fallback for older Python versions
                    with resources.as_file(font_path) as fp:
                        font_data = fp.read_bytes()

                # Create EPUB font item
                font_item = epub.EpubItem(
                    uid=f"font_{font_name.replace('.', '_')}",
                    file_name=f"fonts/{font_name}",
                    media_type="application/vnd.ms-opentype",
                    content=font_data,
                )
                self.book.add_item(font_item)
                logger.debug(f"Embedded font: {font_name}")

        except Exception as e:
            logger.warning(f"Could not embed fonts: {e}. Using system fonts as fallback.")

    def set_metadata(
        self,
        title: str,
        authors: Optional[List[str]] = None,
        abstract: Optional[str] = None,
        language: str = "en",
        publisher: Optional[str] = None,
        source_url: Optional[str] = None,
        keywords: Optional[List[str]] = None,
    ) -> None:
        """
        Set document metadata.

        Args:
            title: Document title
            authors: List of author names
            abstract: Document abstract
            language: Language code (default: "en")
            publisher: Publisher name
            source_url: Original source URL
            keywords: List of keywords
        """
        self.metadata = DocumentMetadata(
            title=title,
            authors=authors or [],
            abstract=abstract,
            language=language,
            publisher=publisher,
            source_url=source_url,
            keywords=keywords or [],
        )

        # Set book metadata
        self.book.set_identifier(self.metadata.identifier)
        self.book.set_title(self.metadata.title)
        self.book.set_language(self.metadata.language)

        for author in self.metadata.authors:
            self.book.add_author(author)

        if self.metadata.publisher:
            self.book.add_metadata("DC", "publisher", self.metadata.publisher)

        if self.metadata.source_url:
            self.book.add_metadata("DC", "source", self.metadata.source_url)

        for keyword in self.metadata.keywords:
            self.book.add_metadata("DC", "subject", keyword)

        logger.info(f"Set metadata: {title} by {', '.join(authors or ['Unknown'])}")

    def set_cover_image(self, image_path: Path) -> bool:
        """
        Set the cover image for the EPUB.

        Args:
            image_path: Path to the cover image file

        Returns:
            True if cover was set successfully, False otherwise
        """
        image_path = Path(image_path)
        if not image_path.exists():
            logger.warning(f"Cover image not found: {image_path}")
            return False

        # Determine file name for cover
        suffix = image_path.suffix.lower()
        cover_filename = f"cover{suffix}"

        try:
            with open(image_path, "rb") as f:
                content = f.read()

            # Use ebooklib's set_cover method
            self.book.set_cover(cover_filename, content)
            logger.info(f"Set cover image: {image_path.name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set cover image: {e}")
            return False

    def add_image(
        self,
        image_path: Path,
        alt_text: Optional[str] = None,
    ) -> str:
        """
        Add an image to the EPUB.

        Args:
            image_path: Path to image file
            alt_text: Alternative text for accessibility

        Returns:
            Reference path for use in HTML (e.g., "images/fig1.png")
        """
        image_path = Path(image_path)
        if not image_path.exists():
            logger.warning(f"Image not found: {image_path}")
            return ""

        # Determine media type
        suffix = image_path.suffix.lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
        }
        media_type = media_types.get(suffix, "image/png")

        # Create unique filename
        file_name = f"images/{image_path.name}"
        if file_name in self.images:
            # Add counter for duplicates
            base = image_path.stem
            file_name = f"images/{base}_{len(self.images)}{suffix}"

        # Read image content
        with open(image_path, "rb") as f:
            content = f.read()

        # Create EPUB image
        epub_image = epub.EpubImage()
        epub_image.file_name = file_name
        epub_image.media_type = media_type
        epub_image.content = content

        self.book.add_item(epub_image)
        self.images[file_name] = epub_image

        logger.debug(f"Added image: {file_name}")
        return file_name

    def add_chapter(
        self,
        title: str,
        content: str,
        level: int = 1,
        images: Optional[List[Path]] = None,
    ) -> epub.EpubHtml:
        """
        Add a chapter to the EPUB.

        Args:
            title: Chapter title
            content: HTML content (paragraphs, figures, etc.)
            level: Heading level (1=chapter, 2=section)
            images: List of image paths to include

        Returns:
            EpubHtml chapter object
        """
        self._chapter_counter += 1

        # Create safe filename
        safe_title = re.sub(r"[^\w\s-]", "", title.lower())
        safe_title = re.sub(r"[-\s]+", "-", safe_title).strip("-")[:50]
        file_name = f"chapter_{self._chapter_counter:02d}_{safe_title}.xhtml"

        # Add images if provided
        image_refs = []
        if images:
            for img_path in images:
                ref = self.add_image(img_path)
                if ref:
                    image_refs.append(ref)

        # Build chapter HTML - use simple structure for ebooklib compatibility
        heading_tag = f"h{min(level, 6)}"
        chapter_class = "chapter" if level == 1 else "section"

        html_content = f"""<html>
<head>
<title>{title}</title>
<link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body class="{chapter_class}">
<{heading_tag}>{title}</{heading_tag}>
{content}
</body>
</html>"""

        # Create EPUB chapter
        chapter = epub.EpubHtml(
            title=title,
            file_name=file_name,
            lang=self.metadata.language if self.metadata else "en",
        )
        chapter.content = html_content

        # Link CSS stylesheet to this chapter
        chapter.add_item(self._css_item)

        self.book.add_item(chapter)
        self.chapters.append(chapter)

        logger.debug(f"Added chapter: {title} ({file_name})")
        return chapter

    def add_title_page(self) -> epub.EpubHtml:
        """
        Add a title page with metadata.

        Returns:
            EpubHtml title page object
        """
        if not self.metadata:
            raise ValueError("Metadata must be set before adding title page")

        authors_html = "<br/>".join(self.metadata.authors) if self.metadata.authors else "Unknown"

        html_content = f"""<html>
<head>
<title>{self.metadata.title}</title>
<link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
<div class="title-page">
<h1>{self.metadata.title}</h1>
<p class="authors">{authors_html}</p>
<p class="date">{self.metadata.date}</p>
</div>
</body>
</html>"""

        title_page = epub.EpubHtml(
            title="Title Page",
            file_name="title.xhtml",
            lang=self.metadata.language,
        )
        title_page.content = html_content

        # Link CSS stylesheet
        title_page.add_item(self._css_item)

        self.book.add_item(title_page)
        self.chapters.insert(0, title_page)  # Add at beginning

        logger.debug("Added title page")
        return title_page

    def add_abstract_page(self) -> Optional[epub.EpubHtml]:
        """
        Add an abstract page if abstract is available.

        Returns:
            EpubHtml abstract page object or None
        """
        if not self.metadata or not self.metadata.abstract:
            return None

        html_content = f"""<html>
<head>
<title>Abstract</title>
<link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
<div class="abstract">
<h2>Abstract</h2>
<blockquote>
{self.metadata.abstract}
</blockquote>
</div>
</body>
</html>"""

        abstract_page = epub.EpubHtml(
            title="Abstract",
            file_name="abstract.xhtml",
            lang=self.metadata.language,
        )
        abstract_page.content = html_content

        # Link CSS stylesheet
        abstract_page.add_item(self._css_item)

        self.book.add_item(abstract_page)
        # Insert after title page
        insert_pos = 1 if self.chapters and self.chapters[0].file_name == "title.xhtml" else 0
        self.chapters.insert(insert_pos, abstract_page)

        logger.debug("Added abstract page")
        return abstract_page

    def build(self, output_path: Path) -> Path:
        """
        Build and save the EPUB file.

        Args:
            output_path: Path to save EPUB file

        Returns:
            Path to the created EPUB file
        """
        output_path = Path(output_path)

        # CSS already added in __init__

        # Set spine (reading order)
        self.book.spine = ["nav"] + self.chapters

        # Create table of contents
        self.book.toc = [
            epub.Link(ch.file_name, ch.title, ch.file_name.replace(".xhtml", ""))
            for ch in self.chapters
        ]

        # Add navigation files
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())

        # Write EPUB file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        epub.write_epub(str(output_path), self.book, {})

        logger.info(f"EPUB created: {output_path}")
        return output_path


class TextToHTMLConverter:
    """
    Converts extracted text to semantic HTML for EPUB.

    Handles:
    - Paragraph detection
    - Heading detection (based on font size or patterns)
    - List detection
    - Figure/image integration
    - References/citations formatting
    """

    def __init__(self):
        # Standalone section names (without numbers)
        self.standalone_sections = [
            "abstract",
            "introduction",
            "background",
            "related work",
            "methods",
            "method",
            "methodology",
            "materials and methods",
            "results",
            "result",
            "findings",
            "discussion",
            "conclusions",
            "conclusion",
            "references",
            "bibliography",
            "acknowledgments",
            "acknowledgements",
            "acknowledgment",
            "appendix",
            "supplementary",
            "supplemental",
            "limitations",
            "future work",
            "future directions",
        ]

    def convert(
        self,
        text: str,
        images: Optional[List[Tuple[Path, str]]] = None,
    ) -> str:
        """
        Convert plain text to HTML.

        Args:
            text: Plain text content
            images: List of (image_path, caption) tuples

        Returns:
            HTML string
        """
        if not text:
            return ""

        # Normalize PUA characters from LaTeX fonts (CMEX10, CMSY10, etc.)
        text = normalize_pua_characters(text)

        # Pre-process to extract tables from mixed content
        text = self._extract_embedded_tables(text)

        # Check if this is a references section
        is_references = self._is_references_section(text)

        # Split into paragraphs
        paragraphs = self._split_paragraphs(text)

        html_parts = []
        table_rows = []  # Buffer for consecutive table rows

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check if it's a heading
            heading_level = self._detect_heading(para)
            is_table = self._is_table_content(para)

            # If we have buffered table rows and this isn't table content, flush the buffer
            if table_rows and not is_table:
                html_parts.append(self._format_table_block(table_rows))
                table_rows = []

            if heading_level:
                html_parts.append(f"<h{heading_level}>{self._escape_html(para)}</h{heading_level}>")
            elif is_table:
                # Buffer table row for grouping
                table_rows.append(para)
            elif is_references and self._is_citation_entry(para):
                # Format as citation entry
                html_parts.append(self._format_citation(para))
            elif self._is_math_content(para):
                # Mathematical content - use standard font
                html_parts.append(f'<p class="math">{self._escape_html(para)}</p>')
            else:
                # Regular paragraph - wrap math inline
                escaped = self._escape_html(para)
                escaped = self._wrap_inline_math(escaped)
                html_parts.append(f"<p>{escaped}</p>")

        # Flush any remaining table rows
        if table_rows:
            html_parts.append(self._format_table_block(table_rows))

        # Add images at the end
        if images:
            for img_path, caption in images:
                img_ref = f"images/{img_path.name}"
                figure_html = f"""
<figure>
    <img src="{img_ref}" alt="{self._escape_html(caption)}"/>
    <figcaption>{self._escape_html(caption)}</figcaption>
</figure>"""
                html_parts.append(figure_html)

        return "\n".join(html_parts)

    def _extract_embedded_tables(self, text: str) -> str:
        """
        Extract table content embedded in paragraphs.

        Academic PDF tables often get extracted as continuous text mixed with
        surrounding paragraphs. This method detects table rows and separates
        them with clear paragraph breaks so each row becomes its own paragraph.
        """
        lines = text.split("\n")
        result_lines = []
        in_table = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect table header row (column headers with CamelCase or abbreviations)
            # e.g., "AdversarialModel Ctxt.Maint. Circuit ServerInputs"
            is_table_header = bool(
                re.search(r"[A-Z][a-z]+[A-Z][a-z]+", stripped)  # CamelCase words
                and len(stripped.split()) >= 4  # Multiple columns
                and not stripped.endswith(".")  # Not a sentence
            )

            # Detect table data row (rows with symbols like #, ?, H#)
            symbol_count = stripped.count("#") + stripped.count("?")
            is_table_row = symbol_count >= 2

            # Detect Table caption (e.g., "Table1. CHARACTERISTICS...")
            is_table_caption = bool(re.match(r"^Table\s*\d+\.?\s+[A-Z]", stripped))

            # Detect table legend/footnote
            is_table_legend = bool(
                re.search(r"[A#?H]\s*(INDICATES|MEANS|=|denotes)", stripped, re.IGNORECASE)
            )

            # Detect single CamelCase column header (e.g., "AdversarialModel")
            is_camel_header = bool(
                re.match(r"^[A-Z][a-z]+[A-Z][a-zA-Z]*$", stripped) and len(stripped) < 30
            )

            is_table_content = (
                is_table_header
                or is_table_row
                or is_table_caption
                or is_table_legend
                or is_camel_header
            )

            if is_table_content:
                if not in_table:
                    # Start of table - add double paragraph break before (two blank lines)
                    result_lines.append("")
                    result_lines.append("")
                    in_table = True
                else:
                    # Between table rows - add single paragraph break
                    result_lines.append("")
                result_lines.append(stripped)
            else:
                if in_table:
                    # End of table - add double paragraph break after
                    result_lines.append("")
                    result_lines.append("")
                    in_table = False
                result_lines.append(line)

        return "\n".join(result_lines)

    def _is_references_section(self, text: str) -> bool:
        """Check if this text block is a references/bibliography section."""
        first_lines = text[:500].lower()
        return any(kw in first_lines for kw in ["references", "bibliography", "works cited"])

    def _is_citation_entry(self, para: str) -> bool:
        """Check if paragraph looks like a citation/reference entry."""
        # Citations typically start with [N], author names, or year patterns
        if re.match(r"^\[\d+\]", para):  # [1], [2], etc.
            return True
        if re.match(r"^[A-Z][a-z]+,\s+[A-Z]\.", para):  # Author, A.
            return True
        if re.match(r"^[A-Z][a-z]+\s+[A-Z][a-z]+", para) and "(" in para[:50]:  # Name Name (Year)
            return True
        return False

    def _is_table_content(self, para: str) -> bool:
        """Check if paragraph looks like table content (comparison symbols, aligned data)."""
        # Table patterns:
        # 1. Lines with repeated symbols like #, ?, checkmarks (strong signal)
        symbol_count = para.count("#") + para.count("?")
        if symbol_count >= 3:
            return True

        # 2. Lines with citation+symbol patterns (strong signal)
        # e.g., "MtE [26] ? Any # # # H # # #"
        if re.match(r"^[A-Za-z]+\s+\[\d+\].*[#?]", para):
            return True

        # 3. Performance data tables (times, values)
        # e.g., "0.003s 0.002s 0.001s 0.807s"
        if re.search(r"\d+\.\d+s\s+\d+\.\d+s", para):
            return True

        # 4. Table caption (e.g., "Table1. CHARACTERISTICS...")
        if re.match(r"^Table\s*\d+\.?\s+[A-Z]", para):
            return True

        # 5. Table legend/footnote (explains symbols like #, ?, H#)
        # e.g., "A?INDICATESINSUFFICIENT..." or "# = supported, ? = unknown"
        if re.search(r"[A#?H]\s*(INDICATES|MEANS|=|denotes)", para, re.IGNORECASE):
            return True

        # 6. Table header row: must have MULTIPLE consecutive CamelCase words
        # (not just one like "TEEs" in a sentence)
        # e.g., "AdversarialModel Ctxt.Maint. Circuit ServerInputs"
        camel_case_matches = re.findall(r"[A-Z][a-z]+[A-Z][a-z]+|[A-Z][a-z]+\.[A-Z]", para)
        if len(camel_case_matches) >= 2 and not para.endswith(".") and len(para) < 150:
            return True

        # 7. Single CamelCase word that's a column header (like "AdversarialModel")
        # Only if it's short and standalone
        if re.match(r"^[A-Z][a-z]+[A-Z][a-zA-Z]*$", para) and len(para) < 30:
            return True

        return False

    def _format_table_content(self, para: str) -> str:
        """Format a single table row with monospace styling."""
        escaped = self._escape_html(para)
        return f'<pre class="table-content">{escaped}</pre>'

    def _format_table_block(self, rows: List[str]) -> str:
        """
        Format multiple table rows as an HTML table.

        Attempts to parse the table structure and convert to proper HTML <table>.
        Falls back to <pre> formatting if parsing fails.
        """
        if not rows:
            return ""

        # Try to parse as structured table
        parsed_table = self._parse_table_structure(rows)
        if parsed_table:
            return parsed_table

        # Fallback to pre-formatted text
        escaped_rows = [self._escape_html(row) for row in rows]
        content = "\n".join(escaped_rows)
        return f'<pre class="table-content">{content}</pre>'

    def _parse_table_structure(self, rows: List[str]) -> Optional[str]:
        """
        Parse table rows into HTML table structure.

        Detects:
        - Header row (column names)
        - Data rows (with symbols like #, ?, checkmarks)
        - Caption row (Table N. DESCRIPTION)

        Returns:
            HTML table string or None if parsing fails
        """
        if not rows:
            return None

        # Separate caption, headers, and data
        caption = None
        header_row = None
        data_rows = []

        for row in rows:
            row = row.strip()
            if not row:
                continue

            # Detect table caption (e.g., "Table 1. CHARACTERISTICS...")
            if re.match(r"^Table\s*\d+\.?\s+[A-Z]", row):
                caption = row
                continue

            # Detect legend/footnote (e.g., "A ? INDICATES...")
            if re.search(r"[A#?]\s*(INDICATES|MEANS|=|denotes)", row, re.IGNORECASE):
                # Add legend to caption
                if caption:
                    caption += " " + row
                else:
                    caption = row
                continue

            # Detect header row: contains column names (CamelCase or short words)
            # and NO symbols like # or ?
            symbol_count = row.count("#") + row.count("?")
            if symbol_count == 0 and header_row is None:
                # Could be a header row - check if it has multiple words
                words = row.split()
                if len(words) >= 3:
                    header_row = row
                    continue

            # Data row - contains symbols
            if symbol_count >= 1 or re.match(r"^[A-Za-z]+\s+\[\d+\]", row):
                # Check if this row contains multiple data rows merged together
                # Pattern: "MtE [26] ? Any # # # [27] ? Any # # #"
                # Split on citation patterns that indicate a new row
                split_rows = self._split_merged_table_rows(row)
                data_rows.extend(split_rows)

        # Need at least some data rows to create a table
        if not data_rows:
            return None

        # Parse cells from rows
        header_cells = self._parse_table_cells(header_row) if header_row else None
        data_cells = [self._parse_table_cells(row) for row in data_rows]

        # If we couldn't parse cells properly, fall back
        if not data_cells or all(len(cells) <= 1 for cells in data_cells):
            return None

        # Determine column count
        max_cols = max(len(cells) for cells in data_cells)
        if header_cells:
            max_cols = max(max_cols, len(header_cells))

        # Build HTML table
        html_parts = ['<table class="data-table">']

        # Add caption if present
        if caption:
            html_parts.append(f"<caption>{self._escape_html(caption)}</caption>")

        # Add header row
        if header_cells:
            html_parts.append("<thead><tr>")
            for cell in header_cells:
                html_parts.append(f"<th>{self._escape_html(cell)}</th>")
            # Pad with empty headers if needed
            for _ in range(max_cols - len(header_cells)):
                html_parts.append("<th></th>")
            html_parts.append("</tr></thead>")

        # Add data rows
        html_parts.append("<tbody>")
        for cells in data_cells:
            html_parts.append("<tr>")
            for cell in cells:
                # Style special symbols
                cell_html = self._format_table_cell(cell)
                html_parts.append(f"<td>{cell_html}</td>")
            # Pad with empty cells if needed
            for _ in range(max_cols - len(cells)):
                html_parts.append("<td></td>")
            html_parts.append("</tr>")
        html_parts.append("</tbody>")

        html_parts.append("</table>")
        return "\n".join(html_parts)

    def _split_merged_table_rows(self, row: str) -> List[str]:
        """
        Split a merged table row into individual rows.

        Handles cases where multiple data rows are concatenated, like:
        "MtE [26] ? Any # # # [27] ? Any # # #"
        Should become:
        ["MtE [26] ? Any # # #", "[27] ? Any # # #"]
        """
        # Look for patterns like "[N]" that indicate a new row
        # But the first citation is part of the method name (e.g., "MtE [26]")

        # Find all citation patterns
        citations = list(re.finditer(r"\[(\d+)\]", row))

        if len(citations) <= 1:
            # Only one citation, return as-is
            return [row]

        # Check if this looks like multiple rows merged
        # Pattern: data followed by citation (e.g., "# # # [27]")
        split_points = []
        for match in citations[1:]:  # Skip first citation
            # Check what comes before this citation
            pos = match.start()
            before = row[:pos].rstrip()
            # If it ends with symbols (# ? or space), this is likely a new row
            if before and (before[-1] in "#? " or before.endswith("  ")):
                split_points.append(pos)

        if not split_points:
            return [row]

        # Split the row
        result = []
        prev = 0
        for pos in split_points:
            part = row[prev:pos].strip()
            if part:
                result.append(part)
            prev = pos

        # Add the last part
        last_part = row[prev:].strip()
        if last_part:
            result.append(last_part)

        return result

    def _parse_table_cells(self, row: str) -> List[str]:
        """
        Parse a table row into cells.

        Handles multiple formats:
        - Space-separated with citation brackets: "MtE [26] ? Any # # #"
        - Citation-only rows: "[27] ? Any # # #"
        - Tab-separated
        - Multiple-space separated
        """
        if not row:
            return []

        # First, try to detect the row pattern

        # Pattern 1: Row starts with method name and citation [N]
        # e.g., "MtE [26] ? Any # # # H # # #"
        citation_match = re.match(r"^([A-Za-z]+)\s+\[(\d+)\]\s+(.+)$", row)
        if citation_match:
            method = citation_match.group(1)
            cite = f"[{citation_match.group(2)}]"
            rest = citation_match.group(3)

            # Parse the rest as space-separated values
            cells = [f"{method} {cite}"]
            tokens = rest.split()
            for token in tokens:
                cells.append(token)
            return cells

        # Pattern 1b: Citation-only row (continuation from split)
        # e.g., "[27] ? Any # # #"
        citation_only_match = re.match(r"^\[(\d+)\]\s+(.+)$", row)
        if citation_only_match:
            cite = f"[{citation_only_match.group(1)}]"
            rest = citation_only_match.group(2)

            # Parse as space-separated values
            cells = [cite]
            tokens = rest.split()
            for token in tokens:
                cells.append(token)
            return cells

        # Pattern 2: Space/tab separated columns
        # Split on multiple spaces or tabs
        parts = re.split(r"\s{2,}|\t", row)
        if len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]

        # Pattern 3: Header row - group abbreviated words with periods
        # e.g., "Ctxt. Maint." should stay together
        # First check if this looks like a header row
        if not any(c in row for c in ["#", "?"]) and re.search(r"\w+\.\s+\w+", row):
            # This is likely a header row with abbreviated column names
            # Group words that end with periods with the next word
            cells = []
            current_cell = []
            tokens = row.split()

            for i, token in enumerate(tokens):
                current_cell.append(token)
                # If token doesn't end with period, or it's the last token, finalize cell
                if not token.endswith(".") or i == len(tokens) - 1:
                    cells.append(" ".join(current_cell))
                    current_cell = []

            # Handle any remaining tokens
            if current_cell:
                cells.append(" ".join(current_cell))

            return cells

        # Pattern 4: Simple space-separated (single words)
        return row.split()

    def _format_table_cell(self, cell: str) -> str:
        """
        Format a table cell, styling special symbols.
        """
        cell = cell.strip()

        # Replace symbols with styled versions
        # # = checkmark/supported (green in color, bold for e-ink)
        # ? = unknown/insufficient (italic)
        # H# = partial support (shown as ½)

        # Handle special cases first (before escaping)
        # H# or H # (partial support)
        if cell in ["H#", "H #", "H"]:
            return "<em>½</em>"

        # Pure symbols
        if cell == "#":
            return "<strong>✓</strong>"
        if cell == "?":
            return "<em>?</em>"

        # Escape HTML for complex cells
        escaped = self._escape_html(cell)

        # Style the symbols in mixed content
        styled = escaped
        styled = styled.replace("#", "<strong>✓</strong>")
        styled = styled.replace("?", "<em>?</em>")

        return styled

    def _format_citation(self, para: str) -> str:
        """Format a citation entry with proper styling."""
        # Escape HTML but preserve structure
        escaped = self._escape_html(para)
        # Add citation class for CSS styling
        return f'<p class="citation">{escaped}</p>'

    def _is_math_content(self, para: str) -> bool:
        """
        Check if a paragraph contains primarily mathematical content.

        Mathematical content includes:
        - Equations with operators (←, →, =, ∈, ∀, ∃)
        - Greek letters (λ, τ, σ, etc.)
        - Function notation: f(x), Enc(x), Dec(x)
        - Probability notation: Pr[...]
        - Set notation: {x | ...}
        - Formal definitions: Definition X.X
        """
        # Count mathematical indicators
        math_indicators = 0

        # Greek letters (common in math)
        greek_pattern = r"[λτσαβγδεζηθικμνξπρςφχψωΛΣΠΩ]"
        math_indicators += len(re.findall(greek_pattern, para))

        # Mathematical operators and arrows
        operators = [
            "←",
            "→",
            "↔",
            "⊕",
            "⊗",
            "∈",
            "∉",
            "⊆",
            "⊇",
            "∀",
            "∃",
            "∧",
            "∨",
            "¬",
            "≤",
            "≥",
            "≠",
            "≈",
            "∞",
            "∑",
            "∏",
            "∫",
        ]
        for op in operators:
            if op in para:
                math_indicators += 2

        # Function-like notation: word(args)
        func_pattern = r"\b[A-Za-z]+\s*\([^)]+\)"
        math_indicators += len(re.findall(func_pattern, para)) * 2

        # Probability notation: Pr[...] or Pr(...)
        if re.search(r"\bPr\s*[\[\(]", para):
            math_indicators += 3

        # Formal assignment: := or ← or →
        if ":=" in para or "←" in para or "→" in para:
            math_indicators += 2

        # Definition/Theorem headers
        if re.match(r"^(Definition|Theorem|Lemma|Corollary|Proposition)\s+\d", para):
            math_indicators += 3

        # Subscript/superscript patterns: x_i, x^2
        if re.search(r"[a-zA-Z][_^]\{?[a-zA-Z0-9]+\}?", para):
            math_indicators += 2

        # Short paragraphs with high symbol density are likely math
        word_count = len(para.split())
        if word_count > 0:
            # If more than 20% of "words" are math indicators, it's math
            math_density = math_indicators / word_count
            if math_density > 0.2:
                return True

        # Absolute threshold for longer content
        return math_indicators >= 5

    def _wrap_inline_math(self, text: str) -> str:
        """
        Wrap inline mathematical expressions with math styling.

        Detects and wraps:
        - Greek letters
        - Mathematical operators
        - Function notation
        """
        # Pattern for inline math: Greek letters or operators surrounded by text
        # Wrap sequences containing Greek letters or math symbols

        # Greek letter pattern
        greek_pattern = r"([λτσαβγδεζηθικμνξπρςφχψωΛΣΠΩ]+)"

        # Wrap Greek letters in math spans
        text = re.sub(greek_pattern, r'<span class="math-inline">\1</span>', text)

        # Mathematical operators that should use math font
        math_ops = [
            "←",
            "→",
            "↔",
            "⊕",
            "⊗",
            "∈",
            "∉",
            "⊆",
            "⊇",
            "∀",
            "∃",
            "∧",
            "∨",
            "¬",
            "≤",
            "≥",
            "≠",
            "≈",
            "∞",
        ]
        for op in math_ops:
            text = text.replace(op, f'<span class="math-inline">{op}</span>')

        return text

    def _split_paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs using multiple detection strategies.

        Strategies:
        1. Double newlines (standard paragraph breaks)
        2. Lines ending with period followed by newline and capital letter
        3. Significant indent changes
        4. Short lines followed by longer lines (often indicates paragraph end)
        """
        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # First pass: split on obvious paragraph breaks (double+ newlines)
        chunks = re.split(r"\n\s*\n+", text)

        result = []
        for chunk in chunks:
            # Second pass: detect sentence-based paragraph breaks within chunks
            lines = chunk.split("\n")
            current_para = []

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    continue

                # Add line to current paragraph
                current_para.append(stripped)

                # Check if this looks like end of paragraph
                is_para_end = False

                # Pattern 1: Line ends with sentence-ending punctuation
                ends_sentence = stripped.endswith((".", "!", "?", ':"', '."', ".'"))

                # Pattern 2: Next line starts with capital (new sentence/paragraph)
                next_starts_capital = False
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and next_line[0].isupper():
                        next_starts_capital = True

                # Pattern 3: Current line is short relative to average
                is_short_line = len(stripped) < 50

                # Pattern 4: Line looks like a list item or heading
                is_list_or_heading = (
                    stripped.startswith(("•", "-", "*", "–", "—"))
                    or re.match(r"^\d+[\.\)]\s", stripped)
                    or re.match(r"^[A-Z][A-Z\s]+$", stripped)  # ALL CAPS
                )

                # Decide if paragraph ends here
                if ends_sentence and is_short_line and next_starts_capital:
                    is_para_end = True
                elif is_list_or_heading and current_para:
                    # List items become their own paragraphs
                    if len(current_para) > 1:
                        # Save previous content as paragraph
                        result.append(" ".join(current_para[:-1]))
                        current_para = [stripped]
                    is_para_end = True

                if is_para_end and current_para:
                    result.append(" ".join(current_para))
                    current_para = []

            # Don't forget remaining content
            if current_para:
                result.append(" ".join(current_para))

        return [p for p in result if p.strip()]

    def _detect_heading(self, text: str) -> Optional[int]:
        """
        Detect if text is a heading and return its level.

        Returns:
            Heading level (2-4) or None if not a heading.
            Level 2 for major sections, 3 for subsections, 4 for subsubsections.
        """
        text_stripped = text.strip()

        # Must be reasonably short to be a heading
        if len(text_stripped) > 80:
            return None

        # Must not end with common sentence punctuation (list items often end with comma/period)
        if text_stripped.endswith((",", ";", ":", "?", "!")):
            return None

        # If ends with period, only accept if it's section number period (e.g., "1. Intro")
        # Not a sentence ending (e.g., "1. Read these documents.")
        if text_stripped.endswith("."):
            # Only allow if pattern is "N. Title" and title is short (2-4 words)
            if not re.match(r"^\d+\.\s+[A-Z][a-z]+(?:\s+[A-Za-z]+){0,3}$", text_stripped):
                return None

        # Subsubsection: "4.1.1 Title" or "4.1.1. Title"
        if re.match(r"^\d+\.\d+\.\d+\.?\s+[A-Z][A-Za-z]", text_stripped):
            words = text_stripped.split()
            if len(words) <= 10:
                return 4

        # Subsection: "2.1 Title" or "2.1. Title"
        if re.match(r"^\d+\.\d+\.?\s+[A-Z][A-Za-z]", text_stripped):
            words = text_stripped.split()
            if len(words) <= 10:
                return 3

        # Major section: "1. Title" or "1 Title"
        if re.match(r"^\d+\.?\s+[A-Z][A-Za-z]", text_stripped):
            words = text_stripped.split()
            # Must be title-like: 2-6 words
            if 2 <= len(words) <= 6:
                # Get the title part (after the number)
                title_part = " ".join(words[1:]).lower()
                # Exclude if looks like a numbered list/instruction (starts with verb)
                verb_starts = [
                    "read",
                    "write",
                    "use",
                    "create",
                    "make",
                    "do",
                    "see",
                    "summarize",
                    "interpret",
                    "analyze",
                    "check",
                    "verify",
                    "note",
                    "ensure",
                    "consider",
                    "apply",
                    "acknowledge",
                ]
                if not any(title_part.startswith(v) for v in verb_starts):
                    return 2

        # Standalone section names
        text_lower = text_stripped.lower()
        if text_lower in self.standalone_sections:
            return 2

        # Appendix sections: "Appendix A", "Appendix B. Tables", etc.
        if re.match(r"^appendix\s+[a-z]\.?\s*", text_stripped, re.IGNORECASE):
            return 2

        return None

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )


def create_epub_from_pdf_result(
    pdf_result: Dict,
    output_path: Path,
    title: Optional[str] = None,
    authors: Optional[List[str]] = None,
) -> Path:
    """
    Create an EPUB from PDF parsing results.

    Args:
        pdf_result: Result from PDFParser.parse()
        output_path: Path to save EPUB
        title: Override title (defaults to PDF filename)
        authors: List of authors

    Returns:
        Path to created EPUB file
    """
    # Initialize builder
    builder = EPUBBuilder()
    converter = TextToHTMLConverter()

    # Extract title from filename if not provided
    if not title:
        output_dir = pdf_result.get("output_dir")
        if output_dir:
            title = Path(output_dir).stem.replace("_extracted", "")
        else:
            title = "Converted Document"

    # Set metadata
    builder.set_metadata(
        title=title,
        authors=authors or [],
        language="en",
    )

    # Add title page
    builder.add_title_page()

    # Get images for chapters
    images = pdf_result.get("images", [])
    images_by_page = {}
    for img in images:
        page_num = img.get("page_num", 0)
        if page_num not in images_by_page:
            images_by_page[page_num] = []
        images_by_page[page_num].append(img)

    # Process pages into chapters
    pages = pdf_result.get("pages", [])

    if not pages:
        # No pages, create a single chapter
        builder.add_chapter("Content", "<p>No content available.</p>")
    else:
        # Group pages into chapters (can be customized)
        # For now, create one chapter per page or combine small pages
        combined_text = ""
        current_images = []

        for page in pages:
            page_num = page.get("page_num", 0)
            text = page.get("text", "")

            # Add images from this page
            if page_num in images_by_page:
                for img_info in images_by_page[page_num]:
                    img_path = img_info.get("image_path")
                    if img_path:
                        current_images.append((Path(img_path), f"Figure from page {page_num}"))

            combined_text += text + "\n\n"

        # Convert all text to HTML
        html_content = converter.convert(combined_text, current_images)

        # Add as single chapter (or split by detected headings)
        builder.add_chapter("Content", html_content)

    # Build EPUB
    return builder.build(output_path)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Create a test EPUB
    builder = EPUBBuilder()
    builder.set_metadata(
        title="Test Document",
        authors=["John Doe", "Jane Smith"],
        abstract="This is a test abstract for the document.",
    )
    builder.add_title_page()
    builder.add_abstract_page()
    builder.add_chapter(
        "Introduction",
        "<p>This is the introduction paragraph.</p>"
        "<p>This is another paragraph with more content.</p>",
    )
    builder.add_chapter(
        "Methods",
        "<p>This section describes the methods used.</p>",
    )
    builder.add_chapter(
        "Conclusion",
        "<p>This is the conclusion of the document.</p>",
    )
    builder.build(Path("test_output.epub"))
    print("Test EPUB created: test_output.epub")
