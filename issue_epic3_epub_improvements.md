# Epic 3: EPUB Quality Improvements - Image Placement & Math Rendering

## Overview
Address two critical EPUB quality issues discovered during user testing of the "Attention Is All You Need" paper conversion.

## Issue 1: Image Duplication Across All Chapters ❌

### Current Behavior
All figures appear in every chapter, regardless of where they're actually referenced.

**Example**:
- Introduction chapter: Shows Figure 1 + Figure 2
- Background chapter: Shows Figure 1 + Figure 2
- Conclusion chapter: Shows Figure 1 + Figure 2
- **Result**: 7 chapters × 2 images = 14 duplicate image displays

### Root Cause
`epub_builder.py:262-276` - The `_build_chapter_html()` method adds ALL figures from `self.latex_doc.figures` to every chapter:

```python
if self.latex_doc and self.latex_doc.figures:
    for idx, figure in enumerate(self.latex_doc.figures):
        # No section filtering - adds to ALL chapters
        html += f"<figure>...</figure>"
```

### Expected Behavior
Figures should only appear in the section where they're defined or first referenced.

**Example**:
- Introduction: No images
- Model Architecture: Figure 1 (Transformer architecture)
- Attention Mechanism: Figure 2 (Scaled Dot-Product Attention)
- Other chapters: No images

### Proposed Fix
1. Track section association in `Figure` dataclass:
   - Add `source_section` field to track which section contains the figure
   - Extract from `figure_node.parent` or context during parsing

2. Modify `_build_chapter_html()` to filter figures:
   ```python
   # Only include figures that belong to this chapter
   chapter_figures = [
       f for f in self.latex_doc.figures
       if f.source_section == main_section.title
   ]
   for figure in chapter_figures:
       html += f"<figure>...</figure>"
   ```

3. Alternative: Use figure labels and `\ref{}` cross-references to determine placement

### Test Case
```python
def test_figure_placement_per_section():
    """Figures should only appear in their source section."""
    doc = LaTeXDocument()
    doc.sections = [
        Section(level=1, title="Introduction", content="..."),
        Section(level=1, title="Methods", content="..."),
    ]
    doc.figures = [
        Figure(number=1, source_section="Methods", ...),
    ]

    builder = EPUBBuilder(metadata, output_path)
    builder.build_from_latex(doc)

    # Check Introduction has NO images
    intro_html = builder._build_chapter_html(doc.sections[0], [])
    assert "<img" not in intro_html

    # Check Methods has 1 image
    methods_html = builder._build_chapter_html(doc.sections[1], [])
    assert intro_html.count("<img") == 1
```

---

## Issue 2: Math Formulas Rendered as Raw LaTeX ❌

### Current Behavior
Mathematical formulas appear as unreadable LaTeX source code in the EPUB:

**Inline Math**:
- Source: `$h_t$`, `$h_t-1$`, `$d_k$`, `$O(n^2)$`
- Rendered: Literal text "$h_t$", "$h_t-1$", "$d_k$", "$O(n^2)"
- Expected: Rendered math symbols (h with subscript t, etc.)

**Display Equations**:
- Source: `equation Attention(Q, K, V) = softmax( QK^T d_k)V equation`
- Rendered: Literal "equation Attention(Q, K, V) = ..." text
- Expected: Centered, formatted equation as image

**Other LaTeX Math Environments**:
- `align*`, `align`, `eqnarray`
- `tabular` (tables)
- `minipage`, `figure` (figure layout commands)

### Root Cause
`latex_processor.py:_node_to_text()` removes LaTeX commands but leaves math content as-is:
- Strips `\begin{}`, `\end{}`, `\textbf{}` etc.
- Does NOT process `$...$` (inline math)
- Does NOT render `equation` environments
- Math symbols like `α`, `β`, `∑` are lost

### Expected Behavior
Math should be rendered as images and embedded inline or as block elements.

**Inline Math**:
```html
<span class="math">
  <img src="math/eq_001.png" alt="h_t" style="display: inline; vertical-align: middle;"/>
</span>
```

**Display Equations**:
```html
<div class="equation">
  <img src="math/eq_002.png" alt="Attention(Q, K, V) = softmax(QK^T/sqrt(d_k))V" class="equation-image"/>
</div>
```

### Proposed Solution

#### Option A: LaTeX → Image Rendering (Recommended)
Use `latex` + `dvipng` or `pdflatex` + `convert` to render formulas to PNG:

1. **Extract math from LaTeX source** (`latex_processor.py`):
   ```python
   def extract_math_formulas(soup: TexNode) -> List[MathFormula]:
       formulas = []
       # Inline: $...$
       inline_math = re.findall(r'\$([^\$]+)\$', str(soup))
       # Display: \begin{equation}...\end{equation}
       for env in ['equation', 'align', 'align*', 'eqnarray']:
           display_math = soup.find_all(env)
       return formulas
   ```

2. **Render to images** (new `math_renderer.py`):
   ```python
   def render_latex_to_image(latex_code: str, output_path: Path) -> Path:
       # Create temp .tex file with preamble
       tex_content = f"""
       \\documentclass{{article}}
       \\usepackage{{amsmath,amssymb}}
       \\begin{{document}}
       \\pagestyle{{empty}}
       {latex_code}
       \\end{{document}}
       """
       # Compile: pdflatex → PDF
       # Convert: pdf2image or ImageMagick → PNG
       # Optimize for e-ink
       return output_path
   ```

