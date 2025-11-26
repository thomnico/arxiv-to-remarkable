# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ArXiv to reMarkable converter - transforms scientific papers (ArXiv, IEEE, PDFs) into **optimized PDF format** for reMarkable e-ink tablets with enhanced readability features (OpenDyslexic font, OCR via Groq Vision API).

**Important**: Output format is **PDF** (not EPUB). See [ADR-002](../docs/ADR-002-pdf-output-format.md) for rationale - EPUB rendering on reMarkable has critical issues (blank pages, missing word spaces).

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install package with dependencies
pip install -e ".[dev]"          # Install with dev tools
pip install -e ".[ocr]"          # Install with OCR capabilities
pip install -e ".[dev,ocr]"      # Install everything

# Install pre-commit hooks
pre-commit install
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov

# Run specific test file
pytest tests/test_config.py

# Run specific test function
pytest tests/test_cli.py::test_convert_command -v
```

### Code Quality
```bash
# Format code (auto-fix)
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/

# Run all pre-commit hooks manually
pre-commit run --all-files
```

### CLI Usage
```bash
# Configure environment
cp .env.template .env
# Edit .env and add GROQ_API_KEY

# Main CLI commands
arxiv2rm convert <url_or_path>              # Convert paper to PDF
arxiv2rm convert paper.pdf -o output.pdf    # Specify output
arxiv2rm convert paper.pdf --font-size 16   # Larger font (12/14/16/18)
arxiv2rm batch papers.txt --parallel 3      # Batch processing
arxiv2rm config --show                      # View configuration
arxiv2rm config --init                      # Create config file
arxiv2rm config --path                      # Show config location

# Handwriting detection CLI
arxiv2rm-detect <image_path>                # Detect handwriting in image

```

## Code Architecture

### Package Structure
- **src/arxiv2rm/**: Main package directory
  - `cli.py`: Click-based CLI interface with `convert`, `batch`, and `config` commands
  - `cli_detect.py`: Handwriting detection CLI entry point
  - `config.py`: Pydantic-based configuration management with YAML and .env support
  - `handwriting_detector.py`: Multi-strategy handwriting detection (edge density, stroke variance, line straightness)
  - `pdf_parser.py`: PDF processing logic

### Configuration System

The project uses a **three-tier configuration approach**:

1. **Default values**: Hardcoded in Pydantic models (src/arxiv2rm/config.py)
2. **YAML config**: User config at `~/.arxiv2rm/config.yaml` (created via `arxiv2rm config --init`)
3. **Environment variables**: Loaded from `.env` file (use `.env.template` as starting point)

Key config sections:
- `TypographyConfig`: Font settings (OpenDyslexic, size 14-16pt)
- `ImageConfig`: reMarkable-optimized dimensions (1404×1872px)
- `OCRConfig`: Groq Vision API or Tesseract, with caching
- `RemarkableConfig`: rmapi integration settings
- `LoggingConfig`: Log levels and file locations

**IMPORTANT**: The `ConfigLoader` class handles:
- Environment variable expansion in YAML (`${VAR_NAME}` syntax)
- Automatic injection of `GROQ_API_KEY` and `REMARKABLE_TOKEN` from environment
- Validation of required keys (raises `ValueError` if Groq API key missing when `ocr.engine=groq`)

### Handwriting Detection Architecture

The `HandwritingDetector` class uses **5 strategies** with weighted scoring:

1. **DeepSeek OCR confidence** (3x weight): Primary signal - low confidence indicates handwriting
2. **Text quality analysis**: Detects fragmentation, gibberish, non-alphanumeric ratio
3. **Edge density**: Measures irregularity using Canny edge detection
4. **Stroke width variance**: Local variance analysis (handwriting = higher variance)
5. **Line straightness**: Horizontal projection profile analysis with scipy peak detection

Returns dict with:
- `is_handwritten`: bool (classification result)
- `confidence`: float 0-1 (aggregate score)
- `reasons`: list of human-readable detection reasons
- `recommendation`: "groq" or "local" (OCR engine to use)
- `scores`: detailed breakdown of all strategy scores

### Logging

- **Rich-based console output**: Uses `rich.console.Console` and `rich.logging.RichHandler`
- **File logging**: Logs written to `~/.arxiv2rm/logs/arxiv2rm.log`
- **Log levels**: Configurable via `--log-level` CLI flag or `config.logging.level`

### CLI Context Management

The Click CLI uses `@click.pass_context` to share configuration across commands:
- Config loaded once in main group command
- Stored in `ctx.obj["config"]`
- Commands merge CLI options with config defaults (CLI options take precedence)

## Code Style and Standards

### Formatting
- **Line length**: 100 characters (Black + isort configured)
- **Target Python**: 3.9-3.12 compatibility
- **Import sorting**: isort with Black profile

### Type Hints
- **mypy configured** but not strict (`disallow_untyped_defs=false`)
- Type checking enabled for untyped defs
- Missing imports ignored for: `arxiv`, `TexSoup`, `piexif`

### Pre-commit Hooks
Enforces:
- Trailing whitespace removal
- End-of-file fixes
- YAML/JSON/TOML validation
- Large file prevention (>500KB)
- Black formatting
- isort import sorting
- Flake8 linting (E203, W503 ignored for Black compatibility)

## Key Dependencies

### Core Libraries

- **CLI**: `click` (commands), `rich` (output), `tqdm` (progress)
- **Config**: `pydantic` (validation), `python-dotenv` (.env), `pyyaml` (config files)
- **PDF Input**: `PyMuPDF` (fitz) - primary text extraction (preserves word spacing)
- **PDF Output**: `reportlab` - PDF generation with font embedding
- **HTML Processing**: `beautifulsoup4`, `lxml`
- **Images**: `Pillow`, `piexif`
- **HTTP**: `requests`, `httpx`
- **ArXiv**: `arxiv` (official Python package)
- **LaTeX**: `TexSoup`

### OCR Dependencies (optional extra)
- `pytesseract`: Tesseract OCR wrapper
- `groq`: Groq Vision API client (Llama 4 Scout, Llama 3.2 Vision)
- `opencv-python`: Image processing for handwriting detection
- `scipy`: Signal processing for line detection

## OCR Integration

### Groq Vision API
- **Preferred models**: Llama 4 Scout (`meta-llama/llama-4-scout-17b-16e-instruct`), Llama 3.2 Vision
- **API endpoint**: `https://api.groq.com/openai/v1/models`
- **Image limits**: 20MB (URL), 4MB (base64), 33 megapixels max
- **Performance**: ~0.5s/page, significantly outperforms Tesseract on handwriting (408 vs 168 chars)

