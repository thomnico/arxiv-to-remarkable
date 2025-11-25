"""Tests for EPUB builder."""

import zipfile

import pytest

from arxiv2rm.epub_builder import EPUBBuilder, EPUBMetadata, build_epub
from arxiv2rm.latex_processor import Figure, LaTeXDocument, Section


class TestEPUBMetadata:
    """Tests for EPUB metadata."""

    def test_defaults(self):
        """Test default metadata values."""
        metadata = EPUBMetadata(title="Test Book")
        assert metadata.title == "Test Book"
        assert metadata.authors == []
        assert metadata.language == "en"
        assert metadata.publisher == "arxiv2rm"
        assert metadata.description is None
        assert metadata.source_url is None

    def test_custom_values(self):
        """Test custom metadata values."""
        metadata = EPUBMetadata(
            title="Custom Book",
            authors=["Author One", "Author Two"],
            language="fr",
            publisher="Custom Publisher",
            description="Test description",
            source_url="https://arxiv.org/abs/1234.5678",
        )
        assert metadata.title == "Custom Book"
        assert len(metadata.authors) == 2
        assert metadata.language == "fr"
        assert metadata.publisher == "Custom Publisher"


class TestEPUBBuilder:
    """Tests for EPUB builder."""

    @pytest.fixture
    def simple_metadata(self):
        """Create simple metadata."""
        return EPUBMetadata(
            title="Test Paper",
            authors=["John Doe"],
        )

    @pytest.fixture
    def simple_latex_doc(self):
        """Create a simple LaTeX document."""
        doc = LaTeXDocument()
        doc.title = "Test Paper"
        doc.authors = ["John Doe", "Jane Smith"]
        doc.abstract = "This is a test abstract."
        doc.sections = [
            Section(level=1, title="Introduction", content="Introduction text here."),
            Section(level=2, title="Background", content="Background information."),
            Section(level=1, title="Methods", content="Methods description."),
            Section(level=2, title="Experimental Setup", content="Setup details."),
            Section(level=1, title="Conclusion", content="Concluding remarks."),
        ]
        return doc

    @pytest.fixture
    def complex_latex_doc(self):
        """Create a more complex LaTeX document."""
        doc = LaTeXDocument()
        doc.title = "Complex Paper"
        doc.authors = ["Author A", "Author B", "Author C"]
        doc.abstract = "Complex abstract with multiple sentences. Second sentence here."
        doc.sections = [
            Section(level=1, title="Introduction", content="Intro content"),
            Section(level=2, title="Motivation", content="Motivation content"),
            Section(level=2, title="Contributions", content="Contributions content"),
            Section(level=1, title="Related Work", content="Related work content"),
            Section(level=1, title="Methodology", content="Method content"),
            Section(level=2, title="Dataset", content="Dataset description"),
            Section(level=2, title="Model", content="Model description"),
            Section(level=3, title="Architecture", content="Architecture details"),
            Section(level=1, title="Experiments", content="Experiments content"),
            Section(level=2, title="Setup", content="Setup details"),
            Section(level=2, title="Results", content="Results discussion"),
            Section(level=1, title="Conclusion", content="Conclusion content"),
        ]
        doc.figures = [
            Figure(number=1, caption="Test figure 1", label="fig:test1"),
            Figure(number=2, caption="Test figure 2", label="fig:test2"),
        ]
        return doc

    def test_init(self, simple_metadata, tmp_path):
        """Test EPUBBuilder initialization."""
        output_path = tmp_path / "test.epub"
        builder = EPUBBuilder(simple_metadata, output_path)

        assert builder.metadata.title == "Test Paper"
        assert builder.metadata.identifier is not None  # UUID generated
        assert builder.metadata.date is not None
        assert builder.output_path == output_path
        assert len(builder.chapters) == 0

    def test_build_from_latex_simple(self, simple_latex_doc, simple_metadata, tmp_path):
        """Test building EPUB from simple LaTeX document."""
        output_path = tmp_path / "simple.epub"
        builder = EPUBBuilder(simple_metadata, output_path)
        book = builder.build_from_latex(simple_latex_doc)

        assert book is not None
        assert len(builder.chapters) > 0

        # Check metadata was set
        assert builder.metadata.title == "Test Paper"
        assert len(builder.metadata.authors) == 2

    def test_build_from_latex_complex(self, complex_latex_doc, simple_metadata, tmp_path):
        """Test building EPUB from complex LaTeX document."""
        output_path = tmp_path / "complex.epub"
        builder = EPUBBuilder(simple_metadata, output_path)
        book = builder.build_from_latex(complex_latex_doc)

        assert book is not None
        # 1 abstract + 5 level-1 sections = 6 chapters
        assert len(builder.chapters) >= 5

    def test_set_metadata(self, simple_metadata, tmp_path):
        """Test metadata setting."""
        metadata = EPUBMetadata(
            title="Full Metadata Test",
            authors=["Author One", "Author Two"],
            language="en",
            publisher="Test Publisher",
            description="Test description",
            source_url="https://example.com/paper",
            identifier="test-id-123",
            date="2025-01-24",
        )

        builder = EPUBBuilder(metadata, tmp_path / "test.epub")
        builder._set_metadata()

        assert builder.book.title == "Full Metadata Test"
        assert len(builder.book.get_metadata("DC", "creator")) == 2

    def test_add_abstract(self, simple_metadata, tmp_path):
        """Test adding abstract chapter."""
        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")
        builder._set_metadata()
        builder._add_abstract("This is a test abstract with special chars: <>&\"'")

        assert len(builder.chapters) == 1
        assert builder.chapters[0].title == "Abstract"

        # Check HTML escaping
        content = builder.chapters[0].content.decode("utf-8")
        assert "&lt;" in content  # < escaped
        assert "&gt;" in content  # > escaped
        assert "&amp;" in content  # & escaped

    def test_create_chapters_from_sections(self, simple_latex_doc, simple_metadata, tmp_path):
        """Test chapter creation from sections."""
        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")
        builder._set_metadata()
        builder._create_chapters_from_sections(simple_latex_doc.sections)

        # Should have 3 level-1 sections = 3 chapters
        assert len(builder.chapters) == 3

        # Check titles
        titles = [ch.title for ch in builder.chapters]
        assert "Introduction" in titles
        assert "Methods" in titles
        assert "Conclusion" in titles

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        assert EPUBBuilder._sanitize_filename("Test Title") == "test-title"
        assert (
            EPUBBuilder._sanitize_filename("Title with (Special) Chars!")
            == "title-with-special-chars"
        )
        assert EPUBBuilder._sanitize_filename("Multiple   Spaces") == "multiple-spaces"
        assert EPUBBuilder._sanitize_filename("UPPERCASE") == "uppercase"
        assert EPUBBuilder._sanitize_filename("123-Numbers") == "123-numbers"
        assert EPUBBuilder._sanitize_filename("") == "chapter"
        # Long title should be truncated
        long_title = "A" * 100
        sanitized = EPUBBuilder._sanitize_filename(long_title)
        assert len(sanitized) <= 50

    def test_escape_html(self):
        """Test HTML escaping."""
        assert EPUBBuilder._escape_html("<tag>") == "&lt;tag&gt;"
        assert EPUBBuilder._escape_html("a & b") == "a &amp; b"
        assert EPUBBuilder._escape_html('"quoted"') == "&quot;quoted&quot;"
        assert EPUBBuilder._escape_html("'apostrophe'") == "&#39;apostrophe&#39;"
        assert EPUBBuilder._escape_html("normal text") == "normal text"

    def test_add_css(self, simple_metadata, tmp_path):
        """Test adding CSS stylesheet."""
        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")

        css_content = """
        body {
            font-family: 'OpenDyslexic', sans-serif;
            font-size: 16pt;
        }
        """

        builder.add_css(css_content, "custom.css")

        # Check CSS was added to book
        items = list(builder.book.get_items())
        css_items = [item for item in items if item.media_type == "text/css"]
        assert len(css_items) == 1

    def test_add_font(self, simple_metadata, tmp_path):
        """Test adding font file."""
        # Create dummy font file
        font_path = tmp_path / "test_font.ttf"
        font_path.write_bytes(b"fake font data")

        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")
        builder.add_font(font_path, "test.ttf")

        # Check font was added
        items = list(builder.book.get_items())
        font_items = [item for item in items if "font" in item.media_type]
        assert len(font_items) == 1

    def test_add_font_missing_file(self, simple_metadata, tmp_path):
        """Test adding non-existent font file."""
        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")

        with pytest.raises(ValueError, match="Font file not found"):
            builder.add_font(tmp_path / "missing.ttf", "missing.ttf")

    def test_add_font_unsupported_format(self, simple_metadata, tmp_path):
        """Test adding unsupported font format."""
        # Create dummy file with wrong extension
        font_path = tmp_path / "test.xyz"
        font_path.write_bytes(b"fake data")

        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")

        with pytest.raises(ValueError, match="Unsupported font format"):
            builder.add_font(font_path, "test.xyz")

    def test_add_image(self, simple_metadata, tmp_path):
        """Test adding image file."""
        # Create dummy image
        from PIL import Image

        img_path = tmp_path / "test_image.jpg"
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        img.save(img_path)

        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")
        builder.add_image(img_path)

        # Check image was added
        items = list(builder.book.get_items())
        image_items = [item for item in items if "image" in item.media_type]
        assert len(image_items) == 1

    def test_add_image_custom_name(self, simple_metadata, tmp_path):
        """Test adding image with custom name."""
        from PIL import Image

        img_path = tmp_path / "original.jpg"
        img = Image.new("RGB", (100, 100))
        img.save(img_path)

        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")
        builder.add_image(img_path, "custom_name.jpg")

        items = list(builder.book.get_items())
        image_items = [item for item in items if "image" in item.media_type]
        assert len(image_items) == 1
        assert "custom_name.jpg" in image_items[0].file_name

    def test_add_image_missing_file(self, simple_metadata, tmp_path):
        """Test adding non-existent image."""
        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")

        with pytest.raises(ValueError, match="Image file not found"):
            builder.add_image(tmp_path / "missing.jpg")

    def test_write_epub(self, simple_latex_doc, simple_metadata, tmp_path):
        """Test writing EPUB to file."""
        output_path = tmp_path / "output.epub"

        builder = EPUBBuilder(simple_metadata, output_path)
        builder.build_from_latex(simple_latex_doc)
        builder.write()

        assert output_path.exists()
        assert output_path.suffix == ".epub"

        # Verify it's a valid ZIP file (EPUB is ZIP)
        assert zipfile.is_zipfile(output_path)

        # Check EPUB structure
        with zipfile.ZipFile(output_path) as zf:
            names = zf.namelist()
            assert "mimetype" in names
            assert any("META-INF" in name for name in names)

    def test_write_without_output_path(self, simple_metadata):
        """Test writing without output path raises error."""
        builder = EPUBBuilder(simple_metadata)

        with pytest.raises(ValueError, match="No output path specified"):
            builder.write()

    def test_write_with_override_path(self, simple_latex_doc, simple_metadata, tmp_path):
        """Test writing with override output path."""
        initial_path = tmp_path / "initial.epub"
        override_path = tmp_path / "override.epub"

        builder = EPUBBuilder(simple_metadata, initial_path)
        builder.build_from_latex(simple_latex_doc)
        builder.write(override_path)

        assert override_path.exists()
        assert not initial_path.exists()

    def test_build_chapter_html(self, simple_metadata, tmp_path):
        """Test HTML generation for chapter."""
        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")

        main_section = Section(level=1, title="Test Chapter", content="Main content")
        subsections = [
            Section(level=2, title="Subsection 1", content="Sub content 1"),
            Section(level=2, title="Subsection 2", content="Sub content 2"),
        ]

        html = builder._build_chapter_html(main_section, subsections)

        assert "<h1>Test Chapter</h1>" in html
        assert "<h2>Subsection 1</h2>" in html
        assert "<h2>Subsection 2</h2>" in html
        assert "Main content" in html
        assert "Sub content 1" in html

    def test_orphaned_subsection_handling(self, simple_metadata, tmp_path):
        """Test handling of orphaned subsections (no parent level-1)."""
        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")

        # Start with level 2 (orphaned)
        sections = [
            Section(level=2, title="Orphaned Subsection", content="Content"),
            Section(level=1, title="Normal Section", content="Content"),
        ]

        builder._create_chapters_from_sections(sections)

        # Should still create chapters
        assert len(builder.chapters) == 2

    def test_convenience_function(self, simple_latex_doc, tmp_path):
        """Test build_epub convenience function."""
        output_path = tmp_path / "convenience.epub"

        result = build_epub(simple_latex_doc, output_path)

        assert result == output_path
        assert output_path.exists()

    def test_convenience_function_custom_metadata(self, simple_latex_doc, tmp_path):
        """Test build_epub with custom metadata."""
        output_path = tmp_path / "custom_meta.epub"

        metadata = EPUBMetadata(
            title="Custom Title",
            authors=["Custom Author"],
            language="fr",
        )

        result = build_epub(simple_latex_doc, output_path, metadata)

        assert result == output_path
        assert output_path.exists()

    def test_empty_document(self, simple_metadata, tmp_path):
        """Test building EPUB from empty document."""
        doc = LaTeXDocument()
        doc.title = "Empty Document"

        output_path = tmp_path / "empty.epub"
        builder = EPUBBuilder(simple_metadata, output_path)
        builder.build_from_latex(doc)
        builder.write()

        assert output_path.exists()

    def test_document_without_abstract(self, simple_metadata, tmp_path):
        """Test building EPUB without abstract."""
        doc = LaTeXDocument()
        doc.title = "No Abstract"
        doc.sections = [
            Section(level=1, title="Introduction", content="Content"),
        ]

        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")
        builder.build_from_latex(doc)

        # Should have 1 chapter (no abstract chapter)
        assert len(builder.chapters) == 1

    def test_toc_generation(self, simple_latex_doc, simple_metadata, tmp_path):
        """Test table of contents generation."""
        builder = EPUBBuilder(simple_metadata, tmp_path / "test.epub")
        builder.build_from_latex(simple_latex_doc)

        # Check TOC was built
        assert len(builder.toc) > 0
        assert builder.book.toc is not None

    def test_unicode_handling(self, simple_metadata, tmp_path):
        """Test Unicode character handling."""
        doc = LaTeXDocument()
        doc.title = "Tëst Ünïcödé 测试"
        doc.authors = ["Authör Ñame"]
        doc.abstract = "Abstrâct with spëcial chars: é, ñ, ü, 中文"
        doc.sections = [
            Section(level=1, title="Séction 1", content="Cöntent with Ünicöde"),
        ]

        builder = EPUBBuilder(simple_metadata, tmp_path / "unicode.epub")
        builder.build_from_latex(doc)
        builder.write()

        assert (tmp_path / "unicode.epub").exists()
