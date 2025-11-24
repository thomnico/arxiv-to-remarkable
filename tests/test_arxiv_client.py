"""Tests for ArXiv client."""

import tarfile
from unittest.mock import Mock, patch

import pytest
import requests

from arxiv2rm.arxiv_client import ArxivClient, ArxivURLParser


class TestArxivURLParser:
    """Tests for ArXiv URL parsing."""

    def test_parse_new_format_abs_url(self):
        """Test parsing new format ArXiv abstract URL."""
        url = "https://arxiv.org/abs/2301.12345"
        assert ArxivURLParser.parse(url) == "2301.12345"

    def test_parse_new_format_pdf_url(self):
        """Test parsing new format ArXiv PDF URL."""
        url = "https://arxiv.org/pdf/2301.12345.pdf"
        assert ArxivURLParser.parse(url) == "2301.12345"

    def test_parse_with_version(self):
        """Test parsing ArXiv URL with version."""
        url = "https://arxiv.org/abs/2301.12345v2"
        assert ArxivURLParser.parse(url) == "2301.12345v2"

    def test_parse_old_format(self):
        """Test parsing old format ArXiv URL."""
        url = "https://arxiv.org/abs/cs/0703123"
        assert ArxivURLParser.parse(url) == "cs/0703123"

    def test_parse_direct_id_new(self):
        """Test parsing direct paper ID (new format)."""
        assert ArxivURLParser.parse("2301.12345") == "2301.12345"

    def test_parse_direct_id_old(self):
        """Test parsing direct paper ID (old format)."""
        assert ArxivURLParser.parse("cs/0703123") == "cs/0703123"

    def test_parse_invalid(self):
        """Test parsing invalid input."""
        assert ArxivURLParser.parse("not-an-arxiv-url") is None
        assert ArxivURLParser.parse("https://google.com") is None

    def test_strip_version(self):
        """Test version stripping."""
        assert ArxivURLParser.strip_version("2301.12345v2") == "2301.12345"
        assert ArxivURLParser.strip_version("2301.12345") == "2301.12345"


