"""Command-line interface for arxiv2rm."""

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress
from rich.table import Table

from arxiv2rm import __version__
from arxiv2rm.config import ConfigLoader, get_config

console = Console()


def setup_logging(level: str = "INFO") -> None:
    """Configure logging with rich handler.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_dir = Path.home() / ".arxiv2rm" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "arxiv2rm.log"

    # Configure logging
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(console=console, rich_tracebacks=True),
            logging.FileHandler(log_file),
        ],
    )


@click.group()
@click.version_option(version=__version__)
@click.option("--config-file", type=click.Path(), help="Path to config file")
@click.option("--log-level", default="INFO", help="Logging level")
@click.pass_context
def main(ctx, config_file, log_level):
    """ArXiv to reMarkable converter.

    Convert scientific papers to EPUB format optimized for reMarkable devices.
    """
    ctx.ensure_object(dict)

    # Setup logging
    setup_logging(log_level)
    logger = logging.getLogger(__name__)

    # Load configuration
    try:
        if config_file:
            from arxiv2rm.config import set_config_path

            set_config_path(Path(config_file))

        config = get_config()
        ctx.obj["config"] = config
        logger.debug("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        logger.info("Using default configuration")
        ctx.obj["config"] = None


@main.command()
@click.argument("url_or_path")
@click.option("--output", "-o", help="Output file path")
@click.option("--format", "output_format", default="epub", help="Output format (epub)")
@click.option("--ocr-engine", default="local", help="OCR engine (local, groq, tesseract)")
@click.option("--image-quality", type=int, default=85, help="JPEG quality (1-100)")
@click.option("--title", help="Override document title")
@click.option("--author", multiple=True, help="Author name (can be repeated)")
@click.option("--columns/--no-columns", default=True, help="Enable column detection")
@click.option("--remarkable-folder", help="reMarkable folder")
@click.option("--upload/--no-upload", default=None, help="Upload to reMarkable")
@click.pass_context
def convert(
    ctx,
    url_or_path,
    output,
    output_format,
    ocr_engine,
    image_quality,
    title,
    author,
    columns,
    remarkable_folder,
    upload,
):
    """Convert a paper to EPUB format.

    \b
    Examples:
        arxiv2rm convert paper.pdf
        arxiv2rm convert paper.pdf --output custom.epub
        arxiv2rm convert paper.pdf --title "My Paper" --author "John Doe"
        arxiv2rm convert paper.pdf --no-columns  # Disable column detection
    """
    from arxiv2rm.converter import ConversionOptions, PDFToEPUBConverter
    from arxiv2rm.image_optimizer import RemarkableDevice

    config = ctx.obj.get("config")

    # Use config values as defaults if not specified
    if config:
        ocr_engine = ocr_engine or config.ocr.engine
        image_quality = image_quality or config.images.quality
        remarkable_folder = remarkable_folder or config.remarkable.default_folder
        if upload is None:
            upload = config.remarkable.auto_upload

    # Check if input is URL or file path
    input_path = Path(url_or_path)
    is_url = url_or_path.startswith(("http://", "https://", "arxiv:"))

    if is_url:
        console.print(
            "[yellow]URL download not yet implemented. Please provide a local PDF.[/yellow]"
        )
        console.print("[dim]Use: arxiv2rm convert paper.pdf[/dim]")
        sys.exit(1)

    if not input_path.exists():
        console.print(f"[red]Error:[/red] File not found: {url_or_path}")
        sys.exit(1)

    if not input_path.suffix.lower() == ".pdf":
        console.print(f"[yellow]Warning:[/yellow] Expected PDF file, got {input_path.suffix}")

    # Determine output path
    output_path = Path(output) if output else input_path.with_suffix(".epub")

    console.print(f"[bold blue]Converting:[/bold blue] {input_path.name}")
    console.print(f"[dim]Output: {output_path}[/dim]")
    console.print(f"[dim]OCR Engine: {ocr_engine}[/dim]")
    console.print(f"[dim]Image Quality: {image_quality}[/dim]")
    console.print(f"[dim]Column Detection: {'enabled' if columns else 'disabled'}[/dim]")

    # Configure conversion options
    options = ConversionOptions(
        output_path=output_path,
        title=title,
        authors=list(author) if author else None,
        optimize_images=True,
        image_quality=image_quality,
        device=RemarkableDevice.REMARKABLE_1,
        detect_columns=columns,
        ocr_engine=ocr_engine,
        include_title_page=True,
    )

    # Run conversion
    converter = PDFToEPUBConverter(options)

    with Progress(console=console, transient=True) as progress:
        task = progress.add_task("[cyan]Converting PDF to EPUB...", total=100)

        # Step 1: Analysis
        progress.update(task, description="[cyan]Analyzing PDF...", advance=10)
        result = converter.convert(input_path, output_path)
        progress.update(task, advance=90)

    if result.success:
        console.print("\n[bold green]Conversion successful![/bold green]")
        console.print(f"[green]Output:[/green] {result.epub_path}")

        # Show stats
        stats = result.stats
        table = Table(title="Conversion Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Pages", str(stats.get("pages", "N/A")))
        table.add_row("Images", str(stats.get("images", "N/A")))
        table.add_row("Optimized Images", str(stats.get("optimized_images", "N/A")))
        table.add_row("Chapters", str(stats.get("chapters", "N/A")))
        table.add_row("Two-Column Layout", "Yes" if stats.get("is_two_column") else "No")
        table.add_row("OCR Required", "Yes" if stats.get("needs_ocr") else "No")
        table.add_row(
            "Input Size",
            f"{stats.get('input_size_kb', 0):.1f} KB",
        )
        table.add_row(
            "Output Size",
            f"{stats.get('output_size_kb', 0):.1f} KB",
        )

        console.print(table)

        # Upload to reMarkable if requested
        if upload:
            console.print("\n[yellow]reMarkable upload not yet implemented.[/yellow]")
    else:
        console.print("\n[bold red]Conversion failed![/bold red]")
        console.print(f"[red]Error:[/red] {result.error}")
        sys.exit(1)


@main.command()
@click.argument("batch_file", type=click.Path(exists=True))
@click.option("--parallel", default=1, type=int, help="Parallel conversions")
@click.pass_context
def batch(ctx, batch_file, parallel):
    """Convert multiple papers from a batch file.

    \b
    Example:
        arxiv2rm batch papers.txt --parallel 3

    Batch file format (one URL or path per line):
        https://arxiv.org/abs/2301.12345
        https://arxiv.org/abs/2302.67890
        /path/to/paper.pdf
    """
    logger = logging.getLogger(__name__)

    console.print(f"[bold blue]Processing batch file:[/bold blue] {batch_file}")
    console.print(f"[dim]Parallel conversions: {parallel}[/dim]")

    # Read batch file
    try:
        with open(batch_file) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        console.print(f"[green]Found {len(urls)} papers to convert[/green]")

        with Progress(console=console) as progress:
            task = progress.add_task("[cyan]Processing batch...", total=len(urls))
            for url in urls:
                logger.info(f"Would process: {url}")
                progress.update(task, advance=1)

        console.print("[yellow]Batch processing not yet implemented.[/yellow]")
    except Exception as e:
        logger.error(f"Failed to process batch file: {e}")
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command("config")
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--init", is_flag=True, help="Create default config file")
@click.option("--path", is_flag=True, help="Show config file path")
@click.pass_context
def config_cmd(ctx, show, init, path):
    """Manage configuration settings.

    \b
    Examples:
        arxiv2rm config --show      # Display current config
        arxiv2rm config --init      # Create default config file
        arxiv2rm config --path      # Show config file location
    """
    logger = logging.getLogger(__name__)

    if init:
        # Create default config file
        try:
            loader = ConfigLoader()
            config_path = loader.create_default_config(force=False)
            console.print(f"[green]Created default configuration file:[/green] {config_path}")
            console.print("\n[dim]Edit this file to customize settings[/dim]")
        except FileExistsError:
            console.print("[yellow]Config file already exists.[/yellow]")
            console.print(f"[dim]Location: {ConfigLoader.DEFAULT_CONFIG_PATH}[/dim]")
            console.print("[dim]Use --show to view current configuration[/dim]")
        except Exception as e:
            logger.error(f"Failed to create config: {e}")
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)

    elif path:
        # Show config file path
        config_path = ConfigLoader.DEFAULT_CONFIG_PATH
        console.print(f"[blue]Configuration file:[/blue] {config_path}")
        if config_path.exists():
            console.print("[green]✓ File exists[/green]")
        else:
            console.print("[yellow]✗ File does not exist (using defaults)[/yellow]")
            console.print("[dim]Run 'arxiv2rm config --init' to create it[/dim]")

    elif show:
        # Show current configuration
        config = ctx.obj.get("config")
        if config:
            console.print("[bold blue]Current Configuration:[/bold blue]\n")

            # Output section
            console.print("[cyan]Output:[/cyan]")
            console.print(f"  Format: {config.output.format}")
            console.print(f"  Directory: {config.output.directory}")

            # Typography section
            console.print("\n[cyan]Typography:[/cyan]")
            console.print(f"  Font: {config.typography.font_family}")
            console.print(f"  Size: {config.typography.default_font_size}")
            console.print(f"  Line height: {config.typography.line_height}")

            # Images section
            console.print("\n[cyan]Images:[/cyan]")
            console.print(f"  Max dimensions: {config.images.max_width}×{config.images.max_height}")
            console.print(f"  Quality: {config.images.quality}")
            console.print(f"  E-ink optimization: {config.images.optimize_for_eink}")

            # OCR section
            console.print("\n[cyan]OCR:[/cyan]")
            console.print(f"  Engine: {config.ocr.engine}")
            console.print(f"  Fallback: {config.ocr.fallback}")
            console.print(f"  Cache enabled: {config.ocr.cache_enabled}")

            # reMarkable section
            console.print("\n[cyan]reMarkable:[/cyan]")
            console.print(f"  Method: {config.remarkable.method}")
            console.print(f"  Default folder: {config.remarkable.default_folder}")
            console.print(f"  Auto upload: {config.remarkable.auto_upload}")

            # Logging section
            console.print("\n[cyan]Logging:[/cyan]")
            console.print(f"  Level: {config.logging.level}")
            console.print(f"  File: {config.logging.file}")
        else:
            console.print("[yellow]No configuration loaded (using defaults)[/yellow]")
            console.print("[dim]Run 'arxiv2rm config --init' to create a config file[/dim]")

    else:
        console.print("[yellow]Use one of the following options:[/yellow]")
        console.print("  --show    Show current configuration")
        console.print("  --init    Create default config file")
        console.print("  --path    Show config file path")


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("--columns/--no-columns", default=True, help="Enable column detection")
@click.option("--output", "-o", type=click.Path(), help="Save analysis to JSON file")
@click.option("--preview", is_flag=True, help="Show text preview of first page")
@click.pass_context
def analyze(ctx, pdf_path, columns, output, preview):
    """Analyze a PDF document structure.

    Detects column layout, text/image ratio, and OCR requirements.

    \b
    Examples:
        arxiv2rm analyze paper.pdf
        arxiv2rm analyze paper.pdf --preview
        arxiv2rm analyze paper.pdf --output analysis.json
        arxiv2rm analyze paper.pdf --no-columns
    """
    import json

    from arxiv2rm.column_detector import ColumnAwareExtractor
    from arxiv2rm.pdf_parser import PDFParser

    logger = logging.getLogger(__name__)
    pdf_path = Path(pdf_path)

    console.print(f"[bold blue]Analyzing:[/bold blue] {pdf_path.name}")

    try:
        # Initialize parser with column detection
        parser = PDFParser(detect_columns=columns)

        with Progress(console=console) as progress:
            task = progress.add_task("[cyan]Analyzing PDF...", total=100)

            # Step 1: Basic analysis
            progress.update(task, description="[cyan]Analyzing PDF structure...")
            analysis = parser.analyze_pdf(pdf_path)
            progress.update(task, advance=50)

            # Step 2: Column-aware extraction (if enabled and has text)
            if columns and not analysis["needs_ocr"]:
                progress.update(task, description="[cyan]Detecting columns...")
                extractor = ColumnAwareExtractor()
                doc_analysis = extractor.analyze_document(pdf_path)
                analysis["column_analysis"] = doc_analysis
            progress.update(task, advance=50)

        # Display results
        console.print("\n[bold green]Analysis Complete[/bold green]\n")

        # Basic stats table
        table = Table(title="Document Structure")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Pages", str(analysis["page_count"]))
        table.add_row("Pages with text", str(analysis["pages_with_text"]))
        table.add_row("Images", str(analysis["image_count"]))
        table.add_row("Text ratio", f"{analysis['text_ratio']:.1%}")
        table.add_row("Is scanned", "Yes" if analysis["is_scanned"] else "No")
        table.add_row("Needs OCR", "Yes" if analysis["needs_ocr"] else "No")

        console.print(table)

        # Column layout table (if available)
        if "column_layout" in analysis:
            col_info = analysis["column_layout"]

            console.print()
            col_table = Table(title="Column Layout")
            col_table.add_column("Property", style="cyan")
            col_table.add_column("Value", style="white")

            col_table.add_row("Dominant layout", f"{col_info['dominant_columns']} column(s)")
            col_table.add_row("Two-column pages", str(col_info["two_column_pages"]))
            col_table.add_row("Is two-column", "Yes" if col_info["is_two_column"] else "No")
            col_table.add_row("Mixed layout", "Yes" if col_info["mixed_layout"] else "No")

            # Distribution
            dist_str = ", ".join(
                f"{count}-col: {num}" for count, num in sorted(col_info["distribution"].items())
            )
            col_table.add_row("Distribution", dist_str)

            console.print(col_table)

        # First page special (if available)
        if "column_analysis" in analysis:
            col_analysis = analysis["column_analysis"]
            if col_analysis.get("first_page_special"):
                console.print(
                    "\n[dim]Note: First page has different layout (likely title page)[/dim]"
                )

        # Preview first page text
        if preview and not analysis["needs_ocr"]:
            console.print("\n[bold cyan]First Page Preview:[/bold cyan]")
            console.print("[dim]─" * 60 + "[/dim]")

            if columns:
                extractor = ColumnAwareExtractor()
                pages = extractor.extract_text(pdf_path)
                if pages:
                    preview_text = pages[0]["text"][:800]
                    console.print(preview_text)
                    if len(pages[0]["text"]) > 800:
                        console.print("[dim]... (truncated)[/dim]")
            else:
                pages = parser.extract_text_pdfplumber(pdf_path)
                if pages:
                    preview_text = pages[0]["text"][:800]
                    console.print(preview_text)
                    if len(pages[0]["text"]) > 800:
                        console.print("[dim]... (truncated)[/dim]")

            console.print("[dim]─" * 60 + "[/dim]")

        # Save to JSON if requested
        if output:
            output_path = Path(output)
            # Convert any non-serializable objects
            serializable = {
                k: v
                for k, v in analysis.items()
                if isinstance(v, (str, int, float, bool, dict, list, type(None)))
            }
            with open(output_path, "w") as f:
                json.dump(serializable, f, indent=2)
            console.print(f"\n[green]Analysis saved to:[/green] {output_path}")

        # Recommendations
        console.print("\n[bold cyan]Recommendations:[/bold cyan]")
        if analysis["needs_ocr"]:
            console.print("  • OCR required for this document")
            console.print("  • Use: arxiv2rm convert paper.pdf --ocr-engine groq")
        elif analysis.get("column_layout", {}).get("is_two_column"):
            console.print("  • Two-column layout detected")
            console.print("  • Column-aware extraction will be used automatically")
        else:
            console.print("  • Single-column layout - standard extraction")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
