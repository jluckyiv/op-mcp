# op-mcp

MCP server that wraps the [1Password CLI](https://developer.1password.com/docs/cli/)
(`op`), exposing secret access and item management to MCP clients
(Cowork, Claude Code, Claude Desktop).

## Architecture

```
MCP client (Cowork, Claude Code, Claude Desktop)
  ↓ stdio (MCP protocol)
op-mcp (this Python server)
  ↓ subprocess per tool call
op CLI (1Password CLI)
  ↓ biometric prompt (Touch ID) + 1Password desktop app
1Password vaults
```

The Python server is deliberately thin. Every tool handler shells out
to the `op` CLI and either parses JSON or returns the raw output. The
CLI handles biometric auth, session caching, and all vault access.
The Python side handles MCP protocol and argv construction.

This design is stateless by construction: each tool call spawns a
fresh CLI process. `op` caches its own session inside the 1Password
desktop app — we don't manage sessions, tokens, or credentials. See
`docs/design-notes.md` for the full rationale.

## Prerequisites

- Python 3.11 or newer
- The `op` CLI installed and on PATH. Install via Homebrew:
  `brew install --cask 1password-cli` (tested with v2.33.1).
- The 1Password desktop app installed and **CLI integration enabled**:
  1Password → Settings → Developer → ✓ "Integrate with 1Password CLI".
- Touch ID enabled for CLI authorization (same settings pane).

## Install

```sh
uv tool install .
```

This creates an isolated venv and puts `op-mcp` on PATH. To upgrade
after code changes:

```sh
uv tool install --force --reinstall .
```

Both flags are needed — `--force` overwrites the existing
executable, `--reinstall` bypasses the build cache.

## Run

The server communicates over stdio, so it's normally launched by
an MCP client rather than invoked by hand. For local smoke testing:

```sh
op-mcp
```

The server logs to stderr and waits for MCP protocol messages on
stdin. Press Ctrl-C to exit.

## Configure an MCP client

**Claude Desktop:** Settings → Connectors → Add → enter `op-mcp`
as the command. Or edit `claude_desktop_config.json` directly:

```json
{
  "mcpServers": {
    "op": {
      "command": "op-mcp"
    }
  }
}
```

**Claude Code:** Add to `.mcp.json` (project) or `~/.claude/mcp.json`
(global) with the same shape.

**Cowork:** Add via Cowork's MCP server configuration.

### Recommended permissions

Reads are safe to allow; writes should ask for confirmation.

```json
{
  "permissions": {
    "allow": [
      "mcp__op__op_read_secret",
      "mcp__op__op_list_items",
      "mcp__op__op_version",
      "mcp__op__op_ping"
    ],
    "ask": [
      "mcp__op__op_create_item",
      "mcp__op__op_edit_item",
      "mcp__op__op_delete_item"
    ]
  }
}
```

## Development

```sh
uv sync --extra dev
uv run pytest                              # unit tests (fake `op` binary)
RUN_LIVE_OP_TESTS=1 uv run pytest -m live  # live tests against real op CLI
uv run ruff check
uv run pyright
```

Tests use a fake `op` binary (temporary shell scripts), so they
don't require the real CLI or 1Password access. Live tests (marked
`@pytest.mark.live`) run against the real CLI, trigger Touch ID,
and are skipped by default.

## Tools

7 tools total: 2 infrastructure, 2 read, 3 write.

### Infrastructure

| Tool | Description |
|------|-------------|
| `op_ping` | MCP server liveness check |
| `op_version` | `op` CLI binary version |

### Read tools

| Tool | Description |
|------|-------------|
| `op_read_secret` | Read a secret by `op://vault/item/field` reference |
| `op_list_items` | List items in a vault (or across all vaults) |

### Write tools

| Tool | Description |
|------|-------------|
| `op_create_item` | Create a new item |
| `op_edit_item` | Edit an existing item |
| `op_delete_item` | Archive or permanently delete an item |

### Out of scope (for now)

- `op signin` / `op signout` — session management is `op`'s job.
- `op document` / `op vault` — add when use cases emerge.
- `op inject` / `op run` — template injection and env-loading workflows
  are command-line conveniences without a clean MCP equivalent.
- Service account tokens — this server assumes biometric desktop auth.
