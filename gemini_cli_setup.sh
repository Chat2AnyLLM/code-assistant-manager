#!/usr/bin/env bash
# gemini_cli_setup.sh
# Google Gemini CLI setup script
# This file is sourced by ai_tool_setup.sh to provide the gemini function

gemini() {
  # Load environment variables first
  if [ -n "$__AI_TOOLBOXX_DIR" ] && [ -f "$__AI_TOOLBOXX_DIR/load_env.sh" ]; then
    # shellcheck disable=SC1091
    source "$__AI_TOOLBOXX_DIR/load_env.sh" >/dev/null 2>&1 || true
  fi
  
  # Prompt for upgrade
  if command -v gemini &> /dev/null; then
    read -p "Would you like to upgrade Google Gemini CLI to the latest version? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo "Upgrading @google/gemini-cli to latest version..."
      npm install -g @google/gemini-cli@latest
    fi
  fi
  
  local settings_file="$HOME/.gemini/settings.json"
  local use_gemini_api_key=false
  local use_vertex_ai=false
  
  # Step 1: Detect and remove security/auth keys from settings.json
  if [ -f "$settings_file" ]; then
    echo "Checking Gemini settings file..."
    
    # Check if security.auth exists in the file
    if grep -q '"security"' "$settings_file" 2>/dev/null; then
      echo "Removing security and auth keys from $settings_file..."
      
      # Use jq if available, otherwise use sed/awk
      if command -v jq &> /dev/null; then
        # Remove security key from JSON
        jq 'del(.security)' "$settings_file" > "${settings_file}.tmp" && mv "${settings_file}.tmp" "$settings_file"
        echo "Security configuration removed from settings file."
      else
        echo "Warning: jq not found. Manual removal may be needed." >&2
        echo "Please install jq for automatic settings cleanup: sudo apt install jq" >&2
      fi
    fi
  fi
  
  # Step 2: Detect GEMINI_API_KEY for Gemini API key auth
  if [ -n "$GEMINI_API_KEY" ]; then
    use_gemini_api_key=true
    echo "Detected GEMINI_API_KEY - using Gemini API key authentication."
  fi
  
  # Step 3: Detect Vertex AI environment variables
  if [ -z "$use_gemini_api_key" ] || [ "$use_gemini_api_key" = false ]; then
    if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ] && \
       [ -n "$GOOGLE_CLOUD_PROJECT" ] && \
       [ -n "$GOOGLE_CLOUD_LOCATION" ] && \
       [ -n "$GOOGLE_GENAI_USE_VERTEXAI" ]; then
      use_vertex_ai=true
      echo "Detected Vertex AI environment variables - using Vertex AI authentication."
    fi
  fi
  
  # Step 4: If neither is set, let user choose in CLI
  if [ "$use_gemini_api_key" = false ] && [ "$use_vertex_ai" = false ]; then
    echo "No authentication credentials detected."
    echo "You can configure authentication in the Gemini CLI or set environment variables:"
    echo "  - For Gemini API: set GEMINI_API_KEY"
    echo "  - For Vertex AI: set GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_GENAI_USE_VERTEXAI"
  fi
  
  # Step 5: Run gemini with all passed arguments
  echo "Starting Google Gemini CLI..."
  if ! command -v gemini &> /dev/null; then
    echo "Error: gemini command not found. Please install the Gemini CLI first." >&2
    return 1
  fi
  
  command gemini "$@"
}

# Export the function so it's available in the shell
export -f gemini
