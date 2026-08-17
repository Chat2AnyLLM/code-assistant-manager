## MODIFIED Requirements

### Requirement: Supported command families

The CLI SHALL provide command families for launch and apply workflows, diagnostics and configuration, providers, agents, instructions, skills, plugins, MCP servers, metadata, extensions, snapshots, lifecycle operations, completion, and version reporting. The snapshot command family SHALL expose `create`, `list`, `show`, `diff`, and `restore` subcommands through both CLI binaries.

#### Scenario: Request root help

- **WHEN** a user requests root command help
- **THEN** the available command families and aliases, including snapshots, are displayed

#### Scenario: Request snapshot help

- **WHEN** a user requests `cam snapshot --help`
- **THEN** the CLI displays the create, list, show, diff, and restore operations

## ADDED Requirements

### Requirement: Snapshot scope and selector options
The snapshot CLI SHALL use long-form `--scope`, `--project-dir`, `--agent`, `--name`, and `--format` options as its canonical interface. `--agent` SHALL be repeatable, scope values SHALL be `user`, `project`, or `all`, and project or all scope SHALL require `--project-dir`.

#### Scenario: Select two agents
- **WHEN** a user creates a snapshot with `--agent claude --agent cursor`
- **THEN** only canonical targets owned by those agents are selected

#### Scenario: Select all scopes
- **WHEN** a user creates a snapshot with `--scope all --project-dir .`
- **THEN** both user targets and targets for the normalized project directory are selected

#### Scenario: Reject an invalid scope
- **WHEN** a user supplies a scope other than user, project, or all
- **THEN** the command fails before snapshot discovery or persistence

### Requirement: Snapshot command output formats
Snapshot list, show, diff, and restore planning SHALL provide human-readable text by default and SHALL accept `--format json` for stable machine-readable output. Unsupported format values MUST fail before performing mutations.

#### Scenario: Request JSON diff
- **WHEN** a user runs snapshot diff with `--format json`
- **THEN** standard output contains one valid JSON result and no human-only decorations

#### Scenario: Reject unsupported output format
- **WHEN** a user supplies an unsupported format to restore
- **THEN** restore fails before confirmation or live-state mutation

### Requirement: Scriptable snapshot diff status
The CLI SHALL exit with status 0 when snapshot diff finds no drift, status 1 when it successfully finds drift, and status 2 when the diff cannot be completed because of invalid input, corruption, target access, or another operational error.

#### Scenario: Diff is clean
- **WHEN** snapshot diff completes and finds no drift
- **THEN** the process exits with status 0

#### Scenario: Diff finds drift
- **WHEN** snapshot diff completes and finds one or more drift entries
- **THEN** the process renders the result and exits with status 1

#### Scenario: Diff encounters an operational failure
- **WHEN** snapshot diff cannot load, verify, resolve, or compare the requested snapshot
- **THEN** the process reports the error and exits with status 2

### Requirement: Explicit restore authorization options
The restore CLI SHALL expose `--dry-run`, `--yes`, and `--exact`. It SHALL accept an optional `--project-dir` for portable project snapshots and SHALL not expose a force option that bypasses integrity or path-safety validation.

#### Scenario: Automate an exact restore
- **WHEN** a user invokes restore with `--exact --yes`
- **THEN** the CLI may apply both replacement and deletion actions without interactive confirmation after all validations pass

#### Scenario: Integrity checks cannot be bypassed
- **WHEN** a snapshot is corrupt and the user supplies all restore authorization options
- **THEN** restore still fails before changing live state
