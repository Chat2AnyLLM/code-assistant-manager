# code-assistant-manager

<div align="center">

[![PyPI Version](https://img.shields.io/pypi/v/code-assistant-manager?color=blue)](https://pypi.org/project/code-assistant-manager/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/code-assistant-manager.svg)](https://pypi.org/project/code-assistant-manager/)

**Unified Python CLI for AI Coding Assistants**
<br>
Manage Claude, Codex, Gemini, Qwen, and more from a single, polished terminal interface.

[Quick Start](#quick-start) • [Features](#core-features) • [Interactive Mode](#interactive-mode) • [Commands](#subcommands-reference) • [MCP Support](#model-context-protocol-mcp) • [Contributing](#contributing)

</div>

---

## Core Features

*   **Unified CLI:** One tool (`cam`) to manage multiple AI assistants.
*   **Interactive Menus:** Polished TUI for model selection and tool launching.
*   **Prompt Management:** Fetch, sync, and manage system prompts across different assistants.
*   **Skill Management:** Install and manage "skills" (tool definitions) for your AI agents.
*   **MCP Integration:** Full support for the Model Context Protocol (MCP) - manage servers and tools.
*   **Diagnostics:** Built-in `doctor` command to check environment health.
*   **Extensible:** Easy to add new models and providers via LiteLLM.

## Quick Start

### Installation

```bash
pip install code-assistant-manager
```

### Basic Usage

Launch the interactive menu:

```bash
cam launch
```

## Interactive Mode

The easiest way to use CAM is through the interactive launcher:

```bash
cam launch
```
This opens a centered menu where you can:
*   **Select Model:** Choose the active LLM model for your sessions.
*   **Launch Assistant:** Start specific assistants (Claude, Codex, etc.) with the selected configuration.
*   **Manage Settings:** Configure API keys and other preferences.

## Subcommands Reference

CAM offers a rich set of subcommands for advanced management.

### Main Commands

| Command | Alias | Description |
| :--- | :--- | :--- |
| `cam launch` | `l` | Open the interactive menu or launch specific tools directly (e.g., `cam l claude`). |
| `cam doctor` | `d` | Run diagnostic checks on your environment, API keys, and configuration. |
| `cam version` | `v` | Display the current version of CAM. |
| `cam upgrade` | `u` | Update underlying tools (like `claude-engineer`, `aider`, etc.) to their latest versions. |
| `cam install` | `i` | Alias for `upgrade`. Installs or updates tools. |
| `cam uninstall` | `un` | Uninstall CLI tools and optionally backup/remove their configuration files. |
| `cam config` | `cf` | Manage configuration files. Use `cam config list` to see all config paths. |
| `cam completion` | `c` | Generate shell completion scripts for Bash or Zsh. |

### Shell Completion

Enable tab completion for `cam` commands in your shell.

**Bash:**
```bash
# Add to ~/.bashrc
source <(cam completion bash)
```

**Zsh:**
```zsh
# Add to ~/.zshrc
source <(cam completion zsh)
```

### Prompt Management (`cam prompt`)

Manage and sync system prompts across all your AI assistants.

```bash
# List all available prompts
cam prompt list

# Fetch latest prompts from remote repositories
cam prompt fetch

# View details of a specific prompt
cam prompt view <prompt_id>

# Set a specific prompt as the default active prompt
cam prompt set-default <prompt_id>

# Sync the default prompt to all installed assistants
cam prompt sync

# Sync a specific prompt to a specific assistant
cam prompt sync <prompt_id> --app gemini

# Create a new prompt from a file
cam prompt create my-new-prompt --file ./my_prompt.md

# Import the current live prompt from an assistant
cam prompt import-live --app claude --name "My Claude Prompt"
```

### Skill Management (`cam skill`)

Equip your assistants with new capabilities (tools/skills).

```bash
# Discover available skills from configured repositories
cam skill fetch

# List all skills and their installation status
cam skill list

# View details of a skill
cam skill view <skill_id>

# Install a skill to a specific assistant (or 'all')
cam skill install <skill_id> --app all

# Uninstall a skill
cam skill uninstall <skill_id>

# Manage skill repositories
cam skill repos                 # List repositories
cam skill add-repo ...          # Add a new GitHub repo
```

### Model Context Protocol (`cam mcp`)

Manage MCP servers to connect your AI assistants to external data and tools.

```bash
# List registered and installed MCP servers
cam mcp server list

# Search for available MCP servers
cam mcp server search "postgres"

# Show details for a server
cam mcp server show "postgres"

# Install an MCP server
cam mcp server add "postgres" --client all

# Remove an MCP server
cam mcp server remove "postgres"
```

## Supported Assistants

CAM provides management and wrappers for:

*   **Claude** (Anthropic)
*   **Codex** (OpenAI / GitHub Copilot CLI)
*   **Gemini** (Google)
*   **Qwen** (Alibaba Cloud)
*   **LiteLLM** (Access to 100+ models via proxy)

## Configuration

CAM uses a combination of configuration files and environment variables.

*   **Configuration Directory:** `~/.config/code-assistant-manager/` (Linux/Mac)
*   **Environment Variables:** Create a `.env` file in your project root or home directory.

Example `.env`:
```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

## Contributing

### Development Setup

1.  Clone the repository:
    ```bash
    git clone https://github.com/Chat2AnyLLM/code-assistant-manager.git
    cd code-assistant-manager
    ```

2.  Install dependencies:
    ```bash
    pip install -e ".[dev]"
    ```

3.  Run tests:
    ```bash
    pytest tests/
    ```

### Repository Structure

*   `code_assistant_manager/`: Main package source.
    *   `cli.py`: Entry point.
    *   `mcp/`: MCP subsystem.
    *   `prompts.py`: Prompt logic.
    *   `skills.py`: Skill logic.
*   `tests/`: Comprehensive test suite.

See [docs/](docs/) for more detailed developer guides.

## License

This project is licensed under the MIT License.
