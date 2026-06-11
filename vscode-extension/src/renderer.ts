import * as vscode from "vscode";

/**
 * The rendering seam. The streaming layer (client.ts) depends on THIS interface,
 * never on a concrete UI — so swapping the OutputChannel for a webview is a
 * renderer change, not a plumbing rewrite (dependency inversion). The four
 * methods map onto the SSE lifecycle: a stream starts, emits chunks, then either
 * completes (done) or fails (error).
 */
export interface Renderer {
  start(title: string): void;
  appendChunk(text: string): void;
  done(): void;
  error(message: string): void;
}

/** Renders a streamed answer into a VS Code OutputChannel (raw text). */
export class OutputChannelRenderer implements Renderer {
  constructor(private readonly channel: vscode.OutputChannel) {}

  start(title: string): void {
    this.channel.clear();
    this.channel.appendLine(title);
    this.channel.appendLine("-".repeat(title.length));
    this.channel.show(true);
  }

  appendChunk(text: string): void {
    this.channel.append(text);
  }

  done(): void {
    this.channel.appendLine("");
    this.channel.appendLine("");
  }

  error(message: string): void {
    this.channel.appendLine("");
    this.channel.appendLine(`[error] ${message}`);
  }
}

/** A message the extension host posts into the webview document. */
interface OutboundMessage {
  type: "start" | "chunk" | "done" | "error";
  title?: string;
  text?: string;
  message?: string;
}

/**
 * Renders a streamed answer into a webview panel with formatted Markdown — the
 * SAME Renderer interface as OutputChannelRenderer, so client.ts is unaware of
 * the difference. Handles the two webview hazards: (1) a strict CSP with a
 * per-load nonce, and (2) the load race — messages posted before the webview's
 * script has registered its listener are dropped, so we buffer until the
 * webview posts {type:"ready"} back, then flush.
 */
export class WebviewRenderer implements Renderer {
  private panel: vscode.WebviewPanel | undefined;
  private ready = false;
  private pending: OutboundMessage[] = [];

  constructor(private readonly extensionUri: vscode.Uri) {}

  start(title: string): void {
    this.ensurePanel();
    this.post({ type: "start", title });
  }

  appendChunk(text: string): void {
    this.post({ type: "chunk", text });
  }

  done(): void {
    this.post({ type: "done" });
  }

  error(message: string): void {
    this.post({ type: "error", message });
  }

  private ensurePanel(): void {
    if (this.panel) {
      this.panel.reveal(vscode.ViewColumn.Beside, true);
      return;
    }
    const panel = vscode.window.createWebviewPanel(
      "salesforceGraph.answer",
      "Salesforce Graph",
      { viewColumn: vscode.ViewColumn.Beside, preserveFocus: true },
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.joinPath(this.extensionUri, "dist")],
      }
    );

    this.ready = false;
    this.pending = [];

    panel.webview.onDidReceiveMessage((msg: { type?: string }) => {
      if (msg?.type === "ready") {
        this.ready = true;
        for (const m of this.pending) {
          void panel.webview.postMessage(m);
        }
        this.pending = [];
      }
    });

    panel.onDidDispose(() => {
      this.panel = undefined;
      this.ready = false;
      this.pending = [];
    });

    panel.webview.html = this.html(panel.webview);
    this.panel = panel;
  }

  private post(msg: OutboundMessage): void {
    if (this.panel && this.ready) {
      void this.panel.webview.postMessage(msg);
    } else {
      this.pending.push(msg);
    }
  }

  private html(webview: vscode.Webview): string {
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, "dist", "webview.js")
    );
    const nonce = makeNonce();
    const csp = [
      "default-src 'none'",
      `img-src ${webview.cspSource} https: data:`,
      `style-src ${webview.cspSource} 'unsafe-inline'`,
      `script-src 'nonce-${nonce}'`,
    ].join("; ");

    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy" content="${csp}" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Salesforce Graph</title>
<style>
  body { font-family: var(--vscode-font-family); color: var(--vscode-editor-foreground);
         padding: 0 18px 28px; line-height: 1.55; }
  h1#title { font-size: 1.05rem; font-weight: 600; position: sticky; top: 0;
             background: var(--vscode-editor-background); padding: 14px 0 8px;
             border-bottom: 1px solid var(--vscode-panel-border); }
  #status { font-size: 0.85rem; color: var(--vscode-descriptionForeground);
            margin: 10px 0 16px; min-height: 1em; }
  #status.error { color: var(--vscode-errorForeground); }
  #content pre { background: var(--vscode-textCodeBlock-background); padding: 12px;
                 border-radius: 4px; overflow-x: auto; }
  #content code { font-family: var(--vscode-editor-font-family); font-size: 0.92em; }
  #content table { border-collapse: collapse; margin: 10px 0; }
  #content th, #content td { border: 1px solid var(--vscode-panel-border);
                             padding: 5px 12px; text-align: left; }
  #content th { background: var(--vscode-editorWidget-background); }
  #content a { color: var(--vscode-textLink-foreground); }
  #content blockquote { border-left: 3px solid var(--vscode-panel-border);
                        margin: 10px 0; padding-left: 12px;
                        color: var(--vscode-descriptionForeground); }
</style>
</head>
<body>
  <h1 id="title">Salesforce Graph</h1>
  <div id="status"></div>
  <div id="content"></div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }
}

function makeNonce(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let text = "";
  for (let i = 0; i < 32; i++) {
    text += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return text;
}
