## Context

CAM's canonical instruction path registry already models supported agents and user/project destinations in `internal/entities`, while `internal/instructions` may install those destinations as symlinks or copies. There is no snapshot domain, system-prompt registry, general archive, diff engine, or multi-file filesystem transaction. Native agent settings are unsuitable as an implicit source because they can contain credentials.

The CLI and compatibility binary share `internal/cli`, whose application currently maps ordinary Cobra errors to status 1. Snapshot behavior must remain reusable by future sidecar or desktop adapters without introducing those interfaces now. See `proposal.md` and the capability specs for observable behavior.

## Goals / Non-Goals

**Goals:**

- Centralize discovery, persistence, verification, comparison, and restoration in a shared Go domain package.
- Produce inspectable, deterministic, versioned snapshots with integrity checks.
- Make restore conservative, path-safe, non-following for destination symlinks, rollback-capable, and recoverable after interruption.
- Keep CLI rendering and process exit policy separate from domain results.
- Make time, home/config roots, confirmation, and filesystem failure points testable without changing production behavior.

**Non-Goals:**

- General-purpose backup of agent settings or the workstation.
- Preserving symbolic-link topology: snapshot equality is defined by logical target presence and bytes. Restore materializes a private regular file at a restored link path to avoid writing through an external target.
- Fully atomic multi-file filesystem commits, which are not available across arbitrary filesystems; the design provides complete preflight, durable progress, rollback, and crash recovery instead.
- Snapshot deletion, retention, compression, encryption, import/export, remote sync, or garbage collection in this change.
- Sidecar handlers, React pages, Tauri commands, or database migrations.

## Decisions

### 1. Introduce `internal/snapshots` as the domain boundary

The package exposes a `Service` for create, list, inspect, diff, restore planning, apply, and recovery. Cobra commands parse options and render domain values but contain no path discovery, hashing, or mutation rules.

The data flow is:

```text
cam snapshot command
        |
        v
internal/snapshots.Service
   |          |             |
   v          v             v
asset       filesystem    snapshot store
registry    targets       manifest + objects + journals
   |
   v
internal/entities instruction metadata
```

A future sidecar/desktop change can call the same service. No current sidecar, desktop service, React, or Tauri flow changes.

**Alternative:** implement directly in `internal/cli`. Rejected because restore policy and persistent formats are domain behavior and would be duplicated by another interface.

### 2. Discover logical assets through the existing instruction registry

An asset provider enumerates `entities.InstructionApps` and supported levels, then resolves paths with `entities.InstructionPath`. Selection uses a snapshot-local validated scope type to avoid coupling to the several existing package-specific scope enums. Agents are normalized to the stable `internal/entities` identifiers.

Discovery emits logical owner IDs and concrete targets. A normalization pass groups identical normalized concrete paths so shared `AGENTS.md` targets are read and restored once while retaining all owners. Every requested agent and scope is validated before capture begins.

V1's `kind` is `instruction`; those canonical files are the only verified system-prompt state presently modeled by CAM. The manifest format retains a kind field so future prompt-specific adapters can be added without reinterpreting existing entries.

**Alternative:** infer current state from instruction SQLite install rows or legacy JSON entities. Rejected because both registries are partial and snapshots must reflect actual canonical destinations whether CAM installed them or not.

### 3. Store immutable snapshots as manifests plus content-addressed objects

The store root is `<CAM_CONFIG_DIR>/snapshots`. A published snapshot is a directory whose name is a UTC sortable identifier with a collision-resistant suffix:

```text
snapshots/
  <id>/
    manifest.json
    objects/sha256/<digest>
  .staging-<id>/
  recovery/
    <restore-id>/manifest.json
    <restore-id>/objects/sha256/<digest>
  restore-journal.json
```

The manifest has an integer schema version, ID, optional validated name, UTC creation timestamp, capture selection, optional capture-time project root, and entries sorted by stable key. Entries store owners, kind, scope, a user locator or clean project-relative path, capture-time diagnostic path, presence, content digest/size, captured permission bits, and optional symlink metadata.

Objects contain exact bytes and are written once with `0600`; directories use `0700`. Creation writes and syncs a private staging tree, writes the manifest last, then renames the tree to its final ID. Readers list only valid published directory names and reject staging directories. JSON uses a fixed struct shape and indentation, and all collections are sorted before serialization.

Names are aliases rather than directory keys. Resolution checks exact ID, then unique ID prefix, then unique name and rejects ambiguity.

**Alternative:** store payloads in SQLite. Rejected because snapshots should be portable/inspectable filesystem artifacts, should not depend on the global `--store` database selector, and can contain substantially more data than metadata records.

### 4. Represent logical content, not symlink topology

Capture uses `Lstat` to identify the destination. A regular file is read directly. A symlink is resolved by the operating system only for capture/read and must resolve to a regular readable file; its link text is retained only for diagnostics. Directories, broken links, cycles, sockets, and devices fail capture.

Diff compares target absence and exact bytes. It does not classify a regular file versus a working symlink as drift when their logical bytes match.

Restore never opens a destination for writing through a symlink. It stages a regular file in the destination directory and renames it over the path. Thus a restored symlink becomes an independent regular file and its former target is untouched.

**Alternative:** recreate and mutate symlink targets. Rejected because links may point outside the selected scope, one target may be shared, and restoring through them can unexpectedly modify unrelated installations.

### 5. Use a versioned locator rather than trusting capture-time absolute paths

User entries identify the canonical agent/scope owners and are re-resolved through current path metadata and the current home environment. Project entries carry a slash-separated clean relative path and resolve beneath the selected project root. Diff and restore use an explicit `--project-dir` when present; otherwise they use the capture-time root only if it is still an existing directory.

