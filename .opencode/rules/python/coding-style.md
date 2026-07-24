# Python Coding Style
- PEP 8 compliant; type annotations on ALL function signatures
- Immutability: `@dataclass(frozen=True)`, `NamedTuple` for data objects
- Formatting: `black` + `isort` + `ruff`
- Use `logging` not `print()`; use context managers for resources
- Prefer `pathlib.Path` over `os.path`; use `sqlite3` with `contextmanager` for connections
- References: `python-patterns` skill