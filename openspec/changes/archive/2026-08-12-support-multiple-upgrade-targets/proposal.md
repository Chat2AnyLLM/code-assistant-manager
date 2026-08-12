## Why

`cam upgrade` currently treats a comma-separated target list as one tool name, so a request such as `cam upgrade codex,claude` fails with `Unknown target: codex,claude`. Users need to upgrade a selected group of coding assistants in one invocation without upgrading every enabled tool.

## What Changes

- Accept a comma-separated list of tool keys or CLI command aliases in the optional `cam upgrade [TARGET]` argument.
- Resolve each requested target in input order, deduplicate tools that are named more than once or through multiple aliases, and upgrade each resolved tool once.
- Validate the complete target list before running any upgrade so an unknown or empty target cannot cause a partial operation.
- Preserve the existing single-target, `all`, alias, dry-run, and verbose behavior.
- Update CLI help and user documentation with the multi-target syntax.
- Non-goals: changing install or uninstall semantics, adding parallel execution, or changing the desktop, sidecar, Tauri, frontend, or shared installer behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `cam-cli`: Define comma-separated multi-target selection and validation for the upgrade command.

## Impact

The public Go CLI interface and its tests under `internal/cli` are affected, along with CLI documentation in `README.md`. The target selection remains in the CLI adapter; `internal/tools` continues to provide registry lookup and installation primitives without API or dependency changes. No HTTP API, desktop UI, persisted state, or external integration changes are required.
