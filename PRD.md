# PRD: ArXiv to reMarkable Converter

## 1. Executive Summary

### Vision
Create a specialized tool that transforms scientific papers from various sources (ArXiv, IEEE, ACM, local PDFs) into optimized, readable EPUB ebooks for the reMarkable e-ink tablet, with enhanced typography, OCR capabilities, and integrated note-taking spaces.

### Problem Statement
Scientific papers are often poorly formatted for e-ink devices:
- Small fonts strain eyes on e-ink displays
- Multi-column layouts are difficult to read on 10.3" screens
- Scanned PDFs lack searchable text
- No dedicated spaces for annotations
- Manual file transfer is cumbersome
- Fixed PDF pagination doesn't adapt to user preferences (font size changes)

### Solution
An automated pipeline that:
1. Use a PDF backlog or fetch papers from multiple sources
2. If ArXiv, prefer the source LaTeX and images
3. Extract text from PDF via OCR when needed (Deepseek-OCR)
4. Detect images and annotate them with EXIF data
5. Reformat content as reflowable EPUB with readable typography (OpenDyslexic font)
6. Generate EPUB with flexible pagination (adapts to user font size preferences)
7. Add annotation zones and metadata
8. Push directly to reMarkable device

---

## 2. Goals & Success Metrics

### Primary Goals
- Convert papers with >95% text accuracy (OCR quality)
- Increase reading comfort (subjective: user surveys)
- Reduce conversion time to <2 minutes per paper
- Achieve zero manual steps from URL to reMarkable

### Success Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| OCR Accuracy | >95% character accuracy | Benchmark against ground truth |
| Conversion Speed | <2 min for 20-page paper | Automated timing tests |
| User Satisfaction | 4.5/5 rating | Post-use survey |
| Adoption Rate | 100+ active users in 6 months | Analytics |

---

## 3. User Personas

### Persona 1: Academic Researcher
- **Name**: Dr. Sarah Chen
- **Role**: PhD candidate in Computer Science
- **Needs**: Read 5-10 papers/week, annotate heavily, review on commute
- **Pain Points**: Eye strain from small fonts, can't search scanned papers
- **Goals**: Quick conversion, searchable text, large margins for notes

### Persona 2: Dyslexic Student
- **Name**: Marc Dubois
- **Role**: Engineering undergraduate
- **Needs**: Dyslexia-friendly fonts, clear layout, less visual clutter
- **Pain Points**: Standard academic PDFs are difficult to parse
- **Goals**: OpenDyslexic font, single-column layout, high contrast

### Persona 3: Industry Professional
- **Name**: Kenji Tanaka
- **Role**: ML Engineer keeping up with research
- **Needs**: Batch process papers weekly, minimal setup
- **Pain Points**: No time for manual formatting
- **Goals**: Automated workflow, reliable cloud sync

---

## 4. Functional Requirements

### 4.1 Input Sources
| Source | Priority | Description |
|--------|----------|-------------|
| ArXiv URL | P0 | Direct download via ArXiv API |
| Local PDF | P0 | User-provided file |
| IEEE Xplore | P1 | Requires institutional access |
| ACM Digital Library | P1 | Requires subscription |
| Generic URL | P2 | Any publicly accessible PDF |

### 4.2 PDF Splitter & Intelligent Page Triage (NEW)

- **Purpose**: Fast pre-processing to classify pages by scan type, extract metadata, and prepare for optimal OCR routing
- **Benefits**:
  - ✅ **80-90% faster** than full OCR on printed pages (skip OCR if text layer exists)
  - ✅ **Automatic detection** of image-only scans vs illustrated documents
  - ✅ **Context preservation** for EPUB reconstruction (page numbers, headers, footers)
  - ✅ **Cost optimization** - route to appropriate OCR engine based on content type
  - ✅ **Quality improvement** - different strategies for different page types

- **Page Classification Strategy**:

  ```text
  PDF Page → Extract text layer → Text exists? → Extract directly (no OCR)
                               ↓
                           No text layer
                               ↓
                    Extract images + positions
                               ↓
              ┌─────────────────┴──────────────┐
              │                                 │
         1 large image?                   Multiple images?
         (>80% page)                      (<50% page each)
              │                                 │
              ├─ + header/footer only? ────────┤
              │  (top 10% + bottom 10%)         │
              │                                 │
              ▼                                 ▼
      IMAGE SCAN                        ILLUSTRATED PAGE
      (full-page image)                 (images + text)
              │                                 │
              ▼                                 ▼
      → Handwriting detection           → Text regions extracted
      → Route to OCR                    → Images: describe via vision
      → Treat as single unit            → Text: OCR if scanned
  ```

- **Page Type Detection**:

  | Page Type | Detection Criteria | Processing Strategy | EPUB Reconstruction |
  |-----------|-------------------|---------------------|---------------------|
  | **Text-based** | PDF has text layer, no images or small decorative images | Extract text directly, skip OCR | Reflowable text, preserve structure |
  | **Image scan** | 1 large image (>80% page area) + optional header/footer | Full-page OCR → extract text | **Text-only EPUB** (NO embedded page image), single column, generous margins |
  | **Illustrated document** | Multiple small images (<50% each) + text regions | Separate text OCR + image description | Text + inline images, single column, captions below |
  | **Mixed scan** | Large background image + text overlay | OCR full page, extract overlay text | Text-only (discard background), single column |
  | **Chart/diagram page** | 1-3 medium images (50-80%) + minimal text | Vision model description, caption OCR | Optimized image + caption text, single column |

