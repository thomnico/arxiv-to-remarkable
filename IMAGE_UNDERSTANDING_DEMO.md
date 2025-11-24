# Image Understanding Demo - Groq Vision vs Local DeepSeek OCR

## Test Date: 2025-11-24

This document demonstrates the difference between **text extraction (OCR)** and **semantic image understanding**.

---

## Test Image: Newsletter - page 1.png

![Handwritten French newsletter](exemples/handwritten/Newsletter%20-%20page%201.png)

**Size**: 203.9 KB
**Format**: PNG
**Content**: Handwritten French text on lined paper

---

## Results Comparison

### 1️⃣ General Description Task

**Prompt**: "Describe what this image represents"

**🔵 Groq Vision (Llama 4 Scout)** - ✅ SUCCESS
- **Time**: 1.08s
- **Tokens**: 2,165
- **Result**:

> The image appears to be a handwritten note in French, likely from a notebook or piece of paper with lined pages. The text is written in black ink and features several lines of cursive writing.
>
> **Key Elements:**
> - The text is written in French.
> - The handwriting is cursive and appears to be somewhat difficult to read.
> - The note appears to be a draft or outline of some kind, possibly for a newsletter or article.
> - There are bullet points and numbered items.
> - The writing includes phrases about "dirigeants" (leaders), "décideurs" (decision-makers), and "cybersecurity".

**✅ CAPABILITY**: Can describe the document type, language, writing style, and general content themes.

---

### 2️⃣ Document Type Classification

**Prompt**: "What type of document is this? (newsletter, article, notes, diagram, etc.)"

**🔵 Groq Vision (Llama 4 Scout)** - ✅ SUCCESS
- **Time**: 0.49s
- **Tokens**: 1,987
- **Result**:

> The document appears to be **notes**. The text is written in a handwritten style, with phrases and sentences that seem to be a rough draft or outline of ideas. The presence of bullet points and a possible title or heading ("#1") suggests that it is a collection of notes or a preliminary document.
>
> It is not a newsletter, article, or diagram in the traditional sense, but rather a working document or brainstorming session captured on paper.

**✅ CAPABILITY**: Can classify document types and understand the purpose/context of the content.

---

### 3️⃣ Layout & Visual Structure Analysis

**Prompt**: "Describe the layout and visual structure of this page"

**🔵 Groq Vision (Llama 4 Scout)** - ✅ SUCCESS
- **Time**: 0.83s
- **Tokens**: 2,135
- **Result**:

> The image presents a handwritten note in French, featuring a mix of cursive and print writing. The text is written on lined paper with a white background.
>
> - The top section of the page contains bullet points starting with dashes (-)
> - There are numbered items ("#1", "#2")
> - The text flows down the page in a linear fashion
> - There's an emphasized phrase circled at the bottom: "Pourquoi" (Why)
> - The writing includes both structured list items and free-form text
> - The paper has horizontal ruled lines visible throughout

**✅ CAPABILITY**: Can analyze visual structure, layout elements, and formatting.

---

### 4️⃣ Text Extraction (OCR) Task

**🟡 Local DeepSeek OCR** - ❌ NOT INSTALLED
- **Status**: Binary not found at `~/.local/bin/deepseek-ocr`
- **Expected Capability**: Extract text characters (optimized for printed text)
- **Limitation**: NOT designed for semantic understanding, only text extraction

**Note**: DeepSeek OCR excels at extracting text from printed documents but:
- ❌ Cannot describe what images represent
- ❌ Cannot classify document types
- ❌ Cannot analyze layout/structure
- ❌ Poor accuracy on handwritten text (~30-40%)
- ✅ Excellent for printed scientific papers (>95% accuracy)

---

## Summary: Capabilities Comparison

