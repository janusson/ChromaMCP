# ChromaMCP in Cursor

**Config file:** `.cursor/mcp.json` in the project, or `~/.cursor/mcp.json` for every project.
**Wrapper key:** `mcpServers`.
**Schema checked:** **not checked in this unit.** Cursor's documentation pages render client-side and
could not be read here, so the wrapper key below is written from the shape Cursor's configuration is
generally documented with — the same `mcpServers` wrapper as Claude Desktop and Claude Code — and it
has **not** been verified against Cursor's own documentation. Check Cursor's MCP page before relying
on it.

Nothing is published to PyPI yet, so `command` points at the interpreter inside a local checkout:
replace `/path/to/ChromaMCP` with that path.

```json
{
  "mcpServers": {
    "chromamcp": {
      "command": "/path/to/ChromaMCP/.venv/bin/python",
      "args": ["-m", "chromamcp.server"],
      "env": {
        "CHROMAMCP_ALLOWED_ROOT": "/path/to/your/data"
      }
    }
  }
}
```

`CHROMAMCP_ALLOWED_ROOT` is the directory every file-reading tool is confined to; a path outside it —
including a symlink that resolves outside it — is refused with the variable named in the error. Left
unset it defaults to the server's working directory, which a GUI client does not set predictably, so
set it explicitly.

**Exercised:** not in this unit, and the schema itself is unverified (see above).
