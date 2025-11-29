"""Marketplace commands.

Handles marketplace update operations.
"""

import logging
from typing import Optional

import typer

from code_assistant_manager.cli.plugins.plugin_install_commands import (
    install_plugin,
    uninstall_plugin,
)
from code_assistant_manager.cli.plugins.plugin_management_commands import list_plugins
from code_assistant_manager.menu.base import Colors
from code_assistant_manager.plugins import VALID_APP_TYPES, get_handler

plugin_app = typer.Typer(
    help="Manage plugins and marketplaces for AI assistants (Claude, CodeBuddy)",
    no_args_is_help=True,
)

# ==================== Marketplace Subcommand ====================

marketplace_app = typer.Typer(
    help="Manage installed marketplaces",
    no_args_is_help=True,
)


@marketplace_app.command("update")
def marketplace_update(
    name: Optional[str] = typer.Argument(
        None,
        help="Marketplace name to update (updates all if not specified)",
    ),
    app_type: str = typer.Option(
        "claude",
        "--app",
        "-a",
        help=f"App type ({', '.join(VALID_APP_TYPES)})",
    ),
):
    """Update installed marketplace(s) from their source.

    This command updates installed marketplaces by pulling the latest changes
    from their source repositories. If no name is specified, all marketplaces
    are updated.

    Examples:
        cam plugin marketplace update                    # Update all marketplaces
        cam plugin marketplace update my-marketplace     # Update specific marketplace
    """
    from code_assistant_manager.cli.option_utils import resolve_single_app

    app = resolve_single_app(app_type, VALID_APP_TYPES, default="claude")
    handler = get_handler(app)

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


# ==================== Add shortcuts ====================
plugin_app.command(name="ls", hidden=True)(list_plugins)
plugin_app.command(name="i", hidden=True)(install_plugin)
plugin_app.command(name="rm", hidden=True)(uninstall_plugin)
