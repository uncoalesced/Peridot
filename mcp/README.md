# Peridot Sovereign Invocation (MCP)

Let cloud agents (Claude Code, Codex CLI, Gemini CLI, Hermes, anything that speaks MCP) hand private-data jobs to **your local Peridot model**. The agent describes the job; Peridot reads your files on your machine and sends back only a result. Your raw data stays on your machine.

`peridot_mcp.py` is a small stdio MCP server that uses only the Python standard library. It exposes one tool, `peridot_invoke`, and talks to the Peridot server over HTTP on loopback. If Peridot is not running, it starts the Peridot relay and waits up to 180 s for the model to load.

## Privacy model

| `return_mode` | What can leave your machine |
|---|---|
| `review` (default) | Only the summary you approved. An always-on-top dialog shows it and lets you edit it first. If you click Deny, close the window, or let the 120 s timer run out, nothing is shared. |
| `full` | Peridot's final answer. Raw file contents are never sent, only the answer. |
| `status_only` | Only "completed" or "failed". No data is included. |

If a task only performs an action (`action_only`), the agent receives just the completion status, whatever mode it asked for. Peridot can only read folders on your allowlist. The `model` argument is accepted but has no effect in v1.6.0.

## Setup

Requires Python 3.10+ with Tkinter (Tkinter is used for the approval dialog). Change the paths below to match your install.

**Claude Code**

```
claude mcp add peridot -- python E:\Peridot\mcp\peridot_mcp.py
```

or in `.mcp.json`:

```json
{ "mcpServers": { "peridot": { "command": "python", "args": ["E:\\Peridot\\mcp\\peridot_mcp.py"] } } }
```

**Codex CLI** (`~/.codex/config.toml`)

```toml
[mcp_servers.peridot]
command = "python"
args = ["E:\\Peridot\\mcp\\peridot_mcp.py"]
```

**Gemini CLI** (`~/.gemini/settings.json`)

```json
{ "mcpServers": { "peridot": { "command": "python", "args": ["E:\\Peridot\\mcp\\peridot_mcp.py"] } } }
```

**Any MCP client** (stdio transport)

```json
{
  "command": "python",
  "args": ["/path/to/Peridot/mcp/peridot_mcp.py"],
  "env": { "PERIDOT_HOME": "/path/to/Peridot", "PERIDOT_PYTHON": "/path/to/Peridot/venv/bin/python" }
}
```

## Environment

- `PERIDOT_HOME`: the Peridot install folder. Defaults to the parent folder of this `mcp/` folder. The server reads `SERVER_HOST`, `SERVER_PORT` (defaults `127.0.0.1:5000`) and `API_KEY` from `PERIDOT_HOME/.env`.
- `PERIDOT_PYTHON`: the Python interpreter used to start the relay and the approval dialog. Point it at Peridot's venv. Defaults to the interpreter running this server.
