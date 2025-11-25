# EPUB Generation Issues Found

## Analysis of 1706.03762.epub ("Attention Is All You Need")

### Issues Identified

#### 1. LaTeX Commands Not Removed ❌

**Problem**: Raw LaTeX commands appear in the EPUB output

**Examples**:
- `\beginabstract` instead of being removed
- `\endabstract` instead of being removed
- `\AND` in author list
- `\thanksEqual contribution...` in author names

**Root Cause**: The `_node_to_text()` method in `latex_processor.py` line 276-310:
- Only removes specific commands (`\textbf`, `\textit`, `\emph`, `\cite`, `\ref`, `\label`)
- Doesn't handle `\begin{...}` and `\end{...}` environments properly
- TexSoup is converting `\begin{abstract}` to `\beginabstract` (concatenated form)

**Impact**: Unreadable text with LaTeX syntax visible to end users

---

#### 2. Missing Section Content ❌

**Problem**: Chapters only show section titles, no body text

**Example**:
```html
<h1>Introduction</h1>
<p>Introduction</p>  <!-- Just repeats the title! -->
```

**Root Cause**: The `_extract_section_content()` method (line 266-274) is broken:
- Returns `self._node_to_text(section_node)` which only gets the title
- Doesn't extract the actual paragraph content following the section
- The text for "Introduction" is in a separate `\input{introduction}` file

**Impact**: EPUB is essentially empty - only structure, no content

---

#### 3. `\input` Files Not Read ❌

**Problem**: Content from `\input{filename}` commands is not extracted

**Example** from ms.tex:
```latex
\section{Introduction}
\input{introduction}  ← This content is NOT being read!
```

**Root Cause**: The `_extract_content()` method (line 170-218):
- Tracks `\input` files in `doc.included_files`
- Recursively calls `_extract_content()` on the included file
- BUT: The included file (e.g., `introduction.tex`) has NO `\section{}` commands
- It only has paragraph text, which TexSoup doesn't parse into the section structure

**Impact**: 90% of paper content is missing because it's in `\input` files

---

#### 4. Images Not Referenced in HTML ❌

**Problem**: Images are embedded in EPUB but not displayed in chapters

**Current State**:
- Images optimized ✅
- Images embedded in EPUB ✅
- Images **NOT referenced** in HTML ❌

**Missing**: No `<img>` or `<figure>` tags in the chapter HTML

**Root Cause**: The `_build_chapter_html()` method (line 230-266) doesn't:
- Check for figures associated with this chapter
- Insert `<figure>` and `<img>` tags
- Link figure numbers to image files

**Impact**: Images exist in EPUB but are never displayed

---

## Detailed Analysis

### Abstract Extraction

**Input** (ms.tex line 126):
```latex
\begin{abstract}
The dominant sequence transduction models...
\end{abstract}
```

**TexSoup Parsing**:
```python
soup.find("abstract")  # Returns the environment
```

**Current Output**:
```
\beginabstract The dominant...sequence data. \endabstract
```

**Expected Output**:
```
The dominant sequence transduction models are based on complex recurrent...
```

**Fix Needed**:
- Detect `\begin{abstract}` and `\end{abstract}` as environment delimiters
- Remove them before output
- Alternative: Use TexSoup's `.text` property instead of converting to string

---

### Section Content Extraction

**Input** (ms.tex line 145-147):
```latex
\section{Introduction}

\input{introduction}
```

**Input** (introduction.tex):
```latex
Recurrent neural networks, long short-term memory \citep{hochreiter1997}...

In this work we propose the Transformer, a model architecture...
```

**Current Behavior**:
- Section title extracted: "Introduction" ✅
- Section content: "Introduction" (just the title!) ❌
- `\input` file: Tracked but content NOT extracted ❌

**Expected Behavior**:
- Section title: "Introduction" ✅
- Section content: "Recurrent neural networks, long short-term memory..." ✅

**Fix Needed**:
- Read content from `\input` files
- Associate content with parent section
- Handle paragraphs (`\n\n` delimited) as separate `<p>` tags