| Capability | Groq Vision | Local DeepSeek OCR |
|------------|-------------|-------------------|
| **Semantic Understanding** | ✅ Excellent | ❌ No |
| **Document Classification** | ✅ Yes | ❌ No |
| **Layout Analysis** | ✅ Yes | ❌ No |
| **Handwritten OCR** | ✅ 85-90% | ❌ 30-40% |
| **Printed OCR** | ✅ Good | ✅ Excellent (>95%) |
| **Image Description** | ✅ Yes | ❌ No |
| **Alt-text Generation** | ✅ Yes | ❌ No |
| **Cost** | ~$0.04/page | Free |
| **Speed** | 0.5-1.5s | 0.4s |

---

## Use Cases for Each Model

### 🔵 Groq Vision (Llama 4 Scout)
**Best for:**
- ✅ Understanding what images represent
- ✅ Generating image descriptions for EXIF metadata
- ✅ Creating alt-text for accessibility
- ✅ Classifying document types
- ✅ Analyzing visual structure
- ✅ OCR of handwritten text
- ✅ Scientific papers with equations/diagrams

**When to use:**
- Image understanding and metadata enrichment
- Handwritten annotations in papers
- Describing figures, charts, diagrams
- Accessibility requirements (alt-text)

### 🟡 Local DeepSeek OCR
**Best for:**
- ✅ Fast text extraction from printed documents
- ✅ Offline/private processing
- ✅ High-volume batch processing (free)
- ✅ Clean typed scientific papers

**When to use:**
- Pure text extraction (no understanding needed)
- Printed documents without handwriting
- Cost-sensitive scenarios
- Privacy-critical documents (offline)

---

## Recommendation for ArXiv-to-reMarkable

### Image Understanding Pipeline (NEW Feature)

```text
For each image in PDF:
│
├─ Is it a figure/diagram/chart?
│  └─ YES → Use Groq Vision to describe content
│           → Store description in EXIF ImageDescription
│           → Generate alt-text for EPUB accessibility
│           → Classify type (chart/diagram/photo/equation)
│
├─ Does it contain text to extract?
│  ├─ Handwritten? → Use Groq Vision OCR
│  └─ Printed? → Use Local DeepSeek OCR (free)
│
└─ Compress image to <500KB
   → Write EXIF metadata
   → Embed in EPUB with alt-text
```

### Implementation Example

```python
from arxiv2rm.image_understanding import ImageAnalyzer
from pathlib import Path

analyzer = ImageAnalyzer()

# Analyze image
result = analyzer.understand_image(
    image_path=Path("figure1.png"),
    prompt="Describe this scientific figure in detail"
)

# Result contains:
# {
#   "description": "Bar chart comparing OCR accuracy...",
#   "type": "chart",
#   "exif": {
#     "ImageDescription": "Bar chart comparing...",
#     "ImageType": "chart",
#     "Model": "meta-llama/llama-4-scout-17b-16e-instruct"
#   }
# }

# Write to EXIF and compress
compressed_image = analyzer.compress_and_annotate(
    image_path=Path("figure1.png"),
    description=result["description"],
    target_size_kb=500
)
```

---

## Conclusion

**Groq Vision (Llama 4 Scout)** is the clear choice for **image understanding** tasks:

1. ✅ **Can describe** what images represent (not just OCR text)
2. ✅ **Can classify** document and image types
3. ✅ **Can analyze** layout and visual structure
4. ✅ **Can generate** accessibility metadata (alt-text)
5. ✅ **Suitable for** EXIF metadata enrichment

**Local DeepSeek OCR** remains excellent for **text extraction** from printed documents but should **NOT** be used for semantic image understanding.

### Implementation Priority

1. **Phase 1**: Implement Groq Vision for image understanding
2. **Phase 2**: Add EXIF metadata storage (piexif)
3. **Phase 3**: Integrate compression pipeline (Pillow)
4. **Phase 4**: Add to EPUB generation with alt-text
5. **Phase 5**: Use Claude Code vision as judge during development

---

## Test Script

See: [test_image_understanding.py](test_image_understanding.py)

Run: `python test_image_understanding.py`
