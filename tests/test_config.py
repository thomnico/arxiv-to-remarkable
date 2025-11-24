"""Tests for configuration module."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import pytest
import yaml

from arxiv2rm.config import Config, ConfigLoader, ImageConfig, OCRConfig, get_config


@pytest.fixture
def temp_config_dir():
    """Create temporary config directory."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_env_file():
    """Create temporary .env file."""
    with NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("GROQ_API_KEY=gsk_test_key_12345\n")
        f.write("REMARKABLE_TOKEN=test_token\n")
        env_path = f.name
    yield env_path
    os.unlink(env_path)


def test_default_config():
    """Test default configuration."""
    config = Config()
    assert config.output.format == "epub"
    assert config.typography.font_family == "OpenDyslexic"
    assert config.images.max_width == 1404
    assert config.images.max_height == 1872
    assert config.ocr.engine == "groq"


def test_image_config_validation():
    """Test image config validation."""
    # Valid config
    config = ImageConfig(max_width=1404, max_height=1872, quality=85)
    assert config.max_width == 1404

    # Invalid quality
    with pytest.raises(ValueError):
        ImageConfig(quality=101)

    with pytest.raises(ValueError):
        ImageConfig(quality=0)


def test_ocr_config_groq_key_validation():
    """Test Groq API key validation."""
    # Valid key
    config = OCRConfig(groq_api_key="gsk_test123")
    assert config.groq_api_key == "gsk_test123"

    # Invalid key format
    with pytest.raises(ValueError, match="must start with 'gsk_'"):
        OCRConfig(groq_api_key="invalid_key")


def test_config_loader_defaults(temp_config_dir, monkeypatch):
    """Test loading with no config file (defaults)."""
    config_path = temp_config_dir / "config.yaml"

    # Provide required Groq API key for default engine
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_defaults")

    loader = ConfigLoader(config_path=config_path)

    config = loader.load()
    assert config.output.format == "epub"
    assert config.typography.default_font_size == 16


def test_config_loader_from_yaml(temp_config_dir, monkeypatch):
    """Test loading from YAML file."""
    config_path = temp_config_dir / "config.yaml"

    # Provide required Groq API key for default engine
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_yaml")

    yaml_content = {
        "typography": {"default_font_size": 18},
        "images": {"quality": 90},
    }

    with open(config_path, "w") as f:
        yaml.dump(yaml_content, f)

    loader = ConfigLoader(config_path=config_path)
    config = loader.load()

    assert config.typography.default_font_size == 18
    assert config.images.quality == 90


def test_config_loader_env_expansion(temp_config_dir, monkeypatch):
    """Test environment variable expansion."""
    config_path = temp_config_dir / "config.yaml"

    monkeypatch.setenv("GROQ_API_KEY", "gsk_from_env")

    yaml_content = {
        "ocr": {
            "groq_api_key": "${GROQ_API_KEY}",
        }
    }

    with open(config_path, "w") as f:
        yaml.dump(yaml_content, f)

    loader = ConfigLoader(config_path=config_path)
    config = loader.load()

    assert config.ocr.groq_api_key == "gsk_from_env"


def test_config_validation_groq_missing_key(temp_config_dir, monkeypatch, tmp_path):
    """Test validation fails when Groq key missing."""
    # Change to temp directory to avoid loading project .env file
    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    try:
        config_path = temp_config_dir / "config.yaml"

        # Ensure no Groq API key in environment
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        yaml_content = {
            "ocr": {
                "engine": "groq",
                # Missing groq_api_key
            }
        }

        with open(config_path, "w") as f:
            yaml.dump(yaml_content, f)

        loader = ConfigLoader(config_path=config_path)

        with pytest.raises(ValueError, match="GROQ_API_KEY is required"):
            loader.load()
    finally:
        os.chdir(original_cwd)


def test_config_validation_cloud_missing_token(temp_config_dir, monkeypatch):
    """Test validation fails when Cloud token missing."""
    config_path = temp_config_dir / "config.yaml"

    # Provide Groq API key so we only test Cloud token validation
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_cloud")

    yaml_content = {
        "remarkable": {
            "method": "cloud",
            # Missing cloud_token
        }
    }

    with open(config_path, "w") as f:
        yaml.dump(yaml_content, f)

    loader = ConfigLoader(config_path=config_path)

    with pytest.raises(ValueError, match="REMARKABLE_TOKEN is required"):
        loader.load()


def test_config_save(temp_config_dir, monkeypatch):
    """Test saving configuration."""
    config_path = temp_config_dir / "config.yaml"

    # Provide required Groq API key
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_save")

    loader = ConfigLoader(config_path=config_path)
    config = loader.load()

    # Modify config
    config.typography.default_font_size = 20
    loader.save()

    # Reload and verify
    loader2 = ConfigLoader(config_path=config_path)
    config2 = loader2.load()
    assert config2.typography.default_font_size == 20


def test_create_default_config(temp_config_dir):
    """Test creating default config file."""
    config_path = temp_config_dir / "config.yaml"

    loader = ConfigLoader(config_path=config_path)
    created_path = loader.create_default_config()

    assert created_path.exists()
    assert created_path == config_path


def test_create_default_config_exists(temp_config_dir):
    """Test creating default config when file exists."""
    config_path = temp_config_dir / "config.yaml"
    config_path.touch()

    loader = ConfigLoader(config_path=config_path)

    with pytest.raises(FileExistsError):
        loader.create_default_config(force=False)

    # Should work with force=True
    loader.create_default_config(force=True)


def test_global_config_instance(monkeypatch):
    """Test global config instance."""
    # This test modifies global state, so be careful
    # In real usage, this should be reset between tests

    # Provide required Groq API key
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_global")

    config = get_config()
    assert isinstance(config, Config)