---

### Author Extraction

**Input** (ms.tex):
```latex
\author{
  Ashish Vaswani\thanks{Equal contribution...}
  \AND
  Noam Shazeer
  \AND
  ...
}
```

**Current Output**:
```
\AND Ashish Vaswani\thanksEqual contribution...
```

**Expected Output**:
```
Ashish Vaswani, Noam Shazeer, Niki Parmar, ...
```

**Fix Needed**:
- Remove `\thanks{...}` footnotes
- Split on `\AND` (currently splitting on `\and`)
- Clean up remaining LaTeX commands

---

## Statistics

**Current EPUB**:
- File size: 210 KB
- Chapters: 9
- Abstract: 1,167 characters (with LaTeX commands)
- Section content: 12 characters average (titles only!)
- Images: 2 embedded, 0 displayed

**Expected EPUB**:
- File size: ~500 KB (with full content)
- Chapters: 8-9
- Abstract: ~1,000 characters (clean)
- Section content: ~5,000+ characters per section
- Images: 2 embedded, 2 displayed in chapters

---

## Proposed Fixes

### Priority 1: Content Extraction

1. **Read `\input` file contents** (latex_processor.py:197-207)
   ```python
   # Instead of just tracking the file:
   doc.included_files.append(input_file)

   # Actually read and extract its content:
   input_content = input_file.read_text()
   # Parse paragraphs and associate with current section
   ```

2. **Fix section content extraction** (latex_processor.py:266-274)
   ```python
   def _extract_section_content(self, section_node: TexNode) -> str:
       # Get all text nodes AFTER the section command
       # Until the next \section, \subsection, or \end{document}
       # Parse multiple paragraphs
   ```

### Priority 2: LaTeX Command Removal

3. **Remove `\begin` and `\end`** (latex_processor.py:276-310)
   ```python
   # Add to _node_to_text():
   text = re.sub(r'\\begin\{[^}]+\}', '', text)
   text = re.sub(r'\\end\{[^}]+\}', '', text)
   text = re.sub(r'\\thanks\{[^}]+\}', '', text)
   text = re.sub(r'\\AND\s+', ', ', text)
   ```

### Priority 3: Image Integration

4. **Add images to chapters** (epub_builder.py:230-266)
   ```python
   def _build_chapter_html(self, main_section, subsections):
       # ... existing code ...

       # Find figures for this chapter
       chapter_figures = [f for f in self.latex_doc.figures
                         if f.source_section == main_section.title]

       for figure in chapter_figures:
           html += f'''
           <figure id="fig{figure.number}">
               <img src="images/{figure.image_name}" alt="{figure.caption}"/>
               <figcaption>Figure {figure.number}: {figure.caption}</figcaption>
           </figure>
           '''
   ```

---

## Testing Plan

1. **Unit Tests**:
   - `test_remove_latex_commands()` - verify `\begin`, `\end`, `\thanks` removed
   - `test_extract_input_content()` - verify `\input` files are read
   - `test_section_content_extraction()` - verify paragraph extraction
   - `test_image_references()` - verify `<img>` tags generated

2. **Integration Test**:
   - Re-process 1706.03762 ("Attention Is All You Need")
   - Verify abstract is clean (no `\beginabstract`)
   - Verify Introduction has full text (not just title)
   - Verify images appear in chapters

3. **Manual Validation**:
   - Open EPUB in Calibre
   - Check readability (no LaTeX commands visible)
   - Check completeness (full paragraphs, not just titles)
   - Check images display correctly

---

## Workaround (Current State)

For now, the EPUB pipeline demonstrates:
- ✅ ArXiv fetching works
- ✅ LaTeX parsing identifies structure
- ✅ Image optimization works (1404×1872, grayscale, CLAHE)
- ✅ EPUB packaging works (valid ZIP structure)
- ✅ CSS integration works
- ❌ Content extraction incomplete
- ❌ LaTeX commands not cleaned
- ❌ Images not displayed

**Status**: Pipeline is 70% complete. Core architecture works, but content processing needs refinement.
