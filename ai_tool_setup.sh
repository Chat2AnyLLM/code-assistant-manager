#!/usr/bin/env bash
# ai_tool_setup.sh
# Source this file from your ~/.bashrc to enable interactive claude/codex wrapper functions
# Usage: source /path/to/ai_tool_setup.sh
# Security: This script sources claude_aliases.sh and codex_aliases.sh which provide the full
# interactive experience. API keys should be stored in endpoints.conf (see endpoints.conf.example).

# Resolve script directory
__AI_TOOLBOXX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
CONFIG_FILE="$__AI_TOOLBOXX_DIR/endpoints.conf"

# Export the toolbox directory so alias scripts can use it
export __AI_TOOLBOXX_DIR

# Load environment variables from .env via load_env.sh if available
if [ -f "$__AI_TOOLBOXX_DIR/load_env.sh" ]; then
  # shellcheck disable=SC1091
  . "$__AI_TOOLBOXX_DIR/load_env.sh" >/dev/null 2>&1 || true
fi

# Helper: list sections in endpoints.conf
_ai_list_sections() {
  [ -f "$CONFIG_FILE" ] || return 1
  awk '/^\s*\[/{gsub(/\[|\]/,"",$0); print $0}' "$CONFIG_FILE"
}

# Helper: get a key value for a section
_ai_get_value() {
  local section="$1" key="$2"
  [ -f "$CONFIG_FILE" ] || return 1
  awk -v sec="$section" -v key="$key" '
    BEGIN{insec=0}
    /^\s*\[/{s=$0; gsub(/\[|\]/,"",s); insec=(s==sec)}
    insec && $0 ~ "^[ \t]*"key"[ \t]*=" { val=substr($0, index($0, "=")+1); gsub(/^[ \t]+|[ \t]+$/,"",val); print val; exit }
  ' "$CONFIG_FILE"
}

# If the simple awk above fails on some shells, provide a fallback parser
_ai_get_value_fallback() {
  local section="$1" key="$2" line insec=0 val
  while IFS= read -r line; do
    # trim
    line="${line%%\#*}"
    [[ -z "$line" ]] && continue
    if [[ "$line" =~ ^\s*\[(.+)\]\s*$ ]]; then
      [[ "${BASH_REMATCH[1]}" == "$section" ]] && insec=1 || insec=0
      continue
    fi
    if [[ $insec -eq 1 && "$line" =~ ^\s*([^=]+)=\s*(.*)\s*$ ]]; then
      k="${BASH_REMATCH[1]// /}"
      v="${BASH_REMATCH[2]}"
      if [[ "$k" == "$key" ]]; then
        printf "%s" "$v"
        return 0
      fi
    fi
  done < "$CONFIG_FILE"
  return 1
}

# Choose parser based on availability
_ai_get() {
  local val
  val=$(_ai_get_value "$@" 2>/dev/null) || val=$(_ai_get_value_fallback "$@" 2>/dev/null)
  printf "%s" "$val"
}

# Export helper functions so alias scripts can use them
export -f _ai_list_sections
export -f _ai_get_value
export -f _ai_get_value_fallback
export -f _ai_get

# Source the claude interactive helper
if [ -f "$__AI_TOOLBOXX_DIR/claude_aliases.sh" ]; then
  # shellcheck disable=SC1091
  source "$__AI_TOOLBOXX_DIR/claude_aliases.sh"
else
  echo "Warning: claude_aliases.sh not found at $__AI_TOOLBOXX_DIR/claude_aliases.sh" >&2
fi

# Source the codex interactive helper
if [ -f "$__AI_TOOLBOXX_DIR/codex_aliases.sh" ]; then
  # shellcheck disable=SC1091
  source "$__AI_TOOLBOXX_DIR/codex_aliases.sh"
else
  echo "Warning: codex_aliases.sh not found at $__AI_TOOLBOXX_DIR/codex_aliases.sh" >&2
fi

# Source the copilot CLI setup helper
if [ -f "$__AI_TOOLBOXX_DIR/copilot_cli_setup.sh" ]; then
  # shellcheck disable=SC1091
  source "$__AI_TOOLBOXX_DIR/copilot_cli_setup.sh"
else
  echo "Warning: copilot_cli_setup.sh not found at $__AI_TOOLBOXX_DIR/copilot_cli_setup.sh" >&2
fi

# Source the gemini CLI setup helper
if [ -f "$__AI_TOOLBOXX_DIR/gemini_cli_setup.sh" ]; then
  # shellcheck disable=SC1091
  source "$__AI_TOOLBOXX_DIR/gemini_cli_setup.sh"
else
  echo "Warning: gemini_cli_setup.sh not found at $__AI_TOOLBOXX_DIR/gemini_cli_setup.sh" >&2
fi

# Source the droid CLI setup helper
if [ -f "$__AI_TOOLBOXX_DIR/droid_cli_setup.sh" ]; then
  # shellcheck disable=SC1091
  source "$__AI_TOOLBOXX_DIR/droid_cli_setup.sh"
else
  echo "Warning: droid_cli_setup.sh not found at $__AI_TOOLBOXX_DIR/droid_cli_setup.sh" >&2
fi

# If endpoints.conf doesn't exist, create an example copy next to this script
if [ ! -f "$CONFIG_FILE" ] && [ -f "$__AI_TOOLBOXX_DIR/endpoints.conf.example" ]; then
  cp "$__AI_TOOLBOXX_DIR/endpoints.conf.example" "$CONFIG_FILE"
  echo "Created example config at $CONFIG_FILE. Edit it and replace placeholder api_key values."
fi

# Prevent direct execution (only allow sourcing)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Error: This script must be sourced, not executed." >&2
  echo "Usage: source ${BASH_SOURCE[0]}" >&2
  exit 1
fi

# Usage instructions
cat <<USAGE

✓ AI Toolboxx loaded successfully!

To enable claude/codex wrappers automatically, add this to your ~/.bashrc:

  source "$__AI_TOOLBOXX_DIR/ai_tool_setup.sh"

Available commands:
  - claude   : Interactive Claude CLI wrapper with model selection
  - codex    : Interactive Codex CLI wrapper with model selection
  - copilot  : Setup and start GitHub Copilot CLI
  - gemini   : Setup and start Google Gemini CLI
  - droid    : Setup and start Factory.ai Droid CLI

Configuration:
  - Edit $CONFIG_FILE to configure endpoints and API keys
  - Use load_env.sh to set per-endpoint API key variables (API_KEY_LITELLM, API_KEY_COPILOT, etc.)

Security note:
  - API keys should be stored in endpoints.conf or environment variables
  - Do not commit secrets to version control

USAGE
