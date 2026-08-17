# Agent State Snapshots Specification

## Purpose

Provide local, integrity-checked snapshots of coding-agent instruction and verified prompt-file state so users can inspect drift and safely recover known content.

## Requirements

### Requirement: Snapshot selection and capture
The system SHALL create a snapshot of canonical instruction-file targets for all supported agents by default and SHALL allow repeated agent selectors to restrict the capture. The default scope SHALL be user scope; project scope SHALL require one explicit existing project directory. The system SHALL validate the complete selection before persisting a snapshot and SHALL deduplicate concrete paths while retaining every logical agent owner.

#### Scenario: Capture default user state
- **WHEN** a user creates a snapshot without scope, project, or agent selectors
- **THEN** the snapshot records every supported user-scope instruction target

#### Scenario: Capture one project
- **WHEN** a user creates a snapshot with project scope and an existing project directory
- **THEN** the snapshot records canonical project-scope targets relative to that project

#### Scenario: Reject incomplete project selection
- **WHEN** a user selects project scope without an existing project directory
- **THEN** snapshot creation fails before any snapshot artifact is persisted

#### Scenario: Reject an unknown agent atomically
- **WHEN** any requested agent identifier is unsupported
- **THEN** snapshot creation identifies the invalid agent and persists no partial snapshot

#### Scenario: Deduplicate a shared target
- **WHEN** two selected logical agent assets resolve to the same concrete file
- **THEN** the snapshot stores that target content once and records both logical owners

### Requirement: Explicit present and absent state
A snapshot SHALL distinguish a present regular file, a present symbolic-link destination, and an absent target. For a symbolic-link destination, capture and comparison SHALL use the linked file's bytes while recording link metadata for diagnostics. Snapshot scope SHALL include only canonical instruction and verified prompt-file targets and MUST exclude whole native settings, credentials, MCP configuration, histories, caches, binaries, and CAM databases.

#### Scenario: Record an absent target
- **WHEN** a canonical target does not exist at capture time
- **THEN** the manifest records the target as absent without creating an empty content object

#### Scenario: Capture linked instruction content
- **WHEN** a canonical instruction target is a symbolic link to a readable regular file
- **THEN** the snapshot records the linked file's exact bytes and diagnostic link metadata

#### Scenario: Reject an unsafe or unsupported source
- **WHEN** a selected target is a directory, a broken link, a link cycle, or another unsupported node type
- **THEN** snapshot creation fails before publishing the snapshot

#### Scenario: Exclude native settings
- **WHEN** an agent's native settings file contains credentials or unrelated configuration
- **THEN** that file is not discovered or persisted by the snapshot operation

### Requirement: Durable versioned snapshot storage
The system SHALL store snapshots beneath CAM's configuration directory using a unique immutable identifier, a schema-versioned deterministic manifest, and SHA-256 content-addressed objects. Snapshot directories MUST be private to the current user, creation SHALL publish a snapshot only after all files are durable, and readers SHALL reject unsupported versions, malformed manifests, path traversal, or content whose size or digest does not match the manifest.

#### Scenario: Create a named snapshot
- **WHEN** a user supplies a valid human-readable name
- **THEN** the system stores it as lookup metadata while retaining a separate unique immutable identifier

#### Scenario: Resolve a snapshot reference
- **WHEN** a user supplies a unique snapshot identifier, unambiguous identifier prefix, or unique name
- **THEN** the system resolves that reference to the matching snapshot

#### Scenario: Reject an ambiguous reference
- **WHEN** a name or identifier prefix matches multiple snapshots
- **THEN** the operation fails and identifies the ambiguity

#### Scenario: Detect corrupted content
- **WHEN** a referenced content object does not match its recorded size or SHA-256 digest
- **THEN** show, diff, and restore reject the snapshot without modifying live state

#### Scenario: Ignore incomplete creation
- **WHEN** snapshot creation is interrupted before publication
- **THEN** the incomplete staging data is not listed as a usable snapshot

### Requirement: Snapshot inspection
The system SHALL list snapshots in reverse creation order and SHALL show one snapshot's identity, name, capture time, selection, project metadata, entries, and integrity state. Inspection SHALL support human-readable text and stable JSON output.

#### Scenario: List snapshots
- **WHEN** a user lists snapshots
- **THEN** the system displays each published snapshot in reverse creation order

#### Scenario: Show structured metadata
- **WHEN** a user shows a snapshot with JSON output
- **THEN** the system emits valid JSON containing the versioned manifest and integrity result

### Requirement: Drift detection
The system SHALL compare each snapshot entry with its current resolved target using byte-exact content semantics and SHALL classify unchanged, added, missing, changed, unreadable, and unsupported current state. Text output SHALL provide a deterministic summary and unified line diff for changed UTF-8 text, while JSON output SHALL expose stable machine-readable entries. Binary or invalid UTF-8 content SHALL be reported without attempting a textual patch.

