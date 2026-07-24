# Testing
- Minimum 80% coverage; unit + integration tests required
- TDD workflow: RED (write failing test) → GREEN (make pass) → IMPROVE (refactor)
- Use `pytest` with `pytest --cov=abvorn --cov-report=term-missing`
- AAA pattern: Arrange-Act-Assert
- Descriptive test names explaining behavior under test
- Test categorization via `pytest.mark` (unit, integration, e2e)
- Run full suite before commits: `pytest tests/ -v`