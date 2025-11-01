"""GitHub Copilot API models fetcher."""

import logging
import os
import threading
import time
import uuid

import requests

from .env_loader import load_env

logger = logging.getLogger(__name__)


COPILOT_PLUGIN_VERSION = "copilot-chat/0.26.7"
COPILOT_USER_AGENT = "GitHubCopilotChat/0.26.7"
API_VERSION = "2025-04-01"


def get_copilot_token(github_token: str):
    """Calls GitHub API: GET /copilot_internal/v2/token"""
    headers = {
        "authorization": f"token {github_token}",
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": "models-fetcher/1.0",
    }
    # Security: Add timeout to prevent hanging connections
    r = requests.get(
        "https://api.github.com/copilot_internal/v2/token", headers=headers, timeout=30
    )
    r.raise_for_status()
    return r.json()


def copilot_base_url(account_type: str = "individual") -> str:
    return (
        "https://api.githubcopilot.com"
        if account_type == "individual"
        else f"https://api.{account_type}.githubcopilot.com"
    )


def copilot_headers(
    copilot_token: str, vs_code_version: str = "1.0.1", vision: bool = False
):
    h = {
        "Authorization": f"Bearer {copilot_token}",
        "content-type": "application/json",
        "copilot-integration-id": "vscode-chat",
        "editor-version": f"vscode/{vs_code_version}",
        "editor-plugin-version": COPILOT_PLUGIN_VERSION,
        "user-agent": COPILOT_USER_AGENT,
        "openai-intent": "conversation-panel",
        "x-github-api-version": API_VERSION,
        "x-request-id": str(uuid.uuid4()),
        "x-vscode-user-agent-library-version": "electron-fetch",
    }
    if vision:
        h["copilot-vision-request"] = "true"
    return h


def fetch_models(copilot_token: str, account_type: str = "individual"):
    url = f"{copilot_base_url(account_type)}/models"
    # Security: Add timeout to prevent hanging connections
    r = requests.get(url, headers=copilot_headers(copilot_token), timeout=30)
    r.raise_for_status()
    return r.json()


def start_refresh_loop(github_token: str, state: dict):
    """Background thread that refreshes the Copilot token and stores it in state."""

    def _loop():
        while True:
            info = get_copilot_token(github_token)
            state["copilot_token"] = info["token"]
            refresh_in = info.get("refresh_in", 300)
            sleep_for = max(30, refresh_in - 60)
            time.sleep(sleep_for)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t


def list_models():
    """List available GitHub Copilot models. Returns model IDs, one per line."""
    # Load environment variables from .env file
    logger.debug("Loading environment variables from .env file")
    load_env()
    logger.debug("Environment variables loaded")

    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is required but not found")
        raise SystemExit("GITHUB_TOKEN environment variable is required")

    logger.debug("Starting Copilot token refresh loop")
    state = {}
    start_refresh_loop(github_token, state)

    time.sleep(1)

    copilot_token = state.get("copilot_token")
    if not copilot_token:
        logger.debug("No token in state, fetching directly")
        info = get_copilot_token(github_token)
        copilot_token = info["token"]
        state["copilot_token"] = copilot_token

    logger.debug("Fetching Copilot models")
    models = fetch_models(copilot_token)
    model_count = len(models.get("data", []))
    logger.debug(f"Found {model_count} models")

    for m in models.get("data", []):
        print(m.get("id"))


if __name__ == "__main__":
    list_models()
