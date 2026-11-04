# ChromaMCP in Claude Code

**Config file:** `.mcp.json` at the project root (project scope, shared through version control), or
`~/.claude.json` (local/user scope).
**Wrapper key:** `mcpServers`.
**Schema checked:** 2026-10-11, against <https://docs.claude.com/en/docs/claude-code/mcp> (sections
"Project scope" and "Add MCP servers from JSON configuration").

Nothing is published to PyPI yet, so `command` points at the interpreter inside a local checkout:
replace `/path/to/ChromaMCP` with that path.

```json
{
  "mcpServers": {
    "chromamcp": {
      "type": "stdio",
      "command": "/path/to/ChromaMCP/.venv/bin/python",
      "args": ["-m", "chromamcp.server"],
      "env": {
        "CHROMAMCP_ALLOWED_ROOT": "/path/to/your/data"
      }
    }
  }
}
```

The same entry can be added from the CLI instead of edited by hand:

```
claude mcp add --transport stdio chromamcp \
  --env CHROMAMCP_ALLOWED_ROOT=/path/to/your/data \
  -- /path/to/ChromaMCP/.venv/bin/python -m chromamcp.server
```

`CHROMAMCP_ALLOWED_ROOT` is the directory every file-reading tool is confined to; a path outside it —
including a symlink that resolves outside it — is refused with the variable named in the error. Left
unset it defaults to the server's working directory.

Claude Code also sets `CLAUDE_PROJECT_DIR` in a server's environment and answers the MCP `roots/list`
request; this server does not use either, and reads `CHROMAMCP_ALLOWED_ROOT` instead.

**Exercised:** not in this unit. The block above was written from the published schema, and the
`claude mcp add` line has not been run.
