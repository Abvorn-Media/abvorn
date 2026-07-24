# Python Security
- Secrets: `os.environ[]` via `abvorn.core.secrets.load_secrets()` — never hardcode
- SQL injection: use parameterized queries (`?` placeholders), never f-strings
- Input validation: sanitize all user/external inputs at boundaries
- No `eval()`, `exec()`, or `pickle.load()` on untrusted data
- Bandit: `bandit -r abvorn/`