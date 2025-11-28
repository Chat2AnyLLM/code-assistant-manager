"""Skill management for Code Assistant Manager.

This package provides functionality to manage skills for AI coding assistants.
Skills are downloaded from GitHub repositories and installed to:
- Claude: ~/.claude/skills/
- Codex: ~/.codex/skills/
- Gemini: ~/.gemini/skills/
- Droid: ~/.factory/skills/
"""

from .base import BaseSkillHandler
from .handlers import (
    ClaudeSkillHandler,
    CodexSkillHandler,
    DroidSkillHandler,
    GeminiSkillHandler,
)
from .manager import VALID_APP_TYPES, SkillManager
from .models import Skill, SkillRepo

__all__ = [
    "Skill",
    "SkillRepo",
    "SkillManager",
    "BaseSkillHandler",
    "ClaudeSkillHandler",
    "CodexSkillHandler",
    "GeminiSkillHandler",
    "DroidSkillHandler",
    "VALID_APP_TYPES",
]
