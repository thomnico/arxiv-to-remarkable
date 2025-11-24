"""Tests for CLI module."""

import pytest
from click.testing import CliRunner

from arxiv2rm.cli import main


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


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


def test_config_show(runner):
    """Test config show command."""
    result = runner.invoke(main, ["config", "--show"])
    assert result.exit_code == 0
