# ArXiv to reMarkable - Task Breakdown

> **Note**: Output format changed from EPUB to **PDF** per [ADR-002](docs/ADR-002-pdf-output-format.md).
> EPUB had critical rendering issues on reMarkable (blank pages, missing word spaces).

## Phase 1: MVP - Core Infrastructure (Weeks 1-6)

### Epic 1: Project Setup & Configuration
**Priority**: P0 | **Estimated**: 1 week

#### Task 1.1: Initialize Python Project
- Set up Python 3.9+ project structure
- Create `pyproject.toml` with dependencies
- Set up virtual environment
- Configure pytest for testing
- Add pre-commit hooks
**Dependencies**: None

#### Task 1.2: Environment Configuration
- Create `.env.template` with required variables
- Implement config loader (python-dotenv)
- Create YAML config parser
- Add config validation
**Dependencies**: 1.1

#### Task 1.3: CLI Framework Setup
- Implement Click-based CLI structure
- Add `convert`, `batch`, `config` commands
- Add `--font-size` flag (12/14/16/18pt)
- Implement progress bars
- Add logging configuration
**Dependencies**: 1.1, 1.2

---

### Epic 2: ArXiv Integration
**Priority**: P0 | **Estimated**: 1 week

#### Task 2.1: ArXiv API Client
- Implement ArXiv URL parser (extract paper ID)
- Create ArXiv API client (fetch metadata)
- Download LaTeX source (tar.gz)
- Download PDF fallback
- Implement caching mechanism
**Dependencies**: 1.1, 1.2

#### Task 2.2: LaTeX Source Processor (to PDF)

- Extract .tar.gz archives
- Parse main .tex file (identify structure)
- Extract figures/images from LaTeX
- Extract text content with structure
- Handle multi-file LaTeX projects
- **Output**: Structured content for PDF generation

**Dependencies**: 2.1

---

### Epic 3: PDF Processing (Input)

**Priority**: P0 | **Estimated**: 1 week

#### Task 3.1: PDF Text Extraction (PyMuPDF)

- Implement PyMuPDF-based text extraction (preserves word spacing)
- **Do NOT use pdfplumber** (loses spacing on certain PDFs)
- Detect text layer presence
- Extract document structure (headings, paragraphs)
- Extract metadata (title, authors)

**Dependencies**: 1.1

#### Task 3.2: PDF Image Extraction
- Extract embedded images from PDF
- Extract figures with bounding boxes
- Save images with metadata (page number, position)
**Dependencies**: 3.1

---

### Epic 4: Image Optimization
**Priority**: P0 | **Estimated**: 1 week

#### Task 4.1: Image Resizer for reMarkable 1
- Implement resize to 1404×1872px (portrait)
- Maintain aspect ratio (letterbox if needed)
- Support batch processing
**Dependencies**: 1.1

#### Task 4.2: E-ink Optimization
- Implement contrast enhancement for e-ink
- Add optional dithering
- Optimize JPEG quality (configurable 1-100)
- Add EXIF metadata (source, page number)
- Target <500KB per image
**Dependencies**: 4.1

---

### Epic 5: PDF Generation (Output) — *Changed from EPUB*

**Priority**: P0 | **Estimated**: 2 weeks

> See [ADR-002](docs/ADR-002-pdf-output-format.md) for rationale.

#### Task 5.1: PDFBuilder with reportlab

- Create `PDFBuilder` class using reportlab
- Set page size to 1404×1872px (reMarkable 1)
- Configure margins (72pt = 1 inch)
- Implement chapter/section structure
- Generate metadata (title, author)

**Dependencies**: 1.1

#### Task 5.2: Text Layout & Font Embedding

- Implement text flow with proper word spacing
- Glyph-level positioning (no spacing issues)
- Support configurable font size (12/14/16/18pt, default 14)
- Handle paragraphs and line breaks
- Embed images inline with text

**Dependencies**: 5.1

#### Task 5.3: OpenDyslexic Font Integration

- Embed OpenDyslexic font directly in PDF
- Register font with reportlab
- Set as default font family
- Configure line-height for readability

**Dependencies**: 5.2

#### Task 5.4: PDF Assembly & Validation

- Generate final PDF with embedded fonts + images
- Add table of contents / bookmarks
- Validate PDF renders correctly
- Test on reMarkable device (no blank pages!)
- Verify file size reasonable

**Dependencies**: 5.3

---

### Epic 6: reMarkable Integration
**Priority**: P0 | **Estimated**: 1 week

#### Task 6.1: rmapi Integration
- Install/detect rmapi binary
- Implement rmapi wrapper
- Upload PDF to device
- Create folders (e.g., "Research")
- Handle upload errors
**Dependencies**: 5.4

#### Task 6.2: reMarkable Cloud API (Alternative)
- Research Cloud API authentication (OAuth)
- Implement Cloud upload
- Handle token refresh
- Document setup instructions
**Dependencies**: 6.1
**Priority**: P1 (optional alternative)

---

## Phase 2: OCR & Advanced Features (Weeks 7-12)

### Epic 7: Groq Vision OCR
**Priority**: P0 | **Estimated**: 2 weeks

#### Task 7.1: Groq API Client
- Implement Groq Vision API client
- Base64 image encoding (<4MB check)
- Send OCR request (Llama 4 Scout model)
- Parse JSON response
- Handle rate limits and errors
**Dependencies**: 1.2, 4.1

#### Task 7.2: OCR Pipeline
- Detect when OCR is needed (no text layer)
- Convert PDF pages to images (150 DPI)
- Batch OCR processing (sequential)
- Show progress (0.5s per page estimate)
- Cache OCR results (SHA256 hash)
**Dependencies**: 3.1, 7.1

