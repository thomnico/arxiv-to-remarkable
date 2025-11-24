"""
PDF Parser with intelligent text/image extraction and layout preservation.

Supports:
- Text-based PDFs (direct extraction)
- Scanned PDFs (OCR with deepseek-ocr.rs)
- Hybrid PDFs (mix of text and images)
- Multi-column layouts
- Mathematical notation
- Tables and figures
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF
import pdfplumber
from PIL import Image

logger = logging.getLogger(__name__)


class PDFParser:
    """Intelligent PDF parser with OCR fallback."""

    def __init__(self, ocr_engine="local", ocr_endpoint=None):
        """
        Initialize PDF parser.

        Args:
            ocr_engine: "local" (deepseek-ocr.rs) or "groq" (Groq API)
            ocr_endpoint: Optional custom endpoint for local OCR
        """
        self.ocr_engine = ocr_engine
        self.ocr_endpoint = ocr_endpoint or "http://localhost:8080"

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
        """
        logger.info(f"Analyzing PDF: {pdf_path}")

        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        pages_with_text = 0
        total_images = 0

        for page_num in range(total_pages):
            page = doc[page_num]

            # Check for text
            text = page.get_text().strip()
            if text:
                pages_with_text += 1

            # Count images
            images = page.get_images()
            total_images += len(images)

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

    def extract_images(self, pdf_path: Path, output_dir: Path) -> List[Dict]:
        """
        Extract images from PDF.

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
            images = page.get_images()

            for img_idx, img in enumerate(images):
                xref = img[0]
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

                extracted.append(
                    {
                        "page_num": page_num + 1,
                        "image_path": image_path,
                        "image_index": img_idx,
                        "bbox": bbox,
                        "width": base_image.get("width"),
                        "height": base_image.get("height"),
                    }
                )

        doc.close()
        logger.info(f"Extracted {len(extracted)} images")
        return extracted

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

        Args:
            pdf_path: Path to PDF file
            output_dir: Optional directory for extracted images

        Returns:
            Dict with:
            - analysis: PDF analysis results
            - pages: List of page data (text + images)
            - images: List of extracted images
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        if output_dir is None:
            output_dir = pdf_path.parent / f"{pdf_path.stem}_extracted"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Analyze PDF
        analysis = self.analyze_pdf(pdf_path)

        # Step 2: Extract images
        images = self.extract_images(pdf_path, output_dir / "images")

        # Step 3: Extract text (choose method based on analysis)
        if analysis["needs_ocr"]:
            logger.info("PDF is scanned or has minimal text - OCR required")
            pages = self._parse_with_ocr(pdf_path, output_dir)
        else:
            logger.info("PDF has text - using direct extraction")
            # Try pdfplumber first (better for complex layouts)
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
