"""CLI commands for Claude Code plugin management.

Uses the `claude` CLI to manage plugins and marketplaces.
"""

import logging
from pathlib import Path
from typing import Optional

import typer

from code_assistant_manager.menu.base import Colors
from code_assistant_manager.plugins import (
    BUILTIN_PLUGIN_REPOS,
    VALID_APP_TYPES,
    PluginManager,
)
from code_assistant_manager.plugins.claude import ClaudePluginHandler

logger = logging.getLogger(__name__)

plugin_app = typer.Typer(
    help="Manage Claude Code plugins and marketplaces (currently only supports Claude Code, uses 'claude' CLI)",
    no_args_is_help=True,
)


def _get_handler() -> ClaudePluginHandler:
    """Get Claude plugin handler instance."""
    return ClaudePluginHandler()


def _check_claude_cli():
    """Check if Claude CLI is available."""
    handler = _get_handler()
    if not handler.get_cli_path():
        typer.echo(
            f"{Colors.RED}✗ Claude CLI not found. Please install Claude Code first.{Colors.RESET}"
        )
        raise typer.Exit(1)


# ==================== Marketplace Commands ====================

marketplace_app = typer.Typer(
    help="Manage Claude Code plugin marketplaces",
    no_args_is_help=True,
)


@marketplace_app.command("add")
def marketplace_add(
    source: str = typer.Argument(
        ...,
        help="Marketplace source: URL, local path, or GitHub repo (owner/repo)",
    ),
):
    """Add a marketplace from URL, path, or GitHub repo."""
    _check_claude_cli()
    handler = _get_handler()

    typer.echo(f"{Colors.CYAN}Adding marketplace: {source}...{Colors.RESET}")
    success, msg = handler.marketplace_add(source)

    if success:
        typer.echo(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")
    else:
        typer.echo(f"{Colors.RED}✗ {msg}{Colors.RESET}")
        raise typer.Exit(1)


@marketplace_app.command("remove")
def marketplace_remove(
    name: str = typer.Argument(..., help="Marketplace name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Remove a configured marketplace."""
    _check_claude_cli()
    handler = _get_handler()

    if not force:
        typer.confirm(f"Remove marketplace '{name}'?", abort=True)

    typer.echo(f"{Colors.CYAN}Removing marketplace: {name}...{Colors.RESET}")
    success, msg = handler.marketplace_remove(name)

    if success:
        typer.echo(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")
    else:
        typer.echo(f"{Colors.RED}✗ {msg}{Colors.RESET}")
        raise typer.Exit(1)


@marketplace_app.command("list")
def marketplace_list():
    """List all configured marketplaces."""
    _check_claude_cli()
    handler = _get_handler()

    success, output = handler.marketplace_list()

    if success:
        if output:
            typer.echo(output)
        else:
            # Fallback to reading known_marketplaces.json
            marketplaces = handler.get_known_marketplaces()
            if not marketplaces:
                typer.echo(
                    f"{Colors.YELLOW}No marketplaces configured. "
                    f"Use 'cam plugin marketplace add' to add one.{Colors.RESET}"
                )
                return

            typer.echo(f"\n{Colors.BOLD}Configured Marketplaces:{Colors.RESET}\n")
            for name, info in sorted(marketplaces.items()):
                typer.echo(
                    f"{Colors.GREEN}✓{Colors.RESET} {Colors.BOLD}{name}{Colors.RESET}"
                )
                source = info.get("source", {})
                if source.get("url"):
                    typer.echo(f"  {Colors.CYAN}URL:{Colors.RESET} {source['url']}")
                location = info.get("installLocation")
                if location:
                    typer.echo(f"  {Colors.CYAN}Location:{Colors.RESET} {location}")
                typer.echo()
    else:
        typer.echo(f"{Colors.RED}✗ {output}{Colors.RESET}")
        raise typer.Exit(1)


@marketplace_app.command("update")
def marketplace_update(
    name: Optional[str] = typer.Argument(
        None,
        help="Marketplace name to update (updates all if not specified)",
    ),
):
    """Update marketplace(s) from their source."""
    _check_claude_cli()
    handler = _get_handler()

    if name:
        typer.echo(f"{Colors.CYAN}Updating marketplace: {name}...{Colors.RESET}")
    else:
        typer.echo(f"{Colors.CYAN}Updating all marketplaces...{Colors.RESET}")

    success, msg = handler.marketplace_update(name)

    if success:
        typer.echo(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")
    else:
        typer.echo(f"{Colors.RED}✗ {msg}{Colors.RESET}")
        raise typer.Exit(1)


# Add marketplace subcommand to plugin app
plugin_app.add_typer(marketplace_app, name="marketplace")


# ==================== Plugin Commands ====================


@plugin_app.command("install")
def install_plugin(
    plugin: str = typer.Argument(
        ...,
        help="Plugin name or plugin@marketplace",
    ),
    marketplace: Optional[str] = typer.Option(
        None,
        "--marketplace",
        "-m",
        help="Marketplace name (alternative to plugin@marketplace format)",
    ),
):
    """Install a plugin from available marketplaces."""
    _check_claude_cli()
    handler = _get_handler()

    # Check if it's a built-in repo that needs marketplace added first
    builtin = BUILTIN_PLUGIN_REPOS.get(plugin)
    if builtin and builtin.repo_owner and builtin.repo_name:
        # Check if marketplace already exists
        known_marketplaces = handler.get_known_marketplaces()
        marketplace_exists = any(
            builtin.repo_owner.lower() in name.lower()
            or builtin.repo_name.lower() in name.lower()
            for name in known_marketplaces
        )

        if not marketplace_exists:
            typer.echo(
                f"{Colors.CYAN}Adding marketplace for built-in plugin: {plugin}...{Colors.RESET}"
            )
            repo_url = f"https://github.com/{builtin.repo_owner}/{builtin.repo_name}"
            success, msg = handler.marketplace_add(repo_url)
            if not success and "already installed" not in msg.lower():
                typer.echo(
                    f"{Colors.RED}✗ Failed to add marketplace: {msg}{Colors.RESET}"
                )
                raise typer.Exit(1)

    plugin_ref = f"{plugin}@{marketplace}" if marketplace else plugin
    typer.echo(f"{Colors.CYAN}Installing plugin: {plugin_ref}...{Colors.RESET}")

    success, msg = handler.install_plugin(plugin, marketplace)

    if success:
        typer.echo(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")
        typer.echo(
            f"\n{Colors.YELLOW}Note: Restart Claude Code to load the new plugin.{Colors.RESET}"
        )
    else:
        typer.echo(f"{Colors.RED}✗ {msg}{Colors.RESET}")
        raise typer.Exit(1)


@plugin_app.command("uninstall")
def uninstall_plugin(
    plugin: str = typer.Argument(..., help="Plugin name to uninstall"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Uninstall an installed plugin."""
    _check_claude_cli()
    handler = _get_handler()

    if not force:
        typer.confirm(f"Uninstall plugin '{plugin}'?", abort=True)

    typer.echo(f"{Colors.CYAN}Uninstalling plugin: {plugin}...{Colors.RESET}")
    success, msg = handler.uninstall_plugin(plugin)

    if success:
        typer.echo(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")
        typer.echo(
            f"\n{Colors.YELLOW}Note: Restart Claude Code to apply changes.{Colors.RESET}"
        )
    else:
        typer.echo(f"{Colors.RED}✗ {msg}{Colors.RESET}")
        raise typer.Exit(1)


@plugin_app.command("enable")
def enable_plugin(
    plugin: str = typer.Argument(..., help="Plugin name to enable"),
):
    """Enable a disabled plugin."""
    _check_claude_cli()
    handler = _get_handler()

    typer.echo(f"{Colors.CYAN}Enabling plugin: {plugin}...{Colors.RESET}")
    success, msg = handler.enable_plugin(plugin)

    if success:
        typer.echo(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")
        typer.echo(
            f"\n{Colors.YELLOW}Note: Restart Claude Code to apply changes.{Colors.RESET}"
        )
    else:
        typer.echo(f"{Colors.RED}✗ {msg}{Colors.RESET}")
        raise typer.Exit(1)


@plugin_app.command("disable")
def disable_plugin(
    plugin: str = typer.Argument(..., help="Plugin name to disable"),
):
    """Disable an enabled plugin."""
    _check_claude_cli()
    handler = _get_handler()

    typer.echo(f"{Colors.CYAN}Disabling plugin: {plugin}...{Colors.RESET}")
    success, msg = handler.disable_plugin(plugin)

    if success:
        typer.echo(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")
        typer.echo(
            f"\n{Colors.YELLOW}Note: Restart Claude Code to apply changes.{Colors.RESET}"
        )
    else:
        typer.echo(f"{Colors.RED}✗ {msg}{Colors.RESET}")
        raise typer.Exit(1)


@plugin_app.command("validate")
def validate_plugin(
    path: str = typer.Argument(..., help="Path to plugin or marketplace to validate"),
):
    """Validate a plugin or marketplace manifest."""
    _check_claude_cli()
    handler = _get_handler()

    typer.echo(f"{Colors.CYAN}Validating: {path}...{Colors.RESET}")
    success, msg = handler.validate_plugin(path)

    if success:
        typer.echo(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")
    else:
        typer.echo(f"{Colors.RED}✗ {msg}{Colors.RESET}")
        raise typer.Exit(1)


@plugin_app.command("list")
def list_plugins(
    show_all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Show all plugins from marketplaces (not just enabled)",
    ),
):
    """List installed/enabled plugins."""
    _check_claude_cli()
    handler = _get_handler()

    # Get enabled plugins from settings
    enabled_plugins = handler.get_enabled_plugins()

    if not enabled_plugins and not show_all:
        typer.echo(
            f"{Colors.YELLOW}No plugins installed. "
            f"Use 'cam plugin install <plugin>' to install one.{Colors.RESET}"
        )

        # Show available built-in repos
        if BUILTIN_PLUGIN_REPOS:
            typer.echo(f"\n{Colors.CYAN}Available built-in plugins:{Colors.RESET}")
            for name, repo in BUILTIN_PLUGIN_REPOS.items():
                typer.echo(f"  • {name}: {repo.description or 'No description'}")
            typer.echo(f"\nInstall with: cam plugin install <name>")
        return

    if enabled_plugins:
        typer.echo(f"\n{Colors.BOLD}Enabled Plugins:{Colors.RESET}\n")
        for plugin_key, enabled in sorted(enabled_plugins.items()):
            # Extract plugin name from key (format: owner/repo:name or name@marketplace)
            if ":" in plugin_key:
                plugin_name = plugin_key.split(":")[-1]
            elif "@" in plugin_key:
                plugin_name = plugin_key.split("@")[0]
            else:
                plugin_name = plugin_key

            if enabled:
                status = f"{Colors.GREEN}✓ enabled{Colors.RESET}"
            else:
                status = f"{Colors.YELLOW}○ disabled{Colors.RESET}"

            typer.echo(f"  {status} {Colors.BOLD}{plugin_name}{Colors.RESET}")
            typer.echo(f"         {Colors.CYAN}Key:{Colors.RESET} {plugin_key}")
        typer.echo()

    if show_all:
        # Scan plugins from marketplaces
        plugins = handler.scan_marketplace_plugins()
        if plugins:
            typer.echo(
                f"\n{Colors.BOLD}Available Plugins from Marketplaces:{Colors.RESET}\n"
            )
            for plugin in sorted(plugins, key=lambda p: p.name):
                if plugin.installed:
                    status = f"{Colors.GREEN}✓{Colors.RESET}"
                else:
                    status = f"{Colors.CYAN}○{Colors.RESET}"

                typer.echo(
                    f"  {status} {Colors.BOLD}{plugin.name}{Colors.RESET} v{plugin.version}"
                )
                if plugin.description:
                    typer.echo(f"      {plugin.description[:80]}...")
                typer.echo(
                    f"      {Colors.CYAN}Marketplace:{Colors.RESET} {plugin.marketplace}"
                )
            typer.echo()


@plugin_app.command("repos")
def list_repos():
    """List available built-in plugin repositories."""
    if not BUILTIN_PLUGIN_REPOS:
        typer.echo(
            f"{Colors.YELLOW}No built-in plugin repositories available.{Colors.RESET}"
        )
        return

    typer.echo(f"\n{Colors.BOLD}Built-in Plugin Repositories:{Colors.RESET}\n")
    for name, repo in sorted(BUILTIN_PLUGIN_REPOS.items()):
        status = (
            f"{Colors.GREEN}✓{Colors.RESET}"
            if repo.enabled
            else f"{Colors.RED}✗{Colors.RESET}"
        )
        typer.echo(f"{status} {Colors.BOLD}{name}{Colors.RESET}")
        if repo.description:
            typer.echo(f"  {Colors.CYAN}Description:{Colors.RESET} {repo.description}")
        if repo.repo_owner and repo.repo_name:
            typer.echo(
                f"  {Colors.CYAN}Source:{Colors.RESET} github.com/{repo.repo_owner}/{repo.repo_name}"
            )
        typer.echo()

    typer.echo(f"{Colors.CYAN}Install with:{Colors.RESET} cam plugin install <name>")
    typer.echo()


@plugin_app.command("info")
def plugin_info():
    """Show Claude Code plugin system information."""
    handler = _get_handler()

    typer.echo(f"\n{Colors.BOLD}Claude Code Plugin System:{Colors.RESET}\n")

    # Show paths
    typer.echo(f"{Colors.CYAN}Configuration:{Colors.RESET}")
    typer.echo(f"  Home: {handler.home_dir}")
    typer.echo(f"  Plugins: {handler.user_plugins_dir}")
    typer.echo(f"  Marketplaces: {handler.marketplaces_dir}")
    typer.echo(f"  Settings: {handler.settings_file}")

    # Check status
    typer.echo(f"\n{Colors.CYAN}Status:{Colors.RESET}")

    home_exists = handler.home_dir.exists()
    status = (
        f"{Colors.GREEN}✓{Colors.RESET}"
        if home_exists
        else f"{Colors.RED}✗{Colors.RESET}"
    )
    typer.echo(f"  {status} Home directory exists")

    plugins_exists = handler.user_plugins_dir.exists()
    status = (
        f"{Colors.GREEN}✓{Colors.RESET}"
        if plugins_exists
        else f"{Colors.RED}✗{Colors.RESET}"
    )
    typer.echo(f"  {status} Plugins directory exists")

    cli_path = handler.get_cli_path()
    status = (
        f"{Colors.GREEN}✓{Colors.RESET}" if cli_path else f"{Colors.RED}✗{Colors.RESET}"
    )
    typer.echo(f"  {status} Claude CLI: {cli_path or 'Not found'}")

    # Show marketplaces
    marketplaces = handler.get_known_marketplaces()
    typer.echo(
        f"\n{Colors.CYAN}Marketplaces:{Colors.RESET} {len(marketplaces)} configured"
    )
    for name in marketplaces:
        typer.echo(f"  • {name}")

    # Show enabled plugins
    enabled = handler.get_enabled_plugins()
    enabled_count = sum(1 for v in enabled.values() if v)
    typer.echo(f"\n{Colors.CYAN}Plugins:{Colors.RESET} {enabled_count} enabled")

    # Built-in repos
    if BUILTIN_PLUGIN_REPOS:
        typer.echo(f"\n{Colors.CYAN}Built-in Repositories:{Colors.RESET}")
        for name in BUILTIN_PLUGIN_REPOS:
            typer.echo(f"  • {name}")

    typer.echo()


# Add shortcuts
plugin_app.command(name="ls", hidden=True)(list_plugins)
plugin_app.command(name="i", hidden=True)(install_plugin)
plugin_app.command(name="rm", hidden=True)(uninstall_plugin)
