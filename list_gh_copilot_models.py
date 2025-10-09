#!/usr/bin/env python3
import os
import uuid
import time
import threading
import requests

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
    r = requests.get("https://api.github.com/copilot_internal/v2/token", headers=headers)
    r.raise_for_status()
    return r.json()


def copilot_base_url(account_type: str = "individual") -> str:
    return "https://api.githubcopilot.com" if account_type == "individual" else f"https://api.{account_type}.githubcopilot.com"


def copilot_headers(copilot_token: str, vs_code_version: str = "1.0.0", vision: bool = False):
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
    r = requests.get(url, headers=copilot_headers(copilot_token))
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


if __name__ == "__main__":
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
    if not GITHUB_TOKEN:
        raise SystemExit("GITHUB_TOKEN environment variable is required")

    state = {}
    # start background refresh so state['copilot_token'] stays valid
    start_refresh_loop(GITHUB_TOKEN, state)

    # Wait briefly for first token fetch
    time.sleep(1)

    copilot_token = state.get("copilot_token")
    if not copilot_token:
        # fallback: fetch synchronously if background thread hasn't populated yet
        info = get_copilot_token(GITHUB_TOKEN)
        copilot_token = info["token"]
        state["copilot_token"] = copilot_token

    models = fetch_models(copilot_token)
    for m in models.get("data", []):
        print(m.get("id"))