- **Image Position Analysis**:

  ```python
  class ImagePosition:
      page_number: int
      bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
      area_ratio: float  # image area / page area
      position_category: str  # "header", "footer", "inline", "full-page", "margin"
      aspect_ratio: float
      estimated_dpi: int

  class PageMetadata:
      page_number: int
      page_type: str  # "text", "image_scan", "illustrated", "mixed", "chart"
      images: List[ImagePosition]
      text_regions: List[BoundingBox]
      header_text: Optional[str]  # "Chapter 3: Neural Networks"
      footer_text: Optional[str]  # "Page 42"
      section_title: Optional[str]
      has_text_layer: bool
      reconstruction_hints: Dict[str, Any]
  ```

- **Fast Triage Algorithm** (10-50ms per page):

  ```text
  1. Check PDF text layer (PyMuPDF: page.get_text())
     → Has text? → Extract and return (no OCR needed)

  2. Extract all images with positions (page.get_images())
     → Count images, calculate area ratios, positions

  3. Classify page type:
     IF 0 images:
        → "text" (already handled in step 1)

     IF 1 image AND area_ratio > 0.8:
        IF header/footer text in top 10% or bottom 10%:
           → "image_scan" (scanned page with running headers)
        ELSE:
           → "image_scan" (pure scan)

     IF 2-10 images AND max(area_ratio) < 0.5:
        → "illustrated" (textbook, paper with figures)

     IF 1-3 images AND 0.5 < area_ratio < 0.8:
        → "chart" (focus page on diagram/graph)

     ELSE:
        → "mixed" (complex layout)

  4. Extract context for reconstruction:
     - Header: top 10% text extraction
     - Footer: bottom 10% text extraction
     - Section title: largest font on page
     - Figure captions: text near images (±50px)
     - Page number: footer text matching "\d+"

  5. Store metadata for OCR routing and EPUB generation
  ```

- **Reconstruction Context Tracking**:

  ```python
  class DocumentContext:
      """Maintains document structure for EPUB reconstruction"""

      pages: List[PageMetadata]
      chapter_breaks: List[int]  # page numbers
      figure_references: Dict[str, int]  # "Figure 3.2" → page 42
      section_hierarchy: List[Tuple[int, str, int]]  # (level, title, page)
      running_headers: Dict[int, str]  # page → header text

      def get_reconstruction_order(self) -> List[ContentBlock]:
          """Returns ordered list of text/images for EPUB assembly"""
          pass

      def resolve_figure_references(self, text: str) -> str:
          """Replace 'Figure 3.2' with hyperlink to actual page"""
          pass
  ```

- **Integration with Image Understanding**:

  ```text
  Page Triage → Identify images → Classify by position/size
                                 ↓
                            Small inline? → "Figure illustration"
                            Full-page? → "Scanned document page"
                            Header? → "Logo/decoration" (skip vision)
                                 ↓
                         Vision model description (4.3)
                                 ↓
                         EXIF metadata + alt-text
  ```

- **Performance Optimization**:
  - **Parallel processing**: Triage all pages concurrently (thread pool)
  - **Caching**: Store page metadata to avoid re-analysis
  - **Smart sampling**: Analyze first/last pages + every 10th page for patterns
  - **Early exit**: If first 5 pages all text-based, assume text PDF

- **Example Output**:

  ```json
  {
    "document_type": "scientific_paper",
    "total_pages": 12,
    "pages": [
      {
        "page": 1,
        "type": "text",
        "has_text_layer": true,
        "section": "Abstract",
        "images": [],
        "processing": "direct_extract"
      },
      {
        "page": 3,
        "type": "illustrated",
        "has_text_layer": true,
        "section": "Methodology",
        "images": [
          {
            "bbox": [100, 200, 500, 600],
            "area_ratio": 0.35,
            "position": "inline",
            "caption": "Figure 1: Network architecture"
          }
        ],
        "processing": "extract_text_and_describe_images"
      },
      {
        "page": 7,
        "type": "image_scan",
        "has_text_layer": false,
        "header": "Chapter 3: Results",
        "footer": "Page 7",
        "images": [
          {
            "bbox": [50, 100, 550, 750],
            "area_ratio": 0.92,
            "position": "full-page"
          }
        ],
        "processing": "handwriting_detection_then_ocr"
      }
    ],
    "reconstruction_hints": {
      "chapter_breaks": [1, 5, 9],
      "figures": {
        "Figure 1": 3,
        "Figure 2": 5,
        "Table 1": 6
      }
    }
  }
  ```

- **Python Libraries**:
  - PyMuPDF (fitz): Fast PDF parsing, text/image extraction
  - Pillow: Image analysis (size, aspect ratio)
  - numpy: Fast array operations for position analysis
  - **pyobjc-framework-Vision** (macOS only): Native Apple Vision framework for image classification
    - Built-in on macOS (no model download needed)
    - Fast image classification (scene, objects, text detection)
    - Can identify document types (receipt, form, etc.)
    - Useful for pre-classification before vision model processing
    - Installation: `pip install pyobjc-framework-Vision`

- **CLI Integration**:

  ```bash
  # Analyze PDF structure before conversion
  arxiv2rm analyze paper.pdf
  # Output:
  # 📄 Document Analysis
  # ├─ Total pages: 12
  # ├─ Text-based: 8 pages (direct extract)
  # ├─ Image scans: 2 pages (OCR needed)
  # ├─ Illustrated: 2 pages (mixed processing)
  # └─ Estimated processing: 45s (8 pages skip OCR)

  # Triage only (fast preview)
  arxiv2rm triage paper.pdf --output metadata.json
  ```

- **Benefits for EPUB Generation**:
  - **Accurate TOC**: Section hierarchy from page analysis
  - **Figure references**: Hyperlinks from "Figure 3" in text to actual image
  - **Page context**: Running headers become chapter titles
  - **Smart pagination**: CSS page breaks at detected chapter boundaries
  - **Alt-text**: Image descriptions from vision model (Section 4.3)

