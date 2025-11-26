"""Prompt data models."""

from datetime import datetime
from typing import Dict, Optional


class Prompt:
    """Represents a prompt configuration."""

    def __init__(
        self,
        id: str,
        name: str,
        content: str,
        description: Optional[str] = None,
        enabled: bool = False,
        app_type: Optional[str] = None,
        created_at: Optional[int] = None,
        updated_at: Optional[int] = None,
        instruction_type: Optional[str] = None,  # "repo-wide", "path-specific", or None
        apply_to: Optional[str] = None,  # Glob pattern for path-specific instructions
        exclude_agent: Optional[str] = None,  # "coding-agent" or "code-review"
    ):
        self.id = id
        self.name = name
        self.content = content
        self.description = description
        self.enabled = enabled
        self.app_type = app_type  # claude, codex, gemini, copilot, or None for all
        self.created_at = created_at or int(datetime.now().timestamp() * 1000)
        self.updated_at = updated_at or int(datetime.now().timestamp() * 1000)
        self.instruction_type = instruction_type  # Type of instructions (for Copilot)
        self.apply_to = apply_to  # Glob pattern for path-specific instructions
        self.exclude_agent = exclude_agent  # Exclude certain agents

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = {
            "id": self.id,
            "name": self.name,
            "content": self.content,
            "enabled": self.enabled,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
        if self.description:
            data["description"] = self.description
        if self.app_type:
            data["appType"] = self.app_type
        if self.instruction_type:
            data["instructionType"] = self.instruction_type
        if self.apply_to:
            data["applyTo"] = self.apply_to
        if self.exclude_agent:
            data["excludeAgent"] = self.exclude_agent
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "Prompt":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            content=data["content"],
            description=data.get("description"),
            enabled=data.get("enabled", False),
            app_type=data.get("appType"),
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
            instruction_type=data.get("instructionType"),
            apply_to=data.get("applyTo"),
            exclude_agent=data.get("excludeAgent"),
        )
