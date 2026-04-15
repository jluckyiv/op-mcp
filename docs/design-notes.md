# op-mcp design notes

## Why this exists

Claude in Cowork, Claude Code, and Claude Desktop sometimes needs ad
hoc access to secrets stored in 1Password: "read the API key for X,"
"what's in my Private vault," "add this new credential." Those flows
benefit from being gated by MCP's permission system rather than being
one-off subprocess calls buried inside other servers.

This server is deliberately not a prerequisite for anything else. If
another MCP needs a secret (e.g. to reach a REST API with a bearer
token), it can shell out to `op read` directly — there's no value in
routing through another process just to call the same CLI. The JAMS
CLI does this already for its login credentials, and the Timing REST
token will do the same when time-entry writes move into Cowork.

See the vault's `1Password MCP Server.md` for the higher-level project
context and its relationship to the Apple Apps and Timing projects.

## Stateless subprocess model

Every tool handler calls `OpRunner.run(...)`, which spawns a fresh
`op` subprocess. The runner holds no session, no cached credentials,
no mutex. `op` caches its own session inside the 1Password desktop
app via the OS keychain — that's `op`'s concern, not ours.

Consequences:

- **No concurrent-auth races.** Two parallel tool calls each spawn
  their own subprocess. `op` handles serialization internally; we
  don't need to.
- **No stale cache bugs.** The Go jams-mcp had persistent bugs where
  cached auth state went stale. We avoid that class of bug entirely
  by not caching.
- **Touch ID prompts are visible where they happen.** First call per
  session triggers biometric. Subsequent calls reuse the session
  until it expires. This behavior is controlled by 1Password, not
  by us.

## JSON handling

The `op` CLI supports `--format=json` on `item get`, `item list`, and
`item create/edit/delete`. It does not support it on `read` (which
returns the raw secret value) or on the binary itself (`--version`
is plain text).

Unlike the jams CLI, `op` is not uniform here. Callers in
`src/op_mcp/tools/` pass `--format=json` explicitly when they want
JSON output, and set `expect_json=True` on the runner call to trigger
parsing. `op read` uses the default (`expect_json=False`) and returns
the stripped secret string.

## Error handling

Three error classes:

- `OpBinaryNotFoundError` — `op` isn't on PATH. Raised on the first
  tool call (not at server startup, though `_preflight_binary_check`
  does log a warning at startup).
- `OpCliError` — CLI exited non-zero. `stderr` and exit code are
  preserved on the exception for diagnostic purposes.
- `OpOutputNotJSONError` — `expect_json=True` but stdout didn't
  parse. Subclass of `OpCliError`.

All three are surfaced to the MCP client as MCP errors via the usual
FastMCP exception flow.

## What's not here

- **Session management.** `op signin` and `op signout` are not exposed.
  Session lifetime is the 1Password app's business.
- **Service account tokens.** This server assumes biometric desktop
  auth. If you need to run without Touch ID (CI, headless), use
  service accounts outside this MCP.
- **Document and vault management.** `op document`, `op vault` — not
  wrapped yet. Add handlers in a new `tools/` module when a real use
  case appears.
- **`op inject` / `op run`.** These are shell-level conveniences
  (template injection, env-var loading) without a clean MCP
  equivalent. Out of scope.

## Future work

- Live smoke tests against a dedicated test vault.
- `op whoami` tool for checking which account is active.
- Structured error surface when the desktop app is locked or CLI
  integration is disabled — currently those fail with generic `op`
  stderr messages.