3. **Replace in HTML** (`epub_builder.py`):
   ```python
   def _replace_math_with_images(self, content: str) -> str:
       # Replace $...$ with <img src="math/inline_N.png"/>
       # Replace equation environments with <div class="equation"><img.../></div>
       return content
   ```

#### Option B: MathJax/KaTeX + SVG
- Use MathJax or KaTeX to render math to SVG
- Embed SVG in EPUB (EPUB 3 supports SVG)
- **Pros**: Better quality, scalable
- **Cons**: Larger file size, not all readers support SVG well

#### Option C: Unicode Math Symbols
- Convert simple math to Unicode: `$α$` → `α`, `$β$` → `β`
- **Pros**: Lightweight, pure text
- **Cons**: Limited coverage, can't render complex equations

### Dependencies
- **Option A**: `pdflatex` or `latex`, `dvipng` or ImageMagick
- **Option B**: `mathjax-node` (Node.js) or `pymathjax`
- **Option C**: Custom Unicode mapping table

### Test Cases
```python
def test_inline_math_rendering():
    """Inline math should render as images."""
    content = "The hidden state $h_t$ depends on $h_{t-1}$."
    processor = LaTeXProcessor(...)
    doc = processor.process()

    builder = EPUBBuilder(metadata, output_path)
    builder.build_from_latex(doc)

    # Check HTML contains math images
    html = builder.chapters[0].content.decode('utf-8')
    assert '<img src="math/inline_' in html
    assert '$h_t$' not in html  # Raw LaTeX removed

def test_display_equation_rendering():
    """Display equations should render as centered images."""
    content = r"\begin{equation} E = mc^2 \end{equation}"
    # ... similar checks for block equation images
```

---

## Additional Cleanup Tasks

### Issue 3: Table/Figure LaTeX Markup Not Removed
**Examples**:
- `table[t] ... tabular ... center table`
- `figure minipage[t]0.5 ... minipage`

**Fix**: Extend `_node_to_text()` to strip:
```python
text = re.sub(r'\\begin\{(table|tabular|center|minipage)\}.*?\\end\{\1\}', '', text, flags=re.DOTALL)
```

### Issue 4: Figure References Not Replaced
**Example**: `See Figure~` should be `See Figure 1`

**Fix**:
```python
# In _node_to_text()
text = re.sub(r'Figure~\\ref\{([^}]+)\}', lambda m: f'Figure {ref_map.get(m.group(1), "?")}', text)
```

---

## Implementation Plan

### Phase 1: Image Placement (Priority: High)
- [ ] Add `source_section` to `Figure` dataclass
- [ ] Track section context during figure extraction
- [ ] Filter figures by section in `_build_chapter_html()`
- [ ] Add test cases for section-specific figures
- [ ] Regenerate demo EPUB and verify

**Estimated effort**: 2-3 hours
**Impact**: Immediate quality improvement

### Phase 2: Math Rendering (Priority: High)
- [ ] Research best approach (Option A, B, or C)
- [ ] Implement math extraction from LaTeX source
- [ ] Implement rendering pipeline (LaTeX → image)
- [ ] Integrate into EPUB builder
- [ ] Optimize images for e-ink display
- [ ] Add comprehensive test coverage
- [ ] Update documentation

**Estimated effort**: 1-2 days
**Impact**: Critical for scientific papers

### Phase 3: Cleanup (Priority: Medium)
- [ ] Remove table/figure markup
- [ ] Replace figure references with numbers
- [ ] Clean up remaining LaTeX artifacts

**Estimated effort**: 1-2 hours
**Impact**: Polish and readability

---

## Success Criteria

### Image Placement
- ✅ Each figure appears only once in the entire EPUB
- ✅ Figures appear in the correct section
- ✅ No duplicate images across chapters

### Math Rendering
- ✅ All inline math (`$...$`) rendered as inline images
- ✅ All display equations (`equation`, `align`, etc.) rendered as block images
- ✅ Math images optimized for reMarkable e-ink display (grayscale, high contrast)
- ✅ Fallback alt text provides the LaTeX source for accessibility
- ✅ No raw LaTeX math symbols in final EPUB

### Demo EPUB Quality
- ✅ "Attention Is All You Need" paper fully readable
- ✅ All equations displayed correctly
- ✅ File size < 5 MB (with math images)
- ✅ Renders correctly in Calibre and reMarkable device

---

## Related Files
- `src/arxiv2rm/latex_processor.py` - Math extraction
- `src/arxiv2rm/epub_builder.py` - Image placement, math integration
- `src/arxiv2rm/math_renderer.py` - **NEW** Math rendering module
- `tests/test_math_rendering.py` - **NEW** Math tests
- `demo_epub_generation.py` - Testing and validation

---

## References
- MathJax: https://www.mathjax.org/
- KaTeX: https://katex.org/
- dvipng: https://ctan.org/pkg/dvipng
- EPUB Math Support: https://www.w3.org/publishing/epub3/epub-contentdocs.html#sec-xhtml-mathml