#### Task 7.3: Tesseract Fallback
- Detect Tesseract installation
- Implement Tesseract OCR wrapper
- Automatic fallback on Groq failure
- Support multiple languages (eng)
**Dependencies**: 7.2
**Priority**: P1

---

### Epic 8: Batch Processing
**Priority**: P1 | **Estimated**: 1 week

#### Task 8.1: Batch Input Handler
- Parse text file with URLs/paths
- Validate each input
- Create job queue
**Dependencies**: 1.3

#### Task 8.2: Batch Processor
- Sequential processing
- Progress tracking (N/M completed)
- Error handling (skip and continue)
- Generate summary report (successes, failures)
**Dependencies**: 2.1, 3.1, 5.4, 6.1, 8.1

---

### Epic 9: Configuration & Customization
**Priority**: P1 | **Estimated**: 1 week

#### Task 9.1: User Configuration
- Implement config file reader (~/.arxiv2rm/config.yaml)
- Add CLI flags for overrides
- Support image quality settings
- Support CSS customization
**Dependencies**: 1.2, 1.3

#### Task 9.2: PDF Typography Presets

- Create default typography preset
- Add high-contrast preset for e-ink
- Add compact preset (smaller font, more text per page)
- Support custom font size via CLI

**Dependencies**: 5.3, 9.1
**Priority**: P2

---

## Phase 3: Polish & Distribution (Weeks 13-16)

### Epic 10: Testing & Quality
**Priority**: P0 | **Estimated**: 2 weeks

#### Task 10.1: Unit Tests

- Test ArXiv client (mock API)
- Test PDF extraction (PyMuPDF)
- Test image optimization
- Test PDF generation (PDFBuilder)
- Target >80% coverage

**Dependencies**: All previous tasks

#### Task 10.2: Integration Tests

- End-to-end test (ArXiv URL → PDF)
- Test batch processing
- Test error scenarios
- Test on actual reMarkable 1

**Dependencies**: 10.1

#### Task 10.3: PDF Quality Tests

- Validate 50 sample papers converted to PDF
- Test on reMarkable 1 device (no blank pages!)
- Verify font rendering at different sizes
- Check image display quality
- Measure conversion times

**Dependencies**: 10.2

---

### Epic 11: Documentation
**Priority**: P0 | **Estimated**: 1 week

#### Task 11.1: User Documentation
- Write comprehensive README.md
- Create QUICKSTART.md guide
- Document configuration options
- Add troubleshooting section
**Dependencies**: All core features

#### Task 11.2: Developer Documentation
- Document architecture (ARCHITECTURE.md)
- Add API documentation (docstrings)
- Create CONTRIBUTING.md
- Document testing procedures
**Dependencies**: 11.1

#### Task 11.3: Example Gallery

- Convert 10 sample papers to PDF
- Create PDF gallery with screenshots on reMarkable
- Document common use cases

**Dependencies**: 10.3, 11.1

---

### Epic 12: Distribution
**Priority**: P1 | **Estimated**: 1 week

#### Task 12.1: PyPI Package
- Create setup.py / pyproject.toml
- Add entry points for CLI
- Test installation (pip install arxiv2rm)
- Publish to PyPI
**Dependencies**: 10.1, 11.1

#### Task 12.2: Docker Image
- Create Dockerfile
- Include all dependencies (Tesseract, fonts)
- Test container build
- Publish to Docker Hub
**Dependencies**: 12.1
**Priority**: P2

#### Task 12.3: CI/CD Pipeline
- Set up GitHub Actions
- Automate tests on push
- Automate PyPI publish on release
- Add lint checks
**Dependencies**: 10.1, 12.1

---

## Phase 4: Future Enhancements (Post-Launch)

### Epic 13: Extended Source Support
**Priority**: P2 | **Estimated**: 2 weeks

#### Task 13.1: IEEE Xplore Integration
- Research IEEE API
- Implement authentication
- Download PDFs
- Handle paywalls
**Dependencies**: 2.1

#### Task 13.2: ACM Digital Library
- Research ACM API
- Implement download
**Dependencies**: 13.1

#### Task 13.3: Generic PDF Backlog
- Support directory of PDFs
- Auto-detect metadata
- Batch process local files
**Dependencies**: 8.2

---

### Epic 14: Web Interface
**Priority**: P2 | **Estimated**: 3 weeks

#### Task 14.1: Flask Backend
- Create Flask app
- Upload endpoint
- Conversion endpoint
- WebSocket for progress
**Dependencies**: All core features

#### Task 14.2: Frontend UI

- Drag-and-drop upload
- URL input field
- Settings panel (font size, etc.)
- PDF preview

**Dependencies**: 14.1

---

## Dependency Graph Summary

```
Phase 1 Critical Path:
1.1 → 1.2 → 1.3 → 2.1 → 2.2 → 3.1 → 3.2 → 4.1 → 4.2 → 5.1 → 5.2 → 5.3 → 5.4 → 6.1

Phase 2 Critical Path:
6.1 → 7.1 → 7.2 → 8.1 → 8.2

Phase 3 Critical Path:
8.2 → 10.1 → 10.2 → 10.3 → 11.1 → 12.1
```

## Priority Legend
- **P0**: Must-have for MVP launch
- **P1**: Important for Phase 2
- **P2**: Nice-to-have, future enhancement

## Estimation Summary
- **Phase 1 (MVP)**: 6 weeks
- **Phase 2 (OCR & Batch)**: 4 weeks
- **Phase 3 (Polish & Distribution)**: 4 weeks
- **Total**: 14-16 weeks

## Notes
- Each task should fit within context window (~2000 tokens)
- Tasks are self-contained with clear inputs/outputs
- Dependencies are explicit for parallel work
- Testing integrated throughout
