## 1. Regression Tests

- [x] 1.1 Add upgrade command tests for ordered comma-separated alias resolution and canonical target output.
- [x] 1.2 Add upgrade command tests for canonical deduplication, unknown and empty target rejection, exclusive `all`, and updated help syntax.

## 2. CLI Implementation

- [x] 2.1 Implement upgrade-only comma-separated target parsing with complete pre-execution validation, alias resolution, input-order preservation, and canonical deduplication.
- [x] 2.2 Update the upgrade command usage string while preserving install and uninstall single-target behavior.

## 3. Documentation

- [x] 3.1 Document single, comma-separated, and all-target upgrade examples in the primary README command reference.

## 4. Verification

- [x] 4.1 Run formatting and focused lifecycle command tests, including upgrade, install, and uninstall regressions.
- [x] 4.2 Run the applicable security scan and the complete repository quality gate.
- [x] 4.3 Validate all OpenSpec artifacts strictly and reinstall CAM using the repository installation workflow.
