# ai-toolboxx
ai toolboxx

This repository contains small utilities and shell aliases for working with AI providers.

Files of interest:
- show_gh_copilot_models.py: script to fetch GitHub Copilot "internal" token and list Copilot models (requires GITHUB_TOKEN env var).
- models_server.py: small local-only HTTP server that exposes /models on 127.0.0.1:5000 and returns the Copilot models JSON. It reads GITHUB_TOKEN from the environment or from MODELS_TOKEN_FILE (file must be owner-readable only). Do not expose this server to the public internet.
- claude_aliases.sh, codex_aliases.sh: shell helper scripts that set provider URLs and models list for local testing.
- endpoints.conf: configuration file for AI endpoints with support for dynamic model listing.

## Configuration

### endpoints.conf

Configure AI endpoints in INI format with the following keys:

```ini
[endpoint-name]
endpoint=https://your-endpoint-url
api_key=your-api-key  # Optional, prefer using environment variables
api_key_env=API_KEY_NAME  # Optional, specify environment variable name for API key
list_models_cmd=command-to-list-models  # Optional shell command to fetch models
keep_proxy_config=true  # Optional, preserve proxy settings when running list_models_cmd (default: false)
```

The `list_models_cmd` supports multiple output formats:
- **Space-separated**: `echo gpt-5-mini gpt-5`
- **Newline-separated**: `printf "model1\nmodel2\nmodel3"`
- **JSON**: curl commands returning `{"data": [{"id": "model1"}, ...]}` or `[{"id": "model1"}, ...]`

#### Proxy Configuration

The `keep_proxy_config` setting controls how HTTP proxy environment variables are handled when executing `list_models_cmd`:

- **`keep_proxy_config=true`**: Proxy environment variables (`http_proxy`, `https_proxy`, `HTTP_PROXY`, `HTTPS_PROXY`, `no_proxy`, `NO_PROXY`, `all_proxy`, `ALL_PROXY`) are preserved when running the command. Use this when your model listing command needs to go through a proxy.

- **`keep_proxy_config=false` or not set** (default): All proxy environment variables are explicitly unset before running the command. Use this when your endpoint is directly accessible and you want to bypass any configured proxies.

Example:
```ini
[litellm]
endpoint=https://10.189.8.10:4142
api_key_env=API_KEY_LITELLM
list_models_cmd=curl -sS -k "$endpoint/v1/models"
keep_proxy_config=false  # Direct access, no proxy

[copilot-api]
endpoint=https://10.189.8.10:5000
api_key_env=API_KEY_COPILOT
list_models_cmd=python list_gh_copilot_models.py
keep_proxy_config=true  # Needs proxy to reach GitHub
```

When executing, the scripts will display the command being run for transparency.

Note: Only the 'claude' and 'codex' helper scripts support selecting models via the endpoints.conf file (using the @endpoint-name notation). Other providers do not currently support model selection through endpoints.conf.

Quickstart
1. Provide a GitHub token with repo access via environment variable:
   export GITHUB_TOKEN=ghp_...
2. Run the local models server (binds to 127.0.0.1:5000):
   python3 models_server.py
3. Fetch models:
   curl -s http://127.0.0.1:5000/models | jq .

Security and token handling
- Never commit your GITHUB_TOKEN or MODELS_TOKEN_FILE to git. Add a .env to .gitignore.
- Prefer storing the token in an OS keyring or a file readable only by the owner (chmod 600).
- The server will not accept tokens over HTTP requests. It only reads tokens from environment variables or a server-side file.

I have included a models_server.py, a .env.example, and a .gitignore entry to help keep tokens out of version control. If you want me to create a git commit for these changes, tell me and I will create one.

Security reminder: Do not run the models server on a public host. It is intended for local development only.

Last updated on 2023-10-18 by Droid.
