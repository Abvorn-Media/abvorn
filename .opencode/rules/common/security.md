# Security
- Pre-commit checklist: no hardcoded secrets, input validation, SQL injection prevention, XSS prevention, no sensitive data in errors
- Secret management: env vars with `python-dotenv` only, validate at startup
- Never commit API keys, tokens, credentials — use `load_secrets()` from `abvorn.core.secrets`
- No `except: pass` — every error path must log or escalate
- Bandit scanning: `bandit -r abvorn/`