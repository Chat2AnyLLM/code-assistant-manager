"""Endpoint management for Code Assistant Manager."""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import ConfigManager, validate_api_key, validate_model_id, validate_url
from .exceptions import EndpointError, TimeoutError, create_error_handler
from .menu.menus import display_centered_menu


class EndpointManager:
    """Manages AI provider endpoints and model fetching."""

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize EndpointManager.

        Args:
            config_manager: ConfigManager instance
        """
        self.config: ConfigManager = config_manager
        self.cache_dir: Path = (
            Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
            / "code-assistant-manager"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def select_endpoint(
        self, client_name: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Display endpoint selection menu.

        Args:
            client_name: Optional client name to filter endpoints

        Returns:
            Tuple of (success, endpoint_name)
        """
        endpoints = self.config.get_sections(exclude_common=True)

        if not endpoints:
            print("Error: No endpoints configured in settings.conf")
            return False, None

        # Filter endpoints by client if specified
        if client_name:
            filtered = []
            for ep in endpoints:
                if self._is_client_supported(ep, client_name):
                    filtered.append(ep)
            endpoints = filtered

            if not endpoints:
                print(
                    f"Error: No endpoints configured for client '{client_name}' in settings.conf"
                )
                return False, None

        # Build endpoint choices with descriptions in the format: name -> endpoint -> description
        choices = []
        for ep in endpoints:
            ep_config = self.config.get_endpoint_config(ep)
            ep_url = ep_config.get("endpoint", "")
            ep_desc = ep_config.get("description", "")

            if not ep_desc:
                ep_desc = ep_url

            choices.append(f"{ep} -> {ep_url} -> {ep_desc}")

        # Display menu
        title = (
            f"Select Endpoint for {client_name}" if client_name else "Select Endpoint"
        )
        success, idx = display_centered_menu(title, choices, "Cancel")

        if success and idx is not None:
            return True, endpoints[idx]

        return False, None

    def get_endpoint_config(self, endpoint_name: str) -> Tuple[bool, Dict[str, str]]:
        """
        Get complete endpoint configuration.

        Args:
            endpoint_name: Name of the endpoint

        Returns:
            Tuple of (success, config_dict)
        """
        config = self.config.get_endpoint_config(endpoint_name)
        if not config:
            print(f"Error: Endpoint '{endpoint_name}' not found in configuration")
            return False, {}

        # Validate endpoint URL
        endpoint_url = config.get("endpoint", "")
        if not validate_url(endpoint_url):
            error = EndpointError(
                f"Endpoint URL failed validation: {endpoint_url}",
                endpoint=endpoint_name,
                suggestions=[
                    "Check that the endpoint URL is properly formatted",
                    "Ensure the URL starts with http:// or https://",
                    "Verify the endpoint is accessible",
                ],
            )
            print(error.get_detailed_message())
            return False, {}

        # Get API key
        actual_api_key = self._resolve_api_key(endpoint_name, config)

        # Validate API key if present
        if actual_api_key and not validate_api_key(actual_api_key):
            error = EndpointError(
                "API key failed validation",
                endpoint=endpoint_name,
                suggestions=[
                    "Check that the API key is properly formatted",
                    "Verify the API key is valid and not expired",
                    "Ensure the API key has the required permissions",
                ],
            )
            print(error.get_detailed_message())
            return False, {}

        # Get proxy settings if use_proxy is true
        proxy_settings = {}
        use_proxy_value = config.get("use_proxy", "false")
        use_proxy = str(use_proxy_value).lower() == "true"
        if use_proxy:
            common_config = self.config.get_common_config()
            proxy_settings = {
                "http_proxy": common_config.get("http_proxy", ""),
                "https_proxy": common_config.get("https_proxy", ""),
                "no_proxy": common_config.get("no_proxy", ""),
            }

        # Display confirmation
        desc = config.get("description", endpoint_url)
        print(f"Using endpoint '{endpoint_name}' ({desc}) -> {endpoint_url}")

        result = {
            **config,
            "actual_api_key": actual_api_key,
            "proxy_settings": json.dumps(proxy_settings),
        }

        return True, result

    def fetch_models(
        self,
        endpoint_name: str,
        endpoint_config: Dict[str, str],
        use_cache_if_available: bool = True,
    ) -> Tuple[bool, List[str]]:
        """
        Fetch available models from endpoint.

        Args:
            endpoint_name: Name of the endpoint
            endpoint_config: Endpoint configuration
            use_cache_if_available: If True, prompt user about using cache. If False, always fetch fresh.

        Returns:
            Tuple of (success, models_list)
        """
        models = []

        # Check cache first (but skip menu if use_cache_if_available is False)
        cache_file = (
            self.cache_dir / f"code_assistant_manager_models_cache_{endpoint_name}.txt"
        )
        cache_ttl = int(self.config.get_common_config().get("cache_ttl_seconds", 86400))

        if cache_file.exists() and use_cache_if_available:
            import time

            # Read cache file and validate timestamp
            try:
                with open(cache_file, "r") as f:
                    lines = f.readlines()

                if not lines:
                    # Empty cache, fetch fresh
                    pass
                else:
                    # First line should be timestamp, rest are models
                    cache_time_str = lines[0].strip()

                    # Validate timestamp is numeric
                    if cache_time_str.isdigit():
                        cache_time = int(cache_time_str)
                        current_time = int(time.time())

                        if (current_time - cache_time) < cache_ttl:
                            # Cache is valid, ask user
                            success, idx = display_centered_menu(
                                "Model List Cache Available",
                                ["Use cached model list", "Refresh from server"],
                                "Cancel",
                            )

                            if success:
                                if idx == 0:
                                    # Use cache - skip first line (timestamp)
                                    models = [
                                        line.strip()
                                        for line in lines[1:]
                                        if line.strip()
                                    ]
                                    return True, models
                                # Otherwise (idx == 1) fall through to fetch fresh
                            # If user cancelled or selected refresh, fall through to fetch fresh
                    # If timestamp is invalid or missing, fall through to fetch fresh
            except Exception as e:
                # Error reading cache, fall through to fetch fresh
                print(f"Warning: Error reading cache: {e}")

        # Fetch fresh models
        list_cmd = endpoint_config.get("list_models_cmd", "")
        if not list_cmd:
            print("Warning: No list_models_cmd configured, using empty model list")
            return True, models

        print("Fetching model list...")
        print("Executing configured list command (redacted)")

        # Set environment variables
        env = os.environ.copy()
        endpoint_url = endpoint_config.get("endpoint", "")
        api_key = endpoint_config.get("actual_api_key", "")
        env["endpoint"] = endpoint_url
        env["api_key"] = api_key

        # Handle proxy settings
        keep_proxy_value = endpoint_config.get("keep_proxy_config", "false")
        keep_proxy = str(keep_proxy_value).lower() == "true"
        if keep_proxy and endpoint_config.get("proxy_settings"):
            try:
                proxy_settings = json.loads(endpoint_config.get("proxy_settings", "{}"))
                for key, value in proxy_settings.items():
                    if value:
                        env[key] = value
            except json.JSONDecodeError:
                # If proxy_settings is not valid JSON, use an empty dict
                pass
        else:
            # Remove proxy variables
            for key in [
                "http_proxy",
                "https_proxy",
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "no_proxy",
                "NO_PROXY",
            ]:
                env.pop(key, None)

        # Execute command
        try:
            toolbox_dir = Path(__file__).parent.parent
            # Security: Use shlex.split() instead of shell=True to prevent injection
            import contextlib
            import importlib
            import io
            import shlex
            import shutil

            tokens = shlex.split(list_cmd)

            output = ""

            # Support running specific python -m modules by calling them directly
            if (
                len(tokens) >= 3
                and tokens[1] == "-m"
                and tokens[2]
                in (
                    "code_assistant_manager.litellm_models",
                    "code_assistant_manager.copilot_models",
                )
            ):
                module_name = tokens[2]
                try:
                    mod = importlib.import_module(module_name)
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        # Call list_models() which prints model IDs
                        mod.list_models()
                    output = buf.getvalue().strip()
                except Exception as e:
                    print(f"Warning: Failed to load module {module_name}: {e}")
                    return True, models

            # If first token is not an executable on PATH, treat the value as literal model list
            elif tokens and shutil.which(tokens[0]) is None:
                output = " ".join(tokens).strip()

            else:
                # Fallback: run as subprocess
                result = subprocess.run(
                    tokens,
                    shell=False,
                    capture_output=True,
                    text=True,
                    cwd=toolbox_dir,
                    env=env,
                    timeout=60,
                )

                output = result.stdout.strip()
                if result.returncode != 0:
                    print(
                        f"Warning: Command failed with return code {result.returncode}"
                    )
                    if result.stderr:
                        print(f"Command stderr: {result.stderr}")
                    return True, models
                if not output:
                    print("Warning: Command returned no output")
                    return True, models

            # Parse output
            models = self._parse_models_output(output)

            # Save to cache with timestamp on first line
            import time

            with open(cache_file, "w") as f:
                f.write(f"{int(time.time())}\n")
                for model in models:
                    f.write(f"{model}\n")

            return True, models

        except subprocess.TimeoutExpired:
            error = TimeoutError(
                f"Model fetch command timed out for endpoint '{endpoint_name}'",
                tool_name="model_fetch",
                timeout_seconds=60,
                suggestions=[
                    "Check network connectivity",
                    "Verify the endpoint is responsive",
                    "Try again with a longer timeout",
                    "Check if the endpoint requires authentication",
                ],
            )
            print(error.get_detailed_message())

            # Try to use cached data if available
            if cache_file.exists():
                try:
                    import time

                    with open(cache_file, "r") as f:
                        lines = f.readlines()
                    if lines:
                        # First line should be timestamp, rest are models
                        cache_time_str = lines[0].strip()
                        # Validate timestamp is numeric
                        if cache_time_str.isdigit():
                            cache_time = int(cache_time_str)
                            current_time = int(time.time())
                            cache_ttl = int(
                                self.config.get_common_config().get(
                                    "cache_ttl_seconds", 86400
                                )
                            )
                            if (current_time - cache_time) < cache_ttl:
                                # Cache is valid, use it
                                models = [
                                    line.strip() for line in lines[1:] if line.strip()
                                ]
                                print("Using cached model list due to timeout")
                                return True, models
                except Exception as cache_e:
                    print(f"Error reading cache after timeout: {cache_e}")
            return False, []
        except Exception as e:
            error_handler = create_error_handler("model_fetch")
            structured_error = error_handler(
                e,
                f"Error fetching models from endpoint '{endpoint_name}'",
                command=list_cmd,
                endpoint=endpoint_name,
            )
            print(structured_error.get_detailed_message())

            # Try to use cached data if available
            if cache_file.exists():
                try:
                    import time

                    with open(cache_file, "r") as f:
                        lines = f.readlines()
                    if lines:
                        # First line should be timestamp, rest are models
                        cache_time_str = lines[0].strip()
                        # Validate timestamp is numeric
                        if cache_time_str.isdigit():
                            cache_time = int(cache_time_str)
                            current_time = int(time.time())
                            cache_ttl = int(
                                self.config.get_common_config().get(
                                    "cache_ttl_seconds", 86400
                                )
                            )
                            if (current_time - cache_time) < cache_ttl:
                                # Cache is valid, use it
                                models = [
                                    line.strip() for line in lines[1:] if line.strip()
                                ]
                                print("Using cached model list due to error")
                                return True, models
                except Exception as cache_e:
                    print(f"Error reading cache after error: {cache_e}")
            return False, []

    def _resolve_api_key(
        self, endpoint_name: str, endpoint_config: Dict[str, str]
    ) -> str:
        """
        Resolve API key from various sources.

        Args:
            endpoint_name: Name of the endpoint
            endpoint_config: Endpoint configuration

        Returns:
            API key or empty string
        """
        # 1. Check api_key_env variable
        api_key_env = endpoint_config.get("api_key_env", "")
        if api_key_env and api_key_env in os.environ:
            return os.environ[api_key_env]

        # 2. Check dynamic env var API_KEY_<ENDPOINT_NAME>
        dynamic_var = f"API_KEY_{endpoint_name.upper().replace('-', '_')}"
        if dynamic_var in os.environ:
            return os.environ[dynamic_var]

        # 3. Check special cases
        if endpoint_name == "copilot-api" and "API_KEY_COPILOT" in os.environ:
            return os.environ["API_KEY_COPILOT"]
        if endpoint_name == "litellm" and "API_KEY_LITELLM" in os.environ:
            return os.environ["API_KEY_LITELLM"]

        # 4. Check generic API_KEY
        if "API_KEY" in os.environ:
            return os.environ["API_KEY"]

        # 5. Check config file value
        return endpoint_config.get("api_key", "")

    def _is_client_supported(self, endpoint_name: str, client_name: str) -> bool:
        """
        Check if endpoint supports a client.

        Args:
            endpoint_name: Name of the endpoint
            client_name: Name of the client

        Returns:
            True if supported, False otherwise
        """
        endpoint_config = self.config.get_endpoint_config(endpoint_name)
        supported = endpoint_config.get("supported_client", "")

        # If no restriction or empty client name, allow all
        if not supported or not client_name:
            return True

        # Check if client is in the comma-separated list
        clients = [c.strip() for c in supported.split(",")]
        return client_name in clients

    def _parse_models_output(self, output: str) -> List[str]:
        """
        Parse model list from various output formats.

        Args:
            output: Raw command output

        Returns:
            List of model IDs
        """
        models = []

        # Try JSON parsing first
        try:
            data = json.loads(output)
            if isinstance(data, dict) and "data" in data:
                # OpenAI format
                for item in data["data"]:
                    if isinstance(item, dict) and "id" in item:
                        model_id = item["id"]
                        if validate_model_id(model_id):
                            models.append(model_id)
            elif isinstance(data, list):
                # Array format
                for item in data:
                    if isinstance(item, dict) and "id" in item:
                        model_id = item["id"]
                        if validate_model_id(model_id):
                            models.append(model_id)
            return models if models else self._parse_text_models(output)
        except json.JSONDecodeError:
            pass

        # Fall back to text parsing
        return self._parse_text_models(output)

    def _parse_text_models(self, output: str) -> List[str]:
        """
        Parse model list from text output (space or newline separated).

        Args:
            output: Raw text output

        Returns:
            List of model IDs
        """
        # Check if output looks like an error message
        if "expected" in output.lower() or "error" in output.lower():
            return []

        models = []

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Try space-separated values
            for token in line.split():
                token = token.strip()
                if token and validate_model_id(token):
                    models.append(token)

        return models
