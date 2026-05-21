"""Configuration management for arxiv2rm."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


class TypographyConfig(BaseModel):
    """Typography configuration."""

    font_family: str = "OpenDyslexic"
    default_font_size: int = Field(default=16, ge=12, le=24)
    line_height: float = Field(default=1.5, ge=1.0, le=2.0)


class LayoutConfig(BaseModel):
    """Layout configuration."""

    margins: Dict[str, str] = Field(
        default={"top": "2em", "bottom": "2em", "left": "1.5em", "right": "1.5em"}
    )
    single_column: bool = True


class ImageConfig(BaseModel):
    """Image processing configuration."""

    max_width: int = Field(default=1404, ge=100, le=2000)
    max_height: int = Field(default=1872, ge=100, le=3000)
    optimize_for_eink: bool = True
    quality: int = Field(default=85, ge=1, le=100)
    dithering: bool = False


class OCRConfig(BaseModel):
    """OCR configuration."""

    engine: str = Field(default="groq", pattern="^(groq|tesseract)$")
    groq_api_key: Optional[str] = None
    fallback: str = Field(default="tesseract", pattern="^(groq|tesseract|none)$")
    language: str = "eng"
    cache_enabled: bool = True
    cache_dir: str = "~/.arxiv2rm/cache/ocr"

    @field_validator("groq_api_key")
    @classmethod
    def validate_groq_key(cls, v: Optional[str], info) -> Optional[str]:
        """Validate Groq API key format."""
        if v and not v.startswith("gsk_"):
            raise ValueError("Groq API key must start with 'gsk_'")
        return v


class RemarkableConfig(BaseModel):
    """reMarkable sync configuration."""

    method: str = Field(default="rmapi", pattern="^(rmapi|cloud|none)$")
    default_folder: str = "Research"
    cloud_token: Optional[str] = None
    auto_upload: bool = False
    device_model: str = Field(default="rmpro", pattern="^(rm1|rm2|rmpro)$")


class ArxivConfig(BaseModel):
    """ArXiv-specific configuration."""

    prefer_latex: bool = True
    cache_dir: str = "~/.arxiv2rm/cache/arxiv"


class PDFConfig(BaseModel):
    """PDF processing configuration."""

    dpi: int = Field(default=150, ge=72, le=300)


class OutputConfig(BaseModel):
    """Output configuration."""

    format: str = Field(default="pdf", pattern="^pdf$")
    directory: str = "~/Downloads/arxiv2rm"


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    file: str = "~/.arxiv2rm/logs/arxiv2rm.log"
    max_size: str = "10MB"
    backup_count: int = Field(default=5, ge=0, le=100)


class Config(BaseModel):
    """Main configuration class."""

    output: OutputConfig = Field(default_factory=OutputConfig)
    typography: TypographyConfig = Field(default_factory=TypographyConfig)
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    images: ImageConfig = Field(default_factory=ImageConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    remarkable: RemarkableConfig = Field(default_factory=RemarkableConfig)
    arxiv: ArxivConfig = Field(default_factory=ArxivConfig)
    pdf: PDFConfig = Field(default_factory=PDFConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class ConfigLoader:
    """Configuration loader and manager."""

    DEFAULT_CONFIG_PATH = Path.home() / ".arxiv2rm" / "config.yaml"
    ENV_FILE = ".env"

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize config loader.

        Args:
            config_path: Optional path to config file. Defaults to ~/.arxiv2rm/config.yaml
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: Optional[Config] = None

    def load(self) -> Config:
        """Load configuration from files and environment.

        Returns:
            Config: Loaded and validated configuration

        Raises:
            ValueError: If configuration is invalid
        """
        # Load environment variables from .env file if it exists
        if Path(self.ENV_FILE).exists():
            load_dotenv(self.ENV_FILE)

        # Load YAML config if exists, otherwise use defaults
        yaml_config = {}
        if self.config_path.exists():
            with open(self.config_path) as f:
                yaml_config = yaml.safe_load(f) or {}

        # Expand environment variables in YAML config
        yaml_config = self._expand_env_vars(yaml_config)

        # Inject environment defaults for keys not in YAML
        yaml_config = self._inject_env_defaults(yaml_config)

        # Validate and create config
        try:
            self._config = Config(**yaml_config)
        except Exception as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        # Additional validation
        self._validate_config()

        return self._config

    def _expand_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively expand environment variables in config.

        Args:
            config: Configuration dictionary

        Returns:
            Dict with expanded environment variables
        """
        if isinstance(config, dict):
            return {k: self._expand_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._expand_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            # Extract variable name and expand
            var_name = config[2:-1]
            return os.environ.get(var_name, config)
        return config

    def _inject_env_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Inject environment variables into config if not already set.

        Args:
            config: Configuration dictionary

        Returns:
            Dict with injected environment variables
        """
        # Inject Groq API key if available in environment
        if "ocr" not in config:
            config["ocr"] = {}
        if "groq_api_key" not in config.get("ocr", {}):
            if groq_key := os.environ.get("GROQ_API_KEY"):
                config["ocr"]["groq_api_key"] = groq_key

        # Inject reMarkable token if available in environment
        if "remarkable" not in config:
            config["remarkable"] = {}
        if "cloud_token" not in config.get("remarkable", {}):
            if rm_token := os.environ.get("REMARKABLE_TOKEN"):
                config["remarkable"]["cloud_token"] = rm_token

        return config

    def _validate_config(self) -> None:
        """Validate configuration requirements.

        Raises:
            ValueError: If required settings are missing
        """
        if not self._config:
            return

        # Check OCR requirements
        if self._config.ocr.engine == "groq":
            if not self._config.ocr.groq_api_key:
                raise ValueError(
                    "GROQ_API_KEY is required when using Groq OCR engine. "
                    "Set it in .env file or config.yaml"
                )

        # Check reMarkable Cloud requirements
        if self._config.remarkable.method == "cloud":
            if not self._config.remarkable.cloud_token:
                raise ValueError(
                    "REMARKABLE_TOKEN is required when using Cloud sync. "
                    "Set it in .env file or config.yaml"
                )

    @property
    def config(self) -> Config:
        """Get loaded configuration.

        Returns:
            Config: Current configuration

        Raises:
            RuntimeError: If config not loaded yet
        """
        if not self._config:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._config

    def save(self, path: Optional[Path] = None) -> None:
        """Save current configuration to file.

        Args:
            path: Optional path to save to. Defaults to config_path.
        """
        if not self._config:
            raise RuntimeError("No configuration to save")

        save_path = path or self.config_path
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict and remove None values
        config_dict = self._config.model_dump(exclude_none=True)

        with open(save_path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

    def create_default_config(self, force: bool = False) -> Path:
        """Create default config file.

        Args:
            force: Overwrite existing file if True

        Returns:
            Path: Path to created config file

        Raises:
            FileExistsError: If config exists and force=False
        """
        if self.config_path.exists() and not force:
            raise FileExistsError(f"Config file already exists: {self.config_path}")

        self._config = Config()
        self.save()
        return self.config_path


# Global config loader instance
_loader: Optional[ConfigLoader] = None


def get_config(reload: bool = False) -> Config:
    """Get global configuration instance.

    Args:
        reload: Force reload configuration

    Returns:
        Config: Global configuration
    """
    global _loader
    if _loader is None or reload:
        _loader = ConfigLoader()
        _loader.load()
    return _loader.config


def set_config_path(path: Path) -> None:
    """Set custom config file path.

    Args:
        path: Path to config file
    """
    global _loader
    _loader = ConfigLoader(config_path=path)
