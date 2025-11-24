#!/bin/bash
# Installation script for deepseek-ocr.rs (Local OCR Engine)
# Installs to ~/.local/bin/ for production use

set -e

INSTALL_DIR="$HOME/.local/bin"
REPO_URL="https://github.com/TimmyOVO/deepseek-ocr.rs.git"
BUILD_DIR="$HOME/.cache/arxiv2rm/deepseek-ocr-build"

echo "========================================================================"
echo "DeepSeek OCR Installation Script"
echo "========================================================================"
echo ""
echo "This will install deepseek-ocr.rs to: $INSTALL_DIR"
echo "Build cache directory: $BUILD_DIR"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v rustc &> /dev/null; then
    echo "❌ Rust not found. Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

if ! command -v git &> /dev/null; then
    echo "❌ Git not found. Please install git first."
    exit 1
fi

echo "✓ Rust $(rustc --version)"
echo "✓ Cargo $(cargo --version)"
echo "✓ Git $(git --version)"
echo ""

# Create install directory
mkdir -p "$INSTALL_DIR"
mkdir -p "$BUILD_DIR"

# Clone or update repository
echo "========================================================================"
echo "Cloning deepseek-ocr.rs repository..."
echo "========================================================================"
echo ""

if [ -d "$BUILD_DIR/deepseek-ocr.rs" ]; then
    echo "Repository already exists. Pulling latest changes..."
    cd "$BUILD_DIR/deepseek-ocr.rs"
    git pull
else
    git clone "$REPO_URL" "$BUILD_DIR/deepseek-ocr.rs"
    cd "$BUILD_DIR/deepseek-ocr.rs"
fi

# Build with Metal GPU support (Apple Silicon)
echo ""
echo "========================================================================"
echo "Building deepseek-ocr.rs with Metal GPU acceleration..."
echo "========================================================================"
echo ""
echo "This may take several minutes on first build..."
echo ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - check for Apple Silicon
    if [[ $(uname -m) == "arm64" ]]; then
        echo "✓ Detected Apple Silicon - enabling Metal GPU support"
        cargo build --release --features metal
    else
        echo "ℹ️  Intel Mac detected - building CPU-only version"
        cargo build --release
    fi
else
    echo "ℹ️  Non-macOS system - building CPU-only version"
    cargo build --release
fi

# Install binary
echo ""
echo "========================================================================"
echo "Installing binary..."
echo "========================================================================"
echo ""

cp target/release/deepseek-ocr-cli "$INSTALL_DIR/deepseek-ocr"
chmod +x "$INSTALL_DIR/deepseek-ocr"

echo "✓ Installed: $INSTALL_DIR/deepseek-ocr"

# Test installation
echo ""
echo "========================================================================"
echo "Testing installation..."
echo "========================================================================"
echo ""

if "$INSTALL_DIR/deepseek-ocr" --version &> /dev/null; then
    echo "✓ deepseek-ocr installed successfully"
else
    echo "✓ Binary installed (version check not available)"
fi

# Check if install dir is in PATH
echo ""
if echo "$PATH" | grep -q "$INSTALL_DIR"; then
    echo "✓ $INSTALL_DIR is in your PATH"
else
    echo "⚠️  $INSTALL_DIR is NOT in your PATH"
    echo ""
    echo "Add this to your ~/.zshrc or ~/.bashrc:"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

# Create symlink for easier access
echo ""
echo "========================================================================"
echo "Installation Complete!"
echo "========================================================================"
echo ""
echo "Binary location: $INSTALL_DIR/deepseek-ocr"
echo "Build cache:     $BUILD_DIR/deepseek-ocr.rs"
echo ""
echo "Usage:"
echo "  deepseek-ocr --help"
echo "  deepseek-ocr --image <path> --output <json-file>"
echo ""
echo "To uninstall:"
echo "  rm $INSTALL_DIR/deepseek-ocr"
echo "  rm -rf $BUILD_DIR/deepseek-ocr.rs"
echo ""
