"""ArXiv URL download and conversion functionality."""

import logging
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

console = Console()

logger = logging.getLogger(__name__)


def download_and_convert_arxiv(
    url_or_id: str,
    output_path: Path | None = None,
    title: str | None = None,
    authors: list[str] | None = None,
    prefer_latex: bool = True,
) -> tuple[bool, Path | None, str | None]:
    """
    Download and convert an ArXiv paper.

    Args:
        url_or_id: ArXiv URL or paper ID
        output_path: Output path for converted PDF
        title: Document title override
        authors: List of authors override
        prefer_latex: Whether to prefer LaTeX source over PDF

    Returns:
        Tuple of (success, output_path, error_message)
    """
    from arxiv2rm.arxiv_client import ArxivClient
    from arxiv2rm.converter import convert_pdf
    from arxiv2rm.pdf_builder import convert_latex_to_remarkable

    try:
        # Initialize ArXiv client
        arxiv_client = ArxivClient()

        console.print(f"[bold blue]Downloading from ArXiv:[/bold blue] {url_or_id}")

        # Fetch paper metadata and source
        with Progress(console=console, transient=True) as progress:
            task = progress.add_task("[cyan]Fetching paper...", total=100)
            progress.update(task, advance=10)

            metadata, source_path = arxiv_client.fetch_paper(url_or_id, prefer_latex=prefer_latex)
            progress.update(task, advance=30)

            # Display paper information
            paper_title = title or metadata["title"]
            paper_authors = authors or metadata["authors"]

            console.print(f"[green]Found paper:[/green] {paper_title}")
            author_suffix = "..." if len(paper_authors) > 3 else ""
            console.print(f"[dim]Authors: {', '.join(paper_authors[:3])}{author_suffix}[/dim]")
            console.print(f"[dim]ArXiv ID: {metadata['paper_id']}[/dim]")
            console.print(f"[dim]Source type: {metadata['source_type']}[/dim]")

            progress.update(task, advance=20)

            # Handle LaTeX source conversion
            if metadata["source_type"] == "latex":
                latex_dir = Path(metadata["latex_dir"])
                main_tex_file = (
                    Path(metadata["main_tex_file"]) if metadata.get("main_tex_file") else None
                )

                # Find main tex file if not specified in metadata
                if not main_tex_file or not main_tex_file.exists():
                    main_tex_file = arxiv_client.find_main_tex_file(latex_dir)

                if not main_tex_file:
                    return False, None, "Could not find main .tex file in LaTeX source"

                console.print(f"[dim]LaTeX source: {latex_dir}[/dim]")
                console.print(f"[dim]Main file: {main_tex_file.name}[/dim]")

                progress.update(task, advance=40)

                # Determine output path
                if output_path is None:
                    # Generate filename from paper metadata
                    safe_title = sanitize_filename(paper_title)
                    arxiv_id = metadata["paper_id"]
                    output_path = (
                        Path.home() / "Downloads" / f"{safe_title}-{arxiv_id}_remarkable.pdf"
                    )
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                console.print(f"[dim]Converting to: {output_path}[/dim]")

                # Convert LaTeX to PDF
                result_path = convert_latex_to_remarkable(
                    latex_dir=latex_dir,
                    main_tex_file=main_tex_file,
                    output_path=output_path,
                    font_size=10,
                    title=paper_title,
                    authors=paper_authors,
                    render_tables_as_images=True,
                )

                progress.update(task, advance=30)

                console.print("\n[bold green]Conversion successful![/bold green]")
                console.print(f"[green]Output:[/green] {result_path}")

                return True, result_path, None

            else:
                # Handle PDF conversion
                pdf_path = Path(metadata["pdf_path"])
                console.print(f"[dim]PDF downloaded: {pdf_path}[/dim]")

                progress.update(task, advance=50)

                # Determine output path
                if output_path is None:
                    # Generate filename from paper metadata
                    safe_title = sanitize_filename(paper_title)
                    arxiv_id = metadata["paper_id"]
                    output_path = (
                        Path.home() / "Downloads" / f"{safe_title}-{arxiv_id}_remarkable.pdf"
                    )
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                console.print(f"[dim]Converting to: {output_path}[/dim]")

                # Convert PDF
                result = convert_pdf(
                    input_path=pdf_path,
                    output_path=output_path,
                    title=paper_title,
                    authors=paper_authors,
                    optimize_images=True,
                    detect_columns=True,
                )

                progress.update(task, advance=40)

                if result.success:
                    console.print("\n[bold green]Conversion successful![/bold green]")
                    console.print(f"[green]Output:[/green] {result.output_path}")
                    return True, result.output_path, None
                else:
                    return False, None, result.error

    except Exception as e:
        error_msg = f"Failed to download or convert ArXiv paper: {e}"
        logger.error(error_msg)
        return False, None, error_msg


def sanitize_filename(title: str, max_length: int = 80) -> str:
    """Sanitize title for use as filename."""
    if not title:
        return "output"

    import re

    filename = title.strip()
    filename = re.sub(r"[/:*?\"<>|\\]", "", filename)  # Remove illegal chars
    filename = re.sub(r"['\u2019\u2018]", "", filename)  # Remove quotes
    filename = re.sub(r"[\u2013\u2014]", "-", filename)  # Replace em/en dashes
    filename = re.sub(r"\s+", " ", filename)  # Collapse whitespace
    filename = filename.strip()
    filename = filename.replace(" ", "_")  # Replace spaces with underscores
    filename = re.sub(r"_+", "_", filename)  # Remove consecutive underscores

    if len(filename) > max_length:
        filename = filename[:max_length].rstrip("_")

    if not filename:
        filename = "output"

    return filename
