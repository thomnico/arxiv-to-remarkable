# ADR-002: Switch from EPUB to PDF Output Format

## Status
**ACCEPTED** - 2024-11-26

## Context

Our current approach generates EPUB files optimized for reMarkable e-ink tablets. After extensive testing, we've identified critical issues with EPUB rendering on reMarkable:

### Problems Observed

| Issue | Severity | Example |
|-------|----------|---------|
| **Missing word spaces** | Critical | "ConceptionsofOverparenting" instead of "Conceptions of Overparenting" |
| **Blank pages** | Critical | ~40% of pages render completely blank (pagination bug) |
| **Garbled TOC** | Medium | Chapter titles without spaces in navigation |
| **Text extraction issues** | Critical | pdfplumber loses character spacing on certain PDFs |

### Root Causes

1. **pdfplumber extraction**: Loses word spacing on certain PDF encodings
2. **reMarkable EPUB renderer**: Creates spurious blank pages (documented in REMARKABLE_BLANK_PAGES_ISSUE.md)
3. **EPUB internal conversion**: reMarkable converts EPUB to internal format poorly

### Research Findings

According to [reMarkable documentation](https://remarkable.jms1.info/faq/file-types.html) and [community discussions](https://borednbookless.com/remarkable-as-an-e-reader-a-must-read-guide/):

- **PDFs work natively**: reMarkable holds PDFs unmodified, overlays annotations separately
- **EPUBs are converted internally**: Large EPUBs take forever to open, often render poorly
- **Recommendation**: "Use Calibre to output to reMarkable PDF dimensions rather than wait for internal EPUB generation"

## Decision

**Generate optimized PDF output instead of EPUB for reMarkable.**

### PDF Generation Strategy

```text
Source PDF → Text Extraction (PyMuPDF) → Layout Engine → Optimized PDF
                                              ↓
                                    - OpenDyslexic font
                                    - Single column
                                    - 1404×1872px pages
                                    - Generous margins
                                    - e-ink optimized
```

### Key Changes

| Aspect | EPUB (Old) | PDF (New) |
|--------|------------|-----------|
| **Format** | EPUB 3.0 | PDF 1.5 |
| **Font embedding** | Via CSS @font-face | Direct embedding |
| **Layout** | Reflowable | Fixed (pre-rendered) |
| **Font size** | User-adjustable on device | Pre-set during conversion (CLI flag) |
| **Page size** | Dynamic | 1404×1872px (reMarkable 1) |
| **Text extraction** | pdfplumber → html | PyMuPDF → reportlab |
| **Blank pages** | Frequent | None (direct rendering) |
| **Word spacing** | Often lost | Preserved (glyph-level control) |

### PDF Generation Library

**Primary**: `reportlab` (Python)
- Industry-standard PDF generation
- Full font embedding support
- Precise glyph positioning (no spacing issues)
- Image embedding with quality control
- Table support

**Alternative**: `weasyprint` (HTML to PDF)
- CSS-based styling
- More familiar for web developers
- Good for complex layouts

### Implementation Architecture

```python
class PDFBuilder:
    """Generate optimized PDF for reMarkable."""

    def __init__(self, page_size=(1404, 1872)):
        self.page_width, self.page_height = page_size
        self.font_family = "OpenDyslexic"
        self.font_size = 14  # Configurable
        self.margin = 72  # 1 inch margins

    def add_chapter(self, title: str, content: str, images: List[Path]):
        """Add a chapter with text and images."""
        pass

    def build(self, output_path: Path) -> Path:
        """Generate the final PDF."""
        pass
```

### Text Extraction Fix

Switch from pdfplumber to PyMuPDF for text extraction:

```python
# OLD (loses spaces on some PDFs):
import pdfplumber
with pdfplumber.open(pdf_path) as pdf:
    text = page.extract_text()  # "NaHu1,2,KewanChen1"

# NEW (preserves spacing):
import fitz  # PyMuPDF
doc = fitz.open(pdf_path)
text = page.get_text("text")  # "Na Hu 1,2, Kewan Chen 1"
```

### Font Size Trade-off

| Approach | Pros | Cons |
|----------|------|------|
| **EPUB (reflowable)** | User adjusts on device | Rendering bugs, blank pages |
| **PDF (fixed)** | Perfect rendering | Must choose size at conversion |

**Mitigation**: Provide `--font-size` CLI flag (default: 14pt, options: 12, 14, 16, 18)

```bash
arxiv2rm convert paper.pdf --font-size 16  # Larger text
arxiv2rm convert paper.pdf --font-size 12  # More text per page
```

## Consequences

### Positive

1. **No blank pages**: PDF renders exactly as generated
2. **Preserved word spacing**: Glyph-level control eliminates spacing issues
3. **Native reMarkable support**: PDFs work perfectly, annotations overlay cleanly
4. **Faster opening**: No internal conversion delay
5. **Predictable layout**: WYSIWYG - what you generate is what you get

### Negative

1. **No reflowable text**: Font size must be chosen at conversion time
2. **Larger file sizes**: PDF with embedded fonts > EPUB
3. **No device font adjustment**: User cannot change font size on reMarkable
4. **Code rewrite**: EPUBBuilder → PDFBuilder requires significant changes

### Neutral

1. **Image handling**: Similar approach (extract, optimize, embed)
2. **Chapter detection**: Same logic, different output format
3. **Metadata**: Both formats support title, author, etc.

## Implementation Plan

### Phase 1: PDF Builder (Priority)
1. Create `PDFBuilder` class using reportlab
2. Implement OpenDyslexic font embedding
3. Add text layout with proper spacing
4. Image embedding with reMarkable optimization

### Phase 2: Text Extraction Fix
1. Switch default extractor from pdfplumber to PyMuPDF
2. Add quality detection (space ratio check)
3. Keep pdfplumber as fallback for tables

### Phase 3: CLI Updates
1. Add `--font-size` flag
2. Update default output format to PDF
3. Keep `--format epub` for users who want it

### Phase 4: Testing
1. Convert 50 test papers to PDF
2. Verify on reMarkable device
3. Compare quality vs EPUB output

## Alternatives Considered

### 1. Fix EPUB Rendering (Rejected)
- **Why rejected**: reMarkable EPUB renderer is closed-source, cannot fix
- **Attempted**: KePub format, CSS tweaks, different page structures
- **Result**: All attempts failed (see REMARKABLE_BLANK_PAGES_ISSUE.md)

### 2. Use Calibre for EPUB→PDF (Rejected)
- **Why rejected**: Extra dependency, less control over output
- **Issue**: Still requires EPUB as intermediate format

### 3. Keep Both Formats (Considered)
- **Status**: Will implement, PDF as default, EPUB as option
- **Rationale**: Some users may prefer reflowable text despite issues

## References

- [REMARKABLE_BLANK_PAGES_ISSUE.md](REMARKABLE_BLANK_PAGES_ISSUE.md) - Documented EPUB issues
- [ADR-001-formula-rendering.md](ADR-001-formula-rendering.md) - Formula extraction approach
- [reMarkable File Types FAQ](https://remarkable.jms1.info/faq/file-types.html)
- [reMarkable E-Reader Guide](https://borednbookless.com/remarkable-as-an-e-reader-a-must-read-guide/)

## Date
2024-11-26

## Authors
- Claude (AI Assistant)
- Project maintainers
