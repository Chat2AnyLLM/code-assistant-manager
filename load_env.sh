#!/usr/bin/env bash
# Small helper to load .env from repo root (if present) into the environment for list commands.
# Usage: . ./load_env.sh

# Save current shell options to restore them later
_load_env_old_opts=$(set +o)

# Set strict mode for this script only
set -euo pipefail

# Search for .env in common locations and source the first one found.
for envf in "$PWD/.env" "${__AI_TOOLBOXX_DIR:+$__AI_TOOLBOXX_DIR/.env}" "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/.env" "$HOME/.config/ai-toolboxx/.env"; do
  if [ -f "$envf" ]; then
    # shellcheck disable=SC1091
    set -a
    # shellcheck disable=SC1090
    . "$envf"
    set +a
    break
  fi
done

# Restore original shell options
eval "$_load_env_old_opts"
unset _load_env_old_opts

