# Design: MCP server deployment scheme (archetypes + S4 rules)

**Date:** 2026-06-10
**Status:** Approved design, pending implementation plan
**Scope:** A workspace-wide deployment standard for MCP servers, declared per
repo as one of three archetypes and enforced by `consistency-check` through
archetype-conditional rules at `min_stage = S4`. Companion to the maturity
ladder (`2026-06-01-mcp-maturity-ladder-design.md`), which defines S4 only as
"deployment model wired plus a release pipeline and versioned releases" and
leaves the deployment model itself unspecified.

## Problem

The standards cover transport behavior (PROTO-008 stdio default, PROTO-013
stdout reserved) and a MAY-tier release rule (MCP-018), but there is no
canonical definition of what a *deployed* MCP server ships. The six servers
have diverged: `unraid-mcp` grew a Dockerfile, `shortcut-mcp` grew an `mcpb/`
bundle and invented its own S3→S4 gate ("MCP-registry submission") in its
README, and the rest are source-only stdio. All sit at S2–S3 with no agreed
path to S4.

A single uniform scheme is impossible: `flipperzero-mcp` requires a USB device
physically attached to the host and can never be a remote service, while
`gandi-mcp` wraps a public cloud API with a portable bearer token and has no
locality constraint at all. The servers genuinely fork on **locality** — but
into three clusters, not six snowflakes.

## The three archetypes

| Archetype | Meaning | Servers today |
|---|---|---|
| `remote-hostable` | No locality constraint; can run as a hosted streamable-HTTP endpoint or locally over stdio | gandi-mcp, shortcut-mcp |
| `site-local` | Bound to a site: must reach a network-private appliance, or cannot bootstrap unattended | protonmail-mcp, unifi-mcp, unraid-mcp |
| `host-local` | Bound to a host: requires physically attached hardware; never a network service | flipperzero-mcp |

### Decision tree (deterministic, in order)

1. Requires physically attached hardware (USB/serial device)? → **`host-local`**
2. Backend not reachable from arbitrary networks (LAN appliance, private
   controller)? → **`site-local`**
3. Cannot bootstrap unattended from env config alone (interactive login,
   stateful session, 2FA prompt at startup)? → **`site-local`**
4. Otherwise (portable token + publicly reachable backend) → **`remote-hostable`**

Step 3 is what keeps `protonmail-mcp` out of `remote-hostable`: its backend is
a public cloud API, but login is interactive (email + password + 2FA prompt)
and the session is stateful, so it cannot be brought up headlessly from env
vars the way a token-auth server can. The criterion is deliberately
*operational* (can it start unattended?) rather than *credential-weight* (how
much does the token grant?) — every server in the suite holds full-account
credentials, so credential weight does not discriminate.

Applied today:

| Server | Step that decides | Archetype |
|---|---|---|
| flipperzero-mcp | 1 — USB serial (`/dev/ttyACM0`) | host-local |
| unraid-mcp | 2 — `UNRAID_HOST` on LAN | site-local |
| unifi-mcp | 2 — controller usually on LAN | site-local |
| protonmail-mcp | 3 — interactive login + stateful session | site-local |
| gandi-mcp | 4 | remote-hostable |
| shortcut-mcp | 4 | remote-hostable |

## Declaration

The README `## Status` section (already required by MCP-007 and already
carrying the `Stage:` token) gains a `Deployment:` token:

```
Stage: S3
Deployment: site-local
```

Accepted token set: `remote-hostable | site-local | host-local`. The auditor
grades against the *declared* token — it trusts the declaration, exactly as it
trusts `Stage:` — and a separate drift meta-rule surfaces contradictions.

A repo may deliberately declare a more constrained archetype than its backend
allows (e.g. a remote-capable server shipped as a personal local tool). The
drift rule fires as a MAY-tier warning, not a failure.

## Common spine (all archetypes)

Existing rules, named here as the shared deployment floor — no new obligations:

- PROTO-008 — stdio is the default transport; HTTP behind an explicit flag
- PROTO-011/012 — secrets from env, never logged
- PROTO-013 — stdout reserved for JSON-RPC
- MCP-021/022 — structured logging to stderr
- MCP-023 — lockfile committed
- MCP-017 — CI actions pinned to SHA

The one **new** universal obligation arrives at S4: a buildable, versioned
distribution artifact plus deploy docs, in the archetype-specific form below.
S4 does **not** require operating a live deployment — the bar is a
reproducible build published to a registry or release, suitable for a solo
maintainer.

## New rules (all `min_stage = S4`; NA when the archetype does not match)

### MCP-DEPLOY-ARTIFACT — archetype's distribution artifact is built and published [MUST]

| Archetype | Required artifact |
|---|---|
| remote-hostable | Container image or serverless config (e.g. Workers), published to a registry on tag |
| site-local | Dockerfile + a compose (or equivalent run) example; image pushed to a registry on tag |
| host-local | `.mcpb` bundle built and attached to the GitHub release |

**Mechanical check.** remote-hostable: repo contains a `Dockerfile` or
serverless config (`wrangler.toml`/`wrangler.jsonc` or equivalent) AND a
workflow step that pushes/deploys it on tag. site-local: `Dockerfile` exists
AND a compose/run example exists in README or `docs/` AND a workflow pushes
the image on tag. host-local: `manifest.json` (MCPB) exists AND a workflow
builds the `.mcpb` and uploads it as a release asset.

### MCP-DEPLOY-DOCS — deploy/install documentation matches the archetype [MUST]

| Archetype | Required docs |
|---|---|
| remote-hostable | How to deploy the service and add it as a connector/custom URL |
| site-local | How to run the container against the appliance, with env wiring |
| host-local | How to install the bundle, including device-attach prerequisites |

