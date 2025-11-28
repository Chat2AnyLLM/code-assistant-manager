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
    PluginRepo,
    fetch_repo_info_from_url,
    parse_github_url,
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
        help="Plugin name, plugin@marketplace, or marketplace name",
    ),
    marketplace: Optional[str] = typer.Option(
        None,
        "--marketplace",
        "-m",
        help="Marketplace name (alternative to plugin@marketplace format)",
    ),
):
    """Install a plugin from available marketplaces or add a built-in marketplace."""
    _check_claude_cli()
    handler = _get_handler()
    manager = PluginManager()

    # Check if it's a configured repo (user repos take precedence over builtin)
    configured_repo = manager.get_repo(plugin)
    if configured_repo and configured_repo.repo_owner and configured_repo.repo_name:
        repo_url = f"https://github.com/{configured_repo.repo_owner}/{configured_repo.repo_name}"

        # Handle marketplace type - just add the marketplace
        if configured_repo.type == "marketplace":
            typer.echo(f"{Colors.CYAN}Adding marketplace: {plugin}...{Colors.RESET}")
            success, msg = handler.marketplace_add(repo_url)
            if success:
                typer.echo(f"{Colors.GREEN}✓ Marketplace added: {plugin}{Colors.RESET}")
                typer.echo(
                    f"\n{Colors.CYAN}Browse plugins with:{Colors.RESET} cam plugin search --marketplace {plugin}"
                )
                typer.echo(
                    f"{Colors.CYAN}Install plugins with:{Colors.RESET} cam plugin install <plugin-name>@{plugin}"
                )
            elif "already installed" in msg.lower():
                typer.echo(
                    f"{Colors.YELLOW}Marketplace '{plugin}' is already installed.{Colors.RESET}"
                )
                typer.echo(
                    f"\n{Colors.CYAN}Browse plugins with:{Colors.RESET} cam plugin search --marketplace {plugin}"
                )
            else:
                typer.echo(
                    f"{Colors.RED}✗ Failed to add marketplace: {msg}{Colors.RESET}"
                )
                raise typer.Exit(1)
            return

        # Handle plugin type - add marketplace first if needed, then install plugin
        known_marketplaces = handler.get_known_marketplaces()
        marketplace_exists = any(
            configured_repo.repo_owner.lower() in name.lower()
            or configured_repo.repo_name.lower() in name.lower()
            for name in known_marketplaces
        )

        if not marketplace_exists:
            typer.echo(
                f"{Colors.CYAN}Adding marketplace for plugin: {plugin}...{Colors.RESET}"
            )
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
    """Uninstall an installed plugin.

    For marketplace plugins, this removes the plugin from enabled plugins settings.
    For standalone plugins, this uses Claude CLI to fully uninstall.
    """
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
        # Claude CLI failed - try to remove from settings directly
        # This handles marketplace plugins which can't be "uninstalled" via CLI
        typer.echo(
            f"{Colors.YELLOW}Claude CLI uninstall failed, trying to remove from settings...{Colors.RESET}"
        )

        removed = _remove_plugin_from_settings(handler, plugin)
        if removed:
            typer.echo(
                f"{Colors.GREEN}✓ Removed '{plugin}' from enabled plugins{Colors.RESET}"
            )
            typer.echo(
                f"\n{Colors.YELLOW}Note: Restart Claude Code to apply changes.{Colors.RESET}"
            )
        else:
            typer.echo(
                f"{Colors.RED}✗ Plugin '{plugin}' not found in settings{Colors.RESET}"
            )
            raise typer.Exit(1)


