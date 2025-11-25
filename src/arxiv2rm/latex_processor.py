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
    source_section: Optional[str] = None  # Section title where figure appears


@dataclass
class Section:
    """Represents a section/subsection in a LaTeX document."""

    level: int  # 1=section, 2=subsection, 3=subsubsection
    title: str
    number: Optional[str] = None
    content: str = ""


@dataclass
class MathFormula:
    """Represents a mathematical formula in LaTeX."""

    formula_id: str
    latex_code: str
    is_display: bool  # True for display equations, False for inline
    line_number: Optional[int] = None


@dataclass
class Table:
    """Represents a table in a LaTeX document."""

    number: int
    label: Optional[str] = None
    caption: Optional[str] = None
    content: str = ""  # Raw LaTeX tabular content
    image_path: Optional[Path] = None  # Path to rendered table image
    source_file: Optional[Path] = None
    line_number: Optional[int] = None
    source_section: Optional[str] = None  # Section title where table appears


@dataclass
class LaTeXDocument:
    """Parsed LaTeX document with extracted content."""

    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    abstract: Optional[str] = None
    sections: List[Section] = field(default_factory=list)
    figures: List[Figure] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    math_formulas: List[MathFormula] = field(default_factory=list)
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
        self.table_counter = 0
        self.math_counter = 0
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

        # Extract math formulas from raw content
        self._extract_math_from_sections(doc)

        # Build reference map
        doc.references = self._build_reference_map(doc.figures)

        # Find all image files
        doc.image_files = self._find_image_files(doc.figures)

        logger.info(
            f"Processed: {len(doc.sections)} sections, "
            f"{len(doc.figures)} figures, "
            f"{len(doc.tables)} tables, "
            f"{len(doc.math_formulas)} math formulas, "
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

        Recursively processes \input and \include commands IN DOCUMENT ORDER.
        This maintains proper hierarchical structure.
        """
        # Build a map of figures to their surrounding section by parsing the raw text
        figures_section_map = self._map_figures_to_sections(soup, current_file)

        # Build a map of input commands to their preceding sections
        # This is critical for associating input file content with the right section
        input_section_map = self._map_inputs_to_sections(soup, current_file)

        # Process document in order to maintain section hierarchy
        # Strategy: Process sections one by one, and immediately process their \input files
        processed_inputs = set()

        # Extract level 1 sections in order
        for section_node in soup.find_all("section"):
            try:
                title = self._node_to_text(section_node.args[0])
                content = self._extract_section_content(section_node)
                section = Section(level=1, title=title, content=content)
                doc.sections.append(section)
                logger.debug(f"Extracted section: {title[:30]}...")

                # Immediately process input files that belong to this section
                for input_cmd in soup.find_all("input"):
                    if id(input_cmd) in processed_inputs:
                        continue

                    input_file = self._resolve_input_file(input_cmd, current_file)
                    if input_file and input_file.exists():
                        input_name = input_file.stem
                        mapped_section = input_section_map.get(input_name)

                        if mapped_section == title:
                            processed_inputs.add(id(input_cmd))
                            doc.included_files.append(input_file)
                            logger.debug(f"Processing \\input: {input_file} for section {title}")

                            # Parse and process the input file
                            input_soup = self._parse_file(input_file)

                            # Check if contains sections
                            has_sections = any(
                                input_soup.find_all(tag) for tag in ["subsection", "subsubsection"]
                            )

                            if has_sections:
                                # Extract subsections and add immediately after parent section
                                self._extract_subsections(input_soup, doc, input_file)
                            else:
                                # Plain content - add to current section
                                clean_content = self._node_to_text(input_soup)
                                if clean_content.strip():
                                    section.content += "\n\n" + clean_content
                                    logger.debug(f"Added {len(clean_content)} chars to {title}")

            except Exception as e:
                logger.warning(f"Failed to extract section: {e}")

        # Extract figures with section context from map
        for figure_node in soup.find_all("figure"):
            try:
                section_title = figures_section_map.get(id(figure_node))
                figure = self._extract_figure(figure_node, current_file, section_title)
                if figure:
                    doc.figures.append(figure)
            except Exception as e:
                logger.warning(f"Failed to extract figure: {e}")

        # Process any remaining unprocessed input files
        for input_cmd in soup.find_all("input"):
            if id(input_cmd) not in processed_inputs:
                try:
                    input_file = self._resolve_input_file(input_cmd, current_file)
                    if input_file and input_file.exists():
                        processed_inputs.add(id(input_cmd))
                        doc.included_files.append(input_file)
                        logger.debug(f"Processing remaining \\input: {input_file}")

                        input_soup = self._parse_file(input_file)
                        self._extract_subsections(input_soup, doc, input_file)
                except Exception as e:
                    logger.warning(f"Failed to process remaining input: {e}")

        for include_cmd in soup.find_all("include"):
            try:
                include_file = self._resolve_input_file(include_cmd, current_file)
                if include_file and include_file.exists():
                    logger.debug(f"Processing \\include: {include_file}")
                    doc.included_files.append(include_file)

                    # Parse the include file
                    include_soup = self._parse_file(include_file)

                    # Check if this include file contains sections
                    has_sections = any(
                        include_soup.find_all(tag)
                        for tag in ["section", "subsection", "subsubsection"]
                    )

                    if has_sections:
                        # Recursively extract sections and figures from include file
                        self._extract_content(include_soup, doc, include_file)
                    else:
                        # No sections - this is content for the most recent section
                        try:
                            clean_content = self._node_to_text(include_soup)
                            if doc.sections and clean_content.strip():
                                # Find the most recent level-1 section to append to
                                for section in reversed(doc.sections):
                                    if section.level == 1:
                                        section.content += "\n\n" + clean_content
                                        logger.debug(
                                            f"Added {len(clean_content)} chars to {section.title}"
                                        )
                                        break
                        except Exception as parse_error:
                            logger.warning(
                                f"Failed to extract text from {include_file}: {parse_error}"
                            )
            except Exception as e:
                logger.warning(f"Failed to process \\include: {e}")

    def _extract_subsections(self, soup: TexNode, doc: LaTeXDocument, current_file: Path):
        """
        Extract subsections (level 2 and 3) from soup and add to doc.

        This also extracts content between subsections from the raw text.
        Also extracts figures from this file.

        Args:
            soup: TexSoup parsed document
            doc: LaTeXDocument to add subsections to
            current_file: Current .tex file
        """
        # Extract figures from this file first
        # Map figures to sections for proper placement
        figures_section_map = self._map_figures_to_sections(soup, current_file)

        for figure_node in soup.find_all("figure"):
            try:
                section_title = figures_section_map.get(id(figure_node))
                figure = self._extract_figure(figure_node, current_file, section_title)
                if figure:
                    doc.figures.append(figure)
                    logger.debug(f"Extracted figure {figure.number} from {current_file.name}")
            except Exception as e:
                logger.warning(f"Failed to extract figure from {current_file.name}: {e}")

        # Extract tables from this file
        tables_section_map = self._map_tables_to_sections(soup, current_file)

        for table_node in soup.find_all("table"):
            try:
                section_title = tables_section_map.get(id(table_node))
                table = self._extract_table(table_node, current_file, section_title)
                if table:
                    doc.tables.append(table)
                    logger.debug(f"Extracted table {table.number} from {current_file.name}")
            except Exception as e:
                logger.warning(f"Failed to extract table from {current_file.name}: {e}")

        # Get raw text to extract content between sections
        raw_text = str(soup)

        # Find all subsection/subsubsection positions
        import re

        subsection_pattern = r"\\(subsection|subsubsection)\{([^}]+)\}"
        matches = list(re.finditer(subsection_pattern, raw_text))

        # Extract content between sections from raw text
        for i, match in enumerate(matches):
            level = 2 if match.group(1) == "subsection" else 3
            title = self._node_to_text(TexSoup(match.group(2)))

            # Find content start (after this section header)
            content_start = match.end()

            # Find content end (before next section or end of file)
            if i + 1 < len(matches):
                content_end = matches[i + 1].start()
            else:
                content_end = len(raw_text)

            # Extract and clean content
            raw_content = raw_text[content_start:content_end]
            clean_content = self._node_to_text(TexSoup(raw_content))

            section = Section(level=level, title=title, content=clean_content)
            doc.sections.append(section)
            section_type = "subsection" if level == 2 else "subsubsection"
            logger.debug(
                f"Extracted {section_type}: {title[:30]}... " f"({len(clean_content)} chars)"
            )

    def _map_inputs_to_sections(self, soup: TexNode, current_file: Path) -> Dict[str, str]:
        r"""
        Map input/include commands to their preceding section.

        This analyzes the raw LaTeX text to determine which section each
        \input command belongs to.

        Args:
            soup: TexSoup parsed document
            current_file: Current .tex file

        Returns:
            Dict mapping input filename to section title
        """
        input_map = {}

        try:
            # Get raw text
            raw_text = str(soup)

            # Find all section positions and input positions
            section_pattern = r"\\section\{([^}]+)\}"
            input_pattern = r"\\input\{([^}]+)\}"

            sections = [(m.start(), m.group(1)) for m in re.finditer(section_pattern, raw_text)]
            input_matches = [(m.start(), m.group(1)) for m in re.finditer(input_pattern, raw_text)]

            # Map each input filename to the most recent section before it
            for input_pos, input_name in input_matches:
                # Find the most recent section before this input
                section_title = None
                for sec_pos, sec_title in reversed(sections):
                    if sec_pos < input_pos:
                        section_title = sec_title
                        break

                if section_title:
                    # Clean up section title and store by input filename
                    section_title = self._node_to_text(TexSoup(section_title))
                    input_map[input_name] = section_title
                    logger.debug(f"Mapped \\input{{{input_name}}} -> section '{section_title}'")

            logger.debug(f"Mapped {len(input_map)} inputs to sections")

        except Exception as e:
            logger.warning(f"Failed to map inputs to sections: {e}")

        return input_map

    def _map_figures_to_sections(self, soup: TexNode, current_file: Path) -> Dict[int, str]:
        """
        Map figure nodes to their containing section by analyzing document structure.

        This uses a simpler heuristic: scan through the raw LaTeX text to find
        which section/subsection each figure appears after.

        Args:
            soup: TexSoup parsed document
            current_file: Current .tex file

        Returns:
            Dict mapping figure node id to section title (or subsection title as fallback)
        """
        figure_map = {}

        try:
            # Get raw text
            raw_text = str(soup)

            # Find all section/subsection positions and figure positions
            # Look for both \section and \subsection
            section_pattern = r"\\(section|subsection)\{([^}]+)\}"
            figure_pattern = r"\\begin\{figure\}"

            sections = [(m.start(), m.group(2)) for m in re.finditer(section_pattern, raw_text)]
            figure_positions = [m.start() for m in re.finditer(figure_pattern, raw_text)]

            # Map each figure to the most recent section/subsection before it
            figure_nodes = list(soup.find_all("figure"))

            for fig_idx, fig_pos in enumerate(figure_positions):
                if fig_idx < len(figure_nodes):
                    # Find the most recent section/subsection before this figure
                    section_title = None
                    for sec_pos, sec_title in reversed(sections):
                        if sec_pos < fig_pos:
                            section_title = sec_title
                            break

                    if section_title:
                        # Clean up section title
                        section_title = self._node_to_text(TexSoup(section_title))
                        figure_map[id(figure_nodes[fig_idx])] = section_title
                        logger.debug(
                            f"Mapped figure {fig_idx+1} to section/subsection '{section_title}'"
                        )

            logger.debug(f"Mapped {len(figure_map)} figures to sections")

        except Exception as e:
            logger.warning(f"Failed to map figures to sections: {e}")

        return figure_map

    def _extract_figure(
        self, figure_node: TexNode, source_file: Path, section_title: Optional[str] = None
    ) -> Optional[Figure]:
        """
        Extract figure information from figure environment.

        Args:
            figure_node: TexSoup figure node
            source_file: Source .tex file
            section_title: Title of the section containing this figure

        Returns:
            Figure object or None if extraction fails
        """
        self.figure_counter += 1
        figure = Figure(
            number=self.figure_counter, source_file=source_file, source_section=section_title
        )

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

    def _extract_table(
        self, table_node: TexNode, source_file: Path, section_title: Optional[str] = None
    ) -> Optional[Table]:
        """
        Extract table information from table environment.

        Args:
            table_node: TexSoup table node
            source_file: Source .tex file
            section_title: Title of the section containing this table

        Returns:
            Table object or None if extraction fails
        """
        self.table_counter += 1
        table = Table(
            number=self.table_counter, source_file=source_file, source_section=section_title
        )

        # Extract table content (tabular environment)
        try:
            tabular_node = table_node.find("tabular")
            if tabular_node:
                table.content = str(tabular_node)
                logger.debug(f"Found tabular content ({len(table.content)} chars)")
        except Exception as e:
            logger.warning(f"Failed to extract tabular: {e}")

        # Extract \caption
        try:
            caption_node = table_node.find("caption")
            if caption_node:
                table.caption = self._node_to_text(caption_node)
                logger.debug(f"Table caption: {table.caption[:50]}...")
        except Exception as e:
            logger.warning(f"Failed to extract table caption: {e}")

        # Extract \label
        try:
            label_node = table_node.find("label")
            if label_node and label_node.args:
                table.label = str(label_node.args[0]).strip("{}")
                logger.debug(f"Table label: {table.label}")
        except Exception as e:
            logger.warning(f"Failed to extract table label: {e}")

        return table if table.content else None

    def _map_tables_to_sections(self, soup: TexNode, current_file: Path) -> Dict[int, str]:
        """
        Map table nodes to their surrounding section.

        Uses the same approach as _map_figures_to_sections.

        Args:
            soup: TexSoup parsed document
            current_file: Current .tex file

        Returns:
            Dict mapping table node id() to section title
        """
        table_section_map = {}

        try:
            raw_text = str(soup)

            # Find all section/subsection headers and table positions
            section_pattern = r"\\(section|subsection)\{([^}]+)\}"
            table_pattern = r"\\begin\{table\}"

            section_matches = list(re.finditer(section_pattern, raw_text))
            table_matches = list(re.finditer(table_pattern, raw_text))

            # For each table, find the most recent section before it
            table_nodes = list(soup.find_all("table"))

            for table_idx, table_match in enumerate(table_matches):
                table_pos = table_match.start()

                # Find the section that comes before this table
                current_section = None
                for section_match in reversed(section_matches):
                    if section_match.start() < table_pos:
                        section_title = self._node_to_text(TexSoup(section_match.group(2)))
                        current_section = section_title
                        break

                # Map table node to section
                if table_idx < len(table_nodes) and current_section:
                    table_section_map[id(table_nodes[table_idx])] = current_section

            logger.debug(
                f"Mapped {len(table_section_map)} tables to sections in {current_file.name}"
            )

        except Exception as e:
            logger.warning(f"Failed to map tables to sections in {current_file.name}: {e}")

        return table_section_map

    @staticmethod
    def tabular_to_html(tabular_content: str) -> str:
        """
        Convert LaTeX tabular to HTML table.

        Args:
            tabular_content: Raw LaTeX tabular environment string

        Returns:
            HTML table string
        """
        # Remove \begin{tabular}{...} and \end{tabular}
        content = re.sub(r"\\begin\{tabular\}\{[^}]+\}", "", tabular_content)
        content = re.sub(r"\\end\{tabular\}", "", content)

        # Remove table rules (including \cmidrule which sometimes appears as content)
        content = re.sub(
            r"\\(toprule|midrule|bottomrule|hline|cmidrule\{[^}]+\}|cline\{[^}]+\})", "", content
        )
        content = re.sub(r"\\rule\{[^}]+\}\{[^}]+\}", "", content)

        # Handle multicolumn: \multicolumn{n}{align}{text} -> text
        content = re.sub(r"\\multicolumn\{[^}]+\}\{[^}]+\}\{([^}]*)\}", r"\1", content)

        # Handle multirow: \multirow{n}{width}{text} -> text
        content = re.sub(r"\\multirow\{[^}]+\}\{[^}]*\}\{([^}]*)\}", r"\1", content)

        # Remove citations
        content = re.sub(r"\\cite[a-z]*\{[^}]+\}", "", content)

        # Remove other LaTeX commands that shouldn't be in table cells
        content = re.sub(r"\\vspace\{[^}]+\}", "", content)
        content = re.sub(r"\\hspace\{[^}]+\}", "", content)
        content = re.sub(r"\\specialrule\{[^}]+\}\{[^}]+\}\{[^}]+\}", "", content)

        # Handle text formatting commands (preserve the text content)
        content = re.sub(r"\\textbf\{([^}]+)\}", r"<strong>\1</strong>", content)
        content = re.sub(r"\\textit\{([^}]+)\}", r"<em>\1</em>", content)
        content = re.sub(r"\\emph\{([^}]+)\}", r"<em>\1</em>", content)
        content = re.sub(r"\\boldmath", "", content)

        # Handle old TeX syntax: {\bf text}, {\it text}, {\em text}
        content = re.sub(r"\{\\bf\s+([^}]+)\}", r"<strong>\1</strong>", content)
        content = re.sub(r"\{\\it\s+([^}]+)\}", r"<em>\1</em>", content)
        content = re.sub(r"\{\\em\s+([^}]+)\}", r"<em>\1</em>", content)

        # Clean up extra whitespace and empty braces
        content = re.sub(r"\{\s*\}", "", content)
        content = re.sub(r"\s+", " ", content)

        # Split into rows (split on \\)
        rows = [r.strip() for r in re.split(r"\\\\", content) if r.strip()]

        # Filter out rows that are just rule commands
        rows = [
            r for r in rows if not re.match(r"^\s*\\(toprule|midrule|bottomrule|hline|cmidrule)", r)
        ]

        html_rows = []

        # First pass: determine the maximum number of columns
        max_cols = 0
        parsed_rows = []
        for row in rows:
            if not row.strip():
                continue
            cells = [c.strip() for c in row.split("&")]
            # Keep empty cells to maintain column alignment
            parsed_rows.append(cells)
            max_cols = max(max_cols, len(cells))

        # Second pass: build HTML with proper column alignment
        for row_idx, cells in enumerate(parsed_rows):
            # Skip completely empty rows
            if not any(c.strip() for c in cells):
                continue

            # First non-empty row is typically header
            tag = "th" if row_idx < 2 else "td"  # First 2 rows are often headers

            # Pad row to max_cols if needed
            while len(cells) < max_cols:
                cells.append("")

            cell_html = "".join(
                f"<{tag}>{cell if cell.strip() else '&nbsp;'}</{tag}>" for cell in cells
            )
            html_rows.append(f"<tr>{cell_html}</tr>")

        # Wrap in thead/tbody for better structure
        if len(html_rows) > 2:
            thead = "".join(html_rows[:2])
            tbody = "".join(html_rows[2:])
            return f"<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>"
        else:
            return f'<table>{"".join(html_rows)}</table>'

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

        # Remove table/figure environments and their content
        text = re.sub(
            r"\\begin\{(table|tabular|center|minipage)\}.*?\\end\{\1\}", "", text, flags=re.DOTALL
        )

        # Replace Figure~ with Figure (remove non-breaking space)
        text = re.sub(r"Figure~\\ref\{[^}]+\}", "Figure", text)
        text = re.sub(r"Figure~", "Figure ", text)

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

    def _extract_math_from_sections(self, doc: LaTeXDocument):
        """
        Extract math formulas from section content and tables.

        This method finds inline math ($...$) and display math
        (equation, align, etc.) in section content and table cells.

        Args:
            doc: LaTeXDocument to extract math from
        """
        # Process abstract if present
        if doc.abstract:
            self._extract_math_from_text(doc.abstract, doc)

        # Process all sections
        for section in doc.sections:
            if section.content:
                self._extract_math_from_text(section.content, doc)

        # Process all tables
        for table in doc.tables:
            if table.content:
                self._extract_math_from_text(table.content, doc)

    def _extract_math_from_text(self, text: str, doc: LaTeXDocument):
        """
        Extract math formulas from text content.

        Args:
            text: Text content containing LaTeX math
            doc: LaTeXDocument to add formulas to
        """
        # Extract inline math: $...$
        inline_pattern = r"\$([^\$]+)\$"
        for match in re.finditer(inline_pattern, text):
            self.math_counter += 1
            formula = MathFormula(
                formula_id=f"inline_{self.math_counter}",
                latex_code=match.group(1),
                is_display=False,
            )
            doc.math_formulas.append(formula)
            logger.debug(f"Extracted inline math: {formula.latex_code[:30]}...")

        # Extract display math: \begin{equation}...\end{equation}
        display_envs = ["equation", "equation*", "align", "align*", "eqnarray", "eqnarray*"]
        for env in display_envs:
            pattern = rf"\\begin\{{{env}\}}(.*?)\\end\{{{env}\}}"
            for match in re.finditer(pattern, text, re.DOTALL):
                self.math_counter += 1
                formula = MathFormula(
                    formula_id=f"display_{self.math_counter}",
                    latex_code=match.group(1).strip(),
                    is_display=True,
                )
                doc.math_formulas.append(formula)
                logger.debug(f"Extracted display math ({env}): {formula.latex_code[:30]}...")

        # Extract display math: \[...\]
        display_bracket_pattern = r"\\\[(.*?)\\\]"
        for match in re.finditer(display_bracket_pattern, text, re.DOTALL):
            self.math_counter += 1
            formula = MathFormula(
                formula_id=f"display_{self.math_counter}",
                latex_code=match.group(1).strip(),
                is_display=True,
            )
            doc.math_formulas.append(formula)
            logger.debug(f"Extracted display math []: {formula.latex_code[:30]}...")


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
