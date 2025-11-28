"""CLI command definitions for Code Assistant Manager."""

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import typer
from typer import Context

from code_assistant_manager.cli.app import app
from code_assistant_manager.cli.options import (
    CONFIG_FILE_OPTION,
    FORCE_OPTION,
    INSTALL_ALIAS_TARGET_OPTION,
    KEEP_CONFIG_OPTION,
    SHELL_OPTION,
    TARGET_OPTION,
    TOOL_NAME_OPTION,
    UNINSTALL_TARGET_OPTION,
    UPGRADE_ALIAS_TARGET_OPTION,
    VALIDATE_VERBOSE_OPTION,
    VERBOSE_DOCTOR_OPTION,
    VERBOSE_OPTION,
)
from code_assistant_manager.config import ConfigManager
from code_assistant_manager.menu.base import Colors
from code_assistant_manager.tools import (
    display_all_tool_endpoints,
    display_tool_endpoints,
    get_registered_tools,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Uninstall Helper Classes and Functions
# ============================================================================


@dataclass
class UninstallContext:
    """Context for uninstall operation."""

    tools_to_uninstall: List[str]
    installed_tools: List[str]
    config_dirs: Dict[str, Path]
    tools_with_config: List[str]
    keep_config: bool
    force: bool


# Tool configuration directories mapping
TOOL_CONFIG_DIRS: Dict[str, Path] = {
    "claude": Path.home() / ".claude",
    "crush": Path.home() / ".config" / "crush",
    "codex": Path.home() / ".codex",
    "gemini": Path.home() / ".gemini",
    "codebuddy": Path.home() / ".codebuddy",
    "droid": Path.home() / ".droid",
    "iflow": Path.home() / ".iflow",
    "neovate": Path.home() / ".neovate",
    "qodercli": Path.home() / ".qodercli",
    "qwen": Path.home() / ".qwen",
    "zed": Path.home() / ".zed",
    "copilot": Path.home() / ".copilot",
    "cursor-agent": Path.home() / ".cursor-agent",
}

# NPM package name mapping
NPM_PACKAGE_MAP: Dict[str, str] = {
    "claude": "@anthropic-ai/claude-code",
    "crush": "@charmland/crush",
    "codex": "@openai/codex",
    "gemini": "@google/genai",
    "qwen": "@qwen-code/qwen-code",
    "codebuddy": "@tencent-ai/codebuddy-code",
    "droid": "@factory-ai/droid",
    "iflow": "@iflytek/iflow",
    "neovate": "@neovate/cli",
    "qodercli": "@qoder/qodercli",
    "copilot": "@githubnext/copilot-cli",
    "cursor-agent": "@cursor/agent",
    "zed": "zed",
}


def _get_config_manager(ctx: Context) -> ConfigManager:
    """Get or create ConfigManager from context."""
    try:
        config_path = None
        if ctx and ctx.obj and hasattr(ctx.obj, "get"):
            config_path = ctx.obj.get("config_path")
        return ConfigManager(config_path) if config_path else ConfigManager()
    except Exception:
        return ConfigManager()


def _get_installed_tools(
    target: str, config: ConfigManager
) -> tuple[List[str], Optional[int]]:
    """Get list of installed tools based on target.

    Returns:
        Tuple of (installed_tools, error_code or None)
    """
    upgradeable_tools = get_registered_tools()

    # Validate target
    if target != "all" and target not in upgradeable_tools:
        typer.echo(f"{Colors.RED}Error: Unknown tool {target!r}{Colors.RESET}")
        return [], 1

    # Determine which tools to check
    tools_to_check = [target] if target != "all" else list(upgradeable_tools.keys())

    # Filter to only installed tools
    installed_tools = []
    for tool_name in tools_to_check:
        try:
            tool = upgradeable_tools[tool_name](config)
            if tool._check_command_available(tool.command_name):
                installed_tools.append(tool_name)
        except Exception:
            pass

    return installed_tools, None


def _display_uninstall_plan(ctx: UninstallContext) -> None:
    """Display what will be uninstalled."""
    typer.echo(f"\n{Colors.BOLD}Tools to uninstall:{Colors.RESET}")
    for tool_name in ctx.installed_tools:
        typer.echo(f"  • {tool_name}")

    if ctx.tools_with_config and not ctx.keep_config:
        typer.echo(f"\n{Colors.BOLD}Configuration directories to backup:{Colors.RESET}")
        for tool in ctx.tools_with_config:
            config_dir = ctx.config_dirs.get(tool)
            typer.echo(f"  • {config_dir}")


def _confirm_uninstall(ctx: UninstallContext) -> bool:
    """Prompt for confirmation if not forced."""
    if ctx.force:
        return True

    if ctx.tools_with_config and not ctx.keep_config:
        typer.echo(
            f"\n{Colors.YELLOW}⚠️  Configuration files will be backed up{Colors.RESET}"
        )
    else:
        typer.echo(
            f"\n{Colors.YELLOW}⚠️  Configuration files will be deleted{Colors.RESET}"
        )

    return typer.confirm(
        f"Continue with uninstalling {len(ctx.installed_tools)} tool(s)?"
    )


def _backup_configs(ctx: UninstallContext) -> Optional[Path]:
    """Backup configuration directories.

    Returns:
        Backup directory path or None if no backup was made
    """
    if not ctx.tools_with_config or ctx.keep_config:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = (
        Path.home() / f".config/code-assistant-manager/backup/uninstall_{timestamp}"
    )
    backup_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"\n{Colors.BOLD}Backing up configuration files...{Colors.RESET}")
    for tool in ctx.tools_with_config:
        config_dir = ctx.config_dirs.get(tool)
        try:
            backup_path = backup_dir / tool
            shutil.copytree(config_dir, backup_path)
            typer.echo(
                f"  {Colors.GREEN}✓{Colors.RESET} {tool}: {config_dir} → {backup_path}"
            )
        except Exception as e:
            typer.echo(f"  {Colors.RED}✗{Colors.RESET} {tool}: Failed to backup - {e}")

    return backup_dir


