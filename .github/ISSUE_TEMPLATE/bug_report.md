---
name: Bug report
about: Report something that isn't working
title: "[bug] "
labels: bug
---

**Transport** (which surface?)
- [ ] CLI
- [ ] MCP server (host: Claude Desktop / Claude Code / Augment AI?)
- [ ] REST API
- [ ] VS Code extension

**What you did**
The command / question / steps to reproduce.

**What you expected**

**What happened instead**
Include any error message, or the SSE `error` event text.

**Graph state**
Output of `GET /api/v1/graph` (node/edge counts), or note if you got a `503`.

**Environment**
- OS:
- Python version:
- Capability (qa / apex / soql / impact / debuglog):

**Logs**
Relevant server stderr. Never paste tokens, keys, or other secrets.
