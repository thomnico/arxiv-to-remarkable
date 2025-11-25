"""
PDF to EPUB Converter for reMarkable.

Main conversion pipeline that orchestrates:
1. PDF analysis and text extraction
2. Column detection and text reordering
3. Image extraction and optimization
4. EPUB generation with proper structure
"""

import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .column_detector import ColumnAwareExtractor
from .epub_builder import EPUBBuilder, TextToHTMLConverter
from .image_optimizer import ImageOptimizer, OptimizationSettings, RemarkableDevice
from .pdf_parser import PDFParser

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of PDF to EPUB conversion."""

    success: bool
    epub_path: Optional[Path] = None
    error: Optional[str] = None
    stats: Dict = field(default_factory=dict)


@dataclass
class ConversionOptions:
    """Options for PDF to EPUB conversion."""

    # Output settings
    output_path: Optional[Path] = None
    title: Optional[str] = None
    authors: Optional[List[str]] = None

    # Image settings
    optimize_images: bool = True
    image_quality: int = 85
    device: RemarkableDevice = RemarkableDevice.REMARKABLE_1

    # Text extraction settings
    detect_columns: bool = True
    ocr_engine: str = "local"  # "local", "groq", or "tesseract"

    # EPUB settings
    include_title_page: bool = True
    include_toc: bool = True

    # Processing settings
    temp_dir: Optional[Path] = None
    keep_temp: bool = False


class PDFToEPUBConverter:
    """
    Converts PDF documents to EPUB format optimized for reMarkable.

    Usage:
        converter = PDFToEPUBConverter()
        result = converter.convert("paper.pdf", "paper.epub")
    """

    def __init__(self, options: Optional[ConversionOptions] = None):
        """
        Initialize converter.

        Args:
            options: Conversion options (uses defaults if not provided)
        """
        self.options = options or ConversionOptions()
        self.pdf_parser = PDFParser(
            ocr_engine=self.options.ocr_engine,
            detect_columns=self.options.detect_columns,
        )
        self.image_optimizer = ImageOptimizer(
            OptimizationSettings(
                device=self.options.device,
                quality=self.options.image_quality,
            )
        )
        self.text_converter = TextToHTMLConverter()
        self.column_extractor = ColumnAwareExtractor()

    def convert(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        options: Optional[ConversionOptions] = None,
    ) -> ConversionResult:
        """
        Convert a PDF to EPUB.

        Args:
            input_path: Path to input PDF file
            output_path: Path for output EPUB (optional)
            options: Override options for this conversion

        Returns:
            ConversionResult with success status and output path
        """
        input_path = Path(input_path)
        options = options or self.options

        if not input_path.exists():
            return ConversionResult(
                success=False,
                error=f"Input file not found: {input_path}",
            )

        # Determine output path
        if output_path is None:
            output_path = options.output_path
        if output_path is None:
            output_path = input_path.with_suffix(".epub")
        output_path = Path(output_path)

        logger.info(f"Converting: {input_path} -> {output_path}")

        # Create temp directory for intermediate files
        temp_dir = options.temp_dir or Path(tempfile.mkdtemp(prefix="arxiv2rm_"))

        try:
            # Step 1: Extract matrix formulas FIRST (to exclude from text extraction)
            logger.info("Step 1: Extracting matrix formulas...")
            formula_dir = temp_dir / "formulas"
            formula_images = self.pdf_parser.extract_matrix_formulas(input_path, formula_dir)
            if formula_images:
                logger.info(f"Extracted {len(formula_images)} matrix formulas")

            # Step 2: Analyze and extract from PDF (with formula exclusions)
            logger.info("Step 2: Analyzing and extracting PDF...")
            # Pass formula regions to exclude their text from extraction
            pdf_result = self.pdf_parser.parse(
                input_path,
                temp_dir,
                exclude_regions=formula_images if formula_images else None,
            )
            analysis = pdf_result["analysis"]

            stats = {
                "pages": analysis["page_count"],
                "images": analysis["image_count"],
                "needs_ocr": analysis["needs_ocr"],
                "is_two_column": analysis.get("column_layout", {}).get("is_two_column", False),
                "formula_images": len(formula_images),
            }

            logger.info(
                f"PDF Analysis: {stats['pages']} pages, "
                f"{stats['images']} images, "
                f"OCR needed: {stats['needs_ocr']}, "
                f"Two-column: {stats['is_two_column']}, "
                f"Formula images: {stats['formula_images']}"
            )

            # Step 3: Extract and optimize images
            logger.info("Step 3: Optimizing images...")
            optimized_images = self._optimize_images(
                pdf_result.get("images", []),
                temp_dir / "optimized_images",
            )
            stats["optimized_images"] = len(optimized_images)

            # Step 4: Extract text content with inline figures and formulas
            logger.info("Step 4: Creating chapters...")
            pages = pdf_result.get("pages", [])
            chapters = self._create_chapters(pages, optimized_images, formula_images)
            stats["chapters"] = len(chapters)

            # Step 5: Build EPUB
            logger.info("Step 5: Building EPUB...")
            epub_path = self._build_epub(
                chapters,
                optimized_images,
                formula_images,
                output_path,
                options,
                input_path,
            )

            # Calculate output stats
            stats["output_size_kb"] = epub_path.stat().st_size / 1024
            stats["input_size_kb"] = input_path.stat().st_size / 1024

            logger.info(
                f"Conversion complete: {stats['output_size_kb']:.1f}KB EPUB "
                f"from {stats['input_size_kb']:.1f}KB PDF"
            )

            return ConversionResult(
                success=True,
                epub_path=epub_path,
                stats=stats,
            )

        except Exception as e:
            logger.error(f"Conversion failed: {e}")
            return ConversionResult(
                success=False,
                error=str(e),
            )

        finally:
            # Cleanup temp directory
            if not options.keep_temp and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {e}")

    def _optimize_images(
        self,
        images: List[Dict],
        output_dir: Path,
    ) -> List[Dict]:
        """
        Optimize extracted images for e-ink display.

        Args:
            images: List of image dicts from PDF parser
            output_dir: Directory for optimized images

        Returns:
            List of dicts with optimized_path, figure_num, page_num, type
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        results: List[Dict] = []

        for img_info in images:
            img_path = img_info.get("image_path")
            if not img_path:
                continue

            img_path = Path(img_path)
            if not img_path.exists():
                continue

            page_num = img_info.get("page_num", 0)
            img_idx = img_info.get("image_index", 0)
            figure_num = img_info.get("figure_num")  # May be None for embedded images
            img_type = img_info.get("type", "embedded")

            try:
                # Optimize image
                output_path = output_dir / f"img_p{page_num}_{img_idx}.jpg"
                optimized = self.image_optimizer.optimize(img_path, output_path)

                results.append(
                    {
                        "path": optimized,
                        "page_num": page_num,
                        "figure_num": figure_num,
                        "type": img_type,
                        "index": len(results),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to optimize image {img_path}: {e}")

        return results

    def _create_chapters(
        self,
        pages: List[Dict],
        optimized_images: List[Dict],
        formula_images: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """
        Create chapter structure from extracted pages with inline figures and formulas.

        Figures are inserted at their first mention in the text (e.g., "Figure 1", "Fig. 2").
        Matrix formulas are inserted at their page positions.

        Args:
            pages: List of page dicts with text content
            optimized_images: List of image dicts with path, figure_num, page_num, type
            formula_images: List of formula image dicts with page, bbox, img_path

        Returns:
            List of chapter dicts with title and HTML content
        """
        if not pages:
            return [{"title": "Content", "content": "<p>No content available.</p>"}]

        # Build figure lookup by figure_num for matching to text references
        # Also assign sequential numbers to figures without detected numbers
        figures_by_num: Dict[int, Dict] = {}
        next_unknown_num = 100  # High number for unmatched figures

        for img in optimized_images:
            fig_num = img.get("figure_num")
            if fig_num is not None:
                # Use detected figure number
                if fig_num not in figures_by_num:
                    figures_by_num[fig_num] = {
                        "img_path": img["path"],
                        "figure_num": fig_num,
                        "page_num": img["page_num"],
                        "inserted": False,
                    }
            else:
                # Assign a high number for figures without detected numbers
                figures_by_num[next_unknown_num] = {
                    "img_path": img["path"],
                    "figure_num": next_unknown_num,
                    "page_num": img["page_num"],
                    "inserted": False,
                    "is_unmatched": True,
                }
                next_unknown_num += 1

        # Convert to list sorted by figure number
        all_figures = [figures_by_num[k] for k in sorted(figures_by_num.keys())]

        # Build formula lookup by page (for chapter detection only)
        formulas_by_page: Dict[int, List[Dict]] = {}
        if formula_images:
            for formula in formula_images:
                page_num = formula.get("page", 0)
                if page_num not in formulas_by_page:
                    formulas_by_page[page_num] = []
                formulas_by_page[page_num].append(formula)

        # Combine all text from pages
        # NOTE: Formula placeholders are already inserted during text extraction
        # (in pdf_parser.py) so we don't need to add them here
        text_parts = []
        for page in pages:
            page_text = page.get("text", "")
            text_parts.append(page_text)

        all_text = "\n\n".join(text_parts)

        # First, try to detect chapter structure
        detected_chapters = self._detect_chapters_with_figures(
            all_text, all_figures, pages, formulas_by_page
        )

        if not detected_chapters:
            # No clear chapter structure - create single chapter
            # NOTE: Formula placeholders in text will be converted to HTML
            # by _insert_figures_at_mentions via the formula_pattern regex
            html_content = self._insert_figures_at_mentions(all_text, all_figures)
            html_content += '\n<div class="notes-zone"></div>'
            return [{"title": "Content", "content": html_content}]
        else:
            # Add notes zone to each chapter
            for chapter in detected_chapters:
                chapter["content"] += '\n<div class="notes-zone"></div>'
            return detected_chapters

    def _generate_formula_html(self, formulas: List[Dict]) -> str:
        """Generate HTML for formula images."""
        if not formulas:
            return ""

        html_parts = []
        for formula in formulas:
            img_path = formula.get("img_path")
            if img_path:
                img_name = Path(img_path).name
                page_num = formula.get("page", 0) + 1
                html_parts.append(
                    f"""
<figure class="formula-figure">
    <img src="images/{img_name}" alt="Formula from page {page_num}" class="formula-img"/>
</figure>
"""
                )
        return "\n".join(html_parts)

    def _insert_figures_at_mentions(
        self,
        text: str,
        figures: List[Dict],
        append_remaining: bool = False,
    ) -> str:
        """
        Convert text to HTML and insert figures at their first mention.

        Args:
            text: Plain text content
            figures: List of figure dicts with img_path, figure_num, inserted flag
            append_remaining: If True, append remaining figures at end (last chapter only)

        Returns:
            HTML content with figures inserted at first mention
        """
        import re

        # Convert text to HTML first
        html = self.text_converter.convert(text)

        # Convert formula placeholders to actual HTML
        # Pattern: [FORMULA_IMAGE:filename.png:pageN]
        formula_pattern = re.compile(r"\[FORMULA_IMAGE:([^:]+):page(\d+)\]")

        def formula_replacement(match):
            img_name = match.group(1)
            page_num = match.group(2)
            return f"""
<figure class="formula-figure">
    <img src="images/{img_name}" alt="Formula from page {page_num}" class="formula-img"/>
</figure>
"""

        html = formula_pattern.sub(formula_replacement, html)

        # Build lookup from figure number to figure dict
        figures_by_num: Dict[int, Dict] = {}
        for fig in figures:
            fig_num = fig.get("figure_num")
            if fig_num is not None and fig_num not in figures_by_num:
                figures_by_num[fig_num] = fig

        # Pattern to find figure references
        # Matches: "Figure 1", "Fig. 1", "Figure 2a", "Figures 1-3", etc.
        fig_pattern = re.compile(
            r"(Fig(?:ure|\.)\s*(\d+)(?:[a-z])?(?:\s*[-–]\s*\d+)?)", re.IGNORECASE
        )

        # Track which figures have been inserted in THIS chapter
        inserted_fig_nums = set()

        # Find all figure mentions and their positions
        mentions = []
        for match in fig_pattern.finditer(html):
            fig_num = int(match.group(2))
            mentions.append(
                {
                    "match": match,
                    "fig_num": fig_num,
                    "end_pos": match.end(),
                }
            )

        # Sort mentions by position (process from end to avoid offset issues)
        mentions.sort(key=lambda x: x["end_pos"], reverse=True)

        # Insert figures at first mention (working backwards through the text)
        for mention in mentions:
            fig_num = mention["fig_num"]

            # Skip if already inserted in this chapter or no matching figure
            if fig_num in inserted_fig_nums or fig_num not in figures_by_num:
                continue

            fig = figures_by_num[fig_num]
            if fig.get("inserted"):
                continue

            # Find the end of the paragraph containing this mention
            end_pos = mention["end_pos"]

            # Look for </p> after the mention
            para_end = html.find("</p>", end_pos)
            if para_end == -1:
                para_end = end_pos
            else:
                para_end += 4  # Include </p>

            # Create figure HTML
            img_ref = f"images/{fig['img_path'].name}"
            caption = f"Figure {fig_num}"
            figure_html = f"""
<figure class="inline-figure">
    <img src="{img_ref}" alt="{caption}"/>
    <figcaption>{caption}</figcaption>
</figure>
"""
            # Insert figure after the paragraph
            html = html[:para_end] + figure_html + html[para_end:]

            # Mark as inserted (globally)
            inserted_fig_nums.add(fig_num)
            fig["inserted"] = True

        # Only append remaining figures if this is the last chapter
        if append_remaining:
            remaining_html = ""
            for fig in figures:
                if not fig.get("inserted"):
                    img_ref = f"images/{fig['img_path'].name}"
                    fig_num = fig.get("figure_num", "?")
                    # Don't show high numbers for unmatched figures
                    if fig.get("is_unmatched"):
                        caption = "Figure"
                    else:
                        caption = f"Figure {fig_num}"
                    remaining_html += f"""
<figure class="inline-figure">
    <img src="{img_ref}" alt="{caption}"/>
    <figcaption>{caption}</figcaption>
</figure>
"""
                    fig["inserted"] = True
            html += remaining_html

        return html

    def _detect_chapters_with_figures(
        self,
        text: str,
        figures: List[Dict],
        pages: List[Dict],
        formulas_by_page: Optional[Dict[int, List[Dict]]] = None,
    ) -> List[Dict]:
        """
        Detect chapters and insert figures/formulas at their positions.

        Args:
            text: Full document text
            figures: List of figure dicts
            pages: List of page dicts
            formulas_by_page: Dict mapping page number to formula dicts

        Returns:
            List of chapter dicts with title and content (figures at first mention)
        """
        formulas_by_page = formulas_by_page or {}
        # Split text into lines
        lines = text.split("\n")
        chapters = []

        # First pass: collect all chapter boundaries
        chapter_boundaries = []  # List of (title, start_line_idx)
        pre_chapter_end = None

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            if not line_stripped:
                continue

            # Check if this line is a section/subsection heading
            heading_level = self._detect_heading_level(line_stripped)

            # Only create new chapters for major sections (level 1-2)
            if heading_level > 0 and heading_level <= 2:
                if pre_chapter_end is None:
                    pre_chapter_end = i
                chapter_boundaries.append((line_stripped, i))

        # Second pass: create chapters with proper figure placement
        if not chapter_boundaries:
            return []  # No chapters detected

        # Handle pre-chapter content
        if pre_chapter_end and pre_chapter_end > 0:
            pre_text = "\n".join(lines[:pre_chapter_end])
            if pre_text.strip():
                html_content = self._insert_figures_at_mentions(
                    pre_text, figures, append_remaining=False
                )
                chapters.append({"title": "Introduction", "content": html_content})

        # Process each chapter
        for idx, (title, start_idx) in enumerate(chapter_boundaries):
            # Find end of this chapter (start of next chapter or end of text)
            if idx + 1 < len(chapter_boundaries):
                end_idx = chapter_boundaries[idx + 1][1]
            else:
                end_idx = len(lines)

            # Get chapter content (skip the title line itself)
            chapter_lines = lines[start_idx + 1 : end_idx]
            content_text = "\n".join(chapter_lines)

            # Only append remaining figures in the LAST chapter
            is_last_chapter = idx == len(chapter_boundaries) - 1
            html_content = self._insert_figures_at_mentions(
                content_text, figures, append_remaining=is_last_chapter
            )

            chapters.append({"title": title, "content": html_content})

        return chapters

    def _detect_heading_level(self, text: str) -> int:
        """
        Detect if text is a section heading and return its level.

        Returns:
            0 if not a heading, 1 for major sections, 2 for subsections, 3 for subsubsections
        """
        import re

        text = text.strip()

        # Must be reasonably short to be a heading
        if len(text) > 80:
            return 0

        # Must not end with common sentence punctuation (list items often end with comma/period)
        if text.endswith((",", ";", ":", "?", "!")):
            return 0

        # If ends with period, only accept if it's section number period (e.g., "1. Intro")
        # Not a sentence ending (e.g., "1. Read these documents.")
        if text.endswith("."):
            # Only allow if pattern is "N. Title" and title is short (2-4 words)
            if not re.match(r"^\d+\.\s+[A-Z][a-z]+(?:\s+[A-Za-z]+){0,3}$", text):
                return 0

        # Subsubsection: "4.1.1 Title" or "4.1.1. Title"
        if re.match(r"^\d+\.\d+\.\d+\.?\s+[A-Z][A-Za-z]", text):
            words = text.split()
            if len(words) <= 10:
                return 3

        # Subsection: "2.1 Title" or "2.1. Title"
        if re.match(r"^\d+\.\d+\.?\s+[A-Z][A-Za-z]", text):
            words = text.split()
            if len(words) <= 10:
                return 2

        # Pattern for numbered sections: "1. Introduction", "2 Background", etc.
        # Major section: single digit, e.g., "1 Title" (no period after number)
        # or "1. Title" where title is clearly a section name
        if re.match(r"^\d+\.?\s+[A-Z][A-Za-z]", text):
            words = text.split()
            # Must be title-like: 2-6 words, first word after number is capitalized
            # and NOT a typical sentence start like verbs
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
                    # Also exclude garbled text (very long "words" indicate missing spaces)
                    first_title_word = words[1] if len(words) > 1 else ""
                    if len(first_title_word) <= 20:  # Normal words are < 20 chars
                        return 1

        # Standalone section names (without numbers)
        standalone_sections = [
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
        text_lower = text.lower()
        if text_lower in standalone_sections:
            return 1

        # Sections with colon-separated subtitles (e.g., "Discussion: Some Subtitle")
        # These are major sections when they start with a known section keyword
        for section_kw in [
            "discussion",
            "conclusion",
            "results",
            "method",
            "introduction",
            "background",
            "conceptual",
        ]:
            if text_lower.startswith(section_kw + ":") or text_lower.startswith(
                section_kw + " flow"
            ):
                return 1

        # Appendix sections: "Appendix A", "Appendix B. Tables", etc.
        if re.match(r"^appendix\s+[a-z]\.?\s*", text, re.IGNORECASE):
            return 1

        # Title Case headings that are short (3-6 words) and end without punctuation
        # This catches things like "Discussion: From Individual Incident to Structural Pathology"
        # Must be strict: pre-colon must be a known section keyword
        if ":" in text:
            title_words = text.split()
            if 3 <= len(title_words) <= 10:
                pre_colon = text.split(":")[0].strip().lower()
                # Only match if pre-colon is a known section name
                known_pre_colon = [
                    "discussion",
                    "conclusion",
                    "results",
                    "methods",
                    "introduction",
                    "background",
                    "conceptual flow",
                ]
                if pre_colon in known_pre_colon:
                    return 1

        return 0

    def _detect_chapters(self, text: str) -> List[Dict]:
        """
        Detect chapter/section structure from text.

        Only detects major sections (single digit numbering like "1 Introduction")
        to avoid splitting on subsections like "2.2 Details".

        Args:
            text: Full document text

        Returns:
            List of chapter dicts with title and content
        """
        import re

        # Major section patterns only (not subsections like 2.1, 2.2)
        # Must be specific academic section names to avoid false positives
        section_patterns = [
            r"^Abstract$",
            r"^(\d+)\.\s*Introduction$",
            r"^(\d+)\.\s*Background$",
            r"^(\d+)\.\s*Related\s+Work$",
            r"^(\d+)\.\s*Methods?$",
            r"^(\d+)\.\s*Methodology$",
            r"^(\d+)\.\s*Results?$",
            r"^(\d+)\.\s*Discussion$",
            r"^(\d+)\.\s*Conclusions?$",
            r"^(\d+)\.\s*References?$",
            r"^(\d+)\.\s*Acknowledgm?ents?$",
            r"^(\d+)\.\s*Limitations?$",
            r"^(\d+)\.\s*Future\s+Work$",
            # Also match without period: "1 Introduction"
            r"^(\d+)\s+Introduction$",
            r"^(\d+)\s+Background$",
            r"^(\d+)\s+Related\s+Work$",
            r"^(\d+)\s+Methods?$",
            r"^(\d+)\s+Methodology$",
            r"^(\d+)\s+Results?$",
            r"^(\d+)\s+Discussion$",
            r"^(\d+)\s+Conclusions?$",
            r"^(\d+)\s+References?$",
            r"^(\d+)\s+Acknowledgm?ents?$",
            r"^(\d+)\s+Limitations?$",
            r"^(\d+)\s+Future\s+Work$",
        ]

        # Split text into lines for processing
        lines = text.split("\n")
        chapters = []
        current_title = None
        current_content = []

        for line in lines:
            line_stripped = line.strip()

            # Skip empty lines for heading detection
            if not line_stripped:
                current_content.append(line)
                continue

            # Headings must be short (< 60 chars) and NOT subsections
            is_heading = False
            if len(line_stripped) < 60:
                # Skip subsections like "2.1 Title"
                if re.match(r"^\d+\.\d+", line_stripped):
                    is_heading = False
                else:
                    for pattern in section_patterns:
                        if re.match(pattern, line_stripped, re.IGNORECASE):
                            is_heading = True
                            break

            if is_heading:
                # Save previous chapter
                if current_title:
                    content = "\n".join(current_content)
                    html_content = self.text_converter.convert(content)
                    chapters.append({"title": current_title, "content": html_content})

                # Start new chapter
                current_title = line_stripped
                current_content = []
            else:
                current_content.append(line)

        # Save last chapter
        if current_title:
            content = "\n".join(current_content)
            html_content = self.text_converter.convert(content)
            chapters.append({"title": current_title, "content": html_content})

        return chapters

    def _build_epub(
        self,
        chapters: List[Dict],
        optimized_images: List[Dict],
        formula_images: List[Dict],
        output_path: Path,
        options: ConversionOptions,
        input_path: Path,
    ) -> Path:
        """
        Build the EPUB file.

        Args:
            chapters: List of chapter dicts
            optimized_images: List of image dicts with path, figure_num, page_num
            formula_images: List of formula image dicts with page, bbox, img_path
            output_path: Output path for EPUB
            options: Conversion options
            input_path: Original input PDF path

        Returns:
            Path to created EPUB file
        """
        builder = EPUBBuilder()

        # Set metadata
        title = options.title or input_path.stem.replace("_", " ").replace("-", " ").title()
        authors = options.authors or []

        builder.set_metadata(
            title=title,
            authors=authors,
            language="en",
            source_url=str(input_path),
        )

        # Set cover image from first image (if available)
        if optimized_images:
            # Sort by page number to get first page's image
            sorted_images = sorted(
                optimized_images, key=lambda x: (x.get("page_num", 0), x.get("index", 0))
            )
            if sorted_images:
                cover_path = sorted_images[0]["path"]
                builder.set_cover_image(cover_path)

        # Add title page
        if options.include_title_page:
            builder.add_title_page()

        # Add all images to EPUB manifest
        for img in optimized_images:
            builder.add_image(img["path"])

        # Add formula images to EPUB manifest
        for formula in formula_images:
            img_path = formula.get("img_path")
            if img_path:
                builder.add_image(img_path)

        # Add chapters
        for chapter in chapters:
            builder.add_chapter(
                title=chapter["title"],
                content=chapter["content"],
            )

        # Build EPUB
        return builder.build(output_path)


def convert_pdf_to_epub(
    input_path: Path,
    output_path: Optional[Path] = None,
    title: Optional[str] = None,
    authors: Optional[List[str]] = None,
    optimize_images: bool = True,
    detect_columns: bool = True,
) -> ConversionResult:
    """
    Convenience function to convert a PDF to EPUB.

    Args:
        input_path: Path to input PDF
        output_path: Path for output EPUB (optional)
        title: Document title (optional)
        authors: List of authors (optional)
        optimize_images: Whether to optimize images for e-ink
        detect_columns: Whether to detect multi-column layouts

    Returns:
        ConversionResult with success status and output path
    """
    options = ConversionOptions(
        output_path=output_path,
        title=title,
        authors=authors,
        optimize_images=optimize_images,
        detect_columns=detect_columns,
    )

    converter = PDFToEPUBConverter(options)
    return converter.convert(input_path, output_path)


# Example usage
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

        result = convert_pdf_to_epub(input_path, output_path)

        if result.success:
            print(f"Conversion successful: {result.epub_path}")
            print(f"Stats: {result.stats}")
        else:
            print(f"Conversion failed: {result.error}")
    else:
        print("Usage: python converter.py <input.pdf> [output.epub]")
