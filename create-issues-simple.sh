#!/usr/bin/env bash
# Simplified script to create GitHub issues for ArXiv to reMarkable project
# Usage: ./create-issues-simple.sh

set -e

echo "Creating GitHub issues for ArXiv to reMarkable..."
echo ""

# Create labels first
echo "Creating labels..."
gh label create "P0" --description "Must-have for MVP" --color "d73a4a" 2>/dev/null || echo "Label P0 exists"
gh label create "P1" --description "Important for Phase 2" --color "fbca04" 2>/dev/null || echo "Label P1 exists"
gh label create "P2" --description "Nice-to-have" --color "0e8a16" 2>/dev/null || echo "Label P2 exists"
gh label create "phase-1" --description "Phase 1: MVP" --color "1d76db" 2>/dev/null || echo "Label phase-1 exists"
gh label create "phase-2" --description "Phase 2: Advanced" --color "5319e7" 2>/dev/null || echo "Label phase-2 exists"
gh label create "phase-3" --description "Phase 3: Polish" --color "0052cc" 2>/dev/null || echo "Label phase-3 exists"

echo ""
echo "Creating Phase 1 MVP issues..."
echo ""

# Epic 1: Project Setup
gh issue create --title "[1.1] Initialize Python Project" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Set up Python 3.9+ project structure with modern tooling.

## Tasks
- [ ] Create project directory structure (src/, tests/, docs/)
- [ ] Set up pyproject.toml with dependencies
- [ ] Configure virtual environment
- [ ] Add pytest configuration
- [ ] Set up pre-commit hooks

## Acceptance Criteria
- Python 3.9+ virtual environment works
- pytest runs (even with 0 tests)
- Pre-commit hooks pass

## Dependencies
None

## Estimated: 2-3 days
EOF
)"

gh issue create --title "[1.2] Environment Configuration" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Implement configuration system using .env and YAML files.

## Tasks
- [ ] Create .env.template with required variables (GROQ_API_KEY, etc.)
- [ ] Implement config loader using python-dotenv
- [ ] Create YAML config parser
- [ ] Add config validation

## Acceptance Criteria
- Config loads from .env and YAML
- Missing required fields raise clear errors

## Dependencies
Blocked by: [1.1]

## Estimated: 1-2 days
EOF
)"

gh issue create --title "[1.3] CLI Framework Setup" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Implement Click-based CLI with core commands.

