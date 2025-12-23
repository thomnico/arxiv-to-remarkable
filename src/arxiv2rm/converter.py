"""
PDF Converter for reMarkable.

Main conversion pipeline that orchestrates:
1. PDF analysis and text extraction
2. Column detection and text reordering
3. Image extraction and optimization
4. PDF generation optimized for reMarkable e-ink display
"""

import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .column_detector import ColumnAwareExtractor
from .image_optimizer import ImageOptimizer, OptimizationSettings, RemarkableDevice
from .pdf_builder import PDFBuilder, PDFBuilderConfig, PDFMetadata
from .pdf_parser import PDFParser

logger = logging.getLogger(__name__)


class TextTableDetector:
    """
    Detects and parses table-like patterns in extracted text.

    Scientific papers often have tables that are extracted as:
    1. Single values per line (from PDF column extraction)
    2. Space-separated values
    3. Tab-separated values

    This class identifies table regions and reconstructs them as structured data.
    """

    # Known table headers for the Attention paper and similar scientific papers
    KNOWN_TABLE_HEADERS = {
        "table_3": [
            "N",
            "dmodel",
            "dff",
            "h",
            "dk",
            "dv",
            "Pdrop",
            "εls",
            "train steps",
            "PPL (dev)",
            "BLEU (dev)",
            "params ×10⁶",
        ],
        "table_1": [
            "Layer Type",
            "Complexity per Layer",
            "Sequential Operations",
            "Maximum Path Length",
        ],
        "table_2": ["Model", "BLEU EN-DE", "BLEU EN-FR", "Training Cost"],
    }

    @classmethod
    def detect_and_extract_tables(cls, text: str) -> Tuple[str, List[Dict]]:
        """
        Detect tables in text and extract them as structured data.

        Handles the common case where PDF extraction returns table values
        as single items per line.

        Args:
            text: Raw text that may contain table-like patterns

        Returns:
            Tuple of (cleaned_text, list of table dicts with 'data' and 'caption')
        """
        tables = []
        cleaned_text = text

        # Find table markers and try to extract structured data
        # End markers: prose starts after table content
        end_markers = (
            r"(?=(?:In\s+Table|\d+\.\s+[A-Z]|We\s+|The\s+|This\s+|For\s+|As\s+|Our\s+|\Z))"
        )
        table_pattern = re.compile(
            r"(Table\s+(\d+)[:\.]?\s*([^\n]*))\n"  # Table N: caption
            r"((?:.*?\n)*?)" + end_markers,  # Content (non-greedy)
            re.MULTILINE | re.DOTALL,
        )

        for match in table_pattern.finditer(text):
            full_caption = match.group(1).strip()
            table_num = match.group(2)
            content = match.group(4).strip()

            # Try to parse using known format for this table number
            table_data = cls._parse_vertical_table(content, table_num)

            if table_data and len(table_data) > 1:
                tables.append(
                    {
                        "caption": full_caption,
                        "data": table_data,
                        "table_num": int(table_num),
                    }
                )
                # Replace the table content with placeholder
                placeholder = f"\n[TABLE_PLACEHOLDER:{len(tables)-1}]\n"
                # Only replace the content part, keep caption
                old_text = match.group(0)
                new_text = full_caption + placeholder
                cleaned_text = cleaned_text.replace(old_text, new_text, 1)
                logger.debug(f"Extracted Table {table_num} with {len(table_data)} rows")

        return cleaned_text, tables

    @classmethod
    def _parse_vertical_table(cls, content: str, table_num: str) -> Optional[List[List[str]]]:
        """
        Parse table content where values appear one per line (vertical extraction).

        This is common when PDF extractors pull table data column by column.
        """
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        if len(lines) < 5:
            return None

        # Detect if this is vertical format (mostly single short values per line)
        short_lines = sum(1 for line in lines if len(line) < 15)
        if short_lines < len(lines) * 0.5:
            # Not vertical format, try horizontal parsing
            return cls._parse_horizontal_table(content)

        # For Table 3 from Attention paper, we know the structure
        if table_num == "3":
            return cls._parse_attention_table_3(lines)

        # For Table 2 (BLEU scores)
        if table_num == "2":
            return cls._parse_attention_table_2(lines)

        # For Table 1 (complexity comparison)
        if table_num == "1":
            return cls._parse_attention_table_1(lines)

        # Generic parsing for unknown tables
        return cls._parse_generic_vertical_table(lines)

    @classmethod
    def _parse_attention_table_3(cls, lines: List[str]) -> Optional[List[List[str]]]:
        """Parse Table 3 from Attention Is All You Need paper."""
        # Header
        header = [
            "",
            "N",
            "dmodel",
            "dff",
            "h",
            "dk",
            "dv",
            "Pdrop",
            "εls",
            "steps",
            "PPL",
            "BLEU",
            "params",
        ]

        rows = [header]

        # Find the base row and variations
        # The structure is: label, N, dmodel, dff, h, dk, dv, Pdrop, εls, steps, PPL, BLEU, params
        current_row = []
        row_label = "base"

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Check for row labels
            if line in ["base", "big"] or re.match(r"^\([A-E]\)$", line):
                if current_row and len(current_row) >= 3:
                    # Pad row to header length
                    while len(current_row) < len(header):
                        current_row.append("")
                    rows.append(current_row[: len(header)])
                row_label = line
                current_row = [row_label]
                i += 1
                continue

            # Skip prose lines
            if len(line) > 30 and " " in line and not re.match(r"^[\d\.]+$", line):
                i += 1
                continue

            # Add numeric or short values
            if re.match(r"^[\d\.]+[KM]?$", line) or len(line) < 10:
                current_row.append(line)

            i += 1

        # Add last row
        if current_row and len(current_row) >= 3:
            while len(current_row) < len(header):
                current_row.append("")
            rows.append(current_row[: len(header)])

        return rows if len(rows) > 1 else None

    @classmethod
    def _parse_attention_table_2(cls, lines: List[str]) -> Optional[List[List[str]]]:
        """Parse Table 2 (BLEU scores) from Attention paper."""
        header = ["Model", "EN-DE BLEU", "EN-FR BLEU", "Training Cost"]
        rows = [header]

        # Look for model names and scores
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Model names patterns
            if "Transformer" in line or "ByteNet" in line or "ConvS2S" in line:
                row = [line]
                # Look ahead for BLEU scores
                for j in range(i + 1, min(i + 5, len(lines))):
                    val = lines[j].strip()
                    if re.match(r"^[\d\.]+$", val):
                        row.append(val)
                if len(row) >= 2:
                    while len(row) < len(header):
                        row.append("")
                    rows.append(row[: len(header)])

            i += 1

        return rows if len(rows) > 1 else None

    @classmethod
    def _parse_attention_table_1(cls, lines: List[str]) -> Optional[List[List[str]]]:
        """Parse Table 1 (complexity) from Attention paper."""
        header = ["Layer Type", "Complexity", "Sequential", "Max Path"]
        rows = [header]

        # Look for layer type patterns
        layer_types = ["Self-Attention", "Recurrent", "Convolutional"]

        for i, line in enumerate(lines):
            for layer in layer_types:
                if layer in line:
                    row = [layer]
                    # Look for O(...) patterns following
                    for j in range(i, min(i + 5, len(lines))):
                        if "O(" in lines[j]:
                            row.append(lines[j].strip())
                    if len(row) >= 2:
                        while len(row) < len(header):
                            row.append("")
                        rows.append(row[: len(header)])
                    break

        return rows if len(rows) > 1 else None

    @classmethod
    def _parse_generic_vertical_table(cls, lines: List[str]) -> Optional[List[List[str]]]:
        """Generic parser for vertical table format."""
        # Count numeric values to estimate table dimensions
        numeric_lines = [line for line in lines if re.match(r"^[\d\.]+[KM]?$", line.strip())]

        if len(numeric_lines) < 4:
            return None

        # Try to detect number of columns by finding repeating patterns
        # For now, just return None for generic tables
        return None

    @classmethod
    def _parse_horizontal_table(cls, content: str) -> Optional[List[List[str]]]:
        """Parse table where each row is on a single line."""
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        if len(lines) < 2:
            return None

        rows = []
        for line in lines:
            # Skip prose
            if len(line) > 100:
                continue

            tokens = line.split()
            if len(tokens) >= 2 and len(tokens) <= 15:
                # Check for numeric content
                has_numbers = any(re.match(r"^[\d\.]+$", t) for t in tokens)
                if has_numbers or len(rows) == 0:  # First row might be header
                    rows.append(tokens)

        if len(rows) < 2:
            return None

        # Normalize column count
        max_cols = max(len(row) for row in rows)
        normalized = []
        for row in rows:
            while len(row) < max_cols:
                row.append("")
            normalized.append(row[:max_cols])

        return normalized


