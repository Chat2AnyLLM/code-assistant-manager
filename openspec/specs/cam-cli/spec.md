# CAM CLI Specification

## Purpose

Define the public behavior of the Code Assistant Manager command-line interface.

## Requirements

### Requirement: Unified command entry point

The system SHALL expose the `cam` command as the primary entry point for managing supported coding assistants and SHALL preserve `code-agent-manager` as a compatibility binary backed by the same application logic.

#### Scenario: Invoke a management command

- **GIVEN** a supported CAM management command
- **WHEN** a user invokes it through `cam`
- **THEN** the Cobra application in the shared CLI package handles the command

#### Scenario: Invoke the compatibility binary

- **GIVEN** the compatibility binary is installed
- **WHEN** a user invokes `code-agent-manager`
- **THEN** it executes the same CLI application behavior as `cam`

### Requirement: Supported command families

The CLI SHALL provide command families for launch and apply workflows, diagnostics and configuration, providers, agents, instructions, skills, plugins, MCP servers, metadata, extensions, lifecycle operations, completion, and version reporting.

#### Scenario: Request root help

- **WHEN** a user requests root command help
- **THEN** the available command families and aliases are displayed

### Requirement: Canonical option naming

The CLI SHALL use long-form option names as the canonical form in documentation and new interfaces while preserving existing shorthand compatibility.

#### Scenario: Document a value option

- **GIVEN** an option accepts a value such as a config path or scope
- **WHEN** it is documented for users
- **THEN** the documentation uses its long name such as `--config` or `--scope`

### Requirement: Upgrade target selection

The CLI SHALL allow `cam upgrade` to select one tool, all enabled tools, or multiple tools expressed as a comma-separated list in the single optional target argument. Each selected tool SHALL be resolved from either its registry key or CLI command alias and SHALL be upgraded at most once in the order of first occurrence.

#### Scenario: Upgrade multiple aliases

- **WHEN** a user runs `cam upgrade codex,claude`
- **THEN** the CLI upgrades the tools resolved from `codex` and `claude` in that order

#### Scenario: Deduplicate resolved tools

- **WHEN** a user names the same tool more than once using a registry key, a CLI command alias, or both
- **THEN** the CLI includes that tool once at its first position in the target list

#### Scenario: Preserve single-target behavior

- **WHEN** a user supplies one valid registry key or CLI command alias
- **THEN** the CLI upgrades that one resolved tool

#### Scenario: Preserve default and all-target behavior

- **WHEN** a user omits the target argument or supplies `all` as the sole target
- **THEN** the CLI upgrades every enabled tool

### Requirement: Upgrade target list validation

The CLI MUST validate the complete comma-separated upgrade target list before starting any upgrade operation. Every list entry MUST be non-empty and resolve to a known tool, and the reserved `all` selector MUST be used alone.

#### Scenario: Reject an unknown target atomically

- **WHEN** a comma-separated target list contains an unknown tool
- **THEN** the command fails with an error identifying that target and performs no upgrade operations

#### Scenario: Reject an empty target

- **WHEN** a comma-separated target list contains an empty entry
- **THEN** the command fails with an invalid target list error and performs no upgrade operations

#### Scenario: Reject all mixed with named targets

- **WHEN** a target list combines `all` with one or more named tools
- **THEN** the command fails with an invalid target list error and performs no upgrade operations
