"""Prompt management for Code Assistant Manager.

This module provides functionality to manage prompts for AI coding assistants.
Prompts can be synced to the actual tool config files at user or project level:

User level (default):
- Claude: ~/.claude/CLAUDE.md
- Codex: ~/.codex/AGENTS.md
- Gemini: ~/.gemini/GEMINI.md

Project level (current directory):
- Claude: ./CLAUDE.md
- Codex: ./AGENTS.md
- Gemini: ./GEMINI.md
"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# User-level prompt file paths for each app type
USER_PROMPT_FILE_PATHS = {
    "claude": Path.home() / ".claude" / "CLAUDE.md",
    "codex": Path.home() / ".codex" / "AGENTS.md",
    "gemini": Path.home() / ".gemini" / "GEMINI.md",
}

# Project-level prompt file names for each app type
PROJECT_PROMPT_FILE_NAMES = {
    "claude": "CLAUDE.md",
    "codex": "AGENTS.md",
    "gemini": "GEMINI.md",
}

# Keep for backward compatibility
PROMPT_FILE_PATHS = USER_PROMPT_FILE_PATHS


def get_prompt_file_path(
    app_type: str, level: str = "user", project_dir: Optional[Path] = None
) -> Optional[Path]:
    """
    Get the prompt file path for an app type at the specified level.

    Args:
        app_type: The app type (claude, codex, gemini)
        level: Either "user" or "project"
        project_dir: Project directory (defaults to current working directory)

    Returns:
        Path to the prompt file, or None if invalid
    """
    if level == "user":
        return USER_PROMPT_FILE_PATHS.get(app_type)
    elif level == "project":
        filename = PROJECT_PROMPT_FILE_NAMES.get(app_type)
        if not filename:
            return None
        if project_dir is None:
            project_dir = Path.cwd()
        return project_dir / filename
    return None


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
    ):
        self.id = id
        self.name = name
        self.content = content
        self.description = description
        self.enabled = enabled
        self.app_type = app_type  # claude, codex, gemini, or None for all
        self.created_at = created_at or int(datetime.now().timestamp() * 1000)
        self.updated_at = updated_at or int(datetime.now().timestamp() * 1000)

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
        )


class PromptManager:
    """Manages prompts storage and retrieval."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize prompt manager."""
        if config_dir is None:
            config_dir = Path.home() / ".config" / "code-assistant-manager"
        self.config_dir = Path(config_dir)
        self.prompts_file = self.config_dir / "prompts.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load_prompts(self) -> Dict[str, Prompt]:
        """Load prompts from file."""
        if not self.prompts_file.exists():
            return {}

        try:
            with open(self.prompts_file, "r") as f:
                data = json.load(f)
            return {
                prompt_id: Prompt.from_dict(prompt_data)
                for prompt_id, prompt_data in data.items()
            }
        except Exception as e:
            logger.warning(f"Failed to load prompts: {e}")
            return {}

    def _save_prompts(self, prompts: Dict[str, Prompt]) -> None:
        """Save prompts to file."""
        try:
            data = {
                prompt_id: prompt.to_dict() for prompt_id, prompt in prompts.items()
            }
            with open(self.prompts_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(prompts)} prompts to {self.prompts_file}")
        except Exception as e:
            logger.error(f"Failed to save prompts: {e}")
            raise

    def get_all(self) -> Dict[str, Prompt]:
        """Get all prompts."""
        return self._load_prompts()

    def get(self, prompt_id: str) -> Optional[Prompt]:
        """Get a specific prompt."""
        prompts = self._load_prompts()
        return prompts.get(prompt_id)

    def create(self, prompt: Prompt) -> None:
        """Create a new prompt."""
        prompts = self._load_prompts()
        if prompt.id in prompts:
            raise ValueError(f"Prompt with id '{prompt.id}' already exists")
        prompts[prompt.id] = prompt
        self._save_prompts(prompts)
        logger.info(f"Created prompt: {prompt.id}")

    def update(self, prompt: Prompt) -> None:
        """Update an existing prompt."""
        prompts = self._load_prompts()
        if prompt.id not in prompts:
            raise ValueError(f"Prompt with id '{prompt.id}' not found")
        prompt.updated_at = int(datetime.now().timestamp() * 1000)
        prompts[prompt.id] = prompt
        self._save_prompts(prompts)
        logger.info(f"Updated prompt: {prompt.id}")

    def upsert(self, prompt: Prompt) -> None:
        """Create or update a prompt."""
        prompts = self._load_prompts()
        prompt.updated_at = int(datetime.now().timestamp() * 1000)
        prompts[prompt.id] = prompt
        self._save_prompts(prompts)
        logger.info(f"Upserted prompt: {prompt.id}")

    def delete(self, prompt_id: str) -> None:
        """Delete a prompt."""
        prompts = self._load_prompts()
        if prompt_id not in prompts:
            raise ValueError(f"Prompt with id '{prompt_id}' not found")
        del prompts[prompt_id]
        self._save_prompts(prompts)
        logger.info(f"Deleted prompt: {prompt_id}")

    def enable(self, prompt_id: str) -> None:
        """Enable a prompt."""
        prompts = self._load_prompts()
        if prompt_id not in prompts:
            raise ValueError(f"Prompt with id '{prompt_id}' not found")
        prompts[prompt_id].enabled = True
        prompts[prompt_id].updated_at = int(datetime.now().timestamp() * 1000)
        self._save_prompts(prompts)
        logger.info(f"Enabled prompt: {prompt_id}")

    def disable(self, prompt_id: str) -> None:
        """Disable a prompt."""
        prompts = self._load_prompts()
        if prompt_id not in prompts:
            raise ValueError(f"Prompt with id '{prompt_id}' not found")
        prompts[prompt_id].enabled = False
        prompts[prompt_id].updated_at = int(datetime.now().timestamp() * 1000)
        self._save_prompts(prompts)
        logger.info(f"Disabled prompt: {prompt_id}")

    def import_from_file(self, file_path: Path) -> None:
        """Import prompts from a JSON file."""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            prompts = self._load_prompts()
            imported_count = 0

            if isinstance(data, dict):
                # Format: {"id": {...}, "id2": {...}}
                for prompt_id, prompt_data in data.items():
                    if isinstance(prompt_data, dict):
                        prompt = Prompt.from_dict(prompt_data)
                        prompts[prompt.id] = prompt
                        imported_count += 1
            elif isinstance(data, list):
                # Format: [{...}, {...}]
                for prompt_data in data:
                    if isinstance(prompt_data, dict):
                        prompt = Prompt.from_dict(prompt_data)
                        prompts[prompt.id] = prompt
                        imported_count += 1

            self._save_prompts(prompts)
            logger.info(f"Imported {imported_count} prompts from {file_path}")
        except Exception as e:
            logger.error(f"Failed to import prompts: {e}")
            raise

    def export_to_file(self, file_path: Path) -> None:
        """Export prompts to a JSON file."""
        try:
            prompts = self._load_prompts()
            data = {
                prompt_id: prompt.to_dict() for prompt_id, prompt in prompts.items()
            }
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Exported {len(prompts)} prompts to {file_path}")
        except Exception as e:
            logger.error(f"Failed to export prompts: {e}")
            raise

    def activate(
        self,
        prompt_id: str,
        app_type: str = "claude",
        level: str = "user",
        project_dir: Optional[Path] = None,
    ) -> None:
        """
        Activate a prompt by syncing it to the app's prompt file.

        Args:
            prompt_id: The prompt identifier
            app_type: The app type (claude, codex, gemini)
            level: Target scope ("user" or "project")
            project_dir: Project directory when targeting project scope
        """
        if level not in ("user", "project"):
            raise ValueError(f"Invalid level: {level}")

        prompts = self._load_prompts()
        if prompt_id not in prompts:
            raise ValueError(f"Prompt with id '{prompt_id}' not found")

        prompt = prompts[prompt_id]
        target_file = get_prompt_file_path(app_type, level, project_dir)
        if not target_file:
            raise ValueError(f"Unknown app type: {app_type}")

        # Backup existing prompt content from the live file first
        self._backup_live_prompt(app_type, level, project_dir)

        prompt.updated_at = int(datetime.now().timestamp() * 1000)

        if level == "user":
            # Disable all other prompts for this app type
            for p in prompts.values():
                if p.app_type == app_type or p.app_type is None:
                    p.enabled = False

            # Enable the selected prompt for user scope tracking
            prompt.enabled = True
            prompt.app_type = app_type
        else:
            # Ensure app type is recorded even if not tracking enabled state
            if not prompt.app_type:
                prompt.app_type = app_type

        # Sync to the target prompt file
        self._sync_prompt_to_file(prompt.content, app_type, level, project_dir)

        # Save changes (updates timestamps and activation state)
        self._save_prompts(prompts)
        logger.info(
            f"Activated prompt: {prompt_id} for {app_type} ({level} scope -> {target_file})"
        )

    def deactivate(self, prompt_id: str) -> None:
        """
        Deactivate a prompt.

        Args:
            prompt_id: The prompt identifier
        """
        prompts = self._load_prompts()
        if prompt_id not in prompts:
            raise ValueError(f"Prompt with id '{prompt_id}' not found")

        prompt = prompts[prompt_id]
        prompt.enabled = False
        prompt.updated_at = int(datetime.now().timestamp() * 1000)

        self._save_prompts(prompts)
        logger.info(f"Deactivated prompt: {prompt_id}")

    def _sync_prompt_to_file(
        self,
        content: str,
        app_type: str,
        level: str = "user",
        project_dir: Optional[Path] = None,
    ) -> None:
        """
        Write prompt content to the app's prompt file.

        Args:
            content: The prompt content
            app_type: The app type (claude, codex, gemini)
            level: Target scope ("user" or "project")
            project_dir: Project directory when targeting project scope
        """
        file_path = get_prompt_file_path(app_type, level, project_dir)
        if not file_path:
            raise ValueError(f"Unknown app type: {app_type}")

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write atomically using temp file
        temp_path = file_path.with_suffix(".tmp")
        try:
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(file_path)
            logger.info(f"Synced prompt to: {file_path}")
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def _backup_live_prompt(
        self,
        app_type: str,
        level: str = "user",
        project_dir: Optional[Path] = None,
    ) -> Optional[str]:
        """
        Backup the current live prompt file content.

        Args:
            app_type: The app type (claude, codex, gemini)
            level: Target scope ("user" or "project")
            project_dir: Project directory when targeting project scope

        Returns:
            The prompt ID if a backup was created, None otherwise
        """
        file_path = get_prompt_file_path(app_type, level, project_dir)
        if not file_path or not file_path.exists():
            return None

        try:
            content = file_path.read_text(encoding="utf-8")
            if not content.strip():
                return None

            # Check if this content already exists in our prompts
            prompts = self._load_prompts()
            for prompt in prompts.values():
                if prompt.content.strip() == content.strip():
                    return None

            # Check if the currently enabled prompt matches the live content
            for prompt in prompts.values():
                if prompt.enabled and prompt.app_type == app_type:
                    if prompt.content.strip() == content.strip():
                        return None
                    # Content differs - update the enabled prompt with live content
                    prompt.content = content
                    prompt.updated_at = int(datetime.now().timestamp() * 1000)
                    self._save_prompts(prompts)
                    logger.info(f"Backfilled live content to prompt: {prompt.id}")
                    return prompt.id

            # Create a backup prompt
            timestamp = int(datetime.now().timestamp())
            scope_label = f"{level} " if level != "user" else ""
            backup_id = f"backup-{level}-{app_type}-{timestamp}"
            backup_prompt = Prompt(
                id=backup_id,
                name=f"Backup from {scope_label}{app_type.capitalize()} ({datetime.now().strftime('%Y-%m-%d %H:%M')})".strip(),
                content=content,
                description=f"Auto-backup of {file_path.name}",
                enabled=False,
                app_type=app_type,
            )
            prompts[backup_id] = backup_prompt
            self._save_prompts(prompts)
            logger.info(f"Created backup prompt: {backup_id}")
            return backup_id

        except Exception as e:
            logger.warning(f"Failed to backup live prompt: {e}")
            return None

    def get_live_content(
        self,
        app_type: str,
        level: str = "user",
        project_dir: Optional[Path] = None,
    ) -> Optional[str]:
        """
        Get the current content of the app's prompt file.

        Args:
            app_type: The app type (claude, codex, gemini)
            level: Prompt level ("user" or "project")
            project_dir: Optional project directory for project level prompts

        Returns:
            The content of the prompt file, or None if it doesn't exist
        """
        file_path = get_prompt_file_path(app_type, level, project_dir)
        if not file_path or not file_path.exists():
            return None

        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read live prompt: {e}")
            return None

    def import_from_live(
        self,
        app_type: str,
        name: Optional[str] = None,
        level: str = "user",
        project_dir: Optional[Path] = None,
    ) -> Optional[str]:
        """
        Import the current live prompt file as a new prompt.

        Args:
            app_type: The app type (claude, codex, gemini)
            name: Optional name for the imported prompt
            level: Prompt level ("user" or "project")
            project_dir: Optional project directory for project level prompts

        Returns:
            The prompt ID if import was successful, None otherwise
        """
        file_path = get_prompt_file_path(app_type, level, project_dir)
        if not file_path or not file_path.exists():
            return None

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read prompt file {file_path}: {e}")
            return None

        if not content or not content.strip():
            return None

        prompts = self._load_prompts()
        stripped_content = content.strip()
        for prompt in prompts.values():
            if prompt.content.strip() == stripped_content and (
                prompt.app_type == app_type or prompt.app_type is None
            ):
                logger.info(
                    "Live prompt content already stored as prompt %s", prompt.id
                )
                return prompt.id

        timestamp = int(datetime.now().timestamp())
        prompt_id = f"imported-{level}-{app_type}-{timestamp}"

        if not name:
            level_label = "User" if level == "user" else "Project"
            name = f"Imported from {level_label} {app_type.capitalize()} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"

        prompt = Prompt(
            id=prompt_id,
            name=name,
            content=content,
            description=f"Imported from {file_path}",
            enabled=False,
            app_type=app_type,
        )

        prompts[prompt_id] = prompt
        self._save_prompts(prompts)

        logger.info(f"Imported prompt: {prompt_id}")
        return prompt_id

    def get_active_prompt(self, app_type: str) -> Optional[Prompt]:
        """
        Get the currently active prompt for an app type.

        Args:
            app_type: The app type (claude, codex, gemini)

        Returns:
            The active prompt, or None if no prompt is active
        """
        prompts = self._load_prompts()
        for prompt in prompts.values():
            if prompt.enabled and (
                prompt.app_type == app_type or prompt.app_type is None
            ):
                return prompt
        return None

    def sync_all(self) -> Dict[str, Optional[str]]:
        """
        Sync all active prompts to their respective app files.

        Returns:
            Dictionary mapping app types to prompt ID synced (or None if no prompt)
        """
        prompts = self._load_prompts()
        results = {}

        for app_type in PROMPT_FILE_PATHS.keys():
            # Find active prompt for this app type
            active_prompt = None
            for prompt in prompts.values():
                if prompt.enabled and (
                    prompt.app_type == app_type or prompt.app_type is None
                ):
                    active_prompt = prompt
                    break

            if active_prompt:
                try:
                    self._sync_prompt_to_file(active_prompt.content, app_type)
                    results[app_type] = active_prompt.id
                except Exception as e:
                    logger.error(f"Failed to sync prompt to {app_type}: {e}")
                    results[app_type] = None
            else:
                results[app_type] = None  # No active prompt

        return results
