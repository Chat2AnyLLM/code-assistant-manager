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
- **Centralized Configuration:** Manage all API keys and endpoint settings from a single `providers.json` file with environment variables in `.env`.
- **Interactive TUI:** A polished, interactive menu (`cam launch`) for easy navigation and operation with arrow-key navigation.
- **MCP Registry:** Built-in registry with **381 pre-configured MCP servers** ready to install across all supported tools.
- **Extensible Framework:** Standardized architecture for managing:
    - **Agents:** Standalone assistant configurations (markdown-based with YAML front matter).
    - **Prompts:** Reusable system prompts synced across assistants at user or project scope.
    - **Skills:** Custom tools and functionalities for your agents (directory-based with SKILL.md).
    - **Plugins:** Marketplace extensions for supported assistants (GitHub repos or local paths).
- **MCP Support:** First-class support for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), allowing assistants to connect to external data sources and tools.
- **Parallel Upgrades:** Concurrent tool upgrades with npm version checking and progress visualization.
- **Diagnostics:** A comprehensive `doctor` command to validate your environment, API keys, tool installations, and cache status.

## Supported AI Assistants

CAM supports **13 AI coding assistants**:

| Assistant | Command | Description | Install Method |
| :--- | :--- | :--- | :--- |
| **Claude** | `claude` | Anthropic Claude Code CLI | Shell script |
| **Codex** | `codex` | OpenAI Codex CLI | npm |
| **Gemini** | `gemini` | Google Gemini CLI | npm |
| **Qwen** | `qwen` | Alibaba Qwen Code CLI | npm |
| **Copilot** | `copilot` | GitHub Copilot CLI | npm |
| **CodeBuddy** | `codebuddy` | Tencent CodeBuddy CLI | npm |
| **Droid** | `droid` | Factory.ai Droid CLI | Shell script |
| **iFlow** | `iflow` | iFlow AI CLI | npm |
| **Crush** | `crush` | Charmland Crush CLI | npm |
| **Cursor** | `cursor-agent` | Cursor Agent CLI | Shell script |
| **Neovate** | `neovate` | Neovate Code CLI | npm |
| **Qoder** | `qodercli` | Qoder CLI | npm |
| **Zed** | `zed` | Zed Editor | Shell script |

## Feature Support Matrix

| Feature | Claude | Codex | Gemini | Qwen | CodeBuddy | Droid | Copilot |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Agent** Management | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Prompt** Syncing | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| **Skill** Installation | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| **Plugin** Support | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **MCP** Integration | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**MCP Integration** is supported across all 13 assistants including: Claude, Codex, Gemini, Qwen, Copilot, CodeBuddy, Droid, iFlow, Zed, Qoder, Neovate, Crush, and Cursor.

> **Note:** Some tools (Zed, Qoder, Neovate) are disabled by default in the menu as they are still under development. You can enable them in `tools.yaml` by setting `enabled: true`.

## Installation

```bash
# Install via pip (Python 3.9+)
pip install code-assistant-manager

# Or install from source
git clone https://github.com/Chat2AnyLLM/code-assistant-manager.git
cd code-assistant-manager
pip install -e ".[dev]"
```

## Quick Start

### 1. Set up Configuration

Create a `providers.json` file in `~/.config/code-assistant-manager/` or your project root:

```json
{
  "common": {
    "http_proxy": "http://proxy.example.com:8080/",
    "https_proxy": "http://proxy.example.com:8080/",
    "cache_ttl_seconds": 86400
  },
  "endpoints": {
    "my-litellm": {
      "endpoint": "https://api.example.com:4142",
      "api_key_env": "API_KEY_LITELLM",
      "list_models_cmd": "python -m code_assistant_manager.litellm_models",
      "supported_client": "claude,codex,qwen,copilot",
      "description": "My LiteLLM Proxy"
    }
  }
}
```

### 2. Set up API Keys

Create a `.env` file in your home directory or project root:

```env
API_KEY_LITELLM="your-api-key-here"
GITHUB_TOKEN="your-github-token"
GEMINI_API_KEY="your-gemini-key"
```

### 3. Check Your Setup

```bash
cam doctor
```

This runs comprehensive diagnostics including:
- Installation verification
- Configuration file validation
- Environment variable checks (Gemini/Vertex AI, GitHub Copilot)
- Tool installation status
- Endpoint connectivity
- Cache status and security audit

### 4. Launch an Assistant

```bash
# Interactive menu to select assistant and model
cam launch

# Or launch a specific assistant directly
cam launch claude
cam launch codex
cam launch gemini
```

## Command Reference

| Command | Alias | Description |
| :--- | :--- | :--- |
| `cam launch [TOOL]` | `l` | Launch interactive TUI or a specific assistant |
| `cam doctor` | `d` | Run diagnostic checks on environment and API keys |
| `cam agent` | `ag` | Manage agent configurations (list, install, fetch from repos) |
| `cam prompt` | `p` | Manage and sync system prompts across assistants |
| `cam skill` | `s` | Install and manage skill collections |
| `cam plugin` | `pl` | Manage marketplace extensions (plugins) |
| `cam mcp` | `m` | Manage MCP servers (add, remove, list, install) |
| `cam upgrade [TARGET]` | `u` | Upgrade tools (default: all) with parallel execution |
| `cam install [TARGET]` | `i` | Alias for upgrade |
| `cam uninstall [TARGET]` | `un` | Uninstall tools and backup configurations |
| `cam config` | `cf` | Manage CAM's internal configuration files |
| `cam completion` | `c` | Generate shell completion scripts (bash, zsh, fish) |
| `cam version` | `v` | Display current version |

