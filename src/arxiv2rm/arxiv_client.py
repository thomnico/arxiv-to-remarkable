"""ArXiv API client for fetching papers and LaTeX sources."""

import logging
import re
import tarfile
from pathlib import Path
from typing import Dict, Optional, Tuple

import arxiv
import requests

logger = logging.getLogger(__name__)


class ArxivURLParser:
    """Parse ArXiv URLs to extract paper IDs."""

    # ArXiv paper ID patterns
    # New format: YYMM.NNNNN or YYMM.NNNNNVN (with version)
    # Old format: arch-ive/YYMMNNN
    PATTERNS = [
        r"arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)",  # New format with optional version
        r"arxiv\.org/pdf/(\d{4}\.\d{4,5}(?:v\d+)?)",  # PDF URL
        r"arxiv\.org/abs/([a-z\-]+/\d{7})",  # Old format
        r"^(\d{4}\.\d{4,5}(?:v\d+)?)$",  # Direct ID (new)
        r"^([a-z\-]+/\d{7})$",  # Direct ID (old)
    ]

    @classmethod
    def parse(cls, url_or_id: str) -> Optional[str]:
        """
        Parse ArXiv URL or ID to extract paper ID.

        Args:
            url_or_id: ArXiv URL or paper ID

        Returns:
            Paper ID (e.g., "2301.12345" or "cs/0703123"), or None if invalid

        Examples:
            >>> ArxivURLParser.parse("https://arxiv.org/abs/2301.12345")
            '2301.12345'
            >>> ArxivURLParser.parse("2301.12345")
            '2301.12345'
            >>> ArxivURLParser.parse("https://arxiv.org/abs/2301.12345v2")
            '2301.12345v2'
        """
        url_or_id = url_or_id.strip()

        for pattern in cls.PATTERNS:
            match = re.search(pattern, url_or_id, re.IGNORECASE)
            if match:
                paper_id = match.group(1)
                logger.debug(f"Parsed ArXiv ID: {paper_id} from {url_or_id}")
                return paper_id

        logger.warning(f"Could not parse ArXiv ID from: {url_or_id}")
        return None

    @classmethod
    def strip_version(cls, paper_id: str) -> str:
        """
        Strip version suffix from paper ID.

        Args:
            paper_id: Paper ID possibly with version (e.g., "2301.12345v2")

        Returns:
            Paper ID without version (e.g., "2301.12345")
        """
        return re.sub(r"v\d+$", "", paper_id)