def _uninstall_tools(installed_tools: List[str]) -> List[str]:
    """Uninstall tools using npm.

    Returns:
        List of failed tool names
    """
    typer.echo(f"\n{Colors.BOLD}Uninstalling tools...{Colors.RESET}")
    failed_uninstalls = []

    for tool_name in installed_tools:
        try:
            npm_package = NPM_PACKAGE_MAP.get(tool_name, tool_name)
            uninstall_cmd = f"npm uninstall -g {npm_package}"

            result = subprocess.run(
                uninstall_cmd, shell=True, capture_output=True, text=True
            )

            if result.returncode == 0:
                typer.echo(f"  {Colors.GREEN}✓{Colors.RESET} {tool_name}")
            else:
                typer.echo(
                    f"  {Colors.RED}✗{Colors.RESET} {tool_name}: {result.stderr.strip()}"
                )
                failed_uninstalls.append(tool_name)
        except Exception as e:
            typer.echo(f"  {Colors.RED}✗{Colors.RESET} {tool_name}: {e}")
            failed_uninstalls.append(tool_name)

    return failed_uninstalls


def _remove_configs(ctx: UninstallContext) -> None:
    """Remove configuration directories."""
    if ctx.keep_config:
        return

    typer.echo(f"\n{Colors.BOLD}Removing configuration files...{Colors.RESET}")
    for tool in ctx.tools_with_config:
        config_dir = ctx.config_dirs.get(tool)
        try:
            shutil.rmtree(config_dir)
            typer.echo(f"  {Colors.GREEN}✓{Colors.RESET} {tool}: {config_dir}")
        except Exception as e:
            typer.echo(f"  {Colors.YELLOW}⚠️  {tool}: {e}{Colors.RESET}")


def _display_summary(
    installed_tools: List[str],
    failed_uninstalls: List[str],
    backup_dir: Optional[Path],
) -> int:
    """Display uninstall summary and return exit code."""
    successful_uninstalls = len(installed_tools) - len(failed_uninstalls)
    typer.echo(f"\n{Colors.BOLD}Uninstall Summary:{Colors.RESET}")
    typer.echo(f"  Successful: {successful_uninstalls}/{len(installed_tools)}")

    if backup_dir:
        typer.echo(f"  Backup location: {backup_dir}")

    if failed_uninstalls:
        typer.echo(
            f"  {Colors.RED}Failed:{Colors.RESET} {', '.join(failed_uninstalls)}"
        )
        return 1

    return 0


def upgrade(
    ctx: Context,
    target: str = TARGET_OPTION,
    verbose: bool = VERBOSE_OPTION,
):
    """Upgrade CLI tools (alias: u). If not installed, will install.
    If installed, will try to upgrade."""
    from code_assistant_manager.cli.upgrade import handle_upgrade_command

    logger.debug(f"Upgrade command called with target: {target}")
    config_path = ctx.obj.get("config_path")
    logger.debug(f"Using config path for upgrade: {config_path}")

    # Initialize config
    try:
        config = ConfigManager(config_path)
        # Validate configuration
        is_valid, errors = config.validate_config()
        if not is_valid:
            logger.error(f"Configuration validation errors during upgrade: {errors}")
            typer.echo("Configuration validation errors:")
            for error in errors:
                typer.echo(f"  - {error}")
            raise typer.Exit(1)
        logger.debug("Configuration validated for upgrade")
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found during upgrade: {e}")
        typer.echo(f"Error: {e}")
        raise typer.Exit(1) from e

    # Handle --endpoints option if specified
    endpoints = ctx.obj.get("endpoints")
    if endpoints:
        from code_assistant_manager.tools import (
            display_all_tool_endpoints,
            display_tool_endpoints,
        )

        logger.debug(f"Handling endpoints option in upgrade: {endpoints}")
        if endpoints == "all":
            display_all_tool_endpoints(config)
        else:
            display_tool_endpoints(config, endpoints)
        raise typer.Exit()

    registered_tools = get_registered_tools()
    logger.debug(f"Starting upgrade process for target: {target}")
    # By default run quietly; verbose flag overrides to show installer output
    sys.exit(handle_upgrade_command(target, registered_tools, config, verbose=verbose))


