import logging
import os
from pathlib import Path
from typing import Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for external CLI tools loaded from tools.yaml with lazy loading."""

    def __init__(self, config_path: Optional[Path] = None):
        env_override = os.environ.get("CODE_ASSISTANT_MANAGER_TOOLS_FILE")
        if config_path is not None:
            self.config_path = Path(config_path)
        elif env_override:
            self.config_path = Path(env_override)
        else:
            # tools.yaml is in the project root, two levels up from this file
            self.config_path = (
                Path(__file__).resolve().parent.parent.parent / "tools.yaml"
            )
        self._tools = None  # Lazy load on first access

    def _load(self) -> Dict[str, dict]:
        """Load tools from packaged resources first, then fall back to file path.

        This attempts to read tools.yaml from package data (works for installed
        wheels and editable installs). If that fails, it falls back to the file
        system path computed in __init__, and finally returns an empty dict on
        error.
        """
        # Try to load tools.yaml from package resources (preferred)
        try:
            import importlib.resources as pkg_resources
        except Exception:
            pkg_resources = None

        if pkg_resources is not None:
            try:
                # Newer API (Python 3.9+)
                if hasattr(pkg_resources, "files"):
                    res = pkg_resources.files("code_assistant_manager").joinpath(
                        "tools.yaml"
                    )
                    if res and res.exists():
                        # as_file gives a pathlib.Path we can read from
                        with pkg_resources.as_file(res) as rf:
                            text = rf.read_text(encoding="utf-8")
                        data = yaml.safe_load(text) or {}
                        tools = data.get("tools", {})
                        return tools if isinstance(tools, dict) else {}
                else:
                    # Older API: open_text
                    try:
                        text = pkg_resources.open_text(
                            "code_assistant_manager", "tools.yaml"
                        ).read()
                        data = yaml.safe_load(text) or {}
                        tools = data.get("tools", {})
                        return tools if isinstance(tools, dict) else {}
                    except Exception as e:
                        # Older API failed, will fall through to filesystem-based loading
                        logger.debug(f"Failed to load via older API: {e}")
            except Exception as e:
                # Fall through to filesystem-based loading
                logger.debug(f"Failed to load from package resources: {e}")

        # Fallback: load from the configured filesystem path (legacy behavior)
        if not self.config_path or not self.config_path.exists():
            return {}
        try:
            with self.config_path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
        except (OSError, yaml.YAMLError):
            return {}

        tools = data.get("tools", {})
        return tools if isinstance(tools, dict) else {}

    def _ensure_loaded(self):
        if self._tools is None:
            self._tools = self._load()

    def reload(self):
        self._tools = self._load()

    def get_tool(self, tool_key: str) -> dict:
        self._ensure_loaded()
        entry = self._tools.get(tool_key, {})
        return entry if isinstance(entry, dict) else {}

    def get_install_command(self, tool_key: str) -> Optional[str]:
        tool = self.get_tool(tool_key)
        install_cmd = tool.get("install_cmd") if isinstance(tool, dict) else None
        if isinstance(install_cmd, str):
            return install_cmd.strip()
        return None


TOOL_REGISTRY = ToolRegistry()