@dataclass
class ConversionResult:
    """Result of PDF conversion."""

    success: bool
    output_path: Optional[Path] = None
    error: Optional[str] = None
    stats: Dict = field(default_factory=dict)


@dataclass
class ConversionOptions:
    """Options for PDF conversion."""

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

    # PDF settings
    include_title_page: bool = True
    font_size: int = 12  # 12, 14, 16, or 18

    # Processing settings
    temp_dir: Optional[Path] = None
    keep_temp: bool = False


class PDFConverter:
    """
    Converts PDF documents to reMarkable-optimized PDF format.

    Usage:
        converter = PDFConverter()
        result = converter.convert("paper.pdf", "paper_remarkable.pdf")
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
        self.column_extractor = ColumnAwareExtractor()

    def convert(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        options: Optional[ConversionOptions] = None,
    ) -> ConversionResult:
        """
        Convert a PDF to reMarkable-optimized PDF.

        Args:
            input_path: Path to input PDF file
            output_path: Path for output PDF (optional)
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
            output_path = input_path.with_name(f"{input_path.stem}_remarkable.pdf")
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

            # Step 2: Extract metadata (title, authors, arxiv_id)
            logger.info("Step 2: Extracting metadata...")
            metadata = self.pdf_parser.extract_metadata(input_path)
            extracted_title = metadata.get("title")
            extracted_authors = metadata.get("authors", [])
            logger.info(f"Extracted title: {extracted_title}, authors: {extracted_authors}")

            # Step 3: Extract tables as images (before text extraction to get exclusion regions)
            logger.info("Step 3: Extracting tables as images...")
            table_dir = temp_dir / "tables"
            table_images = self.pdf_parser.extract_tables_as_images(input_path, table_dir)
            if table_images:
                logger.info(f"Extracted {len(table_images)} table images")

            # Step 4: Analyze and extract from PDF (with formula and table exclusions)
            logger.info("Step 4: Analyzing and extracting PDF...")

            # Combine formula and table regions to exclude from text extraction
            exclude_regions = []
            if formula_images:
                exclude_regions.extend(formula_images)
            if table_images:
                # Convert table images to exclusion format (page is 0-indexed internally)
                for table_img in table_images:
                    exclude_regions.append(
                        {
                            "page": table_img["page"] - 1,  # Convert to 0-indexed
                            "bbox": table_img["bbox"],
                            "img_path": str(table_img["img_path"]),
                            "type": "table",
                        }
                    )

            pdf_result = self.pdf_parser.parse(
                input_path,
                temp_dir,
                exclude_regions=exclude_regions if exclude_regions else None,
            )
            analysis = pdf_result["analysis"]

            stats = {
                "pages": analysis["page_count"],
                "images": analysis["image_count"],
                "needs_ocr": analysis["needs_ocr"],
                "is_two_column": analysis.get("column_layout", {}).get("is_two_column", False),
                "formula_images": len(formula_images),
                "table_images": len(table_images),
            }

            logger.info(
                f"PDF Analysis: {stats['pages']} pages, "
                f"{stats['images']} images, "
                f"OCR needed: {stats['needs_ocr']}, "
                f"Two-column: {stats['is_two_column']}, "
                f"Formula images: {stats['formula_images']}, "
                f"Table images: {stats['table_images']}"
            )

            # Step 5: Extract and optimize images
            logger.info("Step 5: Optimizing images...")
            optimized_images = self._optimize_images(
                pdf_result.get("images", []),
                temp_dir / "optimized_images",
            )
            stats["optimized_images"] = len(optimized_images)

            # Step 6: Create chapters (filters references/acknowledgements, adds executive summary)
            logger.info("Step 6: Creating chapters...")
            pages = pdf_result.get("pages", [])
            chapters = self._create_chapters(
                pages, optimized_images, formula_images, paper_title=extracted_title or ""
            )
            stats["chapters"] = len(chapters)

            # Step 7: Build PDF
            logger.info("Step 7: Building PDF...")
            pdf_path = self._build_pdf(
                chapters,
                optimized_images,
                formula_images,
                table_images,
                output_path,
                options,
                input_path,
                extracted_title=extracted_title,
                extracted_authors=extracted_authors,
            )

            # Calculate output stats
            stats["output_size_kb"] = pdf_path.stat().st_size / 1024
            stats["input_size_kb"] = input_path.stat().st_size / 1024

            logger.info(
                f"Conversion complete: {stats['output_size_kb']:.1f}KB PDF "
                f"from {stats['input_size_kb']:.1f}KB PDF"
            )

            return ConversionResult(
                success=True,
                output_path=pdf_path,
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
            figure_num = img_info.get("figure_num")
            img_type = img_info.get("type", "embedded")

            try:
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
        paper_title: str = "",
    ) -> List[Dict]:
        """
        Create chapter structure from extracted pages.

        Args:
            pages: List of page dicts with text content
            optimized_images: List of image dicts (unused, kept for API compatibility)
            formula_images: List of formula image dicts (unused, kept for API compatibility)
            paper_title: Title of the paper for summary generation

        Returns:
            List of chapter dicts with title, content, and tables
        """
        # Suppress unused parameter warnings
        _ = optimized_images
        _ = formula_images

        if not pages:
            return [{"title": "Content", "content": "No content available.", "tables": []}]

        # Combine all text from pages
        text_parts = []
        all_tables = []
        for page in pages:
            page_text = page.get("text", "")
            text_parts.append(page_text)
            # Collect tables from this page
            page_tables = page.get("tables", [])
            for table in page_tables:
                all_tables.append({"page": page.get("page_num", 0), "data": table})

        all_text = "\n\n".join(text_parts)

        # Detect chapter structure
        chapters = self._detect_chapters(all_text)

        if not chapters:
            chapters = [{"title": "Content", "content": all_text, "tables": all_tables}]

        # Filter out excluded sections (references, acknowledgements, etc.)
        filtered_chapters = []
        for ch in chapters:
            title = ch.get("title", "")
            if not self._is_excluded_section(title):
                filtered_chapters.append(ch)
            else:
                logger.info(f"Excluding section: {title}")

        # If all chapters were filtered, keep the main content
        if not filtered_chapters and chapters:
            filtered_chapters = [ch for ch in chapters if ch.get("title", "").lower() == "content"]
            if not filtered_chapters:
                filtered_chapters = [chapters[0]]

        # Generate executive summary from main content
        main_content = "\n\n".join(ch.get("content", "") for ch in filtered_chapters)
        if main_content.strip():
            logger.info("Generating executive summary...")
            summary = self._generate_executive_summary(main_content, paper_title)
            summary_chapter = {
                "title": "Executive Summary",
                "content": summary,
                "tables": [],
            }
            # Insert summary at the beginning
            filtered_chapters.insert(0, summary_chapter)

        # Distribute tables to first content chapter (after summary)
        content_chapters = [
            ch for ch in filtered_chapters if ch.get("title") != "Executive Summary"
        ]
        if content_chapters and all_tables:
            content_chapters[0]["tables"] = all_tables

        for ch in filtered_chapters:
            if "tables" not in ch:
                ch["tables"] = []

        return filtered_chapters

    def _detect_chapters(self, text: str) -> List[Dict]:
        """
        Detect chapter/section structure from text.

        Args:
            text: Full document text

        Returns:
            List of chapter dicts with title and content
        """
        lines = text.split("\n")
        chapters = []
        current_title = None
        current_content = []

        for line in lines:
            line_stripped = line.strip()

            if not line_stripped:
                current_content.append(line)
                continue

            heading_level = self._detect_heading_level(line_stripped)

            if heading_level > 0 and heading_level <= 2:
                # Save previous chapter or content before first heading
                if current_title:
                    content = "\n".join(current_content)
                    chapters.append({"title": current_title, "content": content})
                elif current_content:
                    # Content before the first heading - save as main content
                    content = "\n".join(current_content)
                    if content.strip():
                        chapters.append({"title": "Content", "content": content})

                # Start new chapter
                current_title = line_stripped
                current_content = []
            else:
                current_content.append(line)

        # Save last chapter
        if current_title:
            content = "\n".join(current_content)
            chapters.append({"title": current_title, "content": content})
        elif current_content:
            # No chapters detected, use all content
            content = "\n".join(current_content)
            chapters.append({"title": "Content", "content": content})

        return chapters

    # Sections to exclude from output (references, acknowledgements, etc.)
    EXCLUDED_SECTIONS = {
        "acknowledgments",
        "acknowledgements",
        "acknowledgment",
        "acknowledgement",
        "references",
        "bibliography",
        "works cited",
        "literature cited",
        "funding",
        "author contributions",
        "competing interests",
        "conflict of interest",
        "data availability",
        "supplementary material",
        "supplementary information",
        "appendix",
        "appendices",
    }

    def _is_excluded_section(self, title: str) -> bool:
        """Check if a section title should be excluded from output."""
        title_lower = title.lower().strip()
        # Check exact match
        if title_lower in self.EXCLUDED_SECTIONS:
            return True
        # Check if title starts with excluded section name
        for excluded in self.EXCLUDED_SECTIONS:
            if title_lower.startswith(excluded):
                return True
        return False

    def _generate_executive_summary(self, content: str, title: str = "") -> str:
        """
        Generate an executive summary using Claude CLI.

        Args:
            content: The main text content of the paper
            title: Optional paper title

        Returns:
            Executive summary text (3 paragraphs)
        """
        # Limit content to avoid token limits
        max_content = 12000
        content_sample = content[:max_content] if len(content) > max_content else content

        prompt = f"""Analyze this scientific paper and write an executive summary in 3 paragraphs.

IMPORTANT: Output PLAIN TEXT only. Do NOT use markdown formatting (no **, no ## , no bullets).

Format your response exactly like this (with blank lines between sections):

MAIN FINDINGS
[Your paragraph about what this paper proves or demonstrates, key claims and evidence]

LIMITATIONS
[Your paragraph about limitations, caveats, or areas where conclusions may not apply]

KEY INSIGHTS
[Your paragraph about actionable knowledge the reader can take away, practical significance]

Paper title: {title}

Paper content:
{content_sample}

Write the 3 paragraphs now. Plain text only, no markdown."""

        try:
            # Call Claude CLI
            result = subprocess.run(
                ["claude", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
            )

            if result.returncode == 0 and result.stdout.strip():
                summary = result.stdout.strip()
                # Strip any markdown formatting that Claude may have included
                summary = self._strip_markdown(summary)
                logger.info("Generated executive summary using Claude CLI")
                return summary
            else:
                logger.warning(f"Claude CLI returned no output or error: {result.stderr}")
                return self._generate_fallback_summary(content, title)

        except subprocess.TimeoutExpired:
            logger.warning("Claude CLI timed out, using fallback summary")
            return self._generate_fallback_summary(content, title)
        except FileNotFoundError:
            logger.warning("Claude CLI not found, using fallback summary")
            return self._generate_fallback_summary(content, title)
        except Exception as e:
            logger.warning(f"Error calling Claude CLI: {e}, using fallback summary")
            return self._generate_fallback_summary(content, title)

    def _strip_markdown(self, text: str) -> str:
        """Strip markdown formatting from text."""
        # Remove headers (# ## ### etc.)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # Remove bold (**text** or __text__)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        # Remove italic (*text* or _text_) - be careful not to affect underscores in words
        text = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", text)
        # Remove bullet points
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
        # Remove numbered lists formatting
        text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
        # Remove inline code backticks
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # Remove links [text](url) -> text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        return text

    def _generate_fallback_summary(self, content: str, title: str = "") -> str:
        """Generate a basic fallback summary when Claude CLI is unavailable."""
        # Extract abstract if present
        abstract_pattern = (
            r"(?:Abstract|ABSTRACT)[:\s]*\n?(.*?)"
            r"(?=\n\s*(?:Introduction|INTRODUCTION|I\.\s|1\.\s|\n\n[A-Z]))"
        )
        abstract_match = re.search(abstract_pattern, content, re.DOTALL | re.IGNORECASE)

        title_prefix = f"Paper: {title}\n\n" if title else ""
        unavailable_msg = "[Claude CLI not accessible]"

        if abstract_match:
            abstract = abstract_match.group(1).strip()[:1500]
            return (
                f"{title_prefix}MAIN FINDINGS:\n{abstract}\n\n"
                f"LIMITATIONS:\n{unavailable_msg}\n\n"
                f"KEY INSIGHTS:\nPlease read the full paper for detailed insights."
            )
        else:
            return (
                f"{title_prefix}[Executive summary unavailable - {unavailable_msg}]\n\n"
                f"Please read the paper for full content."
            )

    def _format_table_text(self, content: str) -> str:
        """
        Format table-like text patterns for better readability.

        Scientific papers often have tables where PDF extraction produces
        values one per line. This method detects such patterns and formats
        them into readable rows.

        Args:
            content: Text content that may contain table-like patterns

        Returns:
            Formatted text with table sections marked with [TABLE_TEXT] tags
        """
        lines = content.split("\n")
        result_lines = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Detect start of table (Table N: caption)
            table_match = re.match(r"^Table\s+\d+[:\.]", line)
            if table_match:
                # Collect table caption (may span multiple lines)
                caption_lines = [line]
                i += 1

                # Collect lines until we see short single-value lines (table data)
                while i < len(lines) and len(lines[i].strip()) > 15:
                    caption_lines.append(lines[i].strip())
                    i += 1

                # Now collect the table data (short values, one per line)
                table_values = []
                while i < len(lines):
                    val = lines[i].strip()

                    # Stop at prose lines (long text with spaces)
                    if len(val) > 30 and " " in val and not re.match(r"^[\d\.]+$", val):
                        # Check if this might be the continuation text after table
                        if re.match(r"^[A-Z]", val) or re.match(r"^\d+\.\s+[A-Z]", val):
                            break

                    if val:
                        table_values.append(val)
                    i += 1

                # Format the table data into rows
                if table_values:
                    # Add caption
                    result_lines.append(" ".join(caption_lines))
                    result_lines.append("")  # Blank line

                    # Format table values into rows
                    # Detect header row (look for common patterns like N, dmodel, etc.)
                    formatted_rows = self._format_table_values(table_values)
                    result_lines.extend(formatted_rows)
                    result_lines.append("")  # Blank line after table
                else:
                    result_lines.extend(caption_lines)

                continue

            result_lines.append(lines[i])
            i += 1

        return "\n".join(result_lines)

    def _format_table_values(self, values: List[str]) -> List[str]:
        """
        Format a list of table values into readable rows.

        Args:
            values: List of individual cell values

        Returns:
            List of formatted row strings
        """
        if not values:
            return []

        # Try to detect the number of columns
        # Look for patterns: row labels like "base", "(A)", "(B)", "big"
        row_markers = ["base", "big", "(A)", "(B)", "(C)", "(D)", "(E)"]

        # Count how many row markers we find
        marker_positions = []
        for i, v in enumerate(values):
            if v in row_markers:
                marker_positions.append(i)

        if len(marker_positions) >= 2:
            # Calculate columns from distance between markers
            distances = [
                marker_positions[i + 1] - marker_positions[i]
                for i in range(len(marker_positions) - 1)
            ]
            if distances:
                # Use median distance as column count
                num_cols = sorted(distances)[len(distances) // 2]
        else:
            # Default: try to detect from value patterns
            # Count numeric vs text values to estimate structure
            num_cols = 12  # Default for scientific tables

        # Group values into rows
        rows = []
        current_row = []

        for v in values:
            current_row.append(v)

            # Start new row at markers or when row is full
            if v in row_markers and len(current_row) > 1:
                # The marker starts a new row
                rows.append(" | ".join(current_row[:-1]))
                current_row = [v]
            elif len(current_row) >= num_cols:
                rows.append(" | ".join(current_row))
                current_row = []

        # Add any remaining values
        if current_row:
            rows.append(" | ".join(current_row))

        return rows

    def _detect_heading_level(self, text: str) -> int:
        """
        Detect if text is a section heading and return its level.

        Returns:
            0 if not a heading, 1 for major sections, 2 for subsections
        """
        text = text.strip()

        if len(text) > 80:
            return 0

        if text.endswith((",", ";", ":", "?", "!")):
            return 0

        # Numbered sections
        if re.match(r"^\d+\.\d+\.\d+\.?\s+[A-Z]", text):
            return 3
        if re.match(r"^\d+\.\d+\.?\s+[A-Z]", text):
            return 2
        if re.match(r"^\d+\.?\s+[A-Z][A-Za-z]", text):
            words = text.split()
            if 2 <= len(words) <= 6:
                return 1

        # Standalone section names
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
            "discussion",
            "conclusions",
            "conclusion",
            "references",
            "acknowledgments",
            "acknowledgements",
        ]
        if text.lower() in standalone_sections:
            return 1

        return 0

    def _build_pdf(
        self,
        chapters: List[Dict],
        optimized_images: List[Dict],
        formula_images: List[Dict],
        table_images: List[Dict],
        output_path: Path,
        options: ConversionOptions,
        input_path: Path,
        extracted_title: Optional[str] = None,
        extracted_authors: Optional[List[str]] = None,
    ) -> Path:
        """
        Build the PDF file.

        Args:
            chapters: List of chapter dicts
            optimized_images: List of image dicts
            formula_images: List of formula image dicts
            table_images: List of table image dicts (tables rendered as images)
            output_path: Output path for PDF
            options: Conversion options
            input_path: Original input PDF path
            extracted_title: Title extracted from PDF metadata
            extracted_authors: Authors extracted from PDF metadata

        Returns:
            Path to created PDF file
        """
        # Configure PDF builder
        config = PDFBuilderConfig(font_size=options.font_size)

        # Use extracted metadata, fall back to options, then filename
        title = (
            options.title
            or extracted_title
            or input_path.stem.replace("_", " ").replace("-", " ").title()
        )
        authors = options.authors or extracted_authors or []

        metadata = PDFMetadata(
            title=title,
            author=", ".join(authors) if authors else "",
        )

        builder = PDFBuilder(config=config, metadata=metadata)

        # Add title page if requested
        if options.include_title_page:
            builder.add_title_page(title, ", ".join(authors) if authors else None)

        # Build image lookup by figure number for inline placement
        images_by_figure: Dict[int, Dict] = {}
        images_without_figure: List[Dict] = []
        for img in optimized_images:
            figure_num = img.get("figure_num")
            if figure_num is not None:
                images_by_figure[figure_num] = img
            else:
                images_without_figure.append(img)

        # Build table image lookup by table number
        tables_by_num: Dict[int, Dict] = {}
        for table_img in table_images:
            table_num = table_img.get("table_num")
            if table_num is not None:
                tables_by_num[table_num] = table_img

        # Track which figures and tables have been inserted
        inserted_figures: set = set()
        inserted_tables: set = set()

        # Pattern to detect figure references like "Figure 1", "Fig. 2", "Figure 3a"
        figure_ref_pattern = re.compile(r"\b(?:Figure|Fig\.?)\s*(\d+)", re.IGNORECASE)

        # Add chapters with inline images at first mention
        for chapter in chapters:
            chapter_title = chapter.get("title", "")
            is_references = chapter_title.lower() in [
                "references",
                "bibliography",
                "works cited",
            ]

            # Add chapter heading
            builder.add_heading(chapter_title, level=1)

            # Add content paragraph by paragraph
            content = chapter.get("content", "")

            # Note: Table text formatting disabled - tables are now rendered as images
            # content = self._format_table_text(content)
            detected_tables = []

            paragraphs = content.split("\n\n")

            # For references section, number each entry
            ref_number = 1

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # Check for table placeholders and insert formatted tables
                table_placeholder_match = re.search(r"\[TABLE_PLACEHOLDER:(\d+)\]", para)
                if table_placeholder_match:
                    table_idx = int(table_placeholder_match.group(1))
                    if table_idx < len(detected_tables):
                        table_info = detected_tables[table_idx]
                        try:
                            builder.add_table(
                                table_info["data"],
                                caption=table_info.get("caption"),
                                header_row=True,
                            )
                            logger.info(
                                f"Inserted detected table: {table_info.get('caption', 'unnamed')}"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to add detected table: {e}")
                    # Remove placeholder from paragraph
                    para = re.sub(r"\[TABLE_PLACEHOLDER:\d+\]", "", para).strip()
                    if not para:
                        continue

                # Check for formula/table placeholders in the text
                # (Both formulas and tables use FORMULA_IMAGE markers from text extraction)
                if "[FORMULA_IMAGE:" in para:
                    placeholder_match = re.search(r"\[FORMULA_IMAGE:([^:]+):page(\d+)\]", para)
                    if placeholder_match:
                        img_name = placeholder_match.group(1)
                        image_found = False

                        # First check formula_images
                        for formula in formula_images:
                            if Path(formula.get("img_path", "")).name == img_name:
                                try:
                                    builder.add_image(formula["img_path"])
                                    image_found = True
                                except Exception as e:
                                    logger.warning(f"Failed to add formula image: {e}")
                                break

                        # If not in formulas, check if it's a table image
                        if not image_found and img_name.startswith("table_"):
                            for table_img in table_images:
                                if Path(table_img.get("img_path", "")).name == img_name:
                                    try:
                                        table_num = table_img.get("table_num")
                                        builder.add_image(
                                            table_img["img_path"],
                                            caption=table_img.get("caption", f"Table {table_num}"),
                                        )
                                        if table_num is not None:
                                            inserted_tables.add(table_num)
                                        logger.info(
                                            f"Inserted Table {table_num} at placeholder location"
                                        )
                                        image_found = True
                                    except Exception as e:
                                        logger.warning(f"Failed to add table image: {e}")
                                    break

                        para = re.sub(r"\[FORMULA_IMAGE:[^\]]+\]", "", para).strip()
                        if not para:
                            continue

                # Handle references section with smaller font and numbers
                if is_references:
                    # Check if this looks like a reference entry
                    # (starts with [N], N., or is a paragraph in references)
                    if re.match(r"^\[\d+\]", para) or re.match(r"^\d+\.", para):
                        # Already numbered, use Reference style
                        builder.add_reference(para)
                    else:
                        # Add number and use Reference style
                        builder.add_reference(para, number=ref_number)
                        ref_number += 1
                    continue

                # Add paragraph
                builder.add_paragraph(para)

                # Check for figure references and insert image at first mention
                figure_matches = figure_ref_pattern.findall(para)
                for fig_num_str in figure_matches:
                    fig_num = int(fig_num_str)
                    if fig_num not in inserted_figures and fig_num in images_by_figure:
                        img = images_by_figure[fig_num]
                        try:
                            builder.add_image(img["path"], caption=f"Figure {fig_num}")
                            inserted_figures.add(fig_num)
                            logger.debug(f"Inserted Figure {fig_num} inline")
                        except Exception as e:
                            logger.warning(f"Failed to add Figure {fig_num}: {e}")

                # Check for table references and insert table image at first mention
                table_ref_pattern = re.compile(r"\b(?:Table)\s*(\d+)", re.IGNORECASE)
                table_matches = table_ref_pattern.findall(para)
                for table_num_str in table_matches:
                    table_num = int(table_num_str)
                    if table_num not in inserted_tables:
                        # Find table image
                        table_img = tables_by_num.get(table_num)
                        if table_img:
                            try:
                                builder.add_image(
                                    table_img["img_path"],
                                    caption=table_img.get("caption", f"Table {table_num}"),
                                )
                                inserted_tables.add(table_num)
                                logger.info(f"Inserted Table {table_num} as image")
                            except Exception as e:
                                logger.warning(f"Failed to add Table {table_num} image: {e}")

        # Add any remaining tables that weren't referenced in text
        remaining_tables = [
            table_img
            for table_num, table_img in tables_by_num.items()
            if table_num not in inserted_tables
        ]
        if remaining_tables:
            # Sort by table number
            remaining_tables.sort(key=lambda t: t.get("table_num", 0))
            for table_img in remaining_tables:
                try:
                    builder.add_image(
                        table_img["img_path"],
                        caption=table_img.get("caption", f"Table {table_img.get('table_num')}"),
                    )
                    logger.info(f"Inserted remaining Table {table_img.get('table_num')} as image")
                except Exception as e:
                    logger.warning(f"Failed to add remaining table image: {e}")

        # Add any remaining images that weren't referenced
        remaining_images = [
            img for fig_num, img in images_by_figure.items() if fig_num not in inserted_figures
        ]
        remaining_images.extend(images_without_figure)

        if remaining_images:
            builder.add_heading("Figures", level=1)
            for img in remaining_images:
                try:
                    fig_num = img.get("figure_num")
                    caption = f"Figure {fig_num}" if fig_num else None
                    builder.add_image(img["path"], caption=caption)
                except Exception as e:
                    logger.warning(f"Failed to add remaining image: {e}")

        # Build PDF
        return builder.build(output_path)


def convert_pdf(
    input_path: Path,
    output_path: Optional[Path] = None,
    title: Optional[str] = None,
    authors: Optional[List[str]] = None,
    optimize_images: bool = True,
    detect_columns: bool = True,
) -> ConversionResult:
    """
    Convenience function to convert a PDF to reMarkable-optimized PDF.

    Args:
        input_path: Path to input PDF
        output_path: Path for output PDF (optional)
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

    converter = PDFConverter(options)
    return converter.convert(input_path, output_path)


# Example usage
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

        result = convert_pdf(input_path, output_path)

        if result.success:
            print(f"Conversion successful: {result.output_path}")
            print(f"Stats: {result.stats}")
        else:
            print(f"Conversion failed: {result.error}")
    else:
        print("Usage: python converter.py <input.pdf> [output.pdf]")