@app.command()
def doctor(
    ctx: Context,
    verbose: bool = VERBOSE_DOCTOR_OPTION,
    config: Optional[str] = CONFIG_FILE_OPTION,
):
    """Run diagnostic checks on the code-assistant-manager installation (alias: d)"""
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["debug"] = False
    ctx.obj["endpoints"] = None

    from code_assistant_manager.cli.doctor import run_doctor_checks

    logger.debug(f"Doctor command called with verbose: {verbose}")
    config_path = ctx.obj.get("config_path")
    logger.debug(f"Using config path for doctor: {config_path}")

    # Initialize config
    try:
        config = ConfigManager(config_path)
        # Load environment variables from .env file
        config.load_env_file()
        # Validate configuration
        is_valid, errors = config.validate_config()
        if not is_valid:
            logger.error(f"Configuration validation errors in doctor: {errors}")
            typer.echo("Configuration validation errors:")
            for error in errors:
                typer.echo(f"  - {error}")
            raise typer.Exit(1)
        logger.debug("Configuration loaded and validated for doctor")
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found in doctor: {e}")
        typer.echo(f"Error: {e}")
        raise typer.Exit(1) from e

    # Handle --endpoints option if specified
    endpoints = ctx.obj.get("endpoints")
    if endpoints:
        from code_assistant_manager.tools import (
            display_all_tool_endpoints,
            display_tool_endpoints,
        )

        logger.debug(f"Handling endpoints option in doctor: {endpoints}")
        if endpoints == "all":
            display_all_tool_endpoints(config)
        else:
            display_tool_endpoints(config, endpoints)
        raise typer.Exit()

    # Run diagnostic checks
    logger.debug("Starting diagnostic checks")
    return run_doctor_checks(config, verbose)


def launch_alias(ctx: Context, tool_name: str = TOOL_NAME_OPTION):
    """Alias for 'launch' command."""
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = None
    ctx.obj["debug"] = False
    ctx.obj["endpoints"] = None

    if tool_name:
        # Direct tool invocation - same as main() function does
        registered_tools = get_registered_tools()
        if tool_name in registered_tools and tool_name != "mcp":
            config_path = ctx.obj.get("config_path")
            try:
                config = ConfigManager(config_path)
                is_valid, errors = config.validate_config()
                if not is_valid:
                    typer.echo("Configuration validation errors:")
                    for error in errors:
                        typer.echo(f"  - {error}")
                    return 1
                tool_class = registered_tools.get(tool_name)
                tool = tool_class(config)
                return tool.run([])
            except Exception as e:
                from code_assistant_manager.exceptions import create_error_handler

                error_handler = create_error_handler("cli")
                structured_error = error_handler(e, "Tool execution failed")
                typer.echo(structured_error.get_detailed_message())
                return 1
        else:
            typer.echo(f"Unknown tool: {tool_name}")
            return 1
    else:
        # Show interactive menu for tool selection
        from code_assistant_manager.menu.menus import display_centered_menu

        logger.debug("No tool specified in 'l' alias, showing interactive menu")
        registered_tools = get_registered_tools()
        editor_tools = {k: v for k, v in registered_tools.items() if k not in ["mcp"]}
        tool_names = sorted(editor_tools.keys())

        logger.debug(f"Available tools for menu: {tool_names}")

        success, selected_idx = display_centered_menu(
            title="Select AI Code Editor", items=tool_names, cancel_text="Cancel"
        )

        if not success or selected_idx is None:
            logger.debug("User cancelled menu selection")
            raise typer.Exit(0)

        selected_tool = tool_names[selected_idx]
        logger.debug(f"User selected tool: {selected_tool}")

        # Get config and launch the selected tool
        config_path = ctx.obj.get("config_path")
        logger.debug(f"Using config path: {config_path}")

        try:
            config = ConfigManager(config_path)
            is_valid, errors = config.validate_config()
            if not is_valid:
                logger.error(f"Configuration validation errors: {errors}")
                typer.echo("Configuration validation errors:")
                for error in errors:
                    typer.echo(f"  - {error}")
                raise typer.Exit(1)
            logger.debug("Configuration loaded and validated successfully")
        except FileNotFoundError as e:
            logger.error(f"Configuration file not found: {e}")
            typer.echo(f"Error: {e}")
            raise typer.Exit(1) from e

        tool_class = editor_tools[selected_tool]
        tool_instance = tool_class(config)
        sys.exit(tool_instance.run([]))


@app.command("upgrade")
def upgrade_command(
    ctx: Context,
    target: str = TARGET_OPTION,
    verbose: bool = VERBOSE_OPTION,
    config: Optional[str] = CONFIG_FILE_OPTION,
):
    """Upgrade CLI tools (alias: u). If not installed, will install."""
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["debug"] = False
    ctx.obj["endpoints"] = None

    return upgrade(ctx, target, verbose)


@app.command("u", hidden=True)
def upgrade_alias(
    ctx: Context,
    target: str = UPGRADE_ALIAS_TARGET_OPTION,
    config: Optional[str] = CONFIG_FILE_OPTION,
):
    """Alias for 'upgrade' command."""
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["debug"] = False
    ctx.obj["endpoints"] = None

    return upgrade(ctx, target)


@app.command("install")
def install_command(
    ctx: Context,
    target: str = TARGET_OPTION,
    verbose: bool = VERBOSE_OPTION,
    config: Optional[str] = CONFIG_FILE_OPTION,
):
    """Install CLI tools (alias: i). Same as upgrade - if not installed, will install. If installed, will try to upgrade."""
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["debug"] = False
    ctx.obj["endpoints"] = None

    return upgrade(ctx, target, verbose)


@app.command("i", hidden=True)
def install_alias(
    ctx: Context,
    target: str = INSTALL_ALIAS_TARGET_OPTION,
    config: Optional[str] = CONFIG_FILE_OPTION,
):
    """Alias for 'install' command."""
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["debug"] = False
    ctx.obj["endpoints"] = None

    return upgrade(ctx, target)


@app.command("uninstall")
def uninstall_command(
    ctx: Context,
    target: str = UNINSTALL_TARGET_OPTION,
    force: bool = FORCE_OPTION,
    keep_config: bool = KEEP_CONFIG_OPTION,
    config: Optional[str] = CONFIG_FILE_OPTION,
):
    """Uninstall CLI tools and backup their configuration files."""
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["debug"] = False
    ctx.obj["endpoints"] = None

    return uninstall(ctx, target, force, keep_config)


