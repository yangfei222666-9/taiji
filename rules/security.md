# Security Rules

## Red Lines

- Never commit API keys, tokens, or credentials
- Secrets only via `os.environ.get()` or `secret_manager.py`
- No hardcoded absolute paths — use `Path(__file__).parent` or env vars

## Injection Prevention

- Experience injection is manifest-only: content must come from indexed entries, not raw user input
- LLM prompt injection: strip BOM, zero-width chars, markdown fences before parsing
- No `eval()`, `exec()`, or `subprocess.run(shell=True)` with untrusted input

## Evidence and Audit

- All artifacts (plan, scores, frames) must have SHA256 provenance
- Evidence is auditable but must not expose secrets or PII
- Run traces include reason_codes, not raw error messages with credentials

## CI Gate

- `secret_scan.py` runs on every PR
- PRs with detected secrets are blocked automatically
