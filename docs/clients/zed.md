# ChromaMCP in Zed

**Config file:** `settings.json` (open it in Zed with the `zed: open settings file` action).
**Wrapper key:** `context_servers`.
**Schema checked:** 2026-10-11, against <https://zed.dev/docs/ai/mcp> (section "As Custom Servers"),
which shows a local server entry of this shape.

Nothing is published to PyPI yet, so `command` points at the interpreter inside a local checkout:
replace `/path/to/ChromaMCP` with that path.

```json
{
  "context_servers": {
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

Zed also accepts the same server as an extension, and separates "local" from "remote" entries; this is
the local, `command` form.

`CHROMAMCP_ALLOWED_ROOT` is the directory every file-reading tool is confined to; a path outside it —
including a symlink that resolves outside it — is refused with the variable named in the error. Left
unset it defaults to the server's working directory, which a GUI client does not set predictably, so
set it explicitly.

**Exercised:** not in this unit. The block above was written from the published schema and has not
been run against Zed.