@app.command("version")
def version_command():
    """Show version information."""
    from code_assistant_manager import __version__

    typer.echo(f"code-assistant-manager version {__version__}")
    raise typer.Exit()


@app.command("v", hidden=True)
def version_alias():
    """Alias for 'version' command."""
    return version_command()


def install(
    ctx: Context,
    target: str = TARGET_OPTION,
    verbose: bool = VERBOSE_OPTION,
):
    """Install CLI tools (alias: i). Same as upgrade - if not installed, will install. If installed, will try to upgrade."""
    return upgrade(ctx, target, verbose)


def upgrade_alias(ctx: Context, target: str = UPGRADE_ALIAS_TARGET_OPTION):
    """Alias for 'upgrade' command."""
    return upgrade(ctx, target)


def install_alias(ctx: Context, target: str = INSTALL_ALIAS_TARGET_OPTION):
    """Alias for 'install' command."""
    return install(ctx, target)


def uninstall(
    ctx: Context,
    target: str = UNINSTALL_TARGET_OPTION,
    force: bool = FORCE_OPTION,
    keep_config: bool = KEEP_CONFIG_OPTION,
):
    """Uninstall CLI tools and backup their configuration files."""
    config = _get_config_manager(ctx)

    # Get installed tools
    installed_tools, error_code = _get_installed_tools(target, config)
    if error_code is not None:
        return error_code

    if not installed_tools:
        typer.echo(f"{Colors.YELLOW}No tools found to uninstall{Colors.RESET}")
        return 0

    # Build uninstall context
    tools_with_config = [
        tool for tool in installed_tools if TOOL_CONFIG_DIRS.get(tool, Path()).exists()
    ]

    uninstall_ctx = UninstallContext(
        tools_to_uninstall=[target] if target != "all" else installed_tools,
        installed_tools=installed_tools,
        config_dirs=TOOL_CONFIG_DIRS,
        tools_with_config=tools_with_config,
        keep_config=keep_config,
        force=force,
    )

    # Display plan and confirm
    _display_uninstall_plan(uninstall_ctx)

    if not _confirm_uninstall(uninstall_ctx):
        typer.echo("Uninstall cancelled")
        return 0

    # Execute uninstall
    backup_dir = _backup_configs(uninstall_ctx)
    failed_uninstalls = _uninstall_tools(installed_tools)
    _remove_configs(uninstall_ctx)

    return _display_summary(installed_tools, failed_uninstalls, backup_dir)


@app.command("un", hidden=True)
def uninstall_alias(
    ctx: Context,
    target: str = UNINSTALL_TARGET_OPTION,
    force: bool = FORCE_OPTION,
    keep_config: bool = KEEP_CONFIG_OPTION,
    config: Optional[str] = CONFIG_FILE_OPTION,
):
    """Alias for 'uninstall' command."""
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["debug"] = False
    ctx.obj["endpoints"] = None

    return uninstall(ctx, target, force, keep_config)


@app.command("d", hidden=True)
def doctor_alias(
    ctx: Context,
    verbose: bool = VERBOSE_DOCTOR_OPTION,
    config: Optional[str] = CONFIG_FILE_OPTION,
):
    """Alias for 'doctor' command."""
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["debug"] = False
    ctx.obj["endpoints"] = None

    return doctor(ctx, verbose, config)


def validate_config(
    config: Optional[str] = CONFIG_FILE_OPTION,
    verbose: bool = VALIDATE_VERBOSE_OPTION,
):
    """Validate the configuration file for syntax and semantic errors."""
    from code_assistant_manager.config import ConfigManager
    from code_assistant_manager.menu.base import Colors

    try:
        cm = ConfigManager(config)
        typer.echo(
            f"{Colors.GREEN}✓ Configuration file loaded successfully{Colors.RESET}"
        )

        # Run full validation
        is_valid, errors = cm.validate_config()

        if is_valid:
            typer.echo(f"{Colors.GREEN}✓ Configuration validation passed{Colors.RESET}")
            return 0
        else:
            typer.echo(f"{Colors.RED}✗ Configuration validation failed:{Colors.RESET}")
            for error in errors:
                typer.echo(f"  - {error}")
            return 1

    except FileNotFoundError as e:
        typer.echo(f"{Colors.RED}✗ Configuration file not found: {e}{Colors.RESET}")
        return 1
    except ValueError as e:
        typer.echo(f"{Colors.RED}✗ Configuration validation failed: {e}{Colors.RESET}")
        return 1
    except Exception as e:
        typer.echo(
            f"{Colors.RED}✗ Unexpected error during validation: {e}{Colors.RESET}"
        )
        return 1


@app.command()
def completion(shell: str = SHELL_OPTION):
    """Generate shell completion scripts."""
    if shell not in ["bash", "zsh"]:
        typer.echo(f"Error: Unsupported shell {shell!r}. Supported shells: bash, zsh")
        raise typer.Exit(1)

    # Generate basic completion script with common commands
    completion_script = generate_completion_script(shell)

    typer.echo(f"# Shell completion script for {shell}")
    typer.echo("# To install, run one of the following:")
    typer.echo("#")
    typer.echo("# Option 1: Add to ~/.bashrc or ~/.zshrc")
    typer.echo(
        f"# echo 'source <(code-assistant-manager completion {shell})' >> ~/.{shell}rc"
    )
    typer.echo("#")
    typer.echo("# Option 2: Save to file and source it")
    typer.echo(
        f"# code-assistant-manager completion {shell} > ~/.{shell}_completion_code_assistant_manager"
    )
    typer.echo(
        f"# echo 'source ~/.{shell}_completion_code_assistant_manager' >> ~/.{shell}rc"
    )
    typer.echo("#")
    typer.echo(
        "# Restart your shell or run 'source ~/.bashrc' (or ~/.zshrc) to apply changes"
    )
    typer.echo()
    typer.echo("# Completion script:")
    typer.echo("=" * 50)
    typer.echo(completion_script)


