# Python Testing
- Framework: `pytest` with `pytest-cov`
- Coverage: `pytest --cov=abvorn --cov-report=term-missing`
- Test categorization: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`
- Async tests: use `asyncio.run()` or `pytest-asyncio`
- Mock external APIs (OpenAI, GitHub, etc.) in unit tests
- TDD: RED → GREEN → IMPROVE cycle