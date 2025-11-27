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
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .column_detector import ColumnAwareExtractor
from .image_optimizer import ImageOptimizer, OptimizationSettings, RemarkableDevice
from .pdf_builder import PDFBuilder, PDFBuilderConfig, PDFMetadata
from .pdf_parser import PDFParser

logger = logging.getLogger(__name__)


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
    font_size: int = 14  # 12, 14, 16, or 18

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

            # Step 3: Analyze and extract from PDF (with formula exclusions)
            logger.info("Step 3: Analyzing and extracting PDF...")
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

            # Step 4: Extract and optimize images
            logger.info("Step 4: Optimizing images...")
            optimized_images = self._optimize_images(
                pdf_result.get("images", []),
                temp_dir / "optimized_images",
            )
            stats["optimized_images"] = len(optimized_images)

            # Step 5: Create chapters
            logger.info("Step 5: Creating chapters...")
            pages = pdf_result.get("pages", [])
            chapters = self._create_chapters(pages, optimized_images, formula_images)
            stats["chapters"] = len(chapters)

            # Step 6: Build PDF
            logger.info("Step 6: Building PDF...")
            pdf_path = self._build_pdf(
                chapters,
                optimized_images,
                formula_images,
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
    ) -> List[Dict]:
        """
        Create chapter structure from extracted pages.

        Args:
            pages: List of page dicts with text content
            optimized_images: List of image dicts
            formula_images: List of formula image dicts

        Returns:
            List of chapter dicts with title, content, and tables
        """
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
            return [{"title": "Content", "content": all_text, "tables": all_tables}]

        # Distribute tables to chapters (simplified: add all to first chapter)
        # TODO: Better table-to-chapter mapping based on page numbers
        if chapters and all_tables:
            chapters[0]["tables"] = all_tables
        for ch in chapters:
            if "tables" not in ch:
                ch["tables"] = []

        return chapters

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
                # Save previous chapter
                if current_title:
                    content = "\n".join(current_content)
                    chapters.append({"title": current_title, "content": content})

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

        # Track which figures have been inserted
        inserted_figures: set = set()

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
            paragraphs = content.split("\n\n")

            # For references section, number each entry
            ref_number = 1

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # Check for formula placeholders in the text
                if "[FORMULA_IMAGE:" in para:
                    placeholder_match = re.search(r"\[FORMULA_IMAGE:([^:]+):page(\d+)\]", para)
                    if placeholder_match:
                        img_name = placeholder_match.group(1)
                        for formula in formula_images:
                            if Path(formula.get("img_path", "")).name == img_name:
                                try:
                                    builder.add_image(formula["img_path"])
                                except Exception as e:
                                    logger.warning(f"Failed to add formula image: {e}")
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

                # Check for table references and insert table at first mention
                table_ref_pattern = re.compile(r"\b(?:Table)\s*(\d+)", re.IGNORECASE)
                table_matches = table_ref_pattern.findall(para)
                for table_num_str in table_matches:
                    table_num = int(table_num_str)
                    # Find table in chapter tables
                    chapter_tables = chapter.get("tables", [])
                    if table_num <= len(chapter_tables):
                        table_info = chapter_tables[table_num - 1]
                        try:
                            builder.add_table(table_info["data"], caption=f"Table {table_num}")
                            logger.debug(f"Inserted Table {table_num} inline")
                        except Exception as e:
                            logger.warning(f"Failed to add Table {table_num}: {e}")

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