#### Scenario: No drift
- **WHEN** every current target has the same presence and exact bytes as the snapshot
- **THEN** diff reports no drift

#### Scenario: Changed text
- **WHEN** a present UTF-8 target has different bytes
- **THEN** diff classifies it as changed and text output includes a unified line diff

#### Scenario: Target added after an absent snapshot state
- **WHEN** a target recorded absent is now present
- **THEN** diff classifies it as added

#### Scenario: Snapshot target is now missing
- **WHEN** a target recorded present is now absent
- **THEN** diff classifies it as missing

#### Scenario: Current target is unreadable
- **WHEN** the current target cannot be read
- **THEN** diff classifies it as unreadable and does not treat the error as unchanged state

### Requirement: Portable project target resolution
User targets SHALL resolve from the current user's home environment. Project entries SHALL store project-relative destinations and SHALL resolve against an explicitly supplied restore or diff project directory when provided, otherwise against the capture-time project directory only while that directory remains valid. Resolved destinations MUST remain beneath the selected project root.

#### Scenario: Compare another checkout
- **WHEN** a project snapshot is diffed with a different explicit project directory
- **THEN** project-relative entries resolve beneath that supplied directory

#### Scenario: Reject project path escape
- **WHEN** manifest data would resolve a project entry outside the selected project root
- **THEN** the operation rejects the snapshot before reading or writing the escaped destination

#### Scenario: Captured project is unavailable
- **WHEN** no project directory is supplied and the capture-time project directory no longer exists
- **THEN** the operation fails with guidance to supply a project directory

### Requirement: Restore planning and confirmation
Restore SHALL verify the entire snapshot and resolve and validate every selected destination before changing live state. It SHALL support a dry-run plan that performs no writes. A non-dry-run restore SHALL require interactive confirmation on a terminal unless `--yes` is supplied, and SHALL fail rather than assume consent when input is non-interactive.

#### Scenario: Preview restore
- **WHEN** a user invokes restore with dry-run enabled
- **THEN** the system displays the complete planned actions and modifies no live target or recovery state

#### Scenario: Confirm interactively
- **WHEN** a restore would change live state in an interactive terminal and `--yes` is absent
- **THEN** the system applies the restore only after explicit affirmative confirmation

#### Scenario: Require automation consent
- **WHEN** a restore would change live state from non-interactive input and neither dry-run nor `--yes` is supplied
- **THEN** the command fails without modifying live state

#### Scenario: No-op restore
- **WHEN** live state already matches all actions requested by restore
- **THEN** restore reports no changes and does not require confirmation

### Requirement: Conservative and exact restore semantics
A conservative restore SHALL recreate or replace targets recorded present but SHALL leave a currently present target untouched when the snapshot recorded it absent. Exact restore SHALL remove those extra targets only when explicitly requested. Restore MUST NOT follow a destination symbolic link while writing; restoring content through a symbolic-link path SHALL atomically replace the link itself with a private regular file so an external link target is not modified.

#### Scenario: Restore changed content
- **WHEN** a target recorded present has drifted and restore is authorized
- **THEN** the destination is atomically replaced with the snapshot's exact bytes

#### Scenario: Preserve an added file by default
- **WHEN** a target was absent in the snapshot but is present during conservative restore
- **THEN** restore reports the extra target and leaves it untouched

#### Scenario: Remove an added file exactly
- **WHEN** a target was absent in the snapshot, is currently present, and exact restore is explicitly authorized
- **THEN** restore removes that target as part of the recoverable restore transaction

#### Scenario: Replace a destination link safely
- **WHEN** a destination to restore is currently a symbolic link
- **THEN** restore replaces the link path without writing through to the link target

### Requirement: Recoverable multi-file restore
Before the first live mutation, the system SHALL persist a private recovery record containing preimages for every affected destination and a durable restore journal. It SHALL stage replacement files beside their destinations, record progress durably, roll back already-applied actions when an operation fails, and retain sufficient data to recover after process interruption. A later snapshot command MUST detect an unfinished journal and refuse unrelated mutation until recovery completes successfully.

#### Scenario: Roll back an apply failure
- **WHEN** any restore action fails after earlier actions were applied
- **THEN** the system attempts to restore every affected destination to its pre-restore state and reports both the original and any rollback errors

#### Scenario: Detect an interrupted restore
- **WHEN** a snapshot command starts while a restore journal is unfinished
- **THEN** the system attempts deterministic recovery before allowing create or restore to mutate state

#### Scenario: Preserve recovery data after failed rollback
- **WHEN** automatic recovery cannot completely restore preimages
- **THEN** the system retains the journal and recovery objects and reports their location for manual recovery

#### Scenario: Complete successful restore
- **WHEN** all planned actions are applied and durably recorded
- **THEN** the journal is marked complete and live targets contain the requested snapshot state
