# Interactive claude helper
# Usage: source claude_aliases.sh
# This script should be sourced from ai_tool_setup.sh which provides:
# - __AI_TOOLBOXX_DIR: directory path
# - _ai_list_sections, _ai_get: endpoint config helpers
# - Environment variables loaded from .env

claude() {
  # Load environment variables first
  if [ -n "$__AI_TOOLBOXX_DIR" ] && [ -f "$__AI_TOOLBOXX_DIR/load_env.sh" ]; then
    # shellcheck disable=SC1091
    source "$__AI_TOOLBOXX_DIR/load_env.sh" >/dev/null 2>&1 || true
  fi
  
  # Prompt for upgrade
  if command -v claude &> /dev/null; then
    read -p "Would you like to upgrade Claude Code to the latest version? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo "Upgrading @anthropic-ai/claude-code to latest version..."
      npm install -g @anthropic-ai/claude-code@latest
    fi
  fi
  
  # Ensure Anthropic-related environment variables are unset initially
  unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_MODEL ANTHROPIC_SMALL_FAST_MODEL CLAUDE_MODEL

  # Preserve proxy env vars, then unset to avoid unexpected proxying during runtime
  local SAVED_http_proxy="${http_proxy:-}"
  local SAVED_https_proxy="${https_proxy:-}"
  local SAVED_HTTP_PROXY="${HTTP_PROXY:-}"
  local SAVED_HTTPS_PROXY="${HTTPS_PROXY:-}"
  local SAVED_no_proxy="${no_proxy:-}"
  local SAVED_NO_PROXY="${NO_PROXY:-}"
  local SAVED_all_proxy="${all_proxy:-}"
  local SAVED_ALL_PROXY="${ALL_PROXY:-}"
  unset http_proxy HTTP_PROXY https_proxy HTTPS_PROXY no_proxy NO_PROXY all_proxy ALL_PROXY

  # Get list of endpoints from endpoints.conf
  local -a endpoints
  mapfile -t endpoints < <(_ai_list_sections)

  if [ ${#endpoints[@]} -eq 0 ]; then
    echo "Error: No endpoints configured in endpoints.conf" >&2
    return 1
  fi

  # Build endpoint selection menu
  local -a endpoint_choices
  for ep in "${endpoints[@]}"; do
    local ep_url=$(_ai_get "$ep" "endpoint")
    endpoint_choices+=("$ep -> $ep_url")
  done

  # Prompt user to select endpoint
  echo "Choose endpoint for Claude:"
  PS3="Select endpoint (or press Ctrl-C to cancel): "
  select choice in "${endpoint_choices[@]}" "Cancel"; do
    if [[ "$REPLY" =~ ^[0-9]+$ ]]; then
      if [ "$REPLY" -gt ${#endpoint_choices[@]} ]; then
        echo "Cancelled"; return 1
      fi
      local idx=$((REPLY-1))
      local endpoint_name="${endpoints[$idx]}"
      break
    else
      echo "Invalid selection"
    fi
  done

  if [ -z "$endpoint_name" ]; then
    echo "No endpoint selected" >&2
    return 1
  fi

  # Get endpoint configuration
  local endpoint=$(_ai_get "$endpoint_name" "endpoint")
  local api_key=$(_ai_get "$endpoint_name" "api_key")
  local list_cmd=$(_ai_get "$endpoint_name" "list_models_cmd")
  local keep_proxy_config=$(_ai_get "$endpoint_name" "keep_proxy_config")

  # Trim whitespace
  endpoint="$(printf '%s' "$endpoint" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  api_key="$(printf '%s' "$api_key" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  list_cmd="$(printf '%s' "$list_cmd" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  keep_proxy_config="$(printf '%s' "$keep_proxy_config" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

  echo "Using endpoint '$endpoint_name' -> $endpoint"
  export ANTHROPIC_BASE_URL="$endpoint"

  # Determine API key: prefer endpoint-specific env var, then config, then generic
  local actual_api_key="$api_key"
  if [[ "$endpoint_name" == "copilot-api" ]]; then
    actual_api_key="${API_KEY_COPILOT:-${API_KEY:-$api_key}}"
  elif [[ "$endpoint_name" == "litellm" ]]; then
    actual_api_key="${API_KEY_LITELLM:-${API_KEY:-$api_key}}"
  else
    actual_api_key="${API_KEY:-$api_key}"
  fi

  # Fetch models using list_models_cmd if configured
  local -a models=()
  if [ -n "$list_cmd" ]; then
    echo "Fetching model list..."
    echo "Executing command: $list_cmd"
    # Run command from toolbox dir, export endpoint and api_key for command to use
    local out
    if [ -n "$__AI_TOOLBOXX_DIR" ]; then
      # Restore proxy settings for the list command only if keep_proxy_config is true
      if [[ "$keep_proxy_config" == "true" ]]; then
        out=$(cd "$__AI_TOOLBOXX_DIR" && \
          http_proxy="$SAVED_http_proxy" \
          https_proxy="$SAVED_https_proxy" \
          HTTP_PROXY="$SAVED_HTTP_PROXY" \
          HTTPS_PROXY="$SAVED_HTTPS_PROXY" \
          no_proxy="$SAVED_no_proxy" \
          NO_PROXY="$SAVED_NO_PROXY" \
          all_proxy="$SAVED_all_proxy" \
          ALL_PROXY="$SAVED_ALL_PROXY" \
          endpoint="$endpoint" \
          api_key="$actual_api_key" \
          bash -c "$list_cmd" 2>&1 || true)
      else
        # Explicitly unset all proxy environment variables when keep_proxy_config is false or not set
        out=$(cd "$__AI_TOOLBOXX_DIR" && \
          unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY all_proxy ALL_PROXY && \
          endpoint="$endpoint" \
          api_key="$actual_api_key" \
          bash -c "$list_cmd" 2>&1 || true)
      fi
    else
      out=$(endpoint="$endpoint" api_key="$actual_api_key" bash -c "$list_cmd" 2>&1 || true)
    fi

    # Parse output
    if [ -n "$out" ]; then
      if command -v jq >/dev/null 2>&1 && echo "$out" | jq -e . >/dev/null 2>&1; then
        # Try common JSON shapes
        if echo "$out" | jq -e '.data' >/dev/null 2>&1; then
          while IFS= read -r id; do models+=("$id"); done < <(echo "$out" | jq -r '.data[]?.id // empty')
        else
          while IFS= read -r id; do models+=("$id"); done < <(echo "$out" | jq -r '.[]? // empty')
        fi
      else
        # Treat as space-separated or newline-separated list
        while IFS= read -r line; do
          # Split by spaces/tabs and process each token
          for token in $line; do
            id="$(printf '%s' "$token" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
            if [ -n "$id" ] && printf '%s' "$id" | grep -Eq '^[A-Za-z0-9._:/-]+$'; then
              models+=("$id")
            fi
          done
        done <<< "$(printf '%s' "$out")"
      fi
    fi
  fi

  # Fallback models if none retrieved
  if [ ${#models[@]} -eq 0 ]; then
    if [[ "$endpoint" == *":5000"* ]]; then
      models=("gpt-4.1" "gpt-5-mini" "gpt-5" "claude-sonnet-4" "claude-opus-4" "o3-mini" "gpt-4o" "gemini-2.0-flash-001")
    elif [[ "$endpoint" == *":4142"* ]]; then
      models=("model-router" "github_copilot/gpt-5-mini" "gpt-5-mini" "alibaba/glm-4.5" "azure/gpt-5-mini")
    else
      models=("gpt-5-mini" "claude-2" "claude-2.1")
    fi
    echo "Warning: Using fallback model list"
  fi

  # Select primary model
  echo "Choose ANTHROPIC_MODEL (primary model):"
  local num_models=${#models[@]}
  for i in "${!models[@]}"; do
    printf "%3d) %s\n" $((i+1)) "${models[$i]}"
  done
  printf "%3d) Cancel\n" $((num_models+1))

  read -p "Enter selection number: " REPLY
  if [[ "$REPLY" =~ ^[0-9]+$ ]] && [ "$REPLY" -ge 1 ] && [ "$REPLY" -le "$((num_models+1))" ]; then
    if [ "$REPLY" -eq $((num_models+1)) ]; then
      echo "Cancelled"; return 1
    fi
    local ANTHROPIC_MODEL_SELECTED="${models[$((REPLY-1))]}"
    echo "Selected ANTHROPIC_MODEL=$ANTHROPIC_MODEL_SELECTED"
  else
    echo "Invalid selection"; return 1
  fi

  # Select small/fast model
  echo "Choose ANTHROPIC_SMALL_FAST_MODEL (fast/smaller model):"
  for i in "${!models[@]}"; do
    printf "%3d) %s\n" $((i+1)) "${models[$i]}"
  done
  printf "%3d) Cancel\n" $((num_models+1))

  read -p "Enter selection number: " REPLY
  if [[ "$REPLY" =~ ^[0-9]+$ ]] && [ "$REPLY" -ge 1 ] && [ "$REPLY" -le "$((num_models+1))" ]; then
    if [ "$REPLY" -eq $((num_models+1)) ]; then
      echo "Cancelled"; return 1
    fi
    local ANTHROPIC_SMALL_FAST_MODEL_SELECTED="${models[$((REPLY-1))]}"
    echo "Selected ANTHROPIC_SMALL_FAST_MODEL=$ANTHROPIC_SMALL_FAST_MODEL_SELECTED"
  else
    echo "Invalid selection"; return 1
  fi

  # Export environment variables
  export ANTHROPIC_AUTH_TOKEN="$actual_api_key"
  export ANTHROPIC_MODEL="$ANTHROPIC_MODEL_SELECTED"
  export ANTHROPIC_SMALL_FAST_MODEL="$ANTHROPIC_SMALL_FAST_MODEL_SELECTED"
  export CLAUDE_MODEL_2="$ANTHROPIC_SMALL_FAST_MODEL_SELECTED"

  # Prepare runtime variables
  local RUN_BASE_URL="$ANTHROPIC_BASE_URL"
  local RUN_AUTH_TOKEN="$ANTHROPIC_AUTH_TOKEN"
  local RUN_MODEL="$ANTHROPIC_MODEL"
  local RUN_SMALL_FAST_MODEL="$ANTHROPIC_SMALL_FAST_MODEL"
  local RUN_SONNET_MODEL="${ANTHROPIC_DEFAULT_SONNET_MODEL:-$RUN_MODEL}"
  local RUN_HAIKU_MODEL="${ANTHROPIC_DEFAULT_HAIKU_MODEL:-$RUN_MODEL}"

  # Build CLAUDE_MODELS list
  local CLAUDE_MODELS_STR="$RUN_MODEL"
  if [ -n "$CLAUDE_MODEL_2" ] && [ "$CLAUDE_MODEL_2" != "$RUN_MODEL" ]; then
    CLAUDE_MODELS_STR+=",${CLAUDE_MODEL_2}"
  fi
  export CLAUDE_MODELS="$CLAUDE_MODELS_STR"

  # Ensure Node.js accepts self-signed certs
  export NODE_TLS_REJECT_UNAUTHORIZED='0'

  # Display complete command to execute
  echo ""
  echo "Complete command to execute:"
  echo "export ANTHROPIC_BASE_URL=$RUN_BASE_URL ANTHROPIC_AUTH_TOKEN=dummy ANTHROPIC_MODEL=$RUN_MODEL ANTHROPIC_DEFAULT_SONNET_MODEL=$RUN_SONNET_MODEL ANTHROPIC_SMALL_FAST_MODEL=$RUN_SMALL_FAST_MODEL ANTHROPIC_DEFAULT_HAIKU_MODEL=$RUN_HAIKU_MODEL DISABLE_NON_ESSENTIAL_MODEL_CALLS=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 claude"
  echo ""

  # Run claude with environment variables
  ANTHROPIC_BASE_URL="$RUN_BASE_URL" \
    ANTHROPIC_AUTH_TOKEN="$RUN_AUTH_TOKEN" \
    ANTHROPIC_MODEL="$RUN_MODEL" \
    CLAUDE_MODELS="$CLAUDE_MODELS_STR" \
    ANTHROPIC_DEFAULT_SONNET_MODEL="$RUN_SONNET_MODEL" \
    ANTHROPIC_SMALL_FAST_MODEL="$RUN_SMALL_FAST_MODEL" \
    ANTHROPIC_DEFAULT_HAIKU_MODEL="$RUN_HAIKU_MODEL" \
    DISABLE_NON_ESSENTIAL_MODEL_CALLS="1" \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1" \
    NODE_TLS_REJECT_UNAUTHORIZED='0' \
    command claude "$@"
}
