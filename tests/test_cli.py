"""Tests for CLI module."""

import os
from tempfile import NamedTemporaryFile

import pytest
from click.testing import CliRunner

from arxiv2rm.cli import main


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_batch_file():
    """Create temporary batch file."""
    with NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("https://arxiv.org/abs/2301.12345\n")
        f.write("# Comment line\n")
        f.write("https://arxiv.org/abs/2302.67890\n")
        batch_path = f.name
    yield batch_path
    os.unlink(batch_path)


def test_version(runner):
    """Test version command."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()


def test_help(runner):
    """Test help command."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "convert" in result.output.lower()
    assert "batch" in result.output.lower()
    assert "config" in result.output.lower()


def test_convert_help(runner):
    """Test convert command help."""
    result = runner.invoke(main, ["convert", "--help"])
    assert result.exit_code == 0
    assert "url_or_path" in result.output.lower()


def test_batch_help(runner):
    """Test batch command help."""
    result = runner.invoke(main, ["batch", "--help"])
    assert result.exit_code == 0
    assert "batch_file" in result.output.lower()


def test_config_help(runner):
    """Test config command help."""
    result = runner.invoke(main, ["config", "--help"])
    assert result.exit_code == 0
    assert "show" in result.output.lower()


def test_config_show(runner, monkeypatch):
    """Test config show command."""
    # Provide required Groq API key
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_cli")

    result = runner.invoke(main, ["config", "--show"])
    assert result.exit_code == 0


def test_config_path(runner):
    """Test config path command."""
    result = runner.invoke(main, ["config", "--path"])
    assert result.exit_code == 0
    assert "config" in result.output.lower()


def test_convert_with_url(runner, monkeypatch):
    """Test convert command with URL (not yet implemented)."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_convert")

    result = runner.invoke(main, ["convert", "https://arxiv.org/abs/2301.12345"])
    # URL download not yet implemented, should show warning and exit
    assert result.exit_code == 1
    assert "url download not yet implemented" in result.output.lower()


def test_batch_command(runner, temp_batch_file, monkeypatch):
    """Test batch command."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_batch")

    result = runner.invoke(main, ["batch", temp_batch_file])
    assert result.exit_code == 0
    assert "2 papers" in result.output.lower()


def test_logging_setup(runner, monkeypatch):
    """Test that logging is set up correctly."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_logging")

    result = runner.invoke(main, ["--log-level", "DEBUG", "config", "--show"])
    assert result.exit_code == 0
