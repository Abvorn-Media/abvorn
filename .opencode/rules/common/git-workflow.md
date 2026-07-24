# Git Workflow
- Commit format: `<type>: <description>` (types: feat, fix, refactor, docs, test, chore, perf, ci)
- Types: `feat:` for features, `fix:` for bugs, `refactor:` for restructuring, `test:` for tests
- Review full diff before committing: `git diff` + `git status`
- Never commit secrets, debug statements, or commented-out code
- PR workflow: use `git diff main...HEAD` for comprehensive summary