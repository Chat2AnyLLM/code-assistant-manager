## Context

The shared Cobra lifecycle command currently accepts at most one positional argument and passes its complete value to `pickTargets`. That resolver handles only the literal `all`, one registry key, or one CLI command alias, so commas remain part of a failed lookup. The lifecycle implementation is shared by install, upgrade, and uninstall, while this change intentionally modifies only upgrade behavior. See `proposal.md` for motivation and `specs/cam-cli/spec.md` for the observable contract.

## Goals / Non-Goals

*Goals:*
- Parse and validate comma-separated upgrade selectors before entering the existing operation loop.
- Preserve first-occurrence order while deduplicating by canonical registry tool name.
- Keep the existing single-argument Cobra shape so shell quoting and flag behavior remain compatible.
- Keep install and uninstall target selection unchanged.

*Non-Goals:*
- Moving CLI-only input syntax into `internal/tools`.
- Parallelizing installers or changing failure aggregation after operations begin.
- Adding multiple positional target arguments.

## Decisions

1. *Add an upgrade-specific selector resolver in `internal/cli`.* The upgrade branch will call a resolver that splits the one target argument on commas, trims each entry, validates the full list, resolves aliases through the registry, and deduplicates by canonical tool name. Install and uninstall continue through the existing single-target resolver. This avoids silently expanding the public behavior of the other shared lifecycle verbs. The alternative of changing `pickTargets` globally is smaller mechanically but violates the declared non-goal.

2. *Validate first, execute second.* The resolver will build the complete candidate slice or return an error before the command writes an action header or invokes any installer. This provides atomic input validation even though actual upgrades remain sequential and can still fail independently at runtime. Resolving while executing was rejected because a later typo could leave earlier tools upgraded.

3. *Treat `all` as an exclusive selector.* Omitted targets and a sole `all` retain current behavior. Mixing `all` with named tools is rejected rather than silently ignoring names or expanding and deduplicating, which keeps intent unambiguous.

4. *Deduplicate by canonical tool name while preserving input order.* A seen-name set prevents `codex,openai-codex` from running the same installer twice, while the candidate slice retains deterministic user-specified order. Sorting was rejected because it would make execution order differ from the command line.

5. *Expose comma syntax in upgrade help and documentation.* The upgrade command use string will show `[TARGET[,TARGET...]]`; install and uninstall retain `[TARGET]`. Dry-run output continues to echo the original selector and lists canonical resolved names, providing a hermetic way to verify ordering and deduplication.

## Risks / Trade-offs

- [Comma is part of a future valid tool name] → Registry keys and CLI commands already act as simple shell tokens; document comma as reserved upgrade-list syntax.
- [Whitespace around entries requires shell quoting] → Trim entries after splitting and document the compact form used by normal invocations.
- [Sequential runtime failures can still produce partial upgrades] → Keep the existing failure model; atomicity applies to selector validation, not external installer execution.
- [Upgrade diverges slightly from shared lifecycle parsing] → Isolate the difference in a small resolver and retain a common execution loop.

## Migration Plan

No data or configuration migration is required. Deploy the updated binary and documentation. Rollback is a binary rollback; existing single-target and `all` invocations remain compatible in both versions.
