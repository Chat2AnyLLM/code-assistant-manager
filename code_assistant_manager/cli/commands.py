"""CLI command definitions for Code Assistant Manager."""

import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

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
    typer.echo("code-assistant-manager version 1.0.0")
    raise typer.Exit()


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
    # Get config - try to get from context, otherwise create new
    try:
        config_path = None
        if ctx and ctx.obj and hasattr(ctx.obj, "get"):
            config_path = ctx.obj.get("config_path")
        config = ConfigManager(config_path) if config_path else ConfigManager()
    except Exception:
        # If config initialization fails, create a new one without path
        config = ConfigManager()

    upgradeable_tools = get_registered_tools()

    # Validate target
    if target != "all" and target not in upgradeable_tools:
        typer.echo(f"{Colors.RED}Error: Unknown tool {target!r}{Colors.RESET}")
        return 1

    # Determine which tools to uninstall
    tools_to_uninstall = [target] if target != "all" else list(upgradeable_tools.keys())

    # Filter to only installed tools
    installed_tools = []
    for tool_name in tools_to_uninstall:
        try:
            tool = upgradeable_tools[tool_name](config)
            # Check if tool is installed
            if tool._check_command_available(tool.command_name):
                installed_tools.append(tool_name)
        except Exception:
            pass

    if not installed_tools:
        typer.echo(f"{Colors.YELLOW}No tools found to uninstall{Colors.RESET}")
        return 0

    # Display what will be uninstalled
    typer.echo(f"\n{Colors.BOLD}Tools to uninstall:{Colors.RESET}")
    for tool_name in installed_tools:
        typer.echo(f"  • {tool_name}")

    # Get config directories for backup
    config_dirs = {
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

    # Check which tools have config directories
    tools_with_config = [
        tool for tool in installed_tools if config_dirs.get(tool, Path()).exists()
    ]

    if tools_with_config and not keep_config:
        typer.echo(f"\n{Colors.BOLD}Configuration directories to backup:{Colors.RESET}")
        for tool in tools_with_config:
            config_dir = config_dirs.get(tool)
            typer.echo(f"  • {config_dir}")

    # Confirmation
    if not force:
        if tools_with_config and not keep_config:
            typer.echo(
                f"\n{Colors.YELLOW}⚠️  Configuration files will be backed up{Colors.RESET}"
            )
        else:
            typer.echo(
                f"\n{Colors.YELLOW}⚠️  Configuration files will be deleted{Colors.RESET}"
            )

        proceed = typer.confirm(
            f"Continue with uninstalling {len(installed_tools)} tool(s)?"
        )
        if not proceed:
            typer.echo("Uninstall cancelled")
            return 0

    # Backup configuration files
    backup_dir = None
    if tools_with_config and not keep_config:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = (
            Path.home() / f".config/code-assistant-manager/backup/uninstall_{timestamp}"
        )
        backup_dir.mkdir(parents=True, exist_ok=True)

        typer.echo(f"\n{Colors.BOLD}Backing up configuration files...{Colors.RESET}")
        for tool in tools_with_config:
            config_dir = config_dirs.get(tool)
            try:
                backup_path = backup_dir / tool
                shutil.copytree(config_dir, backup_path)
                typer.echo(
                    f"  {Colors.GREEN}✓{Colors.RESET} {tool}: {config_dir} → {backup_path}"
                )
            except Exception as e:
                typer.echo(
                    f"  {Colors.RED}✗{Colors.RESET} {tool}: Failed to backup - {e}"
                )

    # Uninstall tools using npm
    # Mapping of tool names to npm package names
    npm_package_map = {
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

    typer.echo(f"\n{Colors.BOLD}Uninstalling tools...{Colors.RESET}")
    failed_uninstalls = []

    for tool_name in installed_tools:
        try:
            # Get the actual npm package name
            npm_package = npm_package_map.get(tool_name, tool_name)
            uninstall_cmd = f"npm uninstall -g {npm_package}"

            # Execute uninstall
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

    # Delete configuration directories after successful uninstall
    if not keep_config:
        typer.echo(f"\n{Colors.BOLD}Removing configuration files...{Colors.RESET}")
        for tool in tools_with_config:
            config_dir = config_dirs.get(tool)
            try:
                shutil.rmtree(config_dir)
                typer.echo(f"  {Colors.GREEN}✓{Colors.RESET} {tool}: {config_dir}")
            except Exception as e:
                typer.echo(f"  {Colors.YELLOW}⚠️  {tool}: {e}{Colors.RESET}")

    # Summary
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


@app.command("validate")
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

    # Main commands
    commands="launch l mcp upgrade u install i doctor d completion comp help --help --version --config --endpoints --debug -d"

    # Tool names for launch command
    tools="claude codex copilot gemini droid qwen codebuddy iflow qodercli zed neovate"

    # MCP subcommands
    mcp_commands="server add remove list refresh"

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
        mcp)
            COMPREPLY=( $(compgen -W "${mcp_commands}" -- ${cur}) )
            return 0
            ;;
        upgrade|u)
            COMPREPLY=( $(compgen -W "all ${tools} mcp" -- ${cur}) )
            return 0
            ;;
        install|i)
            COMPREPLY=( $(compgen -W "all ${tools} mcp" -- ${cur}) )
            return 0
            ;;
        doctor|d)
            COMPREPLY=( $(compgen -W "--verbose -v" -- ${cur}) )
            return 0
            ;;
        completion|comp)
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
        --verbose|-v)
            # After --verbose, complete with commands that support it
            COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
            return 0
            ;;
    esac

    # Check for second level completion
    if [ $cword -ge 2 ]; then
        case "${COMP_WORDS[1]}" in
            launch|l)
                case "${COMP_WORDS[2]}" in
                    claude|codex|copilot|gemini|droid|qwen|codebuddy|iflow|qodercli|zed|neovate)
                        # Tool-specific options can be added here
                        COMPREPLY=( $(compgen -W "--help" -- ${cur}) )
                        return 0
                        ;;
                esac
                ;;
            mcp)
                case "${COMP_WORDS[2]}" in
                    server)
                        COMPREPLY=( $(compgen -W "add remove list refresh --client --help" -- ${cur}) )
                        return 0
                        ;;
                    add|remove|list|refresh)
                        COMPREPLY=( $(compgen -W "--client --help" -- ${cur}) )
                        return 0
                        ;;
                    --client)
                        COMPREPLY=( $(compgen -W "${tools}" -- ${cur}) )
                        return 0
                        ;;
                esac
                ;;
            upgrade|u)
                case "${COMP_WORDS[2]}" in
                    all|claude|codex|copilot|gemini|droid|qwen|codebuddy|iflow|qodercli|zed|neovate|mcp)
                        COMPREPLY=( $(compgen -W "--help" -- ${cur}) )
                        return 0
                        ;;
                esac
                ;;
            install|i)
                case "${COMP_WORDS[2]}" in
                    all|claude|codex|copilot|gemini|droid|qwen|codebuddy|iflow|qodercli|zed|neovate|mcp)
                        COMPREPLY=( $(compgen -W "--help" -- ${cur}) )
                        return 0
                        ;;
                esac
                ;;
            doctor|d)
                COMPREPLY=( $(compgen -W "--verbose --help" -- ${cur}) )
                return 0
                ;;
            completion|comp)
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