- **Documentation**: [docs/pdf_splitting_triage.md](docs/pdf_splitting_triage.md) (to be created)

- **EPUB Reconstruction Principles** (CRITICAL):

  1. **Scanned Pages → Text EPUB (NOT Image EPUB)**:
     - ✅ **ALWAYS convert scanned pages to text via OCR** (whether handwritten or printed)
     - ❌ **NEVER embed full-page scan images in EPUB**
     - 🎯 **Goal**: Reflowable, searchable, readable text on reMarkable
     - **Why**: Fixed-layout page images defeat the purpose (can't reflow, adjust font size, search)
     - **Full scan pages can be**:
       - 📝 **Handwritten**: Use Groq Vision API (85-90% accuracy) → extract text
       - 🖨️ **Printed**: Use local DeepSeek OCR (95%+ accuracy) → extract text
       - 🔀 **Mixed**: Handwriting detection routes to appropriate OCR (Section 4.4)

  2. **Single Column Layout (Mandatory)**:
     - All text flows in single column (no multi-column newspaper layouts)
     - Headings, paragraphs, lists all in linear order
     - Figures embedded inline at appropriate points in text
     - Captions always below figures

  3. **Illustrations Handling** (MANDATORY):
     - ✅ **ALWAYS include ALL original document illustrations** (figures, charts, diagrams, equations as images)
     - ✅ **Applies to ALL sources**: PDF, LaTeX, ArXiv sources
     - Small inline images (<50% page): Extract, compress (<500KB), embed with captions
     - Charts/diagrams: Extract, optimize for e-ink, add alt-text descriptions
     - Equations as images: Extract, optimize, embed inline
     - Full-page diagrams: Extract as separate figures with descriptive captions
     - **Only discard**: Decorative headers/footers, logos, page borders
     - **Preserve**: All content images that aid understanding of the document

  4. **Note-Taking Space**:
     - Generous margins via CSS (min 1.5em left/right)
     - Strategic page breaks (avoid splitting sections)
     - Blank space after sections (CSS: margin-bottom: 2em)
     - reMarkable native annotation works seamlessly on EPUB text

  5. **EPUB Structure**:

     ```text
     EPUB Output Structure:
     ├─ Cover (optional)
     ├─ Title page (metadata)
     ├─ Table of Contents (auto-generated from section hierarchy)
     ├─ Chapter 1
     │  ├─ Section 1.1 (text, single column)
     │  ├─ Figure 1.1 (optimized image + caption)
     │  ├─ Section 1.2 (text, single column)
     │  └─ [margin space for notes]
     ├─ Chapter 2
     │  ├─ Section 2.1 (text from OCR if scanned)
     │  ├─ Figure 2.1 (chart with alt-text)
     │  └─ [margin space for notes]
     └─ References
     ```

  6. **Text Extraction from Scans** (Handwritten or Printed):

     ```text
     Scanned Page Image (1404×1872px)
              ↓
     Handwriting Detection (Section 4.4)
              ↓
         ┌───────┴────────┐
         │                │
     Handwritten?     Printed?
         │                │
     Groq Vision      DeepSeek OCR
     (85-90%)         (95%+)
         │                │
         └───────┬────────┘
                 ↓
     Extracted Text (plain text)
              ↓
     Structure Detection (headings, paragraphs)
              ↓
     Semantic HTML (h1, h2, p, ul, ol)
              ↓
     Single Column EPUB (reflowable text)
              ↓
     [Original scan image DISCARDED - text only in EPUB]
     ```

  7. **Quality Standards**:
     - OCR accuracy >95% for printed text
     - All text searchable and selectable
     - Font size user-adjustable on device (14-18pt default)
     - Images optimized for reMarkable 1 (1404×1872px max)
     - Total EPUB size reasonable (<50MB for 100-page paper)

  8. **Example: 12-Page Scientific Paper with Mixed Content**:

     ```text
     INPUT PDF:
     - Pages 1-2: Text with text layer (abstract, intro)
     - Page 3: SCANNED HANDWRITTEN page (methodology notes)
     - Page 4-5: Text with small figures (results)
     - Page 6: Full-page chart
     - Pages 7-8: SCANNED PRINTED pages (discussion from photocopy)
     - Pages 9-12: Text with text layer (conclusion, refs)

     PROCESSING:
     - Page 3: Handwriting detected → Groq Vision OCR → extract text
     - Pages 7-8: Printed scan detected → DeepSeek OCR → extract text

     OUTPUT EPUB:
     ├─ Abstract (text, extracted from PDF)
     ├─ Introduction (text, extracted from PDF)
     ├─ Methodology (text from Groq OCR, NO scan image)
     ├─ Results (text + 2 inline figures with captions)
     ├─ Figure 3 (full-page chart, optimized, with alt-text)
     ├─ Discussion (text from DeepSeek OCR, NO scan images)
     ├─ Conclusion (text, extracted from PDF)
     └─ References (text, extracted from PDF)

     ALL sections: Single column, generous margins, reflowable
     NO full-page images: All scans converted to searchable text
     ```

  9. **LaTeX Source Processing** (MANDATORY for ArXiv):

     When LaTeX sources are available (ArXiv papers):

     - ✅ **ALWAYS extract and include ALL figures** from LaTeX source
     - ✅ **Parse `\includegraphics{}` commands** to find all referenced images
     - ✅ **Extract images from .tar.gz archive**: PDF, PNG, EPS, JPG formats
     - ✅ **Preserve figure order** and positioning as in original document
     - ✅ **Extract figure captions** from `\caption{}` commands
     - ✅ **Convert vector formats** (EPS, PDF) to raster if needed (PNG/JPG)
     - ✅ **Optimize all images** for e-ink (<500KB, 1404×1872px max)
     - ✅ **Generate alt-text** for each figure using vision model
     - ✅ **Build figure references**: Map `\ref{fig:label}` to actual figure numbers

     **Example LaTeX Processing**:

     ```latex
     % In paper.tex
     \begin{figure}
       \includegraphics[width=0.8\textwidth]{figures/architecture.pdf}
       \caption{Neural network architecture with 5 layers}
       \label{fig:architecture}
     \end{figure}

     As shown in Figure~\ref{fig:architecture}, the model uses...
     ```

     **Output EPUB**:

     ```html
     <figure id="fig-architecture">
       <img src="images/architecture.png"
            alt="Neural network architecture diagram showing 5 layers" />
       <figcaption>Figure 1: Neural network architecture with 5 layers</figcaption>
     </figure>

     <p>As shown in <a href="#fig-architecture">Figure 1</a>, the model uses...</p>
     ```

     **Quality Standards**:
     - Extract 100% of figures from LaTeX source
     - Preserve caption text exactly
     - Convert references to hyperlinks
     - Optimize images while preserving quality
     - Include in EPUB even if vector → raster conversion needed

- **Documentation**: [docs/pdf_splitting_triage.md](docs/pdf_splitting_triage.md) (to be created)

### 4.3 Image Understanding & Metadata Enrichment

- **Vision Model for Content Detection**:
  - **PRIMARY (Local)**: Qwen2.5-VL 7B via MLX - 30-50% faster than Ollama, native Apple Silicon optimization
  - **ALTERNATIVE (Local)**: Pixtral 12B via MLX - Best for charts/multi-image analysis
  - **FALLBACK (Cloud)**: Groq Vision API (Llama 4 Scout) - When local unavailable or maximum speed needed
  - **Purpose**: Detect what images represent (not just OCR text extraction)
  - **Use Cases**:
    - Describe figures, diagrams, charts, and photographs
    - Classify image types (graph, flowchart, photograph, equation, table)
    - Extract semantic meaning for accessibility
    - Generate alt-text for EPUB accessibility (WCAG 2.1)
  - **Compression Pipeline**:
    - Auto-compress images before OCR/vision processing
    - Target size: <500KB per image for reMarkable 1 optimal performance
    - Preserve aspect ratio, optimize for e-ink display
    - Progressive quality reduction until size target met
  - **EXIF Metadata Storage**:
    - Store image descriptions in EXIF ImageDescription field
    - Add custom tags: ImageType, SourcePage, ProcessedDate
    - Preserve original metadata when available
    - Enable searchability within EPUB by image content
  - **Workflow**:

    ```text
    Extract Image → Compress to <500KB → Vision API (describe content)
                                       ↓
                    Generate description → Write to EXIF → Embed in EPUB
    ```

  - **Python Libraries**:
    - mlx-vlm: Local vision models via MLX (primary) - 30-50% faster
    - Pillow: Image compression and EXIF manipulation
    - piexif: EXIF data reading/writing
    - groq: Vision API for fallback
  - **Example EXIF Output**:

    ```python
    {
      "ImageDescription": "Bar chart comparing OCR accuracy: Groq 85%, Tesseract 20%",
      "ImageType": "chart",
      "SourcePage": "5",
      "ProcessedDate": "2025-11-24T10:30:00Z",
      "Model": "qwen2.5-vl:7b"
    }
    ```

  - **Benefits**:
    - Enhanced EPUB accessibility (screen readers can describe images)
    - Searchable image content within EPUB
    - Better organization and cataloging of figures
    - Preserved context for future reference
  - **Quality Assurance - Vision Judge**:
    - Use Claude Code vision capabilities during development to validate outputs
    - Compare vision model descriptions against ground truth
    - Evaluate OCR accuracy on sample images
    - Judge image compression quality vs file size tradeoffs
    - Validate EXIF metadata correctness
    - **Workflow**:

      ```text
      Process Image → Generate Description → Claude Vision Judge
                                          ↓
                      Review accuracy/quality → Adjust parameters → Iterate
      ```

    - **Example Judge Prompts**:
      - "Compare these two OCR outputs and judge which is more accurate"
      - "Describe this chart and validate if the EXIF description matches"
      - "Rate the compression quality of this image for e-ink display (1-10)"
      - "Does this alt-text adequately describe the figure for accessibility?"
  - **Documentation**: [docs/image_understanding.md](docs/image_understanding.md) (to be created)

### 4.4 OCR Processing

- **PRIMARY OCR Engine**: deepseek-ocr.rs (Local, Metal GPU acceleration) - **LOCAL FIRST**
  - **GitHub**: [TimmyOVO/deepseek-ocr.rs](https://github.com/TimmyOVO/deepseek-ocr.rs)
  - **Rationale**: FREE, private, offline - cost savings over performance for personal review
  - Native Metal GPU acceleration on Mac M1/M2/M3/M4
  - Performance: 40-50 tokens/s with Metal GPU (vs 12 tok/s CPU-only)
  - Optimized for Apple Silicon with FP16 execution
  - Faster cold-start, lower memory footprint than Python version
  - Zero Python dependencies - native Rust binary
  - OpenAI-compatible HTTP server for easy integration
  - Use cases: Offline processing, privacy-sensitive documents, batch processing
  - **Installation**: `./scripts/install_deepseek_ocr.sh`
  - **Binary Location**: `~/.local/bin/deepseek-ocr` (production)
  - **Build Cache**: `~/.cache/arxiv2rm/deepseek-ocr-build/`
  - **Status**: Production-ready with automated installer
  - **⚠️ LIMITATION - Handwritten Text**:
    - Trained on 30M printed PDFs, minimal handwriting data
    - 16× token compression (256 tokens/image) loses fine details needed for cursive
    - **Test results**: ~30-40% accuracy on handwritten French vs Groq's ~85-90%
    - **Best for**: Printed scientific papers, clean typed documents
    - **Consider Groq fallback for**: Handwritten annotations, margin notes, cursive text
    - See: [analyze_ocr_failure.md](analyze_ocr_failure.md)
- **OPTIONAL FALLBACK**: Groq Vision API (if local unavailable)
  - **Model**: Llama 4 Scout (meta-llama/llama-4-scout-17b-16e-instruct)
  - **API Endpoint**: https://api.groq.com/openai/v1/chat/completions
  - **Note**: Previous model llama-3.2-90b-vision-preview DECOMMISSIONED (Nov 2024)
  - **Get Available Models**: `curl -X GET "https://api.groq.com/openai/v1/models" -H "Authorization: Bearer $GROQ_API_KEY"`
  - Performance: 0.5-1.5s per image, ~2000 tokens per handwritten page
  - Quality: Superior handling of handwritten text, mathematical notation, scientific papers
  - Image Limits: Max 20MB (URL), 4MB (base64), 33 megapixels resolution
  - **Cost**: $0.02/1K tokens (vs FREE for local)
- **🤖 AUTOMATED HANDWRITING DETECTION & ROUTING** (NEW)
  - **Module**: [src/arxiv2rm/handwriting_detector.py](src/arxiv2rm/handwriting_detector.py)
  - **Purpose**: Automatically detect handwritten vs printed text → route to optimal OCR engine
  - **Benefits**:
    - ✅ **Cost optimization**: Use free local OCR for printed text (95%+ of scientific papers)
    - ✅ **Quality optimization**: Use Groq for handwriting (85-90% accuracy vs 30-40% local)
    - ✅ **Fully automated**: No manual intervention required
    - ✅ **75% cost reduction** on mixed documents vs Groq-only
  - **Detection Strategies** (multi-layered):
    1. **macOS Vision Framework** (0× weight, optional pre-filter) - Native Apple classifier
       - Use `pyobjc-framework-Vision` for fast image classification
       - Built-in on macOS (no model download)
       - Can detect: handwriting, printed text, forms, receipts
       - Very fast (<5ms) pre-classification
       - If clearly printed → skip complex analysis
       - Installation: `pip install pyobjc-framework-Vision`
    2. **DeepSeek Confidence Score** (3× weight) - Most reliable when available
       - High confidence (>85%) → Printed → Local OCR
       - Low confidence (<85%) → Likely handwritten → Groq API
    3. **Image Analysis** (1× weight each) - Fast pre-check (10-50ms)
       - Edge density & irregularity (Canny edge detection)
       - Stroke width variance (pixel intensity analysis)
       - Text line straightness (projection profile)
    4. **Text Quality Analysis** (1× weight) - Post-OCR validation
       - Word fragmentation ratio
       - Gibberish detection (unusual patterns)
       - Non-alphanumeric character ratio
  - **Workflow**:

    ```text
    Image → macOS Vision (5ms, optional) → Clearly printed? → Local DeepSeek ✓
                    ↓
              Not clear? → Quick heuristics (10ms) → Clearly printed? → Local DeepSeek
                                                   ↓
                                         Clearly handwritten? → Groq Vision
                                                   ↓
                                         Uncertain? → Try local → Check confidence
                                                                ↓
                                                    Low (<85%)? → Retry with Groq
                                                                ↓
                                                    High (≥85%)? → Keep local result
    ```

  - **Test Results**: 100% accuracy on handwritten samples, 2/3 correct on mixed scenarios
  - **Documentation**: [docs/automated_ocr_routing.md](docs/automated_ocr_routing.md)
- **Smart Detection**: Skip OCR if PDF already has text layer
- **PDF Parser**: Intelligent detection (text-based vs scanned) - see [src/arxiv2rm/pdf_parser.py](src/arxiv2rm/pdf_parser.py)
- **Formula Handling**: Preserve LaTeX or MathML when possible

### 4.5 Layout & Typography
| Feature | Specification |
|---------|---------------|
| Output Format | EPUB 3.0 (reflowable, not fixed-layout) |
| Font Family | OpenDyslexic (embedded) |
| Font Size | User configurable on device (EPUB advantage) |
| Default Font Size | 14-18pt recommended |
| Line Height | 1.5x font size |
| Column Layout | Single column, reflowable text |
| Headings | Semantic HTML (h1, h2, h3), styled via CSS |
| Figures/Tables | Embedded images optimized for reMarkable 1 (1404×1872px), captions below |
| Pagination | Dynamic (reflows based on user font size) |

### 4.6 Annotation Zones
- **Margins**: Generous margins via CSS for reMarkable annotations
- **Page Breaks**: Strategic breaks using CSS (avoid splitting sections)
- **Visual Cues**: Subtle chapter separators and section breaks
- **EPUB Advantage**: reMarkable's native annotation works seamlessly with EPUB

### 4.7 reMarkable Integration
- **Method 1**: rmapi (command-line tool)
  - Direct upload to device via USB/WiFi
  - No cloud dependency
- **Method 2**: reMarkable Cloud API
  - Sync to cloud account
  - Requires OAuth authentication
- **Folder Organization**: Auto-create folders by topic/date
- **Metadata**: Preserve title, authors, publication date

### 4.8 User Interface
- **CLI (Phase 1)**: Command-line interface for power users
  ```bash
  arxiv2rm convert https://arxiv.org/abs/2301.12345
  arxiv2rm batch papers.txt
  arxiv2rm config --font-size 16
  ```
- **Web UI (Phase 2)**: Simple web interface
  - Drag-and-drop PDF upload
  - URL input field
  - Live preview of converted page
  - Settings panel

---

## 5. Non-Functional Requirements

### 5.1 Performance
- Conversion speed: <2 minutes for 20-page paper (excluding OCR)
- OCR processing: <5 seconds per page (Deepseek-OCR)
- Memory usage: <500MB during conversion
- Batch processing: 10+ papers without manual intervention

### 5.2 Reliability
- Handle network failures gracefully (retry with exponential backoff)
- Resume interrupted conversions
- Validate output PDF before upload
- Cache intermediate results (OCR text, images)

### 5.3 Usability
- Zero-config startup for basic use
- Clear error messages with actionable fixes
- Progress indicators for long operations
- Comprehensive documentation with examples

### 5.4 Security & Privacy
- No data retention: Delete cached files after 24 hours
- OCR via Groq API with optional local execution
- Encrypted storage of reMarkable credentials
- No telemetry without user consent

### 5.5 Compatibility
- Operating Systems: macOS
- Python: 3.9+
- reMarkable 1 : v2.x firmware (2.15+)
- PDF Standards: PDF 1.4-2.0

---

## 6. Technical Architecture

### 6.1 System Components
```
┌─────────────────┐
│  Input Handler  │  (URL fetch, file upload, PDF backlog)
└────────┬────────┘
         │
┌────────▼────────┐
│ Source Detector │  (ArXiv LaTeX? PDF with text? Scanned?)
└────────┬────────┘
         │
    ┌────▼─────┐
    │ LaTeX?   │──Yes──┐
    └────┬─────┘       │
         │No           │
    ┌────▼─────┐       │
    │ OCR?     │──Yes──┤
    └────┬─────┘       │
         │No           │
         │             │
┌────────▼────────┐    │
│  OCR Engine     │    │
│ (Deepseek-OCR)  │────┤
└─────────────────┘    │
         │             │
         └─────┬───────┘
               │
┌──────────────▼──────────┐
│  Content Processor      │  (extract text, images, structure)
└──────────────┬──────────┘
               │
┌──────────────▼──────────┐
│  Image Optimizer        │  (resize to 1404×1872, optimize for e-ink)
└──────────────┬──────────┘
               │
┌──────────────▼──────────┐
│  EPUB Generator         │  (HTML + CSS + embedded fonts)
└──────────────┬──────────┘
              │
┌─────────────▼──────────┐
│  reMarkable Uploader   │  (rmapi, Cloud API)
└────────────────────────┘
```

### 6.2 Technology Stack
| Layer | Technology | Rationale |
|-------|------------|-----------|
| Language | Python 3.9+ | Rich ecosystem for PDF/OCR/EPUB |
| OCR | Deepseek-OCR via Groq API | Math notation support, fast inference |
| PDF Input | PyMuPDF (fitz) | Fast, reliable parsing |
| EPUB Output | ebooklib | EPUB 3.0 generation |
| HTML/CSS | BeautifulSoup4 | Content structuring |
| Image Processing | Pillow | Resize/optimize for reMarkable 1 (1404×1872) |
| Vision Models | mlx-vlm (Qwen2.5-VL, Pixtral) | Local image understanding, 30-50% faster |
| Image Classification | pyobjc-framework-Vision (macOS) | Native Apple Vision framework, built-in |
| Typography | OpenDyslexic (embedded) | Dyslexia-friendly, included in EPUB |
| reMarkable Sync | rmapi | Community-proven tool |
| CLI | Click | Modern Python CLI framework |
| Config | python-dotenv | Environment management |
| Testing | pytest | Standard Python testing |

### 6.3 Data Flow
1. **Input**: User provides ArXiv URL, local PDF, or PDF backlog
2. **Source Detection**:
   - ArXiv: Try to fetch LaTeX source + images
   - PDF: Check for text layer
3. **Content Extraction**:
   - LaTeX: Parse .tex files, extract structure and images
   - PDF with text: Use PyMuPDF to extract text
   - Scanned PDF: Convert pages to images (150 DPI)
4. **OCR** (if needed):
   - Prepare images for Deepseek-OCR processing
   - Submit to Deepseek-OCR via Groq API
   - Extract structured text (fast inference)
5. **Image Processing**:
   - Extract figures/diagrams from PDF or LaTeX
   - Resize to reMarkable 1 resolution (1404×1872px)
   - Optimize for e-ink (contrast, dithering)
   - Add EXIF metadata (source, page number)
6. **EPUB Generation**:
   - Convert text to semantic HTML (h1, h2, p, figure)
   - Apply CSS with OpenDyslexic font
   - Embed optimized images
   - Create navigation (Table of Contents)
   - Package as EPUB 3.0
7. **Upload**: Push to reMarkable via rmapi or Cloud API
8. **Cleanup**: Delete temporary files (images, cache)

---

## 7. User Stories & Acceptance Criteria

### 7.1 Core Stories

#### Story 1: Convert ArXiv Paper
**As a** researcher
**I want to** paste an ArXiv URL and get a reMarkable-optimized EPUB
**So that** I can read it comfortably with adjustable font size on my devic

**Acceptance Criteria**:
- CLI accepts ArXiv URLs in format `https://arxiv.org/abs/YYMM.NNNNN`
- Downloads LaTeX source when available (faster, better quality)
- Uses PDF + OCR if LaTeX unavailable
- Generates EPUB 3.0 with embedded OpenDyslexic font
- Images optimized for reMarkable 1 (1404×1872px)
- Uploads to reMarkable "Research" folder
- Completes in <3 minutes for 20-page paper
- User can adjust font size on device without pagination issues

#### Story 2: OCR Scanned Paper (Local deepseek-ocr.rs)
**As a** student
**I want to** convert a scanned PDF with no text layer
**So that** I can search and copy text on reMarkable

**Acceptance Criteria**:
- Detects missing text layer automatically
- Runs OCR using local deepseek-ocr.rs (Metal GPU acceleration)
- Achieves >95% accuracy on standard text
- Preserves mathematical notation
- Searchable EPUB output with reflowable text
- Shows progress bar during OCR processing
- Images resized to 1404×1872px for optimal display
- **LOCAL FIRST**: Uses free local OCR (deepseek-ocr.rs) by default
- **Optional fallback**: Groq API (Llama 4 Scout vision model) if local unavailable

#### Story 3: Batch Convert Papers
**As a** busy professional
**I want to** convert 10 papers at once
**So that** I don't have to babysit the process

**Acceptance Criteria**:
- Accepts text file with list of URLs/paths
- Processes papers sequentially
- Shows overall progress (3/10 completed)
- Handles failures gracefully (skip and continue)
- Generates summary report at end
- All papers uploaded to reMarkable

#### Story 4: Customize Layout
**As a** user with specific needs
**I want to** adjust EPUB styling preferences
**So that** the output matches my reading preferences

**Acceptance Criteria**:
- Configuration file or CLI flags for settings
- Default font size recommendation (14-18pt)
- CSS margin customization
- Image optimization level (quality vs file size)
- Settings persist across sessions
- EPUB validates against EPUB 3.0 standard
- User can adjust font size on device after conversion

---

## 8. Design & UX

### 8.1 CLI Interface
```bash
# Basic usage
$ arxiv2rm convert https://arxiv.org/abs/2301.12345
Fetching LaTeX source... ✓
Extracting images... ✓ (3 figures found)
Optimizing images for reMarkable 1... ✓
Generating EPUB... ████████████ 100%
Uploading to reMarkable... ✓
Done! EPUB available in 'Research' folder.

# With options
$ arxiv2rm convert paper.pdf \
    --format epub \
    --ocr-engine groq \
    --image-quality high \
    --remarkable-folder "To Read"

# Batch processing
$ arxiv2rm batch papers.txt --parallel 3
Processing 10 papers...
[1/10] arxiv:2301.12345 ✓
[2/10] arxiv:2302.67890 ✓
[3/10] local/paper.pdf ⚠ OCR failed (Deepseek-OCR unavailable)
...
Summary: 9 succeeded, 1 warning, 0 failed

# Configuration
$ arxiv2rm config --set ocr-engine groq
$ arxiv2rm config --set image-max-width 1404
$ arxiv2rm config --set image-max-height 1872
$ arxiv2rm config --show
```

### 8.2 Configuration File
```yaml
# ~/.arxiv2rm/config.yaml
output:
  format: "epub"  # EPUB 3.0 for reflowable content

typography:
  font_family: "OpenDyslexic"  # Embedded in EPUB
  default_font_size: 16  # Recommendation only (user adjustable)
  line_height: 1.5

layout:
  margins:
    top: 2em
    bottom: 2em
    left: 1.5em
    right: 1.5em
  single_column: true

images:
  max_width: 1404  # reMarkable 1 width
  max_height: 1872  # reMarkable 1 height
  optimize_for_eink: true
  quality: 85  # JPEG quality (1-100)

ocr:
  engine: "groq"  # Groq Vision API (Llama 4 Scout)
  groq_api_key: ${GROQ_API_KEY}
  groq_model: "meta-llama/llama-4-scout-17b-16e-instruct"  # Primary vision model
  fallback_models: ["llama-3.2-90b-vision-preview", "llama-3.2-11b-vision-preview"]
  language: "eng"
  prompt: "Extract all text from this image. Transcribe exactly what you see, preserving line breaks and formatting. Focus on accuracy."

remarkable:
  method: "rmapi"  # or "cloud"
  default_folder: "Research"
  cloud_token: ${REMARKABLE_TOKEN}
```

---

## 9. Implementation Plan

### Phase 1: MVP (4-6 weeks)
**Goal**: Convert ArXiv papers to EPUB format

**Features**:
- ArXiv URL support (LaTeX source preferred)
- ArXiv PDF with text extraction
- Image extraction and optimization (1404×1872px)
- EPUB 3.0 generation with OpenDyslexic font
- Reflowable layout (single column)
- rmapi upload
- CLI interface

**Deliverables**:
- Working Python package
- CLI with `convert` command
- EPUB validator integration
- Basic documentation
- 10 test papers converted successfully (EPUB format)

### Phase 2: OCR & Customization (4-6 weeks)
**Goal**: Handle scanned papers and user preferences

**Features**:
- Deepseek-OCR integration for scanned PDFs
- Configurable EPUB styling (CSS)
- Image quality/size optimization levels
- Batch processing
- Progress indicators
- Error handling & retry logic

**Deliverables**:
- Deepseek-OCR pipeline (fast processing)
- Config file support
- Batch mode
- Image optimizer with e-ink presets
- Extended documentation

### Phase 3: Polish & Distribution (3-4 weeks)
**Goal**: Production-ready tool

**Features**:
- IEEE/ACM support
- Local PDF optimization
- PDF backlog processing
- EPUB validation and quality checks
- Web UI (simple Flask app)
- Installer/packaging (pip, Docker)
- Comprehensive tests
- User guide & examples

**Deliverables**:
- PyPI package
- Docker image
- Web interface with EPUB preview
- Video tutorial
- GitHub release
- EPUB sample gallery

---

## 10. Open Questions & Risks

### Open Questions
1. **Deepseek-OCR API**: Pricing model? Rate limits?
2. **reMarkable EPUB support**: Full EPUB 3.0 compatibility on reMarkable 1/2?
3. **Formula preservation**: MathML in EPUB vs images for mathematical notation?
4. **Batch size**: How many papers can typical user convert in one session?
5. **LaTeX parsing**: Which Python library for .tex parsing (TexSoup, PyLaTeX)?

### Risks & Mitigations
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Deepseek-OCR API unavailable | High | Medium | Fail gracefully with clear error message |
| reMarkable EPUB rendering issues | High | Medium | Test extensively with sample papers |
| Poor OCR accuracy on formulas | Medium | High | Preserve formula images in EPUB |
| EPUB file size too large | Medium | Medium | Optimize images aggressively, use adaptive quality |
| LaTeX parsing failures | Medium | Medium | Fallback to PDF extraction |
| Copyright issues (IEEE/ACM) | High | Low | Require user authentication, respect paywalls |

---

## 11. Future Enhancements (Post-MVP)

### Phase 4+: Advanced Features
- **Smart annotations**: Auto-extract key sentences, create summary page in EPUB
- **Citation management**: Integration with Zotero/Mendeley, export to bibliography
- **Collaborative notes**: Sync EPUB annotations to cloud
- **Mobile app**: iOS/Android for on-the-go conversion
- **Browser extension**: Right-click "Send to reMarkable as EPUB"
- **EPUB theme library**: Multiple CSS themes (compact, spacious, academic, high-contrast)
- **Multi-language**: Support for non-English papers (multilingual OCR)
- **Audio narration**: TTS integration for accessibility (EPUB 3.0 media overlays)
- **Interactive elements**: Embedded videos/links in EPUB (for supplementary materials)
- **MathML support**: Native mathematical notation rendering in EPUB

---

## 12. Appendices

### A. Competitive Analysis
| Product | Strengths | Weaknesses |
|---------|-----------|------------|
| PDF Expert | Good annotation tools | Not optimized for e-ink, fixed pagination |
| Zotero | Reference management | No reMarkable integration, no EPUB output |
| Calibre | EPUB conversion | Poor scientific PDF handling, no OCR, generic output |
| reMarkable native | Seamless sync | No preprocessing, small fonts, fixed PDF layout |
| k2pdfopt | Reflow PDFs | Outdated, no EPUB output, complex setup |

**Differentiation**: Only tool specifically designed for scientific papers + reMarkable + EPUB (reflowable) + Deepseek-OCR + dyslexia-friendly typography + image optimization for e-ink.

### B. Font Licensing
- **OpenDyslexic**: Open Font License (OFL), free for commercial use
- **Distribution**: Can bundle font with application
- **Attribution**: Required in documentation

### C. reMarkable Specifications
- **Model**: reMarkable 1
- **Screen**: 10.3" E Ink Carta, 1872×1404 pixels (226 DPI)
- **Optimal Image Size**: 1404×1872 (portrait orientation)
- **Formats**: PDF, EPUB (EPUB preferred for reflowable content)
- **EPUB Support**: EPUB 2.0 and 3.0, reflowable and fixed-layout
- **Annotations**: Vector-based, stored in .rm files, works natively with EPUB
- **Font Rendering**: Supports embedded fonts (OpenDyslexic can be included)
- **Sync**: WiFi, USB, Cloud (optional)

### D. OCR Comparison (Test Results: 2025-11-24)
| Engine | Accuracy | Speed | Cost | Math Support | Handwriting |
|--------|----------|-------|------|--------------|-------------|
| **Groq Vision (Llama 4 Scout)** | **High** | **0.5-1.5s/page** | **~2000 tokens/page** | **Excellent** | **Excellent** |
| Google Cloud Vision | 97% | 1-2s/page | $1.50/1000 pages | Good | Good |
| AWS Textract | 96% | 1-2s/page | $1.50/1000 pages | Good | Good |
| Tesseract 5.5.1 (local) | 92% print, ~20% handwritten | 0.3s/page | Free | Fair | Poor |

**Test Methodology**: 3 handwritten French newsletter pages (140-200KB PNGs)
- **Groq Vision**: 408, 311, 272 chars extracted (meaningful, readable French text)
- **Tesseract**: 168, 120, 64 chars extracted (mostly gibberish)
- **Speed**: Tesseract 3-5x faster but unusable for handwriting
- **Quality**: Groq Vision correctly recognized cursive French, preserved structure

**Recommendation**: Groq Vision API (Llama 4 Scout) as primary OCR engine
- Best quality for handwritten annotations, scanned papers, mathematical notation
- Fast inference through Groq infrastructure
- No local OCR fallback needed - single focused solution
- Test script available: [test_ocr_comparison.py](test_ocr_comparison.py)

**API Discovery**:
```bash
# Get all available Groq models dynamically
curl -X GET "https://api.groq.com/openai/v1/models" \
     -H "Authorization: Bearer $GROQ_API_KEY" \
     -H "Content-Type: application/json"
```

---

## 13. Success Criteria (Go/No-Go)

### Launch Criteria
- [ ] Convert 50 test papers to EPUB with >90% success rate
- [ ] EPUB validates against EPUB 3.0 standard
- [ ] OCR accuracy >95% on 20 sample papers (Deepseek-OCR)
- [ ] Average conversion time <2 min (20-page paper)
- [ ] Images optimized correctly (1404×1872px, <500KB each)
- [ ] EPUBs display correctly on reMarkable 1
- [ ] Font size adjustable on device without layout issues
- [ ] Zero crashes on happy path
- [ ] Documentation complete (README, usage guide, API docs)
- [ ] 5 beta users complete end-to-end workflow
- [ ] All P0 features implemented

### KPIs (6 months post-launch)
- 100+ active users
- 1000+ papers converted to EPUB
- 4.5/5 average user rating
- <5% support ticket rate
- 50% batch usage adoption
- 80%+ prefer EPUB over PDF (user survey)

---

## Document Metadata
- **Version**: 1.0
- **Date**: 2025-11-23
- **Author**: Product Team
- **Status**: Draft
- **Next Review**: After Phase 1 completion