## Tasks
- [ ] Set up Click framework
- [ ] Implement \`arxiv2rm convert\` command (stub)
- [ ] Implement \`arxiv2rm batch\` command (stub)
- [ ] Implement \`arxiv2rm config\` command
- [ ] Add progress bars (tqdm or rich)
- [ ] Configure logging

## Acceptance Criteria
- CLI commands work with --help
- Progress bars display correctly
- Logs written to ~/.arxiv2rm/logs/

## Dependencies
Blocked by: [1.1] [1.2]

## Estimated: 2-3 days
EOF
)"

# Epic 2: ArXiv Integration
gh issue create --title "[2.1] ArXiv API Client" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Implement ArXiv API client to fetch papers and LaTeX sources.

## Tasks
- [ ] Parse ArXiv URLs (extract paper ID: YYMM.NNNNN)
- [ ] Implement ArXiv API client (fetch metadata)
- [ ] Download LaTeX source (.tar.gz)
- [ ] Download PDF fallback
- [ ] Implement caching (~/.arxiv2rm/cache/)

## Acceptance Criteria
- Parse valid ArXiv URLs
- Download LaTeX source successfully
- Fallback to PDF if LaTeX unavailable

## Dependencies
Blocked by: [1.1] [1.2]

## Estimated: 3-4 days

## Test: https://arxiv.org/abs/2301.00001
EOF
)"

gh issue create --title "[2.2] LaTeX Source Processor" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Extract and process LaTeX sources from ArXiv.

## Tasks
- [ ] Extract .tar.gz archives
- [ ] Find main .tex file (main.tex, paper.tex, ms.tex)
- [ ] Parse .tex file structure (sections, paragraphs)
- [ ] Extract figure references (\includegraphics)
- [ ] Extract images (PDF, PNG, EPS)
- [ ] Handle multi-file LaTeX projects

## Acceptance Criteria
- Extract text with structure preserved
- Find and extract all figures
- Handle complex multi-file papers

## Dependencies
Blocked by: [2.1]

## Estimated: 4-5 days

## Libraries: TexSoup, PyLaTeX
EOF
)"

# Epic 3: PDF Processing
gh issue create --title "[3.1] PDF Text Extraction" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Extract text and structure from PDF files using PyMuPDF.

## Tasks
- [ ] Implement PyMuPDF-based text extraction
- [ ] Detect if PDF has text layer
- [ ] Extract document structure (identify headings)
- [ ] Extract metadata (title, authors, date)

## Acceptance Criteria
- Detect text layer presence (OCR needed: yes/no)
- Extract text in reading order
- Preserve paragraph breaks

## Dependencies
Blocked by: [1.1]

## Estimated: 2-3 days
EOF
)"

gh issue create --title "[3.2] PDF Image Extraction" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Extract embedded images and figures from PDF.

## Tasks
- [ ] Extract embedded images from PDF
- [ ] Detect figures (bounding boxes)
- [ ] Save images with metadata (page number, position)
- [ ] Support common formats (JPEG, PNG)

## Acceptance Criteria
- Extract all images from PDF
- Images saved with descriptive names (page_N_fig_M.png)

## Dependencies
Blocked by: [3.1]

## Estimated: 2 days
EOF
)"

# Epic 4: Image Optimization
gh issue create --title "[4.1] Image Resizer for reMarkable 1" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Resize images to optimal resolution for reMarkable 1.

## Tasks
- [ ] Implement resize to 1404×1872px (portrait)
- [ ] Maintain aspect ratio (letterbox with white borders)
- [ ] Support landscape images (rotate if needed)
- [ ] Support batch processing

## Acceptance Criteria
- Images fit 1404×1872 without distortion
- Aspect ratio preserved

## Dependencies
Blocked by: [1.1]

## Estimated: 2 days

## reMarkable 1: 1872×1404 pixels, 226 DPI
EOF
)"

gh issue create --title "[4.2] E-ink Optimization" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Optimize images for e-ink display quality and file size.

## Tasks
- [ ] Implement contrast enhancement (CLAHE algorithm)
- [ ] Add optional dithering (Floyd-Steinberg)
- [ ] Optimize JPEG quality (configurable, default 85)
- [ ] Add EXIF metadata (source, page number)
- [ ] Target <500KB per image
- [ ] Convert to grayscale

## Acceptance Criteria
- Images display well on e-ink
- File sizes <500KB

## Dependencies
Blocked by: [4.1]

## Estimated: 2-3 days
EOF
)"

# Epic 5: EPUB Generation
gh issue create --title "[5.1] EPUB Structure Builder" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Create EPUB 3.0 package structure.

## Tasks
- [ ] Set up ebooklib for EPUB generation
- [ ] Generate metadata (title, author, language, UUID)
- [ ] Create navigation (Table of Contents from headings)
- [ ] Implement chapter/section structure

## Acceptance Criteria
- Valid EPUB 3.0 structure created
- Metadata correctly populated
- TOC navigation works

## Dependencies
Blocked by: [1.1]

## Estimated: 3 days
EOF
)"

gh issue create --title "[5.2] HTML Content Generation" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Convert extracted text to semantic HTML for EPUB.

## Tasks
- [ ] Convert text to semantic HTML (h1, h2, h3, p)
- [ ] Handle paragraphs and line breaks
- [ ] Embed images with <figure> tags
- [ ] Add image captions (alt text)
- [ ] Escape HTML special characters

## Acceptance Criteria
- Valid XHTML5 output
- Semantic structure preserved
- Images embedded correctly

## Dependencies
Blocked by: [5.1]

## Estimated: 3-4 days
EOF
)"

gh issue create --title "[5.3] CSS Styling" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Create CSS stylesheet for EPUB with embedded OpenDyslexic font.

## Tasks
- [ ] Download OpenDyslexic font files (OTF/TTF)
- [ ] Embed fonts in EPUB
- [ ] Create base CSS stylesheet
- [ ] Define typography (font-family: OpenDyslexic, line-height: 1.5)
- [ ] Set margins (2em top/bottom, 1.5em left/right)
- [ ] Style headings and figures

## Acceptance Criteria
- OpenDyslexic font renders on reMarkable
- CSS validates

## Dependencies
Blocked by: [5.2]

## Estimated: 2-3 days

## Font: OpenDyslexic OFL license (can embed)
EOF
)"

gh issue create --title "[5.4] EPUB Assembly & Validation" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
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
Blocked by: [5.3]

## Estimated: 3 days

## Tool: epubcheck
EOF
)"

# Epic 6: reMarkable Integration
gh issue create --title "[6.1] rmapi Integration" --label "P0,phase-1" --body "$(cat <<'EOF'
## Description
Integrate with rmapi for reMarkable device upload.

## Tasks
- [ ] Detect rmapi installation (check PATH)
- [ ] Install rmapi if missing (provide instructions)
- [ ] Implement rmapi wrapper (subprocess calls)
- [ ] Upload EPUB to device (\`rmapi put\`)
- [ ] Create folders (\`rmapi mkdir\`)
- [ ] Handle upload errors

## Acceptance Criteria
- EPUB uploads successfully
- Folder creation works
- Clear error messages if rmapi missing

## Dependencies
Blocked by: [5.4]

## Estimated: 2-3 days

## Tool: https://github.com/juruen/rmapi
EOF
)"

echo ""
echo "✓ Phase 1 MVP issues created!"
echo ""
echo "To view: gh issue list --label phase-1"
echo "To create project board: gh project create --title 'ArXiv to reMarkable MVP'"
