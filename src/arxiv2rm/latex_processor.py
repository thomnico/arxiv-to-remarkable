"""LaTeX source processor for extracting text and figures."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from TexSoup import TexSoup
from TexSoup.data import TexNode

logger = logging.getLogger(__name__)


@dataclass
class Figure:
    """Represents a figure in a LaTeX document."""

    number: int
    label: Optional[str] = None
    caption: Optional[str] = None
    image_path: Optional[str] = None
    source_file: Optional[Path] = None
    line_number: Optional[int] = None


@dataclass
class Section:
    """Represents a section/subsection in a LaTeX document."""

    level: int  # 1=section, 2=subsection, 3=subsubsection
    title: str
    number: Optional[str] = None
    content: str = ""


@dataclass
class LaTeXDocument:
    """Parsed LaTeX document with extracted content."""

    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    abstract: Optional[str] = None
    sections: List[Section] = field(default_factory=list)
    figures: List[Figure] = field(default_factory=list)
    references: Dict[str, int] = field(default_factory=dict)  # label -> figure number
    image_files: Set[Path] = field(default_factory=set)
    main_file: Optional[Path] = None
    included_files: List[Path] = field(default_factory=list)


class LaTeXProcessor:
    """Process LaTeX source files to extract text and figures."""

    # Image extensions to look for
    IMAGE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".eps", ".ps"}

    # Common LaTeX include paths
    FIGURE_DIRS = ["figures", "fig", "images", "imgs", "graphics", "."]

    def __init__(self, latex_dir: Path, main_tex_file: Path):
        """
        Initialize LaTeX processor.

        Args:
            latex_dir: Directory containing LaTeX source files
            main_tex_file: Path to main .tex file
        """
        self.latex_dir = latex_dir
        self.main_tex_file = main_tex_file
        self.figure_counter = 0
        logger.info(f"LaTeX processor initialized: {main_tex_file}")

    def process(self) -> LaTeXDocument:
        """
        Process LaTeX document and extract all content.

        Returns:
            LaTeXDocument with extracted text, figures, and metadata
        """
        logger.info("Processing LaTeX document...")

        doc = LaTeXDocument(main_file=self.main_tex_file)

        # Parse main file
        main_soup = self._parse_file(self.main_tex_file)

        # Extract metadata
        doc.title = self._extract_title(main_soup)
        doc.authors = self._extract_authors(main_soup)
        doc.abstract = self._extract_abstract(main_soup)

        # Extract content recursively (handles \input and \include)
        self._extract_content(main_soup, doc, self.main_tex_file)

        # Build reference map
        doc.references = self._build_reference_map(doc.figures)

        # Find all image files
        doc.image_files = self._find_image_files(doc.figures)

        logger.info(
            f"Processed: {len(doc.sections)} sections, "
            f"{len(doc.figures)} figures, "
            f"{len(doc.image_files)} images"
        )

        return doc

    def _parse_file(self, tex_file: Path) -> TexNode:
        """
        Parse a .tex file using TexSoup.

        Args:
            tex_file: Path to .tex file

        Returns:
            TexSoup parsed tree
        """
        try:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
            # Remove comments
            content = re.sub(r"(?<!\\)%.*$", "", content, flags=re.MULTILINE)
            soup = TexSoup(content)
            logger.debug(f"Parsed {tex_file}")
            return soup
        except Exception as e:
            logger.error(f"Failed to parse {tex_file}: {e}")
            raise ValueError(f"Failed to parse LaTeX file: {e}") from e

    def _extract_title(self, soup: TexNode) -> Optional[str]:
        """Extract document title."""
        try:
            title_node = soup.find("title")
            if title_node:
                title = self._node_to_text(title_node)
                logger.info(f"Extracted title: {title[:50]}...")
                return title
        except Exception as e:
            logger.warning(f"Could not extract title: {e}")
        return None

    def _extract_authors(self, soup: TexNode) -> List[str]:
        """Extract document authors."""
        authors = []
        try:
            author_node = soup.find("author")
            if author_node:
                author_text = self._node_to_text(author_node)
                # Split by common delimiters (including \and)
                authors = re.split(r"\\and\s+|\s+and\s+|,\s*|\n", author_text)
                authors = [a.strip() for a in authors if a.strip()]
                logger.info(f"Extracted {len(authors)} authors")
        except Exception as e:
            logger.warning(f"Could not extract authors: {e}")
        return authors

    def _extract_abstract(self, soup: TexNode) -> Optional[str]:
        """Extract document abstract."""
        try:
            abstract_node = soup.find("abstract")
            if abstract_node:
                abstract = self._node_to_text(abstract_node)
                logger.info(f"Extracted abstract: {len(abstract)} chars")
                return abstract
        except Exception as e:
            logger.warning(f"Could not extract abstract: {e}")
        return None

    def _extract_content(self, soup: TexNode, doc: LaTeXDocument, current_file: Path):
        r"""
        Extract content (sections, figures) from LaTeX tree.

        Recursively processes \input and \include commands.
        """
        # Extract sections
        for level, tag in [(1, "section"), (2, "subsection"), (3, "subsubsection")]:
            for section_node in soup.find_all(tag):
                try:
                    title = self._node_to_text(section_node.args[0])
                    content = self._extract_section_content(section_node)
                    section = Section(level=level, title=title, content=content)
                    doc.sections.append(section)
                    logger.debug(f"Extracted {tag}: {title[:30]}...")
                except Exception as e:
                    logger.warning(f"Failed to extract {tag}: {e}")

        # Extract figures
        for figure_node in soup.find_all("figure"):
            try:
                figure = self._extract_figure(figure_node, current_file)
                if figure:
                    doc.figures.append(figure)
            except Exception as e:
                logger.warning(f"Failed to extract figure: {e}")

        # Handle \input and \include - recursively extract sections and figures
        for input_cmd in soup.find_all("input"):
            try:
                input_file = self._resolve_input_file(input_cmd, current_file)
                if input_file and input_file.exists():
                    logger.debug(f"Processing \\input: {input_file}")
                    doc.included_files.append(input_file)

                    # Parse the input file
                    input_soup = self._parse_file(input_file)

                    # Recursively extract sections and figures from input file
                    self._extract_content(input_soup, doc, input_file)

                    # Also extract raw content for the most recent section if no sections found
                    # This handles input files that are just paragraph text
                    if not any(
                        input_soup.find_all(tag)
                        for tag in ["section", "subsection", "subsubsection"]
                    ):
                        try:
                            clean_content = self._node_to_text(input_soup)
                            if doc.sections and clean_content.strip():
                                # Append to the last section's content
                                doc.sections[-1].content += "\n\n" + clean_content
                                logger.debug(
                                    f"Added {len(clean_content)} chars to {doc.sections[-1].title}"
                                )
                        except Exception as parse_error:
                            logger.warning(
                                f"Failed to extract text from {input_file}: {parse_error}"
                            )
            except Exception as e:
                logger.warning(f"Failed to process \\input: {e}")

        for include_cmd in soup.find_all("include"):
            try:
                include_file = self._resolve_input_file(include_cmd, current_file)
                if include_file and include_file.exists():
                    logger.debug(f"Processing \\include: {include_file}")
                    doc.included_files.append(include_file)

                    # Parse the include file
                    include_soup = self._parse_file(include_file)

                    # Recursively extract sections and figures from include file
                    self._extract_content(include_soup, doc, include_file)

                    # Also extract raw content for the most recent section if no sections found
                    if not any(
                        include_soup.find_all(tag)
                        for tag in ["section", "subsection", "subsubsection"]
                    ):
                        try:
                            clean_content = self._node_to_text(include_soup)
                            if doc.sections and clean_content.strip():
                                doc.sections[-1].content += "\n\n" + clean_content
                        except Exception as parse_error:
                            logger.warning(
                                f"Failed to extract text from {include_file}: {parse_error}"
                            )
            except Exception as e:
                logger.warning(f"Failed to process \\include: {e}")

    def _extract_figure(self, figure_node: TexNode, source_file: Path) -> Optional[Figure]:
        """
        Extract figure information from figure environment.

        Args:
            figure_node: TexSoup figure node
            source_file: Source .tex file

        Returns:
            Figure object or None if extraction fails
        """
        self.figure_counter += 1
        figure = Figure(number=self.figure_counter, source_file=source_file)

        # Extract \includegraphics
        try:
            for graphics in figure_node.find_all("includegraphics"):
                if graphics.args:
                    # Get image path from last argument (required argument)
                    image_arg = str(graphics.args[-1])
                    figure.image_path = image_arg.strip("{}")
                    logger.debug(f"Found image: {figure.image_path}")
                    break
        except Exception as e:
            logger.warning(f"Failed to extract \\includegraphics: {e}")

        # Extract \caption
        try:
            caption_node = figure_node.find("caption")
            if caption_node:
                figure.caption = self._node_to_text(caption_node)
                logger.debug(f"Caption: {figure.caption[:50]}...")
        except Exception as e:
            logger.warning(f"Failed to extract caption: {e}")

        # Extract \label
        try:
            label_node = figure_node.find("label")
            if label_node and label_node.args:
                figure.label = str(label_node.args[0]).strip("{}")
                logger.debug(f"Label: {figure.label}")
        except Exception as e:
            logger.warning(f"Failed to extract label: {e}")

        return figure if figure.image_path else None

    def _extract_section_content(self, section_node: TexNode) -> str:
        r"""
        Extract text content from a section.

        Note: This extracts content directly from the section node.
        Content from \input files is handled separately.
        """
        try:
            # Try to get text content from the section node
            # TexSoup doesn't directly give us paragraph content, so we extract from string
            section_str = str(section_node)

            # Remove the \section{title} part to get just content
            section_str = re.sub(r"^\\[a-z]+\{[^}]+\}", "", section_str, count=1)

            # Clean up the content
            content = self._node_to_text(TexSoup(section_str))

            return content
        except Exception as e:
            logger.warning(f"Failed to extract section content: {e}")
            return ""

    def _node_to_text(self, node: TexNode) -> str:
        """
        Convert TexSoup node to plain text.

        Args:
            node: TexSoup node

        Returns:
            Plain text with LaTeX commands removed
        """
        # Convert to string
        if hasattr(node, "args") and node.args:
            # Extract first argument content for commands like \title{...}
            text = str(node.args[0])
        else:
            text = str(node)

        # Remove braces
        text = re.sub(r"^\{+|\}+$", "", text)

        # Remove environment markers (TexSoup converts \begin{X} to \beginX)
        text = re.sub(r"\\begin[a-zA-Z]+", "", text)
        text = re.sub(r"\\end[a-zA-Z]+", "", text)

        # Remove common LaTeX commands with their braces
        text = re.sub(r"\\textbf\{([^}]+)\}", r"\1", text)
        text = re.sub(r"\\textit\{([^}]+)\}", r"\1", text)
        text = re.sub(r"\\emph\{([^}]+)\}", r"\1", text)
        text = re.sub(r"\\cite[a-z]*\{[^}]+\}", "", text)  # \cite, \citep, \citet
        text = re.sub(r"\\ref\{[^}]+\}", "", text)
        text = re.sub(r"\\label\{[^}]+\}", "", text)
        text = re.sub(r"\\thanks\{[^}]+\}", "", text)  # Remove footnotes

        # Remove author separators
        text = re.sub(r"\\AND\s+", ", ", text)
        text = re.sub(r"\\and\s+", ", ", text)

        # Remove remaining common commands
        text = re.sub(r"\\[a-zA-Z]+\*?\s*", " ", text)  # \command or \command*

        # Remove remaining braces
        text = re.sub(r"[\{\}]", "", text)

        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _resolve_input_file(self, input_node: TexNode, current_file: Path) -> Optional[Path]:
        r"""
        Resolve path to \input or \include file.

        Args:
            input_node: TexSoup input/include node
            current_file: Current .tex file being processed

        Returns:
            Resolved file path or None
        """
        if not input_node.args:
            return None

        input_path = str(input_node.args[0]).strip("{}")

        # Add .tex extension if missing
        if not input_path.endswith(".tex"):
            input_path += ".tex"

        # Try relative to current file
        candidate = current_file.parent / input_path
        if candidate.exists():
            return candidate

        # Try relative to latex_dir
        candidate = self.latex_dir / input_path
        if candidate.exists():
            return candidate

        logger.warning(f"Could not resolve input file: {input_path}")
        return None

    def _build_reference_map(self, figures: List[Figure]) -> Dict[str, int]:
        """
        Build mapping from figure labels to figure numbers.

        Args:
            figures: List of extracted figures

        Returns:
            Dict mapping label -> figure number
        """
        ref_map = {}
        for fig in figures:
            if fig.label:
                ref_map[fig.label] = fig.number
                logger.debug(f"Reference: {fig.label} -> Figure {fig.number}")
        return ref_map

    def _find_image_files(self, figures: List[Figure]) -> Set[Path]:
        """
        Find actual image files referenced in figures.

        Args:
            figures: List of extracted figures

        Returns:
            Set of paths to existing image files
        """
        image_files = set()

        for fig in figures:
            if not fig.image_path:
                continue

            # Try to find the actual file
            found_path = self._resolve_image_path(fig.image_path)
            if found_path:
                image_files.add(found_path)
                logger.debug(f"Found image file: {found_path}")
            else:
                logger.warning(f"Image file not found: {fig.image_path}")

        return image_files

    def _resolve_image_path(self, image_path: str) -> Optional[Path]:
        r"""
        Resolve image path to actual file.

        Tries multiple extensions and common directories.

        Args:
            image_path: Image path from \includegraphics (may be without extension)

        Returns:
            Resolved path or None
        """
        # Remove leading/trailing whitespace
        image_path = image_path.strip()

        # Try as-is if it has an extension
        if any(image_path.lower().endswith(ext) for ext in self.IMAGE_EXTENSIONS):
            candidate = self.latex_dir / image_path
            if candidate.exists():
                return candidate

        # Try adding extensions
        base_path = image_path
        for ext in self.IMAGE_EXTENSIONS:
            # Try in common directories
            for fig_dir in self.FIGURE_DIRS:
                if fig_dir == ".":
                    candidate = self.latex_dir / (base_path + ext)
                else:
                    candidate = self.latex_dir / fig_dir / (base_path + ext)

                if candidate.exists():
                    return candidate

        return None


def process_latex_source(latex_dir: Path, main_tex_file: Path) -> LaTeXDocument:
    """
    Convenience function to process LaTeX source.

    Args:
        latex_dir: Directory containing LaTeX source
        main_tex_file: Path to main .tex file

    Returns:
        LaTeXDocument with extracted content
    """
    processor = LaTeXProcessor(latex_dir, main_tex_file)
    return processor.process()
