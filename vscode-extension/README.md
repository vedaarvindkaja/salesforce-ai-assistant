# Salesforce Graph (VS Code extension)

In-editor access to the Salesforce AI metadata-graph intelligence platform. Ask
questions about your org's metadata dependency graph — and explain Apex, assess
deployment impact, generate SOQL, and root-cause debug logs — without leaving
the editor. Answers stream live from the local REST API and render as formatted
Markdown.

## Requirements

The Salesforce Graph REST API must be running locally. From the project's
`backend/` directory:

```
uvicorn app.main:app --reload
```

The extension talks to it at `http://127.0.0.1:8000` by default.

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
