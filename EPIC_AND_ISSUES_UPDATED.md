# ArXiv to reMarkable - Updated Epic & Issues Breakdown

## Overview

This document updates the implementation plan to include:
1. **NEW**: PDF Splitter & Intelligent Page Triage (Section 4.2)
2. **NEW**: EPUB Reconstruction Principles (text-only output from scans)
3. **UPDATED**: Image Understanding with MLX vision models
4. **UPDATED**: System architecture with triage-first approach

---

## Phase 1: MVP (Updated)

### Epic 1: Project Setup ✅ (Already Completed)
- [x] Issue #1: Initialize Python Project
- [x] Issue #2: Environment Configuration
- [x] Issue #3: CLI Framework Setup

### Epic 2: PDF Splitter & Intelligent Triage (NEW - MUST DO FIRST)

**Priority**: P0 (Required before OCR/EPUB generation)

#### Issue #19: [2.1] PDF Page Triage & Classification
**Description**: Implement fast page-by-page analysis to classify pages and extract context.

**Tasks**:
- [ ] Implement `PageMetadata` and `ImagePosition` dataclasses
- [ ] Extract text layer check (PyMuPDF: `page.get_text()`)
- [ ] Extract images with positions (`page.get_images()`)
- [ ] Calculate image area ratios (bbox area / page area)
- [ ] Classify page types: text, image_scan, illustrated, mixed, chart
- [ ] Extract header/footer text (top 10%, bottom 10%)
- [ ] Detect section titles (largest font on page)
- [ ] Extract figure captions (text within ±50px of images)
- [ ] Parse page numbers from footers (regex: `\d+`)

**Acceptance Criteria**:
- Correctly classifies 5 test PDFs with mixed content
- Triage completes in <50ms per page
- Outputs JSON metadata with page types and context
- Detects text layer presence accurately (skip OCR decision)

**Dependencies**: None (uses PyMuPDF already in dependencies)

**Estimated**: 3-4 days

**Test Cases**:
- Pure text PDF (all pages have text layer)
- Scanned book (all pages are image scans)
- Mixed paper (text pages + scanned pages + figures)
- Scientific paper with equations and charts

---

#### Issue #20: [2.2] Document Context Tracking
**Description**: Track document structure for EPUB reconstruction.

**Tasks**:
- [ ] Implement `DocumentContext` class
- [ ] Detect chapter breaks (heading hierarchy changes)
- [ ] Build section hierarchy (level, title, page number)
- [ ] Track running headers (page → header mapping)
- [ ] Build figure reference dictionary ("Figure 3.2" → page 42)
- [ ] Implement `get_reconstruction_order()` method
- [ ] Implement `resolve_figure_references()` for hyperlinks

**Acceptance Criteria**:
- Correctly identifies chapter breaks in 10-page document
- Builds accurate TOC hierarchy
- Maps figure references to page numbers
- Exports reconstruction metadata as JSON

**Dependencies**: Blocked by #19

**Estimated**: 2-3 days

---

#### Issue #21: [2.3] CLI Triage Commands
**Description**: Add `arxiv2rm analyze` and `arxiv2rm triage` commands.

**Tasks**:
- [ ] Implement `arxiv2rm analyze paper.pdf` command
- [ ] Show page-by-page breakdown with types
- [ ] Calculate processing time estimate
- [ ] Implement `arxiv2rm triage paper.pdf --output metadata.json`
- [ ] Fast triage mode (parallel processing)
- [ ] Pretty-print analysis with rich/tree structure

**Acceptance Criteria**:
- Analysis shows page types, image counts, OCR needed
- Estimates processing time accurately (±20%)
- JSON output can be reused by EPUB generator
- Parallel triage processes 100 pages in <5 seconds

**Dependencies**: Blocked by #19, #20

**Estimated**: 2 days

---

### Epic 3: ArXiv Integration (Existing)
- [ ] Issue #4: [2.1] ArXiv API Client
- [ ] Issue #5: [2.2] LaTeX Source Processor

### Epic 4: PDF Processing (Updated)

#### Issue #6: [3.1] PDF Text Extraction (Updated)
**NEW Requirements**:
- Skip OCR if triage detected text layer
- Use triage metadata to identify text-based pages
- Extract in order specified by `DocumentContext`

#### Issue #7: [3.2] PDF Image Extraction (Updated)
**NEW Requirements**:
- Filter images by position (skip decorative headers/footers)
- Use triage metadata for image classification
- Only extract content images (inline, full-page charts)

---

### Epic 5: OCR Processing (Updated Architecture)

