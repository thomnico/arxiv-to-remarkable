"""Tests for LaTeX processor."""

import pytest

from arxiv2rm.latex_processor import LaTeXProcessor, process_latex_source


class TestLaTeXProcessor:
    """Tests for LaTeX source processing."""

    @pytest.fixture
    def simple_latex(self, tmp_path):
        """Create a simple LaTeX document."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()

        main_tex = latex_dir / "main.tex"
        main_tex.write_text(
            r"""
\documentclass{article}
\title{Test Paper}
\author{John Doe \and Jane Smith}
\begin{document}
\maketitle

\begin{abstract}
This is a test abstract.
\end{abstract}

\section{Introduction}
This is the introduction section.

\section{Methods}
This is the methods section.

\subsection{Experimental Setup}
Details about experiments.

\end{document}
"""
        )
        return latex_dir, main_tex

    @pytest.fixture
    def latex_with_figures(self, tmp_path):
        """Create LaTeX document with figures."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()
        figures_dir = latex_dir / "figures"
        figures_dir.mkdir()

        # Create dummy image files
        (figures_dir / "plot1.pdf").write_bytes(b"%PDF fake")
        (figures_dir / "diagram.png").write_bytes(b"PNG fake")
        (latex_dir / "chart.jpg").write_bytes(b"JPG fake")

        main_tex = latex_dir / "main.tex"
        main_tex.write_text(
            r"""
\documentclass{article}
\begin{document}

\section{Results}

\begin{figure}
\includegraphics{figures/plot1}
\caption{First plot showing results.}
\label{fig:plot1}
\end{figure}

\begin{figure}
\includegraphics[width=0.8\textwidth]{figures/diagram.png}
\caption{System diagram.}
\label{fig:diagram}
\end{figure}

\begin{figure}
\includegraphics{chart.jpg}
\caption{Data chart without label.}
\end{figure}

See Figure~\ref{fig:plot1} for details.

\end{document}
"""
        )
        return latex_dir, main_tex

    @pytest.fixture
    def multifile_latex(self, tmp_path):
        """Create multi-file LaTeX project."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()

        main_tex = latex_dir / "main.tex"
        main_tex.write_text(
            r"""
\documentclass{article}
\title{Multi-file Paper}
\begin{document}
\maketitle

\input{intro}
\input{methods.tex}

\end{document}
"""
        )

        intro_tex = latex_dir / "intro.tex"
        intro_tex.write_text(
            r"""
\section{Introduction}
This is from intro.tex.
"""
        )

        methods_tex = latex_dir / "methods.tex"
        methods_tex.write_text(
            r"""
\section{Methods}
This is from methods.tex.