Before access, resolution rejects absolute project locators, `.`/`..` escapes, NULs, duplicate destinations with conflicting desired states, and any normalized result outside the project root. The capture-time absolute target is informational and never authoritative for writes.

Manifest parsing rejects unknown schema versions, unknown enum values, malformed digests, inconsistent absent entries, unsorted/duplicate owners, and invalid paths before object loading.

**Alternative:** restore directly to recorded absolute paths. Rejected because it is unsafe, prevents checkout portability, and could write into a different user's home.

### 6. Separate exact hashing from presentation diffs

Drift is determined with target state, byte length, and SHA-256. Results are sorted by scope, locator, and owners and classified as unchanged, added, missing, changed, unreadable, or unsupported.

For changed content, text rendering uses a unified line diff when both object and current content are valid UTF-8 and contain no NUL. Binary content receives digest/size metadata only. JSON rendering serializes domain result structs and does not include terminal decoration. A small established diff package may be used solely for rendering; hashing remains the behavioral authority.

**Alternative:** normalize line endings before comparison. Rejected because restore promises exact content and normalization would hide drift.

### 7. Add typed process exit errors at the application boundary

`internal/cli` gains an error wrapper carrying a process status. `App.Run` uses `errors.As` to return that status while printing the underlying message only when present. Snapshot diff renders a successful drift result and then returns a silent status-1 error. Snapshot diff wraps operational failures as status 2. Existing commands retain status 1 for ordinary errors.

This avoids calling `os.Exit` inside command handlers and keeps both binaries consistent.

**Alternative:** treat drift as an ordinary error. Rejected because it would add misleading error text and could not distinguish expected drift from failure in scripts.

### 8. Make restore a plan followed by a journaled apply

Planning performs recovery detection, manifest and object verification, target resolution, current-state reads, collision checks, action construction, and staging feasibility checks without mutation. Actions are `replace`, `remove`, or conservative `preserve-extra`; unchanged entries are reported but not actionable. Dry-run returns this plan and creates no recovery data.

After authorization, apply:

1. acquires an exclusive store-level lock;
2. re-runs recovery and verifies the plan's current-state digests to reject races;
3. writes a recovery manifest and content objects for every target to be changed, including absence and symlink diagnostics;
4. creates and syncs the journal before the first mutation;
5. stages each replacement as a `0600` sibling temporary file, syncing file and parent as supported;
6. applies one action at a time with rename or unlink and durably advances the journal;
7. marks completion only after all parent directories are synced.

On failure it walks applied actions in reverse, restoring recovery bytes through the same non-following staged replacement or restoring absence, and records rollback progress. Complete rollback removes the active journal but retains the recovery snapshot as an audit/recovery artifact. Incomplete rollback retains both and blocks create/restore mutation.

At service startup for mutating operations, an unfinished journal invokes the same rollback routine. Read-only list/show/diff may proceed only when their requested snapshot can be read safely, but they report the outstanding recovery condition; create and restore cannot proceed until recovery completes.

A filesystem abstraction is limited to mutation primitives needed to inject deterministic failures in tests; ordinary reads can remain standard library operations.

**Alternative:** make an automatic normal snapshot before restore. Rejected as the sole mechanism because normal discovery may include unaffected targets and cannot express exact low-level preimages or partial progress. Recovery uses the same object format but has a restore-specific manifest and journal.

### 9. Keep confirmation in the CLI adapter

The domain returns a plan and accepts only an already-authorized apply request. The CLI checks whether actions exist. `--dry-run` renders and returns. `--yes` authorizes. Otherwise the CLI prompts only if stdin and stderr/out context indicate an interactive terminal; it accepts an explicit `y` or `yes` and treats other input as cancellation. Non-interactive input fails with guidance to use `--yes` or `--dry-run`.

This keeps policy visible at the outward-facing boundary and prevents the shared service from depending on terminals.

**Alternative:** silently proceed when stdin is unavailable. Rejected because restore and exact deletion are destructive outward-facing operations.

### 10. No catalog or database precedence changes

Snapshots use the existing instruction registry's effective compiled metadata and `pathutil.ConfigDir`. They neither read catalog repository sources nor change first-definition-wins behavior. No SQLite state or migrations are introduced.

## Risks / Trade-offs

- **[A restore cannot be globally atomic across filesystems]** → Validate the full set first, journal every step, retain preimages, roll back in reverse, and recover unfinished work on the next mutation.
- **[A process can be killed between a filesystem mutation and journal advancement]** → Journal each action's pre-state and inspect both destination and preimage during idempotent recovery rather than assuming the recorded cursor is exact.
- **[Replacing a symlink changes topology]** → Document logical-content semantics, retain link diagnostics, render link replacement in the plan, and never risk mutating an external target.
- **[Instruction files may contain sensitive internal text]** → Restrict directory/file permissions, exclude settings and credentials by construction, and avoid including content in list/show output unless explicitly requested by diff.
- **[Snapshot format becomes a compatibility promise]** → Version the manifest from the first release, validate strictly, sort deterministically, and reject rather than guess at unknown versions.
- **[Unified diffs can be large]** → Keep structured drift metadata authoritative and bound textual diff rendering with a clear truncation marker if necessary; object integrity remains unaffected.
- **[Current instruction registries use overlapping agent identities elsewhere]** → Use only canonical `internal/entities` IDs in V1 and require explicit adapter mappings for future asset providers.

## Migration Plan

1. Add the new domain and CLI command without changing existing instruction installation or stored state.
2. Existing installations need no migration; the snapshot root is created lazily on first creation or restore recovery.
3. Rollback consists of removing the new command registration and package. Existing snapshot directories remain inert user data and can be read by the same released version if the binary is restored.
4. Do not delete snapshot or recovery data automatically during uninstall in this change.
