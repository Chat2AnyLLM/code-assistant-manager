"""Copilot agent handler.

Minimal Copilot agent handler that installs agents (markdown files)
into a user-local Copilot agents directory.
"""

from pathlib import Path

from .base import BaseAgentHandler


class CopilotAgentHandler(BaseAgentHandler):
    """Agent handler for GitHub Copilot CLI.

    Copilot agents are supported as markdown instruction files. By convention
    place them under ~/.copilot/agents/ or the client's agents directory.
    """

    @property
    def app_name(self) -> str:
        return "copilot"

    @property
    def _default_agents_dir(self) -> Path:
        return Path.home() / ".copilot" / "agents"
