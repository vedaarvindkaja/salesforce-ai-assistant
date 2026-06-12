# Contributing to Salesforce Graph

Thanks for your interest. This is an open-source (MIT) developer tool — an AI
metadata graph for Salesforce. Contributions are welcome; this guide covers how
to get set up, the conventions the codebase follows, and how to propose changes.

## Before you start

- This is **Phase 1** — a focused, portfolio-stage project: five capabilities,
  four transports, single-user / local. The scope is deliberately tight (see the
  README's *Project status*). Bug fixes, documentation, tests, and small
  improvements are the easiest contributions to land.
- For anything larger — a new capability, a new transport, the hosted/multi-user
  direction — **open an issue first** so we can discuss whether it fits Phase 1
  or belongs in the Phase 2+ backlog.
- Significant design decisions are recorded as ADRs in [`docs/decisions/`](docs/decisions/).
  If you're changing something architectural, read the relevant ADR first; if your
  change makes a real trade-off, propose a new one.

## Dev setup

**Backend (Python 3.11+):**

```bash
git clone https://github.com/vedaarvindkaja/salesforce-ai-assistant.git
cd salesforce-ai-assistant/backend
pip install -r requirements.txt
```

Then follow [`docs/usage.md`](docs/usage.md) to connect an org and build the
graph — you'll need a Salesforce Developer org and an Anthropic API key. Mock mode
(`USE_MOCK_DATA=true`) covers the legacy account endpoints, but the capabilities
need a real, extracted graph.

**Extension (TypeScript):**

```bash
cd vscode-extension
npm install
```

Use the scripts in `package.json` — an esbuild bundle plus a `tsc` typecheck for
the build, and `npm test` for the vitest suite (the pure SSE parser).

## Running tests

From `backend/`:

```bash
python -m pytest
```

Use `python -m pytest` (not bare `pytest`) so `backend/` is on `sys.path`. The
semantic **eval harness** (`evals/`) is excluded from the default suite — it makes
real Claude API calls (a few cents per run), so it's a regression check you run
when you change a capability's prompt or tools, not part of CI.

Extension: `npm test` from `vscode-extension/` (vitest).

## Conventions

- **Layered architecture (ADR-001).** `salesforce/` → `intelligence/` →
  `interfaces/`, each depending only *downward*. A transport shouldn't know
  Salesforce internals; the graph shouldn't know about transports.
- **Single source of truth.** Capabilities are declared once in `capabilities.py`
  (`CAPABILITY_REGISTRY`); the graph loads through one `bootstrap.load_graph`; edge
  labels live in `naming.py`. Add to the source — don't duplicate.
- **No stubs.** A capability ships when it works end-to-end, or it doesn't ship.
  Quality over breadth.
- **Tests travel with changes.** New behavior → a unit test. A capability or prompt
  change → run the evals.
- **ADRs for real decisions.** If a change carries a genuine trade-off with
  long-term consequences, add an ADR (see `docs/decisions/` for the format and the
  "is this ADR-worthy?" bar).
- **Code style.** Python: type hints, Pydantic models, async (`httpx`/`asyncio`).
  TypeScript: the REST client and SSE parser stay runtime-`vscode`-free and
  unit-tested.

## Proposing a change

1. For non-trivial changes, **open an issue first** (templates provided).
2. Fork, branch, and make the change **with tests**.
3. Run `python -m pytest` (backend) and `npm test` (extension) — green before you
   push.
4. Open a PR describing *what* changed and *why*, and link the issue. If it touches
   architecture, reference the ADR (existing or new).

## Reporting bugs and requesting features

Use the issue templates. For a bug, include the **transport** (CLI / MCP / REST /
extension), what you ran, and expected vs. actual. For anything security-related,
see [`SECURITY.md`](SECURITY.md) — please don't open a public issue.

## Code of conduct

Be respectful and constructive, and assume good faith. This is a small project run
by one maintainer; thoughtful, well-scoped contributions are the ones that land.