### MCP Subcommands

```bash
cam mcp add <tool> <server>      # Add an MCP server to a tool
cam mcp remove <tool> <server>   # Remove an MCP server
cam mcp list <tool>              # List configured MCP servers
cam mcp install --all            # Install MCP servers for all tools
cam mcp registry search <query>  # Search the MCP server registry
```

### Agent Subcommands

```bash
cam agent list                   # List available agents
cam agent install <agent>        # Install an agent
cam agent fetch                  # Fetch agents from configured repos
cam agent repos                  # Manage agent repositories
```

### Prompt Subcommands

```bash
cam prompt list                  # List saved prompts
cam prompt create                # Create a new prompt
cam prompt sync <id> <tool>      # Sync a prompt to a tool
cam prompt set-default <id>      # Set default prompt for sync-all
cam prompt sync-all              # Sync default prompt to all tools
```

### Skill Subcommands

```bash
cam skill list                   # List available skills
cam skill install <skill>        # Install a skill
cam skill fetch                  # Fetch skills from configured repos
```

## Architecture Overview

CAM implements industry-standard design patterns for maintainability and extensibility:

### Core Design Patterns

- **Value Objects:** Immutable domain primitives with validation (`APIKey`, `EndpointURL`, `ModelID`)
- **Factory Pattern:** Centralized tool creation via `ToolFactory` with registration decorators
- **Strategy Pattern:** Pluggable installers for different package managers (npm, pip, shell)
- **Repository Pattern:** Data access abstraction for configuration and caching
- **Service Layer:** Business logic separation (`ConfigurationService`, `ModelService`)
- **Chain of Responsibility:** Validation pipeline for configuration

### Module Structure

```
code_assistant_manager/
├── cli/                    # Typer-based CLI commands
│   ├── app.py              # Main app entry point
│   ├── commands.py         # Core commands (doctor, upgrade, etc.)
│   ├── agents_commands.py  # Agent management
│   ├── prompts_commands.py # Prompt management
│   ├── skills_commands.py  # Skill management
│   └── plugin_commands.py  # Plugin management
├── tools/                  # Tool implementations (13 assistants)
│   ├── base.py             # CLITool base class
│   ├── claude.py, codex.py, gemini.py, ...
│   └── registry.py         # Tool registry from tools.yaml
├── agents/                 # Agent management
│   ├── manager.py          # AgentManager orchestration
│   └── base.py, claude.py, ... # App-specific handlers
├── prompts/                # Prompt management
│   ├── manager.py          # PromptManager with sync capabilities
│   └── claude.py, codex.py, copilot.py, ...
├── skills/                 # Skill management
│   ├── manager.py          # SkillManager orchestration
│   └── base.py, claude.py, ...
├── plugins/                # Plugin management
│   ├── manager.py          # PluginManager with marketplace support
│   └── claude.py, codebuddy.py
├── mcp/                    # Model Context Protocol
│   ├── manager.py          # MCPManager for all tools
│   ├── clients.py          # Tool-specific MCP clients
│   └── registry/servers/   # 381 pre-configured MCP servers
├── menu/                   # Interactive TUI components
│   ├── base.py             # Menu base classes with arrow navigation
│   └── menus.py            # Centered menus, model selectors
├── upgrades/               # Tool installation/upgrade system
│   ├── installer_factory.py # Strategy selection
│   └── npm_upgrade.py, pip_upgrade.py, shell_upgrade.py
├── config.py               # ConfigManager with validation
├── domain_models.py        # Rich domain objects
├── value_objects.py        # Validated primitives
├── factory.py              # ToolFactory and ServiceContainer
├── services.py             # Business logic services
└── tools.yaml              # Tool definitions and install commands
```

### Configuration Files

CAM stores data in `~/.config/code-assistant-manager/`:
- `providers.json` - Endpoint configurations
- `agents.json` - Agent metadata cache
- `skills.json` - Skill metadata cache
- `prompts.json` - Saved prompts with active mappings
- `plugins.json` - Plugin registry
- `agent_repos.json`, `skill_repos.json`, `plugin_repos.json` - Repository sources

### Adding a New Assistant

1. Create a tool class in `code_assistant_manager/tools/` extending `CLITool`
2. Define `command_name`, `tool_key`, and `install_description`
3. Add entry to `tools.yaml` with `install_cmd` and environment configuration
4. Create handlers in `agents/`, `skills/`, `prompts/`, `mcp/` as needed
5. The tool is auto-discovered via `CLITool.__subclasses__()`

## Contributing

Contributions are welcome! Please see our [Developer Guide](docs/DEVELOPER_GUIDE.md) and [Contributing Guidelines](docs/CONTRIBUTING.md) to get started.

### Development Setup

```bash
# Clone and install
git clone https://github.com/Chat2AnyLLM/code-assistant-manager.git
cd code-assistant-manager
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=code_assistant_manager

# Code formatting
black code_assistant_manager tests
isort code_assistant_manager tests

# Linting
flake8 code_assistant_manager
mypy code_assistant_manager
```

### Running Specific Tests

```bash
pytest tests/test_cli.py           # CLI tests
pytest tests/test_config.py        # Configuration tests
pytest tests/unit/                  # Unit tests
pytest tests/integration/           # Integration tests
```

## License

This project is licensed under the MIT License.
