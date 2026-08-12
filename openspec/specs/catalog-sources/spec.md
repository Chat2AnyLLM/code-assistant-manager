# Catalog Sources Specification

## Purpose

Define how CAM resolves configuration and combines local and remote catalogs.

## Requirements

### Requirement: Configuration fallback

The system SHALL load repository source configuration from `~/.config/code-agent-manager/config.yaml` when it exists and SHALL otherwise use the bundled configuration in `internal/camconfig/embed/config.yaml`.

#### Scenario: User configuration is absent

- **GIVEN** the user configuration file does not exist
- **WHEN** CAM loads catalog source configuration
- **THEN** it uses the bundled configuration

### Requirement: Catalog source precedence

The system SHALL load catalog sources in configured declaration order and SHALL keep the first definition encountered for a duplicate key. The bundled configuration SHALL place local sources before remote sources so local entries win under the default configuration.

#### Scenario: Earlier and later source keys conflict

- **GIVEN** two configured catalog sources define the same key
- **WHEN** CAM merges the sources in declaration order
- **THEN** the entry from the earlier source remains effective

#### Scenario: Bundled local and remote keys conflict

- **GIVEN** the bundled configuration declares a local source before a remote source
- **AND** both sources define the same key
- **WHEN** CAM merges the sources
- **THEN** the local catalog entry remains effective

### Requirement: Legacy remote JSON catalog caching

The system SHALL cache fetched legacy remote JSON catalog data beneath `~/.cache/code-agent-manager/repos` according to the configured cache lifetime. Source-driven prompt and MCP YAML flows MAY fetch their upstream configuration and referenced files directly.

#### Scenario: Cached legacy JSON data remains valid

- **GIVEN** cached legacy remote JSON catalog data exists within its configured lifetime
- **WHEN** CAM loads the corresponding source
- **THEN** it may use the cached data rather than fetching it again

### Requirement: Source-driven prompt and MCP catalogs

The system SHALL read prompt and MCP catalog source declarations from their upstream configuration and fetch the configured upstream files directly rather than depending on generated distribution artifacts.

#### Scenario: Load an upstream catalog

- **WHEN** CAM resolves a configured prompt or MCP source
- **THEN** it reads the source declarations and fetches the referenced upstream data files
