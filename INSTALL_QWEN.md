# Installing Qwen2.5-VL for Local Image Understanding

## Quick Start (macOS)

```bash
# 1. Install Ollama
brew install ollama

# 2. Pull Qwen2.5-VL 7B model (~4.7GB download)
ollama pull qwen2.5-vl:7b

# 3. Verify installation
ollama run qwen2.5-vl:7b "Hello, describe yourself"

# 4. Install Python bindings
pip install ollama
```

---

## System Requirements

### Minimum
- **RAM**: 8GB
- **Storage**: 5GB free space
- **CPU**: Apple Silicon M1+ (or x86_64 with AVX2)
- **OS**: macOS 11+ (Big Sur or later)

### Recommended
- **RAM**: 16GB+
- **Storage**: 10GB+ free space
- **CPU**: Apple Silicon M2+
- **OS**: macOS 13+ (Ventura or later)

### Optimal
- **RAM**: 32GB+
- **CPU**: Apple Silicon M3 Pro/Max/Ultra
- **GPU**: Integrated Apple GPU (automatic)

---

## Performance Estimates

| Hardware | Speed per Image | Batch (100 images) |
|----------|-----------------|-------------------|
| M1 (8GB) | 3-5s | ~7 min |
| M2 (16GB) | 2-4s | ~5 min |
| M3 (24GB+) | 1-3s | ~3 min |
| M3 Max/Ultra | 1-2s | ~2 min |

---

## Installation Steps (Detailed)

### Step 1: Install Ollama

**Method A: Homebrew (Recommended)**
```bash
brew install ollama
```

**Method B: Direct Download**
1. Visit https://ollama.com
2. Download macOS installer
3. Run installer package
4. Follow installation wizard

### Step 2: Start Ollama Service

```bash
# Ollama runs as a background service
# Check if running:
ollama list

# If not running, start it:
ollama serve
```

### Step 3: Download Qwen2.5-VL Model

```bash
# This downloads ~4.7GB
ollama pull qwen2.5-vl:7b

# Progress will be shown:
# pulling manifest
# pulling 4f1f3db... 100% |████████████████| (4.7 GB/4.7 GB, 50 MB/s)
# verifying sha256 digest
# writing manifest
# success
```

### Step 4: Test Installation

```bash
# Interactive mode
ollama run qwen2.5-vl:7b

# Test with a prompt
>>> Describe yourself
I am Qwen2.5-VL, a vision-language model developed by Alibaba Cloud...

# Exit with Ctrl+D or /bye
```

### Step 5: Install Python Bindings

```bash
# In your project virtual environment
source .venv/bin/activate

# Install ollama Python library
pip install ollama

# Verify
python -c "import ollama; print('✓ Ollama installed')"
```

---

## Testing Image Understanding

### Test 1: Simple Description

```python
import ollama
from pathlib import Path

# Load image
image_path = Path("exemples/handwritten/Newsletter - page 1.png")

# Generate description
response = ollama.chat(
    model='qwen2.5-vl:7b',
    messages=[{
        'role': 'user',
        'content': 'Describe this image in detail',
        'images': [str(image_path)]
    }]
)

print(response['message']['content'])
```

### Test 2: Document Classification

```python
response = ollama.chat(
    model='qwen2.5-vl:7b',
    messages=[{
        'role': 'user',
        'content': 'What type of document is this? (newsletter, article, notes, diagram, chart)',
        'images': [str(image_path)]
    }]
)

print(f"Document type: {response['message']['content']}")
```

### Test 3: Layout Analysis

```python
response = ollama.chat(
    model='qwen2.5-vl:7b',
    messages=[{
        'role': 'user',
        'content': 'Describe the visual layout and structure of this page',
        'images': [str(image_path)]
    }]
)

print(f"Layout: {response['message']['content']}")
```

---

## Integration with ArXiv-to-reMarkable

### Create Image Understanding Module

```python
# src/arxiv2rm/image_understanding.py
import ollama
from pathlib import Path
from typing import Dict, Optional
import time

class ImageUnderstanding:
    """Local image understanding using Qwen2.5-VL."""

    def __init__(self, model: str = "qwen2.5-vl:7b"):
        self.model = model
        self._check_model_available()

    def _check_model_available(self) -> bool:
        """Check if Qwen2.5-VL is installed."""
        try:
            models = ollama.list()
            return any(self.model in m['name'] for m in models['models'])
        except Exception as e:
            raise RuntimeError(
                f"Qwen2.5-VL not found. Install with: ollama pull {self.model}"
            )

    def describe_image(self, image_path: Path,
                      prompt: str = "Describe this image in detail") -> Dict:
        """Describe what an image represents."""
        start_time = time.time()

        response = ollama.chat(
            model=self.model,
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [str(image_path)]
            }]
        )

        elapsed = time.time() - start_time

        return {
            "description": response['message']['content'],
            "model": self.model,
            "time_seconds": round(elapsed, 2)
        }

    def classify_image_type(self, image_path: Path) -> str:
        """Classify image type (chart, diagram, photo, etc.)."""
        result = self.describe_image(
            image_path,
            prompt="What type of image is this? Answer in one word: chart, diagram, photo, equation, table, or other."
        )
        return result['description'].strip().lower()
```

