"""CLI commands for skill management."""

import json
import logging
from pathlib import Path
from typing import Optional

import typer

from code_assistant_manager.cli.option_utils import (
    resolve_app_targets,
    resolve_single_app,
)
from code_assistant_manager.menu.base import Colors
from code_assistant_manager.skills import (
    SKILL_INSTALL_DIRS,
    Skill,
    SkillManager,
    SkillRepo,
)

logger = logging.getLogger(__name__)

skill_app = typer.Typer(
    help="Manage skills for AI assistants (Claude, Codex, Gemini, Droid)",
    no_args_is_help=True,
)

# Valid app types
VALID_APP_TYPES = ["claude", "codex", "gemini", "droid"]


def _get_skill_manager() -> SkillManager:
    """Get skill manager instance."""
    return SkillManager()


@skill_app.command("list")
def list_skills(
    app_type: str = typer.Option(
        "claude",
        "--app",
        "-a",
        help="App type(s) to check installed status (claude, codex, gemini, all)",
    ),
):
    """List all skills."""
    manager = _get_skill_manager()

    target_apps = resolve_app_targets(app_type, VALID_APP_TYPES, default="claude")

    for app in target_apps:
        manager.sync_installed_status(app)

    skills = manager.get_all()

    if not skills:
        typer.echo(
            f"{Colors.YELLOW}No skills found. Run 'cam skill fetch' to discover skills from repositories.{Colors.RESET}"
        )
        return

    context = ", ".join(target_apps)
    typer.echo(f"\n{Colors.BOLD}Skills (for {context}):{Colors.RESET}\n")
    for skill_key, skill in sorted(skills.items()):
        status = (
            f"{Colors.GREEN}✓{Colors.RESET}"
            if skill.installed
            else f"{Colors.RED}✗{Colors.RESET}"
        )
        typer.echo(f"{status} {Colors.BOLD}{skill.name}{Colors.RESET} ({skill_key})")
        if skill.description:
            typer.echo(f"  {Colors.CYAN}Description:{Colors.RESET} {skill.description}")
        typer.echo(f"  {Colors.CYAN}Directory:{Colors.RESET} {skill.directory}")
        if skill.repo_owner and skill.repo_name:
            typer.echo(
                f"  {Colors.CYAN}Repository:{Colors.RESET} {skill.repo_owner}/{skill.repo_name} ({skill.repo_branch})"
            )
        typer.echo()


@skill_app.command("fetch")
def fetch_skills():
    """Fetch skills from configured repositories."""
    manager = _get_skill_manager()

    typer.echo(f"{Colors.CYAN}Fetching skills from repositories...{Colors.RESET}")

    try:
        skills = manager.fetch_skills_from_repos()
        typer.echo(f"{Colors.GREEN}✓ Found {len(skills)} skills{Colors.RESET}")

        for skill in skills[:10]:  # Show first 10
            status = (
                f"{Colors.GREEN}✓{Colors.RESET}"
                if skill.installed
                else f"{Colors.RED}✗{Colors.RESET}"
            )
            typer.echo(f"  {status} {skill.name} ({skill.key})")

        if len(skills) > 10:
            typer.echo(f"  ... and {len(skills) - 10} more")

        typer.echo(
            f"\n{Colors.CYAN}Run 'cam skill list' to see all skills{Colors.RESET}"
        )
    except Exception as e:
        typer.echo(f"{Colors.RED}✗ Error fetching skills: {e}{Colors.RESET}")
        raise typer.Exit(1)


