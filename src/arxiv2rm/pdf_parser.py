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

    def extract_text_pymupdf(self, pdf_path: Path) -> List[Dict]:
        """
        Extract text using PyMuPDF (for text-based PDFs).

        Returns:
            List of dicts with page_num, text, layout info
        """
        logger.info("Extracting text with PyMuPDF...")

        doc = fitz.open(pdf_path)
        pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Extract text with layout preservation
            text = page.get_text("text")  # Simple text
            blocks = page.get_text("dict")  # Structured layout

            pages.append(
                {
                    "page_num": page_num + 1,
                    "text": text,
                    "blocks": blocks,
                    "width": page.rect.width,
                    "height": page.rect.height,
                }
            )

        doc.close()
        logger.info(f"Extracted text from {len(pages)} pages")
        return pages

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

    def parse(self, pdf_path: Path, output_dir: Optional[Path] = None) -> Dict:
        """
        Parse PDF intelligently (text extraction + OCR when needed).

        Automatically detects and handles:
        - Single-column and multi-column layouts
        - Scanned PDFs requiring OCR
        - Mixed text/image content

        Args:
            pdf_path: Path to PDF file
            output_dir: Optional directory for extracted images

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
                except Exception as e:
                    logger.warning(
                        f"Column-aware extraction failed: {e}, " "falling back to pdfplumber"
                    )
                    pages = self.extract_text_pdfplumber(pdf_path)
            else:
                # Use standard extraction for single-column
                try:
                    pages = self.extract_text_pdfplumber(pdf_path)
                except Exception as e:
                    logger.warning(f"pdfplumber failed: {e}, falling back to PyMuPDF")
                    pages = self.extract_text_pymupdf(pdf_path)

        return {
            "analysis": analysis,
            "pages": pages,
            "images": images,
            "output_dir": output_dir,
        }

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