class ArxivClient:
    """Client for fetching papers from ArXiv with LaTeX source preference."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize ArXiv client.

        Args:
            cache_dir: Directory for caching downloads (default: ~/.arxiv2rm/cache/arxiv)
        """
        self.cache_dir = cache_dir or Path.home() / ".arxiv2rm" / "cache" / "arxiv"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ArXiv client initialized with cache dir: {self.cache_dir}")

    def fetch_metadata(self, paper_id: str) -> Dict:
        """
        Fetch paper metadata from ArXiv API.

        Args:
            paper_id: ArXiv paper ID (e.g., "2301.12345")

        Returns:
            Dict with metadata: title, authors, abstract, published, updated

        Raises:
            ValueError: If paper not found or API error
        """
        try:
            # Strip version for API query
            clean_id = ArxivURLParser.strip_version(paper_id)

            logger.info(f"Fetching metadata for ArXiv paper: {clean_id}")
            search = arxiv.Search(id_list=[clean_id])
            paper = next(search.results())

            metadata = {
                "paper_id": paper_id,
                "title": paper.title,
                "authors": [author.name for author in paper.authors],
                "abstract": paper.summary,
                "published": paper.published,
                "updated": paper.updated,
                "pdf_url": paper.pdf_url,
                "entry_id": paper.entry_id,
                "categories": paper.categories,
            }

            logger.info(f"Fetched metadata: {metadata['title']}")
            return metadata

        except StopIteration:
            raise ValueError(f"ArXiv paper not found: {paper_id}")
        except Exception as e:
            raise ValueError(f"Failed to fetch ArXiv metadata: {e}") from e

    def download_latex_source(self, paper_id: str, output_dir: Optional[Path] = None) -> Path:
        """
        Download LaTeX source (.tar.gz) for a paper.

        Args:
            paper_id: ArXiv paper ID
            output_dir: Directory to extract source (default: cache_dir/paper_id)

        Returns:
            Path to extracted source directory

        Raises:
            ValueError: If LaTeX source not available
        """
        clean_id = ArxivURLParser.strip_version(paper_id)
        output_dir = output_dir or self.cache_dir / clean_id / "latex"

        # Check cache first
        if output_dir.exists() and any(output_dir.glob("*.tex")):
            logger.info(f"Using cached LaTeX source: {output_dir}")
            return output_dir

        # Download LaTeX source
        source_url = f"https://arxiv.org/e-print/{clean_id}"
        logger.info(f"Downloading LaTeX source from: {source_url}")

        try:
            response = requests.get(source_url, timeout=30)
            response.raise_for_status()

            # Save .tar.gz
            tar_path = self.cache_dir / f"{clean_id}.tar.gz"
            tar_path.write_bytes(response.content)
            logger.info(f"Downloaded source to: {tar_path} ({len(response.content)} bytes)")

            # Extract
            output_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(output_dir)

            logger.info(f"Extracted LaTeX source to: {output_dir}")

            # Clean up tar file
            tar_path.unlink()

            return output_dir

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                raise ValueError(f"LaTeX source not available for {paper_id}") from e
            raise ValueError(f"Failed to download LaTeX source: {e}") from e
        except tarfile.TarError as e:
            raise ValueError(f"Failed to extract LaTeX source: {e}") from e

    def download_pdf(self, paper_id: str, output_path: Optional[Path] = None) -> Path:
        """
        Download PDF for a paper (fallback when LaTeX unavailable).

        Args:
            paper_id: ArXiv paper ID
            output_path: Path to save PDF (default: cache_dir/paper_id.pdf)

        Returns:
            Path to downloaded PDF

        Raises:
            ValueError: If download fails
        """
        clean_id = ArxivURLParser.strip_version(paper_id)
        output_path = output_path or self.cache_dir / f"{clean_id}.pdf"

        # Check cache
        if output_path.exists():
            logger.info(f"Using cached PDF: {output_path}")
            return output_path

        # Download PDF
        pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"
        logger.info(f"Downloading PDF from: {pdf_url}")

        try:
            response = requests.get(pdf_url, timeout=60)
            response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)

            logger.info(f"Downloaded PDF to: {output_path} ({len(response.content)} bytes)")
            return output_path

        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to download PDF: {e}") from e

    def find_main_tex_file(self, latex_dir: Path) -> Optional[Path]:
        r"""
        Identify the main .tex file in a LaTeX source directory.

        Looks for common patterns:
        - Files named main.tex, paper.tex, ms.tex, article.tex
        - Files containing \documentclass
        - Largest .tex file

        Args:
            latex_dir: Directory containing LaTeX source files

        Returns:
            Path to main .tex file, or None if not found
        """
        tex_files = list(latex_dir.glob("**/*.tex"))

        if not tex_files:
            logger.warning(f"No .tex files found in {latex_dir}")
            return None

        logger.info(f"Found {len(tex_files)} .tex files")

        # Check for common main file names
        common_names = ["main.tex", "paper.tex", "ms.tex", "article.tex", "manuscript.tex"]
        for name in common_names:
            for tex_file in tex_files:
                if tex_file.name.lower() == name:
                    logger.info(f"Found main file by name: {tex_file}")
                    return tex_file

        # Find files with \documentclass (indicates main document)
        doc_class_files = []
        for tex_file in tex_files:
            try:
                content = tex_file.read_text(encoding="utf-8", errors="ignore")
                if r"\documentclass" in content:
                    doc_class_files.append(tex_file)
            except Exception as e:
                logger.warning(f"Could not read {tex_file}: {e}")

        if len(doc_class_files) == 1:
            logger.info(f"Found main file by \\documentclass: {doc_class_files[0]}")
            return doc_class_files[0]
        elif len(doc_class_files) > 1:
            # Multiple candidates, choose largest
            main_file = max(doc_class_files, key=lambda f: f.stat().st_size)
            logger.info(f"Multiple \\documentclass files, choosing largest: {main_file}")
            return main_file

        # Fallback: largest .tex file
        main_file = max(tex_files, key=lambda f: f.stat().st_size)
        logger.info(f"Using largest .tex file as main: {main_file}")
        return main_file

    def fetch_paper(self, url_or_id: str, prefer_latex: bool = True) -> Tuple[Dict, Optional[Path]]:
        """
        Fetch a paper from ArXiv with LaTeX source preference.

        Args:
            url_or_id: ArXiv URL or paper ID
            prefer_latex: Try to download LaTeX source first (default: True)

        Returns:
            Tuple of (metadata dict, source path)
            - source path is Path to LaTeX dir if available, or PDF path if not

        Raises:
            ValueError: If paper not found or download fails
        """
        # Parse paper ID
        paper_id = ArxivURLParser.parse(url_or_id)
        if not paper_id:
            raise ValueError(f"Invalid ArXiv URL or ID: {url_or_id}")

        # Fetch metadata
        metadata = self.fetch_metadata(paper_id)

        # Try LaTeX source first
        source_path = None
        if prefer_latex:
            try:
                source_path = self.download_latex_source(paper_id)
                metadata["source_type"] = "latex"
                metadata["latex_dir"] = str(source_path)

                # Find main .tex file
                main_tex = self.find_main_tex_file(source_path)
                if main_tex:
                    metadata["main_tex_file"] = str(main_tex)

            except ValueError as e:
                logger.warning(f"LaTeX source unavailable: {e}")

        # Fallback to PDF
        if source_path is None:
            source_path = self.download_pdf(paper_id)
            metadata["source_type"] = "pdf"
            metadata["pdf_path"] = str(source_path)

        logger.info(f"Fetched paper: {metadata['title']} ({metadata['source_type']})")
        return metadata, source_path
