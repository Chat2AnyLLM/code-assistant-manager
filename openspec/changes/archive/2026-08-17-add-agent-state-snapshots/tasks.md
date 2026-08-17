## 1. Snapshot Model and Discovery

- [x] 1.1 Add the versioned snapshot, manifest entry, selection, drift, restore plan, recovery, and journal domain types with strict validation and deterministic ordering.
- [x] 1.2 Implement canonical agent/scope selection and target discovery through `internal/entities`, including project validation, agent validation, target deduplication, safe locators, and present/absent/symlink capture.
- [x] 1.3 Add focused discovery and model tests for invalid selectors, shared targets, missing files, supported links, unsupported nodes, and project path safety.

## 2. Snapshot Persistence and Inspection

- [x] 2.1 Implement the private filesystem snapshot store under CAM's configuration directory, including unique IDs, names, staging publication, deterministic manifests, content-addressed SHA-256 objects, and reference resolution.
- [x] 2.2 Implement snapshot list and show operations with full manifest and object integrity verification.
- [x] 2.3 Add focused store tests for permissions, deterministic ordering, incomplete staging, ambiguous references, unsupported versions, malformed manifests, traversal attempts, and corrupted objects.

## 3. Drift Detection

- [x] 3.1 Implement portable user/project target resolution and byte-exact drift classification for unchanged, added, missing, changed, unreadable, and unsupported states.
- [x] 3.2 Implement deterministic text and JSON representations, including unified UTF-8 text diffs and binary-content summaries.
- [x] 3.3 Add focused diff tests for every classification, line-ending differences, text patches, binary content, project rebasing, unavailable captured projects, and escaped destinations.

## 4. Recoverable Restore

- [x] 4.1 Implement full restore preflight and deterministic plans for replacement, exact removal, conservative preservation, unchanged targets, symlink replacement, and current-state race tokens.
- [x] 4.2 Implement private recovery preimages, durable journal writes, same-directory staged replacements, progress recording, reverse rollback, and idempotent interrupted-restore recovery.
- [x] 4.3 Add focused restore tests for dry-run purity, conservative versus exact behavior, non-following symlink replacement, current-state races, apply failures, successful rollback, failed rollback retention, and next-command recovery.

## 5. CLI Integration

- [x] 5.1 Add typed CLI process-status errors while preserving status 1 for existing ordinary command failures.
- [x] 5.2 Register `cam snapshot` with create, list, show, diff, and restore subcommands and canonical long-form selection/output flags.
- [x] 5.3 Implement human-readable and JSON rendering, diff statuses 0/1/2, restore dry-run, terminal confirmation, `--yes`, `--exact`, and non-interactive refusal.
- [x] 5.4 Add focused CLI tests for command help, flag validation, JSON output, selectors, exit statuses, dry-run, confirmation, cancellation, automation consent, integrity rejection, and both shared binaries' application path.

## 6. Validation and Installation

- [x] 6.1 Run `find` to enumerate applicable Go test files and execute the snapshot domain and CLI test files one by one.
- [x] 6.2 Run formatting, static checks, the complete Go suite, and the repository's full relevant `make check` quality gate.
- [x] 6.3 Run `openspec validate --all --strict --no-interactive` and address every validation issue.
- [x] 6.4 Clean `dist`, uninstall the existing CAM installation, and reinstall with `./install.sh` after all repository checks pass.
