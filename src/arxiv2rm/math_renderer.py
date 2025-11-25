"""Math formula renderer for converting LaTeX math to images."""

import hashlib
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class MathFormula:
    """Represents a mathematical formula."""

    latex_code: str
    is_display: bool  # True for display equations, False for inline
    formula_id: str  # Unique identifier


class MathRenderer:
    """Render LaTeX math formulas to images optimized for reMarkable."""

    # LaTeX preamble for math rendering
    LATEX_PREAMBLE = r"""
\documentclass[12pt]{article}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{amsfonts}
\pagestyle{empty}
\begin{document}
"""

    LATEX_POSTAMBLE = r"""
\end{document}
"""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize math renderer.

        Args:
            cache_dir: Directory to cache rendered images (default: temp dir)
        """
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "arxiv2rm_math_cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Check if required tools are available
        self._check_dependencies()

        logger.info(f"MathRenderer initialized with cache: {self.cache_dir}")

    def _check_dependencies(self):
        """Check if required LaTeX tools are available."""
        required_tools = ["pdflatex", "convert"]

        for tool in required_tools:
            if not shutil.which(tool):
                logger.warning(
                    f"Tool '{tool}' not found. Math rendering may not work. "
                    f"Install TeX Live (for pdflatex) and ImageMagick (for convert)."
                )

    def render(self, formula: MathFormula, output_path: Path, dpi: int = 200) -> Optional[Path]:
        """
        Render LaTeX formula to PNG image.

        Args:
            formula: MathFormula object
            output_path: Path to save rendered image
            dpi: DPI for rendering (higher = better quality, default: 200)

        Returns:
            Path to rendered image or None if rendering fails
        """
        # Check cache first
        cache_key = self._get_cache_key(formula.latex_code, dpi)
        cached_path = self.cache_dir / f"{cache_key}.png"

        if cached_path.exists():
            logger.debug(f"Using cached math image: {cache_key}")
            # Copy from cache to output
            shutil.copy(cached_path, output_path)
            return output_path

        # Render formula
        logger.debug(f"Rendering math: {formula.latex_code[:50]}...")

        try:
            # Create temporary directory for LaTeX compilation
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                # Create .tex file
                tex_file = tmpdir_path / "formula.tex"
                tex_content = self._create_tex_document(formula.latex_code, formula.is_display)
                tex_file.write_text(tex_content, encoding="utf-8")

                # Compile with pdflatex
                pdf_file = tmpdir_path / "formula.pdf"
                result = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, tex_file],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode != 0 or not pdf_file.exists():
                    logger.error(f"pdflatex failed: {result.stderr}")
                    return None

                # Convert PDF to PNG with ImageMagick
                png_file = tmpdir_path / "formula.png"
                result = subprocess.run(
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
                        "-trim",
                        "+repage",
                        str(pdf_file),
                        str(png_file),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode != 0 or not png_file.exists():
                    logger.error(f"ImageMagick convert failed: {result.stderr}")
                    return None

                # Optimize for reMarkable (grayscale, high contrast)
                self._optimize_for_remarkable(png_file, output_path)

                # Cache the result
                shutil.copy(output_path, cached_path)

                logger.debug(f"Rendered math to: {output_path}")
                return output_path

        except subprocess.TimeoutExpired:
            logger.error("LaTeX compilation timed out")
            return None
        except Exception as e:
            logger.error(f"Math rendering failed: {e}")
            return None

    def _create_tex_document(self, latex_code: str, is_display: bool) -> str:
        """
        Create complete LaTeX document for rendering.

        Args:
            latex_code: LaTeX formula code
            is_display: Whether this is display math (centered) or inline

        Returns:
            Complete LaTeX document as string
        """
        if is_display:
            # Display math - use equation* or align* environment
            if not latex_code.strip().startswith("\\begin{"):
                # Wrap in displaymath if not already in environment
                math_content = f"\\[{latex_code}\\]"
            else:
                math_content = latex_code
        else:
            # Inline math
            if not latex_code.startswith("$"):
                math_content = f"${latex_code}$"
            else:
                math_content = latex_code

        return self.LATEX_PREAMBLE + math_content + self.LATEX_POSTAMBLE

    def _optimize_for_remarkable(self, input_path: Path, output_path: Path):
        """
        Optimize image for reMarkable display (grayscale, high contrast).

        Args:
            input_path: Input PNG path
            output_path: Output PNG path
        """
        try:
            img = Image.open(input_path)

            # Convert to grayscale
            img = img.convert("L")

            # Enhance contrast for e-ink display
            from PIL import ImageEnhance

            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.3)  # Increase contrast by 30%

            # Save optimized image
            img.save(output_path, "PNG", optimize=True)

            logger.debug(f"Optimized math image for reMarkable: {output_path}")

        except Exception as e:
            logger.warning(f"Failed to optimize image, using original: {e}")
            shutil.copy(input_path, output_path)

    def _get_cache_key(self, latex_code: str, dpi: int) -> str:
        """
        Generate cache key for formula.

        Args:
            latex_code: LaTeX formula code
            dpi: DPI setting

        Returns:
            Cache key (hash of content + settings)
        """
        content = f"{latex_code}|{dpi}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def clear_cache(self):
        """Clear all cached rendered formulas."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Math rendering cache cleared")
