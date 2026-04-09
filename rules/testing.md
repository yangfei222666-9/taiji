# Testing Rules

## Baseline

- 128+ local tests, 68%+ coverage
- New features must not lower the coverage baseline
- All tests must pass before merge

## Principles

- Tests run locally without Redis, LLM, or network dependencies
- Use `tmp_path` and `monkeypatch` for isolation, never touch real state
- Mock external services (LLM, webhook, task queue), test logic directly
- Fix timestamps in time-sensitive tests, don't rely on wall clock

## Running

```bash
python -m pytest tests/ -v
python -m pytest tests/ -q --cov=aios --cov-report=term-missing
```

## PR Checklist

- [ ] All existing tests pass
- [ ] New code has corresponding tests
- [ ] Coverage does not drop below baseline
