# ChromaMCP in Claude Desktop

**Config file:** `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows).
**Wrapper key:** `mcpServers`.
**Schema checked:** 2026-10-11, against Anthropic's own Claude Desktop example in
<https://docs.claude.com/en/docs/claude-code/mcp> (section "Use Claude Code as an MCP server"), which
shows a `claude_desktop_config.json` entry of this shape.

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

**Exercised:** not in this unit. The block above was written from the published schema and has not
been run against Claude Desktop.
