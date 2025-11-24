"""Command-line interface for arxiv2rm."""

import click

from arxiv2rm import __version__


@click.group()
@click.version_option(version=__version__)
@click.pass_context
def main(ctx):
    """ArXiv to reMarkable converter.

    Convert scientific papers to EPUB format optimized for reMarkable devices.
    """
    ctx.ensure_object(dict)


@main.command()
@click.argument("url_or_path")
@click.option("--output", "-o", help="Output file path")
@click.option("--format", default="epub", help="Output format (epub)")
@click.option("--ocr-engine", default="groq", help="OCR engine (groq, tesseract)")
@click.option("--image-quality", default=85, type=int, help="JPEG quality (1-100)")
@click.option("--remarkable-folder", default="Research", help="reMarkable folder")
def convert(url_or_path, output, format, ocr_engine, image_quality, remarkable_folder):
    """Convert a paper to EPUB format.

    \b
    Examples:
        arxiv2rm convert https://arxiv.org/abs/2301.12345
        arxiv2rm convert paper.pdf --output custom.epub
    """
    click.echo(f"Converting: {url_or_path}")
    click.echo(f"Format: {format}")
    click.echo("This feature is not yet implemented.")


@main.command()
@click.argument("batch_file", type=click.Path(exists=True))
@click.option("--parallel", default=1, type=int, help="Parallel conversions")
def batch(batch_file, parallel):
    """Convert multiple papers from a batch file.

    \b
    Example:
        arxiv2rm batch papers.txt --parallel 3
    """
    click.echo(f"Processing batch file: {batch_file}")
    click.echo("This feature is not yet implemented.")


@main.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--set", "set_value", nargs=2, metavar="KEY VALUE", help="Set config value")
def config(key, value, show, set_value):
    """Manage configuration settings.

    \b
    Examples:
        arxiv2rm config --show
        arxiv2rm config --set ocr-engine groq
    """
    if show:
        click.echo("Current configuration:")
        click.echo("  (No configuration file found)")
    elif set_value:
        key, value = set_value
        click.echo(f"Setting {key} = {value}")
        click.echo("This feature is not yet implemented.")
    else:
        click.echo("Use --show to view configuration or --set KEY VALUE to change settings")


if __name__ == "__main__":
    main()