@app.command("c", hidden=True)
def completion_alias_short(shell: str = SHELL_OPTION):
    """Alias for 'completion' command."""
    return completion(shell)


def generate_completion_script(shell: str) -> str:
    """Generate a comprehensive completion script for the given shell."""
    if shell == "bash":
        return """# code-assistant-manager bash completion

_code_assistant_manager_completions()
{
    local cur prev opts base words cword
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    words="${COMP_WORDS[@]}"
    cword=$COMP_CWORD

    # Main commands (visible and hidden aliases)
    commands="launch l config cf mcp m prompt p skill s upgrade u install i uninstall un doctor d version v completion comp c --help --version --config --endpoints --debug -d"

    # Tool names for launch command
    tools="claude codex copilot gemini droid qwen codebuddy iflow qodercli zed neovate crush cursor-agent"

    # MCP subcommands (mcp server ...)
    mcp_server_commands="list search show add remove update"

    # Config subcommands
    config_commands="validate list ls l"

    # Prompt subcommands
    prompt_commands="list view create update delete sync import-live show-live import export unsync status"

    # Skill subcommands
    skill_commands="list fetch view create update delete install uninstall repos add-repo remove-repo import export installed uninstall-all"

    # Global flags
    global_flags="--help --version --config --endpoints --debug -d"

    # Check if we have a global flag
    for ((i=1; i<cword; i++)); do
        case "${COMP_WORDS[i]}" in
            --config)
                COMPREPLY=( $(compgen -f -- ${cur}) )
                return 0
                ;;
            --endpoints)
                COMPREPLY=( $(compgen -W "all ${tools} mcp" -- ${cur}) )
                return 0
                ;;
        esac
    done

    case "${prev}" in
        launch|l)
            COMPREPLY=( $(compgen -W "${tools}" -- ${cur}) )
            return 0
            ;;
        mcp|m)
            COMPREPLY=( $(compgen -W "server" -- ${cur}) )
            return 0
            ;;
        server)
            # Check if parent is mcp
            if [ "${COMP_WORDS[1]}" = "mcp" ] || [ "${COMP_WORDS[1]}" = "m" ]; then
                COMPREPLY=( $(compgen -W "${mcp_server_commands}" -- ${cur}) )
                return 0
            fi
            ;;
        config|cf)
            COMPREPLY=( $(compgen -W "${config_commands}" -- ${cur}) )
            return 0
            ;;
        prompt|p)
            COMPREPLY=( $(compgen -W "${prompt_commands}" -- ${cur}) )
            return 0
            ;;
        skill|s)
            COMPREPLY=( $(compgen -W "${skill_commands}" -- ${cur}) )
            return 0
            ;;
        upgrade|u)
            COMPREPLY=( $(compgen -W "all ${tools} mcp --verbose -v" -- ${cur}) )
            return 0
            ;;
        install|i)
            COMPREPLY=( $(compgen -W "all ${tools} mcp --verbose -v" -- ${cur}) )
            return 0
            ;;
        uninstall|un)
            COMPREPLY=( $(compgen -W "all ${tools} --force -f --keep-config" -- ${cur}) )
            return 0
            ;;
        doctor|d)
            COMPREPLY=( $(compgen -W "--verbose -v" -- ${cur}) )
            return 0
            ;;
        completion|comp|c)
            COMPREPLY=( $(compgen -W "bash zsh" -- ${cur}) )
            return 0
            ;;
        --config)
            COMPREPLY=( $(compgen -f -- ${cur}) )
            return 0
            ;;
        --endpoints)
            COMPREPLY=( $(compgen -W "all ${tools} mcp" -- ${cur}) )
            return 0
            ;;
        --client|-c)
            COMPREPLY=( $(compgen -W "all ${tools}" -- ${cur}) )
            return 0
            ;;
        --scope|-s)
            COMPREPLY=( $(compgen -W "user project" -- ${cur}) )
            return 0
            ;;
        --app-type|-a)
            COMPREPLY=( $(compgen -W "claude codex gemini qwen codebuddy" -- ${cur}) )
            return 0
            ;;
        --verbose|-v)
            COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
            return 0
            ;;
        # MCP server subcommand options
        list)
            if [ "${COMP_WORDS[1]}" = "mcp" ] || [ "${COMP_WORDS[1]}" = "m" ]; then
                COMPREPLY=( $(compgen -W "--client -c --interactive -i --help" -- ${cur}) )
                return 0
            fi
            ;;
        search)
            if [ "${COMP_WORDS[1]}" = "mcp" ] || [ "${COMP_WORDS[1]}" = "m" ]; then
                COMPREPLY=( $(compgen -W "--help" -- ${cur}) )
                return 0
            fi
            ;;
        show)
            if [ "${COMP_WORDS[1]}" = "mcp" ] || [ "${COMP_WORDS[1]}" = "m" ]; then
                COMPREPLY=( $(compgen -W "--schema --help" -- ${cur}) )
                return 0
            fi
            ;;
        add)
            if [ "${COMP_WORDS[1]}" = "mcp" ] || [ "${COMP_WORDS[1]}" = "m" ]; then
                COMPREPLY=( $(compgen -W "--client -c --method -m --force -f --interactive -i --scope -s --help" -- ${cur}) )
                return 0
            fi
            ;;
        remove)
            if [ "${COMP_WORDS[1]}" = "mcp" ] || [ "${COMP_WORDS[1]}" = "m" ]; then
                COMPREPLY=( $(compgen -W "--client -c --interactive -i --scope -s --help" -- ${cur}) )
                return 0
            fi
            ;;
        update)
            if [ "${COMP_WORDS[1]}" = "mcp" ] || [ "${COMP_WORDS[1]}" = "m" ]; then
                COMPREPLY=( $(compgen -W "--client -c --interactive -i --scope -s --help" -- ${cur}) )
                return 0
            fi
            ;;
    esac

    # Check for second level completion
    if [ $cword -ge 2 ]; then
        case "${COMP_WORDS[1]}" in
            launch|l)
                case "${COMP_WORDS[2]}" in
                    claude|codex|copilot|gemini|droid|qwen|codebuddy|iflow|qodercli|zed|neovate|crush|cursor-agent)
                        COMPREPLY=( $(compgen -W "--config --help" -- ${cur}) )
                        return 0
                        ;;
                esac
                ;;
            mcp|m)
                if [ "${COMP_WORDS[2]}" = "server" ]; then
                    if [ $cword -eq 3 ]; then
                        COMPREPLY=( $(compgen -W "${mcp_server_commands}" -- ${cur}) )
                        return 0
                    fi
                fi
                ;;
            config|cf)
                case "${COMP_WORDS[2]}" in
                    validate)
                        COMPREPLY=( $(compgen -W "--config --verbose --help" -- ${cur}) )
                        return 0
                        ;;
                    list|ls|l)
                        COMPREPLY=( $(compgen -W "--help" -- ${cur}) )
                        return 0
                        ;;
                esac
                ;;
            prompt|p)
                case "${COMP_WORDS[2]}" in
                    list)
                        COMPREPLY=( $(compgen -W "--help" -- ${cur}) )
                        return 0
                        ;;
                    view|delete)
                        COMPREPLY=( $(compgen -W "--help" -- ${cur}) )
                        return 0
                        ;;
                    create)
                        COMPREPLY=( $(compgen -W "--title -t --content -c --description -d --tags --help" -- ${cur}) )
                        return 0
                        ;;
                    update)
                        COMPREPLY=( $(compgen -W "--title -t --content -c --description -d --tags --help" -- ${cur}) )
                        return 0
                        ;;
                    sync)
                        COMPREPLY=( $(compgen -W "--app-type -a --all --help" -- ${cur}) )
                        return 0
                        ;;
                    import-live|show-live)
                        COMPREPLY=( $(compgen -W "--app-type -a --help" -- ${cur}) )
                        return 0
                        ;;
                    import|export)
                        COMPREPLY=( $(compgen -W "--file -f --help" -- ${cur}) )
                        return 0
                        ;;
                    unsync)
                        COMPREPLY=( $(compgen -W "--app-type -a --prompt-id -p --all --help" -- ${cur}) )
                        return 0
                        ;;
                    status)
                        COMPREPLY=( $(compgen -W "--level -l --help" -- ${cur}) )
                        return 0
                        ;;
                esac
                ;;
            skill|s)
                case "${COMP_WORDS[2]}" in
                    list|installed)
                        COMPREPLY=( $(compgen -W "--app-type -a --help" -- ${cur}) )
                        return 0
                        ;;
                    fetch|repos)
                        COMPREPLY=( $(compgen -W "--help" -- ${cur}) )
                        return 0
                        ;;
                    view|delete)
                        COMPREPLY=( $(compgen -W "--help" -- ${cur}) )
                        return 0
                        ;;
                    create)
                        COMPREPLY=( $(compgen -W "--title -t --content -c --description -d --tags --help" -- ${cur}) )
                        return 0
                        ;;
                    update)
                        COMPREPLY=( $(compgen -W "--title -t --content -c --description -d --tags --help" -- ${cur}) )
                        return 0
                        ;;
                    install|uninstall)
                        COMPREPLY=( $(compgen -W "--app-type -a --help" -- ${cur}) )
                        return 0
                        ;;
                    add-repo|remove-repo)
                        COMPREPLY=( $(compgen -W "--owner -o --repo -r --help" -- ${cur}) )
                        return 0
                        ;;
                    import|export)
                        COMPREPLY=( $(compgen -W "--file -f --help" -- ${cur}) )
                        return 0
                        ;;
                    uninstall-all)
                        COMPREPLY=( $(compgen -W "--app-type -a --help" -- ${cur}) )
                        return 0
                        ;;
                esac
                ;;
            upgrade|u|install|i)
                case "${COMP_WORDS[2]}" in
                    all|claude|codex|copilot|gemini|droid|qwen|codebuddy|iflow|qodercli|zed|neovate|crush|cursor-agent|mcp)
                        COMPREPLY=( $(compgen -W "--verbose -v --help" -- ${cur}) )
                        return 0
                        ;;
                esac
                ;;
            uninstall|un)
                case "${COMP_WORDS[2]}" in
                    all|claude|codex|copilot|gemini|droid|qwen|codebuddy|iflow|qodercli|zed|neovate|crush|cursor-agent)
                        COMPREPLY=( $(compgen -W "--force -f --keep-config --help" -- ${cur}) )
                        return 0
                        ;;
                esac
                ;;
            doctor|d)
                COMPREPLY=( $(compgen -W "--verbose -v --help" -- ${cur}) )
                return 0
                ;;
            completion|comp|c)
                case "${COMP_WORDS[2]}" in
                    bash|zsh)
                        COMPREPLY=( $(compgen -W "--help" -- ${cur}) )
                        return 0
                        ;;
                esac
                ;;
        esac
    fi

    # Complete commands
    COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
    return 0
}

complete -F _code_assistant_manager_completions code-assistant-manager
complete -F _code_assistant_manager_completions cam"""

    elif shell == "zsh":
        return """# code-assistant-manager zsh completion

#compdef code-assistant-manager cam

_code_assistant_manager() {
    local -a commands tools mcp_server_commands config_commands prompt_commands skill_commands global_flags
    local context state line

    commands=(
        'launch:Launch AI coding assistants'
        'l:Alias for launch'
        'config:Configuration management commands'
        'cf:Alias for config'
        'mcp:Manage MCP servers'
        'm:Alias for mcp'
        'prompt:Prompt management commands'
        'p:Alias for prompt'
        'skill:Skill management commands'
        's:Alias for skill'
        'upgrade:Upgrade CLI tools'
        'u:Alias for upgrade'
        'install:Install CLI tools'
        'i:Alias for install'
        'uninstall:Uninstall CLI tools'
        'un:Alias for uninstall'
        'doctor:Run diagnostic checks'
        'd:Alias for doctor'
        'version:Show version information'
        'v:Alias for version'
        'completion:Generate shell completion scripts'
        'comp:Alias for completion'
        'c:Alias for completion'
    )

    tools=(
        'claude:Claude Code assistant'
        'codex:OpenAI Codex assistant'
        'copilot:GitHub Copilot assistant'
        'gemini:Google Gemini assistant'
        'droid:Factory.ai Droid assistant'
        'qwen:Qwen assistant'
        'codebuddy:Tencent CodeBuddy assistant'
        'iflow:iFlow assistant'
        'qodercli:Qoder assistant'
        'zed:Zed assistant'
        'neovate:Neovate assistant'
        'crush:Charmland Crush assistant'
        'cursor-agent:Cursor AI assistant'
    )

    mcp_server_commands=(
        'list:List MCP servers'
        'search:Search for MCP servers'
        'show:Show details of an MCP server'
        'add:Add MCP servers to a client'
        'remove:Remove MCP servers from a client'
        'update:Update MCP servers for a client'
    )

    config_commands=(
        'validate:Validate the configuration file'
        'list:List all configuration file locations'
        'ls:Alias for list'
        'l:Alias for list'
    )

    prompt_commands=(
        'list:List all prompts'
        'view:View a specific prompt'
        'create:Create a new prompt'
        'update:Update an existing prompt'
        'delete:Delete a prompt'
        'sync:Sync prompts to editor clients'
        'import-live:Import prompts from live editor'
        'show-live:Show live prompts from editor'
        'import:Import prompts from file'
        'export:Export prompts to file'
        'unsync:Remove synced prompts from editors'
        'status:Show prompt sync status'
    )

    skill_commands=(
        'list:List all skills'
        'fetch:Fetch skills from repositories'
        'view:View a specific skill'
        'create:Create a new skill'
        'update:Update an existing skill'
        'delete:Delete a skill'
        'install:Install a skill to an editor'
        'uninstall:Uninstall a skill from an editor'
        'repos:List skill repositories'
        'add-repo:Add a skill repository'
        'remove-repo:Remove a skill repository'
        'import:Import skills from file'
        'export:Export skills to file'
        'installed:List installed skills'
        'uninstall-all:Uninstall all skills from an editor'
    )

    global_flags=(
        '--help[Show help]'
        '--version[Show version]'
        '--config[Specify config file]:file:_files'
        '--endpoints[Show tool endpoints]:endpoint:->endpoints'
        '--debug[Enable debug logging]'
        '-d[Enable debug logging]'
    )

    _arguments -C \\
        '1: :->command' \\
        '*:: :->args'

    case $state in
        command)
            _describe -t commands 'code-assistant-manager command' commands
            ;;
        args)
            case $words[1] in
                launch|l)
                    if (( CURRENT == 2 )); then
                        _describe -t tools 'AI assistant' tools
                    else
                        _values 'option' '--config[Specify config file]:file:_files' '--help[Show help]'
                    fi
                    ;;
                config|cf)
                    if (( CURRENT == 2 )); then
                        _describe -t config_commands 'config command' config_commands
                    else
                        case $words[2] in
                            validate)
                                _values 'option' '--config[Specify config file]:file:_files' '--verbose[Show verbose output]' '--help[Show help]'
                                ;;
                            *)
                                _values 'option' '--help[Show help]'
                                ;;
                        esac
                    fi
                    ;;
                mcp|m)
                    if (( CURRENT == 2 )); then
                        _values 'mcp command' 'server[Server management commands]'
                    elif (( CURRENT == 3 )) && [[ $words[2] == "server" ]]; then
                        _describe -t mcp_server_commands 'server command' mcp_server_commands
                    else
                        case $words[3] in
                            list)
                                _values 'option' '--client[Specify client]:client:(all claude codex copilot gemini droid qwen codebuddy)' '--interactive[Use interactive mode]' '--help[Show help]'
                                ;;
                            search)
                                _values 'option' '--help[Show help]'
                                ;;
                            show)
                                _values 'option' '--schema[Show raw JSON schema]' '--help[Show help]'
                                ;;
                            add)
                                _values 'option' '--client[Specify client]:client:(all claude codex copilot gemini droid qwen codebuddy)' '--method[Installation method]' '--force[Force installation]' '--interactive[Use interactive mode]' '--scope[Configuration scope]:scope:(user project)' '--help[Show help]'
                                ;;
                            remove|update)
                                _values 'option' '--client[Specify client]:client:(all claude codex copilot gemini droid qwen codebuddy)' '--interactive[Use interactive mode]' '--scope[Configuration scope]:scope:(user project)' '--help[Show help]'
                                ;;
                            *)
                                _values 'option' '--help[Show help]'
                                ;;
                        esac
                    fi
                    ;;
                prompt|p)
                    if (( CURRENT == 2 )); then
                        _describe -t prompt_commands 'prompt command' prompt_commands
                    else
                        case $words[2] in
                            list)
                                _values 'option' '--help[Show help]'
                                ;;
                            view|delete)
                                _values 'option' '--help[Show help]'
                                ;;
                            create|update)
                                _values 'option' '--title[Prompt title]' '--content[Prompt content]' '--description[Prompt description]' '--tags[Prompt tags]' '--help[Show help]'
                                ;;
                            sync)
                                _values 'option' '--app-type[Application type]:app:(claude codex gemini qwen codebuddy)' '--all[Sync all prompts]' '--help[Show help]'
                                ;;
                            import-live|show-live)
                                _values 'option' '--app-type[Application type]:app:(claude codex gemini qwen codebuddy)' '--help[Show help]'
                                ;;
                            import|export)
                                _values 'option' '--file[File path]:file:_files' '--help[Show help]'
                                ;;
                            unsync)
                                _values 'option' '--app-type[Application type]:app:(claude codex gemini qwen codebuddy)' '--prompt-id[Prompt ID]' '--all[Unsync all prompts]' '--help[Show help]'
                                ;;
                            status)
                                _values 'option' '--level[Status level]:level:(summary detailed)' '--help[Show help]'
                                ;;
                            *)
                                _values 'option' '--help[Show help]'
                                ;;
                        esac
                    fi
                    ;;
                skill|s)
                    if (( CURRENT == 2 )); then
                        _describe -t skill_commands 'skill command' skill_commands
                    else
                        case $words[2] in
                            list|installed)
                                _values 'option' '--app-type[Application type]:app:(claude codex gemini qwen codebuddy)' '--help[Show help]'
                                ;;
                            fetch|repos|view|delete)
                                _values 'option' '--help[Show help]'
                                ;;
                            create|update)
                                _values 'option' '--title[Skill title]' '--content[Skill content]' '--description[Skill description]' '--tags[Skill tags]' '--help[Show help]'
                                ;;
                            install|uninstall|uninstall-all)
                                _values 'option' '--app-type[Application type]:app:(claude codex gemini qwen codebuddy)' '--help[Show help]'
                                ;;
                            add-repo|remove-repo)
                                _values 'option' '--owner[Repository owner]' '--repo[Repository name]' '--help[Show help]'
                                ;;
                            import|export)
                                _values 'option' '--file[File path]:file:_files' '--help[Show help]'
                                ;;
                            *)
                                _values 'option' '--help[Show help]'
                                ;;
                        esac
                    fi
                    ;;
                upgrade|u|install|i)
                    if (( CURRENT == 2 )); then
                        local -a upgrade_targets
                        upgrade_targets=('all:Upgrade/install all tools' ${tools[@]} 'mcp:MCP servers')
                        _describe -t targets 'target' upgrade_targets
                    else
                        _values 'option' '--verbose[Show verbose output]' '--help[Show help]'
                    fi
                    ;;
                uninstall|un)
                    if (( CURRENT == 2 )); then
                        local -a uninstall_targets
                        uninstall_targets=('all:Uninstall all tools' ${tools[@]})
                        _describe -t targets 'target' uninstall_targets
                    else
                        _values 'option' '--force[Force uninstall]' '--keep-config[Keep configuration files]' '--help[Show help]'
                    fi
                    ;;
                doctor|d)
                    _values 'option' '--verbose[Show detailed output]' '--help[Show help]'
                    ;;
                version|v)
                    _values 'option' '--help[Show help]'
                    ;;
                completion|comp|c)
                    if (( CURRENT == 2 )); then
                        _values 'shell' 'bash' 'zsh'
                    else
                        _values 'option' '--help[Show help]'
                    fi
                    ;;
                --endpoints)
                    local -a endpoint_targets
                    endpoint_targets=('all' ${${tools[@]%%:*}} 'mcp')
                    _describe -t endpoints 'endpoint target' endpoint_targets
                    ;;
                *)
                    _describe -t global_flags 'global option' global_flags
                    ;;
            esac
            ;;
        endpoints)
            local -a endpoint_targets
            endpoint_targets=('all' ${${tools[@]%%:*}} 'mcp')
            _describe -t endpoints 'endpoint target' endpoint_targets
            ;;
    esac
}

_code_assistant_manager "$@"

# Also register for 'cam' alias
compdef _code_assistant_manager cam"""

    else:
        return f"# Unsupported shell: {shell}"


@app.command("comp", hidden=True)
def completion_alias(shell: str = SHELL_OPTION):
    """Alias for 'completion' command."""
    return completion(shell)
