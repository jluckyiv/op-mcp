"""MCP tool handlers for 1Password item management.

Wraps:
  - op item list       → op_list_items
  - op item create     → op_create_item
  - op item edit       → op_edit_item
  - op item delete     → op_delete_item

Item creation and editing in the `op` CLI uses positional `field.assignment`
syntax (e.g. `notesPlain=some-note api-key=tok_example`). These handlers
accept a plain dict and translate to the CLI's assignment form.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from op_mcp.runner import OpRunner


def register(mcp: FastMCP, runner: OpRunner) -> None:
    """Register item-management tool handlers."""

    @mcp.tool()
    async def op_list_vaults() -> Any:
        """List all 1Password vaults the authenticated account can access.

        Returns an array of vault summaries (id, name, type). Use vault names
        or IDs with op_list_items and op_get_item to scope queries.
        """
        return await runner.run("vault", "list", "--format=json", expect_json=True)

    @mcp.tool()
    async def op_get_item(item: str, vault: str | None = None) -> Any:
        """Get all fields of a 1Password item.

        Returns the full item JSON including all fields, sections, and metadata.
        Use this when you need more than the summary returned by op_list_items,
        or when you want to inspect fields without knowing the exact op:// reference.

        Args:
            item: Item ID or exact title.
            vault: Optional vault name/ID to disambiguate when the title is not unique.
        """
        args: list[str] = ["item", "get", item, "--format=json"]
        if vault is not None:
            args.extend(["--vault", vault])
        return await runner.run(*args, expect_json=True)

    @mcp.tool()
    async def op_list_items(vault: str | None = None) -> Any:
        """List items in a 1Password vault.

        Returns an array of item summaries (id, title, vault, category).
        If vault is omitted, lists items across all vaults the account
        has access to.
        """
        args: list[str] = ["item", "list", "--format=json"]
        if vault is not None:
            args.extend(["--vault", vault])
        return await runner.run(*args, expect_json=True)

    # -- Write tools (permission-gated) --

    @mcp.tool()
    async def op_create_item(
        title: str,
        category: str,
        vault: str,
        fields: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        """Create a new item in a 1Password vault.

        Args:
            title: Display name for the item.
            category: Item category (e.g. "Login", "Password", "API Credential",
                "Secure Note"). See `op item template list` for the full list.
            vault: Target vault name or ID.
            fields: Mapping of field name → value (e.g. {"notesPlain":
                "some note", "api-key": "tok_example"}). Translated to
                the CLI's `field=value` positional form.
            tags: Optional list of tag strings.

        Returns the created item metadata as JSON.
        """
        args: list[str] = [
            "item", "create",
            "--category", category,
            "--vault", vault,
            "--title", title,
            "--format=json",
        ]
        if tags:
            args.extend(["--tags", ",".join(tags)])
        if fields:
            args.extend(f"{name}={value}" for name, value in fields.items())
        return await runner.run(*args, expect_json=True)

    @mcp.tool()
    async def op_edit_item(
        item: str,
        vault: str | None = None,
        fields: dict[str, str] | None = None,
        tags: list[str] | None = None,
        title: str | None = None,
    ) -> Any:
        """Edit an existing item in a 1Password vault.

        Args:
            item: Item ID or exact title.
            vault: Optional vault name/ID to disambiguate.
            fields: Field assignments in the same form as `op_create_item`.
            tags: Replacement tag list (overwrites existing tags).
            title: New display title.

        Returns the updated item metadata as JSON.
        """
        args: list[str] = ["item", "edit", item, "--format=json"]
        if vault is not None:
            args.extend(["--vault", vault])
        if title is not None:
            args.extend(["--title", title])
        if tags is not None:
            args.extend(["--tags", ",".join(tags)])
        if fields:
            args.extend(f"{name}={value}" for name, value in fields.items())
        return await runner.run(*args, expect_json=True)

    @mcp.tool()
    async def op_delete_item(
        item: str,
        vault: str | None = None,
        archive: bool = True,
    ) -> dict[str, str]:
        """Delete or archive an item in a 1Password vault.

        Args:
            item: Item ID or exact title.
            vault: Optional vault name/ID to disambiguate.
            archive: If True (default), archive instead of permanent delete.
                Archived items can be recovered from the 1Password app.

        Returns a status dict. `op item delete` emits no output on success.
        """
        args: list[str] = ["item", "delete", item]
        if vault is not None:
            args.extend(["--vault", vault])
        if archive:
            args.append("--archive")
        await runner.run(*args, expect_json=False)
        return {
            "status": "ok",
            "action": "archived" if archive else "deleted",
            "item": item,
        }
