# ChromaMCP in VS Code

**Config file:** `.vscode/mcp.json` in the workspace.
**Wrapper key:** `servers` — **not** `mcpServers`.
**Schema checked:** 2026-10-11, against
<https://code.visualstudio.com/docs/copilot/customization/mcp-servers> (section "Configure the
`mcp.json` file").

That page also records a change worth knowing: `.vscode/mcp.json` is now listed among the deprecated
destinations, and the **portable** formats are preferred for new servers — a workspace `.mcp.json`
(a `mcpServers` wrapper, Claude/portable shape) or `$COPILOT_HOME/mcp-config.json`. Both are shown
below.

Nothing is published to PyPI yet, so `command` points at the interpreter inside a local checkout:
replace `/path/to/ChromaMCP` with that path.

VS Code's own format (`.vscode/mcp.json`, `servers`):

```json
{
  "servers": {
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

The portable format (workspace `.mcp.json`):

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

`CHROMAMCP_ALLOWED_ROOT` is the directory every file-reading tool is confined to; a path outside it —
including a symlink that resolves outside it — is refused with the variable named in the error. Left
unset it defaults to the server's working directory.

**Exercised:** not in this unit. The blocks above were written from the published schema and have not
been run against VS Code.
