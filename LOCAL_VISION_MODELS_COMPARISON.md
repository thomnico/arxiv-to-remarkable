# Best Local Vision Models for Image Understanding (2025)

## Executive Summary

Based on research from January 2025, the top 3 local vision models for image understanding are:

1. **🥇 Qwen2.5-VL** (Alibaba) - Best overall for document understanding and OCR
2. **🥈 Pixtral** (Mistral AI) - Best for instruction following and multi-image processing
3. **🥉 LLaVA** - Best for ecosystem and specialized variants

---

## Detailed Comparison

### 1. Qwen2.5-VL (Alibaba Cloud) - **RECOMMENDED** ⭐

**Models Available:**
- Qwen2.5-VL-7B (Recommended for local use)
- Qwen2.5-VL-72B-Instruct (High performance)

**Benchmark Performance:**
- **MMMUval**: 70.2 (72B model)
- **MathVista_MINI**: 74.8
- **MMStar**: 70.8
- The 7B variant outperforms Llama 3.2 Vision 11B on several benchmarks

**Strengths:**
- ✅ **Best-in-class OCR** - Superior document understanding
- ✅ **Efficient 7B model** - Runs well on consumer hardware
- ✅ **Multilingual support** - Excellent for non-English documents
- ✅ **Chart/table parsing** - Can output structured JSON/CSV
- ✅ **Object localization** - Precise positioning
- ✅ **Native Ollama support** - Easy installation

**Hardware Requirements (7B model):**
- RAM: 8GB+ (16GB recommended)
- VRAM: 8GB+ for GPU acceleration
- Mac Apple Silicon: Optimized for M1/M2/M3/M4

**Installation (macOS):**
```bash
# Install Ollama
brew install ollama

# Pull Qwen2.5-VL 7B model
ollama pull qwen2.5-vl:7b

# Test installation
ollama run qwen2.5-vl:7b
```

**Use Cases:**
- Scientific paper image analysis
- Chart and diagram description
- Table extraction to structured data
- Handwritten text OCR
- Multilingual document processing

