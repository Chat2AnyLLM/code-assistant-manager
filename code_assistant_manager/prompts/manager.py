"""Prompt manager that coordinates all tool-specific handlers."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Type

from .base import BasePromptHandler
from .claude import ClaudePromptHandler
from .codex import CodexPromptHandler
from .copilot import CopilotPromptHandler
from .gemini import GeminiPromptHandler
from .models import Prompt

logger = logging.getLogger(__name__)

# Registry of all available prompt handlers
PROMPT_HANDLERS: Dict[str, Type[BasePromptHandler]] = {
    "claude": ClaudePromptHandler,
    "codex": CodexPromptHandler,
    "gemini": GeminiPromptHandler,
    "copilot": CopilotPromptHandler,
}

# Valid app types
VALID_APP_TYPES = list(PROMPT_HANDLERS.keys())


def get_handler(app_type: str) -> BasePromptHandler:
    """Get a prompt handler instance for the specified app type."""
    handler_class = PROMPT_HANDLERS.get(app_type)
    if not handler_class:
        raise ValueError(f"Unknown app type: {app_type}. Valid: {VALID_APP_TYPES}")
    return handler_class()


class PromptManager:
    """Manages prompts storage and retrieval across all tools."""

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        handler_overrides: Optional[Dict[str, Dict]] = None,
    ):
        """Initialize prompt manager.

        Args:
            config_dir: Configuration directory for prompt storage
            handler_overrides: Dict of app_type -> {'user_path': Path, 'project_filename': str}
                              for testing purposes
        """
        if config_dir is None:
            config_dir = Path.home() / ".config" / "code-assistant-manager"
        self.config_dir = Path(config_dir)
        self.prompts_file = self.config_dir / "prompts.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Initialize handlers with optional overrides
        self._handlers: Dict[str, BasePromptHandler] = {}
        for name, cls in PROMPT_HANDLERS.items():
            overrides = (handler_overrides or {}).get(name, {})
            self._handlers[name] = cls(
                user_path_override=overrides.get("user_path"),
                project_filename_override=overrides.get("project_filename"),
            )

    def get_handler(self, app_type: str) -> BasePromptHandler:
        """Get the handler for a specific app type."""
        handler = self._handlers.get(app_type)
        if not handler:
            raise ValueError(f"Unknown app type: {app_type}. Valid: {VALID_APP_TYPES}")
        return handler

    @property
    def copilot(self) -> CopilotPromptHandler:
        """Get the Copilot handler for Copilot-specific operations."""
        return self._handlers["copilot"]  # type: ignore

    # ==================== Prompt Storage Operations ====================

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

    # ==================== Tool Sync Operations ====================

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
            app_type: The app type (claude, codex, gemini, copilot)
            level: Target scope ("user" or "project")
            project_dir: Project directory when targeting project scope
        """
        if level not in ("user", "project"):
            raise ValueError(f"Invalid level: {level}")

        handler = self.get_handler(app_type)
        prompts = self._load_prompts()

        if prompt_id not in prompts:
            raise ValueError(f"Prompt with id '{prompt_id}' not found")

        prompt = prompts[prompt_id]

        # Check if level is supported
        target_file = handler.get_prompt_file_path(level, project_dir)
        if not target_file:
            raise ValueError(f"Tool '{app_type}' does not support level '{level}'")

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

        # Sync to the target prompt file using the handler
        handler.sync_prompt(prompt.content, level, project_dir)

        # Save changes (updates timestamps and activation state)
        self._save_prompts(prompts)
        logger.info(
            f"Activated prompt: {prompt_id} for {app_type} ({level} scope -> {target_file})"
        )

    def deactivate(self, prompt_id: str) -> None:
        """Deactivate a prompt."""
        prompts = self._load_prompts()
        if prompt_id not in prompts:
            raise ValueError(f"Prompt with id '{prompt_id}' not found")

        prompt = prompts[prompt_id]
        prompt.enabled = False
        prompt.updated_at = int(datetime.now().timestamp() * 1000)

        self._save_prompts(prompts)
        logger.info(f"Deactivated prompt: {prompt_id}")

    def _backup_live_prompt(
        self,
        app_type: str,
        level: str = "user",
        project_dir: Optional[Path] = None,
    ) -> Optional[str]:
        """Backup the current live prompt file content."""
        handler = self.get_handler(app_type)
        file_path = handler.get_prompt_file_path(level, project_dir)

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
        """Get the current content of the app's prompt file."""
        handler = self.get_handler(app_type)
        return handler.get_live_content(level, project_dir)

    def import_from_live(
        self,
        app_type: str,
        name: Optional[str] = None,
        level: str = "user",
        project_dir: Optional[Path] = None,
    ) -> Optional[str]:
        """Import the current live prompt file as a new prompt."""
        handler = self.get_handler(app_type)
        result = handler.import_from_live(level, project_dir)

        if not result:
            return None

        content = result["content"]
        file_path = result["file_path"]

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
        """Get the currently active prompt for an app type."""
        prompts = self._load_prompts()
        for prompt in prompts.values():
            if prompt.enabled and (
                prompt.app_type == app_type or prompt.app_type is None
            ):
                return prompt
        return None

    def sync_all(self) -> Dict[str, Optional[str]]:
        """Sync all active prompts to their respective app files."""
        prompts = self._load_prompts()
        results = {}

        # Only sync to tools that support user-level prompts
        for app_type, handler in self._handlers.items():
            if not handler.user_prompt_path:
                continue

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
                    handler.sync_prompt(active_prompt.content, "user")
                    results[app_type] = active_prompt.id
                except Exception as e:
                    logger.error(f"Failed to sync prompt to {app_type}: {e}")
                    results[app_type] = None
            else:
                results[app_type] = None  # No active prompt

        return results

    # ==================== Copilot-Specific Operations ====================

    def sync_copilot_instructions(
        self,
        prompt_id: str,
        instruction_type: str = "repo-wide",
        apply_to: Optional[str] = None,
        exclude_agent: Optional[str] = None,
        project_dir: Optional[Path] = None,
    ) -> None:
        """
        Sync a prompt to Copilot instructions file.

        Args:
            prompt_id: The prompt identifier
            instruction_type: "repo-wide" or "path-specific"
            apply_to: Glob pattern (required for path-specific)
            exclude_agent: Optional agent to exclude
            project_dir: Project directory (defaults to current working directory)
        """
        if project_dir is None:
            project_dir = Path.cwd()

        prompts = self._load_prompts()
        if prompt_id not in prompts:
            raise ValueError(f"Prompt with id '{prompt_id}' not found")

        prompt = prompts[prompt_id]
        prompt.instruction_type = instruction_type
        prompt.apply_to = apply_to
        prompt.exclude_agent = exclude_agent

        copilot = self.copilot

        if instruction_type == "repo-wide":
            copilot.sync_repo_wide(prompt.content, project_dir)
        elif instruction_type == "path-specific":
            if not apply_to:
                raise ValueError("apply_to is required for path-specific instructions")
            copilot.sync_path_specific(
                prompt.id, prompt.content, apply_to, exclude_agent, project_dir
            )
        else:
            raise ValueError(f"Unknown instruction type: {instruction_type}")

        prompt.updated_at = int(datetime.now().timestamp() * 1000)
        self._save_prompts(prompts)
        logger.info(
            f"Synced prompt {prompt_id} to Copilot {instruction_type} instructions"
        )

    def import_copilot_instructions(
        self,
        instruction_type: str = "repo-wide",
        name: Optional[str] = None,
        project_dir: Optional[Path] = None,
    ) -> Optional[str]:
        """Import Copilot instructions as a new prompt."""
        if project_dir is None:
            project_dir = Path.cwd()

        if instruction_type != "repo-wide":
            raise ValueError(
                "Only 'repo-wide' import is supported. For path-specific, import individual files."
            )

        result = self.copilot.import_repo_wide(project_dir)
        if not result:
            return None

        content = result["content"]
        file_path = result["file_path"]

        prompts = self._load_prompts()
        stripped_content = content.strip()
        for prompt in prompts.values():
            if (
                prompt.content.strip() == stripped_content
                and prompt.instruction_type == instruction_type
            ):
                logger.info(
                    "Copilot instructions already stored as prompt %s", prompt.id
                )
                return prompt.id

        timestamp = int(datetime.now().timestamp())
        prompt_id = f"copilot-{instruction_type}-{timestamp}"

        if not name:
            name = f"Copilot {instruction_type} instructions ({datetime.now().strftime('%Y-%m-%d %H:%M')})"

        prompt = Prompt(
            id=prompt_id,
            name=name,
            content=content,
            description=f"Imported from {file_path}",
            enabled=False,
            instruction_type=instruction_type,
        )

        prompts[prompt_id] = prompt
        self._save_prompts(prompts)

        logger.info(f"Imported Copilot instructions: {prompt_id}")
        return prompt_id

    def get_copilot_instructions(
        self, project_dir: Optional[Path] = None, instruction_type: str = "repo-wide"
    ) -> Optional[str]:
        """Get current Copilot instructions content from file."""
        if instruction_type == "repo-wide":
            return self.copilot.get_repo_wide_content(project_dir)
        else:
            # For path-specific, just return the directory path info
            return None