**Mechanical check.** README or `docs/*.md` contains a deploy/install section
referencing the artifact from MCP-DEPLOY-ARTIFACT (image name, `.mcpb`
filename, or deploy command).

### MCP-DEPLOY-TRANSPORT — transports offered match the archetype [MUST]

| Archetype | Transports |
|---|---|
| remote-hostable | stdio (default) AND streamable HTTP behind a flag |
| site-local | stdio (default); HTTP behind a flag is optional |
| host-local | stdio only; no network listener code path |

Streamable HTTP is named specifically: SSE was superseded in the 2025-03-26
MCP spec revision and new HTTP listeners must not use it. Existing SSE
listeners (protonmail-mcp) are acceptable for site-local, where HTTP is
optional, but migrate on next transport work.

**Mechanical check.** remote-hostable: entrypoint supports a
`--transport`/env switch whose HTTP mode is streamable HTTP. site-local: no
additional check beyond PROTO-008. host-local: source contains no HTTP
listener construction (no `uvicorn`/`http.server`/FastMCP HTTP app for
Python).

### MCP-DEPLOY-REGISTRY — artifact submitted to the MCP registry [MAY]

Applies to `remote-hostable` and `host-local`; NA for `site-local` (a
site-bound server has no general audience). Absorbs shortcut-mcp's
self-declared "registry submission" gate into the standard.

**Mechanical check.** README references the MCP registry listing, or a
`server.json` registry manifest exists.

### MCP-018 — retiered MAY → MUST, check strengthened

MCP-018 ("release workflow exists for tagged releases") already has
`min_stage = S4`, where the ladder defines S4 as "release pipeline and
versioned releases" — a MAY tier there is incoherent. Retier to MUST and
strengthen the check: the release workflow must build and publish the
archetype's artifact (the same workflow steps MCP-DEPLOY-ARTIFACT looks for).
No new `MCP-DEPLOY-RELEASE` rule — that would duplicate MCP-018, and the
workspace rule is replace, don't deprecate.

## Meta-rules (mirror MCP-STAGE-DECL / MCP-STAGE-DRIFT)

### MCP-DEPLOY-DECL — README declares a deployment archetype [MAY]

Fires when the `## Status` section carries no `Deployment:` token. An
undeclared repo is graded with no archetype-conditional rules (all NA) and
this warning. MAY-tier: surfaces in the report without a nonzero exit code.

### MCP-DEPLOY-DRIFT — declared archetype matches repo signals [MAY]

Fires when the declaration contradicts cheap structural signals:

- `host-local` declared but no serial/USB dependency in the manifest
- `remote-hostable` declared but the server prompts on stdin at startup
- `site-local`/`host-local` declared but the backend base URL is a public
  cloud API and auth is a single env token (the shortcut-mcp case, if it
  declared host-local to keep shipping only the `.mcpb`)

MAY-tier by design: a maintainer may deliberately under-declare; the drift
warning surfaces the mismatch without blocking.

## Auditor implementation sketch

- `consistency_check/types.py`: add `Archetype` StrEnum
  (`REMOTE_HOSTABLE`, `SITE_LOCAL`, `HOST_LOCAL`); add
  `applies_to_archetype: frozenset[Archetype] | None = None` to `Rule`
  (`None` ⇒ applies to all archetypes).
- New `consistency_check/rules/deployment.py` with the four DEPLOY rules and
  the two meta-rules; `read_deployment_token()` helper modeled on
  `stage_meta.py`'s stage-token parser.
- Audit loop: a rule whose `applies_to_archetype` excludes the repo's declared
  archetype yields `FindingStatus.NA`. Undeclared archetype ⇒ all
  archetype-conditional rules NA + MCP-DEPLOY-DECL warning.
- MCP-018: change `tier` to MUST in place; strengthen its check per above.
- Docs: new `docs/standards/deployment.md` (archetypes, decision tree,
  declaration format, rule text); `stages.md` S4 entry updated to point at it;
  min_stage map gains the DEPLOY rules under S4.
- Tests: extend `tests/test_min_stage_map.py`; add archetype-conditional NA
  cases and token-parsing cases (declared/undeclared/invalid token).

## Per-server path to S4

| Server | Archetype | Gap to S4 |
|---|---|---|
| gandi-mcp | remote-hostable | streamable-HTTP transport flag; container/worker artifact; deploy docs; release workflow |
| shortcut-mcp | remote-hostable | streamable-HTTP transport flag; remote artifact + publish (existing `.mcpb` stays as an optional extra); or declare site/host-local and accept the drift warning |
| protonmail-mcp | site-local | Dockerfile + compose example; image publish on tag; release workflow (existing SSE listener already exceeds the transport bar) |
| unifi-mcp | site-local | Dockerfile + compose example; image publish on tag; release workflow |
| unraid-mcp | site-local | compose example; image publish on tag; release workflow (Dockerfile exists) |
| flipperzero-mcp | host-local | `.mcpb` build + release-asset upload (stdio-only already satisfied) |

## Out of scope

- Operating live deployments (uptime, health checks) — S4 is buildable, not
  operated.
- Multi-tenant auth (OAuth/CIMD) for remote-hostable servers — these are
  personal single-tenant servers; hosted endpoints carry the owner's token.
- Migrating protonmail-mcp's SSE listener to streamable HTTP — flagged for
  next transport work, not an S4 gate (HTTP is optional for site-local).
- Changes to the `build-mcp-server` skill's guidance for brand-new servers
  (its decision flow is per-server advice; this scheme governs the workspace
  audit). Aligning the skill's vocabulary with the three archetypes can
  follow once the standard lands.
