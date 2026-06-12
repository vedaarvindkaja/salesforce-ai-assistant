# Salesforce Graph (VS Code extension)

In-editor access to the [Salesforce Graph platform](https://github.com/vedaarvindkaja/salesforce-ai-assistant)
— the AI metadata-graph intelligence layer for Salesforce developers. Ask
questions about your org's metadata dependency graph — and explain Apex, assess
deployment impact, generate SOQL, and root-cause debug logs — without leaving the
editor. Answers stream live from the local REST API and render as formatted
Markdown.

> This extension is one of four transports over a shared intelligence core. For
> the full picture — the metadata graph, the other transports, and the
> architecture — see the [project README](https://github.com/vedaarvindkaja/salesforce-ai-assistant#readme).

## Requirements

The Salesforce Graph REST API must be running locally, **with a populated
metadata graph**. From the project's `backend/` directory:

```
# one-time: build the graph from your org (see the project README Quickstart)
python -m scripts.extract_to_cache

# then start the API
uvicorn app.main:app --reload
```

The extension talks to it at `http://127.0.0.1:8000` by default. Until the graph
is built, capability calls return a "not ready" (503) state, shown in the status
bar.

## Commands

- **Salesforce Graph: Ask** — ask any question about the metadata graph.
- **Salesforce Graph: Explain Current Apex File** — explain the open `.cls`/`.trigger` with its dependencies. (Also on the editor right-click menu.)
- **Salesforce Graph: Deployment Impact of Current File** — blast-radius of changing the open Apex component.
- **Salesforce Graph: Generate SOQL** — generate a query from a description.
- **Salesforce Graph: Analyze Debug Log File** — root-cause the open `.log` against the graph. (Also on the editor right-click menu.)
- **Salesforce Graph: Check API Connection** — verify the API and show node/edge counts.

A connection indicator also appears in the status bar.

## Settings

- `salesforceGraph.apiBaseUrl` — base URL of the REST API (default `http://127.0.0.1:8000`).
- `salesforceGraph.renderer` — `webview` (formatted Markdown panel) or `output` (raw text channel).

## How it works

Commands stream Server-Sent Events from the REST API and render them through a
single `Renderer` interface, so the webview and output-channel surfaces share
one streaming pipeline.
