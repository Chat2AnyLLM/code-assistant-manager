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
