# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

CAM is a Go application that manages configuration and launch workflows for multiple AI coding assistants. It has two interfaces over shared Go services:

- The Cobra CLI enters through `cmd/cam` (with `cmd/code-agent-manager` as the compatibility binary) and registers commands in `internal/cli`.
- The desktop app is React/Vite inside a Tauri shell. Tauri starts the authenticated localhost Go sidecar from `cmd/cam-sidecar`; `internal/sidecar` maps HTTP endpoints to services in `internal/desktop`, which delegate to the same domain packages used by the CLI.

Core domain packages under `internal/` own providers and SQLite state, tool installation/config writing, instructions and other entities, MCP management, diagnostics, and source-backed metadata. Keep business logic in these shared packages rather than duplicating it in CLI handlers, HTTP handlers, or React components.

The frontend API adapter in `frontend/src/services/api.ts` discovers the sidecar configuration from Tauri or environment injection, attaches its bearer token, and uses mock data when running browser-only. `frontend/src/App.tsx` provides local page navigation rather than a router.

Entity repository catalogs and the MCP catalog use `~/.config/code-agent-manager/config.yaml`, falling back to `internal/camconfig/embed/config.yaml`. Catalog sources are merged in declaration order and the first definition of a key wins; keep local sources before remote sources when local entries must take precedence. Legacy remote JSON catalogs use the cache under `~/.cache/code-agent-manager/repos`; source-driven MCP YAML flows fetch their upstream configuration and referenced files directly. The separate prompt-library sync in `internal/prompts` does not consume `repositories.prompts`: it normally fetches the built-in `awesome-prompts` configuration directly, with `CAM_AWESOME_PROMPTS_URL` available as a direct-JSON override.

## OpenSpec workflow

This repository uses OpenSpec under `openspec/` with the `spec-driven` schema.

- Start a change with `/opsx:propose`.
- Implement an approved change with `/opsx:apply`.
- Sync delta specs with `/opsx:sync` and archive completed work with `/opsx:archive`.
- Explore requirements without implementing code with `/opsx:explore`; it may create OpenSpec artifacts when requested.
- Run `openspec validate --all --strict --no-interactive` before finishing OpenSpec work.

Treat `openspec/specs/` as the current behavioral source of truth. Feature work belongs in `openspec/changes/<change-name>/` until archived.

## Commands

Go 1.26.2 or newer is required. Frontend commands use the locked dependencies in `frontend/package-lock.json`; Tauri checks require Cargo.

```bash
# Build and install
make build                 # CLI binaries and sidecar in dist/
make desktop-build         # frontend build, sidecar build, cargo check
make install

# Run during development
make start                 # full Tauri desktop app; aliases: make app, make dev
make frontend              # browser-only Vite UI on 127.0.0.1:5173
make sidecar               # localhost Go API on a random port

# Formatting and static checks
make fmt                   # writes gofmt -s changes under cmd/ and internal/
make fmt-check
make vet

# Test suites
make test                  # go test ./...
make test-race             # Go race detector
npm --prefix frontend run test:run
npm --prefix frontend run test:coverage
npm --prefix frontend run test:e2e
make check                 # complete Go, frontend, sidecar, and Cargo gate

# Focused tests
go test ./internal/tools -run '^TestPlan_PlaceholderSubstitution$' -v
npm --prefix frontend run test:run -- src/pages/MCP.test.tsx
npm --prefix frontend run test:run -- src/pages/MCP.test.tsx -t 'installs a server to the selected clients'
npm --prefix frontend run test:e2e -- tests/e2e/smoke.spec.ts
```

Before finishing a change to executable code, use `find` to enumerate applicable test files and run them one by one. Documentation- or configuration-only changes do not require the language test suites unless they affect build or runtime behavior. Then run the complete relevant quality gate (`make check` for cross-layer changes).

After any repository changes, reinstall with:

```bash
rm -rf dist/*
./install.sh uninstall
./install.sh
```

## Repository rules

- Ask for approval before any git commit or push.
- Never add a `Co-Authored-By: Claude <noreply@anthropic.com>` trailer.
- Never commit credentials, keys, or `.env` files.
- Use long-form CLI option names in documentation and new interfaces (for example, `--config` and `--scope`); preserve existing shorthand compatibility.
- Follow the concise, maintainable style required by `.github/copilot-instructions.md` and match surrounding code.