### Usage Example

```python
from arxiv2rm.image_understanding import ImageUnderstanding
from pathlib import Path

# Initialize
analyzer = ImageUnderstanding()

# Analyze image
result = analyzer.describe_image(
    Path("figure1.png"),
    prompt="Describe this scientific figure"
)

print(f"Description: {result['description']}")
print(f"Time: {result['time_seconds']}s")

# Classify type
image_type = analyzer.classify_image_type(Path("figure1.png"))
print(f"Type: {image_type}")
```

---

## Troubleshooting

### Issue: "ollama: command not found"

**Solution**:
```bash
# Add Ollama to PATH
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Or reinstall
brew reinstall ollama
```

### Issue: "Model not found"

**Solution**:
```bash
# Check installed models
ollama list

# Pull model again
ollama pull qwen2.5-vl:7b

# Verify
ollama run qwen2.5-vl:7b "test"
```

### Issue: Slow performance

**Solution**:
```bash
# Check memory usage
ollama ps

# Free up memory
ollama stop qwen2.5-vl:7b

# Restart with explicit memory limit (if needed)
OLLAMA_MAX_LOADED_MODELS=1 ollama serve
```

### Issue: Image not loading

**Solution**:
```python
# Ensure image path is absolute
from pathlib import Path
image_path = Path("image.png").resolve()

# Check file exists
assert image_path.exists(), f"Image not found: {image_path}"

# Check file size (should be <20MB)
size_mb = image_path.stat().st_size / (1024 * 1024)
print(f"Image size: {size_mb:.1f}MB")
```

---

## Comparison with Groq Vision API

| Feature | Qwen2.5-VL (Local) | Groq Vision API |
|---------|-------------------|-----------------|
| **Cost** | FREE | ~$0.04/page |
| **Speed** | 1-5s | 0.5-1.5s |
| **Privacy** | 100% local | Cloud-based |
| **Quality** | Excellent | Excellent |
| **OCR** | Excellent | Excellent |
| **Offline** | ✅ Yes | ❌ No |
| **Setup** | One-time install | API key needed |

### When to Use Each

**Use Qwen2.5-VL (Local):**
- ✅ Batch processing (no API costs)
- ✅ Privacy-sensitive documents
- ✅ Offline processing needed
- ✅ High-volume workloads

**Use Groq Vision API:**
- ✅ Need fastest speed (<1s)
- ✅ Qwen not installed
- ✅ Occasional use (cost not concern)
- ✅ Maximum quality critical

---

## Next Steps

1. ✅ Install Qwen2.5-VL via Ollama
2. ⏭️ Test on handwritten samples
3. ⏭️ Create `src/arxiv2rm/image_understanding.py`
4. ⏭️ Benchmark performance vs Groq
5. ⏭️ Integrate into PDF processing pipeline
6. ⏭️ Add EXIF metadata writing
7. ⏭️ Update INSTALL.md with Qwen setup

---

## Additional Resources

- [Qwen Documentation](https://qwen.readthedocs.io/en/latest/)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [Ollama Python Library](https://github.com/ollama/ollama-python)
- [LOCAL_VISION_MODELS_COMPARISON.md](LOCAL_VISION_MODELS_COMPARISON.md) - Detailed comparison
- [IMAGE_UNDERSTANDING_DEMO.md](IMAGE_UNDERSTANDING_DEMO.md) - Usage examples

---

## Summary

**Qwen2.5-VL 7B is now the recommended local vision model** for ArXiv-to-reMarkable:

- 🆓 **FREE** - No API costs
- 🔒 **Private** - All processing on-device
- ⚡ **Fast** - 1-5s per image on Apple Silicon
- 📊 **Excellent OCR** - Superior document understanding
- 🌍 **Multilingual** - Great for non-English papers
- 📦 **Easy Setup** - One command install via Ollama

Install now: `brew install ollama && ollama pull qwen2.5-vl:7b`
