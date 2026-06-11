// Build script (esbuild) — two bundles:
//   1) dist/extension.js  — the Node extension host (vscode is external)
//   2) dist/webview.js     — the browser-context webview script (marked bundled)
const esbuild = require("esbuild");

const watch = process.argv.includes("--watch");
const production = process.argv.includes("--production");

const extensionConfig = {
  entryPoints: ["src/extension.ts"],
  bundle: true,
  format: "cjs",
  platform: "node",
  target: "node20",
  outfile: "dist/extension.js",
  external: ["vscode"],
  sourcemap: !production,
  minify: production,
  logLevel: "info",
};

const webviewConfig = {
  entryPoints: ["src/webview/main.ts"],
  bundle: true,
  format: "iife",
  platform: "browser",
  target: "es2020",
  outfile: "dist/webview.js",
  sourcemap: !production,
  minify: production,
  logLevel: "info",
};

async function main() {
  const configs = [extensionConfig, webviewConfig];
  if (watch) {
    const ctxs = await Promise.all(configs.map((c) => esbuild.context(c)));
    await Promise.all(ctxs.map((c) => c.watch()));
    console.log("esbuild: watching for changes...");
  } else {
    await Promise.all(configs.map((c) => esbuild.build(c)));
    console.log("esbuild: build complete -> dist/extension.js + dist/webview.js");
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
