# Go MCP Standards (`GO-*`)

Applies to MCP servers written in Go. Built on top of `mcp.md`.

## Project layout

### GO-001 — Layout: `cmd/<binary>/` and `internal/` [MUST]

**Rationale.** Standard Go layout. `cmd/` for entry points, `internal/` for implementation private to this module.

**Mechanical check.** Both directories exist. `cmd/` contains at least one subdirectory with a `main.go`.

### GO-002 — `go.mod` declares Go ≥ 1.22 [MUST]

**Mechanical check.** `go.mod` `go` directive is `1.22` or higher.

### GO-003 — `go.sum` committed [MUST]

**Mechanical check.** File exists at repo root.

## Tooling

### GO-004 — `.golangci.yml` configured [MUST]

**Rationale.** Consistent lint config across repos.

**Mechanical check.** File exists; enables at least: `errcheck`, `govet`, `staticcheck`, `unused`, `gocritic`.

### GO-005 — `goimports`/`gofmt` enforced via CI [MUST]

**Mechanical check.** `.github/workflows/ci.yml` runs `gofmt -d` or `goimports -d` and fails on output.

## Tests

### GO-006 — Tests use table-driven pattern [SHOULD]

**Rationale.** Project preference; matches global Go style guide.

**Mechanical check.** At least 50% of `*_test.go` files contain the pattern `tests := []struct {` or `tt := []struct {`.

### GO-007 — `go test ./... -race -count=1` runs in CI [MUST]

**Mechanical check.** `.github/workflows/ci.yml` contains `-race` flag in test invocation.

### GO-008 — Integration tests in separate top-level directory or build tag [SHOULD]

**Mechanical check.** Either `integration/` directory at repo root OR `*_test.go` files use `//go:build integration` tag.

## Idioms

### GO-009 — Errors wrapped with `fmt.Errorf("op: %w", err)` [MUST]

**Mechanical check.** No raw `return err` after a non-trivial operation in non-test code; verifier looks for `fmt.Errorf(`...`%w`...`)` or named-error wrapping in error-returning functions.

### GO-010 — `context.Context` is the first parameter of API-facing funcs [MUST]

**Mechanical check.** Every exported function in `internal/` whose name suggests I/O (`Get*`, `List*`, `Create*`, `Update*`, `Delete*`, `Send*`, `Fetch*`) takes `context.Context` as its first non-receiver parameter.

### GO-011 — No `init()` with non-trivial logic [MUST]

**Rationale.** init() runs at import time and is hard to test.

**Mechanical check.** Each `init()` function in non-test code is ≤ 3 statements OR contains only `register()` / `flag.Var()` / similar registry calls.

### GO-012 — Use `mark3labs/mcp-go` SDK [MUST]

**Rationale.** Sole well-maintained Go MCP SDK.

**Mechanical check.** `go.mod` requires `github.com/mark3labs/mcp-go`.

### GO-013 — `errgroup.Group` for parallel fan-out work [SHOULD]

**Mechanical check.** Files using goroutines also import `golang.org/x/sync/errgroup`, OR explicit comment justifies bare goroutine.

### GO-014 — No `panic` in library packages [MUST]

**Mechanical check.** No `panic(` calls in `internal/**/*.go` excluding `*_test.go`.

### GO-015 — Logging via `slog` or `zerolog` [SHOULD]

**Mechanical check.** Source imports `log/slog` or `github.com/rs/zerolog`. Source does NOT import the standard `log` package.
