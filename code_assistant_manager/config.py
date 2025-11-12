"""Configuration management for Code Assistant Manager."""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .env_loader import load_env

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages providers.json file parsing and endpoint configuration."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize ConfigManager.

        Args:
            config_path: Path to providers.json. If None, looks for it in standard locations.
        """
        logger.debug(f"Initializing ConfigManager with config_path: {config_path}")
        if config_path is None:
            # Lookup order for providers.json (installed location first):
            # 1) ~/.config/code-assistant-manager/providers.json
            # 2) ./providers.json (current working directory)
            # 3) $HOME/providers.json
            script_dir = Path(__file__).parent
            home_config = (
                Path.home() / ".config" / "code-assistant-manager" / "providers.json"
            )
            cwd_config = Path.cwd() / "providers.json"
            home_root_config = Path.home() / "providers.json"

            logger.debug(
                f"Checking config locations: home={home_config}, cwd={cwd_config}, home_root={home_root_config}"
            )

            if home_config.exists():
                config_path = str(home_config)
                logger.debug(f"Using home config: {config_path}")
            elif cwd_config.exists():
                config_path = str(cwd_config)
                logger.debug(f"Using cwd config: {config_path}")
            elif home_root_config.exists():
                config_path = str(home_root_config)
                logger.debug(f"Using home root config: {config_path}")
            else:
                # Fallback to bundled providers.json in the package
                config_path = str(script_dir / "providers.json")
                logger.debug(f"Using fallback config: {config_path}")

        self.config_path = Path(config_path)
        self.config_data: Dict[str, Any] = {}
        self._validation_cache: Optional[Tuple[bool, List[str]]] = None
        self._validation_cache_time: float = 0.0
        self._validation_cache_ttl: int = 60
        logger.debug(f"ConfigManager initialized with path: {self.config_path}")
        self.reload()

    def reload(self):
        """Reload configuration from file and invalidate cache."""
        logger.debug(f"Reloading configuration from: {self.config_path}")
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)
                logger.debug(
                    f"Successfully loaded config with {len(self.config_data.get('endpoints', {}))} endpoints"
                )
            except json.JSONDecodeError as e:
                error_msg = (
                    f"Invalid JSON in configuration file {self.config_path}.\n"
                    f"Error: {e}\n"
                    f"Please check the JSON syntax and fix any formatting issues."
                )
                logger.error(error_msg)
                raise ValueError(error_msg) from e
        else:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        # Invalidate validation cache when config changes
        self._validation_cache = None
        self._validation_cache_time = 0
        logger.debug("Invalidated validation cache")

    def get_sections(self, exclude_common: bool = True) -> List[str]:
        """
        Get all endpoint sections from config.

        Args:
            exclude_common: If True, exclude the common section (always True for JSON format)

        Returns:
            List of endpoint names
        """
        endpoints: Dict[str, Any] = self.config_data.get("endpoints", {})
        return list(endpoints.keys())

    def get_value(self, section: str, key: str, default: str = "") -> str:
        """
        Get a configuration value.

        Args:
            section: Section name (endpoint name or "common")
            key: Key name
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        try:
            value: Any = None
            if section == "common":
                value = self.config_data.get("common", {}).get(key)
            else:
                value = self.config_data.get("endpoints", {}).get(section, {}).get(key)

            if value is None:
                return default

            # Convert boolean and numeric values to strings for compatibility
            if isinstance(value, bool):
                return str(value).lower()
            elif isinstance(value, (int, float)):
                return str(value)

            return str(value).strip()
        except Exception:
            return default

    def get_endpoint_config(self, endpoint_name: str) -> Dict[str, str]:
        """
        Get full configuration for an endpoint.

        Args:
            endpoint_name: Name of the endpoint

        Returns:
            Dictionary with endpoint configuration
        """
        endpoints = self.config_data.get("endpoints", {})
        if endpoint_name not in endpoints:
            return {}

        config = endpoints[endpoint_name].copy()

        # Convert all values to strings for compatibility
        for key, value in config.items():
            if isinstance(value, bool):
                config[key] = str(value).lower()
            elif isinstance(value, (int, float)):
                config[key] = str(value)
            else:
                config[key] = str(value).strip()

        return config

    def get_common_config(self) -> Dict[str, str]:
        """
        Get common configuration.

        Returns:
            Dictionary with common configuration
        """
        common = self.config_data.get("common", {})

        config = {}
        for key, value in common.items():
            if isinstance(value, bool):
                config[key] = str(value).lower()
            elif isinstance(value, (int, float)):
                config[key] = str(value)
            else:
                config[key] = str(value).strip()

        return config

    def load_env_file(self, env_file: Optional[str] = None):
        """
        Load environment variables from .env file.

        Args:
            env_file: Path to .env file. If None, looks for it in standard locations.
        """
        logger.debug(f"Loading env file, requested path: {env_file}")
        if load_env(env_file, force=True):
            logger.debug("Environment variables loaded successfully")
        else:
            logger.debug("No .env file found or failed to load")

    def validate_config(self) -> Tuple[bool, List[str]]:
        """
        Validate the entire configuration with caching.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        logger.debug("Starting config validation")
        current_time = time.time()

        # Return cached result if still valid
        if (
            self._validation_cache is not None
            and current_time - self._validation_cache_time < self._validation_cache_ttl
        ):
            logger.debug("Using cached validation result")
            return self._validation_cache

        errors = []
        logger.debug("Performing fresh config validation")

        # Validate common section
        common_config = self.get_common_config()
        if common_config:
            # Validate proxy URLs if present
            http_proxy = common_config.get("http_proxy", "")
            if http_proxy and not validate_url(http_proxy):
                errors.append(f"Invalid HTTP proxy URL: {http_proxy}")

            https_proxy = common_config.get("https_proxy", "")
            if https_proxy and not validate_url(https_proxy):
                errors.append(f"Invalid HTTPS proxy URL: {https_proxy}")

            cache_ttl = common_config.get("cache_ttl_seconds", "")
            if cache_ttl:
                try:
                    int(cache_ttl)
                except ValueError:
                    errors.append(f"Invalid cache_ttl_seconds value: {cache_ttl}")

        # Validate endpoints
        endpoints = self.config_data.get("endpoints", {})
        for endpoint_name, endpoint_config in endpoints.items():
            # Validate endpoint URL
            endpoint_url = endpoint_config.get("endpoint", "")
            if not endpoint_url:
                errors.append(f"Missing endpoint URL for {endpoint_name}")
            elif not validate_url(endpoint_url):
                errors.append(
                    f"Invalid endpoint URL for {endpoint_name}: {endpoint_url}"
                )

            # Validate api_key_env if present
            api_key_env = endpoint_config.get("api_key_env", "")
            if api_key_env and not validate_non_empty_string(api_key_env):
                errors.append(f"Invalid api_key_env for {endpoint_name}: {api_key_env}")

            # Validate list_models_cmd if present
            list_models_cmd = endpoint_config.get("list_models_cmd", "")
            if list_models_cmd and not validate_command(list_models_cmd):
                errors.append(
                    f"Invalid list_models_cmd for {endpoint_name}: {list_models_cmd}"
                )

            # Validate boolean values
            keep_proxy_config = endpoint_config.get("keep_proxy_config", "")
            if keep_proxy_config and not validate_boolean(keep_proxy_config):
                errors.append(
                    f"Invalid keep_proxy_config for {endpoint_name}: {keep_proxy_config}"
                )

            use_proxy = endpoint_config.get("use_proxy", "")
            if use_proxy and not validate_boolean(use_proxy):
                errors.append(f"Invalid use_proxy for {endpoint_name}: {use_proxy}")

            # Validate supported_client if present
            supported_client = endpoint_config.get("supported_client", "")
            if supported_client and not validate_non_empty_string(supported_client):
                errors.append(
                    f"Invalid supported_client for {endpoint_name}: {supported_client}"
                )

        result = (len(errors) == 0, errors)

        # Cache the result
        self._validation_cache = result
        self._validation_cache_time = current_time

        if errors:
            logger.warning(
                f"Config validation failed with {len(errors)} errors: {errors}"
            )
        else:
            logger.debug("Config validation passed")

        return result


def validate_url(url: str) -> bool:
    """
    Validate a URL.

    Args:
        url: URL to validate

    Returns:
        True if valid, False otherwise
    """
    if not url or len(url) > 2048:
        return False

    # Basic URL pattern matching for HTTP/HTTPS
    import re

    pattern = r"^https?://(localhost|127\.0\.0\.1|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})(:[0-9]+)?(/.*)?$"
    return bool(re.match(pattern, url))


def validate_api_key(key: str) -> bool:
    """
    Validate an API key.

    Args:
        key: API key to validate

    Returns:
        True if valid, False otherwise
    """
    if not key or len(key) < 10:
        return False

    # Allow alphanumeric, dots, hyphens, underscores, equals
    import re

    return not bool(re.search(r"[^a-zA-Z0-9._=-]", key))


def validate_model_id(model_id: str) -> bool:
    """
    Validate a model ID.

    Args:
        model_id: Model ID to validate

    Returns:
        True if valid, False otherwise
    """
    import re

    return bool(re.match(r"^[a-zA-Z0-9._:/\-]+$", model_id))


def validate_boolean(value) -> bool:
    """
    Validate a boolean value.

    Args:
        value: String or boolean value to validate

    Returns:
        True if valid, False otherwise
    """
    if value is None:
        return False

    # Handle actual boolean values
    if isinstance(value, bool):
        return True

    # Handle string values
    if isinstance(value, str):
        return value.lower() in ("true", "false", "1", "0", "yes", "no")

    return False


def validate_non_empty_string(value: str) -> bool:
    """
    Validate a non-empty string.

    Args:
        value: String value to validate

    Returns:
        True if valid, False otherwise
    """
    return bool(value and value.strip())


def validate_command(value: str) -> bool:
    """
    Validate a command string with balanced security and functionality.

    Args:
        value: Command string to validate

    Returns:
        True if valid, False otherwise
    """
    if not value:
        return False

    # Strip leading/trailing whitespace
    value = value.strip()

    # Check for obviously dangerous patterns that should never be allowed
    obviously_dangerous_patterns = [
        ";rm ",
        "; rm ",  # rm command execution
        "|rm ",
        "| rm ",  # rm command execution
        "&&rm ",
        "&& rm ",  # rm command execution
        "||rm ",
        "|| rm ",  # rm command execution
        ";reboot",  # System reboot
        ";shutdown",  # System shutdown
        "|reboot",  # System reboot
        "|shutdown",  # System shutdown
        "&&reboot",  # System reboot
        "&&shutdown",  # System shutdown
        "||reboot",  # System reboot
        "||shutdown",  # System shutdown
        "`",  # Command substitution (backticks) - too dangerous
        "$(",  # Command substitution - too dangerous
        ">/etc/",  # Writing to system files
        ">>/etc/",  # Appending to system files
        "< /etc/",  # Reading from system files
        " | sh",
        " | bash",  # Piping to shell
        " > /",
        " >> /",  # Writing to root
        " < /",  # Reading from root
        "sudo ",  # Privilege escalation
        "su ",  # User switching
        "chmod ",  # Permission changes
        "chown ",  # Ownership changes
        "mv ",  # File moving
        "cp ",  # File copying
        "ln ",  # Link creation
        "mount ",  # Mounting filesystems
        "umount ",  # Unmounting filesystems
        "kill ",  # Process killing
        "killall ",  # Killing processes by name
        "crontab ",  # Cron job manipulation
        "at ",  # Scheduled command execution
        "systemctl ",  # System service control
        "service ",  # Service management
        "init ",  # System initialization
        "telnet ",  # Network connections
        "nc ",  # Network connections
        "netcat ",  # Network connections
        "ssh ",  # SSH connections
        "scp ",  # File transfers
        "rsync ",  # File synchronization
        "wget ",  # File downloads (more specific)
        # 'curl ' is allowed as a legitimate command - specific dangerous curl patterns are checked elsewhere
        "ftp ",  # FTP connections
        "sftp ",  # Secure file transfers
        "git clone ",  # Repository cloning
        "git push ",  # Repository pushing
        "git pull ",  # Repository pulling
        "git fetch ",  # Repository fetching
        "git checkout ",  # Repository checkout
        "pip install ",  # Package installation
        "npm install ",  # Node package installation
        "yarn add ",  # Yarn package installation
        "gem install ",  # Ruby gem installation
        "apt-get ",  # Package management
        "yum ",  # Package management
        "dnf ",  # Package management
        "brew ",  # Package management
        "make install",  # Build and install
        "configure ",  # Configuration scripts
        "install ",  # Generic install commands
        "setup ",  # Setup scripts
        "eval ",  # Code evaluation
        "exec ",  # Code execution
        "source ",  # Source commands (bash)
        # '. ' is handled as a safe construct
        "import ",  # Python import (if used in shell context)
        "require ",  # Node.js require (if used in shell context)
        "include ",  # C-style includes
        "import-module ",  # PowerShell module import
        "add-module ",  # PowerShell module addition
        "import-module ",  # PowerShell module import
    ]
    # Check for obviously dangerous patterns
    if any(pattern in value.lower() for pattern in obviously_dangerous_patterns):
        return False

    # Check for dangerous file operations with specific paths
    dangerous_file_operations = [
        "/etc/passwd",
        "/etc/shadow",
        "/etc/group",
        "/etc/sudoers",
        "/root/",
        "/home/",
        "/usr/bin/",
        "/bin/",
        "/sbin/",
        "~/.ssh/",
        "~/.bashrc",
        "~/.zshrc",
        "~/.profile",
    ]

    if any(path in value for path in dangerous_file_operations):
        return False
    # Allow commonly used safe shell constructs
    # These are needed for legitimate use cases like the examples in providers.json
    safe_shell_constructs = [
        "|",  # Pipe (used in the litellm example)
        "&&",  # Command chaining (used in the copilot-api example)
        ". ",  # Source command (used in the copilot-api example)
        "${",  # Variable expansion (used in the litellm example)
    ]

    # If the command contains safe shell constructs, allow it
    # The dangerous patterns check above will still catch malicious usage
    if any(construct in value for construct in safe_shell_constructs):
        return True

    # For simple commands without shell constructs, use the original validation logic
    # Split command into parts (executable and arguments)
    import shlex

    try:
        parts = shlex.split(value)
    except ValueError:
        # If we can't parse it, it's likely malicious
        return False

    if not parts:
        return False

    # Allow plain space-separated model lists (e.g., "qwen3-max qwen3-coder-plus")
    try:
        if all(validate_model_id(p) for p in parts):
            return True
    except Exception:
        # If validate_model_id is not suitable for a token, fall back to executable checks
        pass

    # Validate executable (first part)
    executable = parts[0]

    # Allow only specific safe executables or paths
    safe_executables = {
        "curl",
        "wget",
        "echo",
        "cat",
        "python",
        "python3",
        "node",
        "npm",
        "sh",
        "bash",
        "ls",
        "pwd",
        "whoami",
        "date",
        "git",
        "docker",
        "jq",
        "grep",
        "find",
        "wc",
        "sort",
        "uniq",
        "head",
        "tail",
        "sed",
        "awk",
    }
    # Check if it's a direct path to a file in current directory or subdirectories
    import os

    if os.path.isabs(executable):
        # Absolute paths are not allowed for security
        return False

    # Check if it's a relative path (contains / but not at the beginning)
    if "/" in executable and not executable.startswith("/"):
        # Relative paths are allowed for security - they can't be used for command injection
        # since they must point to files in the current directory or subdirectories
        pass  # Allow all relative paths
    elif executable not in safe_executables:
        # Not a recognized safe executable
        return False

    # Validate arguments (remaining parts)
    for arg in parts[1:]:
        # Check for dangerous patterns in arguments
        dangerous_patterns = [";", "&", "`", "$(", ">>", "<<"]

        # Check for obviously dangerous patterns in arguments
        if any(pattern in arg for pattern in dangerous_patterns):
            return False

        # Check for variable expansion in arguments (allow it in quotes)
        if "$" in arg and not arg.startswith("'") and not arg.endswith("'"):
            # Allow $ in single quotes (literal) but not in unquoted strings
            # This is a compromise to allow legitimate usage while preventing some injection
            pass  # Allow it for now since we've already checked for command substitution

        # Check for dangerous file paths in arguments
        if any(path in arg for path in dangerous_file_operations):
            return False

    return True
