# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in TaijiOS, please report it responsibly.

**Do NOT open a public issue.**

Instead, please email: **yangfei222666-9** (via GitHub private message or issue with `[SECURITY]` prefix).

We will acknowledge your report within 72 hours and provide a detailed response within 7 days.

## Scope

The following are in scope:
- Secret leakage (API keys, tokens, credentials in source code)
- Code injection vulnerabilities
- Unsafe file operations or path traversal
- Authentication/authorization bypass in the LLM Gateway
- Safe Click gate bypass (executing clicks without all 4 gates passing)

## Out of Scope

- Vulnerabilities in third-party dependencies (report upstream)
- Social engineering attacks
- Denial of service attacks on local-only components

## Security Design

TaijiOS follows these security principles:

| Principle | Implementation |
|-----------|---------------|
| No hardcoded secrets | All credentials via `os.environ.get()` or `secret_manager.py` |
| Default deny | Safe Click requires all 4 gates to pass before execution |
| Audit trail | Every LLM call, click decision, and task state change is logged |
| Gate everything | External knowledge enters mainline only after human review |
| Graceful degradation | Components fall back to safe defaults, never crash the system |

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
