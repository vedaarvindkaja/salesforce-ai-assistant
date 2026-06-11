// Webview client script. Runs in the webview's isolated browser context (NOT
// the Node extension host), so it has DOM globals but no vscode/node APIs — it
// talks to the host only via message passing. esbuild bundles this (with marked)
// to dist/webview.js; the host loads it via asWebviewUri behind a CSP nonce.

import { marked } from "marked";

declare function acquireVsCodeApi(): { postMessage(msg: unknown): void };

interface InboundMessage {
  type: "start" | "chunk" | "done" | "error";
  title?: string;
  text?: string;
  message?: string;
}

const vscodeApi = acquireVsCodeApi();
const titleEl = document.getElementById("title") as HTMLElement;
const statusEl = document.getElementById("status") as HTMLElement;
const contentEl = document.getElementById("content") as HTMLElement;

marked.setOptions({ gfm: true, breaks: false });

let buffer = "";

window.addEventListener("message", (event: MessageEvent<InboundMessage>) => {
  const msg = event.data;
  switch (msg.type) {
    case "start":
      buffer = "";
      contentEl.innerHTML = "";
      titleEl.textContent = msg.title ?? "Salesforce Graph";
      statusEl.textContent = "Thinking\u2026";
      statusEl.className = "";
      break;
    case "chunk":
      buffer += msg.text ?? "";
      // Re-render the full markdown each chunk: partial markdown (an unclosed
      // code fence, a half-built table) renders imperfectly mid-stream and
      // self-corrects as more text arrives — expected streaming behavior.
      contentEl.innerHTML = marked.parse(buffer) as string;
      window.scrollTo(0, document.body.scrollHeight);
      break;
    case "done":
      statusEl.textContent = "";
      break;
    case "error":
      statusEl.textContent = "Error: " + (msg.message ?? "unknown");
      statusEl.className = "error";
      break;
  }
});

// Signal the host that the listener is wired, so it can flush buffered messages.
vscodeApi.postMessage({ type: "ready" });
