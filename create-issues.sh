#!/usr/bin/env bash
# Script to create GitHub issues for ArXiv to reMarkable project
# Usage: ./create-issues.sh

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Creating GitHub issues for ArXiv to reMarkable...${NC}"

# Store issue numbers for dependency tracking (bash 4+ feature)
# For older bash, we'll use sequential variables
ISSUE_1_1=""
ISSUE_1_2=""
ISSUE_1_3=""
ISSUE_2_1=""
ISSUE_2_2=""
ISSUE_3_1=""
ISSUE_3_2=""
ISSUE_4_1=""
ISSUE_4_2=""
ISSUE_5_1=""
ISSUE_5_2=""
ISSUE_5_3=""
ISSUE_5_4=""
ISSUE_6_1=""
ISSUE_6_2=""
ISSUE_7_1=""
ISSUE_7_2=""
ISSUE_7_3=""
ISSUE_8_1=""
ISSUE_8_2=""
ISSUE_9_1=""
ISSUE_10_1=""
ISSUE_10_2=""
ISSUE_10_3=""
ISSUE_11_1=""
ISSUE_11_2=""
ISSUE_12_1=""
ISSUE_12_3=""

# Epic 1: Project Setup & Configuration
echo -e "\n${GREEN}Epic 1: Project Setup & Configuration${NC}"

ISSUE_1_1=$(gh issue create \
  --title "Task 1.1: Initialize Python Project" \
  --label "P0,phase-1,setup" \
  --body "## Description
Set up Python 3.9+ project structure with modern tooling.

## Tasks
- [ ] Create project directory structure (src/, tests/, docs/)
- [ ] Set up pyproject.toml with dependencies
- [ ] Configure virtual environment (venv or poetry)
- [ ] Add pytest configuration
- [ ] Set up pre-commit hooks (black, isort, flake8)
- [ ] Create .editorconfig

## Acceptance Criteria
- Python 3.9+ virtual environment works
- pytest runs (even with 0 tests)
- Pre-commit hooks pass
- Project structure follows best practices

## Dependencies
None

## Estimated Time
2-3 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_1_1}: Task 1.1"

ISSUE_1_2=$(gh issue create \
  --title "Task 1.2: Environment Configuration" \
  --label "P0,phase-1,setup" \
  --body "## Description
Implement configuration system using .env and YAML files.

## Tasks
- [ ] Create .env.template with required variables (GROQ_API_KEY, etc.)
- [ ] Implement config loader using python-dotenv
- [ ] Create YAML config parser (~/.arxiv2rm/config.yaml)
- [ ] Add config validation (check required fields)
- [ ] Add config defaults

## Acceptance Criteria
- .env.template documented
- Config loads from .env and YAML
- Missing required fields raise clear errors
- Config accessible via Python API

## Dependencies
- Blocked by #${ISSUE_1_1}

## Estimated Time
1-2 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_1_2}: Task 1.2"

