"""CLI commands for prompt management."""

import json
import logging
from pathlib import Path
from typing import Optional

import typer

from code_assistant_manager.cli.option_utils import (
    ensure_project_dir,
    resolve_app_targets,
    resolve_level_targets,
    resolve_single_app,
    resolve_single_level,
)
from code_assistant_manager.menu.base import Colors
from code_assistant_manager.prompts import (
    PROMPT_FILE_PATHS,
    Prompt,
    PromptManager,
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
        status = (
            f"{Colors.GREEN}✓ active{Colors.RESET}"
            if prompt.enabled
            else f"{Colors.RED}✗{Colors.RESET}"
        )
        app_info = f" [{prompt.app_type}]" if prompt.app_type else ""
        typer.echo(
            f"{status} {Colors.BOLD}{prompt.name}{Colors.RESET}{app_info} ({prompt_id})"
        )
        if prompt.description:
            typer.echo(f"  {Colors.CYAN}{prompt.description}{Colors.RESET}")
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
        f"{Colors.GREEN}enabled{Colors.RESET}"
        if prompt.enabled
        else f"{Colors.RED}disabled{Colors.RESET}"
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


@prompt_app.command("enable")
def enable_prompt(
    prompt_id: str = typer.Argument(..., help="Prompt identifier to enable"),
    app_type: str = typer.Option(
        ...,
        "--app",
        "-a",
        help="App type to enable for (claude, codex, gemini)",
    ),
    level: str = typer.Option(
        "user",
        "--level",
        "-l",
        help="Enable level: 'user' or 'project'",
    ),
    project_dir: Optional[Path] = typer.Option(
        None,
        "--project-dir",
        help="Project directory when using project level (defaults to current directory)",
    ),
):
    """Enable a prompt and sync it to the app file.

    This will:
    - Mark the prompt as enabled for the specified app
    - Disable other prompts for the same app (user level only)
    - Sync the prompt content to the app's prompt file
    """
    if app_type not in USER_LEVEL_APPS:
        typer.echo(
            f"{Colors.RED}✗ Invalid app: {app_type}. Valid: {', '.join(USER_LEVEL_APPS)}{Colors.RESET}"
        )
        raise typer.Exit(1)

    if level not in VALID_LEVELS:
        typer.echo(
            f"{Colors.RED}✗ Invalid level: {level}. Valid: {', '.join(VALID_LEVELS)}{Colors.RESET}"
        )
        raise typer.Exit(1)

    manager = _get_prompt_manager()
    prompt = manager.get(prompt_id)

    if not prompt:
        typer.echo(f"{Colors.RED}✗ Prompt '{prompt_id}' not found{Colors.RESET}")
        raise typer.Exit(1)

    level_project_dir = (
        ensure_project_dir(level, project_dir if level == "project" else None)
        if level == "project"
        else None
    )

    try:
        manager.activate(
            prompt_id,
            app_type,
            level=level,
            project_dir=level_project_dir,
        )
        typer.echo(
            f"{Colors.GREEN}✓ Enabled '{prompt.name}' for {app_type} ({level}){Colors.RESET}"
        )
        file_path = get_prompt_file_path(app_type, level, level_project_dir)
        typer.echo(f"  {Colors.CYAN}File:{Colors.RESET} {file_path}")
    except Exception as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@prompt_app.command("disable")
def disable_prompt(
    prompt_id: str = typer.Argument(..., help="Prompt identifier to disable"),
):
    """Disable a prompt.

    This only changes the prompt's status to disabled.
    It does NOT remove content from any prompt files.
    Use 'unsync' to clear prompt files.
    """
    manager = _get_prompt_manager()
    prompt = manager.get(prompt_id)

    if not prompt:
        typer.echo(f"{Colors.RED}✗ Prompt '{prompt_id}' not found{Colors.RESET}")
        raise typer.Exit(1)

    if not prompt.enabled:
        typer.echo(
            f"{Colors.YELLOW}Prompt '{prompt.name}' is already disabled{Colors.RESET}"
        )
        return

    try:
        manager.deactivate(prompt_id)
        typer.echo(f"{Colors.GREEN}✓ Disabled '{prompt.name}'{Colors.RESET}")
    except Exception as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@prompt_app.command("sync")
def sync_prompts(
    prompt_id: Optional[str] = typer.Argument(
        None, help="Prompt ID to sync. If not specified, syncs all active prompts."
    ),
    app_type: Optional[str] = typer.Option(
        None,
        "--app",
        "-a",
        help="App type to sync to (claude, codex, gemini, copilot). Required if prompt_id is specified.",
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
    enable: bool = typer.Option(
        False,
        "--enable",
        "-e",
        help="Also mark this prompt as active (backs up existing content, disables other prompts for this app)",
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
    """Sync prompts to app files. Can sync a specific prompt or all active prompts.

    For Claude, Codex, Gemini:
    - User level syncs to ~/.{app}/ directory
    - Project level syncs to current directory

    For Copilot (project level only):
    - Without --apply-to: syncs to .github/copilot-instructions.md (repo-wide)
    - With --apply-to: syncs to .github/instructions/{id}.instructions.md (path-specific)

    Use --enable to also mark the prompt as active, which:
    - Backs up existing prompt file content (if different)
    - Disables other prompts for the same app type (user level only)
    - Marks this prompt as enabled for tracking
    """
    manager = _get_prompt_manager()

    if prompt_id:
        # Sync specific prompt to specific app
        if not app_type:
            typer.echo(
                f"{Colors.RED}✗ --app is required when specifying a prompt ID{Colors.RESET}"
            )
            raise typer.Exit(1)

        target_app = resolve_single_app(app_type, VALID_APP_TYPES)

        # Handle Copilot specially
        if target_app == "copilot":
            _sync_copilot(manager, prompt_id, apply_to, exclude_agent, project_dir)
            return

        # For non-Copilot apps
        if level not in VALID_LEVELS:
            typer.echo(
                f"{Colors.RED}✗ Invalid level: {level}. Valid: {', '.join(VALID_LEVELS)}{Colors.RESET}"
            )
            raise typer.Exit(1)

        prompt = manager.get(prompt_id)
        if not prompt:
            typer.echo(f"{Colors.RED}✗ Prompt not found: {prompt_id}{Colors.RESET}")
            raise typer.Exit(1)

        # Resolve project directory for project level
        level_project_dir = (
            ensure_project_dir(level, project_dir if level == "project" else None)
            if level == "project"
            else None
        )

        file_path = get_prompt_file_path(target_app, level, level_project_dir)
        if not file_path:
            typer.echo(f"{Colors.RED}✗ Unknown app type: {app_type}{Colors.RESET}")
            raise typer.Exit(1)

        try:
            if enable:
                # Use activate() which handles backup, disabling other prompts, and syncing
                manager.activate(
                    prompt_id,
                    target_app,
                    level=level,
                    project_dir=level_project_dir,
                )
                typer.echo(
                    f"{Colors.GREEN}✓ Synced and enabled '{prompt_id}' for {target_app} ({level}){Colors.RESET}"
                )
            else:
                # Just sync the file without changing enabled state
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(prompt.content, encoding="utf-8")
                typer.echo(
                    f"{Colors.GREEN}✓ Synced '{prompt_id}' to {target_app} ({level}){Colors.RESET}"
                )
            typer.echo(f"  {Colors.CYAN}File:{Colors.RESET} {file_path}")
        except Exception as e:
            typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
            raise typer.Exit(1)
    else:
        # Sync all active prompts
        if enable:
            typer.echo(
                f"{Colors.RED}✗ --enable requires specifying a prompt ID{Colors.RESET}"
            )
            raise typer.Exit(1)

        if level == "project":
            typer.echo(
                f"{Colors.RED}✗ --level project requires specifying a prompt ID{Colors.RESET}"
            )
            raise typer.Exit(1)

        results = manager.sync_all()

        for app, synced_prompt_id in results.items():
            if synced_prompt_id:
                typer.echo(
                    f"{Colors.GREEN}✓ {app}: synced ({synced_prompt_id}){Colors.RESET}"
                )
            else:
                typer.echo(f"{Colors.YELLOW}○ {app}: no active prompt{Colors.RESET}")


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
    target_dir = ensure_project_dir("project", project_dir) if project_dir else None

    try:
        manager.sync_copilot_instructions(
            prompt_id,
            instruction_type=instruction_type,
            apply_to=apply_to,
            exclude_agent=exclude_agent,
            project_dir=target_dir,
        )

        typer.echo(
            f"{Colors.GREEN}✓ Synced '{prompt_id}' to Copilot {instruction_type} instructions{Colors.RESET}"
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
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@prompt_app.command("import-live")
def import_live_prompt(
    app_type: str = typer.Option(
        "claude",
        "--app",
        "-a",
        help="App type to import from (claude, codex, gemini, copilot, all)",
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
    target_apps = resolve_app_targets(app_type, VALID_APP_TYPES, default="claude")
    target_levels = resolve_level_targets(level, VALID_LEVELS, default="user")

    manager = _get_prompt_manager()
    multiple = len(target_apps) * len(target_levels) > 1

    for lvl in target_levels:
        lvl_project_dir = (
            ensure_project_dir(lvl, project_dir if lvl == "project" else None)
            if lvl == "project"
            else None
        )

        for app in target_apps:
            # Handle Copilot specially - only project level
            if app == "copilot":
                if lvl == "user":
                    continue  # Skip user level for Copilot
                _import_copilot(manager, name, lvl_project_dir)
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
        "claude",
        "--app",
        "-a",
        help="App type to show (claude, codex, gemini, copilot, all)",
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
    target_apps = resolve_app_targets(app_type, VALID_APP_TYPES, default="claude")
    target_levels = resolve_level_targets(level, VALID_LEVELS, default="user")

    manager = _get_prompt_manager()

    for lvl in target_levels:
        lvl_project_dir = (
            ensure_project_dir(lvl, project_dir if lvl == "project" else None)
            if lvl == "project"
            else None
        )

        for app in target_apps:
            # Handle Copilot specially - only project level
            if app == "copilot":
                if lvl == "user":
                    continue  # Skip user level for Copilot
                _show_copilot(manager, lvl_project_dir)
                continue

            content = manager.get_live_content(
                app, level=lvl, project_dir=lvl_project_dir
            )

            file_path = get_prompt_file_path(app, lvl, lvl_project_dir)
            typer.echo(f"\n{Colors.BOLD}Live prompt for {app}:{Colors.RESET}")
            typer.echo(f"{Colors.CYAN}Level:{Colors.RESET} {lvl}")
            typer.echo(f"{Colors.CYAN}File:{Colors.RESET} {file_path}\n")

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
    typer.echo(f"{Colors.CYAN}File:{Colors.RESET} {file_path}\n")

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
        help="App type to unsync (claude, codex, gemini, copilot, all)",
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
    disable: bool = typer.Option(
        True,
        "--disable/--no-disable",
        "-d",
        help="Also disable prompts that were active for the unsynced app (default: enabled)",
    ),
):
    """Clear/unsync prompt files for one or more app/level combinations.

    By default, also disables any prompts that were active for the unsynced app.
    Use --no-disable to only clear the file without changing prompt states.

    For Copilot, clears .github/copilot-instructions.md
    """
    target_apps = resolve_app_targets(app_type, VALID_APP_TYPES)
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

    manager = _get_prompt_manager()

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

            if disable and lvl == "user" and app != "copilot":
                prompts = manager.get_all()
                for prompt in prompts.values():
                    if prompt.enabled and prompt.app_type == app:
                        prompt.enabled = False
                        manager.update(prompt)
                        typer.echo(
                            f"  {Colors.CYAN}Disabled:{Colors.RESET} {prompt.id}"
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

            # Only show active prompt for user level
            if lvl == "user":
                active_prompt = manager.get_active_prompt(app_type)
                if active_prompt:
                    typer.echo(
                        f"  {Colors.GREEN}Active Prompt:{Colors.RESET} {active_prompt.name} ({active_prompt.id})"
                    )
                else:
                    typer.echo(f"  {Colors.YELLOW}Active Prompt:{Colors.RESET} None")

            typer.echo()


def _show_copilot_status(manager: PromptManager, project_dir: Optional[Path]):
    """Helper to show Copilot status."""
    base_dir = project_dir or Path.cwd()
    file_path = base_dir / ".github" / "copilot-instructions.md"

    typer.echo(f"{Colors.BOLD}Copilot:{Colors.RESET}")
    typer.echo(f"  {Colors.CYAN}File:{Colors.RESET} {file_path}")

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
