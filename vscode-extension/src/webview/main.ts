// Webview client script. Runs in the webview's isolated browser context (DOM,
// no node/vscode), talks to the host only via message passing. esbuild bundles
// this with marked to dist/webview.js; the host loads it behind a CSP nonce.

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

function setStatus(text: string, cls: string): void {
  statusEl.textContent = text;
  statusEl.className = cls;
}

let buffer = "";
let gotChunk = false;

window.addEventListener("message", (event: MessageEvent<InboundMessage>) => {
  const msg = event.data;
  switch (msg.type) {
    case "start":
      buffer = "";
      gotChunk = false;
      contentEl.innerHTML = "";
      titleEl.textContent = msg.title ?? "Salesforce Graph";
      setStatus("Thinking\u2026", "thinking");
      break;
    case "chunk":
      buffer += msg.text ?? "";
      if (!gotChunk) {
        gotChunk = true;
        setStatus("", ""); // the streaming text itself is now the indicator
      }
      // Re-render the full buffer each chunk: partial markdown self-corrects as
      // more text arrives — expected streaming behavior.
      contentEl.innerHTML = marked.parse(buffer) as string;
      window.scrollTo(0, document.body.scrollHeight);
      break;
    case "done":
      setStatus(gotChunk ? "" : "No response.", "");
      break;
    case "error":
      setStatus("Error: " + (msg.message ?? "unknown"), "error");
      break;
  }
});

// Signal the host that the listener is wired, so it can flush buffered messages.
vscodeApi.postMessage({ type: "ready" });
