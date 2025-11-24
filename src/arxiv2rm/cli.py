"""Command-line interface for arxiv2rm."""

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress

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
@click.option("--format", default="epub", help="Output format (epub)")
@click.option("--ocr-engine", help="OCR engine (groq, tesseract)")
@click.option("--image-quality", type=int, help="JPEG quality (1-100)")
@click.option("--remarkable-folder", help="reMarkable folder")
@click.option("--upload/--no-upload", default=None, help="Upload to reMarkable")
@click.pass_context
def convert(ctx, url_or_path, output, format, ocr_engine, image_quality, remarkable_folder, upload):
    """Convert a paper to EPUB format.

    \b
    Examples:
        arxiv2rm convert https://arxiv.org/abs/2301.12345
        arxiv2rm convert paper.pdf --output custom.epub
        arxiv2rm convert paper.pdf --upload
    """
    logger = logging.getLogger(__name__)
    config = ctx.obj.get("config")

    # Use config values as defaults if not specified
    if config:
        ocr_engine = ocr_engine or config.ocr.engine
        image_quality = image_quality or config.images.quality
        remarkable_folder = remarkable_folder or config.remarkable.default_folder
        if upload is None:
            upload = config.remarkable.auto_upload

    console.print(f"[bold blue]Converting:[/bold blue] {url_or_path}")
    console.print(f"[dim]Format: {format}[/dim]")
    console.print(f"[dim]OCR Engine: {ocr_engine}[/dim]")
    console.print(f"[dim]Image Quality: {image_quality}[/dim]")

    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Converting...", total=100)
        progress.update(task, advance=10)
        logger.info(f"Starting conversion of {url_or_path}")
        progress.update(task, advance=90)

    console.print("[yellow]This feature is not yet implemented.[/yellow]")
    logger.warning("Conversion feature not yet implemented")


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


if __name__ == "__main__":
    main()
