"""EPUB builder for reMarkable-optimized ebooks."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ebooklib import epub

from arxiv2rm.latex_processor import LaTeXDocument, Section

logger = logging.getLogger(__name__)


@dataclass
class EPUBMetadata:
    """Metadata for EPUB generation."""

    title: str
    authors: List[str] = field(default_factory=list)
    language: str = "en"
    publisher: str = "arxiv2rm"
    description: Optional[str] = None
    source_url: Optional[str] = None
    identifier: Optional[str] = None  # ISBN or UUID
    date: Optional[str] = None


class EPUBBuilder:
    """Build EPUB 3.0 books from LaTeX documents."""

    def __init__(
        self,
        metadata: EPUBMetadata,
        output_path: Optional[Path] = None,
    ):
        """
        Initialize EPUB builder.

        Args:
            metadata: EPUB metadata (title, authors, etc.)
            output_path: Path to save EPUB file
        """
        self.metadata = metadata
        self.output_path = output_path
        self.book = epub.EpubBook()
        self.chapters = []
        self.spine = ["nav"]
        self.toc = []
        self.latex_doc = None  # Store LaTeX doc for figure references

        # Generate UUID if not provided
        if not metadata.identifier:
            metadata.identifier = str(uuid.uuid4())

        # Set date if not provided
        if not metadata.date:
            metadata.date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"EPUBBuilder initialized: {metadata.title}")

    def build_from_latex(self, latex_doc: LaTeXDocument) -> epub.EpubBook:
        """
        Build EPUB from parsed LaTeX document.

        Args:
            latex_doc: Parsed LaTeX document

        Returns:
            EpubBook object ready to write
        """
        logger.info("Building EPUB from LaTeX document...")

        # Store latex_doc for figure references
        self.latex_doc = latex_doc

        # Use LaTeX metadata if available
        if latex_doc.title:
            self.metadata.title = latex_doc.title
        if latex_doc.authors:
            self.metadata.authors = latex_doc.authors

        # Set metadata
        self._set_metadata()

        # Create abstract chapter if present
        if latex_doc.abstract:
            self._add_abstract(latex_doc.abstract)

        # Create chapters from sections
        self._create_chapters_from_sections(latex_doc.sections)

        # Build navigation
        self._build_navigation()

        logger.info(f"EPUB built: {len(self.chapters)} chapters")
        return self.book

    def _set_metadata(self):
        """Set EPUB metadata from EPUBMetadata."""
        # Title
        self.book.set_title(self.metadata.title)

        # Language
        self.book.set_language(self.metadata.language)

        # Identifier (ISBN or UUID)
        self.book.set_identifier(self.metadata.identifier)

        # Authors
        for author in self.metadata.authors:
            self.book.add_author(author)

        # Publisher
        if self.metadata.publisher:
            self.book.add_metadata("DC", "publisher", self.metadata.publisher)

        # Description
        if self.metadata.description:
            self.book.add_metadata("DC", "description", self.metadata.description)

        # Date
        if self.metadata.date:
            self.book.add_metadata("DC", "date", self.metadata.date)

        # Source URL
        if self.metadata.source_url:
            self.book.add_metadata("DC", "source", self.metadata.source_url)

        logger.debug(f"Metadata set: {self.metadata.title}")

    def _add_abstract(self, abstract: str):
        """
        Add abstract as first chapter.

        Args:
            abstract: Abstract text
        """
        chapter = epub.EpubHtml(
            title="Abstract",
            file_name="abstract.xhtml",
            lang=self.metadata.language,
        )

        # Simple HTML content
        content = f"""
        <html>
        <head>
            <title>Abstract</title>
        </head>
        <body>
            <h1>Abstract</h1>
            <div class="abstract">
                <p>{self._escape_html(abstract)}</p>
            </div>
        </body>
        </html>
        """

        chapter.content = content.encode("utf-8")
        self.book.add_item(chapter)
        self.chapters.append(chapter)
        self.spine.append(chapter)
        self.toc.append(epub.Link("abstract.xhtml", "Abstract", "abstract"))

        logger.debug("Added abstract chapter")

    def _create_chapters_from_sections(self, sections: List[Section]):
        """
        Create EPUB chapters from LaTeX sections.

        Args:
            sections: List of LaTeX sections
        """
        # Group sections by level 1 (top-level sections)
        current_chapter = None
        chapter_sections = []

        for section in sections:
            if section.level == 1:
                # Save previous chapter if exists
                if current_chapter:
                    self._add_chapter(current_chapter, chapter_sections)

                # Start new chapter
                current_chapter = section
                chapter_sections = []
            else:
                # Add subsection to current chapter
                if current_chapter:
                    chapter_sections.append(section)
                else:
                    # Orphaned subsection - create chapter for it
                    logger.warning(f"Orphaned subsection: {section.title}")
                    current_chapter = section
                    chapter_sections = []

        # Add final chapter
        if current_chapter:
            self._add_chapter(current_chapter, chapter_sections)

        logger.debug(f"Created {len(self.chapters)} chapters from sections")

    def _add_chapter(self, main_section: Section, subsections: List[Section]):
        """
        Add a chapter to the EPUB.

        Args:
            main_section: Main section (level 1)
            subsections: Subsections within this chapter
        """
        # Sanitize filename
        file_name = self._sanitize_filename(main_section.title) + ".xhtml"

        chapter = epub.EpubHtml(
            title=main_section.title,
            file_name=file_name,
            lang=self.metadata.language,
        )

        # Build HTML content
        content = self._build_chapter_html(main_section, subsections)
        chapter.content = content.encode("utf-8")

        self.book.add_item(chapter)
        self.chapters.append(chapter)
        self.spine.append(chapter)
        self.toc.append(epub.Link(file_name, main_section.title, file_name))

        logger.debug(f"Added chapter: {main_section.title}")

    def _build_chapter_html(self, main_section: Section, subsections: List[Section]) -> str:
        """
        Build HTML content for a chapter.

        Args:
            main_section: Main section
            subsections: Subsections

        Returns:
            HTML content as string
        """
        html = f"""
        <html>
        <head>
            <title>{self._escape_html(main_section.title)}</title>
        </head>
        <body>
            <h1>{self._escape_html(main_section.title)}</h1>
        """

        # Main section content - split into paragraphs
        if main_section.content:
            paragraphs = main_section.content.split("\n\n")
            for para in paragraphs:
                para = para.strip()
                if para:
                    html += f"<p>{self._escape_html(para)}</p>\n"

        # Add figures for this chapter (if any)
        if self.latex_doc and self.latex_doc.figures:
            # Find figures that might belong to this chapter
            # (simple heuristic: include all figures for now, can be refined)
            for idx, figure in enumerate(self.latex_doc.figures):
                # Check if we've embedded this image
                figure_filename = f"figure_{idx + 1}_opt.jpg"

                caption_text = f": {self._escape_html(figure.caption)}" if figure.caption else ""
                html += f"""
            <figure id="fig{figure.number}">
                <img src="images/{figure_filename}" alt="Figure {figure.number}"/>
                <figcaption>Figure {figure.number}{caption_text}</figcaption>
            </figure>