complete -F _code_assistant_manager_completions code-assistant-manager"""

    elif shell == "zsh":
        return """# code-assistant-manager zsh completion

#compdef code-assistant-manager

_code_assistant_manager() {
    local -a commands tools mcp_commands global_flags
    local context state line

    commands=(
        'launch:Launch AI coding assistants'
        'l:Alias for launch'
        'mcp:Manage MCP servers'
        'upgrade:Upgrade CLI tools'
        'u:Alias for upgrade'
        'install:Install CLI tools'
        'i:Alias for install'
        'doctor:Run diagnostic checks'
        'd:Alias for doctor'
        'completion:Generate shell completion scripts'
        'comp:Alias for completion'
        'help:Show help'
        '--help:Show help'
        '--version:Show version'
        '--config[Specify config file]:file:_files'
        '--endpoints[Show tool endpoints]:endpoint:->endpoints'
        '--debug[Enable debug logging]'
        '-d[Enable debug logging]'
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
    )

    mcp_commands=(
        'server:Server management commands'
        'add:Add MCP servers'
        'remove:Remove MCP servers'
        'list:List MCP servers'
        'refresh:Refresh MCP servers'
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
            case $words[2] in
                launch|l)
                    if (( CURRENT == 3 )); then
                        _describe -t tools 'AI assistant' tools
                    else
                        _values 'option' '--help[Show help]'
                    fi
                    ;;
                mcp)
                    if (( CURRENT == 3 )); then
                        _describe -t mcp_commands 'MCP command' mcp_commands
                    elif (( CURRENT == 4 )); then
                        case $words[3] in
                            server)
                                _values 'server command' \\
                                    'add[Add servers]' \\
                                    'remove[Remove servers]' \\
                                    'list[List servers]' \\
                                    'refresh[Refresh servers]' \\
                                    '--client[Specify client]:client:(${(j: :)${(k)tools}})' \\
                                    '--help[Show help]'
                                ;;
                            add|remove|list|refresh)
                                _values 'option' \\
                                    '--client[Specify client]:client:(${(j: :)${(k)tools}})' \\
                                    '--help[Show help]'
                                ;;
                        esac
                    else
                        _values 'option' '--help[Show help]'
                    fi
                    ;;
                upgrade|u)
                    if (( CURRENT == 3 )); then
                        local upgrade_targets
                        upgrade_targets=(${(k)tools} 'all' 'mcp')
                        _describe -t targets 'upgrade target' upgrade_targets
                    else
                        _values 'option' '--help[Show help]'
                    fi
                    ;;
                install|i)
                    if (( CURRENT == 3 )); then
                        local install_targets
                        install_targets=(${(k)tools} 'all' 'mcp')
                        _describe -t targets 'install target' install_targets
                    else
                        _values 'option' '--help[Show help]'
                    fi
                    ;;
                doctor|d)
                    _values 'option' \\
                        '--verbose[Show detailed output]' \\
                        '--help[Show help]'
                    ;;
                completion|comp)
                    if (( CURRENT == 3 )); then
                        _values 'shell' 'bash' 'zsh'
                    else
                        _values 'option' '--help[Show help]'
                    fi
                    ;;
                --endpoints)
                    local endpoint_targets
                    endpoint_targets=(${(k)tools} 'all' 'mcp')
                    _describe -t endpoints 'endpoint target' endpoint_targets
                    ;;
                *)
                    # Handle global flags and unknown commands
                    _describe -t global_flags 'global option' global_flags
                    ;;
            esac
            ;;
        endpoints)
            local endpoint_targets
            endpoint_targets=(${(k)tools} 'all' 'mcp')
            _describe -t endpoints 'endpoint target' endpoint_targets
            ;;
    esac
}

_code_assistant_manager"""

    else:
        return f"# Unsupported shell: {shell}"


@app.command("comp", hidden=True)
def completion_alias(shell: str = SHELL_OPTION):
    """Alias for 'completion' command."""
    return completion(shell)
