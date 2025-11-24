# ArXiv to reMarkable Converter

## Project Overview
Tool to convert scientific papers (ArXiv, IEEE, etc.) into reMarkable-optimized PDFs with enhanced readability and annotation capabilities.

## Core Objectives
- Convert scientific papers to reMarkable-friendly format
- Use OCR (DeepSync OCR preferred) for text extraction
- Apply OpenDyslexic font for improved readability
- Increase font size for comfortable reading on e-ink display
- Add annotation zones for note-taking
- Push converted files directly to reMarkable device

## Technology Stack
- **OCR Engine**: Groq Vision API (Llama 4 Scout, Llama 3.2 Vision) via Deepseek-OCR
- **PDF Processing**: PyMuPDF (fitz), PDFPlumber, or pdf2image
- **Font**: OpenDyslexic (open-source dyslexia-friendly font)
- **reMarkable Integration**: rmapi or rMsync for file transfer
- **Language**: Python 3.9+

## Groq API Configuration
- **Vision Models**: Llama 4 Scout (meta-llama/llama-4-scout-17b-16e-instruct), Llama 3.2 Vision (llama-3.2-90b-vision-preview, llama-3.2-11b-vision-preview)
- **API Endpoint**: https://api.groq.com/openai/v1/models
- **Get Available Models**:
  ```bash
  curl -X GET "https://api.groq.com/openai/v1/models" \
       -H "Authorization: Bearer $GROQ_API_KEY" \
       -H "Content-Type: application/json"
  ```
- **Image Limits**: Max 20MB per request (URLs), 4MB (base64), 33 megapixels max resolution
- **OCR Testing Results**: Groq Vision (Llama 4 Scout) significantly outperforms Tesseract on handwritten text (408 vs 168 chars extracted, meaningful vs gibberish)

## Key Features
1. **Multi-source support**: ArXiv, IEEE, PDF URLs, local PDFs
2. **OCR processing**: Extract text from scanned/image-based PDFs
3. **Layout optimization**:
   - Larger font size (14-16pt minimum)
   - OpenDyslexic typeface
   - Single column layout
   - Margins for annotations
4. **Note-taking zones**: Dedicated areas for handwritten notes
5. **Metadata preservation**: Author, title, publication info
6. **Batch processing**: Convert multiple papers at once
7. **Auto-sync**: Direct push to reMarkable cloud/device

## Project Structure
```
arxiv-to-remarkable/
├── src/
│   ├── converters/       # PDF conversion logic
│   ├── ocr/             # OCR processing
│   ├── formatters/      # Layout and typography
│   ├── remarkable/      # reMarkable integration
│   └── cli.py           # Command-line interface
├── tests/
├── config/
│   ├── fonts/           # OpenDyslexic fonts
│   └── templates/       # Page layout templates
├── .env.template        # Configuration template
└── requirements.txt
```

## Development Guidelines
- Minimal dependencies
- Configurable settings (font size, margins, OCR engine)
- Progress indicators for long operations
- Error handling for network/OCR failures
- Cache OCR results to avoid reprocessing

## Security
- Never commit API keys or credentials
- Use .env for reMarkable cloud tokens
- Add .env to .gitignore

## Quality Standards
- Test with various paper formats (2-column, single-column, scanned)
- Verify OCR accuracy on mathematical formulas
- Validate output on actual reMarkable device
- Benchmark conversion speed