def _remove_plugin_from_settings(handler, plugin: str) -> bool:
    """Remove a plugin from Claude's settings.json.

    Args:
        handler: Claude plugin handler
        plugin: Plugin name (with or without @marketplace suffix)

    Returns:
        True if plugin was found and removed, False otherwise
    """
    import json

    settings_file = handler.settings_file
    if not settings_file.exists():
        return False

    try:
        with open(settings_file, "r") as f:
            settings = json.load(f)
    except Exception:
        return False

    enabled = settings.get("enabledPlugins", {})
    if not enabled:
        return False

    # Find matching plugin key(s)
    keys_to_remove = []
    plugin_lower = plugin.lower()
    for key in enabled:
        # Match exact key or plugin name part (before @)
        key_name = key.split("@")[0] if "@" in key else key
        if key.lower() == plugin_lower or key_name.lower() == plugin_lower:
            keys_to_remove.append(key)

    if not keys_to_remove:
        return False

    # Remove the plugin(s)
    for key in keys_to_remove:
        del enabled[key]

    settings["enabledPlugins"] = enabled

    # Write back
    try:
        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception:
        return False


def _set_plugin_enabled(handler, plugin: str, enabled: bool) -> bool:
    """Set a plugin's enabled state in Claude's settings.json.

    Args:
        handler: Claude plugin handler
        plugin: Plugin name (with or without @marketplace suffix)
        enabled: True to enable, False to disable

    Returns:
        True if plugin was found and updated, False otherwise
    """
    import json

    settings_file = handler.settings_file
    if not settings_file.exists():
        return False

    try:
        with open(settings_file, "r") as f:
            settings = json.load(f)
    except Exception:
        return False

    enabled_plugins = settings.get("enabledPlugins", {})

    # Find matching plugin key
    plugin_lower = plugin.lower()
    matching_key = None
    for key in enabled_plugins:
        key_name = key.split("@")[0] if "@" in key else key
        if key.lower() == plugin_lower or key_name.lower() == plugin_lower:
            matching_key = key
            break

    if not matching_key:
        return False

    # Update the enabled state
    enabled_plugins[matching_key] = enabled
    settings["enabledPlugins"] = enabled_plugins

    # Write back
    try:
        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception:
        return False


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
        # Claude CLI failed - try to enable in settings directly
        typer.echo(
            f"{Colors.YELLOW}Claude CLI enable failed, trying to update settings...{Colors.RESET}"
        )

        enabled = _set_plugin_enabled(handler, plugin, True)
        if enabled:
            typer.echo(f"{Colors.GREEN}✓ Enabled '{plugin}' in settings{Colors.RESET}")
            typer.echo(
                f"\n{Colors.YELLOW}Note: Restart Claude Code to apply changes.{Colors.RESET}"
            )
        else:
            typer.echo(
                f"{Colors.RED}✗ Plugin '{plugin}' not found in settings{Colors.RESET}"
            )
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
        # Claude CLI failed - try to disable in settings directly
        typer.echo(
            f"{Colors.YELLOW}Claude CLI disable failed, trying to update settings...{Colors.RESET}"
        )

        disabled = _set_plugin_enabled(handler, plugin, False)
        if disabled:
            typer.echo(f"{Colors.GREEN}✓ Disabled '{plugin}' in settings{Colors.RESET}")
            typer.echo(
                f"\n{Colors.YELLOW}Note: Restart Claude Code to apply changes.{Colors.RESET}"
            )
        else:
            typer.echo(
                f"{Colors.RED}✗ Plugin '{plugin}' not found in settings{Colors.RESET}"
            )
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
    """List available plugin repositories and marketplaces (built-in + user)."""
    manager = PluginManager()

    # Get all repos (builtin + user)
    all_repos = manager.get_all_repos()
    user_repos = manager.get_user_repos()

    if not all_repos:
        typer.echo(f"{Colors.YELLOW}No plugin repositories available.{Colors.RESET}")
        typer.echo(
            f"\n{Colors.CYAN}Add a repo with:{Colors.RESET} cam plugin fetch <github-url> --save"
        )
        return

    # Separate plugins and marketplaces
    plugins = {k: v for k, v in all_repos.items() if v.type == "plugin"}
    marketplaces = {k: v for k, v in all_repos.items() if v.type == "marketplace"}

    def _print_repo(name: str, repo: PluginRepo, is_user: bool = False):
        status = (
            f"{Colors.GREEN}✓{Colors.RESET}"
            if repo.enabled
            else f"{Colors.RED}✗{Colors.RESET}"
        )
        user_tag = f" {Colors.YELLOW}(user){Colors.RESET}" if is_user else ""
        typer.echo(f"{status} {Colors.BOLD}{name}{Colors.RESET}{user_tag}")
        if repo.description:
            typer.echo(f"  {Colors.CYAN}Description:{Colors.RESET} {repo.description}")
        if repo.repo_owner and repo.repo_name:
            typer.echo(
                f"  {Colors.CYAN}Source:{Colors.RESET} github.com/{repo.repo_owner}/{repo.repo_name}"
            )
        typer.echo()

    if plugins:
        typer.echo(f"\n{Colors.BOLD}Plugins:{Colors.RESET}\n")
        for name, repo in sorted(plugins.items()):
            _print_repo(name, repo, name in user_repos)
        typer.echo(
            f"{Colors.CYAN}Install with:{Colors.RESET} cam plugin install <name>"
        )

    if marketplaces:
        typer.echo(f"\n{Colors.BOLD}Marketplaces:{Colors.RESET}\n")
        for name, repo in sorted(marketplaces.items()):
            _print_repo(name, repo, name in user_repos)
        typer.echo(
            f"{Colors.CYAN}Add marketplace with:{Colors.RESET} cam plugin install <marketplace-name>"
        )

    typer.echo(
        f"\n{Colors.CYAN}Add new repo:{Colors.RESET} cam plugin fetch <github-url> --save"
    )
    typer.echo()


