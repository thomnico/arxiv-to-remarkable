# Groq Vision OCR Integration Guide

## Overview

This document provides implementation guidance for integrating Groq Vision API for OCR in the ArXiv to reMarkable converter, based on proven patterns from the ghost-in-the-mail project.

## Key Insights from ghost-in-the-mail

### What Works

✅ **Groq Vision API** (Llama 4 Scout/Maverick models)
- Ultra-fast OCR: 0.4-0.7s per document
- 100% accuracy on test documents
- Excellent structure preservation (tables, formatting)
- Handles complex layouts and mathematical notation
- Base64 image encoding support (max 4MB)

❌ **What Groq Does NOT Support**
- Text embeddings (use OpenAI or local ONNX models instead)
- Vector similarity search

### Architecture Pattern

```
ArXiv PDF → Extract Pages as Images → Groq Vision OCR → Text Content
                                                          ↓
                                            Combine with LaTeX source (if available)
                                                          ↓
                                            Format for reMarkable
```

## Implementation Code (Go Reference)

### 1. OCR Service Structure

```go
package ocr

import (
    "bytes"
    "context"
    "encoding/base64"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "os"
    "path/filepath"
    "time"

    "go.uber.org/zap"
)

// GroqVisionService implements OCR using Groq's vision models
type GroqVisionService struct {
    endpoint string
    apiKey   string
    model    string
    timeout  time.Duration
    client   *http.Client
    logger   *zap.Logger
}

type GroqVisionConfig struct {
    Endpoint string
    APIKey   string
    Model    string // "meta-llama/llama-4-scout-17b-16e-instruct" or "maverick"
    Timeout  int    // seconds
}

func NewGroqVisionService(cfg GroqVisionConfig, logger *zap.Logger) *GroqVisionService {
    timeout := 60 * time.Second
    if cfg.Timeout > 0 {
        timeout = time.Duration(cfg.Timeout) * time.Second
    }

    model := cfg.Model
    if model == "" {
        model = "meta-llama/llama-4-scout-17b-16e-instruct"
    }

    return &GroqVisionService{
        endpoint: cfg.Endpoint,
        apiKey:   cfg.APIKey,
        model:    model,
        timeout:  timeout,
        client:   &http.Client{Timeout: timeout},
        logger:   logger,
    }
}
```

### 2. Request/Response Structures

```go
type visionChatRequest struct {
    Model    string          `json:"model"`
    Messages []visionMessage `json:"messages"`
    MaxTokens int            `json:"max_completion_tokens,omitempty"`
}

type visionMessage struct {
    Role    string          `json:"role"`
    Content []visionContent `json:"content"`
}

type visionContent struct {
    Type     string    `json:"type"` // "text" or "image_url"
    Text     string    `json:"text,omitempty"`
    ImageURL *imageURL `json:"image_url,omitempty"`
}

type imageURL struct {
    URL string `json:"url"` // data:image/jpeg;base64,...
}

type visionChatResponse struct {
    ID      string `json:"id"`
    Choices []struct {
        Index   int `json:"index"`
        Message struct {
            Role    string `json:"role"`
            Content string `json:"content"`
        } `json:"message"`
        FinishReason string `json:"finish_reason"`
    } `json:"choices"`
    Usage struct {
        PromptTokens     int `json:"prompt_tokens"`
        CompletionTokens int `json:"completion_tokens"`
        TotalTokens      int `json:"total_tokens"`
    } `json:"usage"`
}
```

### 3. OCR Extraction Method