@skill_app.command("view")
def view_skill(skill_key: str):
    """View a specific skill."""
    manager = _get_skill_manager()
    skill = manager.get(skill_key)

    if not skill:
        typer.echo(f"{Colors.RED}✗ Skill '{skill_key}' not found{Colors.RESET}")
        raise typer.Exit(1)

    typer.echo(f"\n{Colors.BOLD}Skill: {skill.name}{Colors.RESET}")
    typer.echo(f"{Colors.CYAN}Description:{Colors.RESET} {skill.description}")
    typer.echo(f"{Colors.CYAN}Key:{Colors.RESET} {skill_key}")
    typer.echo(f"{Colors.CYAN}Directory:{Colors.RESET} {skill.directory}")
    status = (
        f"{Colors.GREEN}installed{Colors.RESET}"
        if skill.installed
        else f"{Colors.RED}not installed{Colors.RESET}"
    )
    typer.echo(f"{Colors.CYAN}Status:{Colors.RESET} {status}")

    if skill.repo_owner and skill.repo_name:
        typer.echo(
            f"{Colors.CYAN}Repository:{Colors.RESET} {skill.repo_owner}/{skill.repo_name}"
        )
        typer.echo(f"{Colors.CYAN}Branch:{Colors.RESET} {skill.repo_branch or 'main'}")

    if skill.skills_path:
        typer.echo(f"{Colors.CYAN}Skills Path:{Colors.RESET} {skill.skills_path}")

    if skill.readme_url:
        typer.echo(f"{Colors.CYAN}README:{Colors.RESET} {skill.readme_url}")

    typer.echo()


@skill_app.command("create")
def create_skill(
    skill_key: str = typer.Argument(..., help="Unique identifier for the skill"),
    name: str = typer.Option(..., "--name", "-n", help="Skill name"),
    description: str = typer.Option(
        ..., "--description", "-d", help="Skill description"
    ),
    directory: str = typer.Option(..., "--directory", "-dir", help="Skill directory"),
    repo_owner: Optional[str] = typer.Option(
        None, "--repo-owner", help="Repository owner"
    ),
    repo_name: Optional[str] = typer.Option(
        None, "--repo-name", help="Repository name"
    ),
    repo_branch: Optional[str] = typer.Option(
        None, "--repo-branch", help="Repository branch"
    ),
    skills_path: Optional[str] = typer.Option(
        None, "--skills-path", help="Skills subdirectory path"
    ),
    readme_url: Optional[str] = typer.Option(None, "--readme-url", help="README URL"),
):
    """Create a new skill."""
    manager = _get_skill_manager()

    try:
        skill = Skill(
            key=skill_key,
            name=name,
            description=description,
            directory=directory,
            repo_owner=repo_owner,
            repo_name=repo_name,
            repo_branch=repo_branch,
            skills_path=skills_path,
            readme_url=readme_url,
        )
        manager.create(skill)
        typer.echo(f"{Colors.GREEN}✓ Skill created: {skill_key}{Colors.RESET}")
    except ValueError as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@skill_app.command("update")
def update_skill(
    skill_key: str = typer.Argument(..., help="Skill identifier"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New skill name"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="New skill description"
    ),
    directory: Optional[str] = typer.Option(
        None, "--directory", "-dir", help="New skill directory"
    ),
):
    """Update an existing skill."""
    manager = _get_skill_manager()
    skill = manager.get(skill_key)

    if not skill:
        typer.echo(f"{Colors.RED}✗ Skill '{skill_key}' not found{Colors.RESET}")
        raise typer.Exit(1)

    # Update fields if provided
    if name:
        skill.name = name
    if description:
        skill.description = description
    if directory:
        skill.directory = directory

    try:
        manager.update(skill)
        typer.echo(f"{Colors.GREEN}✓ Skill updated: {skill_key}{Colors.RESET}")
    except ValueError as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@skill_app.command("delete")
