# Security Policy

## Supported versions

This is a Phase 1, single-user / local project (currently `v0.1.0`). Security
fixes are applied to the latest `main`.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Use GitHub's private vulnerability reporting: the repository's **Security** tab →
**Report a vulnerability**. (If that isn't available, contact the maintainer via
their GitHub profile.) You'll get an acknowledgement; please allow time to
investigate and patch before any public disclosure.

## How this project handles secrets

- **Nothing secret is committed.** OAuth tokens (`tokens.json`) and the `.env`
  file — which holds your Salesforce Consumer Secret and your Anthropic API key —
  are gitignored. Never commit them.
- **It runs locally.** The backend runs on your machine; the metadata cache
  (SQLite) and OAuth tokens stay local.
- **Where data goes.** The only outbound calls are to your Salesforce org's APIs
  (to extract metadata) and to the Anthropic API (to answer queries). No third
  party hosts your data.
- **No caller auth yet.** Phase 1 is single-user; the REST API gates only on graph
  readiness (`503`), not caller identity. Don't expose the local API to an
  untrusted network. API-key auth is planned for the multi-user phase.

## If you've exposed a credential

Rotate it immediately: regenerate the Connected App's **Consumer Secret** in
Salesforce, and rotate your **Anthropic API key** in the Anthropic console.