# ==================== Browse Marketplace Helper Functions ====================


def _resolve_marketplace_repo(
    manager: PluginManager, handler: ClaudePluginHandler, marketplace: str
) -> tuple[Optional[str], Optional[str], str]:
    """Resolve marketplace name to repo owner/name/branch.

    Returns:
        Tuple of (repo_owner, repo_name, repo_branch) or (None, None, "main") if not found
    """
    repo = manager.get_repo(marketplace)

    if repo and repo.repo_owner and repo.repo_name:
        return repo.repo_owner, repo.repo_name, repo.repo_branch

    # Try Claude's known marketplaces as fallback
    return _resolve_from_known_marketplaces(handler, marketplace)


def _resolve_from_known_marketplaces(
    handler: ClaudePluginHandler, marketplace: str
) -> tuple[Optional[str], Optional[str], str]:
    """Fallback resolution from Claude's known_marketplaces.json."""
    import json

    known_file = handler.known_marketplaces_file
    if not known_file.exists():
        return None, None, "main"

    try:
        with open(known_file, "r") as f:
            known = json.load(f)

        if marketplace not in known:
            return None, None, "main"

        source_url = known[marketplace].get("source", {}).get("url", "")
        if "github.com" not in source_url:
            return None, None, "main"

        parsed = parse_github_url(source_url)
        if parsed:
            return parsed
    except Exception:
        pass

    return None, None, "main"


def _filter_plugins(
    plugins: list[dict],
    query: Optional[str] = None,
    category: Optional[str] = None,
) -> list[dict]:
    """Filter plugins by query string and/or category."""
    result = plugins

    if query:
        query_lower = query.lower()
        result = [
            p
            for p in result
            if query_lower in p.get("name", "").lower()
            or query_lower in p.get("description", "").lower()
        ]

    if category:
        category_lower = category.lower()
        result = [p for p in result if category_lower in p.get("category", "").lower()]

    return result


def _display_marketplace_not_found(
    manager: PluginManager, handler: ClaudePluginHandler, marketplace: str
) -> None:
    """Display error message when marketplace is not found."""
    typer.echo(
        f"{Colors.RED}✗ Marketplace '{marketplace}' not found in config or Claude.{Colors.RESET}"
    )
    typer.echo(f"\n{Colors.CYAN}Available repos:{Colors.RESET}")
    for name in manager.get_all_repos():
        typer.echo(f"  • {name}")
    typer.echo(f"\n{Colors.CYAN}Installed marketplaces:{Colors.RESET}")
    for name in handler.get_known_marketplaces():
        typer.echo(f"  • {name}")


