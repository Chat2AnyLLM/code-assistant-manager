#!/usr/bin/env bash
# droid_cli_setup.sh
# Factory.ai Droid CLI setup script
# This file is sourced by ai_tool_setup.sh to provide the droid function

droid() {
  # Load environment variables first
  if [ -n "$__AI_TOOLBOXX_DIR" ] && [ -f "$__AI_TOOLBOXX_DIR/load_env.sh" ]; then
    # shellcheck disable=SC1091
    source "$__AI_TOOLBOXX_DIR/load_env.sh" >/dev/null 2>&1 || true
  fi
  
  # Step 1: Check if droid command exists
  if ! command -v droid &> /dev/null; then
    echo "Factory.ai Droid CLI not found."
    read -p "Would you like to install it now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo "Installing droid CLI from factory.ai..."
      curl -fsSL https://app.factory.ai/cli | sh
      if [ $? -ne 0 ]; then
        echo "Error: Failed to install Droid CLI" >&2
        return 1
      fi
    else
      echo "Droid CLI not installed. Exiting."
      return 1
    fi
  else
    # Step 2: Ask if user wants to update to latest
    echo "Factory.ai Droid CLI is already installed."
    read -p "Would you like to update to the latest version? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo "Upgrading droid CLI to latest version..."
      curl -fsSL https://app.factory.ai/cli | sh
      if [ $? -ne 0 ]; then
        echo "Warning: Failed to update Droid CLI" >&2
      fi
    fi
  fi

  # Step 3: Let user select one model from each endpoint
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

  echo "Configuring Droid with models from all endpoints..."
  echo ""

  # Arrays to store selected model information
  local -a selected_models
  local -A model_to_endpoint
  local -A model_to_base_url
  local -A model_to_api_key
  
  # For each endpoint, fetch models and let user select one
  for endpoint_name in "${endpoints[@]}"; do
    local endpoint=$(_ai_get "$endpoint_name" "endpoint")
    local api_key=$(_ai_get "$endpoint_name" "api_key")
    local api_key_env=$(_ai_get "$endpoint_name" "api_key_env")
    local list_cmd=$(_ai_get "$endpoint_name" "list_models_cmd")
    local keep_proxy_config=$(_ai_get "$endpoint_name" "keep_proxy_config")

    # Trim whitespace
    endpoint="$(printf '%s' "$endpoint" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    api_key="$(printf '%s' "$api_key" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    list_cmd="$(printf '%s' "$list_cmd" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    keep_proxy_config="$(printf '%s' "$keep_proxy_config" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

    echo "Processing endpoint: $endpoint_name -> $endpoint"

    # Skip if no list command
    if [ -z "$list_cmd" ]; then
      echo "Warning: No list_models_cmd configured for $endpoint_name, skipping"
      echo ""
      continue
    fi

    # Determine API key: prefer endpoint-specific env var, then config, then generic
    local actual_api_key="$api_key"
    if [ -n "$api_key_env" ]; then
      actual_api_key="${!api_key_env:-$api_key}"
    fi
    if [ -z "$actual_api_key" ]; then
      local env_var_specific="API_KEY_${endpoint_name^^}"
      env_var_specific="${env_var_specific//-/_}"
      actual_api_key="${!env_var_specific}"
    fi
    if [ -z "$actual_api_key" ]; then
      actual_api_key="${API_KEY:-}"
    fi

    # Fetch models using list_models_cmd
    echo "Fetching model list..."
    echo "Executing command: $list_cmd"
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
    local -a endpoint_models=()
    if [ -n "$out" ]; then
      if command -v jq >/dev/null 2>&1 && echo "$out" | jq -e . >/dev/null 2>&1; then
        # Try common JSON shapes
        if echo "$out" | jq -e '.data' >/dev/null 2>&1; then
          while IFS= read -r id; do endpoint_models+=("$id"); done < <(echo "$out" | jq -r '.data[]?.id // empty')
        else
          while IFS= read -r id; do endpoint_models+=("$id"); done < <(echo "$out" | jq -r '.[]? // empty')
        fi
      else
        # Treat as space-separated or newline-separated list
        while IFS= read -r line; do
          # Split by spaces/tabs and process each token
          for token in $line; do
            id="$(printf '%s' "$token" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
            if [ -n "$id" ] && printf '%s' "$id" | grep -Eq '^[A-Za-z0-9._:/-]+$'; then
              endpoint_models+=("$id")
            fi
          done
        done <<< "$(printf '%s' "$out")"
      fi
    fi

    # Fallback models if none retrieved
    if [ ${#endpoint_models[@]} -eq 0 ]; then
      echo "Warning: No models found for $endpoint_name"
      echo ""
      continue
    fi

    echo "Found ${#endpoint_models[@]} models"

    # Let user select one model from this endpoint
    echo ""
    echo "Select model from $endpoint_name:"
    local num_models=${#endpoint_models[@]}
    for i in "${!endpoint_models[@]}"; do
      printf "%3d) %s\n" $((i+1)) "${endpoint_models[$i]}"
    done
    printf "%3d) Skip this endpoint\n" $((num_models+1))

    read -p "Enter selection number: " REPLY
    if [[ "$REPLY" =~ ^[0-9]+$ ]] && [ "$REPLY" -ge 1 ] && [ "$REPLY" -le "$((num_models+1))" ]; then
      if [ "$REPLY" -eq $((num_models+1)) ]; then
        echo "Skipped $endpoint_name"
        echo ""
        continue
      fi
      local model_id="${endpoint_models[$((REPLY-1))]}"
      local display_name="${model_id} [${endpoint_name}]"
      
      # Store the selected model
      selected_models+=("$display_name")
      model_to_endpoint["$display_name"]="$endpoint_name"
      model_to_base_url["$display_name"]="$endpoint"
      model_to_api_key["$display_name"]="$actual_api_key"
      
      echo "Selected: $display_name"
      echo ""
    else
      echo "Invalid selection, skipping $endpoint_name"
      echo ""
    fi
  done

  if [ ${#selected_models[@]} -eq 0 ]; then
    echo "No models selected"
    return 1
  fi

  echo "Total models selected: ${#selected_models[@]}"

  # Generate droid config with only selected models
  local config_dir="$HOME/.factory"
  local config_file="$config_dir/config.json"
  mkdir -p "$config_dir"

  # Build JSON array
  local custom_models="["
  local first_entry=true

  for display_name in "${selected_models[@]}"; do
    local endpoint_name="${model_to_endpoint[$display_name]}"
    local base_url="${model_to_base_url[$display_name]}"
    local api_key="${model_to_api_key[$display_name]}"
    
    # Extract model ID from display name (remove " [endpoint]" suffix)
    local model_id="${display_name% \[*\]}"
    
    if [ "$first_entry" = false ]; then
      custom_models+=","
    fi
    first_entry=false

    # Escape special characters in JSON strings
    local display_name_escaped="${display_name//\\/\\\\}"
    display_name_escaped="${display_name_escaped//\"/\\\"}"
    local base_url_escaped="${base_url//\\/\\\\}"
    base_url_escaped="${base_url_escaped//\"/\\\"}"
    local model_id_escaped="${model_id//\\/\\\\}"
    model_id_escaped="${model_id_escaped//\"/\\\"}"
    local api_key_escaped="${api_key//\\/\\\\}"
    api_key_escaped="${api_key_escaped//\"/\\\"}"

    custom_models+="
  {
    \"model_display_name\": \"$display_name_escaped\",
    \"model\": \"$model_id_escaped\",
    \"base_url\": \"$base_url_escaped\",
    \"api_key\": \"$api_key_escaped\",
    \"provider\": \"generic-chat-completion-api\",
    \"max_tokens\": 16384
  }"
  done

  custom_models+="
]"

  # Write config file
  cat > "$config_file" <<EOF
{
  "custom_models": $custom_models
}
EOF

  echo "Droid config written to $config_file"

  # Step 4: Run droid with all passed arguments
  echo "Starting Factory.ai Droid CLI..."
  unset http_proxy HTTP_PROXY https_proxy HTTPS_PROXY no_proxy NO_PROXY all_proxy ALL_PROXY
  echo "DEBUG: running: droid $*"
  export NODE_TLS_REJECT_UNAUTHORIZED='0'
  command droid "$@"
}

# Export the function so it's available in the shell
export -f droid
