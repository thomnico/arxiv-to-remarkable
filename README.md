# ArXiv to reMarkable

Convert scientific papers from ArXiv (and other sources) to EPUB format optimized for reMarkable e-ink tablets.

## Features

- **EPUB Output**: Reflowable format with adjustable font size
- **ArXiv Integration**: Direct download from ArXiv URLs (LaTeX source preferred)
- **OCR Support**: Groq Vision API for ultra-fast OCR (0.5s/page)
- **Image Optimization**: Resize to 1404×1872px for reMarkable 1
- **OpenDyslexic Font**: Embedded dyslexia-friendly typography
- **reMarkable Sync**: Direct upload via rmapi

## Installation

### From Source

```bash
# Clone repository
git clone https://github.com/thomnico/arxiv-to-remarkable.git
cd arxiv-to-remarkable

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Quick Start

```bash
# Set up environment variables
cp .env.template .env
# Edit .env and add your GROQ_API_KEY

# Convert an ArXiv paper
arxiv2rm convert https://arxiv.org/abs/2301.12345

# Convert a local PDF
arxiv2rm convert paper.pdf --output custom.epub

# Batch convert
arxiv2rm batch papers.txt --parallel 3

# Configure settings
arxiv2rm config --show
arxiv2rm config --set ocr-engine groq
```

## Project Status

🚧 **Phase 1: MVP (In Progress)**

See [GITHUB_ISSUES_SUMMARY.md](GITHUB_ISSUES_SUMMARY.md) for detailed roadmap.

### Completed
- ✅ Issue #1: Initialize Python Project

### In Progress
- ⏳ Issue #2: Environment Configuration
- ⏳ Issue #3: CLI Framework Setup

### Planned
- Issue #4-14: ArXiv integration, PDF processing, EPUB generation, reMarkable upload

## Requirements

- Python 3.9+
- reMarkable 1 or 2 device
- Groq API key (for OCR)
- rmapi (for device upload)

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov

# Format code
black src/ tests/
isort src/ tests/

# Lint
flake8 src/ tests/

# Type check
mypy src/

# Run all pre-commit hooks
pre-commit run --all-files
```

## Architecture

```
ArXiv/PDF → LaTeX/OCR → Text + Images → EPUB → reMarkable
```

See [docs/GROQ_OCR_INTEGRATION.md](docs/GROQ_OCR_INTEGRATION.md) for OCR details.

## Documentation

- [PRD.md](PRD.md) - Product Requirements Document
- [TASKS.md](TASKS.md) - Detailed task breakdown
- [GITHUB_ISSUES_SUMMARY.md](GITHUB_ISSUES_SUMMARY.md) - Issue roadmap
- [docs/GROQ_OCR_INTEGRATION.md](docs/GROQ_OCR_INTEGRATION.md) - Groq OCR guide

## Contributing

See [GitHub Issues](https://github.com/thomnico/arxiv-to-remarkable/issues) for planned features and bugs.

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Groq Vision OCR implementation based on [ghost-in-the-mail](https://github.com/inkan/ghost-in-the-mail)
- OpenDyslexic font by Abbie Gonzalez (OFL license)
- reMarkable community tools: [rmapi](https://github.com/juruen/rmapi)
