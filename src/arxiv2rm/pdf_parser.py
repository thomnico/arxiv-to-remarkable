"""
PDF Parser with intelligent text/image extraction and layout preservation.

Supports:
- Text-based PDFs (direct extraction)
- Scanned PDFs (OCR with deepseek-ocr.rs)
- Hybrid PDFs (mix of text and images)
- Multi-column layouts (automatic detection and reordering)
- Mathematical notation
- Tables and figures
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF
import pdfplumber
from PIL import Image

from .column_detector import ColumnAwareExtractor, ColumnDetector

logger = logging.getLogger(__name__)


class PDFParser:
    """Intelligent PDF parser with OCR fallback and column detection."""

    def __init__(self, ocr_engine="local", ocr_endpoint=None, detect_columns=True):
        """
        Initialize PDF parser.

        Args:
            ocr_engine: "local" (deepseek-ocr.rs) or "groq" (Groq API)
            ocr_endpoint: Optional custom endpoint for local OCR
            detect_columns: Enable automatic column layout detection (default: True)
        """
        self.ocr_engine = ocr_engine
        self.ocr_endpoint = ocr_endpoint or "http://localhost:8080"
        self.detect_columns = detect_columns
        self.column_extractor = ColumnAwareExtractor() if detect_columns else None
        self.column_detector = ColumnDetector() if detect_columns else None

    def extract_metadata(self, pdf_path: Path) -> Dict:
        """
        Extract metadata from PDF including title, authors, and ArXiv ID.

        Tries multiple strategies:
        1. PDF metadata (title, author fields)
        2. First page text analysis (largest font = title)
        3. ArXiv ID from metadata or filename

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with title, authors, arxiv_id (if found)
        """
        import re

        pdf_path = Path(pdf_path)
        doc = fitz.open(pdf_path)

        metadata = {
            "title": None,
            "authors": [],
            "arxiv_id": None,
        }

        # Strategy 1: Check PDF metadata
        pdf_meta = doc.metadata
        if pdf_meta:
            if pdf_meta.get("title") and len(pdf_meta["title"].strip()) > 3:
                metadata["title"] = pdf_meta["title"].strip()
            if pdf_meta.get("author"):
                # Authors can be comma or semicolon separated
                author_str = pdf_meta["author"]
                if ";" in author_str:
                    metadata["authors"] = [a.strip() for a in author_str.split(";")]
                elif "," in author_str:
                    metadata["authors"] = [a.strip() for a in author_str.split(",")]
                else:
                    metadata["authors"] = [author_str.strip()]

        # Strategy 2: Extract title from first page (largest font text)
        if not metadata["title"] or metadata["title"].lower() in ["untitled", "unknown"]:
            first_page = doc[0]
            blocks = first_page.get_text("dict").get("blocks", [])

            # Find text with largest font size in top portion of page
            candidates = []
            page_height = first_page.rect.height
            page_width = first_page.rect.width

            # Patterns to skip (arXiv watermarks, headers, etc.)
            skip_patterns = [
                r"^arXiv:",  # arXiv identifier
                r"^\d{4}\.\d{4,5}",  # arXiv ID at start
                r"^\[.*\]$",  # Category tags like [cs.CR]
                r"^Preprint",  # Preprint headers
                r"^Draft",  # Draft markers
                r"^Page\s+\d+",  # Page numbers
                r"^\d+\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",  # Dates
                r"^NIH\s+Public\s+Access",  # NIH archive header
                r"^Author\s+Manuscript",  # NIH/PMC author manuscript header
                r"^NIH-PA\s+Author",  # NIH-PA Author Manuscript
                r"^PMC\s+",  # PMC headers
                r"^Review$",  # Generic "Review" header
                r"^Article$",  # Generic "Article" header
                r"^Research\s+Article$",  # Journal article type header
                r"^Original\s+Article$",  # Journal article type header
            ]
            skip_regex = re.compile("|".join(skip_patterns), re.IGNORECASE)

            for block in blocks:
                if block.get("type") != 0:  # Only text blocks
                    continue

                for line in block.get("lines", []):
                    bbox = line.get("bbox", [0, 0, 0, 0])
                    # Only consider text in top 30% of page
                    if bbox[1] > page_height * 0.3:
                        continue

                    # Skip text in margins (left 10% or right 10%) - often watermarks
                    if bbox[0] < page_width * 0.1 or bbox[2] > page_width * 0.9:
                        # Allow if text is centered (title often spans wide)
                        text_center = (bbox[0] + bbox[2]) / 2
                        if abs(text_center - page_width / 2) > page_width * 0.3:
                            continue

                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        font_size = span.get("size", 0)

                        # Skip very short text, small fonts, or skip patterns
                        if len(text) <= 5 or font_size <= 10:
                            continue
                        if skip_regex.search(text):
                            continue

                        candidates.append(
                            {
                                "text": text,
                                "size": font_size,
                                "y": bbox[1],
                            }
                        )

            # Sort by font size (largest first), then by position (top first)
            candidates.sort(key=lambda x: (-x["size"], x["y"]))

            # Take the largest font text as title (combine if multi-line title)
            if candidates:
                title_parts = []
                title_size = candidates[0]["size"]
                for c in candidates:
                    # Include text with same font size (multi-line title)
                    if c["size"] >= title_size * 0.95:  # Allow 5% variance
                        # Skip if this part looks like metadata
                        if not skip_regex.search(c["text"]):
                            title_parts.append(c["text"])
                    else:
                        break

                if title_parts:
                    metadata["title"] = " ".join(title_parts)

        # Strategy 3: Detect ArXiv ID
        # Check filename first (e.g., 2301.12345.pdf, 2301.12345v2.pdf)
        arxiv_pattern = re.compile(r"(\d{4}\.\d{4,5}(?:v\d+)?)")
        filename_match = arxiv_pattern.search(pdf_path.stem)
        if filename_match:
            metadata["arxiv_id"] = filename_match.group(1)
        else:
            # Check PDF metadata for arxiv reference
            if pdf_meta:
                for key in ["subject", "keywords", "creator", "producer"]:
                    value = pdf_meta.get(key, "")
                    if value:
                        arxiv_match = arxiv_pattern.search(value)
                        if arxiv_match:
                            metadata["arxiv_id"] = arxiv_match.group(1)
                            break

            # Check first page text for ArXiv ID
            if not metadata["arxiv_id"]:
                first_page_text = doc[0].get_text()
                # Look for "arXiv:2301.12345" pattern
                arxiv_full_pattern = re.compile(r"arXiv[:\s]*(\d{4}\.\d{4,5}(?:v\d+)?)", re.I)
                arxiv_match = arxiv_full_pattern.search(first_page_text)
                if arxiv_match:
                    metadata["arxiv_id"] = arxiv_match.group(1)

        doc.close()

        logger.info(
            f"Extracted metadata: title='{metadata['title']}', arxiv_id={metadata['arxiv_id']}"
        )
        return metadata

    def analyze_pdf(self, pdf_path: Path) -> Dict:
        """
        Analyze PDF structure and content type.

        Returns:
            Dict with:
            - has_text: bool
            - has_images: bool
            - page_count: int
            - is_scanned: bool
            - needs_ocr: bool
            - column_layout: dict (if column detection enabled)
        """
        logger.info(f"Analyzing PDF: {pdf_path}")

        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        pages_with_text = 0
        total_images = 0
        column_counts = []

        for page_num in range(total_pages):
            page = doc[page_num]

            # Check for text
            text = page.get_text().strip()
            if text:
                pages_with_text += 1

            # Count images
            images = page.get_images()
            total_images += len(images)

            # Detect columns if enabled
            if self.detect_columns and self.column_detector:
                layout = self.column_detector.detect_layout(page)
                column_counts.append(layout.column_count)

        doc.close()

        # Determine PDF type
        text_ratio = pages_with_text / total_pages if total_pages > 0 else 0
        is_scanned = text_ratio < 0.5  # Less than 50% pages have text
        has_text = pages_with_text > 0
        has_images = total_images > 0

        analysis = {
            "has_text": has_text,
            "has_images": has_images,
            "page_count": total_pages,
            "pages_with_text": pages_with_text,
            "image_count": total_images,
            "text_ratio": text_ratio,
            "is_scanned": is_scanned,
            "needs_ocr": is_scanned or not has_text,
        }

        # Add column layout analysis
        if self.detect_columns and column_counts:
            # Calculate dominant column count
            column_distribution = {}
            for count in column_counts:
                column_distribution[count] = column_distribution.get(count, 0) + 1

            dominant_columns = max(column_distribution, key=column_distribution.get)
            two_column_pages = column_distribution.get(2, 0)

            analysis["column_layout"] = {
                "dominant_columns": dominant_columns,
                "distribution": column_distribution,
                "two_column_pages": two_column_pages,
                "is_two_column": dominant_columns == 2 or two_column_pages > total_pages * 0.5,
                "mixed_layout": len(column_distribution) > 1,
            }

            logger.info(
                f"Column analysis: {dominant_columns}-column dominant, "
                f"{two_column_pages}/{total_pages} 2-column pages"
            )

        logger.info(f"PDF Analysis: {analysis}")
        return analysis

    def analyze_special_characters(self, pdf_path: Path) -> Dict:
        """
        Analyze PDF for special characters that may not render in standard fonts.

        Detects:
        - PUA characters (Private Use Area: U+E000-U+F8FF) from LaTeX fonts
        - Mathematical symbols from CMEX, CMSY, CMMIB fonts
        - Replacement characters (U+FFFD) indicating extraction issues

        Returns:
            Dict with:
            - pua_chars: Dict mapping code point to (count, fonts_using)
            - replacement_count: Number of replacement characters found
            - problematic_fonts: Set of fonts with non-standard characters
            - unicode_mapping: Suggested mappings for PUA chars to standard Unicode
        """
        logger.info(f"Analyzing special characters in: {pdf_path}")

        doc = fitz.open(pdf_path)

        pua_chars: Dict[int, Dict] = {}  # code_point -> {count, fonts}
        replacement_count = 0
        problematic_fonts = set()

        # PUA to Unicode mappings for common LaTeX/CM fonts
        # CMEX10 bracket pieces
        pua_unicode_map = {
            0xF8EE: "⎡",  # Left square bracket upper corner
            0xF8EF: "⎣",  # Left square bracket lower corner
            0xF8F0: "⎡",  # Alternative upper left
            0xF8F1: "⎢",  # Left bracket extension
            0xF8F9: "⎤",  # Right square bracket upper corner
            0xF8FA: "⎦",  # Right square bracket lower corner
            0xF8FB: "⎤",  # Alternative upper right
            0xF8FC: "⎥",  # Right bracket extension
            # CMSY10 symbols
            0xF8E6: "∑",  # Summation
            0xF8E7: "∏",  # Product
            0xF8FF: "→",  # Arrow (Apple PUA)
            # More bracket variants
            0xF8F3: "⎧",  # Left curly bracket upper
            0xF8F4: "⎨",  # Left curly bracket middle
            0xF8F5: "⎩",  # Left curly bracket lower
            0xF8FE: "⎫",  # Right curly bracket upper
            0xF8FD: "⎬",  # Right curly bracket middle
            0xF8F6: "⎭",  # Right curly bracket lower
        }

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block.get("type") != 0:
                    continue

                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        font = span.get("font", "unknown")

                        for char in text:
                            code = ord(char)

                            # Check for replacement character
                            if code == 0xFFFD:
                                replacement_count += 1
                                problematic_fonts.add(font)
                                continue

                            # Check for PUA range (U+E000-U+F8FF)
                            if 0xE000 <= code <= 0xF8FF:
                                if code not in pua_chars:
                                    pua_chars[code] = {"count": 0, "fonts": set()}
                                pua_chars[code]["count"] += 1
                                pua_chars[code]["fonts"].add(font)
                                problematic_fonts.add(font)

        doc.close()

        # Convert sets to lists for JSON serialization
        for code in pua_chars:
            pua_chars[code]["fonts"] = list(pua_chars[code]["fonts"])

        analysis = {
            "pua_chars": {f"U+{code:04X}": info for code, info in pua_chars.items()},
            "pua_count": sum(info["count"] for info in pua_chars.values()),
            "replacement_count": replacement_count,
            "problematic_fonts": list(problematic_fonts),
            "unicode_mapping": {
                f"U+{code:04X}": char for code, char in pua_unicode_map.items() if code in pua_chars
            },
            "unmapped_pua": [f"U+{code:04X}" for code in pua_chars if code not in pua_unicode_map],
        }

        if pua_chars or replacement_count:
            logger.warning(
                f"Special characters found: {len(pua_chars)} PUA chars, "
                f"{replacement_count} replacement chars from fonts: {problematic_fonts}"
            )
        else:
            logger.info("No problematic special characters found")

        return analysis

    def extract_matrix_formulas(self, pdf_path: Path, output_dir: Path) -> List[Dict]:
        """
        Extract matrix/bracket notation as images from PDF.

        Detects multi-line equations with large brackets (from CMEX10 font)
        that cannot be properly rendered as text in EPUB.

        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save extracted formula images

        Returns:
            List of dicts with:
            - page: page number (0-indexed)
            - bbox: bounding box coordinates
            - img_path: path to extracted image
            - img_name: filename of extracted image
        """
        logger.info(f"Extracting matrix formulas from: {pdf_path}")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(pdf_path)

        # First pass: detect all blocks with bracket pieces
        bracket_blocks = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block.get("type") != 0:
                    continue

                bbox = block.get("bbox")
                has_bracket_pieces = False

                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        # Check for CMEX10 bracket pieces (PUA range F8EE-F8FF)
                        for c in text:
                            code = ord(c)
                            if 0xF8EE <= code <= 0xF8FF:
                                has_bracket_pieces = True
                                break
                        if has_bracket_pieces:
                            break
                    if has_bracket_pieces:
                        break

                if has_bracket_pieces:
                    bracket_blocks.append(
                        {
                            "page": page_num,
                            "bbox": bbox,
                        }
                    )

        # Second pass: merge adjacent bracket blocks into formula regions
        from collections import defaultdict

        by_page = defaultdict(list)
        for block in bracket_blocks:
            by_page[block["page"]].append(block)

        merged_regions = []
        for page_num, blocks in by_page.items():
            # Sort by vertical position
            blocks.sort(key=lambda b: b["bbox"][1])

            current_group = None
            for block in blocks:
                bbox = block["bbox"]
                if current_group is None:
                    current_group = {
                        "page": page_num,
                        "bbox": list(bbox),
                    }
                else:
                    # Merge if within 30 pixels vertically
                    if bbox[1] - current_group["bbox"][3] < 30:
                        current_group["bbox"][0] = min(current_group["bbox"][0], bbox[0])
                        current_group["bbox"][2] = max(current_group["bbox"][2], bbox[2])
                        current_group["bbox"][3] = bbox[3]
                    else:
                        merged_regions.append(current_group)
                        current_group = {
                            "page": page_num,
                            "bbox": list(bbox),
                        }

            if current_group:
                merged_regions.append(current_group)

        # Third pass: extract images
        zoom = 2.5  # Good quality for formulas
        mat = fitz.Matrix(zoom, zoom)
        results = []

        for i, region in enumerate(merged_regions):
            page = doc[region["page"]]
            bbox = region["bbox"]

            # Add padding around the formula
            clip = fitz.Rect(bbox[0] - 25, bbox[1] - 15, bbox[2] + 25, bbox[3] + 15)
            clip.intersect(page.rect)

            pix = page.get_pixmap(matrix=mat, clip=clip)

            img_name = f"formula_{i + 1:03d}_p{region['page'] + 1}.png"
            img_path = output_dir / img_name
            pix.save(str(img_path))

            results.append(
                {
                    "page": region["page"],
                    "bbox": tuple(region["bbox"]),
                    "img_path": img_path,
                    "img_name": img_name,
                    "width": pix.width,
                    "height": pix.height,
                }
            )

            logger.debug(f"Extracted formula: {img_name} ({pix.width}x{pix.height})")

        doc.close()

        logger.info(f"Extracted {len(results)} matrix formula images")
        return results

    def extract_text_pymupdf(
        self,
        pdf_path: Path,
        exclude_regions: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """
        Extract text using PyMuPDF (for text-based PDFs).

        Args:
            pdf_path: Path to PDF file
            exclude_regions: Optional list of regions to exclude from text extraction.
                Each region should have 'page' (0-indexed) and 'bbox' (x0, y0, x1, y1).
                Text blocks overlapping these regions will be replaced with placeholders.

        Returns:
            List of dicts with page_num, text, layout info
        """
        logger.info("Extracting text with PyMuPDF...")

        # Build lookup of excluded regions by page
        excluded_by_page: Dict[int, List[tuple]] = {}
        if exclude_regions:
            for region in exclude_regions:
                page_num = region.get("page", 0)
                bbox = region.get("bbox")
                if bbox:
                    if page_num not in excluded_by_page:
                        excluded_by_page[page_num] = []
                    excluded_by_page[page_num].append(tuple(bbox))

        doc = fitz.open(pdf_path)
        pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Get excluded regions for this page
            page_exclusions = excluded_by_page.get(page_num, [])

            if page_exclusions:
                # Extract text block by block, skipping excluded regions
                text_parts = []
                blocks = page.get_text("dict")["blocks"]

                for block in blocks:
                    if block.get("type") != 0:  # Skip non-text blocks
                        continue

                    block_bbox = block.get("bbox", (0, 0, 0, 0))

                    # Check if this block overlaps with any excluded region
                    is_excluded = False
                    excluded_region_idx = None
                    for idx, excl_bbox in enumerate(page_exclusions):
                        if self._bboxes_overlap(block_bbox, excl_bbox):
                            is_excluded = True
                            excluded_region_idx = idx
                            break

                    if is_excluded:
                        # Insert placeholder for the first excluded block in this region
                        # (subsequent overlapping blocks are just skipped)
                        if excluded_region_idx is not None:
                            # Find the corresponding formula image
                            for region in exclude_regions or []:
                                if (
                                    region.get("page") == page_num
                                    and tuple(region.get("bbox", ()))
                                    == page_exclusions[excluded_region_idx]
                                ):
                                    img_name = Path(region.get("img_path", "")).name
                                    if img_name:
                                        placeholder = f"[FORMULA_IMAGE:{img_name}:page{page_num+1}]"
                                        if placeholder not in text_parts:
                                            text_parts.append(placeholder)
                                    break
                    else:
                        # Extract text from this block
                        block_text = self._extract_block_text(block)
                        if block_text.strip():
                            text_parts.append(block_text)

                text = "\n".join(text_parts)
                blocks_dict = page.get_text("dict")
            else:
                # No exclusions - extract normally
                text = page.get_text("text")
                blocks_dict = page.get_text("dict")

            pages.append(
                {
                    "page_num": page_num + 1,
                    "text": text,
                    "blocks": blocks_dict,
                    "width": page.rect.width,
                    "height": page.rect.height,
                }
            )

        doc.close()
        logger.info(f"Extracted text from {len(pages)} pages")
        return pages

    def _bboxes_overlap(self, bbox1: tuple, bbox2: tuple, margin: float = 5.0) -> bool:
        """
        Check if two bounding boxes overlap (with optional margin).

        Args:
            bbox1: First bounding box (x0, y0, x1, y1)
            bbox2: Second bounding box (x0, y0, x1, y1)
            margin: Extra margin to expand bbox2 for overlap detection

        Returns:
            True if boxes overlap
        """
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

    def _extract_block_text(self, block: Dict) -> str:
        """
        Extract text from a single text block.

        Args:
            block: PyMuPDF text block dict

        Returns:
            Text content of the block
        """
        text_parts = []
        for line in block.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                line_text += span.get("text", "")
            text_parts.append(line_text)
        return "\n".join(text_parts)

    def extract_text_pdfplumber(self, pdf_path: Path) -> List[Dict]:
        """
        Extract text using pdfplumber (better for tables/columns).

        Returns:
            List of dicts with page_num, text, tables
        """
        logger.info("Extracting text with pdfplumber...")

        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # Extract text
                text = page.extract_text() or ""

                # Extract tables
                tables = page.extract_tables()

                pages.append(
                    {
                        "page_num": page.page_number,
                        "text": text,
                        "tables": tables,
                        "width": page.width,
                        "height": page.height,
                    }
                )

        table_count = sum(len(p.get("tables", [])) for p in pages)
        logger.info(f"Extracted text from {len(pages)} pages (with {table_count} tables)")
        return pages

    def _extract_tables_pdfplumber(self, pdf_path: Path) -> Dict[int, List]:
        """
        Extract tables from PDF using pdfplumber.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict mapping page number (1-indexed) to list of tables.
            Each table is a 2D list of cell contents.
        """
        tables_by_page: Dict[int, List] = {}

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    # Filter out empty/invalid tables
                    valid_tables = []
                    for table in tables:
                        if table and len(table) > 0 and len(table[0]) > 0:
                            # Check table has some content
                            has_content = any(
                                cell and str(cell).strip() for row in table for cell in row
                            )
                            if has_content:
                                valid_tables.append(table)

                    if valid_tables:
                        tables_by_page[page.page_number] = valid_tables

        table_count = sum(len(tables) for tables in tables_by_page.values())
        logger.info(f"Extracted {table_count} tables from {len(tables_by_page)} pages")
        return tables_by_page

    def extract_tables_as_images(self, pdf_path: Path, output_dir: Path) -> List[Dict]:
        """
        Extract tables from PDF as images by detecting "Table N:" markers.

        This method finds table captions and extracts the table region
        as a high-quality image, which renders much better than trying
        to parse table structure.

        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save table images

        Returns:
            List of dicts with:
            - page: page number (1-indexed)
            - table_num: table number (e.g., 1, 2, 3)
            - caption: table caption text
            - img_path: path to extracted image
            - bbox: bounding box coordinates
        """
        logger.info(f"Extracting tables as images from: {pdf_path}")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(pdf_path)
        results = []

        # Track which tables we've already extracted (avoid duplicates)
        extracted_tables = set()

        # Find all "Table N:" text locations
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()

            # Find table markers - only match actual table captions with colon
            # "Table N:" indicates a caption, while "Table N." or "Table N " is a reference
            import re

            table_pattern = re.compile(r"Table\s+(\d+):\s*[A-Z]")

            for match in table_pattern.finditer(text):
                table_num = int(match.group(1))

                # Skip if we already extracted this table number
                if table_num in extracted_tables:
                    continue

                # Search for the exact table caption location (with colon)
                text_instances = page.search_for(f"Table {table_num}:")
                if not text_instances:
                    # Try without colon as fallback
                    text_instances = page.search_for(f"Table {table_num}")
                if not text_instances:
                    continue

                # Get the position of the table marker
                table_rect = text_instances[0]

                # Find the extent of the table by looking for the next major text block
                # or the bottom of the page
                blocks = page.get_text("dict")["blocks"]

                # Find the table start (at or below "Table N:")
                table_top = table_rect.y0 - 5  # Slight margin above

                # Find where the table ends
                # Look for blocks that start after the table marker
                # and find where prose text resumes
                table_bottom = table_top + 300  # Default extent

                # Sort blocks by vertical position
                text_blocks = [b for b in blocks if b.get("type") == 0]
                text_blocks.sort(key=lambda b: b["bbox"][1])

                # Find blocks below the table header
                in_table = False
                prev_block_bottom = table_top

                for block in text_blocks:
                    block_top = block["bbox"][1]
                    block_bottom = block["bbox"][3]

                    if block_top >= table_top:
                        if not in_table:
                            in_table = True

                        # Check if this block looks like prose (wide, text)
                        # Tables tend to have narrow blocks or structured layout
                        block_text = ""
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                block_text += span.get("text", "")

                        # If we see a new section or paragraph start after table data
                        is_new_section = (
                            block_text.strip().startswith(
                                ("In Table", "We ", "The ", "This ", "For ", "As ")
                            )
                            or re.match(r"^\d+\.\s+[A-Z]", block_text.strip())
                            or re.match(r"^\d+\s+[A-Z][a-z]", block_text.strip())
                        )

                        if is_new_section and block_top > table_top + 50:
                            table_bottom = block_top - 5
                            break

                        # Check for large gap indicating end of table
                        if block_top - prev_block_bottom > 40 and in_table:
                            if block_top > table_top + 100:
                                table_bottom = prev_block_bottom + 10
                                break

                        prev_block_bottom = block_bottom

                # Set reasonable bounds
                table_bottom = min(table_bottom, page.rect.height - 20)
                table_bottom = max(table_bottom, table_top + 100)

                # Extract the table region as an image
                # Include full page width to capture the entire table
                clip = fitz.Rect(
                    20,  # Left margin
                    table_top,
                    page.rect.width - 20,  # Right margin
                    table_bottom,
                )
                clip.intersect(page.rect)

                # High quality rendering
                zoom = 2.5
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, clip=clip)

                # Save the image
                img_name = f"table_{table_num}_p{page_num + 1}.png"
                img_path = output_dir / img_name
                pix.save(str(img_path))

                # Get caption text
                caption_text = f"Table {table_num}"
                # Try to extract full caption
                caption_match = re.search(rf"Table\s+{table_num}[:\.]?\s*([^\n]+)", text)
                if caption_match:
                    caption_text = f"Table {table_num}: {caption_match.group(1).strip()}"

                results.append(
                    {
                        "page": page_num + 1,
                        "table_num": table_num,
                        "caption": caption_text,
                        "img_path": img_path,
                        "bbox": (clip.x0, clip.y0, clip.x1, clip.y1),
                        "width": pix.width,
                        "height": pix.height,
                    }
                )

                # Mark this table as extracted to avoid duplicates
                extracted_tables.add(table_num)
                logger.info(f"Extracted table {table_num} from page {page_num + 1} as image")

        doc.close()
        logger.info(f"Extracted {len(results)} table images")
        return results

    def extract_text_column_aware(self, pdf_path: Path) -> List[Dict]:
        """
        Extract text with automatic column detection and reordering.

        Best for 2-column academic papers (IEEE, ACM format).
        Reorders text to follow proper reading order:
        - Full-width header (title, abstract)
        - Left column (top to bottom)
        - Right column (top to bottom)
        - Full-width footer

        Returns:
            List of dicts with page_num, text, column_count, confidence
        """
        if not self.column_extractor:
            logger.warning("Column detection disabled, falling back to pdfplumber")
            return self.extract_text_pdfplumber(pdf_path)

        logger.info("Extracting text with column-aware processing...")
        pages = self.column_extractor.extract_text(pdf_path)

        # Log summary
        two_col_count = sum(1 for p in pages if p.get("column_count") == 2)
        logger.info(
            f"Column-aware extraction: {len(pages)} pages, " f"{two_col_count} two-column pages"
        )

        return pages

    def extract_images(self, pdf_path: Path, output_dir: Path) -> List[Dict]:
        """
        Extract images from PDF, including rendered figures.

        This method extracts:
        1. Embedded raster images (photos, screenshots)
        2. Rendered figure regions (charts, plots, diagrams)

        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save extracted images

        Returns:
            List of dicts with page_num, image_path, bbox
        """
        logger.info("Extracting images from PDF...")

        output_dir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(pdf_path)
        extracted = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Method 1: Extract embedded raster images
            # First, detect figure captions on this page for matching
            import re

            fig_pattern = re.compile(r"^(?:Fig(?:ure)?\.?\s*)(\d+)", re.IGNORECASE)
            text_dict = page.get_text("dict")
            blocks = text_dict.get("blocks", [])
            page_captions = []  # List of (rect, figure_num)

            for block in blocks:
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        text = "".join(span.get("text", "") for span in line.get("spans", []))
                        match = fig_pattern.match(text.strip())
                        if match:
                            bbox = line.get("bbox")
                            if bbox:
                                page_captions.append(
                                    {
                                        "rect": fitz.Rect(bbox),
                                        "figure_num": int(match.group(1)),
                                    }
                                )

            images = page.get_images()
            for img_idx, img in enumerate(images):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    # Save image
                    image_path = output_dir / f"page{page_num + 1}_img{img_idx + 1}.{image_ext}"
                    with open(image_path, "wb") as f:
                        f.write(image_bytes)

                    # Get image position on page
                    rects = page.get_image_rects(xref)
                    bbox = rects[0] if rects else None

                    # Try to match with a figure caption nearby
                    figure_num = None
                    if bbox and page_captions:
                        min_dist = float("inf")
                        for cap in page_captions:
                            # Caption is usually below the figure
                            if self._rects_are_close(bbox, cap["rect"], margin=100):
                                dist = abs(cap["rect"].y0 - bbox.y1)
                                if dist < min_dist:
                                    min_dist = dist
                                    figure_num = cap["figure_num"]

                    extracted.append(
                        {
                            "page_num": page_num + 1,
                            "image_path": image_path,
                            "image_index": img_idx,
                            "bbox": bbox,
                            "width": base_image.get("width"),
                            "height": base_image.get("height"),
                            "type": "embedded",
                            "figure_num": figure_num,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to extract embedded image {img_idx} from page {page_num + 1}: {e}"
                    )

            # Method 2: Detect and extract figure regions (vector graphics, plots)
            figure_regions = self._detect_figure_regions(page, page_num)
            for fig_idx, region_info in enumerate(figure_regions):
                try:
                    region = region_info["rect"]
                    figure_num = region_info.get("figure_num")
                    fig_image = self._render_figure_region(page, region, dpi=200)
                    if fig_image:
                        image_path = output_dir / f"page{page_num + 1}_fig{fig_idx + 1}.png"
                        fig_image.save(image_path, "PNG")

                        extracted.append(
                            {
                                "page_num": page_num + 1,
                                "image_path": image_path,
                                "image_index": len(images) + fig_idx,
                                "bbox": region,
                                "width": fig_image.width,
                                "height": fig_image.height,
                                "type": "rendered_figure",
                                "figure_num": figure_num,  # Detected figure number from caption
                            }
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to render figure region {fig_idx} from page {page_num + 1}: {e}"
                    )

        doc.close()
        logger.info(f"Extracted {len(extracted)} images (embedded + figures)")
        return extracted

    def _detect_figure_regions(self, page: fitz.Page, page_num: int) -> List[Dict]:
        """
        Detect figure regions on a page by analyzing drawings and image areas.

        Looks for:
        - Vector graphics (paths, lines, curves)
        - Drawing clusters that form charts/plots
        - Areas with figure captions nearby

        Args:
            page: PyMuPDF page object
            page_num: Page number (0-indexed)

        Returns:
            List of dicts with 'rect' (fitz.Rect) and 'figure_num' (int or None)
        """
        import re

        figure_regions = []
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        # Get all drawings (vector graphics) on the page
        drawings = page.get_drawings()
        if not drawings:
            return []

        # Get text blocks to find figure captions
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])

        # Find figure caption locations with their figure numbers
        # Pattern matches "Fig. 1", "Figure 2", "Fig 3a", etc.
        fig_pattern = re.compile(r"^(?:Fig(?:ure)?\.?\s*)(\d+)", re.IGNORECASE)
        caption_info = []  # List of (rect, figure_num, text)

        for block in blocks:
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    text = "".join(span.get("text", "") for span in line.get("spans", []))
                    text_stripped = text.strip()
                    match = fig_pattern.match(text_stripped)
                    if match:
                        bbox = line.get("bbox")
                        if bbox:
                            fig_num = int(match.group(1))
                            caption_info.append(
                                {
                                    "rect": fitz.Rect(bbox),
                                    "figure_num": fig_num,
                                    "text": text_stripped,
                                }
                            )

        # Cluster drawings into figure regions
        if drawings:
            drawing_rects = []
            for d in drawings:
                rect = d.get("rect")
                if rect:
                    drawing_rects.append(fitz.Rect(rect))

            # Merge overlapping/nearby drawing rectangles into figure regions
            merged_regions = self._merge_nearby_rects(drawing_rects, margin=10)

            # Filter regions - keep only significant ones
            for region in merged_regions:
                # Skip very small regions (likely just lines or decorations)
                if region.width < 50 or region.height < 50:
                    continue

                # Skip regions that span the full page width (likely borders)
                if region.width > page_width * 0.95:
                    continue

                # Skip tiny regions relative to page
                area_ratio = (region.width * region.height) / (page_width * page_height)
                if area_ratio < 0.02:  # Less than 2% of page
                    continue

                # Find the closest caption to this region
                closest_caption = None
                min_distance = float("inf")
                for cap in caption_info:
                    if self._rects_are_close(region, cap["rect"], margin=100):
                        # Calculate vertical distance (caption usually below figure)
                        dist = abs(cap["rect"].y0 - region.y1)  # Caption below
                        if dist < min_distance:
                            min_distance = dist
                            closest_caption = cap

                # Keep if it's a significant region or near a caption
                is_near_caption = closest_caption is not None and min_distance < 100
                if area_ratio > 0.05 or is_near_caption:
                    # Expand region slightly to include margins
                    expanded = fitz.Rect(
                        max(0, region.x0 - 5),
                        max(0, region.y0 - 5),
                        min(page_width, region.x1 + 5),
                        min(page_height, region.y1 + 5),
                    )
                    figure_regions.append(
                        {
                            "rect": expanded,
                            "figure_num": closest_caption["figure_num"]
                            if closest_caption
                            else None,
                        }
                    )

        logger.debug(
            f"Page {page_num + 1}: Found {len(figure_regions)} figure regions "
            f"from {len(drawings)} drawings"
        )
        return figure_regions

    def _merge_nearby_rects(self, rects: List[fitz.Rect], margin: float = 10) -> List[fitz.Rect]:
        """
        Merge overlapping or nearby rectangles into larger regions.

        Args:
            rects: List of rectangles to merge
            margin: Distance threshold for merging

        Returns:
            List of merged rectangles
        """
        if not rects:
            return []

        # Sort by position
        rects = sorted(rects, key=lambda r: (r.y0, r.x0))

        merged = []
        current = rects[0]

        for rect in rects[1:]:
            # Expand current rect by margin for overlap check
            expanded = fitz.Rect(
                current.x0 - margin, current.y0 - margin, current.x1 + margin, current.y1 + margin
            )

            if expanded.intersects(rect):
                # Merge rectangles
                current = fitz.Rect(
                    min(current.x0, rect.x0),
                    min(current.y0, rect.y0),
                    max(current.x1, rect.x1),
                    max(current.y1, rect.y1),
                )
            else:
                merged.append(current)
                current = rect

        merged.append(current)
        return merged

    def _rects_are_close(self, rect1: fitz.Rect, rect2: fitz.Rect, margin: float) -> bool:
        """Check if two rectangles are within margin distance of each other."""
        expanded = fitz.Rect(
            rect1.x0 - margin, rect1.y0 - margin, rect1.x1 + margin, rect1.y1 + margin
        )
        return expanded.intersects(rect2)

    def _render_figure_region(
        self, page: fitz.Page, region: fitz.Rect, dpi: int = 200
    ) -> Optional[Image.Image]:
        """
        Render a specific region of a page to an image.

        Args:
            page: PyMuPDF page object
            region: Bounding box of the region to render
            dpi: Resolution for rendering

        Returns:
            PIL Image of the region, or None if rendering fails
        """
        try:
            # Create clip rectangle
            clip = fitz.Rect(region)

            # Calculate matrix for desired DPI
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)

            # Render the clipped region
            pix = page.get_pixmap(matrix=mat, clip=clip)

            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Skip if the image is mostly white (empty region)
            if self._is_mostly_white(img):
                return None

            return img

        except Exception as e:
            logger.warning(f"Failed to render region {region}: {e}")
            return None

    def _is_mostly_white(self, img: Image.Image, threshold: float = 0.98) -> bool:
        """
        Check if an image is mostly white (empty).

        Args:
            img: PIL Image
            threshold: Ratio of white pixels to consider "mostly white"

        Returns:
            True if image is mostly white
        """
        # Convert to grayscale
        gray = img.convert("L")

        # Count pixels above threshold (near white)
        pixels = list(gray.getdata())
        white_count = sum(1 for p in pixels if p > 250)
        ratio = white_count / len(pixels)

        return ratio > threshold

    def convert_page_to_image(self, pdf_path: Path, page_num: int, dpi: int = 150) -> Image.Image:
        """
        Convert a PDF page to an image for OCR.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (0-indexed)
            dpi: Resolution for rendering

        Returns:
            PIL Image
        """
        doc = fitz.open(pdf_path)
        page = doc[page_num]

        # Render page at desired DPI
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        doc.close()
        return img

    def parse(
        self,
        pdf_path: Path,
        output_dir: Optional[Path] = None,
        exclude_regions: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Parse PDF intelligently (text extraction + OCR when needed).

        Automatically detects and handles:
        - Single-column and multi-column layouts
        - Scanned PDFs requiring OCR
        - Mixed text/image content

        Args:
            pdf_path: Path to PDF file
            output_dir: Optional directory for extracted images
            exclude_regions: Optional list of regions to exclude from text extraction
                (e.g., formula regions that will be replaced with images).
                Each region should have 'page' (0-indexed), 'bbox', and 'img_path'.

        Returns:
            Dict with:
            - analysis: PDF analysis results (includes column_layout)
            - pages: List of page data (text + images)
            - images: List of extracted images
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        if output_dir is None:
            output_dir = pdf_path.parent / f"{pdf_path.stem}_extracted"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Analyze PDF (includes column detection)
        analysis = self.analyze_pdf(pdf_path)

        # Step 2: Extract images
        images = self.extract_images(pdf_path, output_dir / "images")

        # Step 3: Extract text (choose method based on analysis)
        if analysis["needs_ocr"]:
            logger.info("PDF is scanned or has minimal text - OCR required")
            pages = self._parse_with_ocr(pdf_path, output_dir)
        else:
            logger.info("PDF has text - using direct extraction")

            # Check if this is a multi-column document
            is_multi_column = self.detect_columns and analysis.get("column_layout", {}).get(
                "is_two_column", False
            )

            if is_multi_column:
                # Use column-aware extraction for 2-column PDFs
                logger.info("Detected 2-column layout - using column-aware extraction")
                try:
                    pages = self.extract_text_column_aware(pdf_path)
                    # If we have exclude_regions, we need to post-process
                    # to remove formula text (column-aware doesn't support exclusions yet)
                    if exclude_regions:
                        pages = self._apply_exclusions_to_pages(pdf_path, pages, exclude_regions)
                except Exception as e:
                    logger.warning(
                        f"Column-aware extraction failed: {e}, " "falling back to pdfplumber"
                    )
                    pages = self.extract_text_pdfplumber(pdf_path)
            else:
                # Use standard extraction for single-column
                # Use PyMuPDF for text extraction - pdfplumber loses word spacing
                # in some PDFs (especially MDPI publications)
                # Also extract tables with pdfplumber
                logger.info("Using PyMuPDF for text extraction (preserves word spacing)")
                pages = self.extract_text_pymupdf(pdf_path, exclude_regions=exclude_regions)

                # Extract tables separately with pdfplumber
                logger.info("Extracting tables with pdfplumber...")
                try:
                    tables_by_page = self._extract_tables_pdfplumber(pdf_path)
                    # Add tables to page data
                    for page_data in pages:
                        page_num = page_data.get("page_num", 0)
                        page_data["tables"] = tables_by_page.get(page_num, [])
                except Exception as e:
                    logger.warning(f"Table extraction failed: {e}")

        return {
            "analysis": analysis,
            "pages": pages,
            "images": images,
            "output_dir": output_dir,
        }

    def _apply_exclusions_to_pages(
        self,
        pdf_path: Path,
        pages: List[Dict],
        exclude_regions: List[Dict],
    ) -> List[Dict]:
        """
        Post-process pages to remove text from excluded regions.

        This is used when the primary extraction method doesn't support exclusions.

        Args:
            pdf_path: Path to PDF file
            pages: List of extracted page dicts
            exclude_regions: List of regions to exclude

        Returns:
            Pages with excluded text replaced by placeholders
        """
        # Build lookup by page
        exclusions_by_page: Dict[int, List[Dict]] = {}
        for region in exclude_regions:
            page_num = region.get("page", 0)
            if page_num not in exclusions_by_page:
                exclusions_by_page[page_num] = []
            exclusions_by_page[page_num].append(region)

        # For pages with exclusions, re-extract using PyMuPDF with exclusions
        doc = fitz.open(pdf_path)

        for i, page_data in enumerate(pages):
            page_num = page_data.get("page_num", i + 1) - 1  # Convert to 0-indexed

            if page_num in exclusions_by_page:
                # Re-extract this page with exclusions
                page = doc[page_num]
                page_exclusions = exclusions_by_page[page_num]

                text_parts = []
                blocks = page.get_text("dict")["blocks"]
                inserted_placeholders = set()

                for block in blocks:
                    if block.get("type") != 0:
                        continue

                    block_bbox = block.get("bbox", (0, 0, 0, 0))

                    # Check if this block overlaps with any excluded region
                    matched_region = None
                    for region in page_exclusions:
                        bbox = region.get("bbox")
                        if bbox and self._bboxes_overlap(block_bbox, tuple(bbox)):
                            matched_region = region
                            break

                    if matched_region:
                        # Insert placeholder (only once per region)
                        img_name = Path(matched_region.get("img_path", "")).name
                        if img_name:
                            placeholder = f"[FORMULA_IMAGE:{img_name}:page{page_num+1}]"
                            if placeholder not in inserted_placeholders:
                                text_parts.append(placeholder)
                                inserted_placeholders.add(placeholder)
                    else:
                        block_text = self._extract_block_text(block)
                        if block_text.strip():
                            text_parts.append(block_text)

                # Update the page text
                pages[i]["text"] = "\n".join(text_parts)

        doc.close()
        return pages

    def _parse_with_ocr(self, pdf_path: Path, output_dir: Path) -> List[Dict]:
        """
        Parse PDF using OCR (for scanned PDFs).

        Args:
            pdf_path: Path to PDF file
            output_dir: Directory for temporary images

        Returns:
            List of page data with OCR text
        """
        logger.info("Starting OCR processing...")

        doc = fitz.open(pdf_path)
        pages = []

        for page_num in range(len(doc)):
            logger.info(f"OCR processing page {page_num + 1}/{len(doc)}")

            # Convert page to image
            img = self.convert_page_to_image(pdf_path, page_num, dpi=150)

            # Save temporary image
            temp_img_path = output_dir / f"temp_page{page_num + 1}.png"
            img.save(temp_img_path)

            # Run OCR (local deepseek-ocr.rs)
            if self.ocr_engine == "local":
                text = self._ocr_local(temp_img_path)
            else:
                text = self._ocr_groq(temp_img_path)

            pages.append(
                {
                    "page_num": page_num + 1,
                    "text": text,
                    "ocr_used": True,
                    "temp_image": temp_img_path,
                }
            )

        doc.close()
        logger.info(f"OCR completed for {len(pages)} pages")
        return pages

    def _ocr_local(self, image_path: Path) -> str:
        """Run OCR using local deepseek-ocr.rs."""
        # TODO: Implement local OCR call
        # This will use deepseek-ocr.rs via subprocess or HTTP API
        logger.warning("Local OCR not yet implemented - returning placeholder")
        return f"[OCR text would be extracted from {image_path}]"

    def _ocr_groq(self, image_path: Path) -> str:
        """Run OCR using Groq Vision API."""
        # TODO: Implement Groq API call
        logger.warning("Groq OCR not yet implemented - returning placeholder")
        return f"[Groq OCR text would be extracted from {image_path}]"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test with a PDF
    parser = PDFParser(ocr_engine="local")

    # Example: analyze a PDF
    pdf_path = Path("example.pdf")
    if pdf_path.exists():
        result = parser.parse(pdf_path)
        print(f"Analysis: {result['analysis']}")
        print(f"Pages: {len(result['pages'])}")
        print(f"Images: {len(result['images'])}")
