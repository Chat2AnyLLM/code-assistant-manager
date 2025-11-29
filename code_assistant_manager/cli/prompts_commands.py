"""CLI commands for prompt management."""

import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional

import typer

from code_assistant_manager.cli.option_utils import (
    ensure_project_dir,
    resolve_level_targets,
)
from code_assistant_manager.menu.base import Colors
from code_assistant_manager.prompts import (
    PROMPT_FILE_PATHS,
    Prompt,
    PromptManager,
    get_handler,
    get_prompt_file_path,
)

logger = logging.getLogger(__name__)

prompt_app = typer.Typer(
    help="Manage prompts for AI assistants (Claude, Codex, Gemini, Copilot)",
    no_args_is_help=True,
)

# Valid app types - copilot is special (project-level only with different structure)
VALID_APP_TYPES = ["claude", "codex", "gemini", "copilot"]
# Apps that support user-level prompts
USER_LEVEL_APPS = ["claude", "codex", "gemini"]
VALID_LEVELS = ["user", "project"]


def _get_prompt_manager() -> PromptManager:
    """Get prompt manager instance."""
    return PromptManager()


def generate_prompt_id(prefix: str = "prompt") -> str:
    """Generate a unique prompt ID with a short UUID suffix."""
    short_uuid = uuid.uuid4().hex[:8]
    return f"{prefix}-{short_uuid}"


def _parse_app_list(app_str: str) -> List[str]:
    """Parse comma-separated app list and validate."""
    if app_str.lower() == "all":
        return VALID_APP_TYPES.copy()

    apps = [a.strip().lower() for a in app_str.split(",")]
    invalid = [a for a in apps if a not in VALID_APP_TYPES]
    if invalid:
        raise typer.BadParameter(
            f"Invalid app(s): {', '.join(invalid)}. Valid: {', '.join(VALID_APP_TYPES)}"
        )
    return apps


@prompt_app.command("list")
def list_prompts():
    """List all prompts."""
    manager = _get_prompt_manager()
    prompts = manager.get_all()

    if not prompts:
        typer.echo(f"{Colors.YELLOW}No prompts found{Colors.RESET}")
        return

    typer.echo(f"\n{Colors.BOLD}Prompts:{Colors.RESET}\n")
    for prompt_id, prompt in sorted(prompts.items()):
        # Check if this prompt is active for any apps by comparing content
        active_apps = []
        for app_type in VALID_APP_TYPES:
            try:
                if app_type == "copilot":
                    # Copilot uses project level
                    live_content = manager.get_copilot_instructions()
                else:
                    # Other apps use user level
                    live_content = manager.get_live_content(app_type, level="user")

                if live_content and live_content.strip() == prompt.content.strip():
                    active_apps.append(app_type.capitalize())
            except Exception:
                # Ignore errors when checking live content
                pass

        status_parts = []
        if prompt.is_default:
            status_parts.append(f"{Colors.GREEN}★ default{Colors.RESET}")
        if active_apps:
            status_parts.append(
                f"{Colors.BLUE}linked: {', '.join(active_apps)}{Colors.RESET}"
            )

        if status_parts:
            status = " | ".join(status_parts)
        else:
            status = f"{Colors.CYAN}○{Colors.RESET}"

        typer.echo(f"{status} {Colors.BOLD}{prompt.name}{Colors.RESET}")
        typer.echo(f"  {Colors.CYAN}ID:{Colors.RESET} {prompt_id}")
        if prompt.description:
            typer.echo(
                f"  {Colors.CYAN}Description:{Colors.RESET} {prompt.description}"
            )
        typer.echo()


@prompt_app.command("view")
def view_prompt(prompt_id: str):
    """View a specific prompt."""
    manager = _get_prompt_manager()
    prompt = manager.get(prompt_id)

    if not prompt:
        typer.echo(f"{Colors.RED}✗ Prompt '{prompt_id}' not found{Colors.RESET}")
        raise typer.Exit(1)

    typer.echo(f"\n{Colors.BOLD}Prompt: {prompt.name}{Colors.RESET}")
    if prompt.description:
        typer.echo(f"{Colors.CYAN}Description:{Colors.RESET} {prompt.description}")
    status = (
        f"{Colors.GREEN}default{Colors.RESET}"
        if prompt.is_default
        else f"{Colors.CYAN}not default{Colors.RESET}"
    )
    typer.echo(f"{Colors.CYAN}Status:{Colors.RESET} {status}")
    typer.echo(f"{Colors.CYAN}ID:{Colors.RESET} {prompt_id}")
    typer.echo(f"\n{Colors.CYAN}Content:{Colors.RESET}\n")
    typer.echo(prompt.content)
    typer.echo()


