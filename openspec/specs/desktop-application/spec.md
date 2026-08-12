# Desktop Application Specification

## Purpose

Define how the Tauri desktop interface accesses CAM's shared Go behavior safely.

## Requirements

### Requirement: Shared backend behavior

The desktop application SHALL expose CAM domain operations through Go services shared with the CLI instead of reimplementing domain behavior in React or Rust.

#### Scenario: Execute a desktop operation

- **GIVEN** a user initiates a provider, tool, entity, MCP, diagnostic, configuration, or launch operation in the desktop UI
- **WHEN** the request reaches the Go sidecar
- **THEN** the sidecar delegates it to the corresponding shared desktop service and domain package

### Requirement: Authenticated loopback sidecar

The sidecar SHALL bind to loopback by default, reject unexpected Host values, restrict allowed browser origins, and require the configured bearer token for API requests.

#### Scenario: Tauri starts the sidecar

- **WHEN** the desktop shell starts
- **THEN** it launches the sidecar on `127.0.0.1` with a random available port
- **AND** receives the selected port and generated bearer token from startup JSON
- **AND** makes that configuration available to the frontend

#### Scenario: Unauthorized request

- **GIVEN** the sidecar has a bearer token
- **WHEN** a non-preflight API request omits or supplies a different token
- **THEN** the sidecar responds with an unauthorized status

### Requirement: Browser-only development mode

The frontend SHALL support operation without a Tauri-provided sidecar by using an explicitly injected API configuration when present and mock fallback data otherwise.

#### Scenario: No sidecar configuration exists

- **GIVEN** the frontend runs in a browser without injected sidecar configuration
- **WHEN** it requests read-only application data
- **THEN** the API adapter returns the corresponding mock fallback data