ISSUE_1_3=$(gh issue create \
  --title "Task 1.3: CLI Framework Setup" \
  --label "P0,phase-1,cli" \
  --body "## Description
Implement Click-based CLI with core commands.

## Tasks
- [ ] Set up Click framework
- [ ] Implement \`arxiv2rm convert\` command (stub)
- [ ] Implement \`arxiv2rm batch\` command (stub)
- [ ] Implement \`arxiv2rm config\` command (show/set)
- [ ] Add progress bars (tqdm or rich)
- [ ] Configure logging (console + file)

## Acceptance Criteria
- CLI commands work with --help
- Progress bars display correctly
- Logs written to ~/.arxiv2rm/logs/
- Version command works

## Dependencies
- Blocked by #${ISSUE_1_1} #${ISSUE_1_2}

## Estimated Time
2-3 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_1_3}: Task 1.3"

# Epic 2: ArXiv Integration
echo -e "\n${GREEN}Epic 2: ArXiv Integration${NC}"

ISSUE_2_1=$(gh issue create \
  --title "Task 2.1: ArXiv API Client" \
  --label "P0,phase-1,arxiv" \
  --body "## Description
Implement ArXiv API client to fetch papers and LaTeX sources.

## Tasks
- [ ] Parse ArXiv URLs (extract paper ID: YYMM.NNNNN)
- [ ] Implement ArXiv API client (fetch metadata)
- [ ] Download LaTeX source (.tar.gz from https://arxiv.org/e-print/)
- [ ] Download PDF fallback
- [ ] Implement caching (~/.arxiv2rm/cache/)
- [ ] Handle rate limits

## Acceptance Criteria
- Parse valid ArXiv URLs
- Download LaTeX source successfully
- Fallback to PDF if LaTeX unavailable
- Cache prevents re-downloads

## Dependencies
- Blocked by #${ISSUE_1_1} #${ISSUE_1_2}

## Estimated Time
3-4 days

## Test Papers
- https://arxiv.org/abs/2301.00001 (example)" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_2_1}: Task 2.1"

ISSUE_2_2=$(gh issue create \
  --title "Task 2.2: LaTeX Source Processor" \
  --label "P0,phase-1,arxiv,latex" \
  --body "## Description
Extract and process LaTeX sources from ArXiv.

## Tasks
- [ ] Extract .tar.gz archives
- [ ] Find main .tex file (common: main.tex, paper.tex, ms.tex)
- [ ] Parse .tex file structure (sections, paragraphs)
- [ ] Extract figure references (\includegraphics)
- [ ] Extract images (PDF, PNG, EPS)
- [ ] Handle multi-file LaTeX projects (\input, \include)
- [ ] Strip LaTeX commands, keep text content

## Acceptance Criteria
- Extract text with structure preserved
- Find and extract all figures
- Handle complex multi-file papers

## Dependencies
- Blocked by #${ISSUE_2_1}

## Estimated Time
4-5 days

## Libraries to Consider
- TexSoup (LaTeX parser)
- PyLaTeX" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_2_2}: Task 2.2"

# Epic 3: PDF Processing
echo -e "\n${GREEN}Epic 3: PDF Processing${NC}"

ISSUE_3_1=$(gh issue create \
  --title "Task 3.1: PDF Text Extraction" \
  --label "P0,phase-1,pdf" \
  --body "## Description
Extract text and structure from PDF files using PyMuPDF.

## Tasks
- [ ] Implement PyMuPDF-based text extraction
- [ ] Detect if PDF has text layer
- [ ] Extract document structure (identify headings)
- [ ] Extract metadata (title, authors, date)
- [ ] Handle multi-column layouts

## Acceptance Criteria
- Detect text layer presence (OCR needed: yes/no)
- Extract text in reading order
- Preserve paragraph breaks

## Dependencies
- Blocked by #${ISSUE_1_1}

## Estimated Time
2-3 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_3_1}: Task 3.1"

ISSUE_3_2=$(gh issue create \
  --title "Task 3.2: PDF Image Extraction" \
  --label "P0,phase-1,pdf,images" \
  --body "## Description
Extract embedded images and figures from PDF.

## Tasks
- [ ] Extract embedded images from PDF
- [ ] Detect figures (bounding boxes)
- [ ] Save images with metadata (page number, position)
- [ ] Support common formats (JPEG, PNG)

## Acceptance Criteria
- Extract all images from PDF
- Images saved with descriptive names (page_N_fig_M.png)
- Metadata preserved

## Dependencies
- Blocked by #${ISSUE_3_1}

## Estimated Time
2 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_3_2}: Task 3.2"

# Epic 4: Image Optimization
echo -e "\n${GREEN}Epic 4: Image Optimization${NC}"

ISSUE_4_1=$(gh issue create \
  --title "Task 4.1: Image Resizer for reMarkable 1" \
  --label "P0,phase-1,images" \
  --body "## Description
Resize images to optimal resolution for reMarkable 1.

## Tasks
- [ ] Implement resize to 1404×1872px (portrait)
- [ ] Maintain aspect ratio (letterbox with white borders)
- [ ] Support landscape images (rotate if needed)
- [ ] Support batch processing

## Acceptance Criteria
- Images fit 1404×1872 without distortion
- Aspect ratio preserved
- White letterbox for smaller images

## Dependencies
- Blocked by #${ISSUE_1_1}

## Estimated Time
2 days

## reMarkable 1 Specs
- Screen: 1872×1404 pixels (portrait)
- Resolution: 226 DPI" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_4_1}: Task 4.1"

ISSUE_4_2=$(gh issue create \
  --title "Task 4.2: E-ink Optimization" \
  --label "P0,phase-1,images" \
  --body "## Description
Optimize images for e-ink display quality and file size.

## Tasks
- [ ] Implement contrast enhancement (CLAHE algorithm)
- [ ] Add optional dithering (Floyd-Steinberg)
- [ ] Optimize JPEG quality (configurable 1-100, default 85)
- [ ] Add EXIF metadata (source, page number)
- [ ] Target <500KB per image
- [ ] Convert to grayscale (e-ink is monochrome)

## Acceptance Criteria
- Images display well on e-ink
- File sizes <500KB
- EXIF metadata present

## Dependencies
- Blocked by #${ISSUE_4_1}

## Estimated Time
2-3 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_4_2}: Task 4.2"

# Epic 5: EPUB Generation
echo -e "\n${GREEN}Epic 5: EPUB Generation${NC}"

ISSUE_5_1=$(gh issue create \
  --title "Task 5.1: EPUB Structure Builder" \
  --label "P0,phase-1,epub" \
  --body "## Description
Create EPUB 3.0 package structure.

## Tasks
- [ ] Set up ebooklib for EPUB generation
- [ ] Generate metadata (title, author, language, UUID)
- [ ] Create navigation (Table of Contents from headings)
- [ ] Implement chapter/section structure
- [ ] Add cover page (optional)

## Acceptance Criteria
- Valid EPUB 3.0 structure created
- Metadata correctly populated
- TOC navigation works

## Dependencies
- Blocked by #${ISSUE_1_1}

## Estimated Time
3 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_5_1}: Task 5.1"

ISSUE_5_2=$(gh issue create \
  --title "Task 5.2: HTML Content Generation" \
  --label "P0,phase-1,epub,html" \
  --body "## Description
Convert extracted text to semantic HTML for EPUB.

## Tasks
- [ ] Convert text to semantic HTML (h1, h2, h3, p)
- [ ] Handle paragraphs and line breaks
- [ ] Embed images with <figure> tags
- [ ] Add image captions (alt text)
- [ ] Generate image references
- [ ] Escape HTML special characters

## Acceptance Criteria
- Valid XHTML5 output
- Semantic structure preserved
- Images embedded correctly

## Dependencies
- Blocked by #${ISSUE_5_1}

## Estimated Time
3-4 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_5_2}: Task 5.2"

ISSUE_5_3=$(gh issue create \
  --title "Task 5.3: CSS Styling" \
  --label "P0,phase-1,epub,css" \
  --body "## Description
Create CSS stylesheet for EPUB with embedded OpenDyslexic font.

## Tasks
- [ ] Download OpenDyslexic font files (OTF/TTF)
- [ ] Embed fonts in EPUB
- [ ] Create base CSS stylesheet
- [ ] Define typography (font-family: OpenDyslexic, line-height: 1.5)
- [ ] Set margins (2em top/bottom, 1.5em left/right)
- [ ] Add chapter breaks (page-break-after: always)
- [ ] Style headings (h1, h2, h3)
- [ ] Style figures (max-width: 100%)

## Acceptance Criteria
- OpenDyslexic font renders on reMarkable
- CSS validates
- Readable typography

## Dependencies
- Blocked by #${ISSUE_5_2}

## Estimated Time
2-3 days

## Font License
- OpenDyslexic: OFL (can embed)" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_5_3}: Task 5.3"

ISSUE_5_4=$(gh issue create \
  --title "Task 5.4: EPUB Assembly & Validation" \
  --label "P0,phase-1,epub" \
  --body "## Description
Package EPUB and validate against EPUB 3.0 standard.

## Tasks
- [ ] Package HTML + CSS + images + fonts into .epub
- [ ] Validate with epubcheck
- [ ] Test with EPUB readers (Calibre, Apple Books)
- [ ] Verify file size (<50MB target)
- [ ] Test on reMarkable 1

## Acceptance Criteria
- EPUB passes epubcheck validation
- Opens in standard EPUB readers
- Displays correctly on reMarkable 1
- Font size adjustable on device

## Dependencies
- Blocked by #${ISSUE_5_3}

## Estimated Time
3 days

## Tools
- epubcheck: https://www.w3.org/publishing/epubcheck/" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_5_4}: Task 5.4"

# Epic 6: reMarkable Integration
echo -e "\n${GREEN}Epic 6: reMarkable Integration${NC}"

ISSUE_6_1=$(gh issue create \
  --title "Task 6.1: rmapi Integration" \
  --label "P0,phase-1,remarkable" \
  --body "## Description
Integrate with rmapi for reMarkable device upload.

## Tasks
- [ ] Detect rmapi installation (check PATH)
- [ ] Install rmapi if missing (provide instructions)
- [ ] Implement rmapi wrapper (subprocess calls)
- [ ] Upload EPUB to device (\`rmapi put\`)
- [ ] Create folders (\`rmapi mkdir\`)
- [ ] Handle upload errors
- [ ] Verify file appears on device

## Acceptance Criteria
- EPUB uploads successfully
- Folder creation works
- Clear error messages if rmapi missing

## Dependencies
- Blocked by #${ISSUE_5_4}

## Estimated Time
2-3 days

## rmapi
- https://github.com/juruen/rmapi" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_6_1}: Task 6.1"

ISSUE_6_2=$(gh issue create \
  --title "Task 6.2: reMarkable Cloud API (Alternative)" \
  --label "P1,phase-2,remarkable" \
  --body "## Description
Alternative upload method using reMarkable Cloud API.

## Tasks
- [ ] Research Cloud API documentation
- [ ] Implement OAuth authentication flow
- [ ] Upload EPUB via Cloud API
- [ ] Handle token refresh
- [ ] Document setup instructions

## Acceptance Criteria
- Cloud upload works as alternative to rmapi
- Token management robust

## Dependencies
- Blocked by #${ISSUE_6_1}

## Estimated Time
5 days

## Priority
P1 (optional alternative method)" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_6_2}: Task 6.2"

# Epic 7: Groq Vision OCR
echo -e "\n${GREEN}Epic 7: Groq Vision OCR${NC}"

ISSUE_7_1=$(gh issue create \
  --title "Task 7.1: Groq API Client" \
  --label "P0,phase-2,ocr" \
  --body "## Description
Implement Groq Vision API client for OCR using Llama 4.

## Tasks
- [ ] Implement Groq Vision API client (based on ghost-in-the-mail reference)
- [ ] Base64 image encoding (<4MB check)
- [ ] Send OCR request (model: meta-llama/llama-4-scout-17b-16e-instruct)
- [ ] Parse JSON response (extract text)
- [ ] Handle rate limits (429 errors)
- [ ] Handle API errors (401, 500)
- [ ] Add timeout (60s)

## Acceptance Criteria
- OCR extracts text from images
- Speed: ~0.5s per page
- Accuracy: >95%

## Dependencies
- Blocked by #${ISSUE_1_2}, #${ISSUE_4_1}

## Estimated Time
3-4 days

## Reference
See: docs/GROQ_OCR_INTEGRATION.md" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_7_1}: Task 7.1"

ISSUE_7_2=$(gh issue create \
  --title "Task 7.2: OCR Pipeline" \
  --label "P0,phase-2,ocr" \
  --body "## Description
Build complete OCR pipeline with caching.

## Tasks
- [ ] Detect when OCR needed (check PDF text layer)
- [ ] Convert PDF pages to images (150 DPI)
- [ ] Batch OCR processing (sequential)
- [ ] Show progress bar (estimate 0.5s per page)
- [ ] Cache OCR results (SHA256 hash of image)
- [ ] Handle mathematical formulas (preserve as images)

## Acceptance Criteria
- OCR pipeline processes scanned PDFs
- Cache prevents reprocessing
- Math formulas handled correctly

## Dependencies
- Blocked by #${ISSUE_3_1}, #${ISSUE_7_1}

## Estimated Time
4-5 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_7_2}: Task 7.2"

ISSUE_7_3=$(gh issue create \
  --title "Task 7.3: Tesseract Fallback" \
  --label "P1,phase-2,ocr" \
  --body "## Description
Add Tesseract OCR as offline fallback.

## Tasks
- [ ] Detect Tesseract installation
- [ ] Implement Tesseract OCR wrapper (pytesseract)
- [ ] Automatic fallback on Groq API failure
- [ ] Support multiple languages (eng, fra, deu)
- [ ] Compare accuracy with Groq

## Acceptance Criteria
- Tesseract works offline
- Fallback automatic on Groq failure

## Dependencies
- Blocked by #${ISSUE_7_2}

## Estimated Time
2-3 days

## Priority
P1" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_7_3}: Task 7.3"

# Epic 8: Batch Processing
echo -e "\n${GREEN}Epic 8: Batch Processing${NC}"

ISSUE_8_1=$(gh issue create \
  --title "Task 8.1: Batch Input Handler" \
  --label "P1,phase-2,batch" \
  --body "## Description
Handle batch input files with URLs and paths.

## Tasks
- [ ] Parse text file (one URL/path per line)
- [ ] Support comments (# prefix)
- [ ] Validate each input (check format)
- [ ] Create job queue

## Acceptance Criteria
- Parse batch file correctly
- Skip invalid entries with warnings

## Dependencies
- Blocked by #${ISSUE_1_3}

## Estimated Time
1 day" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_8_1}: Task 8.1"

ISSUE_8_2=$(gh issue create \
  --title "Task 8.2: Batch Processor" \
  --label "P1,phase-2,batch" \
  --body "## Description
Process multiple papers in batch mode.

## Tasks
- [ ] Sequential processing (one at a time)
- [ ] Progress tracking (N/M completed)
- [ ] Error handling (skip failures, continue)
- [ ] Generate summary report (successes/warnings/failures)
- [ ] Save failed items to retry.txt

## Acceptance Criteria
- Batch processes multiple papers
- Failures don't stop batch
- Summary report clear

## Dependencies
- Blocked by #${ISSUE_2_1}, #${ISSUE_3_1}, #${ISSUE_5_4}, #${ISSUE_6_1}, #${ISSUE_8_1}

## Estimated Time
3-4 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_8_2}: Task 8.2"

# Epic 9: Configuration & Customization
echo -e "\n${GREEN}Epic 9: Configuration${NC}"

ISSUE_9_1=$(gh issue create \
  --title "Task 9.1: User Configuration System" \
  --label "P1,phase-2,config" \
  --body "## Description
Comprehensive user configuration system.

## Tasks
- [ ] Config file reader (~/.arxiv2rm/config.yaml)
- [ ] CLI flags for overrides (--image-quality, etc.)
- [ ] Image quality settings (1-100)
- [ ] CSS customization support
- [ ] Config validation

## Acceptance Criteria
- User can customize all settings
- CLI flags override config file
- Validation prevents invalid configs

## Dependencies
- Blocked by #${ISSUE_1_2}, #${ISSUE_1_3}

## Estimated Time
2-3 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_9_1}: Task 9.1"

# Epic 10: Testing & Quality
echo -e "\n${GREEN}Epic 10: Testing${NC}"

ISSUE_10.1=$(gh issue create \
  --title "Task 10.1: Unit Tests" \
  --label "P0,phase-3,testing" \
  --body "## Description
Write comprehensive unit tests.

## Tasks
- [ ] Test ArXiv client (mock API responses)
- [ ] Test PDF extraction
- [ ] Test image optimization
- [ ] Test EPUB generation
- [ ] Target >80% code coverage

## Acceptance Criteria
- All unit tests pass
- Coverage >80%

## Estimated Time
1 week" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_10.1}: Task 10.1"

ISSUE_10.2=$(gh issue create \
  --title "Task 10.2: Integration Tests" \
  --label "P0,phase-3,testing" \
  --body "## Description
End-to-end integration tests.

## Tasks
- [ ] Test full pipeline (ArXiv URL → EPUB)
- [ ] Test batch processing
- [ ] Test error scenarios
- [ ] Test on actual reMarkable 1 device

## Acceptance Criteria
- E2E tests pass
- Tested on real device

## Dependencies
- Blocked by #${ISSUE_10.1}

## Estimated Time
3-4 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_10.2}: Task 10.2"

ISSUE_10.3=$(gh issue create \
  --title "Task 10.3: EPUB Quality Tests" \
  --label "P0,phase-3,testing" \
  --body "## Description
Quality assurance for EPUB output.

## Tasks
- [ ] Validate 50 sample ArXiv papers
- [ ] Test on reMarkable 1 device
- [ ] Verify font size adjustment works
- [ ] Check image display quality
- [ ] Measure conversion times
- [ ] Collect user feedback

## Acceptance Criteria
- 90%+ success rate on 50 papers
- All EPUBs display correctly

## Dependencies
- Blocked by #${ISSUE_10.2}

## Estimated Time
1 week" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_10.3}: Task 10.3"

# Epic 11: Documentation
echo -e "\n${GREEN}Epic 11: Documentation${NC}"

ISSUE_11.1=$(gh issue create \
  --title "Task 11.1: User Documentation" \
  --label "P0,phase-3,docs" \
  --body "## Description
Write user-facing documentation.

## Tasks
- [ ] Write comprehensive README.md
- [ ] Create QUICKSTART.md guide
- [ ] Document all CLI commands
- [ ] Document configuration options
- [ ] Add troubleshooting section
- [ ] Add FAQ

## Acceptance Criteria
- Documentation covers all features
- Examples for common use cases

## Estimated Time
4-5 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_11.1}: Task 11.1"

ISSUE_11.2=$(gh issue create \
  --title "Task 11.2: Developer Documentation" \
  --label "P1,phase-3,docs" \
  --body "## Description
Developer and contributor documentation.

## Tasks
- [ ] Document architecture (ARCHITECTURE.md)
- [ ] Add comprehensive docstrings
- [ ] Create CONTRIBUTING.md
- [ ] Document testing procedures
- [ ] Add code examples

## Dependencies
- Blocked by #${ISSUE_11.1}

## Estimated Time
3 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_11.2}: Task 11.2"

# Epic 12: Distribution
echo -e "\n${GREEN}Epic 12: Distribution${NC}"

ISSUE_12.1=$(gh issue create \
  --title "Task 12.1: PyPI Package" \
  --label "P1,phase-3,distribution" \
  --body "## Description
Create PyPI package for easy installation.

## Tasks
- [ ] Configure pyproject.toml for packaging
- [ ] Add entry points for CLI
- [ ] Test installation (\`pip install arxiv2rm\`)
- [ ] Publish to TestPyPI
- [ ] Publish to PyPI

## Acceptance Criteria
- \`pip install arxiv2rm\` works
- CLI accessible globally

## Dependencies
- Blocked by #${ISSUE_10.1}, #${ISSUE_11.1}

## Estimated Time
2-3 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_12.1}: Task 12.1"

ISSUE_12.3=$(gh issue create \
  --title "Task 12.3: CI/CD Pipeline" \
  --label "P1,phase-3,cicd" \
  --body "## Description
Set up CI/CD with GitHub Actions.

## Tasks
- [ ] Create test workflow (run on push)
- [ ] Add lint checks (black, isort, flake8)
- [ ] Add coverage reporting
- [ ] Create release workflow (publish to PyPI)
- [ ] Add badge to README

## Acceptance Criteria
- Tests run automatically on PR
- Releases publish to PyPI automatically

## Dependencies
- Blocked by #${ISSUE_10.1}, #${ISSUE_12.1}

## Estimated Time
2 days" | grep -oP '#\K\d+')

echo "Created issue #${ISSUE_12.3}: Task 12.3"

echo -e "\n${GREEN}✓ Created all GitHub issues!${NC}"
echo -e "\n${BLUE}Summary:${NC}"
echo "- Phase 1 (MVP): Issues #${ISSUE_1_1} - #${ISSUE_6_1}"
echo "- Phase 2 (Advanced): Issues #${ISSUE_6_2}, #${ISSUE_7_1} - #${ISSUE_9_1}"
echo "- Phase 3 (Polish): Issues #${ISSUE_10.1} - #${ISSUE_12.3}"
echo ""
echo "View issues: gh issue list --milestone 'Phase 1: MVP'"
echo "Project board: gh project list"