@prompt_app.command("create")
def create_prompt(
    prompt_id: str = typer.Argument(..., help="Unique identifier for the prompt"),
    name: str = typer.Option(..., "--name", "-n", help="Prompt name"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Prompt description"
    ),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Read content from file"
    ),
):
    """Create a new prompt."""
    manager = _get_prompt_manager()

    if file and file.exists():
        content = file.read_text()
    else:
        typer.echo(
            f"{Colors.CYAN}Enter prompt content (press Ctrl+D or Ctrl+Z when done):{Colors.RESET}"
        )
        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass
        content = "\n".join(lines)

    if not content.strip():
        typer.echo(f"{Colors.RED}✗ Prompt content cannot be empty{Colors.RESET}")
        raise typer.Exit(1)

    try:
        prompt = Prompt(
            id=prompt_id,
            name=name,
            content=content,
            description=description,
        )
        manager.create(prompt)
        typer.echo(f"{Colors.GREEN}✓ Prompt created: {prompt_id}{Colors.RESET}")
    except ValueError as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@prompt_app.command("update")
def update_prompt(
    prompt_id: str = typer.Argument(..., help="Prompt identifier"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New prompt name"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="New prompt description"
    ),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Read new content from file"
    ),
):
    """Update an existing prompt."""
    manager = _get_prompt_manager()
    prompt = manager.get(prompt_id)

    if not prompt:
        typer.echo(f"{Colors.RED}✗ Prompt '{prompt_id}' not found{Colors.RESET}")
        raise typer.Exit(1)

    # Update fields if provided
    if name:
        prompt.name = name
    if description:
        prompt.description = description
    if file and file.exists():
        prompt.content = file.read_text()

    try:
        manager.update(prompt)
        typer.echo(f"{Colors.GREEN}✓ Prompt updated: {prompt_id}{Colors.RESET}")
    except ValueError as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@prompt_app.command("delete")
