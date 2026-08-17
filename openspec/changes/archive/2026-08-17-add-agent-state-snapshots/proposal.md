## Why

CAM can install coding-agent instructions but cannot capture their current state before an upgrade or experiment, detect later drift, or safely return the files to a known point in time. Users need a local, inspectable recovery mechanism for agent instruction and verified prompt files without copying credentials or unrelated native settings.

## What Changes

- Add a `cam snapshot` CLI command family with `create`, `list`, `show`, `diff`, and `restore` operations.
- Capture canonical user-scope instruction targets for supported agents and, when explicitly requested, the targets for one project directory.
- Persist versioned deterministic manifests and content-addressed objects under CAM's configuration directory, including explicit records for targets that were absent at capture time.
- Compare a snapshot with live targets using byte-exact content hashes and render human-readable unified diffs or structured JSON.
- Restore through complete preflight validation, dry-run planning, interactive confirmation or `--yes`, recovery data, a durable journal, rollback on failure, checksum validation, and conservative symlink/path protections.
- Support an explicit exact restore mode for removing targets that were absent in the snapshot; conservative restore leaves such live files untouched by default.
- Define distinct diff exit statuses for no drift, drift, and operational failure.
- Treat the canonical instruction files as the verified prompt state in the first release. Whole native settings, credentials, MCP configuration, histories, caches, installed binaries, CAM databases, cloud synchronization, and the desktop/sidecar UI are explicit non-goals.

## Capabilities

### New Capabilities
- `agent-state-snapshots`: Capture, inspect, compare, and safely restore coding-agent instruction and verified prompt-file state.

### Modified Capabilities
- `cam-cli`: Expose the snapshot command family, machine-readable output, project/scope selectors, confirmation behavior, and scriptable exit statuses.

## Impact

- **CLI interface:** `internal/cli` gains the `cam snapshot` command family and reusable typed exit-status handling.
- **Shared domain:** a new `internal/snapshots` package owns discovery, storage, integrity verification, diff calculation, restore planning, journaling, rollback, and recovery; it reuses canonical instruction path metadata from `internal/entities` and CAM configuration paths from `internal/pathutil`.
- **Persistent files:** snapshots are stored below CAM's configuration directory with restrictive permissions; no new SQLite schema is required.
- **Dependencies:** a Go unified-diff implementation may be added if the standard library cannot provide the required rendering.
- **Cross-layer non-goals:** this change does not add sidecar endpoints, desktop/Tauri UI, frontend behavior, or snapshot transport/synchronization. The shared package remains reusable for those interfaces in a future change.
