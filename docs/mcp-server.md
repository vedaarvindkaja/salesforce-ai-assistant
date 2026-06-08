# MCP Server — Installation & Configuration

The Salesforce metadata-graph MCP server exposes the platform's developer
capabilities to any [Model Context Protocol](https://modelcontextprotocol.io/)
client over **stdio** transport. It's a thin transport layer over the existing
orchestration stack — the same graph, tools, and Claude agentic loop the CLI
uses — so no capability logic is reimplemented here.

Verified end-to-end against **Claude Desktop**, **Claude Code**, and
**Augment AI**. The server is identical across all three; only the per-client
registration differs.

## Capabilities exposed

The server exposes five tools:

| Tool | What it does |
|------|--------------|
| `health` | Reports server status and graph stats (nodes/edges by type). No arguments. |
| `metadata_qa` | Answers natural-language questions about org metadata and dependencies. |
| `explain_apex` | Explains Apex classes/triggers and suggests refactors, anchored to the graph. |
| `generate_soql` | Generates SOQL using the org's actual object names. (Object grain, not field grain.) |
| `analyze_deployment_impact` | Traces the blast radius of changing a component. Topology-only — does not read source. |

> **Note:** A fifth capability, debug-log analysis, is planned but not yet
> exposed (it requires a dedicated log parser). The four capabilities above all
> exercise the metadata dependency graph, which is the platform's core.

## Prerequisites

Before configuring any client, the server must be able to run locally:

1. **Python 3.11+** with the project dependencies installed
   (`pip install -r requirements.txt` from `backend/`, including `mcp`).
2. **A populated metadata cache.** The server reads a pre-built SQLite cache;
   it does not extract metadata on demand. Build it once:
   ```
   python -m scripts.extract_to_cache
   ```
   (Requires valid OAuth tokens — visit `http://localhost:8000/auth/login`
   first if you haven't authenticated.)
3. **An Anthropic API key** in `backend/.env` as `ANTHROPIC_API_KEY`. The
   server's capability tools call the Claude API; this key pays for that usage.

Confirm the server runs standalone before wiring up any client:
```
python -m app.interfaces.mcp_server.server
```
It should log `Starting salesforce-metadata-graph MCP server (stdio)...` and
then block, waiting for a client on stdin. That blocked wait is success —
press `Ctrl+C` to stop it. (The `Ctrl+C` produces a noisy `anyio`/`asyncio`
traceback as it unwinds the interrupted wait; that's harmless, not an error.)

## A note on paths and the working directory

MCP clients **launch the server process themselves**, from a working directory
you don't control. (Claude Desktop, for example, was observed launching it from
`C:\Windows\System32`.) The `cwd` field some clients offer is **not reliably
honoured**.

The server is therefore written to be **working-directory-independent**:

- The Python package root (`backend/`) must be on `PYTHONPATH` so `import app`
  resolves regardless of launch directory.
- The metadata cache is located via the `SF_CACHE_PATH` environment variable,
  falling back to a path computed relative to the server's own source file.
- `.env` is loaded relative to the source file, not the cwd.

**Practical upshot:** every client config below sets two environment variables —
`PYTHONPATH` (pointing at `backend/`) and `SF_CACHE_PATH` (pointing at the cache
file). Set these and the launch directory no longer matters.

Throughout, replace the placeholders with absolute paths on your machine:

- `<python>` — absolute path to the Python interpreter with the project deps
  (find it with `python -c "import sys; print(sys.executable)"`)
- `<backend>` — absolute path to the `backend/` directory
- `<backend>/data/metadata_cache.db` — the cache file built in step 2 above

On Windows, use double backslashes (`\\`) or forward slashes in JSON paths.

---

## Claude Desktop

**Config file location**

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

On Windows MSIX installs the app may actually read a *virtualized* copy under
`%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\`. To avoid
editing the wrong file, open the config through the app:
**Settings → Developer → Edit Config** — this always opens the file the app reads.

**Configuration**

Add the server under `mcpServers` (merge into the file if it already has other
keys; don't overwrite them):

```json
{
  "mcpServers": {
    "salesforce-metadata-graph": {
      "command": "<python>",
      "args": ["-m", "app.interfaces.mcp_server.server"],
      "cwd": "<backend>",
      "env": {
        "PYTHONPATH": "<backend>",
        "SF_CACHE_PATH": "<backend>/data/metadata_cache.db"
      }
    }
  }
}
```

(`cwd` is included as a best-effort hint; the `env` vars are what actually make
it work.)

**Apply**

1. Save the file.
2. Fully quit Claude Desktop — on Windows it stays in the system tray, so
   right-click the tray icon → **Quit**. Closing the window is not enough.
3. Reopen Claude Desktop.
4. In a new chat, open the tools/connector menu and confirm
   `salesforce-metadata-graph` appears with its tools.

---

## Claude Code

**Install** (native installer, no Node required):

```
irm https://claude.ai/install.ps1 | iex
```

The binary lands in `%USERPROFILE%\.local\bin`. **Open a new terminal** after
install — PATH only updates in a fresh session. If you use VS Code's integrated
terminal, restart VS Code entirely (it caches its environment at launch).

**Register the server** (one command — adjust the line-continuation character
for your shell; backtick shown for PowerShell):

```
claude mcp add salesforce-metadata-graph `
  --scope user `
  --env PYTHONPATH=<backend> `
  --env SF_CACHE_PATH=<backend>/data/metadata_cache.db `
  -- <python> -m app.interfaces.mcp_server.server
```

Everything after `--` is the launch command. The registration is stored in
`~/.claude.json`.

**Verify**

```
claude mcp list
```

Should show `salesforce-metadata-graph: ... - ✓ Connected`. Then start an
interactive session with `claude` and ask it to use the `health` tool.

---

## Augment AI

Augment configures MCP through its settings panel, not a hand-edited file.

1. Open the **Augment panel** in VS Code → options menu → **Settings**.
2. Go to **Integrations → MCP Servers**.
3. Click **Import from JSON** and paste:

```json
{
  "mcpServers": {
    "salesforce-metadata-graph": {
      "command": "<python>",
      "args": ["-m", "app.interfaces.mcp_server.server"],
      "env": {
        "PYTHONPATH": "<backend>",
        "SF_CACHE_PATH": "<backend>/data/metadata_cache.db"
      }
    }
  }
}
```

4. Save. The server should appear in the list as
   `● salesforce-metadata-graph (5) tools` with a green/connected indicator.
5. MCP tools run in Augment's **Agent** mode (not Chat/Completions). Open an
   Agent thread and ask it to use the `health` tool.

---

## Verifying it works

In any client, the cleanest first test is the `health` tool — it exercises the
full transport chain (process launch, handshake, graph load) **without** an API
call, so it isolates transport problems from capability problems:

> Use the health tool to check the metadata graph server.

A healthy response reports `OK`, your org's `instance_url`, and node/edge
counts. Once `health` works, try a capability:

> Using the metadata graph, what is the deployment impact of changing the
> Opportunity object?

## Cost reporting

Each capability call runs an agentic loop that makes Claude API calls. Per-call
cost and token usage are logged to the server's **stderr** (visible in the
client's MCP server log), not returned in the tool response — an MCP host's
model treats the tool result as content to interpret and will drop a cost
footer, so stderr is the reliable channel. Look for lines like:

```
capability=impact turns=5 in=14793 out=1492 cost=$0.0668
```

Note there are two independent cost layers when running through a client: the
**host's** own model usage (covered by your Claude subscription or the host's
billing) and the **server's** internal Claude API calls (billed to the
`ANTHROPIC_API_KEY` in `.env`).

---

## Troubleshooting

**Server shows "disconnected" / tools don't appear.**
The process failed to launch. Read the server log — it shows the exact Python
error. On Windows MSIX, the log is under
`%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\logs\mcp-server-salesforce-metadata-graph.log`,
**not** the documented `%APPDATA%\Claude\logs\` path.

**`ModuleNotFoundError: No module named 'app'`.**
The client launched Python from a directory where `app` isn't importable, and
`cwd` wasn't honoured. Fix: ensure `PYTHONPATH=<backend>` is set in the config's
`env` block. This is the most common failure.

**`Graph not available: Cache not found ...` (often pointing at an unexpected
directory like `System32`).**
Same root cause — the working directory isn't `backend/`. Fix: set
`SF_CACHE_PATH` to the absolute path of the cache file in the config's `env`
block. (Also confirm the cache exists: run `python -m scripts.extract_to_cache`.)

**`claude` not recognized after install (Claude Code).**
PATH didn't refresh. Open a *new* terminal. If using VS Code's integrated
terminal, restart VS Code entirely — it caches its environment from launch.
Verify the binary directly: `& "$env:USERPROFILE\.local\bin\claude.exe" --version`.

**Config edit silently disables everything (Claude Desktop).**
JSON is strict — a trailing comma, missing brace, or unescaped backslash breaks
the whole file silently. Validate before restarting:
```
python -c "import json; json.load(open(r'<config-path>', encoding='utf-8-sig'))"
```
(`utf-8-sig` strips a BOM if present.) Should print nothing (success) or a clear
error pointing at the problem line.

**Config edits don't take effect.**
The client cached the old config. Fully quit and relaunch — for Claude Desktop,
quit from the system tray, not just the window. To force it on Windows:
`Get-Process *claude* | Stop-Process -Force`, then reopen.

**Garbled characters in logs or output (`·` → `Â·`).**
A non-UTF-8 console encoding. The server forces UTF-8 on its streams at startup;
if you see this elsewhere, set `PYTHONUTF8=1` in the client's `env` block.

**A tool works in one client but misbehaves in another.**
Not all MCP clients are equally compatible with all servers, and host models
differ in how they route to tools. The server is identical across clients; if
behaviour differs, it's a host/model difference, not a server bug. The server
log (stderr) shows exactly which internal tools the loop called, which is the
fastest way to compare.
