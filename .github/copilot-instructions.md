# CLAUDE.md — Repository guidelines for AI-assisted edits

This file documents repository-level expectations and instructions intended to guide contributors and AI-assisted editing tools (like Claude Code) when making changes in this project.

- Ask for approval before any git commit and push
- Always run tests before completing all development of new changes
- Always test the CLI usages
- After any changes, run the folling to reinstall the project:
```
rm -rf dist/*
./install.sh uninstall
./install.sh
cp ~/.config/code-assistant-manager/providers.json.bak ~/.config/code-assistant-manager/providers.json
```
