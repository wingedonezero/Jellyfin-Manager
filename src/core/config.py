"""
Application configuration management.

Handles persistent storage of user settings including media paths,
Docker preferences, and container configuration.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class ContainerConfig:
    """Jellyfin container configuration."""
    image: str = "jellyfin/jellyfin:latest"
    container_name: str = "jellyfin-manager"
    web_port: int = 8096
    # Paths inside container where we mount things
    config_mount: str = "/config"
    cache_mount: str = "/cache"
    media_mount_base: str = "/media"


@dataclass
class AppConfig:
    """Main application configuration."""
    # Local paths for Jellyfin data
    config_dir: Path = field(default_factory=lambda: Path.home() / ".jellyfin-manager" / "config")
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".jellyfin-manager" / "cache")

    # User-selected media folders (will be mounted into container)
    media_paths: list[Path] = field(default_factory=list)

    # Docker daemon preferences
    stop_daemon_on_exit: bool = False

    # Hardware acceleration
    enable_hw_accel: bool = True
    hw_accel_type: str = "vaapi"  # vaapi for AMD/Intel

    # Container settings
    container: ContainerConfig = field(default_factory=ContainerConfig)

    def __post_init__(self):
        """Ensure paths are Path objects."""
        if isinstance(self.config_dir, str):
            self.config_dir = Path(self.config_dir)
        if isinstance(self.cache_dir, str):
            self.cache_dir = Path(self.cache_dir)
        self.media_paths = [Path(p) if isinstance(p, str) else p for p in self.media_paths]
        if isinstance(self.container, dict):
            self.container = ContainerConfig(**self.container)


class ConfigManager:
    """Manages loading and saving application configuration."""

    DEFAULT_CONFIG_PATH = Path.home() / ".jellyfin-manager" / "app_config.json"

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: Optional[AppConfig] = None

    @property
    def config(self) -> AppConfig:
        """Get current configuration, loading from disk if needed."""
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> AppConfig:
        """Load configuration from disk, or create default if not exists."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                return AppConfig(**data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Warning: Could not load config, using defaults: {e}")
                return AppConfig()
        return AppConfig()

    def save(self, config: Optional[AppConfig] = None) -> None:
        """Save configuration to disk."""
        if config is not None:
            self._config = config

        if self._config is None:
            return

        # Ensure parent directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, handling Path objects
        data = self._serialize_config(self._config)

        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _serialize_config(self, config: AppConfig) -> dict:
        """Convert config to JSON-serializable dict."""
        data = asdict(config)
        # Convert Path objects to strings
        data['config_dir'] = str(config.config_dir)
        data['cache_dir'] = str(config.cache_dir)
        data['media_paths'] = [str(p) for p in config.media_paths]
        return data

    def add_media_path(self, path: Path) -> None:
        """Add a media path to the configuration."""
        if path not in self.config.media_paths:
            self.config.media_paths.append(path)
            self.save()

    def remove_media_path(self, path: Path) -> None:
        """Remove a media path from the configuration."""
        if path in self.config.media_paths:
            self.config.media_paths.remove(path)
            self.save()

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.config.config_dir.mkdir(parents=True, exist_ok=True)
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)