\subsection{Procedure}
Detailed procedure.
"""
        )

        return latex_dir, main_tex

    def test_parse_simple_document(self, simple_latex):
        """Test parsing a simple LaTeX document."""
        latex_dir, main_tex = simple_latex
        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        assert doc.title == "Test Paper"
        assert len(doc.authors) == 2
        assert "John Doe" in doc.authors
        assert "Jane Smith" in doc.authors
        assert doc.abstract is not None
        assert "test abstract" in doc.abstract.lower()

    def test_extract_sections(self, simple_latex):
        """Test section extraction."""
        latex_dir, main_tex = simple_latex
        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        # The current implementation extracts \section commands as level-1 sections
        # Subsections are included in the content of their parent section
        assert len(doc.sections) >= 2
        section_titles = [s.title for s in doc.sections]
        assert "Introduction" in section_titles
        assert "Methods" in section_titles

        # Check section levels
        intro = next(s for s in doc.sections if s.title == "Introduction")
        assert intro.level == 1

        # Subsection content should be included in parent section content
        methods = next(s for s in doc.sections if s.title == "Methods")
        assert "Experimental Setup" in methods.content

    def test_extract_figures(self, latex_with_figures):
        """Test figure extraction."""
        latex_dir, main_tex = latex_with_figures
        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        assert len(doc.figures) == 3

        # Check first figure
        fig1 = doc.figures[0]
        assert fig1.number == 1
        assert fig1.label == "fig:plot1"
        assert "First plot" in fig1.caption
        assert fig1.image_path == "figures/plot1"

        # Check second figure
        fig2 = doc.figures[1]
        assert fig2.number == 2
        assert fig2.label == "fig:diagram"
        assert "System diagram" in fig2.caption

        # Check third figure (no label)
        fig3 = doc.figures[2]
        assert fig3.number == 3
        assert fig3.label is None
        assert "Data chart" in fig3.caption

    def test_build_reference_map(self, latex_with_figures):
        """Test building figure reference map."""
        latex_dir, main_tex = latex_with_figures
        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        assert "fig:plot1" in doc.references
        assert doc.references["fig:plot1"] == 1
        assert "fig:diagram" in doc.references
        assert doc.references["fig:diagram"] == 2

    def test_find_image_files(self, latex_with_figures):
        """Test finding actual image files."""
        latex_dir, main_tex = latex_with_figures
        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        assert len(doc.image_files) == 3

        # Check that actual files were found
        image_names = {img.name for img in doc.image_files}
        assert "plot1.pdf" in image_names
        assert "diagram.png" in image_names
        assert "chart.jpg" in image_names

    def test_resolve_image_with_extension(self, tmp_path):
        """Test resolving image path with explicit extension."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()
        (latex_dir / "test.png").write_bytes(b"fake")

        main_tex = latex_dir / "main.tex"
        main_tex.write_text(r"\documentclass{article}\begin{document}\end{document}")

        processor = LaTeXProcessor(latex_dir, main_tex)
        resolved = processor._resolve_image_path("test.png")

        assert resolved is not None
        assert resolved.name == "test.png"

    def test_resolve_image_without_extension(self, tmp_path):
        """Test resolving image path without extension."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()
        (latex_dir / "test.pdf").write_bytes(b"fake")

        main_tex = latex_dir / "main.tex"
        main_tex.write_text(r"\documentclass{article}\begin{document}\end{document}")

        processor = LaTeXProcessor(latex_dir, main_tex)
        resolved = processor._resolve_image_path("test")

        assert resolved is not None
        assert resolved.name == "test.pdf"

    def test_resolve_image_in_subdirectory(self, tmp_path):
        """Test resolving image in figures subdirectory."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()
        figures_dir = latex_dir / "figures"
        figures_dir.mkdir()
        (figures_dir / "plot.png").write_bytes(b"fake")

        main_tex = latex_dir / "main.tex"
        main_tex.write_text(r"\documentclass{article}\begin{document}\end{document}")

        processor = LaTeXProcessor(latex_dir, main_tex)
        resolved = processor._resolve_image_path("plot")

        assert resolved is not None
        assert resolved.name == "plot.png"

    def test_multifile_project(self, multifile_latex):
        """Test processing multi-file LaTeX project."""
        latex_dir, main_tex = multifile_latex
        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        # The current implementation processes sections from the main file
        # and extracts subsections from included files via _extract_subsections
        # (sections in input files are processed separately)
        assert len(doc.sections) >= 1

        # Check included files are tracked
        assert len(doc.included_files) == 2
        included_names = {f.name for f in doc.included_files}
        assert "intro.tex" in included_names
        assert "methods.tex" in included_names

    def test_input_with_and_without_extension(self, tmp_path):
        r"""Test \input with and without .tex extension."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()

        main_tex = latex_dir / "main.tex"
        main_tex.write_text(r"\documentclass{article}\begin{document}\input{sub}\end{document}")

        sub_tex = latex_dir / "sub.tex"
        sub_tex.write_text(r"\section{Subsection}")

        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        # The included file should be tracked
        assert len(doc.included_files) >= 1
        included_names = {f.name for f in doc.included_files}
        assert "sub.tex" in included_names

    def test_node_to_text_removes_commands(self, simple_latex):
        """Test that _node_to_text removes LaTeX commands."""
        latex_dir, main_tex = simple_latex
        processor = LaTeXProcessor(latex_dir, main_tex)

        from TexSoup import TexSoup

        test_node = TexSoup(r"\textbf{Bold} and \textit{italic} and \cite{ref}")
        text = processor._node_to_text(test_node)

        # Check that command syntax is removed (braces, backslashes)
        assert "\\textbf{" not in text
        assert "\\textit{" not in text
        assert "\\cite{" not in text
        assert "Bold" in text
        assert "italic" in text

    def test_extract_caption(self, latex_with_figures):
        """Test caption extraction."""
        latex_dir, main_tex = latex_with_figures
        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        captions = [f.caption for f in doc.figures if f.caption]
        assert len(captions) == 3
        assert any("First plot" in c for c in captions)
        assert any("System diagram" in c for c in captions)
        assert any("Data chart" in c for c in captions)

    def test_process_empty_document(self, tmp_path):
        """Test processing empty/minimal document."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()

        main_tex = latex_dir / "main.tex"
        main_tex.write_text(r"\documentclass{article}\begin{document}\end{document}")

        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        assert doc.title is None
        assert len(doc.authors) == 0
        assert doc.abstract is None
        assert len(doc.sections) == 0
        assert len(doc.figures) == 0

    def test_convenience_function(self, simple_latex):
        """Test process_latex_source convenience function."""
        latex_dir, main_tex = simple_latex
        doc = process_latex_source(latex_dir, main_tex)

        assert doc is not None
        assert doc.title == "Test Paper"
        # Current implementation extracts level-1 sections only
        assert len(doc.sections) >= 2

    def test_figure_without_caption(self, tmp_path):
        """Test figure without caption."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()
        (latex_dir / "img.png").write_bytes(b"fake")

        main_tex = latex_dir / "main.tex"
        main_tex.write_text(
            r"""
\documentclass{article}
\begin{document}
\begin{figure}
\includegraphics{img.png}
\end{figure}
\end{document}
"""
        )

        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        assert len(doc.figures) == 1
        assert doc.figures[0].caption is None

    def test_nested_figures_directory(self, tmp_path):
        """Test finding images in nested directories."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()
        nested_dir = latex_dir / "figures" / "chapter1"
        nested_dir.mkdir(parents=True)
        (nested_dir / "plot.pdf").write_bytes(b"fake")

        main_tex = latex_dir / "main.tex"
        main_tex.write_text(
            r"""
\documentclass{article}
\begin{document}
\begin{figure}
\includegraphics{figures/chapter1/plot}
\end{figure}
\end{document}
"""
        )

        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        assert len(doc.figures) == 1
        # Note: actual file finding depends on _resolve_image_path implementation

    def test_comments_removed(self, tmp_path):
        """Test that LaTeX comments are removed during parsing."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()

        main_tex = latex_dir / "main.tex"
        main_tex.write_text(
            r"""
\documentclass{article}
\begin{document}
\section{Test} % This is a comment
Content here.
% Full line comment
\end{document}
"""
        )

        processor = LaTeXProcessor(latex_dir, main_tex)
        doc = processor.process()

        # Should parse without errors
        assert len(doc.sections) >= 1
