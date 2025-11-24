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
3. Extract text from PDF via OCR when needed (Groq Vision)
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

### 4.2 OCR Processing
- **Primary Engine**: DeepSync OCR using Groq access/API
  - Superior handling of mathematical notation
  - Multi-language support
  - Cloud API or local deployment
- **Smart Detection**: Skip OCR if PDF already has text layer
- **Formula Handling**: Preserve LaTeX or MathML when possible

### 4.3 Layout & Typography
| Feature | Specification |
|---------|---------------|
| Output Format | EPUB 3.0 (reflowable, not fixed-layout) |
| Font Family | OpenDyslexic (embedded), OpenSans (fallback) |
| Font Size | User configurable on device (EPUB advantage) |
| Default Font Size | 14-18pt recommended |
| Line Height | 1.5x font size |
| Column Layout | Single column, reflowable text |
| Headings | Semantic HTML (h1, h2, h3), styled via CSS |
| Figures/Tables | Embedded images optimized for reMarkable 1 (1404×1872px), captions below |
| Pagination | Dynamic (reflows based on user font size) |

### 4.4 Annotation Zones
- **Margins**: Generous margins via CSS for reMarkable annotations
- **Page Breaks**: Strategic breaks using CSS (avoid splitting sections)
- **Visual Cues**: Subtle chapter separators and section breaks
- **EPUB Advantage**: reMarkable's native annotation works seamlessly with EPUB

### 4.5 reMarkable Integration
- **Method 1**: rmapi (command-line tool)
  - Direct upload to device via USB/WiFi
  - No cloud dependency
- **Method 2**: reMarkable Cloud API
  - Sync to cloud account
  - Requires OAuth authentication
- **Folder Organization**: Auto-create folders by topic/date
- **Metadata**: Preserve title, authors, publication date

### 4.6 User Interface
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
- OCR processing: <5 seconds per page (DeepSync OCR)
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
- Local processing option (no cloud OCR)
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
│  (Groq Vision)  │────┤
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
| OCR | Groq Vision API (Llama 4) | Ultra-fast, accurate (0.5s/page, 100% accuracy) |
| OCR (Fallback) | Tesseract 5.0 | Offline, open-source |
| PDF Input | PyMuPDF (fitz) | Fast, reliable parsing |
| EPUB Output | ebooklib | EPUB 3.0 generation |
| HTML/CSS | BeautifulSoup4 | Content structuring |
| Image Processing | Pillow | Resize/optimize for reMarkable 1 (1404×1872) |
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
   - Resize images to optimize for Groq API (<4MB)
   - Submit to Groq Vision API (Llama 4 Scout)
   - Extract structured text (0.5s per page)
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
**So that** I can read it comfortably with adjustable font size on my device

**Acceptance Criteria**:
- CLI accepts ArXiv URLs in format `https://arxiv.org/abs/YYMM.NNNNN`
- Downloads LaTeX source when available (faster, better quality)
- Falls back to PDF + OCR if LaTeX unavailable
- Generates EPUB 3.0 with embedded OpenDyslexic font
- Images optimized for reMarkable 1 (1404×1872px)
- Uploads to reMarkable "Research" folder
- Completes in <3 minutes for 20-page paper
- User can adjust font size on device without pagination issues

#### Story 2: OCR Scanned Paper
**As a** student
**I want to** convert a scanned PDF with no text layer
**So that** I can search and copy text on reMarkable

**Acceptance Criteria**:
- Detects missing text layer automatically
- Runs OCR using Groq Vision API (Llama 4)
- Achieves >95% accuracy on standard text
- Preserves mathematical notation
- Searchable EPUB output with reflowable text
- Shows progress bar during OCR (0.5s per page)
- Images resized to 1404×1872px for optimal display

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
[3/10] local/paper.pdf ⚠ OCR failed, using fallback
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
  engine: "groq"  # Groq Vision API (Llama 4)
  groq_api_key: ${GROQ_API_KEY}
  fallback: "tesseract"
  language: "eng"

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
- ArXiv PDF fallback with text extraction
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
- Groq Vision OCR integration (Llama 4)
- Tesseract fallback
- Configurable EPUB styling (CSS)
- Image quality/size optimization levels
- Batch processing
- Progress indicators
- Error handling & retry logic

**Deliverables**:
- Groq OCR pipeline (0.5s per page)
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
1. **Groq Vision API pricing**: Current costs per page? Free tier limits?
2. **reMarkable EPUB support**: Full EPUB 3.0 compatibility on reMarkable 1/2?
3. **Formula preservation**: MathML in EPUB vs images for mathematical notation?
4. **Batch size**: How many papers can typical user convert before hitting Groq rate limits?
5. **LaTeX parsing**: Which Python library for .tex parsing (TexSoup, PyLaTeX)?

### Risks & Mitigations
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Groq Vision API unavailable | High | Medium | Implement Tesseract fallback |
| reMarkable EPUB rendering issues | High | Medium | Test extensively, provide PDF fallback option |
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

**Differentiation**: Only tool specifically designed for scientific papers + reMarkable + EPUB (reflowable) + Groq OCR + dyslexia-friendly typography + image optimization for e-ink.

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

### D. OCR Comparison
| Engine | Accuracy | Speed | Cost | Math Support |
|--------|----------|-------|------|--------------|
| Groq Vision (Llama 4) | 98-100% | 0.5s/page | Check groq.com/pricing | Excellent |
| Tesseract | 92% | 1-3s/page | Free | Fair |
| Google Cloud Vision | 97% | 1-2s/page | $1.50/1000 pages | Good |
| AWS Textract | 96% | 1-2s/page | $1.50/1000 pages | Good |

**Recommendation**: Groq Vision API (primary, ultra-fast) + Tesseract (offline fallback)

---

## 13. Success Criteria (Go/No-Go)

### Launch Criteria
- [ ] Convert 50 test papers to EPUB with >90% success rate
- [ ] EPUB validates against EPUB 3.0 standard
- [ ] OCR accuracy >95% on 20 sample papers (Groq Vision)
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
