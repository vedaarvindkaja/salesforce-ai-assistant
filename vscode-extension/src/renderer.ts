import * as vscode from "vscode";

/**
 * The rendering seam. The streaming layer (client.ts) depends on THIS interface,
 * never on a concrete UI — so swapping the OutputChannel for a webview later
 * (Day 4) is a renderer change, not a plumbing rewrite (dependency inversion).
 * The four methods map onto the SSE lifecycle: a stream starts, emits chunks,
 * then either completes (done) or fails (error).
 */
export interface Renderer {
  start(title: string): void;
  appendChunk(text: string): void;
  done(): void;
  error(message: string): void;
}

/** Renders a streamed answer into a VS Code OutputChannel (the Day-3 surface). */
export class OutputChannelRenderer implements Renderer {
  constructor(private readonly channel: vscode.OutputChannel) {}

  start(title: string): void {
    this.channel.clear();
    this.channel.appendLine(title);
    this.channel.appendLine("-".repeat(title.length));
    this.channel.show(true); // preserveFocus: keep the cursor in the editor
  }

  appendChunk(text: string): void {
    this.channel.append(text); // fragments concatenate into flowing text
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
