"""Server configuration management utilities.

Provides functions for managing MCP server configurations in config files.
"""

from pathlib import Path

from .config_helpers import (
    _add_server_to_config,
    _load_config_file,
    _remove_server_from_containers,
    _save_config_file,
)


def _remove_server_from_config(config_path: Path, server_name: str) -> bool:
    """Remove a server from a specific MCP config file."""
    if not config_path.exists():
        return False

    try:
        config, is_toml = _load_config_file(config_path)
        if config is None:
            return False

        if _remove_server_from_containers(config, server_name):
            return _save_config_file(config_path, config, is_toml)

    except Exception as e:
        print(f"  Warning: Failed to process {config_path}: {type(e).__name__}: {e}")

    return False
