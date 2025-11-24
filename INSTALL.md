# Installation Guide - ArXiv to reMarkable

Complete installation guide for production use.

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/thomnico/arxiv-to-remarkable.git
cd arxiv-to-remarkable

# 2. Install Python package
pip install -e ".[ocr]"

# 3. (Optional) Install local DeepSeek OCR for offline processing
./scripts/install_deepseek_ocr.sh

# 4. Configure API keys
cp .env.template .env
# Edit .env and add your GROQ_API_KEY
```

## System Requirements

- **Python**: 3.9+ (tested on 3.9, 3.10, 3.11, 3.12, 3.14)
- **Operating System**: macOS, Linux, Windows
- **Optional**: Rust toolchain for local DeepSeek OCR compilation

## Installation Steps

### 1. Python Environment Setup

#### Option A: Using venv (Recommended)

```bash
# Create virtual environment
python3 -m venv .venv

# Activate (macOS/Linux)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate
```

#### Option B: Using conda

```bash
conda create -n arxiv2rm python=3.11
conda activate arxiv2rm
```

### 2. Install ArXiv2RM Package

#### Development Installation (Editable)

```bash
# Install with all dependencies including OCR tools
pip install -e ".[ocr]"

# Or minimal installation without OCR
pip install -e .
```

#### Production Installation (from PyPI - when published)

```bash
pip install arxiv2rm[ocr]
```

### 3. Install Local OCR Engine (Optional but Recommended)

The local DeepSeek OCR engine provides **free, offline OCR** for printed documents.

```bash
./scripts/install_deepseek_ocr.sh
```

**What this does:**
- Clones [deepseek-ocr.rs](https://github.com/TimmyOVO/deepseek-ocr.rs)
- Builds with Metal GPU support (Apple Silicon) or CPU-only
- Installs to `~/.local/bin/deepseek-ocr`
- Takes 5-10 minutes on first build

**Requirements:**
- Rust toolchain (script will install if missing)
- ~500MB disk space for build cache

**Testing installation:**

```bash
deepseek-ocr --version  # If ~/.local/bin is in PATH
# or
~/.local/bin/deepseek-ocr --version
```

### 4. Configure API Keys

```bash
# Copy environment template
cp .env.template .env

# Edit .env file
nano .env  # or your preferred editor
```

Add your API keys:

```bash
# Groq Vision API (for handwritten text OCR)
GROQ_API_KEY=gsk_your_key_here

# reMarkable Cloud (optional - for cloud sync)
REMARKABLE_TOKEN=your_token_here
```

**Get Groq API Key:**
1. Visit https://console.groq.com
2. Sign up (free tier available)
3. Create API key
4. Copy to `.env`

## Verify Installation

```bash
# Check Python package
python -c "import arxiv2rm; print('✓ Package installed')"

# Test handwriting detection CLI
python -m arxiv2rm.cli_detect --help

# Test detection on examples
python -m arxiv2rm.cli_detect detect exemples/handwritten/*.png

# Expected output:
# Newsletter - page 1.png: HANDWRITTEN (100%) → GROQ
# Newsletter - page 2.png: HANDWRITTEN (100%) → GROQ
# Newsletter - page 3.png: HANDWRITTEN (100%) → GROQ
```

## Directory Structure (Production)

```
$HOME/
├── .local/
│   └── bin/
│       └── deepseek-ocr          # Local OCR binary
├── .cache/
│   └── arxiv2rm/
│       └── deepseek-ocr-build/   # Build artifacts (can be deleted after install)
└── .config/
    └── arxiv2rm/
        └── config.yaml            # User configuration (auto-created)

Project/
├── .env                           # API keys (gitignored)
├── src/arxiv2rm/                  # Python package
├── scripts/                       # Installation scripts
└── exemples/                      # Test samples
```

## CLI Commands

Once installed, use these commands:

### Handwriting Detection

```bash
# Detect handwriting in images
python -m arxiv2rm.cli_detect detect <image1> [image2 ...]

# Batch detection
python -m arxiv2rm.cli_detect detect exemples/handwritten/*.png

# With verbose output
python -m arxiv2rm.cli_detect detect --verbose image.png

# JSON output
python -m arxiv2rm.cli_detect detect --json image.png
```

### Cost Estimation

```bash
# Estimate OCR costs for batch
python -m arxiv2rm.cli_detect estimate exemples/handwritten/*.png

# Output:
# ============================================================
#   OCR COST ESTIMATE
# ============================================================
# Total images:     3
# Routing decision:
#   → Groq API:     3 images (100%)
#   → Local OCR:    0 images (0%)
# Cost breakdown:
#   Groq pages:     3 × $0.04 = $0.12
#   Total cost:     $0.12
```

### Detailed Analysis

```bash
# Analyze single image with detailed scores
python -m arxiv2rm.cli_detect analyze exemples/handwritten/"Newsletter - page 1.png"
```

## Troubleshooting

### Python Package Not Found

```bash
# Ensure you're in the correct virtual environment
which python  # Should show .venv/bin/python

# Reinstall package
pip uninstall arxiv2rm
pip install -e ".[ocr]"
```

### CLI Command Not Found

```bash
# Use module syntax instead
python -m arxiv2rm.cli_detect detect image.png

# Or check if scripts are installed
pip show arxiv2rm | grep Location
```

### Local DeepSeek OCR Not Found

```bash
# Check if binary exists
ls -la ~/.local/bin/deepseek-ocr

# Add to PATH if needed
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Or use full path
~/.local/bin/deepseek-ocr --version
```

### Missing Dependencies

```bash
# Install OpenCV system dependencies (Linux)
sudo apt-get install libopencv-dev python3-opencv

# Install Tesseract (optional, for fallback OCR)
# macOS
brew install tesseract

# Linux
sudo apt-get install tesseract-ocr

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

### Rust Compilation Issues (Local OCR)

```bash
# Update Rust
rustup update

# Clean and rebuild
cd ~/.cache/arxiv2rm/deepseek-ocr-build/deepseek-ocr.rs
cargo clean
cargo build --release --features metal  # macOS Apple Silicon
# or
cargo build --release  # Other systems
```

## Uninstall

```bash
# Remove Python package
pip uninstall arxiv2rm

# Remove local OCR binary
rm ~/.local/bin/deepseek-ocr

# Remove build cache
rm -rf ~/.cache/arxiv2rm/deepseek-ocr-build
```

## Next Steps

After installation:

1. **Read the documentation**: [docs/automated_ocr_routing.md](docs/automated_ocr_routing.md)
2. **Test on samples**: Run detection on `exemples/handwritten/`
3. **Configure settings**: Edit `~/.config/arxiv2rm/config.yaml`
4. **Process your first paper**: See [README.md](README.md) for usage examples

## Support

- **Issues**: https://github.com/thomnico/arxiv-to-remarkable/issues
- **Documentation**: [docs/](docs/)
- **Examples**: [exemples/](exemples/)
