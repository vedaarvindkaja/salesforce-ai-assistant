import * as vscode from "vscode";

import {
  fetchGraphSummary,
  streamCapability,
  type ProbeResult,
  type RequestBody,
} from "./client";
import {
  OutputChannelRenderer,
  type Renderer,
  WebviewRenderer,
} from "./renderer";

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";
const APEX_EXTENSIONS = [".cls", ".trigger"];

function getApiBaseUrl(): string {
  const configured = vscode.workspace
    .getConfiguration("salesforceGraph")
    .get<string>("apiBaseUrl");
  return configured && configured.trim() ? configured.trim() : DEFAULT_BASE_URL;
}

function pickRenderer(
  webview: WebviewRenderer,
  output: OutputChannelRenderer
): Renderer {
  const choice = vscode.workspace
    .getConfiguration("salesforceGraph")
    .get<string>("renderer");
  return choice === "output" ? output : webview;
}

// ---------------------------------------------------------------------------
// Editor-context input sources
// ---------------------------------------------------------------------------

function activeApexName(): string | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return undefined;
  }
  const p = editor.document.uri.fsPath;
  const ext = APEX_EXTENSIONS.find((e) => p.toLowerCase().endsWith(e));
  if (!ext) {
    return undefined;
  }
  const base = p.split(/[\\/]/).pop() ?? "";
  return base.slice(0, base.length - ext.length);
}

function activeLogPath(): string | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.uri.scheme !== "file") {
    return undefined;
  }
  const p = editor.document.uri.fsPath;
  return p.toLowerCase().endsWith(".log") ? p : undefined;
}

// ---------------------------------------------------------------------------
// Shared capability runner — every command funnels through here.
// ---------------------------------------------------------------------------

async function runCapability(
  renderer: Renderer,
  title: string,
  path: string,
  body: RequestBody
): Promise<void> {
  const baseUrl = getApiBaseUrl();
  renderer.start(title);

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Querying the metadata graph...",
      cancellable: true,
    },
    async (_progress, token) => {
      const controller = new AbortController();
      token.onCancellationRequested(() => controller.abort());
      await streamCapability(baseUrl, path, body, renderer, controller.signal);
      if (token.isCancellationRequested) {
        // Aborted streams don't emit a `done` event, so finalize the indicator.
        renderer.appendChunk("\n\n_(stopped)_");
        renderer.done();
      }
    }
  );
}

// ---------------------------------------------------------------------------
// Status bar
// ---------------------------------------------------------------------------

