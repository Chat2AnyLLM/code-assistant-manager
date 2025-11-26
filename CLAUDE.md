
Prompt: Imported from Project Claude (2025-11-26 00:58)
Description: Imported from /home/jzhu/code-assistant-manager/CLAUDE.md
Status: disabled
ID: imported-project-claude-1764118687

Content:

# CLAUDE.md — Repository guidelines for AI-assisted edits

This file documents repository-level expectations and instructions intended to guide contributors and AI-assisted editing tools (like Claude Code) when making changes in this project.

- Ask for approval before any git commit and push
- Always run tests before completing all development of new changes
- Always test the CLI usages
- Never commit credentials, keys, .env files
- After any changes, run the folling to reinstall the project:
```
rm -rf dist/*
./install.sh uninstall
./install.sh
cp ~/.config/code-assistant-manager/providers.json.bak ~/.config/code-assistant-manager/providers.json
```
