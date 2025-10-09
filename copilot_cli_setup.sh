#!/usr/bin/env bash
# copilot_cli_setup.sh
# GitHub Copilot CLI setup script
# This file is sourced by ai_tool_setup.sh to provide the copilot function

copilot() {
  # Load environment variables first
  if [ -n "$__AI_TOOLBOXX_DIR" ] && [ -f "$__AI_TOOLBOXX_DIR/load_env.sh" ]; then
    # shellcheck disable=SC1091
    source "$__AI_TOOLBOXX_DIR/load_env.sh" >/dev/null 2>&1 || true
  fi
  
  export NODE_TLS_REJECT_UNAUTHORIZED='0'
  # Step 1: Check if copilot command exists
  if ! command -v copilot &> /dev/null; then
    echo "GitHub Copilot CLI not found."
    read -p "Would you like to install it now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo "Installing @github/copilot..."
      npm install -g @github/copilot
      if [ $? -ne 0 ]; then
        echo "Error: Failed to install GitHub Copilot CLI" >&2
        return 1
      fi
    else
      echo "Copilot CLI not installed. Exiting."
      return 1
    fi
  else
    # Step 2: Ask if user wants to update to latest
    echo "GitHub Copilot CLI is already installed."
    read -p "Would you like to update to the latest version? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo "Upgrading @github/copilot to latest version..."
      npm install -g @github/copilot@latest
      if [ $? -ne 0 ]; then
        echo "Warning: Failed to update GitHub Copilot CLI" >&2
      fi
    fi
  fi

  # Step 3: Check if GITHUB_TOKEN environment variable is set
  if [ -z "$GITHUB_TOKEN" ]; then
    echo "GITHUB_TOKEN not found in environment."
    echo "Error: GITHUB_TOKEN environment variable is not set." >&2
    echo "Please set GITHUB_TOKEN in your environment or add it to .env file." >&2
    return 1
  fi

  # Step 4: Run copilot with all passed arguments
  echo "Starting GitHub Copilot CLI..."
  # If NODE_EXTRA_CA_CERTS points to a file, use it for this invocation only.
  if [ -n "${NODE_EXTRA_CA_CERTS:-}" ] && [ -f "$NODE_EXTRA_CA_CERTS" ]; then
    echo "Using NODE_EXTRA_CA_CERTS=$NODE_EXTRA_CA_CERTS"
    NODE_EXTRA_CA_CERTS="$NODE_EXTRA_CA_CERTS" command copilot --banner "$@"
  else
    command copilot --banner "$@"
  fi
}

# Export the function so it's available in the shell
export -f copilot