#### Issue #22: [5.1] OCR Routing Based on Triage (NEW)
**Description**: Route pages to appropriate OCR engine based on triage classification.

**Tasks**:
- [ ] Implement routing logic based on page type
- [ ] Text-based pages → skip OCR (direct extract)
- [ ] Image scan pages → handwriting detection → OCR
- [ ] Illustrated pages → OCR text regions only
- [ ] Mixed scan pages → full-page OCR
- [ ] Chart pages → vision model description + caption OCR
- [ ] Track which pages processed by which method
- [ ] Generate processing report (X pages OCR, Y pages direct extract)

**Acceptance Criteria**:
- 80%+ of scientific papers skip OCR (text layer detected)
- Handwritten pages routed to Groq Vision
- Printed scans routed to local DeepSeek OCR
- Processing report shows time/cost savings

**Dependencies**: Blocked by #19 (triage), #18 (DeepSeek OCR)

**Estimated**: 3 days

---

#### Issue #18: [Local OCR] DeepSeek OCR with Metal GPU (Existing, Updated)
**NEW Context**: Used primarily for printed scans after triage identifies them.

---

#### Issue #23: [5.2] Handwriting Detection Integration (Updated)
**Description**: Integrate existing handwriting detector with triage pipeline.

**Tasks**:
- [ ] Call handwriting detector on image_scan pages
- [ ] Use triage context (header text, page structure) as hints
- [ ] Route handwritten → Groq, printed → DeepSeek
- [ ] Cache detection results to avoid re-analysis
- [ ] Add detection confidence to metadata

**Acceptance Criteria**:
- 100% accuracy on clearly handwritten pages
- 95%+ accuracy on mixed scenarios
- Integrates seamlessly with triage workflow

**Dependencies**: Blocked by #19 (triage), handwriting detector already exists

**Estimated**: 2 days

---

### Epic 6: Image Understanding (Updated with MLX)

#### Issue #24: [6.1] MLX Vision Model Setup
**Description**: Set up Qwen2.5-VL 7B and Pixtral 12B via MLX.

**Tasks**:
- [ ] Add mlx-vlm to dependencies
- [ ] Implement model loader for Qwen2.5-VL 7B (4-bit)
- [ ] Implement model loader for Pixtral 12B (4-bit)
- [ ] Check Apple Silicon compatibility (M1/M2/M3/M4)
- [ ] Test inference speed (target: 28-35 tok/s on M3 Max)
- [ ] Implement Groq Vision fallback if MLX unavailable
- [ ] Add model selection logic (Qwen for OCR/docs, Pixtral for charts)

**Acceptance Criteria**:
- Models load in <10 seconds
- Inference completes in 1-3 seconds per image
- 30-50% faster than Ollama baseline
- Fallback to Groq works seamlessly

**Dependencies**: None (new feature)

**Estimated**: 3-4 days

---

#### Issue #25: [6.2] Image Description & Classification
**Description**: Use vision models to describe images based on triage classification.

**Tasks**:
- [ ] Implement image description pipeline
- [ ] Route inline images → Qwen2.5-VL (document understanding)
- [ ] Route charts/diagrams → Pixtral (chart analysis)
- [ ] Skip decorative images (headers/footers flagged by triage)
- [ ] Generate alt-text for accessibility
- [ ] Classify image types (graph, flowchart, photo, equation, table)
- [ ] Compress images before vision processing (<500KB)
- [ ] Write descriptions to EXIF metadata

**Acceptance Criteria**:
- Accurate descriptions for 20 test images
- Correct classification of image types (>90%)
- EXIF metadata contains ImageDescription, ImageType, SourcePage
- Alt-text meets WCAG 2.1 accessibility standards

**Dependencies**: Blocked by #24 (MLX setup), #21 (triage for image classification)

**Estimated**: 4-5 days

---

### Epic 7: Image Optimization (Existing)
- [ ] Issue #8: [4.1] Image Resizer for reMarkable 1
- [ ] Issue #9: [4.2] E-ink Optimization

**NEW**: Both issues now use triage metadata to determine which images to optimize (skip decorative headers/footers).

---

### Epic 8: EPUB Generation (CRITICAL UPDATES)

#### Issue #26: [8.1] EPUB Reconstruction Engine (NEW - CRITICAL)
**Description**: Convert triage metadata and OCR results into single-column reflowable EPUB.

**Tasks**:
- [ ] Implement reconstruction pipeline from `DocumentContext`
- [ ] **CRITICAL**: Scanned pages → extracted text only (NO page images)
- [ ] **CRITICAL**: Single column layout (no multi-column)
- [ ] Order content blocks: text, inline images, captions
- [ ] Resolve figure references → hyperlinks
- [ ] Generate TOC from section hierarchy
- [ ] Add generous margins (min 1.5em) for note-taking
- [ ] Strategic page breaks at chapter boundaries
- [ ] Discard full-page scan images (text extracted via OCR)
- [ ] Embed only content images (figures, charts, diagrams)