def delete_prompt(
    prompt_id: str = typer.Argument(..., help="Prompt identifier"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a prompt."""
    manager = _get_prompt_manager()
    prompt = manager.get(prompt_id)

    if not prompt:
        typer.echo(f"{Colors.RED}✗ Prompt '{prompt_id}' not found{Colors.RESET}")
        raise typer.Exit(1)

    if not force:
        typer.confirm(f"Delete prompt '{prompt.name}' ({prompt_id})?", abort=True)

    try:
        manager.delete(prompt_id)
        typer.echo(f"{Colors.GREEN}✓ Prompt deleted: {prompt_id}{Colors.RESET}")
    except ValueError as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@prompt_app.command("set-default")
def set_default_prompt(
    prompt_id: str = typer.Argument(..., help="Prompt identifier to set as default"),
):
    """Set a prompt as the default prompt.

    The default prompt is used when running 'sync' without specifying a prompt ID.
    Only one prompt can be the default at a time.
    """
    manager = _get_prompt_manager()
    prompt = manager.get(prompt_id)

    if not prompt:
        typer.echo(f"{Colors.RED}✗ Prompt '{prompt_id}' not found{Colors.RESET}")
        raise typer.Exit(1)

    try:
        manager.set_default(prompt_id)
        typer.echo(f"{Colors.GREEN}✓ Set '{prompt_id}' as default prompt{Colors.RESET}")
    except ValueError as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@prompt_app.command("clear-default")
def clear_default_prompt():
    """Clear the default prompt setting."""
    manager = _get_prompt_manager()

    try:
        manager.clear_default()
        typer.echo(f"{Colors.GREEN}✓ Cleared default prompt{Colors.RESET}")
    except ValueError as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@prompt_app.command("sync")
def sync_prompts(
    prompt_id: Optional[str] = typer.Argument(
        None, help="Prompt ID to sync. If not specified, syncs the default prompt."
    ),
    app_type: Optional[str] = typer.Option(
        None,
        "--app",
        "-a",
        help="App(s) to sync to, comma-separated (e.g., 'claude,codex,gemini' or 'all'). Default: all user-level apps.",
    ),
    level: str = typer.Option(
        "user",
        "--level",
        "-l",
        help="Sync level: 'user' (~/.claude/) or 'project' (current directory). Copilot only supports 'project'.",
    ),
    project_dir: Optional[Path] = typer.Option(
        None,
        "--project-dir",
        help="Project directory when using project level (defaults to current directory)",
    ),
    # Copilot-specific options
    apply_to: Optional[str] = typer.Option(
        None,
        "--apply-to",
        help="(Copilot only) Glob pattern for path-specific instructions",
    ),
    exclude_agent: Optional[str] = typer.Option(
        None,
        "--exclude-agent",
        help="(Copilot only) Exclude agent: 'coding-agent' or 'code-review'",
    ),
):
    """Sync prompts to app files.

    Without arguments: syncs the default prompt to all user-level apps (claude, codex, gemini).

    Examples:
        cam prompt sync                           # Sync default to all apps
        cam prompt sync my-prompt -a claude       # Sync specific prompt to claude
        cam prompt sync -a claude,codex           # Sync default to multiple apps
        cam prompt sync my-prompt -a copilot      # Sync to copilot
        cam prompt sync -a all -l project         # Sync default to all apps at project level
    """
    manager = _get_prompt_manager()

    # Determine which prompt to sync
    if prompt_id:
        prompt = manager.get(prompt_id)
        if not prompt:
            typer.echo(f"{Colors.RED}✗ Prompt not found: {prompt_id}{Colors.RESET}")
            raise typer.Exit(1)
    else:
        prompt = manager.get_default()
        if not prompt:
            typer.echo(
                f"{Colors.RED}✗ No default prompt set. Use 'set-default' first or specify a prompt ID.{Colors.RESET}"
            )
            raise typer.Exit(1)
        prompt_id = prompt.id

    # Determine target apps
    if app_type:
        try:
            target_apps = _parse_app_list(app_type)
        except typer.BadParameter as e:
            typer.echo(f"{Colors.RED}✗ {e}{Colors.RESET}")
            raise typer.Exit(1)
    else:
        # Default: all user-level apps for user level, all apps for project level
        target_apps = USER_LEVEL_APPS if level == "user" else VALID_APP_TYPES

    # Validate level
    if level not in VALID_LEVELS:
        typer.echo(
            f"{Colors.RED}✗ Invalid level: {level}. Valid: {', '.join(VALID_LEVELS)}{Colors.RESET}"
        )
        raise typer.Exit(1)

    # Resolve project directory for project level
    level_project_dir = (
        ensure_project_dir(level, project_dir if level == "project" else None)
        if level == "project"
        else None
    )

    # Sync to each target app
    for app in target_apps:
        # Handle Copilot specially
        if app == "copilot":
            if level == "user":
                typer.echo(
                    f"{Colors.YELLOW}○ copilot: skipped (project level only){Colors.RESET}"
                )
                continue
            _sync_copilot(
                manager, prompt_id, apply_to, exclude_agent, level_project_dir
            )
            continue

        # Skip apps that don't support user level if at user level
        if level == "user" and app not in USER_LEVEL_APPS:
            typer.echo(
                f"{Colors.YELLOW}○ {app}: skipped (no user level support){Colors.RESET}"
            )
            continue

        file_path = get_prompt_file_path(app, level, level_project_dir)
        if not file_path:
            typer.echo(f"{Colors.RED}✗ Unknown app type: {app}{Colors.RESET}")
            continue

        try:
            manager.sync_to_app(prompt_id, app, level, level_project_dir)
            typer.echo(
                f"{Colors.GREEN}✓ {app}: synced '{prompt_id}' ({level}){Colors.RESET}"
            )
            typer.echo(f"  {Colors.CYAN}File:{Colors.RESET} {file_path}")
        except Exception as e:
            typer.echo(f"{Colors.RED}✗ {app}: {e}{Colors.RESET}")


def _sync_copilot(
    manager: PromptManager,
    prompt_id: str,
    apply_to: Optional[str],
    exclude_agent: Optional[str],
    project_dir: Optional[Path],
):
    """Helper to sync a prompt to Copilot instructions."""
    prompt = manager.get(prompt_id)
    if not prompt:
        typer.echo(f"{Colors.RED}✗ Prompt not found: {prompt_id}{Colors.RESET}")
        raise typer.Exit(1)

    instruction_type = "path-specific" if apply_to else "repo-wide"

    try:
        manager.sync_copilot_instructions(
            prompt_id,
            instruction_type=instruction_type,
            apply_to=apply_to,
            exclude_agent=exclude_agent,
            project_dir=project_dir,
        )

        typer.echo(
            f"{Colors.GREEN}✓ copilot: synced '{prompt_id}' ({instruction_type}){Colors.RESET}"
        )

        if instruction_type == "repo-wide":
            typer.echo(
                f"  {Colors.CYAN}File:{Colors.RESET} .github/copilot-instructions.md"
            )
        else:
            typer.echo(
                f"  {Colors.CYAN}File:{Colors.RESET} .github/instructions/{prompt_id}.instructions.md"
            )
            typer.echo(f"  {Colors.CYAN}Apply to:{Colors.RESET} {apply_to}")
            if exclude_agent:
                typer.echo(
                    f"  {Colors.CYAN}Exclude agent:{Colors.RESET} {exclude_agent}"
                )

    except ValueError as e:
        typer.echo(f"{Colors.RED}✗ copilot: {e}{Colors.RESET}")
        raise typer.Exit(1)


@prompt_app.command("import-live")
def import_live_prompt(
    app_type: str = typer.Option(
        "all",
        "--app",
        "-a",
        help="App(s) to import from, comma-separated (e.g., 'claude,codex' or 'all')",
    ),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Name for the imported prompt"
    ),
    level: str = typer.Option(
        "user",
        "--level",
        "-l",
        help="Prompt level to import from: 'user', 'project', or 'all'. Copilot only supports 'project'.",
    ),
    project_dir: Optional[Path] = typer.Option(
        None,
        "--project-dir",
        help="Project directory when using project level (defaults to current directory)",
    ),
):
    """Import the current live prompt file as a new prompt.

    For Copilot, imports from .github/copilot-instructions.md
    """
    try:
        target_apps = _parse_app_list(app_type)
    except typer.BadParameter as e:
        typer.echo(f"{Colors.RED}✗ {e}{Colors.RESET}")
        raise typer.Exit(1)

    target_levels = resolve_level_targets(level, VALID_LEVELS, default="user")

    manager = _get_prompt_manager()
    multiple = len(target_apps) * len(target_levels) > 1

    # Track if we've imported copilot (to avoid duplicates)
    copilot_imported = False

    for lvl in target_levels:
        lvl_project_dir = (
            ensure_project_dir(lvl, project_dir if lvl == "project" else None)
            if lvl == "project"
            else None
        )

        for app in target_apps:
            # Handle Copilot specially - only project level
            if app == "copilot":
                if not copilot_imported:
                    copilot_project_dir = ensure_project_dir("project", project_dir)
                    _import_copilot(manager, name, copilot_project_dir)
                    copilot_imported = True
                continue

            prompt_name = name
            if name and multiple:
                prompt_name = f"{name} ({app}-{lvl})"

            prompt_id = manager.import_from_live(
                app,
                prompt_name,
                level=lvl,
                project_dir=lvl_project_dir,
            )
            file_path = get_prompt_file_path(app, lvl, lvl_project_dir)

            if prompt_id:
                typer.echo(
                    f"{Colors.GREEN}✓ Prompt imported: {prompt_id}{Colors.RESET}"
                )
                typer.echo(f"  {Colors.CYAN}From:{Colors.RESET} {file_path}")
            else:
                target = file_path or f"{lvl}:{app}"
                typer.echo(
                    f"{Colors.YELLOW}No content to import from {target}{Colors.RESET}"
                )


def _import_copilot(
    manager: PromptManager,
    name: Optional[str],
    project_dir: Optional[Path],
):
    """Helper to import Copilot instructions."""
    try:
        prompt_id = manager.import_copilot_instructions(
            instruction_type="repo-wide",
            name=name,
            project_dir=project_dir,
        )

        if prompt_id:
            typer.echo(f"{Colors.GREEN}✓ Prompt imported: {prompt_id}{Colors.RESET}")
            typer.echo(
                f"  {Colors.CYAN}From:{Colors.RESET} .github/copilot-instructions.md"
            )
        else:
            typer.echo(
                f"{Colors.YELLOW}No content to import from Copilot instructions{Colors.RESET}"
            )

    except Exception as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")


@prompt_app.command("show-live")
def show_live_prompt(
    app_type: str = typer.Option(
        "all",
        "--app",
        "-a",
        help="App(s) to show, comma-separated (e.g., 'claude,codex' or 'all')",
    ),
    level: str = typer.Option(
        "user",
        "--level",
        "-l",
        help="Prompt level to show: 'user', 'project', or 'all'. Copilot only supports 'project'.",
    ),
    project_dir: Optional[Path] = typer.Option(
        None,
        "--project-dir",
        help="Project directory when showing project prompts (defaults to current directory)",
    ),
):
    """Show the current live prompt file content.

    For Copilot, shows content from .github/copilot-instructions.md
    """
    try:
        target_apps = _parse_app_list(app_type)
    except typer.BadParameter as e:
        typer.echo(f"{Colors.RED}✗ {e}{Colors.RESET}")
        raise typer.Exit(1)

    target_levels = resolve_level_targets(level, VALID_LEVELS, default="user")

    manager = _get_prompt_manager()

    # Track if we've shown copilot (to avoid duplicates)
    copilot_shown = False

    for lvl in target_levels:
        lvl_project_dir = (
            ensure_project_dir(lvl, project_dir if lvl == "project" else None)
            if lvl == "project"
            else None
        )

        for app in target_apps:
            # Handle Copilot specially - only project level
            if app == "copilot":
                if not copilot_shown:
                    copilot_project_dir = ensure_project_dir("project", project_dir)
                    _show_copilot(manager, copilot_project_dir)
                    copilot_shown = True
                continue

            content = manager.get_live_content(
                app, level=lvl, project_dir=lvl_project_dir
            )

            file_path = get_prompt_file_path(app, lvl, lvl_project_dir)
            typer.echo(f"\n{Colors.BOLD}Live prompt for {app}:{Colors.RESET}")
            typer.echo(f"{Colors.CYAN}Level:{Colors.RESET} {lvl}")
            typer.echo(f"{Colors.CYAN}File:{Colors.RESET} {file_path}")

            # Check which prompt is linked to this file
            linked_prompt = None
            if content:
                # Find which stored prompt matches this content
                for prompt_id, prompt in manager.get_all().items():
                    if prompt.content.strip() == content.strip():
                        linked_prompt = prompt
                        break

            if linked_prompt:
                typer.echo(
                    f"{Colors.BLUE}Linked Prompt:{Colors.RESET} {linked_prompt.name} ({linked_prompt.id})"
                )

            typer.echo()

            if content:
                typer.echo(content)
            else:
                typer.echo(
                    f"{Colors.YELLOW}(No content or file does not exist){Colors.RESET}"
                )

    typer.echo()


def _show_copilot(manager: PromptManager, project_dir: Optional[Path]):
    """Helper to show Copilot instructions."""
    content = manager.get_copilot_instructions(project_dir=project_dir)

    base_dir = project_dir or Path.cwd()
    file_path = base_dir / ".github" / "copilot-instructions.md"

    typer.echo(f"\n{Colors.BOLD}Live prompt for copilot:{Colors.RESET}")
    typer.echo(f"{Colors.CYAN}Level:{Colors.RESET} project")
    typer.echo(f"{Colors.CYAN}File:{Colors.RESET} {file_path}")

    # Check which prompt is linked to this file
    linked_prompt = None
    if content:
        # Find which stored prompt matches this content
        for prompt_id, prompt in manager.get_all().items():
            if prompt.content.strip() == content.strip():
                linked_prompt = prompt
                break

    if linked_prompt:
        typer.echo(
            f"{Colors.BLUE}Linked Prompt:{Colors.RESET} {linked_prompt.name} ({linked_prompt.id})"
        )

    typer.echo()

    if content:
        typer.echo(content)
    else:
        typer.echo(f"{Colors.YELLOW}(No content or file does not exist){Colors.RESET}")


@prompt_app.command("import")
def import_prompts(
    file: Path = typer.Option(..., "--file", "-f", help="JSON file to import from")
):
    """Import prompts from a JSON file."""
    manager = _get_prompt_manager()

    if not file.exists():
        typer.echo(f"{Colors.RED}✗ File not found: {file}{Colors.RESET}")
        raise typer.Exit(1)

    try:
        manager.import_from_file(file)
        typer.echo(f"{Colors.GREEN}✓ Prompts imported from {file}{Colors.RESET}")
    except Exception as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@prompt_app.command("export")
def export_prompts(
    file: Path = typer.Option(..., "--file", "-f", help="JSON file to export to")
):
    """Export prompts to a JSON file."""
    manager = _get_prompt_manager()

    try:
        manager.export_to_file(file)
        typer.echo(f"{Colors.GREEN}✓ Prompts exported to {file}{Colors.RESET}")
    except Exception as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@prompt_app.command("unsync")
def unsync_prompt(
    app_type: str = typer.Option(
        ...,
        "--app",
        "-a",
        help="App(s) to unsync, comma-separated (e.g., 'claude,codex' or 'all')",
    ),
    level: str = typer.Option(
        "user",
        "--level",
        "-l",
        help="Unsync level: 'user', 'project', or 'all'. Copilot only supports 'project'.",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    project_dir: Optional[Path] = typer.Option(
        None,
        "--project-dir",
        help="Project directory when clearing project prompts (defaults to current directory)",
    ),
):
    """Clear/unsync prompt files for one or more app/level combinations.

    For Copilot, clears .github/copilot-instructions.md
    """
    try:
        target_apps = _parse_app_list(app_type)
    except typer.BadParameter as e:
        typer.echo(f"{Colors.RED}✗ {e}{Colors.RESET}")
        raise typer.Exit(1)

    target_levels = resolve_level_targets(level, VALID_LEVELS, default="user")

    targets = []
    copilot_targets = []

    for lvl in target_levels:
        lvl_project_dir = (
            ensure_project_dir(lvl, project_dir if lvl == "project" else None)
            if lvl == "project"
            else None
        )
        for app in target_apps:
            if app == "copilot":
                if lvl == "project":
                    base_dir = lvl_project_dir or Path.cwd()
                    copilot_path = base_dir / ".github" / "copilot-instructions.md"
                    copilot_targets.append(
                        ("copilot", lvl, copilot_path, lvl_project_dir)
                    )
                continue

            file_path = get_prompt_file_path(app, lvl, lvl_project_dir)
            if not file_path:
                continue
            targets.append((app, lvl, file_path, lvl_project_dir))

    all_targets = targets + copilot_targets

    if not all_targets:
        typer.echo(f"{Colors.YELLOW}No matching prompt files found{Colors.RESET}")
        return

    if not force:
        summary = ", ".join(f"{app}:{lvl}" for app, lvl, *_ in all_targets)
        typer.confirm(f"Clear prompt files for {summary}?", abort=True)

    for app, lvl, file_path, _ in all_targets:
        if not file_path.exists():
            typer.echo(
                f"{Colors.YELLOW}Prompt file does not exist: {file_path}{Colors.RESET}"
            )
            continue

        try:
            file_path.write_text("", encoding="utf-8")
            typer.echo(
                f"{Colors.GREEN}✓ Cleared prompt file: {file_path}{Colors.RESET}"
            )
        except Exception as e:
            typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
            raise typer.Exit(1)


@prompt_app.command("status")
def show_prompt_status(
    level: str = typer.Option(
        "all",
        "--level",
        "-l",
        help="Show status for: 'user', 'project', or 'all' (default)",
    ),
    project_dir: Optional[Path] = typer.Option(
        None,
        "--project-dir",
        help="Project directory for project level status (defaults to current directory)",
    ),
):
    """Show prompt status for all apps."""
    manager = _get_prompt_manager()

    # Show default prompt first
    default_prompt = manager.get_default()
    if default_prompt:
        typer.echo(f"\n{Colors.BOLD}Default Prompt:{Colors.RESET}")
        typer.echo(f"  {Colors.GREEN}★{Colors.RESET} {default_prompt.name}")
        typer.echo(f"  {Colors.CYAN}ID:{Colors.RESET} {default_prompt.id}")
    else:
        typer.echo(
            f"\n{Colors.BOLD}Default Prompt:{Colors.RESET} {Colors.YELLOW}(none set){Colors.RESET}"
        )

    levels_to_show = resolve_level_targets(level, VALID_LEVELS, default="all")

    for lvl in levels_to_show:
        typer.echo(
            f"\n{Colors.BOLD}Prompt Status ({lvl.capitalize()} Level):{Colors.RESET}\n"
        )

        # Determine which apps to show for this level
        apps_for_level = USER_LEVEL_APPS if lvl == "user" else VALID_APP_TYPES

        for app_type in apps_for_level:
            # Handle Copilot specially
            if app_type == "copilot":
                _show_copilot_status(manager, project_dir)
                continue

            file_path = get_prompt_file_path(
                app_type, lvl, project_dir if lvl == "project" else None
            )

            typer.echo(f"{Colors.BOLD}{app_type.capitalize()}:{Colors.RESET}")
            typer.echo(f"  {Colors.CYAN}File:{Colors.RESET} {file_path}")

            # Check which prompt is linked to this file
            linked_prompt = None
            try:
                live_content = manager.get_live_content(
                    app_type,
                    level=lvl,
                    project_dir=project_dir if lvl == "project" else None,
                )
                if live_content:
                    # Find which stored prompt matches this content
                    for prompt_id, prompt in manager.get_all().items():
                        if prompt.content.strip() == live_content.strip():
                            linked_prompt = prompt
                            break
            except Exception:
                pass

            if linked_prompt:
                typer.echo(
                    f"  {Colors.BLUE}Linked Prompt:{Colors.RESET} {linked_prompt.name} ({linked_prompt.id})"
                )

            if file_path and file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                if content.strip():
                    lines = content.strip().split("\n")
                    preview = lines[0][:50] + "..." if len(lines[0]) > 50 else lines[0]
                    typer.echo(f"  {Colors.GREEN}Content:{Colors.RESET} {preview}")
                    typer.echo(f"  {Colors.CYAN}Lines:{Colors.RESET} {len(lines)}")
                else:
                    typer.echo(f"  {Colors.YELLOW}Content:{Colors.RESET} (empty)")
            else:
                typer.echo(f"  {Colors.YELLOW}Content:{Colors.RESET} (file not found)")

            typer.echo()


def _show_copilot_status(manager: PromptManager, project_dir: Optional[Path]):
    """Helper to show Copilot status."""
    base_dir = project_dir or Path.cwd()
    file_path = base_dir / ".github" / "copilot-instructions.md"

    typer.echo(f"{Colors.BOLD}Copilot:{Colors.RESET}")
    typer.echo(f"  {Colors.CYAN}File:{Colors.RESET} {file_path}")

    # Check which prompt is linked to this file
    linked_prompt = None
    try:
        live_content = manager.get_copilot_instructions(project_dir=project_dir)
        if live_content:
            # Find which stored prompt matches this content
            for prompt_id, prompt in manager.get_all().items():
                if prompt.content.strip() == live_content.strip():
                    linked_prompt = prompt
                    break
    except Exception:
        pass

    if linked_prompt:
        typer.echo(
            f"  {Colors.BLUE}Linked Prompt:{Colors.RESET} {linked_prompt.name} ({linked_prompt.id})"
        )

    if file_path.exists():
        content = file_path.read_text(encoding="utf-8")
        if content.strip():
            lines = content.strip().split("\n")
            preview = lines[0][:50] + "..." if len(lines[0]) > 50 else lines[0]
            typer.echo(f"  {Colors.GREEN}Content:{Colors.RESET} {preview}")
            typer.echo(f"  {Colors.CYAN}Lines:{Colors.RESET} {len(lines)}")
        else:
            typer.echo(f"  {Colors.YELLOW}Content:{Colors.RESET} (empty)")
    else:
        typer.echo(f"  {Colors.YELLOW}Content:{Colors.RESET} (file not found)")

    # Check for path-specific instructions
    instructions_dir = base_dir / ".github" / "instructions"
    if instructions_dir.exists():
        instruction_files = list(instructions_dir.glob("*.instructions.md"))
        if instruction_files:
            typer.echo(
                f"  {Colors.CYAN}Path-specific:{Colors.RESET} {len(instruction_files)} file(s)"
            )

    typer.echo()


# Add list shorthand
prompt_app.command(name="ls", hidden=True)(list_prompts)
