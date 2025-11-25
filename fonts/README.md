# OpenDyslexic Fonts

This directory contains OpenDyslexic fonts used for EPUB generation.

## About OpenDyslexic

OpenDyslexic is an open-source typeface designed to increase readability for readers with dyslexia. The typeface includes regular, bold, italic, and bold-italic styles.

**License**: [SIL Open Font License (OFL)](https://scripts.sil.org/OFL)
**Website**: https://opendyslexic.org/
**Repository**: https://github.com/antijingoist/opendyslexic

## Required Fonts

For full EPUB styling, download these files:

```
OpenDyslexic-Regular.otf
OpenDyslexic-Bold.otf
OpenDyslexic-Italic.otf
OpenDyslexic-BoldItalic.otf
```

## Installation Methods

### Option 1: Manual Download

1. Visit https://opendyslexic.org/
2. Download the font package
3. Extract the `.otf` files to this directory
4. Ensure the filenames match those listed above

### Option 2: Direct Download from GitHub

```bash
# Download from GitHub releases
cd fonts/
curl -L -O https://github.com/antijingoist/opendyslexic/releases/download/v3.0.2/OpenDyslexic-Regular.otf
curl -L -O https://github.com/antijingoist/opendyslexic/releases/download/v3.0.2/OpenDyslexic-Bold.otf
curl -L -O https://github.com/antijingoist/opendyslexic/releases/download/v3.0.2/OpenDyslexic-Italic.otf
curl -L -O https://github.com/antijingoist/opendyslexic/releases/download/v3.0.2/OpenDyslexic-BoldItalic.otf
```

### Option 3: Automated Download (Python)

Run the font download helper:

```bash
python -m arxiv2rm.utils.download_fonts
```

## Verification

After installation, verify the fonts are present:

```bash
ls -lh fonts/OpenDyslexic-*.otf
```

Expected output:
```
OpenDyslexic-Bold.otf
OpenDyslexic-BoldItalic.otf
OpenDyslexic-Italic.otf
OpenDyslexic-Regular.otf
```

## Fallback

If OpenDyslexic fonts are not available, the EPUB builder will:
1. Warn about missing fonts
2. Generate EPUB with system default fonts (serif)
3. Continue without errors

The CSS includes fallback fonts: `'DejaVu Sans', Arial, sans-serif`

## License Compliance

OpenDyslexic is licensed under the SIL Open Font License (OFL), which allows:
- ✅ Free commercial and non-commercial use
- ✅ Modification and redistribution
- ✅ Embedding in documents (EPUB)

Requirements:
- ⚠️ Font files must not be sold by themselves
- ⚠️ Modified versions must use a different name (not required for embedding)

Full license: https://scripts.sil.org/OFL

## Troubleshooting

### Fonts not displaying on reMarkable

1. Verify fonts are embedded in EPUB (check EPUB contents with an unzip tool)
2. Ensure font MIME types are correct (`font/otf`)
3. Test EPUB in Calibre or another EPUB reader first
4. reMarkable may cache fonts - restart the device after transfer

### File size concerns

Each `.otf` file is approximately 20-50KB. Total font size: ~150KB, which is negligible for academic papers with images.

## Alternative Fonts

If OpenDyslexic doesn't suit your needs, consider:

- **Atkinson Hyperlegible**: Optimized for low vision readers
- **Literata**: Google's font for reading on screens
- **EB Garamond**: Classic serif with good e-ink rendering

Replace the `@font-face` declarations in `epub_styles.py` accordingly.
