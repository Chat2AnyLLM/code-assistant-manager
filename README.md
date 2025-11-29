# Code Assistant Manager (CAM)

<div align="center">

[![PyPI Version](https://img.shields.io/pypi/v/code-assistant-manager?color=blue)](https://pypi.org/project/code-assistant-manager/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/code-assistant-manager.svg)](https://pypi.org/project/code-assistant-manager/)

**One CLI to Rule Them All.**
<br>
Tired of juggling multiple AI coding assistants? **CAM** is a unified Python CLI to manage configurations, prompts, skills, and plugins for **13 AI assistants** including Claude, Codex, Gemini, Qwen, Copilot, and more from a single, polished terminal interface.

</div>

---

## Why CAM?

In the era of AI-driven development, developers often use multiple powerful assistants like Claude, GitHub Copilot, and Gemini. However, this leads to a fragmented and inefficient workflow:
- **Scattered Configurations:** Each tool has its own setup, API keys, and configuration files.
- **Inconsistent Behavior:** System prompts and custom instructions diverge, leading to different AI behaviors across projects.
- **Wasted Time:** Constantly switching between different CLIs and UIs is a drain on productivity.

CAM solves this by providing a single, consistent interface to manage everything, turning a chaotic toolkit into a cohesive and powerful development partner.

## Key Features

- **Unified Management:** One tool (`cam`) to install, configure, and run all your AI assistants.
- **Centralized Configuration:** Manage all API keys and settings from a single `.env` file.
- **Interactive TUI:** A polished, interactive menu (`cam launch`) for easy navigation and operation.
- **MCP Registry:** Built-in registry with **381 pre-configured MCP servers** ready to install.
- **Extensible Framework:** Standardized architecture for managing:
    - **Agents:** Standalone assistant configurations.
    - **Prompts:** Reusable system prompts synced across assistants.
    - **Skills:** Custom tools and functionalities for your agents.
    - **Plugins:** Marketplace extensions for supported assistants.
- **MCP Support:** First-class support for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), allowing assistants to connect to external data sources and tools.
- **Diagnostics:** A built-in `doctor` command to validate your environment and connectivity.

## Supported AI Assistants

CAM supports **13 AI coding assistants**:

| Assistant | Description |
| :--- | :--- |
| **Claude** | Anthropic Claude Code CLI |
| **Codex** | OpenAI Codex CLI |
| **Gemini** | Google Gemini CLI |
| **Qwen** | Alibaba Qwen Code CLI |
| **Copilot** | GitHub Copilot CLI |
| **CodeBuddy** | Tencent CodeBuddy CLI |
| **Droid** | Factory.ai Droid CLI |
| **iFlow** | iFlow AI CLI |
| **Crush** | Charmland Crush CLI |
| **Cursor** | Cursor Agent CLI |
| **Neovate** | Neovate Code CLI |
| **Qoder** | Qoder CLI |
| **Zed** | Zed Editor |

## Feature Support Matrix

| Feature | Claude | Codex | Gemini | Qwen | CodeBuddy | Droid | Copilot |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Agent** Management | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| **Prompt** Syncing | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| **Skill** Installation | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| **Plugin** Support | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **MCP** Integration | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

> **Note:** MCP integration primarily supports Claude, Codex, Gemini, and Droid.

## Installation

```bash
# Not available via pip yet; run the installer
./install.sh
```

## Quick Start

1.  **Set up API Keys:**
    Create a `.env` file in your home directory (`~`) or your project's root directory.

    ```env
    # ~/.env or ./.env
    ANTHROPIC_API_KEY="sk-ant-..."
    OPENAI_API_KEY="sk-..."
    GEMINI_API_KEY="..."
    QWEN_API_KEY="..."
    ```

2.  **Check Your Setup:**
    Run the `doctor` command to verify that your API keys are correctly configured.

    ```bash
    cam doctor
    ```

3.  **Launch the Interactive Menu:**
    The easiest way to get started is with the interactive TUI.

    ```bash
    cam launch
    ```
    This menu allows you to select models, launch assistants, and manage settings without memorizing commands.

## Command Reference

CAM provides a rich set of subcommands for power users.

| Command | Alias | Description |
| :--- | :--- | :--- |
| `cam launch` | `l` | Launch the interactive TUI or a specific assistant. |
| `cam doctor` | `d` | Run diagnostic checks on your environment and API keys. |
| `cam agent` | `ag` | Manage and configure AI assistants (Agents). |
| `cam prompt` | `p` | Manage and sync system prompts across all assistants. |
| `cam skill` | `s` | Install and manage collections of tools (Skills). |
| `cam plugin` | `pl` | Manage marketplace extensions (Plugins). |
| `cam mcp` | `m` | Manage Model Context Protocol (MCP) servers. |
| `cam upgrade` | `u` | Upgrade CAM and all underlying assistant tools. |
| `cam install` | `i` | Alias for `upgrade`. |
| `cam uninstall` | `un` | Uninstall tools and manage their configuration files. |
| `cam config` | `cf` | Manage CAM's internal configuration files. |
| `cam completion`| `c` | Generate shell completion scripts. |
| `cam version` | `v` | Display the current version of CAM. |

For detailed usage of each command, run `cam [COMMAND] --help`.

## How It Works: Architecture Overview

CAM is built on a modular and extensible architecture.
- **Entry Point:** The CLI is powered by **Typer**, with the main app defined in `code_assistant_manager/cli/app.py`.
- **Manager/Handler Pattern:** A key design pattern is the use of a `Manager` class for each core concept (e.g., `AgentManager`, `SkillManager`). These managers handle the generic logic of fetching, caching, and managing extensions.
- **App-Specific Logic:** For each supported AI assistant (like Claude), there is a corresponding `Handler` class (e.g., `ClaudeAgentHandler`) that contains the specific logic for installing an agent or skill in the correct directory for that application. This decouples the core logic from the specifics of each tool.
- **Extensible by Design:** This architecture makes it straightforward to add support for new assistants or new types of extensions in the future.

## Contributing

Contributions are welcome! Please see our [Developer Guide](docs/DEVELOPER_GUIDE.md) and [Contributing Guidelines](docs/CONTRIBUTING.md) to get started.

### Development Setup

1.  Clone the repository.
2.  Install in editable mode with development dependencies:
    ```bash
    pip install -e ".[dev]"
    ```
3.  Run tests:
    ```bash
    pytest
    ```

## License

This project is licensed under the MIT License.