"""

        # Subsections
        for subsection in subsections:
            heading_level = min(subsection.level, 6)  # h2-h6 (h1 is chapter title)
            html += f"<h{heading_level}>{self._escape_html(subsection.title)}</h{heading_level}>\n"
            if subsection.content:
                # Split subsection content into paragraphs too
                paragraphs = subsection.content.split("\n\n")
                for para in paragraphs:
                    para = para.strip()
                    if para:
                        html += f"<p>{self._escape_html(para)}</p>\n"

        html += """
        </body>
        </html>
        """

        return html

    def _build_navigation(self):
        """Build EPUB navigation (TOC)."""
        self.book.toc = tuple(self.toc)
        self.book.spine = self.spine

        # Add default NCX and Nav files
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())

        logger.debug("Navigation built")

    def add_css(self, css_content: str, file_name: str = "style.css"):
        """
        Add CSS stylesheet to EPUB.

        Args:
            css_content: CSS content as string
            file_name: CSS file name
        """
        css = epub.EpubItem(
            uid="style",
            file_name=file_name,
            media_type="text/css",
            content=css_content.encode("utf-8"),
        )
        self.book.add_item(css)

        # Apply CSS to all chapters
        for chapter in self.chapters:
            chapter.add_item(css)

        logger.debug(f"Added CSS: {file_name}")

    def add_font(self, font_path: Path, font_name: str):
        """
        Add font file to EPUB.

        Args:
            font_path: Path to font file (TTF/OTF)
            font_name: Font file name in EPUB
        """
        if not font_path.exists():
            raise ValueError(f"Font file not found: {font_path}")

        # Determine media type
        suffix = font_path.suffix.lower()
        if suffix == ".ttf":
            media_type = "font/ttf"
        elif suffix == ".otf":
            media_type = "font/otf"
        elif suffix == ".woff":
            media_type = "font/woff"
        elif suffix == ".woff2":
            media_type = "font/woff2"
        else:
            raise ValueError(f"Unsupported font format: {suffix}")

        font = epub.EpubItem(
            uid=f"font_{font_name}",
            file_name=f"fonts/{font_name}",
            media_type=media_type,
            content=font_path.read_bytes(),
        )
        self.book.add_item(font)

        logger.debug(f"Added font: {font_name}")

    def add_image(self, image_path: Path, image_name: Optional[str] = None):
        """
        Add image to EPUB.

        Args:
            image_path: Path to image file
            image_name: Image file name in EPUB (default: same as source)
        """
        if not image_path.exists():
            raise ValueError(f"Image file not found: {image_path}")

        if image_name is None:
            image_name = image_path.name

        # Determine media type
        suffix = image_path.suffix.lower()
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
        }

        media_type = media_types.get(suffix, "image/jpeg")

        image = epub.EpubItem(
            uid=f"image_{image_name}",
            file_name=f"images/{image_name}",
            media_type=media_type,
            content=image_path.read_bytes(),
        )
        self.book.add_item(image)

        logger.debug(f"Added image: {image_name}")

    def write(self, output_path: Optional[Path] = None):
        """
        Write EPUB to file.

        Args:
            output_path: Path to save EPUB file (overrides init path)
        """
        if output_path is None:
            output_path = self.output_path

        if output_path is None:
            raise ValueError("No output path specified")

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write EPUB
        epub.write_epub(str(output_path), self.book, {})

        logger.info(f"EPUB written: {output_path}")

    @staticmethod
    def _escape_html(text: str) -> str:
        """
        Escape HTML special characters.

        Args:
            text: Plain text

        Returns:
            HTML-escaped text
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """
        Sanitize string for use as filename.

        Args:
            name: Original name

        Returns:
            Sanitized filename (lowercase, alphanumeric + hyphens)
        """
        # Convert to lowercase
        name = name.lower()

        # Replace spaces with hyphens
        name = name.replace(" ", "-")

        # Keep only alphanumeric and hyphens
        name = "".join(c for c in name if c.isalnum() or c == "-")

        # Remove consecutive hyphens
        while "--" in name:
            name = name.replace("--", "-")

        # Trim hyphens from ends
        name = name.strip("-")

        # Limit length
        if len(name) > 50:
            name = name[:50].rstrip("-")

        return name or "chapter"


def build_epub(
    latex_doc: LaTeXDocument,
    output_path: Path,
    metadata: Optional[EPUBMetadata] = None,
) -> Path:
    """
    Convenience function to build EPUB from LaTeX document.

    Args:
        latex_doc: Parsed LaTeX document
        output_path: Path to save EPUB file
        metadata: Optional EPUB metadata (will use LaTeX metadata if None)

    Returns:
        Path to created EPUB file
    """
    # Create metadata from LaTeX if not provided
    if metadata is None:
        metadata = EPUBMetadata(
            title=latex_doc.title or "Untitled",
            authors=latex_doc.authors or [],
            description=latex_doc.abstract,
        )

    builder = EPUBBuilder(metadata, output_path)
    builder.build_from_latex(latex_doc)
    builder.write()

    return output_path
