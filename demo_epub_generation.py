#!/usr/bin/env python3
"""Demo: Generate EPUB from ArXiv paper with images."""

import sys
import zipfile
from pathlib import Path

from arxiv2rm.arxiv_client import ArxivClient
from arxiv2rm.epub_builder import EPUBBuilder, EPUBMetadata
from arxiv2rm.epub_styles import get_remarkable_css
from arxiv2rm.image_optimizer import ImageOptimizer
from arxiv2rm.latex_processor import process_latex_source


def demo_epub_generation(paper_id: str = "1706.03762", output_dir: Path = None):
    """
    Demonstrate complete EPUB generation pipeline.

    Args:
        paper_id: ArXiv paper ID (default: "Attention Is All You Need")
        output_dir: Output directory (default: ./demo_output)
    """
    if output_dir is None:
        output_dir = Path("./demo_output")

    output_dir.mkdir(exist_ok=True)

    print("=" * 80)
    print("ArXiv to reMarkable EPUB Generator - Demo")
    print("=" * 80)
    print()

    # Step 1: Fetch ArXiv paper
    print(f"📥 Step 1: Fetching ArXiv paper {paper_id}...")
    client = ArxivClient()
    metadata, latex_dir = client.fetch_paper(paper_id, prefer_latex=True)

    print(f"   ✓ Title: {metadata['title']}")
    print(f"   ✓ Authors: {', '.join(metadata['authors'][:3])}...")
    print(f"   ✓ Source type: {metadata['source_type']}")
    print()

    if metadata["source_type"] != "latex":
        print("   ⚠️  LaTeX source not available, using PDF fallback")
        print("   Note: Cannot extract images from PDF in this demo")
        return

    # Step 2: Parse LaTeX source
    print("📄 Step 2: Parsing LaTeX source...")
    main_tex = client.find_main_tex_file(latex_dir)
    if not main_tex:
        print("   ❌ Could not find main .tex file")
        return

    latex_doc = process_latex_source(latex_dir, main_tex)

    print(f"   ✓ Sections: {len(latex_doc.sections)}")
    print(f"   ✓ Figures: {len(latex_doc.figures)}")
    print(f"   ✓ Image files: {len(latex_doc.image_files)}")
    print()

    # Step 3: Optimize images
    print("🖼️  Step 3: Optimizing images for reMarkable...")
    optimized_images = []
    image_path_to_filename = {}  # Map source image path to optimized filename

    if latex_doc.image_files:
        optimizer = ImageOptimizer()
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        for i, img_path in enumerate(latex_doc.image_files, 1):
            try:
                # Use sanitized image name to avoid duplicates
                base_name = img_path.stem.replace("-", "_").replace(" ", "_")
                output_filename = f"{base_name}_opt.jpg"
                output_path = images_dir / output_filename

                result = optimizer.optimize(img_path, output_path)
                optimized_images.append(result)

                # Store mapping from original figure image_path to optimized filename
                # Multiple figures may reference the same image
                image_path_to_filename[img_path.stem] = output_filename

                size_kb = result.stat().st_size // 1024
                print(f"   ✓ Optimized {img_path.name} → {output_filename} ({size_kb}KB)")
            except Exception as e:
                print(f"   ⚠️  Skipped {img_path.name}: {e}")

        print(f"   ✓ Total: {len(optimized_images)} images optimized")
    else:
        print("   ℹ️  No images found in LaTeX source")
    print()

    # Step 3.5: Render tables as images
    print("📊 Step 3.5: Rendering tables as images...")
    rendered_tables = []
    if latex_doc.tables:
        from arxiv2rm.table_renderer import TableRenderer

        table_renderer = TableRenderer()
        tables_dir = output_dir / "tables"
        tables_dir.mkdir(exist_ok=True)

        for table in latex_doc.tables:
            try:
                output_path = tables_dir / f"table_{table.number}.png"
                result = table_renderer.render(table, output_path, dpi=150)
                if result:
                    rendered_tables.append(result)
                    table.image_path = result  # Update table with image path
                    size_kb = result.stat().st_size // 1024
                    print(
                        f"   ✓ Rendered Table {table.number} → "
                        f"table_{table.number}.png ({size_kb}KB)"
                    )
                else:
                    print(f"   ⚠️  Failed to render Table {table.number}")
            except Exception as e:
                print(f"   ⚠️  Skipped Table {table.number}: {e}")

        print(f"   ✓ Total: {len(rendered_tables)}/{len(latex_doc.tables)} tables rendered")
    else:
        print("   ℹ️  No tables found in LaTeX source")
    print()

    # Step 4: Build EPUB
    print("📚 Step 4: Building EPUB...")
    epub_metadata = EPUBMetadata(
        title=latex_doc.title or metadata["title"],
        authors=latex_doc.authors or metadata["authors"],
        description=latex_doc.abstract,
        source_url=metadata.get("pdf_url"),
    )

    # Generate filename: sanitized title + arxiv ID
    title = latex_doc.title or metadata["title"]
    # Sanitize title: lowercase, replace spaces/special chars with hyphens, truncate
    safe_title = "".join(c if c.isalnum() or c in [" ", "-"] else "" for c in title)
    safe_title = "-".join(safe_title.lower().split())[:50]  # Max 50 chars
    safe_paper_id = paper_id.replace("/", "_").replace(".", "_")

    epub_filename = f"{safe_title}-{safe_paper_id}.epub"
    epub_path = output_dir / epub_filename
    builder = EPUBBuilder(epub_metadata, epub_path)
    builder.build_from_latex(latex_doc)

    # Add CSS
    css_content = get_remarkable_css()
    builder.add_css(css_content)
    print("   ✓ Added CSS stylesheet")

    # Add OpenDyslexic fonts
    from os.path import expanduser

    font_names = [
        "OpenDyslexic-Regular.otf",
        "OpenDyslexic-Bold.otf",
        "OpenDyslexic-Italic.otf",
        "OpenDyslexic-BoldItalic.otf",
    ]

    # Try to find fonts in system fonts directories
    system_font_paths = [
        Path(expanduser("~/Library/Fonts")),  # macOS user fonts
        Path("/Library/Fonts"),  # macOS system fonts
        Path("/System/Library/Fonts"),  # macOS system fonts
    ]

    # Embed fonts into EPUB directly from system
    fonts_embedded = 0
    for font_name in font_names:
        # Search for font in system directories
        for font_dir in system_font_paths:
            font_path = font_dir / font_name
            if font_path.exists():
                try:
                    builder.add_font(font_path, font_name)
                    fonts_embedded += 1
                    break
                except Exception as e:
                    print(f"   ⚠️  Could not embed {font_name}: {e}")

    if fonts_embedded > 0:
        print(f"   ✓ Embedded {fonts_embedded} OpenDyslexic font files")
    else:
        print("   ⚠️  No fonts embedded (will use fallback fonts)")

    # Add optimized images
    for img_path in optimized_images:
        builder.add_image(img_path, img_path.name)
    print(f"   ✓ Embedded {len(optimized_images)} images")

    # Add rendered table images
    for table_path in rendered_tables:
        builder.add_image(table_path, table_path.name)
    print(f"   ✓ Embedded {len(rendered_tables)} table images")

    # Write EPUB
    builder.write()
    print(f"   ✓ EPUB written: {epub_path}")
    print()

    # Step 5: Show results
    print("📊 Step 5: EPUB Statistics")
    print("-" * 80)

    # File size
    epub_size = epub_path.stat().st_size
    print(f"File size: {epub_size / 1024:.1f} KB ({epub_size / (1024*1024):.2f} MB)")
    print()

    # EPUB contents
    print("EPUB Contents:")
    with zipfile.ZipFile(epub_path) as zf:
        files = zf.namelist()
        print(f"  Total files: {len(files)}")

        xhtml_files = [f for f in files if f.endswith(".xhtml")]
        print(f"  Chapters: {len(xhtml_files)}")

        image_files = [f for f in files if f.startswith("images/")]
        print(f"  Images: {len(image_files)}")

        css_files = [f for f in files if f.endswith(".css")]
        print(f"  Stylesheets: {len(css_files)}")

    print()

    # Structure preview
    print("Document Structure:")
    if latex_doc.title:
        print(f"  Title: {latex_doc.title[:60]}...")
    if latex_doc.authors:
        print(f"  Authors: {', '.join(latex_doc.authors[:3])}")
    if latex_doc.abstract:
        print(f"  Abstract: {latex_doc.abstract[:100]}...")
    print()
    print("  Sections:")
    for section in latex_doc.sections[:10]:
        indent = "  " * section.level
        print(f"{indent}- {section.title}")
    if len(latex_doc.sections) > 10:
        print(f"  ... and {len(latex_doc.sections) - 10} more sections")
    print()

    # Success
    print("=" * 80)
    print("✅ EPUB generation complete!")
    print("=" * 80)
    print()
    print(f"Output file: {epub_path.absolute()}")
    print()
    print("Next steps:")
    print("  1. Test in Calibre: calibre-ebook-viewer", epub_path.name)
    print("  2. Validate: epubcheck", epub_path.name)
    print("  3. Transfer to reMarkable device")
    print()

    return epub_path


if __name__ == "__main__":
    paper_id = sys.argv[1] if len(sys.argv) > 1 else "1706.03762"
    demo_epub_generation(paper_id)