```go
func (g *GroqVisionService) ExtractText(ctx context.Context, filePath string) (string, error) {
    // Read and encode image
    imageData, err := os.ReadFile(filePath)
    if err != nil {
        return "", fmt.Errorf("failed to read image file: %w", err)
    }

    // Check file size (max 4MB for base64)
    if len(imageData) > 4*1024*1024 {
        return "", fmt.Errorf("image file too large (max 4MB): %d bytes", len(imageData))
    }

    // Detect MIME type and encode
    mimeType := getMimeType(filePath)
    base64Image := base64.StdEncoding.EncodeToString(imageData)
    dataURI := fmt.Sprintf("data:%s;base64,%s", mimeType, base64Image)

    // Prepare OCR prompt
    prompt := "Extract all text from this image. Return only the extracted text without any additional commentary or formatting. If the image contains tables, preserve the structure with tabs and newlines."

    // Build request
    reqBody := visionChatRequest{
        Model: g.model,
        Messages: []visionMessage{
            {
                Role: "user",
                Content: []visionContent{
                    {Type: "text", Text: prompt},
                    {Type: "image_url", ImageURL: &imageURL{URL: dataURI}},
                },
            },
        },
        MaxTokens: 4096,
    }

    jsonData, err := json.Marshal(reqBody)
    if err != nil {
        return "", fmt.Errorf("failed to marshal request: %w", err)
    }

    // Create HTTP request
    req, err := http.NewRequestWithContext(ctx, "POST", g.endpoint, bytes.NewBuffer(jsonData))
    if err != nil {
        return "", fmt.Errorf("failed to create request: %w", err)
    }

    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", g.apiKey))

    // Execute request
    startTime := time.Now()
    resp, err := g.client.Do(req)
    if err != nil {
        return "", fmt.Errorf("failed to execute request: %w", err)
    }
    defer resp.Body.Close()

    duration := time.Since(startTime)

    // Read response
    body, err := io.ReadAll(resp.Body)
    if err != nil {
        return "", fmt.Errorf("failed to read response: %w", err)
    }

    if resp.StatusCode != http.StatusOK {
        return "", fmt.Errorf("Groq Vision API error (status %d): %s", resp.StatusCode, string(body))
    }

    // Parse response
    var chatResp visionChatResponse
    if err := json.Unmarshal(body, &chatResp); err != nil {
        return "", fmt.Errorf("failed to parse response: %w", err)
    }

    if len(chatResp.Choices) == 0 {
        return "", fmt.Errorf("no response choices returned")
    }

    extractedText := chatResp.Choices[0].Message.Content

    g.logger.Info("OCR extraction complete",
        zap.String("file", filePath),
        zap.Int("text_length", len(extractedText)),
        zap.Int("prompt_tokens", chatResp.Usage.PromptTokens),
        zap.Int("completion_tokens", chatResp.Usage.CompletionTokens),
        zap.Duration("duration", duration),
    )

    return extractedText, nil
}

func getMimeType(filePath string) string {
    ext := filepath.Ext(filePath)
    switch ext {
    case ".jpg", ".jpeg":
        return "image/jpeg"
    case ".png":
        return "image/png"
    case ".gif":
        return "image/gif"
    case ".webp":
        return "image/webp"
    case ".pdf":
        return "application/pdf"
    default:
        return "application/octet-stream"
    }
}
```

## Python Implementation

### Using OpenAI-compatible API

```python
import base64
import os
from pathlib import Path
import requests
from typing import Optional

class GroqVisionOCR:
    def __init__(self, api_key: str, model: str = "meta-llama/llama-4-scout-17b-16e-instruct"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"
        self.timeout = 60

    def extract_text(self, image_path: str) -> str:
        """Extract text from an image using Groq Vision API."""
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = f.read()

        # Check size (max 4MB)
        if len(image_data) > 4 * 1024 * 1024:
            raise ValueError(f"Image too large: {len(image_data)} bytes (max 4MB)")

        # Encode to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        mime_type = self._get_mime_type(image_path)
        data_uri = f"data:{mime_type};base64,{base64_image}"

        # Prepare request
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all text from this image. Return only the extracted text without any additional commentary or formatting. If the image contains tables, preserve the structure with tabs and newlines."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_uri
                            }
                        }
                    ]
                }
            ],
            "max_completion_tokens": 4096
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # Make request
        response = requests.post(
            self.endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout
        )

        if response.status_code != 200:
            raise Exception(f"Groq API error ({response.status_code}): {response.text}")

        result = response.json()

        if not result.get('choices'):
            raise Exception("No response from Groq API")

        extracted_text = result['choices'][0]['message']['content']

        return extracted_text

    def _get_mime_type(self, file_path: str) -> str:
        """Determine MIME type from file extension."""
        ext = Path(file_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.pdf': 'application/pdf'
        }
        return mime_types.get(ext, 'application/octet-stream')
```

### Usage Example

```python
# Initialize
ocr = GroqVisionOCR(api_key=os.getenv("GROQ_API_KEY"))

# Extract text from PDF page (converted to image)
text = ocr.extract_text("/tmp/arxiv_page_1.png")
print(text)
```

## Configuration

### Environment Variables

```bash
# .env.template
GROQ_API_KEY=gsk_your_key_here
```

### Config File (YAML)

