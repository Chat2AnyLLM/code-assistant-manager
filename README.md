# code-assistant-manager

Unified Python CLI for AI coding assistants — a focused, concise guide.

Overview

code-assistant-manager provides a single CLI to access multiple AI coding assistants (Claude, Codex, Qwen, GitHub Copilot, and more). It offers interactive model selection, configurable endpoints, secure environment management, MCP server integration, and a polished terminal UI.

Deep analysis of this repository (developer-focused)

This section is intended to give contributors and maintainers a clear, practical understanding of the repository layout, architecture, important files, runtime behavior, and recommended workflows for development and release.

Repository layout

- code_assistant_manager/ — main Python package implementing the CLI, tools registry, MCP support, menus and utilities.
  - cli.py: Main Typer-based CLI and legacy compatibility layer. Key commands: launch, upgrade/install, uninstall, doctor, completion. (file: code_assistant_manager/cli.py)
  - __init__.py: Package metadata and __version__.
  - tools/: Tool implementations and CLITool interface.
  - mcp/: MCP subsystem with manager, CLI, server registry JSONs. (files: code_assistant_manager/mcp/manager.py, server_commands.py, cli.py, registry/servers/*.json)
  - menu/: Terminal UI components and centered menus used to select tools interactively.
  - config.py, env_loader.py: Configuration parsing and .env helper utilities.
  - list_models_cmd supports three forms now: (1) a python module invocation (e.g. "python -m code_assistant_manager.litellm_models"), (2) legacy shell commands (e.g. "curl ... | jq -r '.data.[].id'"), and (3) a plain space-separated model list (e.g. "qwen3-max qwen3-coder-plus").

- tests/: Pytest test suite (unit, integration, interactive). Test configuration in pytest.ini. Run with: python -m pytest tests/

- docs/: Supporting documentation (developer guides, API docs, testing notes).

- tools.yaml: Tool installation and environment setup metadata used by the upgrade/install flows.

Key files and responsibilities

- pyproject.toml and setup.py: Packaging metadata and entry points for the CLIs (code-assistant-manager, cam). Prefer pyproject as source-of-truth for modern builds, setup.py exists for compatibility.

- README.md (this file): User-facing quick-start and developer deep analysis (this section).

- docs/INSTALL.md: Detailed installation options and scripts.

- docs/CLAUDE.md: Repository guidelines for AI-assisted edits. Important: follow these when creating AI-generated changes.

- pytest.ini: Configures test discovery and pytest run options.

Entrypoints and CLI flow

- Console scripts: `code-assistant-manager` and `cam` map to code_assistant_manager.cli:main (pyproject.toml and setup.py).

- The CLI is implemented with Typer (click-based). Subcommands include `launch` (interactive menu or per-tool commands), `version` (show version information), `mcp` (MCP server management), `upgrade`/`install` (tool installers), `doctor` (diagnostics), `completion` (generate shell completion script).

- `cli.py` also contains compatibility code that allows `code-assistant-manager <tool>` direct invocation and a legacy `main()` wrapper for backward compatibility.

Development workflow and testing

- Run tests locally with `python -m pytest tests/`. The repository uses pytest.ini to set testpaths and addopts.

- Recommended local development flow:
  1. Create a feature branch: feature/<desc> or fix/<desc>.
  2. Run linters and formatters (project uses Black/Flake8? not enforced in repo snapshot) and the full test suite.
  3. Make focused commits and open a PR with tests and a clear description. Include `Co-Authored-By: Claude <noreply@anthropic.com>` when AI-assisted edits were used (see docs/CLAUDE.md).

- Tests are fairly extensive and broken into unit, integration, and interactive categories under tests/.

MCP subsystem

- MCP (Model Connector Protocol) manager and registry lives under code_assistant_manager/mcp/. The registry contains server JSON definitions for many MCP servers (registry/servers/*.json).

- MCP CLI integrates as a Typer app (mcp/cli.py). Use `code-assistant-manager mcp server list` and related commands to manage MCP servers.

Tools & installer logic

- tools.yaml contains installer commands for each tool (npm installs, curl downloads, etc.). The upgrade/install flow uses this registry to perform global `npm install -g` operations and detect versions.

- Each tool implements a CLITool-like interface exposing: command_name, _check_command_available(), _get_version(), and _perform_upgrade(). The CLI orchestrates parallel upgrades using ThreadPoolExecutor.

Security & configuration

- Sensitive API keys should be provided via environment variables (recommended) or a .env file loaded by env_loader.py. The doctor command performs basic security checks (checks for common key patterns and file permissions).

- Recommended: Keep .env out of version control; use OS keyrings or CI secrets for production environments.

Repository strengths

- Comprehensive CLI UX: Typer-based app with interactive menus, shell completion, and clear commands.

- MCP integration: Extensible server registry and CLI to add/remove/list/refresh servers.

- Solid diagnostics: `doctor` performs many helpful checks (env, config permissions, installed tools, endpoints, cache, basic security scanning).

- Tests: Structured test suite ready for CI.

Areas for improvement and recommendations

1. Add CI configuration (GitHub Actions or equivalent). The repo lacks .github/workflows/. Provide jobs for linting, tests, type-checking (mypy/pydantic checks), and security scans.

2. Add pre-commit hooks with formatting/linting (Black, isort, Flake8) and run them in CI.

3. Consider replacing global `npm install -g` patterns with safer per-user or containerized installers (or document the implications clearly).

4. Add a Dockerfile and/or GitHub Codespaces devcontainer for easy contributor setup.

5. Hardening: Add secrets scanning to CI and improve the heuristic used in the doctor security check (e.g., integrate detect-secrets or truffleHog).

6. Documentation: docs/CONTRIBUTING.md and CODE_OF_CONDUCT.md to standardize PR process and contributor expectations (though docs/CLAUDE.md provides AI-specific guidance).

7. Release automation: Add a release workflow for pushing to PyPI and draft GitHub releases; ensure version bumping is automated (bump2version or similar).

Recommended TODOs for the project (short term)

- Add GitHub Actions workflow with jobs: lint, test, build, publish-check (no publish), and security-scan.
- Add a Makefile with common commands: make test, make lint, make format, make release.
- Add CONTRIBUTING.md summarizing CLAUDE.md for human contributors and CI expectations.
- Add a Dockerfile for a reproducible developer environment.

How to review changes made by AI

- Per CLAUDE.md: Treat AI edits as drafts. Review line-by-line, run tests, and annotate generated code with a short AI-assisted comment.

Appendix: Quick file references

- Main CLI: code_assistant_manager/cli.py:1
- Package version: code_assistant_manager/__init__.py:17
- MCP manager: code_assistant_manager/mcp/manager.py
- Tools registry: code_assistant_manager/tools.yaml
- Tests: tests/ (run with pytest)
- Packaging: pyproject.toml, setup.py

Last updated: 2025-10-28
