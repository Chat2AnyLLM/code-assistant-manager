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
    help="Manage prompts for AI assistants (Claude, Codex, Gemini)",
    no_args_is_help=True,
)

# Valid app types
VALID_APP_TYPES = ["claude", "codex", "gemini"]
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


@prompt_app.command("sync")
def sync_prompts(
    prompt_id: Optional[str] = typer.Argument(
        None, help="Prompt ID to sync. If not specified, syncs all active prompts."
    ),
    app_type: Optional[str] = typer.Option(
        None,
        "--app",
        "-a",
        help="App type to sync to (claude, codex, gemini). Required if prompt_id is specified.",
    ),
    level: str = typer.Option(
        "user",
        "--level",
        "-l",
        help="Sync level: 'user' (~/.claude/) or 'project' (current directory)",
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
):
    """Sync prompts to app files. Can sync a specific prompt or all active prompts.

    Use --enable to also mark the prompt as active, which:
    - Backs up existing prompt file content (if different)
    - Disables other prompts for the same app type (user level only)
    - Marks this prompt as enabled for tracking
    """
    if level not in VALID_LEVELS:
        typer.echo(
            f"{Colors.RED}✗ Invalid level: {level}. Valid: {', '.join(VALID_LEVELS)}{Colors.RESET}"
        )
        raise typer.Exit(1)

    manager = _get_prompt_manager()

    # Resolve project directory for project level
    level_project_dir = (
        ensure_project_dir(level, project_dir if level == "project" else None)
        if level == "project"
        else None
    )

    if prompt_id:
        # Sync specific prompt to specific app
        if not app_type:
            typer.echo(
                f"{Colors.RED}✗ --app is required when specifying a prompt ID{Colors.RESET}"
            )
            raise typer.Exit(1)

        target_app = resolve_single_app(app_type, VALID_APP_TYPES)

        prompt = manager.get(prompt_id)
        if not prompt:
            typer.echo(f"{Colors.RED}✗ Prompt not found: {prompt_id}{Colors.RESET}")
            raise typer.Exit(1)

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


@prompt_app.command("import-live")
def import_live_prompt(
    app_type: str = typer.Option(
        "claude",
        "--app",
        "-a",
        help="App type to import from (claude, codex, gemini, all)",
    ),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Name for the imported prompt"
    ),
    level: str = typer.Option(
        "user",
        "--level",
        "-l",
        help="Prompt level to import from: 'user', 'project', or 'all'",
    ),
    project_dir: Optional[Path] = typer.Option(
        None,
        "--project-dir",
        help="Project directory when using project level (defaults to current directory)",
    ),
):
    """Import the current live prompt file as a new prompt."""
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


@prompt_app.command("show-live")
def show_live_prompt(
    app_type: str = typer.Option(
        "claude",
        "--app",
        "-a",
        help="App type to show (claude, codex, gemini, all)",
    ),
    level: str = typer.Option(
        "user",
        "--level",
        "-l",
        help="Prompt level to show: 'user', 'project', or 'all'",
    ),
    project_dir: Optional[Path] = typer.Option(
        None,
        "--project-dir",
        help="Project directory when showing project prompts (defaults to current directory)",
    ),
):
    """Show the current live prompt file content."""
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
        help="App type to unsync (claude, codex, gemini, all)",
    ),
    level: str = typer.Option(
        "user",
        "--level",
        "-l",
        help="Unsync level: 'user', 'project', or 'all'",
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
    """
    target_apps = resolve_app_targets(app_type, VALID_APP_TYPES)
    target_levels = resolve_level_targets(level, VALID_LEVELS, default="user")

    targets = []
    for lvl in target_levels:
        lvl_project_dir = (
            ensure_project_dir(lvl, project_dir if lvl == "project" else None)
            if lvl == "project"
            else None
        )
        for app in target_apps:
            file_path = get_prompt_file_path(app, lvl, lvl_project_dir)
            if not file_path:
                continue
            targets.append((app, lvl, file_path, lvl_project_dir))

    if not targets:
        typer.echo(f"{Colors.YELLOW}No matching prompt files found{Colors.RESET}")
        return

    if not force:
        summary = ", ".join(f"{app}:{lvl}" for app, lvl, *_ in targets)
        typer.confirm(f"Clear prompt files for {summary}?", abort=True)

    manager = _get_prompt_manager()

    for app, lvl, file_path, _ in targets:
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

            if disable and lvl == "user":
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
):
    """Show prompt status for all apps."""
    manager = _get_prompt_manager()

    levels_to_show = resolve_level_targets(level, VALID_LEVELS, default="all")

    for lvl in levels_to_show:
        typer.echo(
            f"\n{Colors.BOLD}Prompt Status ({lvl.capitalize()} Level):{Colors.RESET}\n"
        )

        for app_type in VALID_APP_TYPES:
            file_path = get_prompt_file_path(app_type, lvl)

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


# Add list shorthand
prompt_app.command(name="ls", hidden=True)(list_prompts)
