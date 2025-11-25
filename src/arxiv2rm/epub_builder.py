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
    line-height: 1.8;  /* Increased for better readability */
    margin: 1em;
    padding: 0;
    color: #000000;
    background-color: #ffffff;
    text-align: justify;
    hyphens: auto;
}

/* Headings */
h1 {
    font-size: 1.8em;
    font-weight: bold;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    text-align: left;
    page-break-after: avoid;
}

h2 {
    font-size: 1.4em;
    font-weight: bold;
    margin-top: 1.2em;
    margin-bottom: 0.4em;
    text-align: left;
    page-break-after: avoid;
}

h3 {
    font-size: 1.2em;
    font-weight: bold;
    margin-top: 1em;
    margin-bottom: 0.3em;
    text-align: left;
}

/* Paragraphs - increased spacing for visual separation */
p {
    margin-top: 0.8em;
    margin-bottom: 0.8em;
    text-indent: 0;  /* No indent for cleaner look */
}

/* Empty line between paragraphs effect */
p + p {
    margin-top: 1.2em;
}

p:first-of-type {
    margin-top: 0;
}

/* Paragraph breaks - visible spacing */
.para-break {
    height: 0.5em;
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

/* Code blocks */
pre, code {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.9em;
    background-color: #f5f5f5;
    border: 1px solid #cccccc;
    padding: 0.2em 0.4em;
}

pre {
    display: block;
    padding: 1em;
    margin: 1em 0;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
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
    margin: 1em 2em;
    padding: 0.5em 1em;
    border-left: 3px solid #666666;
    font-style: italic;
    background-color: #f9f9f9;
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
    page-break-before: always;
}

/* Notes zone - 20% of page height at bottom for handwriting annotations */
.notes-zone {
    margin-top: 2em;
    padding: 1em;
    border-top: 1px dashed #999999;
    min-height: 20vh;  /* 20% of viewport height */
    height: 20vh;
    color: #999999;
    font-size: 0.8em;
    font-style: italic;
    background-color: #fafafa;
}

.notes-zone::before {
    content: "Notes";
    display: block;
    margin-bottom: 0.5em;
    font-weight: bold;
}

/* Page section with notes area */
.page-section {
    margin-bottom: 2em;
    padding-bottom: 1em;
}

/* Inline figures (placed within content flow) */
.inline-figure {
    margin: 1.5em auto;
    max-width: 90%;
}

/* Citations/References styling */
.citation {
    margin-left: 2em;
    text-indent: -2em;  /* Hanging indent for citations */
    margin-bottom: 0.8em;
    font-size: 0.95em;
    line-height: 1.5;
}

/* Subsubsection headings */
h4 {
    font-size: 1.1em;
    font-weight: bold;
    margin-top: 0.8em;
    margin-bottom: 0.2em;
    text-align: left;
}

/* Page numbers (for PDF conversion) */
@page {
    margin: 2cm;
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

        # Check if this is a references section
        is_references = self._is_references_section(text)

        # Split into paragraphs
        paragraphs = self._split_paragraphs(text)

        html_parts = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check if it's a heading
            heading_level = self._detect_heading(para)
            if heading_level:
                html_parts.append(f"<h{heading_level}>{self._escape_html(para)}</h{heading_level}>")
            elif is_references and self._is_citation_entry(para):
                # Format as citation entry
                html_parts.append(self._format_citation(para))
            else:
                # Regular paragraph
                html_parts.append(f"<p>{self._escape_html(para)}</p>")

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

    def _format_citation(self, para: str) -> str:
        """Format a citation entry with proper styling."""
        # Escape HTML but preserve structure
        escaped = self._escape_html(para)
        # Add citation class for CSS styling
        return f'<p class="citation">{escaped}</p>'

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
