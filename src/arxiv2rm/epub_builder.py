"""EPUB builder for reMarkable-optimized ebooks."""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ebooklib import epub

from arxiv2rm.latex_processor import Figure, LaTeXDocument, Section, Table
from arxiv2rm.math_renderer import MathFormula, MathRenderer

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
        render_math: bool = True,
    ):
        """
        Initialize EPUB builder.

        Args:
            metadata: EPUB metadata (title, authors, etc.)
            output_path: Path to save EPUB file
            render_math: Whether to render math formulas to images (default: True)
        """
        self.metadata = metadata
        self.output_path = output_path
        self.book = epub.EpubBook()
        self.chapters = []
        self.spine = ["nav"]
        self.toc = []
        self.latex_doc = None  # Store LaTeX doc for figure references
        self.render_math = render_math
        self.math_renderer = MathRenderer() if render_math else None
        self.rendered_math: Dict[str, Path] = {}  # formula_id -> image path
        self.globally_placed_figures: set = set()  # Track figures placed in chapters
        self.globally_placed_tables: set = set()  # Track tables placed in chapters

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

        # Render math formulas if enabled
        if self.render_math and latex_doc.math_formulas:
            self._render_math_formulas(latex_doc.math_formulas)

        # Create abstract chapter if present
        if latex_doc.abstract:
            self._add_abstract(latex_doc.abstract)

        # Create chapters from sections
        self._create_chapters_from_sections(latex_doc.sections)

        # Add appendix for unmatched figures and tables
        self._add_figures_tables_appendix()

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
        Build HTML content for a chapter with inline figure/table placement.

        Figures and tables are placed immediately after the paragraph where they
        are first referenced, using <<<REF:label>>> markers in the content.

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

        # Track which figures/tables have been placed to avoid duplicates
        placed_figures = set()
        placed_tables = set()

        # Helper function to process content with inline reference placement
        def process_content_with_inline_refs(content: str) -> str:
            if not content:
                return ""

            paragraphs = content.split("\n\n")
            html_parts = []

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # Find all reference markers in this paragraph
                refs_in_para = re.findall(r"<<<REF:([^>]+)>>>", para)

                # Replace markers with readable text
                for ref_label in refs_in_para:
                    if ref_label.startswith("fig:"):
                        fig_result = self._find_figure_by_label(ref_label)
                        if fig_result:
                            _, fig = fig_result
                            para = para.replace(f"<<<REF:{ref_label}>>>", f"Figure {fig.number}")
                        else:
                            # Reference not found, just remove marker
                            para = para.replace(f"<<<REF:{ref_label}>>>", "")
                    elif ref_label.startswith("tab:"):
                        table = self._find_table_by_label(ref_label)
                        if table:
                            para = para.replace(f"<<<REF:{ref_label}>>>", f"Table {table.number}")
                        else:
                            # Reference not found, just remove marker
                            para = para.replace(f"<<<REF:{ref_label}>>>", "")

                # Add paragraph HTML
                html_parts.append(f"<p>{self._escape_html(para)}</p>\n")

                # Check if this is the FIRST reference to any figure/table in this paragraph
                for ref_label in refs_in_para:
                    if ref_label.startswith("fig:"):
                        fig_result = self._find_figure_by_label(ref_label)
                        if fig_result:
                            _, fig = fig_result
                            if fig.number not in placed_figures:
                                # Render and insert figure HTML immediately
                                fig_html = self._render_figure_html(fig)
                                if fig_html:
                                    html_parts.append(fig_html)
                                    placed_figures.add(fig.number)
                                    self.globally_placed_figures.add(fig.number)

                    elif ref_label.startswith("tab:"):
                        table = self._find_table_by_label(ref_label)
                        if table and table.number not in placed_tables:
                            # Render and insert table HTML immediately
                            table_html = self._render_table_html(table)
                            if table_html:
                                html_parts.append(table_html)
                                placed_tables.add(table.number)
                                self.globally_placed_tables.add(table.number)

            return "".join(html_parts)

        # Process main section content
        html += process_content_with_inline_refs(main_section.content)

        # Process subsections
        for subsection in subsections:
            heading_level = min(subsection.level, 6)  # h2-h6 (h1 is chapter title)
            html += f"<h{heading_level}>{self._escape_html(subsection.title)}</h{heading_level}>\n"
            html += process_content_with_inline_refs(subsection.content)

        # Add any unplaced figures/tables that belong to this chapter at the end
        # (fallback for figures without references or with broken references)
        if self.latex_doc:
            chapter_section_titles = {main_section.title}
            for subsection in subsections:
                chapter_section_titles.add(subsection.title)

            # Add unplaced figures
            for fig in self.latex_doc.figures:
                if (
                    fig.source_section in chapter_section_titles
                    and fig.number not in placed_figures
                ):
                    fig_html = self._render_figure_html(fig)
                    if fig_html:
                        html += fig_html
                        placed_figures.add(fig.number)
                        self.globally_placed_figures.add(fig.number)

            # Add unplaced tables
            for table in self.latex_doc.tables:
                if (
                    table.source_section in chapter_section_titles
                    and table.number not in placed_tables
                ):
                    table_html = self._render_table_html(table)
                    if table_html:
                        html += table_html
                        placed_tables.add(table.number)
                        self.globally_placed_tables.add(table.number)

        # Add notes section at the end of the chapter
        html += self._build_notes_section()

        html += """
        </body>
        </html>
        """

        # Replace math formulas with images if enabled
        if self.render_math:
            html = self._replace_math_in_content(html)

        return html

    def _render_figure_html(self, figure: Figure) -> str:
        """
        Render a single figure as HTML.

        Args:
            figure: Figure object to render

        Returns:
            HTML string for the figure
        """
        from pathlib import Path

        # Skip PDF figures
        if figure.image_path and figure.image_path.endswith(".pdf"):
            return ""

        # Determine image filename
        if figure.image_path:
            img_stem = Path(figure.image_path).stem.replace("-", "_").replace(" ", "_")
            figure_filename = f"{img_stem}_opt.jpg"
        else:
            figure_filename = f"figure_{figure.number}_opt.jpg"

        caption_text = f": {self._escape_html(figure.caption)}" if figure.caption else ""

        return f"""
            <figure id="fig{figure.number}">
                <img src="images/{figure_filename}" alt="Figure {figure.number}"/>
                <figcaption>Figure {figure.number}{caption_text}</figcaption>
            </figure>
"""

    def _render_table_html(self, table: Table) -> str:
        """
        Render a single table as HTML (as image if available).

        Args:
            table: Table object to render

        Returns:
            HTML string for the table
        """
        # Only render tables that have been converted to images
        if not table.image_path:
            return ""

        table_filename = f"table_{table.number}.png"
        caption_text = f": {self._escape_html(table.caption)}" if table.caption else ""

        return f"""
            <figure class="table-figure" id="tab{table.number}">
                <img src="images/{table_filename}" alt="Table {table.number}"/>
                <figcaption>Table {table.number}{caption_text}</figcaption>
            </figure>
"""

    def _find_figure_by_label(self, label: str) -> Optional[tuple[int, Figure]]:
        """
        Find figure by label.

        Args:
            label: Figure label (e.g., "fig:architecture")

        Returns:
            Tuple of (index, Figure) or None if not found
        """
        if not self.latex_doc:
            return None

        for idx, fig in enumerate(self.latex_doc.figures):
            if fig.label == label:
                return (idx, fig)

        return None

    def _find_table_by_label(self, label: str) -> Optional[Table]:
        """
        Find table by label.

        Args:
            label: Table label (e.g., "tab:results")

        Returns:
            Table object or None if not found
        """
        if not self.latex_doc:
            return None

        for table in self.latex_doc.tables:
            if table.label == label:
                return table

        return None

    def _add_figures_tables_appendix(self):
        """
        Add an appendix chapter with all unmatched figures and tables.

        This catches figures/tables that couldn't be matched to a specific section
        (i.e., those with source_section=None).
        """
        if not self.latex_doc:
            return

        # Collect all sections that were used in chapters
        used_sections = set()
        for section in self.latex_doc.sections:
            if section.level == 1:
                used_sections.add(section.title)

        # Find unmatched figures that were NOT already placed in chapters
        unmatched_figures = [
            fig
            for fig in self.latex_doc.figures
            if (not fig.source_section or fig.source_section not in used_sections)
            and fig.number not in self.globally_placed_figures
        ]

        # Find unmatched tables that were NOT already placed in chapters
        unmatched_tables = [
            table
            for table in self.latex_doc.tables
            if (not table.source_section or table.source_section not in used_sections)
            and table.number not in self.globally_placed_tables
        ]

        # Only create appendix if there are unmatched items
        if not unmatched_figures and not unmatched_tables:
            logger.debug("No unmatched figures or tables, skipping appendix")
            return

        logger.info(
            f"Creating appendix for {len(unmatched_figures)} figures "
            f"and {len(unmatched_tables)} tables"
        )

        # Create appendix chapter
        chapter = epub.EpubHtml(
            title="Figures and Tables",
            file_name="appendix_figures_tables.xhtml",
            lang=self.metadata.language,
        )

        # Build HTML content
        html = """
        <html>
        <head>
            <title>Figures and Tables</title>
        </head>
        <body>
            <h1>Figures and Tables</h1>
            <p style="font-style: italic; color: #666;">
            This appendix contains figures and tables that could not be
            automatically placed in their corresponding sections.
            </p>
        """

        # Add unmatched figures
        for figure in unmatched_figures:
            # Skip PDF figures
            if figure.image_path and figure.image_path.endswith(".pdf"):
                logger.debug(f"Skipping PDF figure {figure.number}")
                continue

            # Determine image filename
            if figure.image_path:
                from pathlib import Path

                img_stem = Path(figure.image_path).stem.replace("-", "_").replace(" ", "_")
                figure_filename = f"{img_stem}_opt.jpg"
            else:
                figure_filename = f"figure_{figure.number}_opt.jpg"

            caption_text = f": {self._escape_html(figure.caption)}" if figure.caption else ""
            html += f"""
            <figure id="fig{figure.number}">
                <img src="images/{figure_filename}" alt="Figure {figure.number}"/>
                <figcaption>Figure {figure.number}{caption_text}</figcaption>
            </figure>
"""

        # Add unmatched tables
        for table in unmatched_tables:
            # Only add tables that have been rendered to images
            if not table.image_path:
                logger.debug(f"Skipping table {table.number}: no rendered image")
                continue

            table_filename = f"table_{table.number}.png"
            caption_text = f": {self._escape_html(table.caption)}" if table.caption else ""
            html += f"""
            <figure class="table-figure" id="tab{table.number}">
                <img src="images/{table_filename}" alt="Table {table.number}"/>
                <figcaption>Table {table.number}{caption_text}</figcaption>
            </figure>
"""

        # Add notes section
        html += self._build_notes_section()

        html += """
        </body>
        </html>
        """

        chapter.content = html.encode("utf-8")
        self.book.add_item(chapter)
        self.chapters.append(chapter)
        self.spine.append(chapter)
        self.toc.append(
            epub.Link("appendix_figures_tables.xhtml", "Figures and Tables", "appendix")
        )

        logger.debug("Added Figures and Tables appendix")

    def _build_notes_section(self) -> str:
        """
        Build a notes section for handwritten annotations.

        Creates a blank area with ruled lines that takes up approximately
        20% of the vertical space, suitable for reMarkable stylus notes.

        Returns:
            HTML string for notes section
        """
        # Create a section with ruled lines for notes
        # Using multiple divs with border-bottom to create ruled lines
        lines = []
        line_style = "height: 2em; border-bottom: 1px solid #CCCCCC; margin: 0;"
        for i in range(8):  # 8 ruled lines for notes
            lines.append(f'<div class="notes-line" style="{line_style}"></div>')

        notes_style = "margin-top: 4em; padding-top: 1em; " "border-top: 2px solid #000000;"
        label_style = "font-size: 10pt; font-style: italic; " "color: #666666; margin-bottom: 1em;"

        notes_html = f"""
        <div class="notes-section" style="{notes_style}">
            <p style="{label_style}">Notes:</p>
            {''.join(lines)}
        </div>
        """
        return notes_html

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

    def _render_math_formulas(self, formulas: List[MathFormula]):
        """
        Render math formulas to images and add to EPUB.

        Args:
            formulas: List of math formulas to render
        """
        import tempfile

        logger.info(f"Rendering {len(formulas)} math formulas...")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            for formula in formulas:
                try:
                    # Render formula to image
                    output_path = tmpdir_path / f"{formula.formula_id}.png"
                    rendered_path = self.math_renderer.render(formula, output_path)

                    if rendered_path:
                        # Add image to EPUB
                        self.add_image(rendered_path, f"{formula.formula_id}.png")
                        self.rendered_math[formula.formula_id] = rendered_path
                        logger.debug(f"Rendered math formula: {formula.formula_id}")
                    else:
                        logger.warning(f"Failed to render math formula: {formula.formula_id}")

                except Exception as e:
                    logger.error(f"Error rendering math {formula.formula_id}: {e}")

        logger.info(f"Rendered {len(self.rendered_math)} math formulas")

    def _replace_math_in_content(self, content: str) -> str:
        """
        Replace LaTeX math with image tags in HTML content.

        Args:
            content: HTML content with LaTeX math

        Returns:
            HTML content with math replaced by images
        """
        if not self.render_math or not self.latex_doc:
            return content

        # Replace inline math: $...$
        def replace_inline(match):
            latex_code = match.group(1)
            # Find matching formula
            for formula in self.latex_doc.math_formulas:
                if formula.latex_code == latex_code and not formula.is_display:
                    if formula.formula_id in self.rendered_math:
                        return (
                            f'<span class="math-inline">'
                            f'<img src="images/{formula.formula_id}.png" '
                            f'alt="{self._escape_html(latex_code)}" '
                            f'style="display: inline; vertical-align: middle;"/>'
                            f"</span>"
                        )
            # If not found, leave as-is
            return match.group(0)

        content = re.sub(r"\$([^\$]+)\$", replace_inline, content)

        # Replace display math environments
        display_envs = ["equation", "equation*", "align", "align*", "eqnarray", "eqnarray*"]
        for env in display_envs:
            pattern = rf"\\begin\{{{env}\}}(.*?)\\end\{{{env}\}}"

            def replace_display(match):
                latex_code = match.group(1).strip()
                # Find matching formula
                for formula in self.latex_doc.math_formulas:
                    if formula.latex_code == latex_code and formula.is_display:
                        if formula.formula_id in self.rendered_math:
                            return (
                                f'<div class="math-display">'
                                f'<img src="images/{formula.formula_id}.png" '
                                f'alt="{self._escape_html(latex_code)}" '
                                f'class="equation-image"/>'
                                f"</div>"
                            )
                # If not found, leave as-is
                return match.group(0)

            content = re.sub(pattern, replace_display, content, flags=re.DOTALL)

        # Replace \[...\] display math
        def replace_bracket_display(match):
            latex_code = match.group(1).strip()
            # Find matching formula
            for formula in self.latex_doc.math_formulas:
                if formula.latex_code == latex_code and formula.is_display:
                    if formula.formula_id in self.rendered_math:
                        return (
                            f'<div class="math-display">'
                            f'<img src="images/{formula.formula_id}.png" '
                            f'alt="{self._escape_html(latex_code)}" '
                            f'class="equation-image"/>'
                            f"</div>"
                        )
            # If not found, leave as-is
            return match.group(0)

        content = re.sub(r"\\\[(.*?)\\\]", replace_bracket_display, content, flags=re.DOTALL)

        return content

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