def delete_skill(
    skill_key: str = typer.Argument(..., help="Skill identifier"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a skill."""
    manager = _get_skill_manager()
    skill = manager.get(skill_key)

    if not skill:
        typer.echo(f"{Colors.RED}✗ Skill '{skill_key}' not found{Colors.RESET}")
        raise typer.Exit(1)

    if not force:
        typer.confirm(f"Delete skill '{skill.name}' ({skill_key})?", abort=True)

    try:
        manager.delete(skill_key)
        typer.echo(f"{Colors.GREEN}✓ Skill deleted: {skill_key}{Colors.RESET}")
    except ValueError as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@skill_app.command("install")
def install_skill(
    skill_key: str = typer.Argument(..., help="Skill identifier"),
    app_type: str = typer.Option(
        "claude",
        "--app",
        "-a",
        help="App type(s) to install to (claude, codex, gemini, all)",
    ),
):
    """Install a skill to one or more app skills directories."""
    target_apps = resolve_app_targets(app_type, VALID_APP_TYPES, default="claude")

    manager = _get_skill_manager()

    for app in target_apps:
        try:
            manager.install(skill_key, app)
            install_dir = SKILL_INSTALL_DIRS.get(app)
            typer.echo(
                f"{Colors.GREEN}✓ Skill installed to {app}: {skill_key}{Colors.RESET}"
            )
            typer.echo(f"  {Colors.CYAN}Location:{Colors.RESET} {install_dir}")
        except ValueError as e:
            typer.echo(f"{Colors.RED}✗ Error installing to {app}: {e}{Colors.RESET}")
            raise typer.Exit(1)


@skill_app.command("uninstall")
def uninstall_skill(
    skill_key: str = typer.Argument(..., help="Skill identifier"),
    app_type: str = typer.Option(
        "claude",
        "--app",
        "-a",
        help="App type(s) to uninstall from (claude, codex, gemini, all)",
    ),
):
    """Uninstall a skill from one or more app skills directories."""
    target_apps = resolve_app_targets(app_type, VALID_APP_TYPES, default="claude")

    manager = _get_skill_manager()

    for app in target_apps:
        try:
            manager.uninstall(skill_key, app)
            typer.echo(
                f"{Colors.GREEN}✓ Skill uninstalled from {app}: {skill_key}{Colors.RESET}"
            )
        except ValueError as e:
            typer.echo(
                f"{Colors.RED}✗ Error uninstalling from {app}: {e}{Colors.RESET}"
            )
            raise typer.Exit(1)


@skill_app.command("repos")
def list_repos():
    """List all skill repositories."""
    manager = _get_skill_manager()
    repos = manager.get_repos()

    if not repos:
        typer.echo(f"{Colors.YELLOW}No skill repositories configured{Colors.RESET}")
        return

    typer.echo(f"\n{Colors.BOLD}Skill Repositories:{Colors.RESET}\n")
    for repo in repos:
        status = (
            f"{Colors.GREEN}✓{Colors.RESET}"
            if repo.enabled
            else f"{Colors.RED}✗{Colors.RESET}"
        )
        typer.echo(f"{status} {Colors.BOLD}{repo.owner}/{repo.name}{Colors.RESET}")
        typer.echo(f"  {Colors.CYAN}Branch:{Colors.RESET} {repo.branch}")
        if repo.skills_path:
            typer.echo(f"  {Colors.CYAN}Skills Path:{Colors.RESET} {repo.skills_path}")
        typer.echo()


@skill_app.command("add-repo")
def add_repo(
    owner: str = typer.Option(..., "--owner", "-o", help="Repository owner"),
    name: str = typer.Option(..., "--name", "-n", help="Repository name"),
    branch: str = typer.Option("main", "--branch", "-b", help="Repository branch"),
    skills_path: Optional[str] = typer.Option(
        None, "--skills-path", help="Skills subdirectory path"
    ),
):
    """Add a skill repository."""
    manager = _get_skill_manager()

    try:
        repo = SkillRepo(
            owner=owner,
            name=name,
            branch=branch,
            enabled=True,
            skills_path=skills_path,
        )
        manager.add_repo(repo)
        typer.echo(f"{Colors.GREEN}✓ Repository added: {owner}/{name}{Colors.RESET}")
    except Exception as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@skill_app.command("remove-repo")
def remove_repo(
    owner: str = typer.Option(..., "--owner", "-o", help="Repository owner"),
    name: str = typer.Option(..., "--name", "-n", help="Repository name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Remove a skill repository."""
    manager = _get_skill_manager()

    if not force:
        typer.confirm(f"Remove repository '{owner}/{name}'?", abort=True)

    try:
        manager.remove_repo(owner, name)
        typer.echo(f"{Colors.GREEN}✓ Repository removed: {owner}/{name}{Colors.RESET}")
    except ValueError as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@skill_app.command("import")
def import_skills(
    file: Path = typer.Option(..., "--file", "-f", help="JSON file to import from")
):
    """Import skills from a JSON file."""
    manager = _get_skill_manager()

    if not file.exists():
        typer.echo(f"{Colors.RED}✗ File not found: {file}{Colors.RESET}")
        raise typer.Exit(1)

    try:
        manager.import_from_file(file)
        typer.echo(f"{Colors.GREEN}✓ Skills imported from {file}{Colors.RESET}")
    except Exception as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@skill_app.command("export")
def export_skills(
    file: Path = typer.Option(..., "--file", "-f", help="JSON file to export to")
):
    """Export skills to a JSON file."""
    manager = _get_skill_manager()

    try:
        manager.export_to_file(file)
        typer.echo(f"{Colors.GREEN}✓ Skills exported to {file}{Colors.RESET}")
    except Exception as e:
        typer.echo(f"{Colors.RED}✗ Error: {e}{Colors.RESET}")
        raise typer.Exit(1)


@skill_app.command("installed")
def list_installed_skills(
    app_type: Optional[str] = typer.Option(
        None,
        "--app",
        "-a",
        help="App type(s) to show (claude, codex, gemini, all). Default shows all.",
    ),
):
    """Show installed skills for each app."""
    manager = _get_skill_manager()
    all_skills = manager.get_all()

    target_apps = resolve_app_targets(
        app_type,
        VALID_APP_TYPES,
        default=None,
        fallback_to_all_if_none=True,
    )

    for app in target_apps:
        install_dir = SKILL_INSTALL_DIRS.get(app)
        typer.echo(f"\n{Colors.BOLD}{app.capitalize()} ({install_dir}):{Colors.RESET}")

        if not install_dir or not install_dir.exists():
            typer.echo(f"  {Colors.YELLOW}No skills installed{Colors.RESET}")
            continue

        installed = list(install_dir.iterdir()) if install_dir.exists() else []
        skill_dirs = [d for d in installed if d.is_dir()]

        if not skill_dirs:
            typer.echo(f"  {Colors.YELLOW}No skills installed{Colors.RESET}")
            continue

        for skill_dir in sorted(skill_dirs):
            skill_key = None
            for key, skill in all_skills.items():
                if skill.directory == skill_dir.name:
                    skill_key = key
                    break

            if skill_key:
                typer.echo(
                    f"  {Colors.GREEN}✓{Colors.RESET} {skill_dir.name} ({Colors.CYAN}{skill_key}{Colors.RESET})"
                )
            else:
                typer.echo(f"  {Colors.GREEN}✓{Colors.RESET} {skill_dir.name}")

    typer.echo()


@skill_app.command("uninstall-all")
def uninstall_all_skills(
    app_type: str = typer.Option(
        ...,
        "--app",
        "-a",
        help="App type(s) to uninstall all skills from (claude, codex, gemini, all)",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Uninstall all skills for one or more apps."""
    target_apps = resolve_app_targets(app_type, VALID_APP_TYPES)
    manager = _get_skill_manager()

    for app in target_apps:
        install_dir = SKILL_INSTALL_DIRS.get(app)
        if not install_dir or not install_dir.exists():
            typer.echo(
                f"{Colors.YELLOW}No skills directory found for {app}{Colors.RESET}"
            )
            continue

        skill_dirs = [d for d in install_dir.iterdir() if d.is_dir()]
        if not skill_dirs:
            typer.echo(f"{Colors.YELLOW}No skills installed for {app}{Colors.RESET}")
            continue

        if not force:
            typer.confirm(
                f"Uninstall all {len(skill_dirs)} skills from {app}?", abort=True
            )

        removed_count = 0
        for skill_dir in skill_dirs:
            try:
                import shutil

                shutil.rmtree(skill_dir)
                typer.echo(f"  {Colors.GREEN}✓{Colors.RESET} Removed: {skill_dir.name}")
                removed_count += 1
            except Exception as e:
                typer.echo(
                    f"  {Colors.RED}✗{Colors.RESET} Failed to remove {skill_dir.name}: {e}"
                )

        manager.sync_installed_status(app)
        typer.echo(
            f"\n{Colors.GREEN}✓ Removed {removed_count} skills from {app}{Colors.RESET}"
        )


# Add list shorthand
skill_app.command(name="ls", hidden=True)(list_skills)