### OCR Routing Strategy
1. Run local OCR first (fast, free)
2. Analyze confidence + image features with `HandwritingDetector`
3. If handwriting detected (confidence < threshold), re-run with Groq Vision
4. Cache OCR results to `~/.arxiv2rm/cache/ocr/` (configurable)

## Environment Variables

Required:
- `GROQ_API_KEY`: Groq Vision API key (must start with `gsk_`)

Optional:
- `REMARKABLE_TOKEN`: reMarkable Cloud API token
- `CONFIG_FILE`: Override config path (default: `~/.arxiv2rm/config.yaml`)

## Testing

### Test Structure
- `tests/test_config.py`: Configuration loading and validation tests
- `tests/test_cli.py`: CLI command tests

### Coverage Configuration
- **Source**: `src/` directory
- **Omit**: `tests/*`, `*/test_*.py`
- **Excluded lines**: pragma, `__repr__`, `__main__`, TYPE_CHECKING, abstractmethod
- **Reports**: terminal, HTML (`htmlcov/`), XML

## Known Limitations

- **Font size fixed at conversion**: PDF font size cannot be changed on device after conversion
- **reMarkable upload**: Integration pending (rmapi or cloud API)

## Documentation References

- [PRD.md](../PRD.md): Product Requirements Document
- [TASKS.md](../TASKS.md): Detailed task breakdown
- [GITHUB_ISSUES_SUMMARY.md](../GITHUB_ISSUES_SUMMARY.md): Issue roadmap
- [docs/ADR-002-pdf-output-format.md](../docs/ADR-002-pdf-output-format.md): PDF output decision
- [docs/ADR-001-formula-rendering.md](../docs/ADR-001-formula-rendering.md): Formula extraction as images
- [docs/GROQ_OCR_INTEGRATION.md](../docs/GROQ_OCR_INTEGRATION.md): Groq OCR integration guide
- [docs/automated_ocr_routing.md](../docs/automated_ocr_routing.md): Handwriting detection architecture

## reMarkable Device Specs

- **reMarkable 1**: 10.3" E Ink display, 1872×1404 pixels (portrait), 226 DPI
- **Page size for PDF**: 1404×1872px (width × height in portrait mode)
- **Optimization targets**: High contrast for e-ink, JPEG quality 85, OpenDyslexic font embedded
