# Contributing to TaijiOS

Thanks for your interest in contributing.

## Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `python -m pytest tests/`
5. Submit a pull request

## Code Guidelines

- Use `Path(__file__).parent` for relative paths, never hardcode absolute paths
- Use `os.environ.get()` for secrets, never commit credentials
- Use `sys.executable` instead of hardcoded Python paths
- Follow existing patterns in the module you're modifying
- Add structured logging for observable operations

## Security

- Never commit API keys, tokens, or credentials
- Use `secret_manager.py` for all secret access
- Report security issues privately (see [SECURITY.md](SECURITY.md))

## Architecture

See [README.md](README.md) for the system architecture diagram.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