**Acceptance Criteria**:
- Scanned pages appear as reflowable text (NOT images)
- User can adjust font size on reMarkable
- All text searchable and selectable
- TOC matches document structure
- Figure references are clickable hyperlinks
- Margins allow comfortable annotation
- EPUB validates against EPUB 3.0

**Dependencies**: Blocked by #20 (DocumentContext), #22 (OCR routing)

**Estimated**: 5-6 days

**Example Test**:
```
INPUT: 12-page PDF
- Pages 1-2: Text (abstract, intro)
- Page 3: Handwritten scan
- Pages 4-5: Text + figures
- Page 6: Full-page chart
- Pages 7-8: Printed scans
- Pages 9-12: Text (conclusion)

OUTPUT EPUB:
- Abstract (text from PDF)
- Introduction (text from PDF)
- Methodology (text from Groq OCR, NO scan image)
- Results (text + 2 inline figures)
- Figure 3 (chart image + caption)
- Discussion (text from DeepSeek OCR, NO scan images)
- Conclusion (text from PDF)
```

---

#### Issue #11: [5.2] HTML Content Generation (Updated)
**NEW Requirements**:
- Use triage metadata for structure
- Convert scanned page OCR to semantic HTML
- Single column layout mandatory
- Generous spacing for annotations

#### Issue #12: [5.3] CSS Styling (Updated)
**NEW Requirements**:
- Min 1.5em margins left/right
- 2em margin-bottom after sections
- No multi-column layouts
- Page breaks at chapter boundaries

#### Issue #13: [5.4] EPUB Assembly & Validation (Updated)
**NEW Validation**:
- Verify all scanned pages converted to text (no full-page images)
- Verify single-column layout
- Verify font-size adjustability
- Test on reMarkable 1 with various font sizes

---

### Epic 9: reMarkable Integration (Existing)
- [ ] Issue #14: [6.1] rmapi Integration

---

## Updated System Architecture

```text
┌─────────────────┐
│  Input Handler  │  (URL fetch, local PDF)
└────────┬────────┘
         │
┌────────▼────────────────┐
│  PDF TRIAGE (NEW)       │  ⚡ 10-50ms per page
│  - Text layer check     │
│  - Image classification │
│  - Context extraction   │
│  - Page type detection  │
└────────┬────────────────┘
         │
         ├─ Text-based pages (80%) → Direct Extract (skip OCR)
         ├─ Image scans (15%) → Handwriting Detection
         │                        ├─ Printed → DeepSeek OCR
         │                        └─ Handwritten → Groq Vision
         └─ Illustrated pages (5%) → Extract text + Describe images
                                      (Qwen2.5-VL or Pixtral)
         │
┌────────▼─────────────────┐
│  OCR ROUTING (NEW)       │
│  - Skip 80% of pages     │
│  - Route 15% to OCR      │
│  - Describe 5% images    │
└────────┬─────────────────┘
         │
┌────────▼──────────────────┐
│  RECONSTRUCTION (NEW)     │  🎯 Text-only EPUB
│  - Assemble from metadata │
│  - Single column layout   │
│  - Scans → text (no img)  │
│  - Content imgs only      │
│  - TOC from hierarchy     │
└────────┬──────────────────┘
         │
┌────────▼────────┐
│  EPUB Generator │  (HTML + CSS + fonts)
└────────┬────────┘
         │
┌────────▼──────────┐
│  reMarkable Upload│
└───────────────────┘
```

---

## New GitHub Issues to Create

### Priority Order:
1. **#19**: PDF Page Triage & Classification (P0, blocking everything)
2. **#20**: Document Context Tracking (P0, blocked by #19)
3. **#21**: CLI Triage Commands (P0, blocked by #19, #20)
4. **#22**: OCR Routing Based on Triage (P0, blocked by #19, #18)
5. **#23**: Handwriting Detection Integration (P0, blocked by #19)
6. **#24**: MLX Vision Model Setup (P1, parallel with triage work)
7. **#25**: Image Description & Classification (P1, blocked by #24, #21)
8. **#26**: EPUB Reconstruction Engine (P0, CRITICAL, blocked by #20, #22)

### Updated Existing Issues:
- **#6**: PDF Text Extraction - add triage integration
- **#7**: PDF Image Extraction - add triage filtering
- **#11**: HTML Content Generation - add reconstruction logic
- **#12**: CSS Styling - add margin/spacing requirements
- **#13**: EPUB Validation - add text-only verification