**Sources:**
- [Qwen 2.5 VL Complete Guide 2025](https://apatero.com/blog/qwen-25-vl-image-understanding-complete-guide-2025)
- [Run Qwen2.5-VL 7B Locally](https://www.labellerr.com/blog/run-qwen2-5-vl-locally/)
- [Qwen Documentation - Ollama](https://qwen.readthedocs.io/en/latest/run_locally/ollama.html)

---

### 2. Pixtral (Mistral AI)

**Models Available:**
- Pixtral 12B (Initial release)
- Pixtral Large (State-of-the-art)

**Benchmark Performance:**
- **Instruction Following**: Significantly outperforms Qwen2-VL 7B and LLaVA-OneVision 7B
- **MathVista**: State-of-the-art
- **DocVQA**: State-of-the-art
- **VQAv2**: State-of-the-art

**Strengths:**
- ✅ **Multi-image processing** - Handle multiple images simultaneously (30+ at native resolution)
- ✅ **Large context window** - 128,000 tokens
- ✅ **Instruction following** - Best-in-class for complex instructions
- ✅ **Native resolution** - Processes images without downscaling

**Hardware Requirements (12B model):**
- RAM: 12GB+ (24GB recommended)
- VRAM: 12GB+ for GPU acceleration
- Context window requires significant memory for multi-image tasks

**Strengths over Qwen2.5-VL:**
- Better at complex instruction following
- Can process many images at once
- Superior for visual reasoning tasks

**Weaknesses:**
- Larger model size (12B vs 7B)
- Less optimized for Apple Silicon than Qwen
- Fewer community resources/examples

**Use Cases:**
- Multi-page document analysis
- Comparative visual analysis (multiple images)
- Complex visual reasoning
- Interactive image Q&A

**Sources:**
- [Best Multimodal Vision Models 2025](https://www.koyeb.com/blog/best-multimodal-vision-models-in-2025)
- [Multimodal AI Guide - BentoML](https://www.bentoml.com/blog/multimodal-ai-a-guide-to-open-source-vision-language-models)

---

### 3. LLaVA (Various Organizations)

**Models Available:**
- LLaVA-1.5 (7B, 13B)
- LLaVA-NeXT (7B, 13B, 34.75B)
- LLaVA-OneVision (7B)

**Benchmark Performance:**
- State-of-the-art across 11 benchmarks (LLaVA-1.5)
- Generally outperformed by Qwen2.5-VL on document understanding and OCR

**Strengths:**
- ✅ **Large ecosystem** - Many fine-tuned variants for specific tasks
- ✅ **Mature community** - Extensive documentation and examples
- ✅ **Specialized models** - Domain-specific variants available
- ✅ **Well-tested** - One of the earliest and most refined VLMs

**Weaknesses:**
- Lower OCR performance vs Qwen2.5-VL
- Less efficient than newer models
- Document understanding not as strong

**Use Cases:**
- General-purpose image understanding
- Fine-tuned for specific domains
- Research and experimentation

**Sources:**
- [Top Vision Language Models 2025](https://www.datacamp.com/blog/top-vision-language-models)
- [Best Local Vision-Language Models](https://blog.roboflow.com/local-vision-language-models/)

---

## Quick Comparison Table

| Feature | Qwen2.5-VL (7B) | Pixtral (12B) | LLaVA (7B) |
|---------|-----------------|---------------|------------|
| **OCR Quality** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Document Understanding** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Instruction Following** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Multi-image Support** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Apple Silicon Optimization** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Memory Efficiency (7B)** | ⭐⭐⭐⭐⭐ | N/A (12B) | ⭐⭐⭐⭐ |
| **Ease of Installation** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Community/Ecosystem** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Multilingual** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## Cost & Performance Analysis

**Open-source VLMs in 2025:**
- **60% reduction** in inference costs vs commercial models
- **Competitive benchmarks**: MMBench >80%, MM-Vet >75% (top models)
- **Free to run locally** - No API costs
- **Privacy-preserving** - All processing on-device

**Groq Vision API (for comparison):**
- Cost: ~$0.04/page (~2000 tokens)
- Speed: 0.5-1.5s per image
- Quality: Excellent (Llama 4 Scout 17B)
- Requires internet connection

**Qwen2.5-VL 7B Local:**
- Cost: FREE (after initial download)
- Speed: 2-5s per image (Apple Silicon M3)
- Quality: Excellent for OCR and document understanding
- Offline-capable

---

## Recommendation for ArXiv-to-reMarkable

### Primary: Qwen2.5-VL 7B (Local)

**Why Qwen2.5-VL:**
1. ✅ **Best OCR performance** - Critical for scientific papers
2. ✅ **Document understanding** - Excellent for academic content
3. ✅ **Efficient 7B model** - Runs on consumer hardware
4. ✅ **FREE** - No API costs for batch processing
5. ✅ **Privacy** - Process sensitive research offline
6. ✅ **Easy installation** - Native Ollama support
7. ✅ **Apple Silicon optimized** - Fast on M1/M2/M3/M4

### Fallback: Groq Vision API (Cloud)

**When to use Groq:**
- Qwen2.5-VL not installed
- Need fastest possible speed (<1s)
- Extremely complex visual reasoning
- User doesn't mind API costs

---

## Implementation Plan

### Step 1: Install Qwen2.5-VL 7B

```bash
# Install Ollama (if not already installed)
brew install ollama

# Pull Qwen2.5-VL 7B model (~4.7GB download)
ollama pull qwen2.5-vl:7b

# Verify installation
ollama run qwen2.5-vl:7b "Describe this test"
```

### Step 2: Create Python Wrapper

```python
# src/arxiv2rm/image_understanding.py
import subprocess
import json
import base64
from pathlib import Path
from typing import Dict, Optional

class ImageUnderstanding:
    """Image understanding using local Qwen2.5-VL or cloud Groq Vision."""

    def __init__(self, prefer_local: bool = True):
        self.prefer_local = prefer_local
        self.local_available = self._check_qwen_available()

    def _check_qwen_available(self) -> bool:
        """Check if Qwen2.5-VL is installed in Ollama."""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return "qwen2.5-vl" in result.stdout.lower()
        except:
            return False

    def describe_image(self, image_path: Path,
                      prompt: str = "Describe this image in detail") -> Dict:
        """Describe what an image represents."""

        if self.prefer_local and self.local_available:
            return self._describe_with_qwen(image_path, prompt)
        else:
            return self._describe_with_groq(image_path, prompt)

    def _describe_with_qwen(self, image_path: Path, prompt: str) -> Dict:
        """Use local Qwen2.5-VL via Ollama."""
        # Implementation using ollama Python library
        # See: https://github.com/ollama/ollama-python
        pass

    def _describe_with_groq(self, image_path: Path, prompt: str) -> Dict:
        """Use Groq Vision API as fallback."""
        # Existing Groq implementation
        pass
```

### Step 3: Update PRD.md

Update section 4.2 to list Qwen2.5-VL as the **PRIMARY** local option:

```markdown
- **Vision Model for Content Detection**:
  - **PRIMARY (Local)**: Qwen2.5-VL 7B via Ollama
  - **FALLBACK (Cloud)**: Groq Vision API (Llama 4 Scout)
```

### Step 4: Test on Scientific Papers

```bash
# Test on handwritten samples
python -m arxiv2rm.image_understanding \
  describe \
  exemples/handwritten/*.png \
  --model qwen2.5-vl

# Compare with Groq
python -m arxiv2rm.image_understanding \
  compare \
  exemples/handwritten/*.png \
  --models qwen2.5-vl,groq
```

---

## Hardware Requirements Summary

### Qwen2.5-VL 7B (Recommended)
- **Minimum**: 8GB RAM, Apple Silicon M1+
- **Recommended**: 16GB RAM, M2+ or better
- **Optimal**: 32GB+ RAM, M3 Max/Ultra
- **Storage**: 5GB for model weights

### Performance Estimates (Apple Silicon)
- **M1 (8GB)**: 3-5s per image
- **M2 (16GB)**: 2-4s per image
- **M3 (24GB+)**: 1-3s per image
- **Batch processing**: ~100 images/hour on M2

---

## Next Steps

1. ✅ Research completed - Qwen2.5-VL identified as best local option
2. ⏭️ Install Qwen2.5-VL 7B via Ollama
3. ⏭️ Create Python wrapper: `src/arxiv2rm/image_understanding.py`
4. ⏭️ Test on handwritten samples vs Groq
5. ⏭️ Benchmark performance and quality
6. ⏭️ Update PRD.md with Qwen2.5-VL as primary local option
7. ⏭️ Integrate into PDF processing pipeline
8. ⏭️ Add EXIF metadata writing
9. ⏭️ Document usage in INSTALL.md

---

## Sources

1. [Best Open-Source Vision Language Models of 2025](https://www.labellerr.com/blog/top-open-source-vision-language-models/)
2. [Best Multimodal Vision Models in 2025 - Koyeb](https://www.koyeb.com/blog/best-multimodal-vision-models-in-2025)
3. [Qwen 2.5 VL Complete Guide 2025](https://apatero.com/blog/qwen-25-vl-image-understanding-complete-guide-2025)
4. [Top 10 Vision Language Models 2025 - DataCamp](https://www.datacamp.com/blog/top-vision-language-models)
5. [Multimodal AI - BentoML](https://www.bentoml.com/blog/multimodal-ai-a-guide-to-open-source-vision-language-models)
6. [Best Local Vision-Language Models](https://blog.roboflow.com/local-vision-language-models/)
7. [Ollama Qwen 3 VL Local Setup Guide](https://apatero.com/blog/ollama-qwen-3-vl-models-local-guide-2025)
8. [Qwen Documentation - Ollama](https://qwen.readthedocs.io/en/latest/run_locally/ollama.html)
9. [Run Qwen2.5-VL 7B Locally](https://www.labellerr.com/blog/run-qwen2-5-vl-locally/)
10. [Setting up local LLM on macOS with Ollama](https://gist.github.com/othyn/42e67d7b6116d88d6c9c83e7d84b20c0)

---

## Conclusion

**Qwen2.5-VL 7B is the best local vision model** for the ArXiv-to-reMarkable project because:

- 🥇 Superior OCR and document understanding
- 💰 FREE (no API costs)
- 🔒 Privacy-preserving (offline processing)
- ⚡ Fast on Apple Silicon (optimized)
- 📦 Easy installation via Ollama
- 🌍 Excellent multilingual support
- 📊 Can parse charts/tables to structured data

It should be used as the **PRIMARY** option for image understanding, with Groq Vision API as a cloud fallback when needed.
