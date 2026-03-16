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
    figure_refs: List[str] = field(default_factory=list)  # Ordered list of figure labels
    table_refs: List[str] = field(default_factory=list)  # Ordered list of table labels


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

    @staticmethod
    def _extract_braced_content(text: str, start_pos: int) -> tuple[str, int]:
        """
        Extract content from a LaTeX command argument, handling nested braces.

        Args:
            text: Full LaTeX text
            start_pos: Position of the opening brace

        Returns:
            Tuple of (extracted_content, end_position)
        """
        if start_pos >= len(text) or text[start_pos] != "{":
            return "", start_pos

        depth = 1
        pos = start_pos + 1
        while pos < len(text) and depth > 0:
            if text[pos] == "{" and (pos == 0 or text[pos - 1] != "\\"):
                depth += 1
            elif text[pos] == "}" and (pos == 0 or text[pos - 1] != "\\"):
                depth -= 1
            pos += 1

        if depth == 0:
            return text[start_pos + 1 : pos - 1], pos
        return "", start_pos

    @staticmethod
    def _find_sections(text: str):
        """
        Find section commands in LaTeX text, handling nested braces properly.

        Args:
            text: LaTeX text to search

        Yields:
            Match objects with start(), end(), and group(1) for section title
        """
        import re

        class SectionMatch:
            """Match-like object for section extraction."""

            def __init__(self, start_pos, end_pos, title, full_text):
                self._start = start_pos
                self._end = end_pos
                self._title = title
                self._full = full_text

            def start(self):
                return self._start

            def end(self):
                return self._end

            def group(self, n):
                return self._title if n == 1 else self._full

        # Find all \section{ positions
        pattern = r"\\section\{"
        for match in re.finditer(pattern, text):
            start = match.start()
            brace_start = match.end()

            # Count braces to find matching closing brace
            depth = 1
            pos = brace_start
            while pos < len(text) and depth > 0:
                if text[pos] == "{" and (pos == 0 or text[pos - 1] != "\\"):
                    depth += 1
                elif text[pos] == "}" and (pos == 0 or text[pos - 1] != "\\"):
                    depth -= 1
                pos += 1

            if depth == 0:
                title = text[brace_start : pos - 1]
                logger.debug(f"Extracted section title with nested braces: {title[:80]}...")
                yield SectionMatch(start, pos, title, text[start:pos])

    @staticmethod
    def _fix_texsoup_incompatibilities(content: str) -> str:
        """
        Fix LaTeX patterns that TexSoup can't parse.

        Args:
            content: Raw LaTeX content

        Returns:
            Fixed LaTeX content that TexSoup can parse
        """
        # Fix possessive apostrophes after LaTeX commands (}'s pattern)
        # TexSoup can't parse \command{text}'s, so rewrite to \command{text's}
        # This handles patterns like \textsc{LLM-Guard}'s -> \textsc{LLM-Guard's}
        # Fix possessive apostrophes after LaTeX commands
        content = re.sub(r"\}('s)\b", r"\1}", content)

        # Fix \\[Npt] line breaks with optional spacing argument
        # TexSoup misinterprets the [ after \\ as an unmatched bracket
        # Replace \\[5pt] with just \\ (spacing is irrelevant for text extraction)
        content = re.sub(r"\\\\(?:\[[\d.]+(?:pt|em|ex|mm|cm|in)\])", r"\\\\", content)

        # Strip \ifx conditional blocks that TexSoup cannot parse
        # These are TeX primitives for conditional compilation (e.g., multi-venue papers)
        # We keep the content but remove the \ifx/\else/\fi control flow
        # Handle nested \ifx...\else...\fi patterns by removing the directives
        content = re.sub(r"\\ifx\s*\\[a-zA-Z]+\s*\\[a-zA-Z]+\s*\n?", "", content)
        content = re.sub(r"\\else\\ifx\s*\\[a-zA-Z]+\s*\\[a-zA-Z]+\s*\n?", "", content)
        # Remove standalone \else (not followed by \ifx)
        content = re.sub(r"\\else\s*\n(?!\\ifx)", "", content)
        # Remove \fi that's not part of a word (keep \fill, \figure, etc.)
        content = re.sub(r"\\fi(?![a-zA-Z])", "", content)

        # Remove \twocolumn[ with unmatched bracket (common in ICML templates)
        content = re.sub(r"\\twocolumn\s*\[", "", content)

        # Remove \makeatletter...\makeatother blocks (internal LaTeX macro definitions)
        # These often contain \newenvironment with \begin/\end pairs that TexSoup
        # misinterprets as real environments (e.g., \begin{algorithm} inside a definition)
        content = re.sub(r"\\makeatletter.*?\\makeatother", "", content, flags=re.DOTALL)

        # Replace LaTeX backtick quotes (`word' and ``word'') with straight quotes
        # TexSoup misparses backticks inside braced arguments as malformed tokens
        content = re.sub(r"``(.*?)''", r'"\1"', content)
        content = re.sub(r"`(.*?)'", r"'\1'", content)

        # Remove \titleformat and \titlespacing commands (from titlesec package)
        # These contain \section/\subsection as arguments, which TexSoup tries to
        # parse as actual sectioning commands, causing malformed argument errors
        content = re.sub(
            r"\\titleformat\{[^}]*\}" r"(?:\s*(?:\[[^\]]*\])?\s*\{[^}]*\})*",
            "",
            content,
        )
        content = re.sub(
            r"\\titlespacing\*?\{[^}]*\}" r"(?:\s*\{[^}]*\})*",
            "",
            content,
        )

        return content

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
        # Note: Math formulas are extracted from raw content during this step
        self._extract_content(main_soup, doc, self.main_tex_file)

        # Extract math from abstract if present (from raw LaTeX)
        if doc.abstract:
            # Get raw abstract content from the soup
            abstract_node = main_soup.find("abstract")
            if abstract_node:
                raw_abstract = str(abstract_node)
                self._extract_math_from_text(raw_abstract, doc)

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

    def _parse_string(self, latex_str: str) -> TexNode:
        """
        Parse a LaTeX string using TexSoup with compatibility fixes.

        Args:
            latex_str: LaTeX string to parse

        Returns:
            TexSoup parsed tree
        """
        # Apply TexSoup compatibility fixes
        fixed_content = self._fix_texsoup_incompatibilities(latex_str)
        try:
            return TexSoup(fixed_content)
        except Exception:
            # Log context for debugging
            logger.error(f"TexSoup parsing failed. String preview: {repr(latex_str[:200])}")
            logger.error(f"After fix: {repr(fixed_content[:200])}")
            logger.error(f"Strings equal: {latex_str == fixed_content}")
            raise

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
            soup = self._parse_string(content)
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
        Extract content (sections, figures, tables) from LaTeX tree.

        Uses raw text parsing to extract content BETWEEN sections since TexSoup
        doesn't capture content between section commands.
        """
        # Track processed input commands to avoid duplicates
        processed_inputs: Set[int] = set()

        # Get raw text for parsing
        raw_text = str(soup)

        # Expand \input{} commands inline to get full content
        raw_text = self._expand_inputs(raw_text, current_file)

        # Find all section positions (handle nested braces)
        section_matches = list(self._find_sections(raw_text))

        logger.debug(f"Found {len(section_matches)} sections in {current_file.name}")

        # Extract content between sections
        for i, match in enumerate(section_matches):
            title = match.group(1)
            # Clean title
            title = self._node_to_text(self._parse_string(title))

            # Find content start (after section header)
            content_start = match.end()

            # Find content end (before next section or end of document/file)
            if i + 1 < len(section_matches):
                content_end = section_matches[i + 1].start()
            else:
                # Last section - go until \end{document} or end of file
                end_doc_match = re.search(r"\\end\{document\}", raw_text[content_start:])
                if end_doc_match:
                    content_end = content_start + end_doc_match.start()
                else:
                    content_end = len(raw_text)

            # Extract raw content
            raw_content = raw_text[content_start:content_end]

            # Extract math formulas from RAW content BEFORE cleaning
            self._extract_math_from_text(raw_content, doc)

            # Clean and convert to text (this will replace math with markers)
            content = self._clean_latex_content(raw_content)

            # Extract figure/table references from content
            figure_refs, table_refs = self._extract_references_from_content(raw_content)

            section = Section(
                level=1,
                title=title,
                content=content,
                figure_refs=figure_refs,
                table_refs=table_refs,
            )
            doc.sections.append(section)
            logger.debug(f"Extracted section: {title[:30]}... ({len(content)} chars)")

        # Extract tables from raw text
        self._extract_tables_from_raw(raw_text, doc, current_file)

        # Build figure section map and extract figures
        figures_section_map = self._map_figures_to_sections(soup, current_file)

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
                                        # Re-extract references after adding content
                                        fig_refs, tab_refs = self._extract_references_from_content(
                                            section.content
                                        )
                                        section.figure_refs = fig_refs
                                        section.table_refs = tab_refs
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

    def _clean_latex_content(self, raw_content: str) -> str:
        """
        Clean raw LaTeX content to readable text.

        Removes environments, commands, and formats text for reading.
        """
        content = raw_content

        # Remove figure environments entirely (they're extracted separately)
        content = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", "", content, flags=re.DOTALL)

        # Remove table environments entirely (they're extracted separately)
        content = re.sub(r"\\begin\{table\}.*?\\end\{table\}", "", content, flags=re.DOTALL)

        # Remove algorithm environments
        content = re.sub(r"\\begin\{algorithm\}.*?\\end\{algorithm\}", "", content, flags=re.DOTALL)

        # Handle subsection/subsubsection - keep as markers
        content = re.sub(r"\\subsection\{([^}]+)\}", r"\n\n### \1\n\n", content)
        content = re.sub(r"\\subsubsection\{([^}]+)\}", r"\n\n#### \1\n\n", content)

        # Handle paragraph commands
        content = re.sub(r"\\paragraph\{([^}]+)\}", r"\n\n**\1** ", content)

        # Handle itemize/enumerate environments
        content = re.sub(r"\\begin\{itemize\}(\[.*?\])?", "", content)
        content = re.sub(r"\\end\{itemize\}", "", content)
        content = re.sub(r"\\begin\{enumerate\}(\[.*?\])?", "", content)
        content = re.sub(r"\\end\{enumerate\}", "", content)
        content = re.sub(r"\\item(\[.*?\])?", "• ", content)

        # Handle text formatting
        content = re.sub(r"\\textbf\{([^}]+)\}", r"\1", content)
        content = re.sub(r"\\textit\{([^}]+)\}", r"\1", content)
        content = re.sub(r"\\emph\{([^}]+)\}", r"\1", content)
        content = re.sub(r"\\underline\{([^}]+)\}", r"\1", content)
        content = re.sub(r"\\url\{([^}]+)\}", r"\1", content)

        # Handle citations - replace with [citation]
        content = re.sub(r"\\cite[a-z]*\{[^}]+\}", "[citation]", content)

        # Handle footnotes - remove or simplify
        content = re.sub(r"\\footnote\{[^}]+\}", "", content)

        # Remove labels
        content = re.sub(r"\\label\{[^}]+\}", "", content)

        # Preserve references with markers
        content = re.sub(r"\\ref\{([^}]+)\}", r"<<<REF:\1>>>", content)
        content = re.sub(r"\\cref\{([^}]+)\}", r"<<<REF:\1>>>", content)

        # Handle inline math - simplify for text display
        # Convert to readable form with brackets
        content = re.sub(r"\$([^$]+)\$", r"[\1]", content)

        # Preserve display math environments with markers for image replacement
        # Use hash of content for consistent matching
        import hashlib

        def make_display_marker(match):
            latex_code = match.group(1).strip()
            content_hash = hashlib.md5(latex_code.encode()).hexdigest()[:8]
            return f"\n\n<<<DISPLAY_MATH:{content_hash}>>>\n\n"

        content = re.sub(
            r"\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}",
            make_display_marker,
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r"\\begin\{align\*?\}(.*?)\\end\{align\*?\}",
            make_display_marker,
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r"\\\[(.*?)\\\]",
            make_display_marker,
            content,
            flags=re.DOTALL,
        )

        # Remove other common commands
        content = re.sub(r"\\vspace\{[^}]+\}", "", content)
        content = re.sub(r"\\hspace\{[^}]+\}", "", content)
        content = re.sub(r"\\newline", "\n", content)
        content = re.sub(r"\\\\", "\n", content)
        content = re.sub(r"\\noindent", "", content)
        content = re.sub(r"\\centering", "", content)

        # Handle special characters
        content = re.sub(r"~", " ", content)  # Non-breaking space
        content = re.sub(r"\\&", "&", content)
        content = re.sub(r"\\%", "%", content)
        content = re.sub(r"\\_", "_", content)
        content = re.sub(r"\\#", "#", content)
        content = re.sub(r"\\ldots", "...", content)
        content = re.sub(r"\\dots", "...", content)

        # Remove any remaining LaTeX commands (but keep their content if in braces)
        content = re.sub(r"\\[a-zA-Z]+\*?\{([^}]*)\}", r"\1", content)
        content = re.sub(r"\\[a-zA-Z]+\*?", "", content)

        # Clean up braces
        content = re.sub(r"[\{\}]", "", content)

        # Clean up whitespace
        content = re.sub(r"\n\s*\n\s*\n+", "\n\n", content)
        content = re.sub(r"[ \t]+", " ", content)

        return content.strip()

    def _extract_tables_from_raw(self, raw_text: str, doc: LaTeXDocument, current_file: Path):
        """
        Extract tables from raw LaTeX text.

        Uses regex to find table environments and extract their content.
        """
        # Find all table environments
        table_pattern = r"\\begin\{table\}(.*?)\\end\{table\}"
        table_matches = list(re.finditer(table_pattern, raw_text, flags=re.DOTALL))

        logger.debug(f"Found {len(table_matches)} tables in {current_file.name}")

        for match in table_matches:
            table_content = match.group(1)

            self.table_counter += 1
            table = Table(
                number=self.table_counter,
                source_file=current_file,
            )

            # Extract caption (handle nested braces)
            caption_match = re.search(r"\\caption\{", table_content)
            if caption_match:
                caption_content, _ = self._extract_braced_content(
                    table_content, caption_match.end() - 1
                )
                if caption_content:
                    table.caption = self._node_to_text(self._parse_string(caption_content))

            # Extract label
            label_match = re.search(r"\\label\{([^}]+)\}", table_content)
            if label_match:
                table.label = label_match.group(1)

            # Extract tabular content
            tabular_match = re.search(
                r"\\begin\{tabular\}(\{[^}]+\})?(.*?)\\end\{tabular\}",
                table_content,
                flags=re.DOTALL,
            )
            if tabular_match:
                table.content = tabular_match.group(0)

            if table.content or table.caption:
                doc.tables.append(table)
                logger.debug(f"Extracted table {table.number}: {table.label or 'no label'}")

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
            title = self._node_to_text(self._parse_string(match.group(2)))

            # Find content start (after this section header)
            content_start = match.end()

            # Find content end (before next section or end of file)
            if i + 1 < len(matches):
                content_end = matches[i + 1].start()
            else:
                content_end = len(raw_text)

            # Extract raw content
            raw_content = raw_text[content_start:content_end]

            # Extract math formulas from RAW content BEFORE cleaning
            self._extract_math_from_text(raw_content, doc)

            # Clean the content
            clean_content = self._node_to_text(self._parse_string(raw_content))

            # Extract figure/table references from content
            figure_refs, table_refs = self._extract_references_from_content(clean_content)

            section = Section(
                level=level,
                title=title,
                content=clean_content,
                figure_refs=figure_refs,
                table_refs=table_refs,
            )
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
                    section_title = self._node_to_text(self._parse_string(section_title))
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
                        section_title = self._node_to_text(self._parse_string(section_title))
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
                        section_title = self._node_to_text(
                            self._parse_string(section_match.group(2))
                        )
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
            content = self._node_to_text(self._parse_string(section_str))

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
        # PRESERVE REFERENCES: Replace \ref{label} with marker instead of removing
        text = re.sub(r"\\ref\{([^}]+)\}", r"<<<REF:\1>>>", text)
        text = re.sub(r"\\label\{[^}]+\}", "", text)
        text = re.sub(r"\\thanks\{[^}]+\}", "", text)  # Remove footnotes

        # Remove table/figure environments and their content
        text = re.sub(
            r"\\begin\{(table|tabular|center|minipage)\}.*?\\end\{\1\}", "", text, flags=re.DOTALL
        )

        # Replace Figure~/Table~ with marker-preserved versions
        text = re.sub(r"Figure~<<<REF:([^>]+)>>>", r"<<<REF:\1>>>", text)
        text = re.sub(r"Table~<<<REF:([^>]+)>>>", r"<<<REF:\1>>>", text)
        text = re.sub(r"Figure~", "Figure ", text)
        text = re.sub(r"Table~", "Table ", text)

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

    def _extract_references_from_content(self, content: str) -> tuple[List[str], List[str]]:
        """
        Extract figure and table references in order from content.

        Args:
            content: Text content with <<<REF:label>>> markers

        Returns:
            Tuple of (figure_refs, table_refs) - lists of labels in order of appearance
        """
        figure_refs = []
        table_refs = []

        # Find all <<<REF:...>>> markers in order
        for match in re.finditer(r"<<<REF:([^>]+)>>>", content):
            ref_label = match.group(1)
            if ref_label.startswith("fig:"):
                if ref_label not in figure_refs:  # Only first occurrence
                    figure_refs.append(ref_label)
            elif ref_label.startswith("tab:"):
                if ref_label not in table_refs:  # Only first occurrence
                    table_refs.append(ref_label)

        return figure_refs, table_refs

    def _expand_inputs(self, raw_text: str, current_file: Path, depth: int = 0) -> str:
        r"""
        Expand \input{} commands inline to get full content.

        Args:
            raw_text: Raw LaTeX text
            current_file: Current .tex file being processed
            depth: Recursion depth to prevent infinite loops

        Returns:
            Text with \input{} commands replaced by file contents
        """
        if depth > 10:  # Prevent infinite recursion
            logger.warning("Max input recursion depth reached")
            return raw_text

        # Find all \input{filename} patterns
        input_pattern = r"\\input\{([^}]+)\}"

        def replace_input(match):
            input_name = match.group(1).strip()
            # Add .tex extension if missing
            if not input_name.endswith(".tex"):
                input_name += ".tex"

            # Try to resolve file path
            input_path = current_file.parent / input_name
            if not input_path.exists():
                input_path = self.latex_dir / input_name

            if input_path.exists():
                try:
                    content = input_path.read_text(encoding="utf-8", errors="ignore")
                    # Remove comments
                    content = re.sub(r"(?<!\\)%.*$", "", content, flags=re.MULTILINE)
                    # Apply TexSoup compatibility fixes
                    content = self._fix_texsoup_incompatibilities(content)
                    # Recursively expand nested inputs
                    content = self._expand_inputs(content, input_path, depth + 1)
                    logger.debug(f"Expanded \\input{{{input_name}}} ({len(content)} chars)")
                    return content
                except Exception as e:
                    logger.warning(f"Failed to expand \\input{{{input_name}}}: {e}")
                    return match.group(0)  # Keep original
            else:
                logger.warning(f"Input file not found: {input_name}")
                return match.group(0)  # Keep original

        return re.sub(input_pattern, replace_input, raw_text)

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

    def _pdf_to_png(self, pdf_path: Path) -> Optional[Path]:
        """Convert first page of a PDF figure to PNG using PyMuPDF."""
        try:
            import fitz

            png_path = pdf_path.with_suffix(".png")
            if png_path.exists():
                return png_path
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            mat = fitz.Matrix(2.5, 2.5)
            pix = page.get_pixmap(matrix=mat)
            pix.save(str(png_path))
            doc.close()
            return png_path
        except Exception as e:
            logger.warning(f"Failed to convert PDF figure to PNG: {pdf_path}: {e}")
            return None

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
            # For PDF figures, prefer raster alternatives (PNG/JPG) since
            # PDF images cannot be rendered directly by PIL/reportlab
            if image_path.lower().endswith(".pdf"):
                base_without_ext = image_path[:-4]
                for alt_ext in [".png", ".jpg", ".jpeg"]:
                    alt_candidate = self.latex_dir / (base_without_ext + alt_ext)
                    if alt_candidate.exists():
                        return alt_candidate
            # Fall back to converting PDF to PNG
            candidate = self.latex_dir / image_path
            if candidate.exists():
                png = self._pdf_to_png(candidate)
                return png

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
            # Escape special regex chars in env name (like * in align*)
            env_escaped = re.escape(env)
            pattern = rf"\\begin\{{{env_escaped}\}}(.*?)\\end\{{{env_escaped}\}}"
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