def _display_marketplace_header(
    info, query: Optional[str], category: Optional[str], total: int
) -> None:
    """Display marketplace info header."""
    typer.echo(
        f"\n{Colors.BOLD}{info.name}{Colors.RESET} - {info.description or 'No description'}"
    )
    if info.version:
        typer.echo(f"Version: {info.version}")
    typer.echo(f"Total plugins: {info.plugin_count}")
    if query or category:
        typer.echo(f"Matching: {total}")


def _display_plugin(plugin: dict) -> None:
    """Display a single plugin entry."""
    name = plugin.get("name", "unknown")
    version = plugin.get("version", "")
    desc = plugin.get("description", "")
    cat = plugin.get("category", "")

    version_str = f" v{version}" if version else ""
    cat_str = f" [{cat}]" if cat else ""

    typer.echo(
        f"  {Colors.BOLD}{name}{Colors.RESET}{version_str}{Colors.CYAN}{cat_str}{Colors.RESET}"
    )
    if desc:
        if len(desc) > 80:
            desc = desc[:77] + "..."
        typer.echo(f"    {desc}")


def _display_marketplace_footer(info, marketplace: str, total: int, limit: int) -> None:
    """Display marketplace footer with categories and install hint."""
    if total > limit:
        typer.echo(f"\n  ... and {total - limit} more")

    categories = {p.get("category") for p in info.plugins if p.get("category")}
    if categories:
        typer.echo(
            f"\n{Colors.CYAN}Categories:{Colors.RESET} {', '.join(sorted(categories))}"
        )

    typer.echo(
        f"\n{Colors.CYAN}Install with:{Colors.RESET} cam plugin install <plugin-name>@{marketplace}"
    )
    typer.echo()


# ==================== Browse Marketplace Command ====================


@plugin_app.command("browse")
def browse_marketplace(
    marketplace: str = typer.Argument(
        ...,
        help="Marketplace name to browse (from 'cam plugin repos')",
    ),
    query: Optional[str] = typer.Option(
        None,
        "--query",
        "-q",
        help="Filter plugins by name or description",
    ),
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter plugins by category",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Maximum number of plugins to show",
    ),
):
    """Browse plugins in a configured marketplace.

    Fetches the marketplace manifest from GitHub and lists all available plugins.
    Use --query to search by name/description, --category to filter by category.
    """
    from code_assistant_manager.plugins.fetch import fetch_repo_info

    manager = PluginManager()
    handler = _get_handler()

    # Resolve marketplace to repo info
    repo_owner, repo_name, repo_branch = _resolve_marketplace_repo(
        manager, handler, marketplace
    )

    if not repo_owner or not repo_name:
        _display_marketplace_not_found(manager, handler, marketplace)
        raise typer.Exit(1)

    # Fetch plugins
    typer.echo(f"{Colors.CYAN}Fetching plugins from {marketplace}...{Colors.RESET}")
    info = fetch_repo_info(repo_owner, repo_name, repo_branch)

    if not info or not info.plugins:
        typer.echo(f"{Colors.RED}✗ Could not fetch plugins from repo.{Colors.RESET}")
        raise typer.Exit(1)

    # Filter and display
    plugins = _filter_plugins(info.plugins, query, category)
    total = len(plugins)
    plugins = plugins[:limit]

    _display_marketplace_header(info, query, category, total)
    typer.echo(f"\n{Colors.BOLD}Plugins:{Colors.RESET}\n")

    for plugin in plugins:
        _display_plugin(plugin)

    _display_marketplace_footer(info, marketplace, total, limit)


