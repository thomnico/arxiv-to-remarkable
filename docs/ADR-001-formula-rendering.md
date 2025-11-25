# ADR-001: Mathematical Formula Rendering Strategy

## Status
Accepted

## Context

Academic PDFs, especially those from ArXiv and IEEE, contain complex mathematical formulas with:
- Greek letters (λ, τ, σ, α, β, etc.)
- Mathematical operators (←, →, ∈, ∀, ∃, ≤, ≥)
- Large delimiters (brackets, braces, parentheses spanning multiple lines)
- Subscripts and superscripts
- Special fonts (CMEX10, CMSY10, CMMI10, CMR10 from LaTeX)

When converting PDF to EPUB for reMarkable e-ink display, we face several challenges:

1. **Font Compatibility**: LaTeX math fonts (Computer Modern) use Private Use Area (PUA) Unicode characters (U+E000-U+F8FF) that don't render in standard fonts
2. **OpenDyslexic Limitations**: Our primary font (OpenDyslexic) lacks math symbols
3. **Complex Formatting**: Multi-line equations with aligned brackets cannot be reliably recreated in HTML/CSS
4. **Rendering Fidelity**: Text-based extraction loses visual formatting that is essential for understanding

## Decision

**Extract mathematical formulas as images directly from the PDF** rather than attempting to convert them to text/HTML.

### Detection Criteria for Matrix/Bracket Formulas

**Strict detection**: Only extract formulas with CMEX10 bracket pieces that CANNOT be rendered as text.

A text block requires image extraction if it contains:

- **CMEX10 bracket pieces** (PUA characters U+F8EE to U+F8FF)

These are the vertical components of large brackets (⎡⎢⎣⎤⎥⎦⎧⎨⎩⎫⎬⎭) that span multiple lines in display equations like:

```text
    ⎡                    ⎤
Pr ⎢ Dec_sk(c_y) = f(x) ⎥ = 1
    ⎣                    ⎦
```

This strict approach avoids false positives and only extracts formulas that truly require image rendering.

### Implementation

```python
def extract_matrix_formulas(self, pdf_path: Path, output_dir: Path) -> List[Dict]:
    """
    Extract matrix/bracket notation as images from PDF.
    Only detects blocks with CMEX10 bracket pieces (U+F8EE-U+F8FF).
    """
    # First pass: detect blocks with bracket pieces
    for block in page.get_text("dict")["blocks"]:
        for span in block["lines"][...]["spans"]:
            for c in span["text"]:
                if 0xF8EE <= ord(c) <= 0xF8FF:
                    bracket_blocks.append(block)

    # Second pass: merge adjacent bracket blocks
    # Large brackets span multiple text blocks that must be combined

    # Third pass: extract merged regions as images
```

### Merging Adjacent Bracket Blocks

Large multi-line equations have bracket pieces in separate text blocks:

- Left bracket upper corner (⎡) - one block
- Left bracket extension (⎢) - separate block
- Left bracket lower corner (⎣) - separate block
- Content blocks in between
- Right bracket pieces - separate blocks

These must be merged vertically (within 30px) to capture the complete formula as a single image.

### Image Extraction Parameters

- **Zoom factor**: 2.5x (good balance of quality and file size)
- **Padding**: 15px horizontal, 8px vertical
- **Format**: PNG (lossless, good for text/line art)

## Consequences

### Positive
- **Perfect rendering fidelity**: Formulas look exactly as in the original PDF
- **No font dependency**: Images render on any device
- **Handles all complexity**: Multi-line equations, matrices, aligned brackets all work
- **Predictable output**: No surprises from font substitution or missing glyphs

### Negative
- **Larger file size**: PNG images add to EPUB size (mitigated by selective extraction)
- **No text selection**: Users cannot copy formula text
- **Fixed scaling**: Images don't reflow with text (acceptable for display equations)
- **Accessibility**: Screen readers cannot read formula images (future: add alt text with LaTeX)

### Neutral
- **Hybrid approach**: Regular text uses OpenDyslexic, formulas use images
- **Processing time**: Additional step to extract images (acceptable for batch processing)

## Alternatives Considered

### 1. MathML Conversion
- **Rejected**: EPUB readers have inconsistent MathML support; requires complex LaTeX parsing

### 2. Unicode Character Mapping
- **Partially used**: We map known PUA chars to Unicode equivalents for inline math
- **Insufficient**: Cannot handle multi-line display equations or complex formatting

### 3. SVG Rendering
- **Rejected**: More complex than PNG; limited benefit for static formulas

### 4. Re-typesetting with MathJax/KaTeX
- **Rejected**: Requires LaTeX source (not available from PDF); introduces new rendering engine

## Implementation Notes

### PUA Character Mapping (for inline math)

For simple inline math that can be rendered as text, we map CMEX10 PUA characters:

```python
PUA_UNICODE_MAP = {
    0xF8EE: '⎡',  # Left square bracket upper
    0xF8EF: '⎣',  # Left square bracket lower
    0xF8F9: '⎤',  # Right square bracket upper
    0xF8FA: '⎦',  # Right square bracket lower
    # ... etc
}
```

### CSS for Formula Images

```css
.formula {
    text-align: center;
    margin: 1em 0;
}
.formula-img {
    max-width: 100%;
    height: auto;
}
```

## Related Documents

- [GROQ_OCR_INTEGRATION.md](GROQ_OCR_INTEGRATION.md) - OCR for scanned PDFs
- [automated_ocr_routing.md](automated_ocr_routing.md) - Handwriting detection

## Date
2024-11-25

## Authors
- Claude (AI Assistant)
- Project maintainers
