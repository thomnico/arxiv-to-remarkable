# ArXiv to reMarkable - Task Breakdown

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

#### Task 2.2: LaTeX Source Processor
- Extract .tar.gz archives
- Parse main .tex file (identify structure)
- Extract figures/images from LaTeX
- Extract text content with structure
- Handle multi-file LaTeX projects
**Dependencies**: 2.1

---

### Epic 3: PDF Processing
**Priority**: P0 | **Estimated**: 1 week

#### Task 3.1: PDF Text Extraction
- Implement PyMuPDF-based text extraction
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

### Epic 5: EPUB Generation
**Priority**: P0 | **Estimated**: 2 weeks

#### Task 5.1: EPUB Structure Builder
- Create EPUB 3.0 package (ebooklib)
- Generate metadata (title, author, language)
- Create navigation (Table of Contents)
- Implement chapter/section structure
**Dependencies**: 1.1

#### Task 5.2: HTML Content Generation
- Convert text to semantic HTML (h1, h2, p)
- Handle paragraphs and line breaks
- Embed images with figure tags
- Add image captions
- Generate image references
**Dependencies**: 5.1

#### Task 5.3: CSS Styling
- Create base CSS stylesheet
- Embed OpenDyslexic font files
- Define typography (font-family, line-height)
- Set margins and spacing (em units)
- Add chapter breaks (page-break-after)
**Dependencies**: 5.2

#### Task 5.4: EPUB Assembly & Validation
- Package HTML + CSS + images + fonts
- Validate EPUB 3.0 compliance (epubcheck)
- Test with EPUB readers
- Verify file size (<50MB target)
**Dependencies**: 5.3

---

### Epic 6: reMarkable Integration
**Priority**: P0 | **Estimated**: 1 week

#### Task 6.1: rmapi Integration
- Install/detect rmapi binary
- Implement rmapi wrapper
- Upload EPUB to device
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

#### Task 9.2: EPUB Theme System
- Create default CSS theme
- Add high-contrast theme
- Add compact theme
- Allow user CSS injection
**Dependencies**: 5.3, 9.1
**Priority**: P2

---

## Phase 3: Polish & Distribution (Weeks 13-16)

### Epic 10: Testing & Quality
**Priority**: P0 | **Estimated**: 2 weeks

#### Task 10.1: Unit Tests
- Test ArXiv client (mock API)
- Test PDF extraction
- Test image optimization
- Test EPUB generation
- Target >80% coverage
**Dependencies**: All previous tasks

#### Task 10.2: Integration Tests
- End-to-end test (ArXiv URL → EPUB)
- Test batch processing
- Test error scenarios
- Test on actual reMarkable 1
**Dependencies**: 10.1

#### Task 10.3: EPUB Quality Tests
- Validate 50 sample papers
- Test on reMarkable 1 device
- Verify font size adjustment
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
- Convert 10 sample papers
- Create EPUB gallery with screenshots
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
- Settings panel
- EPUB preview
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