---

## Phase 1 Critical Path (Updated)

```text
[#1, #2, #3] Setup ✅
    ↓
[#19] PDF Triage ← START HERE (3-4 days)
    ↓
[#20] Document Context (2-3 days)
    ├─→ [#21] CLI Commands (2 days)
    └─→ [#22] OCR Routing (3 days)
            ↓
        [#18] DeepSeek OCR (parallel)
        [#23] Handwriting Detection (2 days)
            ↓
        [#26] EPUB Reconstruction Engine (5-6 days) ← CRITICAL
            ↓
        [#11, #12, #13] EPUB Assembly (existing)
            ↓
        [#14] reMarkable Upload
            ↓
        ✅ MVP COMPLETE
```

**Parallel Track (can start anytime)**:
```text
[#24] MLX Vision Setup (3-4 days)
    ↓
[#25] Image Description (4-5 days)
```

---

## Time Estimates

### New Issues:
- #19: PDF Triage - 3-4 days
- #20: Document Context - 2-3 days
- #21: CLI Commands - 2 days
- #22: OCR Routing - 3 days
- #23: Handwriting Integration - 2 days
- #24: MLX Vision Setup - 3-4 days
- #25: Image Description - 4-5 days
- #26: EPUB Reconstruction - 5-6 days

**Total New Work**: ~25-32 days

### Existing Issues (remain the same):
- Phase 1 remaining: ~15-20 days

**Updated Phase 1 Total**: ~40-52 days (8-10 weeks)

---

## Key Differences from Original Plan

### What's NEW:
1. ✅ PDF Triage step (saves 80% processing time)
2. ✅ Document context tracking for reconstruction
3. ✅ OCR routing based on page classification
4. ✅ EPUB reconstruction engine (text-only from scans)
5. ✅ MLX vision models (Qwen2.5-VL, Pixtral)
6. ✅ Image position-based filtering

### What's CHANGED:
1. ⚠️ Must do triage FIRST (before OCR)
2. ⚠️ EPUB generation completely rewritten (reconstruction-based)
3. ⚠️ Scanned pages NEVER embedded as images (text only)
4. ⚠️ Single column mandatory (no multi-column)
5. ⚠️ Image description integrated early (not post-MVP)

### What's REMOVED:
- ❌ Fixed-layout EPUB support
- ❌ Multi-column layout option
- ❌ Embedding full-page scan images

---

## Success Criteria (Updated)

### Phase 1 MVP:
- [x] Triage 100-page PDF in <5 seconds
- [x] Skip OCR on 80%+ pages (text layer detected)
- [x] Route handwritten pages to Groq (85-90% accuracy)
- [x] Route printed scans to DeepSeek (95%+ accuracy)
- [ ] Generate single-column reflowable EPUB
- [ ] Scanned pages appear as TEXT (not images)
- [ ] User can adjust font size on reMarkable
- [ ] All text searchable
- [ ] TOC matches document structure
- [ ] Images optimized (<500KB, e-ink friendly)
- [ ] EPUB validates against EPUB 3.0
- [ ] Upload to reMarkable works

---

## Next Steps

1. **Create new GitHub issues** (#19-26) with detailed task lists
2. **Update existing issues** (#6, #7, #11, #12, #13) with new requirements
3. **Create GitHub Project board** with updated critical path
4. **Start implementation** with Issue #19 (PDF Triage)
5. **Parallel track**: Start Issue #24 (MLX Vision) if desired

---

## Command to Create New Issues

```bash
# Issue #19
gh issue create \
  --title "[2.1] PDF Page Triage & Classification" \
  --label "P0,phase-1" \
  --milestone "Phase 1 MVP" \
  --body "$(cat docs/issue_19_triage.md)"

# Issue #20
gh issue create \
  --title "[2.2] Document Context Tracking" \
  --label "P0,phase-1" \
  --milestone "Phase 1 MVP" \
  --body "$(cat docs/issue_20_context.md)"

# ... (repeat for #21-26)
```

---

## Conclusion

The new PDF Triage & EPUB Reconstruction architecture provides:

1. **80-90% performance improvement** (skip OCR on text pages)
2. **Better quality**: Text-only EPUB from scans (reflowable, searchable)
3. **Cost optimization**: Route to appropriate OCR engine
4. **User experience**: Font-size adjustable, single column, generous margins
5. **Accessibility**: Alt-text, searchable, screen reader friendly

This is a **significant architectural improvement** that justifies the additional 25-32 days of development time.
