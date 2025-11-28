"""App-specific skill handlers."""

from pathlib import Path

from .base import BaseSkillHandler


class ClaudeSkillHandler(BaseSkillHandler):
    """Skill handler for Claude Code."""

    @property
    def app_name(self) -> str:
        return "claude"

    @property
    def _default_skills_dir(self) -> Path:
        return Path.home() / ".claude" / "skills"


class CodexSkillHandler(BaseSkillHandler):
    """Skill handler for OpenAI Codex CLI."""

    @property
    def app_name(self) -> str:
        return "codex"

    @property
    def _default_skills_dir(self) -> Path:
        return Path.home() / ".codex" / "skills"


class GeminiSkillHandler(BaseSkillHandler):
    """Skill handler for Google Gemini CLI."""

    @property
    def app_name(self) -> str:
        return "gemini"

    @property
    def _default_skills_dir(self) -> Path:
        return Path.home() / ".gemini" / "skills"


class DroidSkillHandler(BaseSkillHandler):
    """Skill handler for Factory.ai Droid CLI."""

    @property
    def app_name(self) -> str:
        return "droid"

    @property
    def _default_skills_dir(self) -> Path:
        return Path.home() / ".factory" / "skills"
