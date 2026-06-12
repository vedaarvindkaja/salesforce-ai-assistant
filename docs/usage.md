# Using Salesforce Graph

A complete walkthrough — from nothing installed to your first answered question —
plus every way to ask.

> **The one prerequisite that gates everything:** the capabilities need a **built
> metadata graph**. Until you've authenticated against your org and run the
> extraction (steps 5–6 below), every capability returns
> `503 "metadata graph not loaded"`. Steps 1–6 get you there once; after that,
> just start the server and ask.

---

## What you'll need

| | For | Notes |
|---|---|---|
| **Python 3.11+** | the backend | core requirement |
| **Git** | cloning the repo | |
| **A Salesforce Developer Edition org** | the metadata to map | free at [developer.salesforce.com](https://developer.salesforce.com) |
| **An Anthropic API key** | the AI layer | the capabilities call Claude |
| VS Code | *(optional)* the in-editor experience | for the extension |
| Claude Desktop / Claude Code / Augment AI | *(optional)* natural-language access | for the MCP server |

---

## Install — step by step

### 1. Get the code

```bash
git clone https://github.com/vedaarvindkaja/salesforce-ai-assistant.git
cd salesforce-ai-assistant/backend
pip install -r requirements.txt
```

### 2. Create a Salesforce connected app (one-time, ~10 min)

In your dev org: **Setup → App Manager → New External Client App**.

- Enable OAuth.
- Callback URL: `http://localhost:8000/auth/callback`
- Scopes: `api`, `refresh_token`, `id`
- Enable **PKCE** and **Refresh Token Rotation**.
- Save, then **wait ~10 minutes** for Salesforce to propagate it.
- Copy the **Consumer Key** and **Consumer Secret** (Manage Consumer Details).

### 3. Configure your environment

```bash
cp .env.example .env
```

Edit `.env`:

- `SALESFORCE_CLIENT_ID` = your Consumer Key
- `SALESFORCE_CLIENT_SECRET` = your Consumer Secret
- `ANTHROPIC_API_KEY` = your Anthropic key
- `USE_MOCK_DATA=false` (use your real org)

### 4. Start the server

```bash
uvicorn app.main:app --reload
```

It runs at `http://localhost:8000`. The startup log prints `REAL` or `MOCK` so you
can confirm the mode.

### 5. Authenticate with Salesforce (one-time)

With the server running, open **`http://localhost:8000/auth/login`** in a browser
and approve access. You'll be redirected back and `tokens.json` is written —
you're connected.

### 6. Build the graph

This extracts your org's Apex, triggers, and Flows into the local cache — what the
graph is built from. From `backend/` (the server can stay running; use a new
terminal):

```bash
python -m scripts.extract_to_cache
```

It makes ~5–8 API calls and prints what it cached. Run it once; re-run when your
org's metadata changes.

### 7. Confirm it's ready

Open **`http://localhost:8000/api/v1/graph`** — you should see your node/edge
counts (e.g. `57 nodes / 172 edges`). If you see `503`, the graph isn't built —
re-check step 6.

---

## Ask your first question

Fastest path — the CLI, from `backend/`:

```bash
python ask_cli.py --mode impact "What breaks if I change the Opportunity object?"
```

The answer streams into your terminal, with the dependency path traced through
your org. That's it — you're using it.

---

## Ways to ask

There are **four ways to ask — one per transport** — all backed by the same graph.

### 1. CLI

```bash
python ask_cli.py --mode <mode> "<your question>"
```

Modes: `qa`, `apex`, `soql`, `impact`, `debuglog`. For `debuglog`, point at a log
file:

```bash
python ask_cli.py --mode debuglog --log path/to/debug.log "why did this fail?"
```

The quickest way to a first answer; nothing to install beyond the backend.

### 2. VS Code extension (the visual way)

Install `vscode-extension/salesforce-graph-0.1.0.vsix` (Extensions panel → **⋯ →
Install from VSIX…**). With the backend running, a status-bar **`SF Graph`** item
shows your node/edge count (or `not ready` / `offline`). Three entry points:

- **Command Palette** (`Ctrl+Shift+P` → type `Salesforce Graph:`) — **Ask**,
  **Generate SOQL**, **Check API Connection**.
- **Right-click in the editor** — open a `.cls`/`.trigger` and choose **Explain
  Current Apex File** or **Deployment Impact of Current File**; open a `.log` and
  choose **Analyze Debug Log File**. The open file *is* the context — no typing.
- **Status bar** — click the `SF Graph` item to re-check the connection.

Answers stream into a **"Salesforce Graph" panel** as formatted Markdown (a
"Thinking…" pulse until the first token). Settings: `salesforceGraph.apiBaseUrl`
(default `http://127.0.0.1:8000`) and `salesforceGraph.renderer` (`webview` or
`output`).

### 3. REST API (try it in the browser)

With the server running, open **`http://localhost:8000/docs`** (interactive
OpenAPI). Expand a route, e.g. `POST /api/v1/deployment-impact` → **Try it out** →
enter `{"question": "..."}` → **Execute**, and watch the SSE stream. Or `curl` it
directly — see [`rest-api.md`](rest-api.md).

### 4. MCP server (natural language in your AI client)

Add the server to Claude Desktop / Claude Code / Augment AI (per-client config in
[`mcp-server.md`](mcp-server.md)), then just ask in plain English in the chat:

> Using the metadata graph, what's the deployment impact of changing the
> Opportunity object?

The host calls the graph tools and answers inline — it feels like talking to an
assistant that happens to know your org.

---

## Good first questions

| Capability | Try |
|---|---|
| Metadata Q&A | *"What references `PricingService`?"* |
| Apex explanation | open a trigger → right-click → **Explain Current Apex File** |
| SOQL generation | *"Opportunities created last quarter for accounts with no contacts."* |
| Deployment impact | *"What breaks if I change the Opportunity object?"* |
| Debug-log analysis | open a `.log` → right-click → **Analyze Debug Log File** |

---

## Troubleshooting

- **`503 "metadata graph not loaded"`** — the graph isn't built. Run
  `python -m scripts.extract_to_cache` (step 6).
- **Status bar shows `offline` / connection refused** — the backend isn't running.
  Start it: `uvicorn app.main:app --reload`.
- **"No tokens" / auth errors** — visit `http://localhost:8000/auth/login` (step 5).
- **Capabilities don't work in mock mode** — `USE_MOCK_DATA` only affects the
  legacy account endpoints; the graph always needs real OAuth + the extracted
  cache. Set `USE_MOCK_DATA=false` and complete steps 5–6.
- **MCP-specific issues** (server "disconnected", path/cwd) — see
  [`mcp-server.md`](mcp-server.md), which has a full troubleshooting section.

---

For the platform overview see the [project README](../README.md); for the HTTP API
see [`rest-api.md`](rest-api.md); for how it all fits together see
[`architecture.md`](architecture.md).
