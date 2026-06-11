import * as vscode from "vscode";

import { fetchGraphSummary } from "./client";

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

/** Read the configured API base URL, falling back to the default. */
function getApiBaseUrl(): string {
  const configured = vscode.workspace
    .getConfiguration("salesforceGraph")
    .get<string>("apiBaseUrl");
  return configured && configured.trim() ? configured.trim() : DEFAULT_BASE_URL;
}

/** Run the readiness probe and report each of the three states to the user. */
async function checkConnection(): Promise<void> {
  const baseUrl = getApiBaseUrl();

  const result = await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: `Checking Salesforce Graph API at ${baseUrl}...`,
    },
    () => fetchGraphSummary(baseUrl)
  );

  switch (result.status) {
    case "ready": {
      const { node_count, edge_count, org_key } = result.summary;
      vscode.window.showInformationMessage(
        `Connected to ${org_key} — ${node_count} nodes / ${edge_count} edges.`
      );
      break;
    }
    case "not-ready":
      vscode.window.showWarningMessage(
        `API is up but the graph isn't loaded (${result.detail}). ` +
          `Build/load the graph, then retry.`
      );
      break;
    case "unreachable":
      vscode.window.showErrorMessage(
        `Can't reach the Salesforce Graph API at ${baseUrl}. ` +
          `Start it from backend/ with: uvicorn app.main:app --reload  ` +
          `(${result.detail})`
      );
      break;
    case "http-error":
      vscode.window.showErrorMessage(
        `Unexpected response from the API: ${result.detail}`
      );
      break;
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const ask = vscode.commands.registerCommand("salesforceGraph.ask", () => {
    vscode.window.showInformationMessage("Salesforce Graph extension is alive.");
  });

  const connection = vscode.commands.registerCommand(
    "salesforceGraph.checkConnection",
    checkConnection
  );

  context.subscriptions.push(ask, connection);
}

export function deactivate(): void {
  // No-op: disposables in context.subscriptions are cleaned up by the host.
}