function updateStatusItem(item: vscode.StatusBarItem, result: ProbeResult): void {
  const warn = new vscode.ThemeColor("statusBarItem.warningBackground");
  switch (result.status) {
    case "ready":
      item.text = `$(database) SF Graph: ${result.summary.node_count}/${result.summary.edge_count}`;
      item.tooltip = `Connected to ${result.summary.org_key}`;
      item.backgroundColor = undefined;
      break;
    case "not-ready":
      item.text = "$(database) SF Graph: not ready";
      item.tooltip = "API is up but the graph isn't loaded (503). Click to retry.";
      item.backgroundColor = warn;
      break;
    default:
      item.text = "$(database) SF Graph: offline";
      item.tooltip = "API unreachable. Start uvicorn, then click to retry.";
      item.backgroundColor = warn;
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const channel = vscode.window.createOutputChannel("Salesforce Graph");
  const outputRenderer = new OutputChannelRenderer(channel);
  const webviewRenderer = new WebviewRenderer(context.extensionUri);
  const renderer = () => pickRenderer(webviewRenderer, outputRenderer);

  const statusItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100
  );
  statusItem.command = "salesforceGraph.checkConnection";
  statusItem.text = "$(database) SF Graph";
  statusItem.tooltip = "Check the Salesforce Graph API connection";
  statusItem.show();
  // Quiet initial probe so the status reflects reality on activation.
  void fetchGraphSummary(getApiBaseUrl()).then((r) => updateStatusItem(statusItem, r));

  // qa — free-text question.
  const ask = vscode.commands.registerCommand("salesforceGraph.ask", async () => {
    const q = await vscode.window.showInputBox({
      title: "Salesforce Graph: Ask",
      prompt: "Ask a question about your org's metadata graph.",
      placeHolder: "Which Apex classes reference AccountTriggerHandler?",
      ignoreFocusOut: true,
    });
    const trimmed = q?.trim();
    if (!trimmed) {
      return;
    }
    await runCapability(renderer(), `Q: ${trimmed}`, "/api/v1/metadata-qa", {
      question: trimmed,
    });
  });

  // apex — explain the active Apex file.
  const explainApex = vscode.commands.registerCommand(
    "salesforceGraph.explainApex",
    async () => {
      const name = activeApexName();
      if (!name) {
        vscode.window.showWarningMessage(
          "Open an Apex .cls or .trigger file first, then run Explain Current Apex File."
        );
        return;
      }
      await runCapability(
        renderer(),
        `Explain Apex: ${name}`,
        "/api/v1/apex-explain",
        { question: `Explain the Apex ${name}, including its dependencies.` }
      );
    }
  );

  // impact — deployment impact of the active Apex component.
  const deploymentImpact = vscode.commands.registerCommand(
    "salesforceGraph.deploymentImpact",
    async () => {
      const name = activeApexName();
      if (!name) {
        vscode.window.showWarningMessage(
          "Open an Apex .cls or .trigger file first, then run Deployment Impact of Current File."
        );
        return;
      }
      await runCapability(
        renderer(),
        `Impact: ${name}`,
        "/api/v1/deployment-impact",
        { question: `What is the deployment impact of changing ${name}?` }
      );
    }
  );

  // soql — free-text description.
  const generateSoql = vscode.commands.registerCommand(
    "salesforceGraph.generateSoql",
    async () => {
      const desc = await vscode.window.showInputBox({
        title: "Salesforce Graph: Generate SOQL",
        prompt: "Describe the query you want.",
        placeHolder: "All open Opportunities with an amount over 50000, newest first",
        ignoreFocusOut: true,
      });
      const trimmed = desc?.trim();
      if (!trimmed) {
        return;
      }
      await runCapability(
        renderer(),
        `SOQL: ${trimmed}`,
        "/api/v1/soql-generate",
        { question: trimmed }
      );
    }
  );

  // debuglog — analyze the active .log file (path is server-readable: same machine).
  const analyzeDebugLog = vscode.commands.registerCommand(
    "salesforceGraph.analyzeDebugLog",
    async () => {
      const logPath = activeLogPath();
      if (!logPath) {
        vscode.window.showWarningMessage(
          "Open a Salesforce debug .log file first, then run Analyze Debug Log File."
        );
        return;
      }
      const name = logPath.split(/[\\/]/).pop() ?? logPath;
      await runCapability(
        renderer(),
        `Debug log: ${name}`,
        "/api/v1/debug-log-analysis",
        { log_path: logPath }
      );
    }
  );

  // Day-2 readiness probe — also refreshes the status bar item.
  const connection = vscode.commands.registerCommand(
    "salesforceGraph.checkConnection",
    async () => {
      const baseUrl = getApiBaseUrl();
      const result = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: `Checking Salesforce Graph API at ${baseUrl}...`,
        },
        () => fetchGraphSummary(baseUrl)
      );
      updateStatusItem(statusItem, result);

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
            `API is up but the graph isn't loaded (${result.detail}). Build/load the graph, then retry.`
          );
          break;
        case "unreachable":
          vscode.window.showErrorMessage(
            `Can't reach the Salesforce Graph API at ${baseUrl}. ` +
              `Start it from backend/ with: uvicorn app.main:app --reload  (${result.detail})`
          );
          break;
        case "http-error":
          vscode.window.showErrorMessage(
            `Unexpected response from the API: ${result.detail}`
          );
          break;
      }
    }
  );

  context.subscriptions.push(
    channel,
    statusItem,
    ask,
    explainApex,
    deploymentImpact,
    generateSoql,
    analyzeDebugLog,
    connection
  );
}

export function deactivate(): void {
  // No-op: disposables in context.subscriptions are cleaned up by the host.
}