class TestArxivClient:
    """Tests for ArXiv client."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create ArXiv client with temp cache dir."""
        return ArxivClient(cache_dir=tmp_path / "cache")

    @pytest.fixture
    def mock_arxiv_paper(self):
        """Mock arxiv.Result object."""
        paper = Mock()
        paper.title = "Test Paper Title"

        # Create author mocks with .name attribute
        author1 = Mock()
        author1.name = "Author One"
        author2 = Mock()
        author2.name = "Author Two"
        paper.authors = [author1, author2]

        paper.summary = "Test abstract"
        paper.published = "2023-01-15"
        paper.updated = "2023-01-20"
        paper.pdf_url = "https://arxiv.org/pdf/2301.12345.pdf"
        paper.entry_id = "http://arxiv.org/abs/2301.12345v1"
        paper.categories = ["cs.AI", "cs.LG"]
        return paper

    def test_init_creates_cache_dir(self, tmp_path):
        """Test initialization creates cache directory."""
        cache_dir = tmp_path / "test_cache"
        client = ArxivClient(cache_dir=cache_dir)

        assert client.cache_dir == cache_dir
        assert cache_dir.exists()

    @patch("arxiv2rm.arxiv_client.arxiv.Search")
    def test_fetch_metadata_success(self, mock_search, client, mock_arxiv_paper):
        """Test successful metadata fetch."""
        mock_search.return_value.results.return_value = iter([mock_arxiv_paper])

        metadata = client.fetch_metadata("2301.12345")

        assert metadata["paper_id"] == "2301.12345"
        assert metadata["title"] == "Test Paper Title"
        assert metadata["authors"] == ["Author One", "Author Two"]
        assert metadata["abstract"] == "Test abstract"
        assert len(metadata["categories"]) == 2

    @patch("arxiv2rm.arxiv_client.arxiv.Search")
    def test_fetch_metadata_not_found(self, mock_search, client):
        """Test metadata fetch for non-existent paper."""
        mock_search.return_value.results.return_value = iter([])

        with pytest.raises(ValueError, match="paper not found"):
            client.fetch_metadata("9999.99999")

    @patch("arxiv2rm.arxiv_client.arxiv.Search")
    def test_fetch_metadata_strips_version(self, mock_search, client, mock_arxiv_paper):
        """Test that version is stripped when fetching metadata."""
        mock_search.return_value.results.return_value = iter([mock_arxiv_paper])

        client.fetch_metadata("2301.12345v2")

        # Verify Search was called with clean ID
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["id_list"] == ["2301.12345"]

    @patch("arxiv2rm.arxiv_client.requests.get")
    def test_download_latex_source_success(self, mock_get, client, tmp_path):
        """Test successful LaTeX source download."""
        # Create a mock .tar.gz file
        tar_content = b"fake tar content"
        mock_response = Mock()
        mock_response.content = tar_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Create a real tar.gz with a .tex file for extraction
        tex_content = b"\\documentclass{article}\n\\begin{document}\nTest\n\\end{document}"
        tar_path = tmp_path / "test.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            import io

            tex_data = io.BytesIO(tex_content)
            info = tarfile.TarInfo(name="main.tex")
            info.size = len(tex_content)
            tar.addfile(info, tex_data)

        mock_response.content = tar_path.read_bytes()

        result = client.download_latex_source("2301.12345")

        assert result.exists()
        assert (result / "main.tex").exists()

    @patch("arxiv2rm.arxiv_client.requests.get")
    def test_download_latex_source_not_available(self, mock_get, client):
        """Test LaTeX source download when not available (403)."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=403)
        )
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="not available"):
            client.download_latex_source("2301.12345")

    @patch("arxiv2rm.arxiv_client.requests.get")
    def test_download_latex_source_uses_cache(self, mock_get, client, tmp_path):
        """Test that cached LaTeX source is reused."""
        # Create cached source
        latex_dir = client.cache_dir / "2301.12345" / "latex"
        latex_dir.mkdir(parents=True)
        (latex_dir / "main.tex").write_text("cached content")

        result = client.download_latex_source("2301.12345")

        assert result == latex_dir
        mock_get.assert_not_called()  # Should not download

    @patch("arxiv2rm.arxiv_client.requests.get")
    def test_download_pdf_success(self, mock_get, client):
        """Test successful PDF download."""
        pdf_content = b"%PDF-1.4\nfake pdf content"
        mock_response = Mock()
        mock_response.content = pdf_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = client.download_pdf("2301.12345")

        assert result.exists()
        assert result.suffix == ".pdf"
        assert result.read_bytes() == pdf_content

    @patch("arxiv2rm.arxiv_client.requests.get")
    def test_download_pdf_uses_cache(self, mock_get, client):
        """Test that cached PDF is reused."""
        # Create cached PDF
        pdf_path = client.cache_dir / "2301.12345.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"cached pdf")

        result = client.download_pdf("2301.12345")

        assert result == pdf_path
        mock_get.assert_not_called()

    def test_find_main_tex_file_by_name(self, tmp_path):
        """Test finding main .tex file by common name."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()

        # Create files
        (latex_dir / "main.tex").write_text("main")
        (latex_dir / "other.tex").write_text("other")

        client = ArxivClient()
        result = client.find_main_tex_file(latex_dir)

        assert result.name == "main.tex"

    def test_find_main_tex_file_by_documentclass(self, tmp_path):
        """Test finding main .tex file by \\documentclass."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()

        # Create files
        (latex_dir / "supplement.tex").write_text("supplement")
        (latex_dir / "paper.tex").write_text("\\documentclass{article}\nContent")

        client = ArxivClient()
        result = client.find_main_tex_file(latex_dir)

        assert result.name == "paper.tex"

    def test_find_main_tex_file_by_size(self, tmp_path):
        """Test finding main .tex file by size (fallback)."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()

        # Create files
        (latex_dir / "small.tex").write_text("small")
        (latex_dir / "large.tex").write_text("large content " * 100)

        client = ArxivClient()
        result = client.find_main_tex_file(latex_dir)

        assert result.name == "large.tex"

    def test_find_main_tex_file_no_files(self, tmp_path):
        """Test finding main .tex file when no .tex files exist."""
        latex_dir = tmp_path / "latex"
        latex_dir.mkdir()

        client = ArxivClient()
        result = client.find_main_tex_file(latex_dir)

        assert result is None

    @patch("arxiv2rm.arxiv_client.arxiv.Search")
    @patch("arxiv2rm.arxiv_client.requests.get")
    def test_fetch_paper_latex_preferred(
        self, mock_get, mock_search, client, mock_arxiv_paper, tmp_path
    ):
        """Test fetching paper with LaTeX preference."""
        mock_search.return_value.results.return_value = iter([mock_arxiv_paper])

        # Mock LaTeX download
        tex_content = b"\\documentclass{article}\nTest"
        tar_path = tmp_path / "test.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            import io

            tex_data = io.BytesIO(tex_content)
            info = tarfile.TarInfo(name="main.tex")
            info.size = len(tex_content)
            tar.addfile(info, tex_data)

        mock_response = Mock()
        mock_response.content = tar_path.read_bytes()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        metadata, source_path = client.fetch_paper("2301.12345", prefer_latex=True)

        assert metadata["source_type"] == "latex"
        assert source_path.exists()
        assert (source_path / "main.tex").exists()

    @patch("arxiv2rm.arxiv_client.arxiv.Search")
    @patch("arxiv2rm.arxiv_client.requests.get")
    def test_fetch_paper_pdf_fallback(self, mock_get, mock_search, client, mock_arxiv_paper):
        """Test fetching paper with PDF fallback when LaTeX unavailable."""
        mock_search.return_value.results.return_value = iter([mock_arxiv_paper])

        # Mock LaTeX 403, then PDF success
        responses = [
            Mock(
                raise_for_status=Mock(
                    side_effect=requests.exceptions.HTTPError(response=Mock(status_code=403))
                )
            ),
            Mock(content=b"%PDF-1.4\ntest", raise_for_status=Mock()),
        ]
        mock_get.side_effect = responses

        metadata, source_path = client.fetch_paper("2301.12345", prefer_latex=True)

        assert metadata["source_type"] == "pdf"
        assert source_path.suffix == ".pdf"

    def test_fetch_paper_invalid_url(self, client):
        """Test fetching paper with invalid URL."""
        with pytest.raises(ValueError, match="Invalid ArXiv"):
            client.fetch_paper("not-a-valid-url")
