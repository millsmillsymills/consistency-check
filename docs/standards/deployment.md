# MCP Server Deployment Archetypes

The **deployment archetype** records where a server can run. It is declared per
repo and gates the archetype-conditional `MCP-DEPLOY-*` rules, all of which sit
at `min_stage = S4`. See
`docs/superpowers/specs/2026-06-10-mcp-deployment-scheme-design.md` for the full
design rationale.

## The three archetypes

- **`remote-hostable`** — no locality constraint; can run as a hosted
  streamable-HTTP endpoint or locally over stdio.
- **`site-local`** — bound to a site: must reach a network-private appliance,
  or cannot bootstrap unattended (interactive/stateful auth).
- **`host-local`** — bound to a host: requires physically attached hardware;
  never a network service.

## Decision tree (deterministic, in order)

1. Requires physically attached hardware (USB/serial)? → `host-local`
2. Backend not reachable from arbitrary networks (LAN appliance)? → `site-local`
3. Cannot bootstrap unattended from env config alone (interactive login,
   stateful session)? → `site-local`
4. Otherwise (portable token + publicly reachable backend) → `remote-hostable`

## Declaration

The README `## Status` section (MCP-007) carries a `Deployment:` token beside
the `Stage:` token:

````
Stage: S3
Deployment: site-local
````

Accepted tokens: `remote-hostable | site-local | host-local`. The auditor
grades against the declared token; an undeclared repo gets all
archetype-conditional rules as `n/a` plus the MCP-DEPLOY-DECL warning. A repo
may deliberately under-declare (ship a remote-capable server as a local tool);
MCP-DEPLOY-DRIFT surfaces the mismatch without blocking.

## Current assignments

| Server | Archetype | Deciding step |
|---|---|---|
| flipperzero-mcp | host-local | 1 — USB serial |
| unraid-mcp | site-local | 2 — LAN appliance |
| unifi-mcp | site-local | 2 — LAN controller |
| protonmail-mcp | site-local | 3 — interactive, stateful auth |
| gandi-mcp | remote-hostable | 4 |
| shortcut-mcp | remote-hostable | 4 |

## Rules (all `min_stage = S4`; `n/a` when the archetype does not match)

### MCP-DEPLOY-ARTIFACT — archetype's distribution artifact is built and published [MUST]

| Archetype | Required |
|---|---|
| remote-hostable | Dockerfile or wrangler config, plus a workflow step that publishes the image or deploys the worker |
| site-local | Dockerfile + compose/run example, plus a workflow step that pushes the image to a registry |
| host-local | MCPB `manifest.json`, plus a workflow that builds the `.mcpb` and uploads it as a release asset |

### MCP-DEPLOY-DOCS — deploy/install documentation matches the archetype [MUST]

| Archetype | Required docs (README or docs/) |
|---|---|
| remote-hostable | Deploying the service and adding it as a connector/custom URL |
| site-local | Running the container (`docker compose` / `docker run`) against the appliance |
| host-local | Installing the `.mcpb` bundle, including device prerequisites |
