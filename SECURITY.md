<!-- Global context: vulnerability reporting policy and supported security posture for the public companion repository. -->

# Security policy

## Supported versions

Security fixes are applied to the latest `1.x` release and the default branch.
This project is validated on Windows only. Upstream Ableton Live MCP defects
should also be reported to the
[`bschoepke/ableton-live-mcp`](https://github.com/bschoepke/ableton-live-mcp)
maintainer when appropriate.

## Report a vulnerability

Use **Security → Report a vulnerability** in this GitHub repository when private
vulnerability reporting is available. Include:

- affected release or commit;
- impact and prerequisites;
- minimal reproduction steps;
- whether secrets, Live Sets, or local processes are exposed;
- a proposed mitigation, if known.

If private reporting is unavailable, open a public issue containing no exploit,
secret, personal path, or private Live data and ask the maintainer to establish a
private channel. Do not publish working destructive payloads before coordination.

## Security boundaries

The installer verifies pinned Git identities, uses a local virtual environment,
binds the Live bridge to loopback, backs up Codex configuration, and supports
scoped rollback. Those controls do not make the MCP sandboxed. The upstream
server can evaluate arbitrary Python in Live, and approval mode `approve` allows
Codex to invoke every exposed tool without a per-tool prompt.

Computer Use permissions, Codex task sandbox/approvals, MCP tool approvals, and
Live's own capabilities are separate controls. Enabling one does not grant or
restrict the others.

Read the [operator threat model and hardening guide](docs/security.md) before
using the standard allow-all profile.
