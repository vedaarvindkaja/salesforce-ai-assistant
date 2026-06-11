import * as vscode from "vscode";

import { fetchGraphSummary, streamCapability } from "./client";
import {
  OutputChannelRenderer,
  Renderer,
  WebviewRenderer,
} from "./renderer";

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

function getApiBaseUrl(): string {
  const configured = vscode.workspace
    .getConfiguration("salesforceGraph")
    .get<string>("apiBaseUrl");
  return configured && configured.trim() ? configured.trim() : DEFAULT_BASE_URL;
}

/** Readiness probe (Day 2): report each of the three API states to the user. */
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

/** Ask a metadata-graph question and stream the answer to the chosen renderer. */
async function askMetadataQuestion(
  webviewRenderer: WebviewRenderer,
  outputRenderer: OutputChannelRenderer
): Promise<void> {
  const question = await vscode.window.showInputBox({
    title: "Salesforce Graph: Ask",
    prompt: "Ask a question about your org's metadata graph.",
    placeHolder: "Which Apex classes reference AccountTriggerHandler?",
    ignoreFocusOut: true,
  });
  const trimmed = question?.trim();
  if (!trimmed) {
    return;
  }

  // Same SSE stream, renderer chosen at runtime — the seam made tangible.
  const choice = vscode.workspace
    .getConfiguration("salesforceGraph")
    .get<string>("renderer");
  const renderer: Renderer =
    choice === "output" ? outputRenderer : webviewRenderer;

  const baseUrl = getApiBaseUrl();
  renderer.start(`Q: ${trimmed}`);

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Asking the metadata graph...",
      cancellable: true,
    },
    async (_progress, token) => {
      const controller = new AbortController();
      token.onCancellationRequested(() => controller.abort());
      await streamCapability(
        baseUrl,
        "/api/v1/metadata-qa",
        { question: trimmed },
        renderer,
        controller.signal
      );
    }
  );
}

export function activate(context: vscode.ExtensionContext): void {
  const channel = vscode.window.createOutputChannel("Salesforce Graph");
  const outputRenderer = new OutputChannelRenderer(channel);
  const webviewRenderer = new WebviewRenderer(context.extensionUri);

  const ask = vscode.commands.registerCommand("salesforceGraph.ask", () =>
    askMetadataQuestion(webviewRenderer, outputRenderer)
  );
  const connection = vscode.commands.registerCommand(
    "salesforceGraph.checkConnection",
    checkConnection
  );

  context.subscriptions.push(channel, ask, connection);
}

export function deactivate(): void {
  // No-op: disposables in context.subscriptions are cleaned up by the host.
}
