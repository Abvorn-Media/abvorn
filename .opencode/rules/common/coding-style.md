# Coding Style
- **Immutability:** always create new objects, never mutate in place
- KISS, DRY, YAGNI — prefer small focused files (200-400 lines, 800 max)
- Error handling: explicit at every level, log server-side, user-friendly in UI
- Input validation: at boundaries, schema-based, fail fast
- Naming: `snake_case` for Python vars/fns, `PascalCase` for classes, `UPPER_SNAKE` for constants
- Smells: deep nesting (>4 levels), magic numbers, long functions (>50 lines)
- Type annotations on all function signatures (Python)