"""Table renderer for converting LaTeX tables to images."""

import hashlib
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image

from arxiv2rm.latex_processor import Table

logger = logging.getLogger(__name__)


class TableRenderer:
    """Render LaTeX tables to images optimized for reMarkable."""

    # LaTeX preamble for table rendering
    LATEX_PREAMBLE = r"""
\documentclass[12pt]{article}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{amsfonts}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{array}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{colortbl}
\usepackage{float}
\usepackage[margin=0.5in]{geometry}
% Define custom commands used in papers
\newcommand{\dmodel}{d_{\text{model}}}
\newcommand{\dff}{d_{\text{ff}}}
\newcommand{\specialrule}[3]{\toprule}
% Dummy cite command
\newcommand{\citep}[1]{}
\newcommand{\citet}[1]{}
\pagestyle{empty}
\begin{document}
"""

    LATEX_POSTAMBLE = r"""
\end{document}
"""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize table renderer.

        Args:
            cache_dir: Directory to cache rendered images (default: temp dir)
        """
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "arxiv2rm_table_cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Check if required tools are available
        self._check_dependencies()

        logger.info(f"TableRenderer initialized with cache: {self.cache_dir}")

    def _check_dependencies(self):
        """Check if required LaTeX tools are available."""
        required_tools = ["pdflatex", "convert"]

        for tool in required_tools:
            if not shutil.which(tool):
                logger.warning(
                    f"Tool '{tool}' not found. Table rendering may not work. "
                    f"Install TeX Live (for pdflatex) and ImageMagick (for convert)."
                )

    def render(
        self, table: Table, output_path: Path, dpi: int = 150, max_width: int = 1404
    ) -> Optional[Path]:
        """
        Render LaTeX table to PNG image.

        Args:
            table: Table object with LaTeX content
            output_path: Path to save rendered image
            dpi: DPI for rendering (default: 150 for tables)
            max_width: Maximum width in pixels for reMarkable (default: 1404)

        Returns:
            Path to rendered image, or None if rendering failed
        """
        # Generate cache key from table content
        cache_key = hashlib.md5(table.content.encode()).hexdigest()
        cache_file = self.cache_dir / f"table_{cache_key}.png"

        # Return cached version if exists
        if cache_file.exists():
            logger.debug(f"Using cached table image: {cache_file}")
            if output_path != cache_file:
                shutil.copy(cache_file, output_path)
            return output_path

        # Create temporary directory for LaTeX compilation
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            tex_file = tmpdir_path / "table.tex"
            pdf_file = tmpdir_path / "table.pdf"

            # Write LaTeX document
            latex_content = self._build_latex_document(table.content)
            tex_file.write_text(latex_content, encoding="utf-8")

            try:
                # Compile LaTeX to PDF
                result = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "table.tex"],
                    cwd=tmpdir_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                # pdflatex may return non-zero even with warnings, check if PDF exists
                if not pdf_file.exists():
                    logger.error(f"pdflatex failed for table {table.number}: {result.stderr}")
                    return None
                if result.returncode != 0:
                    logger.debug(f"pdflatex warnings for table {table.number}")

                # Convert PDF to PNG using ImageMagick
                convert_result = subprocess.run(
                    [
                        "convert",
                        "-density",
                        str(dpi),
                        "-quality",
                        "100",
                        "-background",
                        "white",
                        "-alpha",
                        "remove",
                        str(pdf_file),
                        str(cache_file),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if convert_result.returncode != 0 or not cache_file.exists():
                    logger.error(
                        f"ImageMagick convert failed for table {table.number}: "
                        f"{convert_result.stderr}"
                    )
                    return None

                # Resize if too wide for reMarkable
                try:
                    img = Image.open(cache_file)
                    if img.width > max_width:
                        ratio = max_width / img.width
                        new_height = int(img.height * ratio)
                        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                        img.save(cache_file, "PNG", optimize=True)
                        logger.debug(
                            f"Resized table {table.number} from "
                            f"{img.width}x{img.height} to {max_width}x{new_height}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to resize table image: {e}")

                # Copy to output path if different
                if output_path != cache_file:
                    shutil.copy(cache_file, output_path)

                logger.info(f"Rendered table {table.number} to {output_path}")
                return output_path

            except subprocess.TimeoutExpired:
                logger.error(f"Timeout rendering table {table.number}")
                return None
            except Exception as e:
                logger.error(f"Error rendering table {table.number}: {e}")
                return None

    def _build_latex_document(self, table_content: str) -> str:
        """
        Build complete LaTeX document for table rendering.

        Args:
            table_content: Raw LaTeX table content (tabular environment)

        Returns:
            Complete LaTeX document as string
        """
        # Ensure table has begin/end if not present
        if "\\begin{tabular}" not in table_content:
            table_content = f"\\begin{{tabular}}{{c}}\n{table_content}\n\\end{{tabular}}"

        return self.LATEX_PREAMBLE + table_content + self.LATEX_POSTAMBLE

    def render_all(self, tables: list[Table], output_dir: Path, dpi: int = 150) -> dict[int, Path]:
        """
        Render all tables to images.

        Args:
            tables: List of Table objects
            output_dir: Directory to save rendered images
            dpi: DPI for rendering

        Returns:
            Dictionary mapping table number to rendered image path
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        rendered = {}

        for table in tables:
            output_path = output_dir / f"table_{table.number}.png"
            result = self.render(table, output_path, dpi=dpi)
            if result:
                rendered[table.number] = result
                table.image_path = result  # Update table with image path

        logger.info(f"Rendered {len(rendered)}/{len(tables)} tables to images")
        return rendered