```yaml
ocr:
  provider: "groq"
  groq:
    endpoint: "https://api.groq.com/openai/v1/chat/completions"
    api_key: ${GROQ_API_KEY}
    model: "meta-llama/llama-4-scout-17b-16e-instruct"
    timeout: 60

  # Fallback to Tesseract for offline processing
  tesseract:
    enabled: true
    language: "eng"
```

## Performance Benchmarks

Based on ghost-in-the-mail testing:

| Document Type | Size | Duration | Accuracy | Tokens |
|---------------|------|----------|----------|--------|
| Simple text | 11KB | 384ms | 100% | 1,093 |
| Complex invoice | 67KB | 734ms | 100% | 1,162 |
| Scientific paper page | ~50KB | ~600ms | >95% | ~1,200 |

**Average**: 0.5-0.7s per page

## Best Practices

### 1. Image Preprocessing

For scientific papers:
- Convert PDF pages to PNG at 150-300 DPI
- Ensure images are under 4MB
- Use lossless compression when possible

### 2. Error Handling

```python
def extract_with_fallback(image_path: str) -> str:
    """Try Groq OCR first, fall back to Tesseract."""
    try:
        return groq_ocr.extract_text(image_path)
    except Exception as e:
        logger.warning(f"Groq OCR failed: {e}, falling back to Tesseract")
        return tesseract_ocr.extract_text(image_path)
```

### 3. Caching

```python
import hashlib
import json

def cached_ocr(image_path: str, cache_dir: str = ".ocr_cache") -> str:
    """Cache OCR results to avoid reprocessing."""
    # Generate cache key from file hash
    with open(image_path, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    cache_file = Path(cache_dir) / f"{file_hash}.json"

    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)['text']

    # Extract text
    text = ocr.extract_text(image_path)

    # Save to cache
    cache_file.parent.mkdir(exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump({'text': text, 'path': image_path}, f)

    return text
```

### 4. Batch Processing

```python
from concurrent.futures import ThreadPoolExecutor
import time

def batch_ocr(image_paths: list[str], max_workers: int = 3) -> list[str]:
    """Process multiple images in parallel (respect rate limits)."""
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(ocr.extract_text, path) for path in image_paths]

        for future in futures:
            try:
                text = future.result()
                results.append(text)
            except Exception as e:
                print(f"OCR failed: {e}")
                results.append("")

            # Rate limiting (optional)
            time.sleep(0.1)

    return results
```

## Cost Estimation

Check current Groq pricing at: https://groq.com/pricing

Typical usage for 20-page paper:
- 20 pages × ~1,200 tokens/page = 24,000 tokens
- Estimated cost: Check Groq pricing page
- Compare to: Tesseract (free, slower), Google Cloud Vision ($1.50/1000 images)

## Limitations

### Technical Limits
- Max image size: 4MB (base64) or 20MB (URL)
- Max resolution: 33 megapixels
- Max images per request: 5
- Timeout: 60 seconds recommended

### Accuracy Considerations
- Mathematical formulas: 95%+ accuracy, but verify complex equations
- Handwritten text: Variable (not primary use case)
- Low-quality scans: May require preprocessing

## Integration with ArXiv LaTeX Source

For ArXiv papers, prefer LaTeX source when available:

```python
def get_paper_content(arxiv_id: str) -> dict:
    """Get paper content from LaTeX source or OCR fallback."""
    try:
        # Try to download LaTeX source
        latex_source = download_arxiv_latex(arxiv_id)
        text = extract_text_from_latex(latex_source)
        return {'source': 'latex', 'text': text}
    except Exception:
        # Fallback to PDF OCR
        pdf_path = download_arxiv_pdf(arxiv_id)
        images = pdf_to_images(pdf_path)
        texts = [ocr.extract_text(img) for img in images]
        return {'source': 'ocr', 'text': '\n\n'.join(texts)}
```

## Troubleshooting

### Rate Limit Errors
```
Error 429: Rate limit exceeded
```
**Solution**: Add delay between requests or reduce parallel workers

### Image Size Errors
```
Error: Image too large (4MB limit)
```
**Solution**: Compress image or reduce resolution before encoding

### Timeout Errors
```
Error: Request timeout
```
**Solution**: Increase timeout value or split large documents

## References

- Groq API Documentation: https://console.groq.com/docs
- Groq Vision Models: https://console.groq.com/docs/models
- ghost-in-the-mail implementation: `/Users/nicolasthomas/inkan/ghost-in-the-mail/internal/ocr/groq_vision.go`
