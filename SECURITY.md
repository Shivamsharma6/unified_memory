# Security Policy

## Supported Use

UAMS is designed as a local-first memory system. The default deployment binds Qdrant to localhost and stores memories as Markdown files in the vault. Keep the FastAPI service on localhost unless you add authentication and network controls.

## Security Expectations

- Do not expose the FastAPI service publicly without adding authentication, TLS, rate limiting, and network controls.
- Do not store secrets, access tokens, private keys, or raw transcripts in memory notes.
- Treat MCP tools as privileged local tools. Only register UAMS with agents you trust.
- Review generated memories before sharing a vault publicly.
- Keep Qdrant, Python dependencies, and MCP clients updated.

## Reporting Vulnerabilities

Please open a private security advisory on GitHub or contact the maintainer directly. Include:

- affected version or commit,
- reproduction steps,
- expected and actual behavior,
- impact assessment.

## Out Of Scope

- Issues caused by publicly exposing the local API without authentication.
- Secrets intentionally written into the vault by users or agents.
- Prompt-injection behavior from untrusted memory content unless it bypasses documented safety boundaries.