@plugin_app.command("fetch")
def fetch_repo(
    url: str = typer.Argument(
        ...,
        help="GitHub URL or owner/repo (e.g., https://github.com/owner/repo or owner/repo)",
    ),
    save: bool = typer.Option(
        False,
        "--save",
        "-s",
        help="Save the fetched repo to user config",
    ),
):
    """Fetch and detect repo type (plugin or marketplace) from GitHub.

    Analyzes a GitHub repository to determine if it's a single plugin
    or a marketplace with multiple plugins, then optionally saves it
    to your local configuration.
    """
    typer.echo(f"{Colors.CYAN}Fetching repository info...{Colors.RESET}")

    # Parse and validate URL
    parsed = parse_github_url(url)
    if not parsed:
        typer.echo(f"{Colors.RED}✗ Invalid GitHub URL: {url}{Colors.RESET}")
        raise typer.Exit(1)

    owner, repo, branch = parsed
    typer.echo(f"  Repository: {Colors.BOLD}{owner}/{repo}{Colors.RESET}")

    # Fetch repo info
    info = fetch_repo_info_from_url(url)
    if not info:
        typer.echo(
            f"{Colors.RED}✗ Could not fetch repository info. "
            f"Make sure the repo has .claude-plugin/marketplace.json{Colors.RESET}"
        )
        raise typer.Exit(1)

    # Display results
    typer.echo(f"\n{Colors.BOLD}Repository Information:{Colors.RESET}\n")
    typer.echo(f"  {Colors.CYAN}Name:{Colors.RESET} {info.name}")
    typer.echo(f"  {Colors.CYAN}Type:{Colors.RESET} {info.type}")
    typer.echo(f"  {Colors.CYAN}Description:{Colors.RESET} {info.description or 'N/A'}")
    typer.echo(f"  {Colors.CYAN}Branch:{Colors.RESET} {info.branch}")

    if info.version:
        typer.echo(f"  {Colors.CYAN}Version:{Colors.RESET} {info.version}")

    if info.type == "marketplace":
        typer.echo(f"  {Colors.CYAN}Plugin Count:{Colors.RESET} {info.plugin_count}")
        if info.plugins and len(info.plugins) <= 10:
            typer.echo(f"\n  {Colors.CYAN}Plugins:{Colors.RESET}")
            for p in info.plugins[:10]:
                typer.echo(f"    • {p.get('name', 'unknown')}")
        elif info.plugins:
            typer.echo(f"\n  {Colors.CYAN}Plugins:{Colors.RESET} (showing first 10)")
            for p in info.plugins[:10]:
                typer.echo(f"    • {p.get('name', 'unknown')}")
            typer.echo(f"    ... and {len(info.plugins) - 10} more")
    else:
        if info.plugin_path:
            typer.echo(f"  {Colors.CYAN}Plugin Path:{Colors.RESET} {info.plugin_path}")

    # Save if requested
    if save:
        manager = PluginManager()

        # Check if already exists
        existing = manager.get_repo(info.name)
        if existing:
            typer.echo(
                f"\n{Colors.YELLOW}Repository '{info.name}' already exists in config.{Colors.RESET}"
            )
            if not typer.confirm("Overwrite?"):
                raise typer.Exit(0)

        # Create PluginRepo and save
        plugin_repo = PluginRepo(
            name=info.name,
            description=info.description,
            repo_owner=info.owner,
            repo_name=info.repo,
            repo_branch=info.branch,
            plugin_path=info.plugin_path,
            type=info.type,
            enabled=True,
        )
        manager.add_user_repo(plugin_repo)
        typer.echo(
            f"\n{Colors.GREEN}✓ Saved '{info.name}' to user config as {info.type}{Colors.RESET}"
        )
        typer.echo(f"  Config file: {manager.plugin_repos_file}")

        # Show next steps
        if info.type == "marketplace":
            typer.echo(
                f"\n{Colors.CYAN}Next:{Colors.RESET} cam plugin install {info.name}"
            )
        else:
            typer.echo(
                f"\n{Colors.CYAN}Next:{Colors.RESET} cam plugin install {info.name}"
            )
    else:
        typer.echo(
            f"\n{Colors.CYAN}To save:{Colors.RESET} cam plugin fetch '{url}' --save"
        )

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
