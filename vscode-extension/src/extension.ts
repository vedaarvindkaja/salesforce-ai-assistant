import * as vscode from "vscode";

export function activate(context: vscode.ExtensionContext): void {
  const disposable = vscode.commands.registerCommand(
    "salesforceGraph.ask",
    () => {
      vscode.window.showInformationMessage(
        "Salesforce Graph extension is alive."
      );
    }
  );

  context.subscriptions.push(disposable);
}

export function deactivate(): void {
  // No-op: disposables in context.subscriptions are cleaned up by the host.
}
